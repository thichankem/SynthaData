"""Kiểm tra & làm sạch SCHEMA của một bản ghi (thuần, không trạng thái dùng chung).

Đây là một mắt xích trong dây chuyền QA (xem package `quality`). Phần chống trùng
(tuyệt đối / mờ / ngữ nghĩa) và giám sát liên tục nằm ở `quality/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .schema import Domain
from .utils import clean_text, is_placeholder, normalize_key

# --- Mã lý do loại bản ghi (dùng thống nhất toàn hệ thống) ---
R_OK = "ok"
R_NOT_DICT = "not_a_dict"
R_MISSING = "missing_required"
R_PLACEHOLDER = "placeholder_value"
R_TOO_SHORT = "too_short"
R_TOO_LONG = "too_long"
R_BAD_ENUM = "invalid_enum"
R_BAD_NUMBER = "invalid_number"
R_EMPTY_KEY = "empty_key"
R_DUP_EXACT = "duplicate_exact"
R_DUP_NEAR = "duplicate_near"
R_DUP_SEMANTIC = "duplicate_semantic"
R_PROVIDER_ERROR = "provider_error"
R_UNPARSEABLE = "unparseable_json"   # phản hồi rỗng / JSON hỏng / bị cắt giữa chừng


@dataclass
class ValidationResult:
    ok: bool
    reason: str
    record: Optional[dict] = None     # bản ghi đã làm sạch (nếu hợp lệ)
    key: str = ""                     # khoá chống trùng đã chuẩn hoá
    detail: str = ""


class RecordValidator:
    """Làm sạch và kiểm tra tính hợp lệ của một bản ghi theo domain."""

    def __init__(self, domain: Domain):
        self.domain = domain
        self.key_col = domain.effective_dedup_key

    def validate(self, raw: dict) -> ValidationResult:
        if not isinstance(raw, dict):
            return ValidationResult(False, R_NOT_DICT)

        cleaned: dict[str, str] = {}
        for col in self.domain.columns:
            value = raw.get(col.name, "")

            if col.type == "number":
                res = self._check_number(col, value)
                if res is not None:
                    return res
                cleaned[col.name] = clean_text(value)
                continue

            text = clean_text(value)

            if not text or is_placeholder(text):
                if col.required:
                    reason = R_MISSING if not text else R_PLACEHOLDER
                    return ValidationResult(False, reason, detail=col.name)
                cleaned[col.name] = ""
                continue

            if col.type == "enum" and col.enum:
                match = self._match_enum(text, col.enum)
                if match is None:
                    return ValidationResult(False, R_BAD_ENUM, detail=f"{col.name}={text}")
                text = match

            if len(text) < col.min_len:
                return ValidationResult(False, R_TOO_SHORT, detail=col.name)
            if len(text) > col.max_len:
                text = text[: col.max_len].rstrip()  # cắt thay vì loại

            cleaned[col.name] = text

        key = normalize_key(cleaned.get(self.key_col, ""))
        if not key:
            return ValidationResult(False, R_EMPTY_KEY, detail=self.key_col)

        return ValidationResult(True, R_OK, record=cleaned, key=key)

    # ------------------------------------------------------------------
    @staticmethod
    def _match_enum(text: str, allowed: list[str]) -> Optional[str]:
        low = text.strip().lower()
        for opt in allowed:
            if low == opt.lower():
                return opt
        for opt in allowed:
            if opt.lower() in low or low in opt.lower():
                return opt
        return None

    @staticmethod
    def _check_number(col, value) -> Optional[ValidationResult]:
        text = clean_text(value)
        if not text:
            if col.required:
                return ValidationResult(False, R_MISSING, detail=col.name)
            return None
        try:
            float(str(value).replace(",", "").split()[0])
        except (ValueError, IndexError):
            return ValidationResult(False, R_BAD_NUMBER, detail=f"{col.name}={text}")
        return None
