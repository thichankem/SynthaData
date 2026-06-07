"""Giao diện dòng lệnh cho SynthaData."""

from __future__ import annotations

import argparse
import sys


def _ensure_utf8_console() -> None:
    """Ép stdout/stderr về UTF-8 để không crash khi in tiếng Việt trên
    console Windows mặc định (cp1252). An toàn nếu không hỗ trợ."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


_ensure_utf8_console()

try:
    from dotenv import load_dotenv

    load_dotenv()  # nạp API key từ file .env nếu có
except ImportError:
    pass

from .config import AppConfig
from .embeddings import build_embedder
from .embeddings.hashing import HashingEmbedder
from .generator import DataGenerator
from .modes import VALID_MODES, build_generation_provider, build_phase2_provider
from .providers.base import ProviderError
from .schema import Domain
from .writer import CsvWriter


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="synthadata",
        description="Sinh dữ liệu tổng hợp dạng CSV để train model AI khác "
                    "(hỗ trợ API ngoài và Ollama offline).",
    )
    p.add_argument("--gui", action="store_true",
                   help="Mở giao diện đồ hoạ (GUI) thay vì chạy dòng lệnh.")
    p.add_argument("--domain",
                   help="Đường dẫn file domain YAML (vd: domains/diseases.yaml). "
                        "Bắt buộc trừ khi dùng --gui.")
    p.add_argument("--config", default="config.yaml",
                   help="File cấu hình chung (mặc định: config.yaml).")

    # Chế độ chạy.
    p.add_argument("--mode", choices=["api", "offline", "hybrid", "augment"],
                   help="api=API online | offline=Ollama cục bộ | "
                        "hybrid=API, hết quota tự chuyển Ollama | "
                        "augment=API sinh hạt giống rồi Ollama nhân bản thêm.")
    p.add_argument("--offline-model", dest="offline_model",
                   help="Model Ollama dùng cho phần offline (vd qwen2.5-coder:7b).")
    p.add_argument("--seed-rows", type=int, dest="seed_rows",
                   help="(mode augment) số dòng hạt giống sinh bằng API trước khi "
                        "chuyển sang Ollama.")

    # Override nhanh từ CLI.
    p.add_argument("--provider", choices=["openai", "anthropic", "ollama"],
                   help="Loại provider (ghi đè config).")
    p.add_argument("--model", help="Tên model (ghi đè config).")
    p.add_argument("--base-url", dest="base_url", help="Endpoint cho provider API ngoài.")
    p.add_argument("--host", help="Host Ollama (mặc định http://localhost:11434).")
    p.add_argument("--target", type=int, dest="target_rows",
                   help="Số dòng cần sinh (mặc định 1000).")
    p.add_argument("--batch-size", type=int, dest="batch_size",
                   help="Số bản ghi xin mỗi lần gọi.")
    p.add_argument("--workers", type=int, help="Số luồng song song.")
    p.add_argument("--temperature", type=float, help="Độ sáng tạo (0..2).")
    p.add_argument("--out", dest="output_path", help="Đường dẫn file CSV đầu ra.")
    # Chống trùng ngữ nghĩa (embeddings).
    p.add_argument("--embed-provider", dest="embed_provider",
                   choices=["ollama", "openai", "hashing", "none"],
                   help="Nguồn embedding cho chống trùng ngữ nghĩa.")
    p.add_argument("--embed-model", dest="embed_model",
                   help="Model embedding (vd nomic-embed-text).")
    p.add_argument("--no-semantic", action="store_true",
                   help="Tắt chống trùng ngữ nghĩa.")
    p.add_argument("--no-resume", action="store_true",
                   help="Ghi đè file cũ thay vì chạy tiếp.")
    p.add_argument("--dry-run", action="store_true",
                   help="Chỉ kiểm tra cấu hình + provider rồi thoát.")
    return p


def _setup_embedder(cfg: AppConfig):
    """Tạo embedder + kiểm tra. Nếu hỏng và cho phép, lùi về hashing (lexical).
    Nếu vẫn không được -> tắt chống trùng ngữ nghĩa (vẫn còn tuyệt đối + mờ)."""
    if not cfg.quality.semantic_enabled:
        return None
    try:
        embedder = build_embedder(cfg.embedding)
    except ValueError as err:
        print(f"[cảnh báo] Embedding lỗi cấu hình: {err}", file=sys.stderr)
        embedder = None
    if embedder is None:
        cfg.quality.semantic_enabled = False
        return None
    try:
        embedder.health_check()
        print(f"[ok] Embedder sẵn sàng: {embedder.name}")
        return embedder
    except Exception as err:  # noqa: BLE001
        print(f"[cảnh báo] Embedder '{embedder.name}' không sẵn sàng: {err}")
        if cfg.embedding.fallback_to_hashing and cfg.embedding.type != "hashing":
            print("           -> Lùi về embedder 'hashing' (lexical, không cần model).\n"
                  "              Để chống trùng NGỮ NGHĨA thật: ollama pull nomic-embed-text")
            return HashingEmbedder(cfg.embedding)
        cfg.quality.semantic_enabled = False
        print("           -> Tắt chống trùng ngữ nghĩa (vẫn giữ tuyệt đối + mờ).")
        return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        from .gui import main as gui_main
        return gui_main()

    if not args.domain:
        parser.error("thiếu --domain (hoặc dùng --gui để mở giao diện).")

    overrides = {
        "mode": args.mode,
        "offline_model": args.offline_model,
        "seed_rows": args.seed_rows,
        "provider": args.provider,
        "model": args.model,
        "base_url": args.base_url,
        "host": args.host,
        "target_rows": args.target_rows,
        "batch_size": args.batch_size,
        "workers": args.workers,
        "temperature": args.temperature,
        "output_path": args.output_path,
        "embed_provider": args.embed_provider,
        "embed_model": args.embed_model,
        "semantic_enabled": False if args.no_semantic else None,
    }

    cfg = AppConfig.load(args.config, overrides=overrides)

    try:
        domain = Domain.load(args.domain)
    except (OSError, ValueError) as err:
        print(f"[lỗi] Không nạp được domain: {err}", file=sys.stderr)
        return 2

    if cfg.mode not in VALID_MODES:
        print(f"[lỗi] mode '{cfg.mode}' không hợp lệ. Chọn: {', '.join(VALID_MODES)}.",
              file=sys.stderr)
        return 2

    _MODE_DESC = {
        "api": "API online (xoay vòng)",
        "offline": f"Ollama offline ({cfg.offline.model})",
        "hybrid": f"API online; hết quota → Ollama offline ({cfg.offline.model})",
        "augment": f"API sinh {cfg.generation.seed_rows} hạt giống → Ollama "
                   f"offline ({cfg.offline.model}) nhân bản thêm",
    }
    sem = "bật" if cfg.quality.semantic_enabled else "tắt"
    print("=" * 64)
    print(f"  Domain    : {domain.name}  ({len(domain.columns)} cột, "
          f"{len(domain.facets)} facet)")
    print(f"  Chế độ    : {cfg.mode} — {_MODE_DESC[cfg.mode]}")
    print(f"  Embedding : {cfg.embedding.type} / {cfg.embedding.model} "
          f"(chống trùng ngữ nghĩa: {sem})")
    print(f"  Mục tiêu  : {cfg.generation.target_rows} dòng, "
          f"batch={cfg.generation.batch_size}, workers={cfg.generation.workers}")
    print(f"  Đầu ra    : {cfg.output.path}")
    print("=" * 64)

    # Khởi tạo + kiểm tra provider (theo chế độ).
    phase2 = None
    try:
        provider = build_generation_provider(cfg)
        provider.health_check()
        print(f"[ok] Provider sẵn sàng: {provider.name}")
        phase2 = build_phase2_provider(cfg)
        if phase2 is not None:
            phase2.health_check()
            print(f"[ok] Provider nhân bản (pha 2) sẵn sàng: {phase2.name}")
    except (ProviderError, ValueError) as err:
        print(f"[lỗi] Provider không sẵn sàng: {err}", file=sys.stderr)
        return 3

    # Khởi tạo embedder cho chống trùng ngữ nghĩa (lùi về hashing nếu cần).
    embedder = _setup_embedder(cfg)

    if args.dry_run:
        print("[dry-run] Cấu hình hợp lệ. Thoát.")
        return 0

    writer = CsvWriter(
        domain, cfg.output.path,
        encoding=cfg.output.encoding,
        write_rejects=cfg.output.write_rejects,
    )
    gen = DataGenerator(provider, domain, cfg.generation, writer,
                        embedder=embedder, quality_cfg=cfg.quality,
                        phase2_provider=phase2, seed_rows=cfg.generation.seed_rows)

    with writer:
        writer.open(append=cfg.output.checkpoint and not args.no_resume)
        outcome = gen.run()

    # Báo cáo cuối.
    print("\n" + "=" * 64)
    print("  KẾT QUẢ")
    print("=" * 64)
    for line in outcome.report.summary_lines():
        print(line)
    rate = outcome.accepted_this_run / outcome.elapsed_sec if outcome.elapsed_sec else 0
    print(f"  Tổng dòng trong file: {outcome.total_rows}")
    print(f"  Số lần gọi model    : {outcome.calls}")
    print(f"  Thời gian           : {outcome.elapsed_sec:.1f}s "
          f"({rate:.1f} dòng/giây)")
    print(f"  File CSV            : {cfg.output.path}")
    print("=" * 64)

    if outcome.stalled and outcome.total_rows < cfg.generation.target_rows:
        print("[cảnh báo] Dừng sớm: nhiều đợt liên tiếp không sinh thêm được dòng mới.\n"
              "           Có thể chủ đề đã 'cạn' hoặc model lặp nhiều. Thử tăng "
              "temperature / đổi model / thêm facet.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
