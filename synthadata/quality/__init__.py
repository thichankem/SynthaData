"""Package QA: dây chuyền kiểm tra chất lượng chạy LIÊN TỤC.

    dedup.py    -> chỉ mục chống trùng 3 tầng: tuyệt đối + mờ + NGỮ NGHĨA
    checks.py   -> các "check" cắm-rút (pluggable) cho từng bản ghi
    monitor.py  -> giám sát liên tục: tỉ lệ chấp nhận, phân bố, mode-collapse
    pipeline.py -> ráp các check + dedup + embedder thành một dây chuyền
"""

from __future__ import annotations

from .dedup import DedupRegistry
from .monitor import QualityMonitor
from .checks import Check, CheckContext, CheckResult, StructureCheck, SchemaCheck
from .pipeline import QualityPipeline

__all__ = [
    "DedupRegistry",
    "QualityMonitor",
    "Check",
    "CheckContext",
    "CheckResult",
    "StructureCheck",
    "SchemaCheck",
    "QualityPipeline",
]
