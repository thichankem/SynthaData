"""Giám sát chất lượng LIÊN TỤC trong lúc sinh.

Theo dõi (an toàn đa luồng):
    - số nhận / loại theo từng lý do
    - tỉ lệ chấp nhận trượt (rolling) -> phát hiện chủ đề sắp 'cạn'
    - phân bố giá trị các cột enum -> phát hiện 'mode collapse' (model lặp 1 giá trị)
Định kỳ phát "snapshot" để người dùng thấy sức khoẻ dữ liệu theo thời gian thực.
"""

from __future__ import annotations

import threading
from collections import Counter, deque
from dataclasses import dataclass, field

from ..schema import Domain


@dataclass
class QualityMonitor:
    domain: Domain
    rolling_window: int = 200
    monitor_every: int = 100

    accepted: int = 0
    rejects: Counter = field(default_factory=Counter)
    _recent: deque = field(default_factory=lambda: deque(maxlen=200))
    _enum_dist: dict = field(default_factory=dict)
    _since_emit: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        self._recent = deque(maxlen=self.rolling_window)
        self._enum_cols = [c.name for c in self.domain.columns if c.type == "enum"]
        self._enum_dist = {c: Counter() for c in self._enum_cols}

    # ------------------------------------------------------------------
    def record_accept(self, record: dict) -> bool:
        """Ghi nhận 1 dòng hợp lệ. Trả True nếu tới mốc cần in snapshot."""
        with self._lock:
            self.accepted += 1
            self._recent.append(1)
            for col in self._enum_cols:
                self._enum_dist[col][record.get(col, "")] += 1
            self._since_emit += 1
            if self._since_emit >= self.monitor_every:
                self._since_emit = 0
                return True
            return False

    def record_reject(self, reason: str) -> None:
        with self._lock:
            self.rejects[reason] += 1
            self._recent.append(0)

    # ------------------------------------------------------------------
    @property
    def total_rejected(self) -> int:
        return sum(self.rejects.values())

    def rolling_accept_rate(self) -> float:
        with self._lock:
            if not self._recent:
                return 1.0
            return sum(self._recent) / len(self._recent)

    def mode_collapse_warnings(self, dominance: float = 0.85) -> list[str]:
        """Cảnh báo nếu một giá trị enum chiếm ưu thế quá mức (model lặp lại)."""
        warns = []
        with self._lock:
            for col, dist in self._enum_dist.items():
                total = sum(dist.values())
                if total >= 20:
                    val, cnt = dist.most_common(1)[0]
                    if cnt / total >= dominance:
                        warns.append(f"cột '{col}': '{val}' chiếm {cnt/total:.0%}")
        return warns

    # ------------------------------------------------------------------
    def snapshot_line(self) -> str:
        rate = self.rolling_accept_rate()
        line = (f"[giám sát] đã nhận={self.accepted} | loại={self.total_rejected} "
                f"| tỉ lệ nhận gần đây={rate:.0%}")
        warns = self.mode_collapse_warnings()
        if warns:
            line += " | ⚠ lệch phân bố: " + "; ".join(warns)
        return line

    def summary_lines(self) -> list[str]:
        lines = [f"  Đã nhận (hợp lệ): {self.accepted}"]
        if self.rejects:
            lines.append(f"  Đã loại (tổng):   {self.total_rejected}")
            for reason, count in self.rejects.most_common():
                lines.append(f"      - {reason:<18}: {count}")
        warns = self.mode_collapse_warnings()
        if warns:
            lines.append("  ⚠ Phân bố lệch (cân nhắc tăng đa dạng):")
            for w in warns:
                lines.append(f"      - {w}")
        return lines
