"""Embedder qua API tương thích OpenAI (text-embedding-3-small/large)."""

from __future__ import annotations

import requests

from ..config import EmbeddingConfig
from .base import Embedder, EmbedderError

_DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAIEmbedder(Embedder):
    def __init__(self, cfg: EmbeddingConfig):
        super().__init__(cfg)
        self.base_url = (cfg.base_url or _DEFAULT_BASE).rstrip("/")
        self.api_key = cfg.api_key()

    @property
    def name(self) -> str:
        return f"openai-embed:{self.cfg.model}"

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbedderError(f"Thiếu API key (biến môi trường '{self.cfg.api_key_env}').")
        resp = requests.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.cfg.model, "input": texts},
            timeout=self.cfg.timeout,
        )
        if resp.status_code >= 400:
            raise EmbedderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json().get("data", [])
        # Sắp theo index để khớp thứ tự đầu vào.
        data.sort(key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in data]
