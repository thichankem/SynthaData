"""Lớp điều phối: sinh dữ liệu song song nhiều luồng + QA liên tục.

Mỗi worker: gọi model -> trích JSON -> đẩy CẢ LÔ qua dây chuyền QA
(`QualityPipeline.process_batch`, gồm cả nhúng embedding theo lô) -> trả về các
dòng hợp lệ. Luồng chính chỉ việc ghi CSV + in giám sát. Có cơ chế SINH THÍCH
ỨNG: khi tỉ lệ chấp nhận gần đây tụt thấp (chủ đề sắp cạn / model lặp), tự tăng
nhiệt độ để đẩy đa dạng.
"""

from __future__ import annotations

import itertools
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .config import GenerationConfig, QualityConfig
from .prompts import build_system_prompt, build_user_prompt
from .providers.base import LLMProvider
from .quality.dedup import DedupRegistry
from .quality.monitor import QualityMonitor
from .quality.pipeline import build_pipeline
from .schema import Domain
from .utils import coerce_records, extract_json, salvage_records
from .writer import CsvWriter

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


@dataclass
class GenerationOutcome:
    accepted_this_run: int
    total_rows: int
    elapsed_sec: float
    calls: int
    report: QualityMonitor       # monitor đóng vai báo cáo cuối
    stalled: bool


