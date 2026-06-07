"""Các "check" cắm-rút chạy trên TỪNG bản ghi.

Mỗi check là một lớp con của `Check`, nhận `CheckContext` (mang bản ghi thô,
bản ghi đã làm sạch, khoá, vector...) và trả `CheckResult`. Muốn thêm luật kiểm
tra mới (vd: PII, độ độc hại, ràng buộc giữa các cột) chỉ cần viết thêm một lớp
`Check` và đăng ký vào pipeline — không phải sửa phần lõi.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..schema import Domain
from ..validation import R_OK, RecordValidator


@dataclass
class CheckResult:
    ok: bool
    reason: str = R_OK
    detail: str = ""


@dataclass
class CheckContext:
    raw: dict                                  # bản ghi thô từ model
    cleaned: Optional[dict] = None             # bản ghi đã làm sạch (sau SchemaCheck)
    norm_key: str = ""                         # khoá chống trùng đã chuẩn hoá
    signature: str = ""                        # văn bản dùng để nhúng (ngữ nghĩa)
    embedding: Optional[list[float]] = None    # vector nhúng (nếu có)
    extra: dict = field(default_factory=dict)


class Check(abc.ABC):
    """Một mắt xích kiểm tra. Trả CheckResult(ok=False, ...) để loại bản ghi."""

    name: str = "check"

    @abc.abstractmethod
    def run(self, ctx: CheckContext) -> CheckResult:
        ...


class StructureCheck(Check):
    """Bản ghi phải là dict và không rỗng."""

    name = "structure"

    def run(self, ctx: CheckContext) -> CheckResult:
        if not isinstance(ctx.raw, dict) or not ctx.raw:
            return CheckResult(False, "not_a_dict")
        return CheckResult(True)


class SchemaCheck(Check):
    """Làm sạch + validate theo schema (uỷ quyền cho RecordValidator).

    Khi đạt: gắn `cleaned`, `norm_key`, `signature` vào context để các check sau dùng.
    """

    name = "schema"

    def __init__(self, domain: Domain):
        self.validator = RecordValidator(domain)
        self.domain = domain
        self._sig_cols = self._pick_signature_columns(domain)

    @staticmethod
    def _pick_signature_columns(domain: Domain) -> list[str]:
        """Chọn các cột tạo 'chữ ký ngữ nghĩa' để nhúng: ưu tiên cấu hình
        domain.semantic_fields, không có thì lấy khoá + cột text dài nhất."""
        if domain.semantic_fields:
            return [c for c in domain.semantic_fields if domain.column(c)]
        cols = [domain.effective_dedup_key]
        text_cols = [c for c in domain.columns if c.type == "text"
                     and c.name != domain.effective_dedup_key]
        if text_cols:
            longest = max(text_cols, key=lambda c: c.max_len)
            cols.append(longest.name)
        return cols

    def run(self, ctx: CheckContext) -> CheckResult:
        result = self.validator.validate(ctx.raw)
        if not result.ok:
            return CheckResult(False, result.reason, result.detail)
        ctx.cleaned = result.record
        ctx.norm_key = result.key
        ctx.signature = " | ".join(
            str(result.record.get(c, "")) for c in self._sig_cols
        ).strip(" |")
        return CheckResult(True)


class ConsistencyCheck(Check):
    """Kiểm tra ràng buộc giữa các cột bằng các hàm luật do người dùng cấp.

    Mỗi luật là callable(cleaned_record) -> Optional[str]: trả None nếu hợp lệ,
    hoặc chuỗi mô tả lỗi nếu vi phạm. Cho phép cài "check liên tục" tuỳ domain.
    """

    name = "consistency"

    def __init__(self, rules: list[Callable[[dict], Optional[str]]]):
        self.rules = rules

    def run(self, ctx: CheckContext) -> CheckResult:
        if ctx.cleaned is None:
            return CheckResult(True)
        for rule in self.rules:
            msg = rule(ctx.cleaned)
            if msg:
                return CheckResult(False, "inconsistent", msg)
        return CheckResult(True)
