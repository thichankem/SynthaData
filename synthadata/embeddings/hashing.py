"""Embedder fallback KHÔNG cần model: hashing n-gram (lexical).

Đây KHÔNG phải embedding ngữ nghĩa thực thụ — nó chỉ vector hoá theo từ/ký tự,
nên chỉ bắt được trùng về mặt chữ. Dùng khi không có embedder thật (Ollama/OpenAI)
để vẫn duy trì một lớp chống trùng "gần ngữ nghĩa" chạy liên tục, không phụ thuộc
mạng. Có embedder thật thì nên dùng nó để bắt trùng ngữ nghĩa đúng nghĩa.
"""

from __future__ import annotations

import hashlib
import math
import re

from ..config import EmbeddingConfig

_DIM = 512
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    def __init__(self, cfg: EmbeddingConfig | None = None):
        self.cfg = cfg
        self.dim = _DIM

    @property
    def name(self) -> str:
        return "hashing-lexical:512"

    def health_check(self) -> None:
        # Luôn sẵn sàng (thuần Python).
        return None

    def _features(self, text: str):
        text = (text or "").lower()
        words = _TOKEN_RE.findall(text)
        # unigram + bigram từ + 3-gram ký tự -> bắt cả biến thể chính tả.
        feats = list(words)
        feats += [f"{a}_{b}" for a, b in zip(words, words[1:])]
        compact = "".join(words)
        feats += [compact[i:i + 3] for i in range(len(compact) - 2)]
        return feats

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * _DIM
        for feat in self._features(text):
            h = int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16)
            idx = h % _DIM
            sign = 1.0 if (h >> 16) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]
