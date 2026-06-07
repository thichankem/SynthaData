"""Dây chuyền QA: ráp các check + embedder + chống trùng + giám sát.

`process_batch` xử lý cả MỘT lô bản ghi để nhúng embedding theo lô (hiệu quả):
    1. Chạy các pre-check (structure, schema, consistency) trên từng bản ghi.
    2. Nhúng "chữ ký ngữ nghĩa" của các bản ghi qua được, MỘT lần gọi cho cả lô.
    3. Chống trùng 3 tầng (tuyệt đối + mờ + ngữ nghĩa) + ghi nhận giám sát.
Embedding (chậm, qua mạng) chạy NGOÀI khoá; phần so vector (nhanh) chạy trong khoá.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import QualityConfig
from ..schema import Domain
from ..validation import R_PROVIDER_ERROR, R_UNPARSEABLE
from .checks import Check, CheckContext, SchemaCheck, StructureCheck
from .dedup import DedupRegistry
from .monitor import QualityMonitor


@dataclass
class BatchOutcome:
    accepted: list[dict] = field(default_factory=list)
    rejects: list[tuple] = field(default_factory=list)   # (reason, detail, raw)
    snapshots: list[str] = field(default_factory=list)    # dòng giám sát cần in


class QualityPipeline:
    def __init__(self, domain: Domain, registry: DedupRegistry,
                 monitor: QualityMonitor, embedder, checks: list[Check],
                 *, semantic_enabled: bool = True):
        self.domain = domain
        self.registry = registry
        self.monitor = monitor
        self.embedder = embedder
        self.checks = checks
        self.semantic_enabled = semantic_enabled and embedder is not None
        self._embed_warned = False

    # ------------------------------------------------------------------
    def process_batch(self, raw_records: list[dict]) -> BatchOutcome:
        out = BatchOutcome()

        # --- Giai đoạn 1: pre-check thuần (không khoá, không mạng) ---
        survivors: list[CheckContext] = []
        for raw in raw_records:
            ctx = CheckContext(raw=raw)
            failed = None
            for check in self.checks:
                res = check.run(ctx)
                if not res.ok:
                    failed = res
                    break
            if failed is None:
                survivors.append(ctx)
            else:
                self._reject(out, failed.reason, failed.detail, raw)

        # --- Giai đoạn 2: nhúng embedding theo lô (ngoài khoá) ---
        if self.semantic_enabled and survivors:
            self._embed_survivors(out, survivors)

        # --- Giai đoạn 3: chống trùng 3 tầng + giám sát (nguyên tử/khoá) ---
        for ctx in survivors:
            dup = self.registry.check_and_commit(ctx.norm_key, ctx.embedding)
            if dup.ok:
                out.accepted.append(ctx.cleaned)
                if self.monitor.record_accept(ctx.cleaned):
                    out.snapshots.append(self.monitor.snapshot_line())
            else:
                self._reject(out, dup.reason, dup.detail, ctx.raw)
        return out

    # ------------------------------------------------------------------
    def _embed_survivors(self, out: BatchOutcome, survivors: list[CheckContext]) -> None:
        try:
            vectors = self.embedder.embed([c.signature for c in survivors])
            for ctx, vec in zip(survivors, vectors):
                ctx.embedding = vec
        except Exception as err:  # noqa: BLE001 - lỗi nhúng không được làm sập phiên
            if not self._embed_warned:
                self._embed_warned = True
                out.snapshots.append(
                    f"[cảnh báo] Nhúng embedding lỗi, TẠM TẮT chống trùng ngữ nghĩa "
                    f"cho phần còn lại: {err}"
                )
            self.semantic_enabled = False

    def _reject(self, out: BatchOutcome, reason: str, detail: str, raw) -> None:
        self.monitor.record_reject(reason)
        out.rejects.append((reason, detail, raw))

    def record_provider_error(self, message: str) -> None:
        self.monitor.record_reject(R_PROVIDER_ERROR)

    def record_unparseable(self) -> None:
        """Phản hồi không trích được bản ghi nào (rỗng / JSON hỏng / bị cắt)."""
        self.monitor.record_reject(R_UNPARSEABLE)


# ---------------------------------------------------------------------------
def build_pipeline(domain: Domain, registry: DedupRegistry, monitor: QualityMonitor,
                   embedder, qcfg: QualityConfig, *,
                   consistency_rules=None) -> QualityPipeline:
    """Factory dựng dây chuyền QA mặc định (dễ thêm/bớt check)."""
    checks: list[Check] = [StructureCheck(), SchemaCheck(domain)]
    if consistency_rules:
        from .checks import ConsistencyCheck
        checks.append(ConsistencyCheck(consistency_rules))
    return QualityPipeline(
        domain, registry, monitor, embedder, checks,
        semantic_enabled=qcfg.semantic_enabled,
    )
