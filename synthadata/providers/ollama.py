"""Provider Ollama: chạy model offline ngay trên máy.

Yêu cầu: đã cài Ollama (https://ollama.com) và kéo sẵn model, ví dụ:
    ollama pull llama3.1
    ollama pull qwen2.5
Server mặc định lắng nghe tại http://localhost:11434
"""

from __future__ import annotations

import requests

from ..config import ProviderConfig
from .base import LLMProvider, ProviderError


class OllamaProvider(LLMProvider):
    def __init__(self, cfg: ProviderConfig):
        super().__init__(cfg)
        self.host = cfg.host.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama:{self.cfg.model}"

    def _call(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        body = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            # Ép Ollama trả JSON hợp lệ.
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        data = self._post(f"{self.host}/api/chat", headers={"Content-Type": "application/json"}, json_body=body)
        try:
            return data["message"]["content"] or ""
        except (KeyError, TypeError) as err:
            raise ProviderError(f"Phản hồi Ollama không đúng định dạng: {err}; raw={str(data)[:300]}")

    def health_check(self) -> None:
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=self.cfg.timeout)
        except requests.RequestException as err:
            raise ProviderError(
                f"Không kết nối được Ollama tại {self.host}. "
                f"Đã chạy 'ollama serve' chưa? Lỗi: {err}"
            )
        if resp.status_code >= 400:
            raise ProviderError(f"Ollama trả HTTP {resp.status_code}: {resp.text[:200]}")

        # Cảnh báo nếu model chưa được kéo về.
        try:
            tags = resp.json().get("models", [])
            names = {m.get("name", "").split(":")[0] for m in tags}
            base = self.cfg.model.split(":")[0]
            if names and base not in names:
                raise ProviderError(
                    f"Model '{self.cfg.model}' chưa có trên máy. "
                    f"Chạy: ollama pull {self.cfg.model}"
                )
        except ValueError:
            pass
