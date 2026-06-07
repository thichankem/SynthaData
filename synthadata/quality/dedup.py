"""Chỉ mục chống trùng 3 tầng, an toàn đa luồng.

Tầng 1 - Tuyệt đối : so khoá đã chuẩn hoá (bỏ dấu, hạ chữ).
Tầng 2 - Mờ (mlex)  : độ tương đồng chuỗi trong cùng "bucket" (rapidfuzz/difflib).
Tầng 3 - Ngữ nghĩa : cosine giữa các vector embedding (bắt cách diễn đạt khác nhau
                     của cùng một khái niệm, vd "Leprosy" vs "Hansen's Disease").

`check_and_commit` thực hiện kiểm tra + thêm vào chỉ mục một cách NGUYÊN TỬ để
an toàn khi nhiều luồng cùng ghi.
"""

from __future__ import annotations

import threading
from typing import Optional

from ..validation import (
    R_DUP_EXACT, R_DUP_NEAR, R_DUP_SEMANTIC, R_OK, ValidationResult,
)

# Tương đồng chuỗi: ưu tiên rapidfuzz, fallback difflib.
try:  # pragma: no cover
    from rapidfuzz.fuzz import ratio as _fuzz_ratio

    def _str_sim(a: str, b: str) -> float:
        return _fuzz_ratio(a, b) / 100.0
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    def _str_sim(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

# Cosine theo lô bằng numpy nếu có, không thì thuần Python.
try:  # pragma: no cover
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None


class DedupRegistry:
    def __init__(self, *, fuzzy_threshold: float = 0.92,
                 semantic_threshold: float = 0.90, semantic_enabled: bool = True):
        self.fuzzy_threshold = fuzzy_threshold
        self.semantic_threshold = semantic_threshold
        self.semantic_enabled = semantic_enabled

        self._exact: set[str] = set()
        self._buckets: dict[str, list[str]] = {}
        self._keys: list[str] = []          # song song với hàng của _matrix
        # Buffer vector đã CHUẨN HOÁ. Với numpy: ma trận (capacity x D) cấp phát
        # trước, nhân đôi sức chứa khi đầy -> chèn amortized O(1) (tránh vstack
        # sao chép lại toàn bộ mỗi lần, vốn khiến chống trùng ngữ nghĩa chậm dần
        # theo bậc hai khi số dòng lớn). `_count` là số vector đang thực dùng.
        self._matrix = None                  # numpy (capacity x D) hoặc list[list] fallback
        self._count = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._exact)

    # ------------------------------------------------------------------
    def check_and_commit(self, norm_key: str,
                         embedding: Optional[list[float]] = None) -> ValidationResult:
        """Kiểm tra trùng (3 tầng) và thêm nếu chưa trùng — nguyên tử."""
        with self._lock:
            # Tầng 1: tuyệt đối.
            if norm_key in self._exact:
                return ValidationResult(False, R_DUP_EXACT, key=norm_key)

            # Tầng 2: mờ (lexical), chỉ so trong bucket cùng 3 ký tự đầu.
            bucket_id = norm_key[:3]
            bucket = self._buckets.get(bucket_id, [])
            for existing in bucket:
                if _str_sim(norm_key, existing) >= self.fuzzy_threshold:
                    return ValidationResult(False, R_DUP_NEAR, key=norm_key, detail=existing)

            # Tầng 3: ngữ nghĩa.
            if self.semantic_enabled and embedding is not None and self._keys:
                idx, sim = self._nearest(embedding)
                if sim >= self.semantic_threshold:
                    return ValidationResult(
                        False, R_DUP_SEMANTIC, key=norm_key,
                        detail=f"{self._keys[idx]} (cos={sim:.3f})",
                    )

            # Hợp lệ -> commit vào cả 3 tầng.
            self._exact.add(norm_key)
            bucket.append(norm_key)
            self._buckets[bucket_id] = bucket
            if self.semantic_enabled and embedding is not None:
                self._append_vector(embedding)
                self._keys.append(norm_key)
            return ValidationResult(True, R_OK, key=norm_key)

    # ------------------------------------------------------------------
    def _append_vector(self, embedding: list[float]) -> None:
        if _np is not None:
            vec = _np.asarray(embedding, dtype=_np.float32)
            norm = float(_np.linalg.norm(vec)) or 1.0
            vec = vec / norm
            if self._matrix is None:
                self._matrix = _np.empty((8, vec.shape[0]), dtype=_np.float32)
            elif self._count >= self._matrix.shape[0]:
                bigger = _np.empty((self._matrix.shape[0] * 2, self._matrix.shape[1]),
                                   dtype=_np.float32)
                bigger[:self._count] = self._matrix[:self._count]
                self._matrix = bigger
            self._matrix[self._count] = vec
        else:
            norm = (sum(v * v for v in embedding) ** 0.5) or 1.0
            if self._matrix is None:
                self._matrix = []
            self._matrix.append([v / norm for v in embedding])
        self._count += 1

    def _nearest(self, embedding: list[float]) -> tuple[int, float]:
        """Trả (chỉ số, cosine lớn nhất) so với các vector đã lưu."""
        if _np is not None:
            vec = _np.asarray(embedding, dtype=_np.float32)
            norm = float(_np.linalg.norm(vec)) or 1.0
            vec = vec / norm
            sims = self._matrix[:self._count] @ vec   # (N,) vì các hàng đã chuẩn hoá
            i = int(sims.argmax())
            return i, float(sims[i])
        # Fallback thuần Python.
        norm = (sum(v * v for v in embedding) ** 0.5) or 1.0
        q = [v / norm for v in embedding]
        best_i, best = 0, -1.0
        for i in range(self._count):
            s = sum(a * b for a, b in zip(q, self._matrix[i]))
            if s > best:
                best_i, best = i, s
        return best_i, best

    # ------------------------------------------------------------------
    def seed(self, norm_key: str) -> None:
        """Nạp lại khoá cũ khi resume (chỉ tầng tuyệt đối + mờ; không có vector)."""
        with self._lock:
            if norm_key and norm_key not in self._exact:
                self._exact.add(norm_key)
                self._buckets.setdefault(norm_key[:3], []).append(norm_key)

    def sample(self, n: int) -> list[str]:
        import random
        with self._lock:
            if not self._exact:
                return []
            keys = list(self._exact)
        return random.sample(keys, min(n, len(keys)))
