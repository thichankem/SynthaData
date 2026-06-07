"""Lớp ghi đầu ra: CSV chính (an toàn đa luồng) + file rejects để debug.

Hỗ trợ checkpoint: nếu file CSV đã tồn tại, nạp lại các khoá đã ghi để
chạy tiếp mà không trùng (resume).
"""

from __future__ import annotations

import csv
import os
import threading
from typing import Optional

from .schema import Domain
from .utils import normalize_key


class CsvWriter:
    def __init__(self, domain: Domain, path: str, *, encoding: str = "utf-8-sig",
                 write_rejects: bool = True):
        self.domain = domain
        self.path = path
        self.encoding = encoding
        self.write_rejects = write_rejects
        self.columns = domain.column_names
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

        self._file = None
        self._writer: Optional[csv.DictWriter] = None
        self._reject_file = None
        self._reject_writer: Optional[csv.writer] = None

    # ------------------------------------------------------------------
    def existing_keys(self) -> list[str]:
        """Đọc các khoá đã ghi từ CSV cũ (phục vụ resume). Rỗng nếu chưa có."""
        if not os.path.exists(self.path):
            return []
        key_col = self.domain.effective_dedup_key
        keys: list[str] = []
        try:
            with open(self.path, "r", encoding=self.encoding, newline="") as f:
                for row in csv.DictReader(f):
                    k = normalize_key(row.get(key_col, ""))
                    if k:
                        keys.append(k)
        except (OSError, csv.Error):
            return []
        return keys

    def open(self, *, append: bool) -> None:
        mode = "a" if append and os.path.exists(self.path) else "w"
        new_file = mode == "w"
        self._file = open(self.path, mode, encoding=self.encoding, newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self.columns, extrasaction="ignore")
        if new_file:
            self._writer.writeheader()
            self._file.flush()

        if self.write_rejects:
            reject_path = self._reject_path()
            rmode = "a" if append and os.path.exists(reject_path) else "w"
            self._reject_file = open(reject_path, rmode, encoding=self.encoding, newline="")
            self._reject_writer = csv.writer(self._reject_file)
            if rmode == "w":
                self._reject_writer.writerow(["reason", "detail", "raw_record"])
                self._reject_file.flush()

    def _reject_path(self) -> str:
        root, ext = os.path.splitext(self.path)
        return f"{root}_rejects{ext or '.csv'}"

    # ------------------------------------------------------------------
    def write_row(self, record: dict) -> None:
        with self._lock:
            assert self._writer is not None, "Writer chưa được open()"
            self._writer.writerow(record)
            self._file.flush()

    def write_reject(self, reason: str, detail: str, raw: dict | str) -> None:
        if not self.write_rejects or self._reject_writer is None:
            return
        with self._lock:
            self._reject_writer.writerow([reason, detail, str(raw)[:1000]])

    def close(self) -> None:
        with self._lock:
            for f in (self._file, self._reject_file):
                if f:
                    try:
                        f.flush()
                        f.close()
                    except OSError:
                        pass
            self._file = self._reject_file = None

    def __enter__(self) -> "CsvWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