class DataGenerator:
    def __init__(self, provider: LLMProvider, domain: Domain,
                 gen_cfg: GenerationConfig, writer: CsvWriter,
                 embedder=None, quality_cfg: QualityConfig | None = None,
                 on_progress=None, stop_event=None, show_bar: bool = True,
                 phase2_provider: LLMProvider | None = None, seed_rows: int = 0):
        self.provider = provider
        self.domain = domain
        self.cfg = gen_cfg
        self.writer = writer
        self.qcfg = quality_cfg or QualityConfig()
        # CHẾ ĐỘ augment: sinh `seed_rows` dòng "hạt giống" bằng `provider` (API)
        # rồi TỰ CHUYỂN sang `phase2_provider` (Ollama offline) cho phần còn lại.
        self.phase2_provider = phase2_provider
        self.seed_rows = seed_rows
        self._phase = 1
        # Tuỳ chọn cho GUI / tích hợp khác (CLI để mặc định -> không đổi hành vi):
        #   on_progress(total, target, rejected, temperature) gọi mỗi lần cập nhật.
        #   stop_event: threading.Event -> set để dừng sớm an toàn.
        #   show_bar=False -> tắt thanh tqdm (GUI tự hiển thị tiến trình).
        self.on_progress = on_progress
        self.stop_event = stop_event
        self.show_bar = show_bar

        self.registry = DedupRegistry(
            fuzzy_threshold=self.qcfg.fuzzy_threshold,
            semantic_threshold=self.qcfg.semantic_threshold,
            semantic_enabled=self.qcfg.semantic_enabled and embedder is not None,
        )
        self.monitor = QualityMonitor(
            domain, rolling_window=self.qcfg.rolling_window,
            monitor_every=self.qcfg.monitor_every,
        )
        self.pipeline = build_pipeline(domain, self.registry, self.monitor,
                                       embedder, self.qcfg)

        self.system_prompt = build_system_prompt(domain)
        self._facets = itertools.cycle(domain.facets) if domain.facets else None
        self.existing = 0
        self._temperature = gen_cfg.temperature
        self._temp_lock = threading.Lock()

    # ------------------------------------------------------------------
    def _resume(self) -> None:
        for key in self.writer.existing_keys():
            self.registry.seed(key)
        self.existing = len(self.registry)
        if self.existing:
            print(f"[resume] Tìm thấy {self.existing} dòng có sẵn, sẽ sinh tiếp.")

    def _next_facet(self) -> str | None:
        return next(self._facets) if self._facets else None

    def _maybe_switch_phase2(self, bar) -> bool:
        """Augment: khi đủ số dòng hạt giống từ API -> chuyển sang Ollama offline."""
        if (self.phase2_provider is not None and self._phase == 1
                and self.monitor.accepted >= self.seed_rows):
            self.provider = self.phase2_provider
            self._phase = 2
            self._log(bar, f"[augment] Đã có {self.monitor.accepted} dòng hạt giống "
                           f"từ API → chuyển sang Ollama offline ({self.provider.name}) "
                           f"để nhân bản phần còn lại.")
            return True
        return False

    def _current_temp(self) -> float:
        with self._temp_lock:
            return self._temperature

    def _maybe_adapt(self) -> None:
        """Sinh thích ứng: nếu tỉ lệ nhận gần đây thấp -> tăng nhiệt độ."""
        if not self.qcfg.adaptive:
            return
        if self.monitor.accepted < self.qcfg.rolling_window // 2:
            return
        if self.monitor.rolling_accept_rate() < self.qcfg.min_rolling_accept:
            with self._temp_lock:
                new_t = min(self._temperature + self.qcfg.temp_boost_step, self.qcfg.temp_max)
                if new_t > self._temperature:
                    self._temperature = new_t

    # ------------------------------------------------------------------
    def _worker(self, facet: str | None):
        """Một lần gọi model + đẩy cả lô qua QA. Trả BatchOutcome (hoặc None lỗi)."""
        avoid = self.registry.sample(self.cfg.avoid_sample_size)
        user_prompt = build_user_prompt(
            self.domain, batch_size=self.cfg.batch_size, facet=facet, avoid=avoid
        )
        try:
            content = self.provider.chat(
                self.system_prompt, user_prompt,
                temperature=self._current_temp(), max_tokens=self.cfg.max_tokens,
            )
        except Exception as err:  # noqa: BLE001
            self.pipeline.record_provider_error(str(err))
            self.writer.write_reject("provider_error", str(err)[:200], "")
            return None
        records = coerce_records(extract_json(content))
        # JSON có thể bị CẮT GIỮA CHỪNG khi model đụng trần max_tokens -> vớt lại
        # các bản ghi đã hoàn chỉnh thay vì mất trắng cả lần gọi tốn kém.
        if not records and content.strip():
            records = salvage_records(content)
        # Phản hồi rỗng/hỏng hẳn: ghi nhận rõ ràng (đừng để "stall" im lặng).
        if not records:
            self.pipeline.record_unparseable()
            self.writer.write_reject("unparseable_json", content[:200], "")
            return None
        return self.pipeline.process_batch(records)

    # ------------------------------------------------------------------
    def run(self) -> GenerationOutcome:
        self._resume()
        target = self.cfg.target_rows
        workers = max(1, self.cfg.workers)
        max_calls = int(target * self.cfg.max_attempts_factor / max(1, self.cfg.batch_size)) + workers

        start = time.time()
        calls = 0
        stall = 0          # đợt SINH ĐƯỢC record nhưng toàn trùng -> chủ đề đang cạn
        dead = 0           # đợt KHÔNG sinh được gì (lỗi/rate-limit) -> hạ tầng, chờ được
        # Lỗi hạ tầng (rate-limit free...) kiên nhẫn gấp đôi rồi mới chịu dừng.
        dead_rounds = max(self.cfg.stall_rounds * 2, 10)
        bar = self._make_bar(target)

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                while (self._total() < target and calls < max_calls
                       and stall < self.cfg.stall_rounds and dead < dead_rounds
                       and not self._stop_requested()):
                    if self._maybe_switch_phase2(bar):
                        stall = dead = 0       # pha mới -> cấp lại ngân sách kiên nhẫn
                    futures = [pool.submit(self._worker, self._next_facet())
                               for _ in range(workers)]
                    wave_added = 0
                    wave_outcomes = 0    # số worker trả KẾT QUẢ thực (không phải None do lỗi)
                    # Luôn DRAIN hết các future trong đợt để không mất dòng đã
                    # được QA chấp nhận (việc ghi CSV nằm ở luồng chính).
                    for fut in as_completed(futures):
                        outcome = fut.result()
                        if outcome is None:
                            continue
                        wave_outcomes += 1
                        for record in outcome.accepted:
                            self.writer.write_row(record)
                        for reason, detail, raw in outcome.rejects:
                            self.writer.write_reject(reason, detail, raw)
                        for line in outcome.snapshots:
                            self._log(bar, line)
                        wave_added += len(outcome.accepted)
                        self._refresh(bar, target)
                    calls += len(futures)
                    if wave_added > 0:
                        stall = dead = 0
                    elif wave_outcomes > 0:   # có sinh ra record nhưng toàn bị loại (trùng)
                        stall += 1
                    else:                     # cả đợt đều lỗi/rate-limit -> không phải "cạn chủ đề"
                        dead += 1
                    self._maybe_adapt()
        finally:
            if bar is not None:
                self._refresh(bar, target)
                bar.close()

        return GenerationOutcome(
            accepted_this_run=self.monitor.accepted,
            total_rows=self._total(),
            elapsed_sec=time.time() - start,
            calls=calls,
            report=self.monitor,
            stalled=stall >= self.cfg.stall_rounds or dead >= dead_rounds,
        )

    # ------------------------------------------------------------------
    def _total(self) -> int:
        return self.existing + self.monitor.accepted

    def _stop_requested(self) -> bool:
        return self.stop_event is not None and self.stop_event.is_set()

    def _make_bar(self, target: int):
        if not self.show_bar or tqdm is None:
            return None
        bar = tqdm(total=target, unit="dòng", desc="Sinh dữ liệu", dynamic_ncols=True)
        bar.n = min(self._total(), target)
        bar.refresh()
        return bar

    def _refresh(self, bar, target: int) -> None:
        total = min(self._total(), target)
        if bar is not None:
            bar.n = total
            bar.set_postfix_str(
                f"loại={self.monitor.total_rejected} nhiệt={self._current_temp():.2f}",
                refresh=True,
            )
        if self.on_progress is not None:
            try:
                self.on_progress(total, target, self.monitor.total_rejected,
                                 self._current_temp())
            except Exception:  # noqa: BLE001 - callback GUI không được làm hỏng phiên sinh
                pass

    def _log(self, bar, line: str) -> None:
        if bar is not None and tqdm is not None:
            tqdm.write(line)
        else:
            print(line)
