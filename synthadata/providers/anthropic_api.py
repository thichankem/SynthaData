"""Provider API ngoài: Anthropic (Claude).

Dùng endpoint /v1/messages. Model gợi ý (mới nhất):
    claude-opus-4-8     - mạnh nhất
    claude-sonnet-4-6   - cân bằng tốc độ/chi phí (mặc định khuyến nghị)
    claude-haiku-4-5    - nhanh, rẻ
"""

from __future__ import annotations

import requests

from ..config import ProviderConfig
from .base import LLMProvider, ProviderError

_DEFAULT_BASE = "https://api.anthropic.com/v1"
_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def __init__(self, cfg: ProviderConfig):
        super().__init__(cfg)
        self.base_url = (cfg.base_url or _DEFAULT_BASE).rstrip("/")
        self.api_key = cfg.api_key()

    @property
    def name(self) -> str:
        return f"anthropic:{self.cfg.model}"

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
            "anthropic-version": _API_VERSION,
        }

    def _call(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        body = {
            "model": self.cfg.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = self._post(f"{self.base_url}/messages", headers=self._headers(), json_body=body)
        try:
            # content là list các block; lấy text của block đầu.
            blocks = data["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (KeyError, IndexError, TypeError) as err:
            raise ProviderError(f"Phản hồi Anthropic không đúng định dạng: {err}; raw={str(data)[:300]}")

    def health_check(self) -> None:
        if not self.api_key:
            raise ProviderError(
                f"Thiếu API key. Đặt biến môi trường '{self.cfg.api_key_env}' "
                f"(thường là ANTHROPIC_API_KEY)."
            )
        # Anthropic không có endpoint health rẻ; thử 1 ping nhỏ.
        try:
            resp = requests.post(
                f"{self.base_url}/messages",
                headers=self._headers(),
                json={
                    "model": self.cfg.model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                timeout=self.cfg.timeout,
            )
            if resp.status_code == 401:
                raise ProviderError("API key bị từ chối (401). Kiểm tra lại key.")
        except requests.RequestException as err:
            raise ProviderError(f"Không kết nối được Anthropic: {err}")
