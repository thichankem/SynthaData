"""Lớp embeddings: biến văn bản thành vector để chống TRÙNG NGỮ NGHĨA.

Các loại:
    ollama  -> embedding offline (vd model nomic-embed-text)
    openai  -> embedding qua API (text-embedding-3-small)
    hashing -> fallback không cần model (lexical, dùng khi thiếu embedder thật)
    none    -> tắt embedding (chỉ chống trùng tuyệt đối + mờ)
"""

from __future__ import annotations

from ..config import EmbeddingConfig
from .base import Embedder
from .ollama_embed import OllamaEmbedder
from .openai_embed import OpenAIEmbedder
from .hashing import HashingEmbedder


def build_embedder(cfg: EmbeddingConfig) -> Embedder | None:
    kind = (cfg.type or "none").lower().strip()
    if kind in ("none", "off", "disabled"):
        return None
    if kind == "ollama":
        return OllamaEmbedder(cfg)
    if kind in ("openai", "openai-compatible"):
        return OpenAIEmbedder(cfg)
    if kind in ("hashing", "hash", "lexical"):
        return HashingEmbedder(cfg)
    raise ValueError(f"Embedder không hỗ trợ: '{cfg.type}'.")


__all__ = [
    "Embedder",
    "OllamaEmbedder",
    "OpenAIEmbedder",
    "HashingEmbedder",
    "build_embedder",
]
