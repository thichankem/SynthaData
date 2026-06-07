"""Provider API ngoài tương thích OpenAI (OpenAI, OpenRouter, Together, vLLM, LM Studio...).

Dùng endpoint chuẩn /chat/completions. Bật JSON mode để model trả JSON ổn định.
"""

from __future__ import annotations

import requests

from ..config import ProviderConfig
from .base import LLMProvider, ProviderError

_DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAIProvider(LLMProvider):
    def __init__(self, cfg: ProviderConfig):
        super().__init__(cfg)
        self.base_url = (cfg.base_url or _DEFAULT_BASE).rstrip("/")
        self.api_key = cfg.api_key()

    @property
    def name(self) -> str:
        return f"openai:{self.cfg.model}"

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _call(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        body = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # Buộc đầu ra là JSON object hợp lệ (đa số model mới hỗ trợ). Tắt được
        # cho vài dịch vụ không nhận tham số này (cfg.json_mode = false).
        if getattr(self.cfg, "json_mode", True):
            body["response_format"] = {"type": "json_object"}
        data = self._post(f"{self.base_url}/chat/completions", headers=self._headers(), json_body=body)
        try:
            # .get để KHÔNG crash với model 'reasoning' (gpt-oss, glm...) trả message
            # thiếu 'content' khi token bị tiêu hết cho phần suy luận -> coi như rỗng.
            message = data["choices"][0]["message"]
            return message.get("content") or ""
        except (KeyError, IndexError, TypeError) as err:
            raise ProviderError(f"Phản hồi OpenAI không đúng định dạng: {err}; raw={str(data)[:300]}")

    def health_check(self) -> None:
        if not self.api_key:
            raise ProviderError(
                f"Thiếu API key. Đặt biến môi trường '{self.cfg.api_key_env}'."
            )
        # Gọi /models để xác nhận key + endpoint sống (không bắt buộc thành công tuyệt đối).
        try:
            resp = requests.get(
                f"{self.base_url}/models", headers=self._headers(), timeout=self.cfg.timeout
            )
            if resp.status_code == 401:
                raise ProviderError("API key bị từ chối (401). Kiểm tra lại key.")
        except requests.RequestException as err:
            raise ProviderError(f"Không kết nối được endpoint '{self.base_url}': {err}")
