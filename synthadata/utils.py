"""Tiện ích dùng chung: trích xuất JSON bền bỉ và chuẩn hoá văn bản."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _balanced_slice(text: str, open_ch: str, close_ch: str) -> str | None:
    """Lấy đoạn JSON cân bằng ngoặc đầu tiên bắt đầu bằng open_ch."""
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> Any:
    """Trích xuất JSON từ output model dù bị bọc ```fence``` hay lẫn văn bản.

    Trả về dict/list đã parse, hoặc None nếu không tìm được JSON hợp lệ.
    """
    if not text:
        return None

    # 1. Thử parse thẳng.
    candidates: list[str] = []
    stripped = text.strip()
    candidates.append(stripped)

    # 2. Nội dung trong khối ```fence```.
    for m in _FENCE_RE.finditer(text):
        candidates.append(m.group(1).strip())

    # 3. Đoạn object {...} hoặc array [...] cân bằng đầu tiên.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        sliced = _balanced_slice(text, open_ch, close_ch)
        if sliced:
            candidates.append(sliced)

    for cand in candidates:
        try:
            return json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


_ARRAY_KEY_RE = re.compile(
    r'"(?:records|data|rows|items|results|list)"\s*:\s*\[', re.IGNORECASE
)


def salvage_records(text: str) -> list[dict]:
    """Vớt các bản ghi {...} HOÀN CHỈNH từ một JSON có thể bị CẮT GIỮA CHỪNG.

    Khi model đụng trần `num_predict`, JSON cuối cùng thường thiếu dấu đóng nên
    `extract_json` thất bại và làm MẤT TRẮNG cả lô (kèm thời gian gọi tốn kém).
    Hàm này quét lần lượt từng object cân bằng ngoặc trong mảng record, parse
    riêng từng cái, giữ lại các bản ghi đã hoàn chỉnh và bỏ cái dở dang cuối.
    """
    if not text:
        return []
    m = _ARRAY_KEY_RE.search(text)
    start = (m.end() - 1) if m else text.find("[")
    if start < 0:
        start = 0

    records: list[dict] = []
    i = start
    n = len(text)
    while i < n:
        j = text.find("{", i)
        if j == -1:
            break
        obj = _balanced_slice(text[j:], "{", "}")
        if obj is None:          # object cuối bị cắt -> dừng, giữ những cái trước
            break
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, dict):
                records.append(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        i = j + len(obj)
    return records


def coerce_records(parsed: Any) -> list[dict]:
    """Đưa kết quả parse về list[dict] bản ghi, bất kể model trả dạng nào."""
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return [r for r in parsed if isinstance(r, dict)]
    if isinstance(parsed, dict):
        # Trường hợp {"records": [...]} hoặc tên khoá tương tự.
        for key in ("records", "data", "rows", "items", "results", "list"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
        # Bản thân dict là một bản ghi.
        return [parsed]
    return []


# Các giá trị "rỗng/placeholder" cần loại.
_PLACEHOLDER_RE = re.compile(
    r"^\s*(n/?a|none|null|nil|unknown|unspecified|tbd|todo|\.{2,}|-+|xxx+|"
    r"lorem ipsum|placeholder|string|example|test)\s*$",
    re.IGNORECASE,
)


def is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(value or ""))


_WS_RE = re.compile(r"\s+")


def clean_text(value: Any) -> str:
    """Chuẩn hoá một giá trị text: NFC, gộp khoảng trắng, bỏ ký tự điều khiển."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(v) for v in value)
    elif isinstance(value, dict):
        value = "; ".join(f"{k}: {v}" for k, v in value.items())
    else:
        value = str(value)

    value = unicodedata.normalize("NFC", value)
    # Bỏ ký tự điều khiển (giữ tab/newline rồi gộp thành space).
    value = "".join(ch for ch in value if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    value = _WS_RE.sub(" ", value).strip()
    # Bỏ ngoặc kép bao quanh dư thừa.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def normalize_key(value: str) -> str:
    """Chuẩn hoá khoá để so trùng: bỏ dấu, hạ chữ thường, bỏ ký tự lạ."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()
