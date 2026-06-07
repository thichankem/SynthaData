"""Interface chung cho mọi provider LLM + tiện ích retry."""

from __future__ import annotations

import abc
import random
import re
import time

import requests

from ..config import ProviderConfig


class ProviderError(RuntimeError):
    """Lỗi khi gọi provider sau khi đã thử lại hết số lần cho phép."""


class RateLimitError(ProviderError):
    """Lỗi 429 (vượt rate-limit). `retry_after` (giây) là thời gian nên chờ
    trước khi gọi lại, lấy từ header nếu nhà cung cấp có trả về."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _duration_to_seconds(text: str) -> float | None:
    """Đổi chuỗi thời lượng kiểu Groq ('205ms', '2.5s', '8m38.4s') sang giây."""
    text = (text or "").strip().lower()
    if not text:
        return None
    if text.endswith("ms"):
        try:
            return float(text[:-2]) / 1000.0
        except ValueError:
            return None
    total, found = 0.0, False
    for num, unit in re.findall(r"([\d.]+)\s*(h|m|s)", text):
        found = True
        total += float(num) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total if found else None


def _parse_retry_after(resp) -> float | None:
    ra = resp.headers.get("retry-after")
    if ra:
        secs = _duration_to_seconds(ra)
        if secs is not None:
            return secs
    # Groq/OpenAI: thời gian tới khi bucket token/request hồi.
    for h in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        secs = _duration_to_seconds(resp.headers.get(h, ""))
        if secs is not None:
            return secs
    return None


class LLMProvider(abc.ABC):
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Tên hiển thị của provider (gồm model)."""

    @abc.abstractmethod
    def _call(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        """Gọi 1 lần tới model, trả về chuỗi nội dung thô. (Có thể raise.)"""

    @abc.abstractmethod
    def health_check(self) -> None:
        """Kiểm tra provider sẵn sàng (key hợp lệ / server sống). Raise nếu hỏng."""

    # -------------------------------------------------------------------
    def chat(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        """Gọi model có retry + exponential backoff (kèm jitter)."""
        last_err: Exception | None = None
        for attempt in range(self.cfg.max_retries):
            try:
                return self._call(system, user, temperature=temperature, max_tokens=max_tokens)
            except Exception as err:  # noqa: BLE001 - gom mọi lỗi mạng/parse để retry
                last_err = err
                if attempt < self.cfg.max_retries - 1:
                    backoff = min(2 ** attempt + random.uniform(0, 0.75), 30)
                    time.sleep(backoff)
        raise ProviderError(f"{self.name}: thất bại sau {self.cfg.max_retries} lần thử: {last_err}")

    # Helper HTTP dùng chung cho các provider con.
    def _post(self, url: str, *, headers: dict, json_body: dict) -> dict:
        resp = requests.post(url, headers=headers, json=json_body, timeout=self.cfg.timeout)
        if resp.status_code == 429:
            raise RateLimitError(f"HTTP 429: {resp.text[:300]}",
                                 retry_after=_parse_retry_after(resp))
        if resp.status_code >= 400:
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json()
