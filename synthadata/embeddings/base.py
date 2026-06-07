"""Interface chung cho mọi embedder + retry."""

from __future__ import annotations

import abc
import random
import time

from ..config import EmbeddingConfig


class EmbedderError(RuntimeError):
    pass


class Embedder(abc.ABC):
    def __init__(self, cfg: EmbeddingConfig):
        self.cfg = cfg

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @abc.abstractmethod
    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Nhúng một lô văn bản -> danh sách vector. (Có thể raise.)"""

    def health_check(self) -> None:
        """Kiểm tra embedder sẵn sàng. Raise nếu hỏng. Mặc định thử nhúng 1 câu."""
        self.embed(["health check"])

    # -------------------------------------------------------------------
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        last_err: Exception | None = None
        for attempt in range(self.cfg.max_retries):
            try:
                vectors = self._embed(texts)
                if len(vectors) != len(texts):
                    raise EmbedderError(
                        f"Số vector ({len(vectors)}) khác số văn bản ({len(texts)})."
                    )
                return vectors
            except Exception as err:  # noqa: BLE001
                last_err = err
                if attempt < self.cfg.max_retries - 1:
                    time.sleep(min(2 ** attempt + random.uniform(0, 0.5), 15))
        raise EmbedderError(f"{self.name}: nhúng thất bại: {last_err}")
