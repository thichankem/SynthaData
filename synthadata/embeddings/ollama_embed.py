"""Embedder offline qua Ollama (vd model nomic-embed-text, mxbai-embed-large).

    ollama pull nomic-embed-text
"""

from __future__ import annotations

import requests

from ..config import EmbeddingConfig
from .base import Embedder, EmbedderError


class OllamaEmbedder(Embedder):
    def __init__(self, cfg: EmbeddingConfig):
        super().__init__(cfg)
        self.host = cfg.host.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama-embed:{self.cfg.model}"

    def _embed(self, texts: list[str]) -> list[list[float]]:
        # Endpoint mới /api/embed nhận cả lô (input là list).
        resp = requests.post(
            f"{self.host}/api/embed",
            json={"model": self.cfg.model, "input": texts},
            timeout=self.cfg.timeout,
        )
        if resp.status_code == 404:
            # Ollama cũ: rơi về /api/embeddings (từng câu một).
            return [self._embed_single(t) for t in texts]
        if resp.status_code >= 400:
            raise EmbedderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        vectors = data.get("embeddings")
        if not vectors:
            raise EmbedderError(f"Phản hồi thiếu 'embeddings': {str(data)[:200]}")
        return vectors

    def _embed_single(self, text: str) -> list[float]:
        resp = requests.post(
            f"{self.host}/api/embeddings",
            json={"model": self.cfg.model, "prompt": text},
            timeout=self.cfg.timeout,
        )
        if resp.status_code >= 400:
            raise EmbedderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        vec = resp.json().get("embedding")
        if not vec:
            raise EmbedderError("Phản hồi thiếu 'embedding'.")
        return vec
