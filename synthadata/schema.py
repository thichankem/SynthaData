"""Lớp định nghĩa domain / schema dữ liệu.

Một "domain" mô tả bộ dữ liệu cần sinh: chủ đề, các cột, quy tắc hợp lệ,
và các "facet" (lát cắt chủ đề) giúp tăng độ đa dạng khi sinh số lượng lớn.
Domain được nạp từ file YAML để dễ tái sử dụng cho mọi loại dữ liệu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class Column:
    name: str                       # tên cột (header CSV)
    description: str = ""           # mô tả để model hiểu phải sinh gì
    type: str = "text"             # text | number | enum | bool
    required: bool = True           # bắt buộc có giá trị?
    min_len: int = 0                # độ dài tối thiểu (cột text)
    max_len: int = 2000             # độ dài tối đa (cột text)
    enum: list[str] = field(default_factory=list)  # tập giá trị hợp lệ (type=enum)

    def spec_line(self) -> str:
        """Một dòng đặc tả cột để đưa vào prompt."""
        parts = [f'- "{self.name}" ({self.type})']
        if self.description:
            parts.append(f": {self.description}")
        if self.type == "enum" and self.enum:
            parts.append(f" [chỉ chọn một trong: {', '.join(self.enum)}]")
        if not self.required:
            parts.append(" [có thể để trống]")
        return "".join(parts)


@dataclass
class Domain:
    name: str                       # tên domain (vd: diseases)
    topic: str                      # mô tả chủ đề cho model
    columns: list[Column]
    # Cột dùng làm khoá chống trùng lặp (vd: disease_name).
    dedup_key: str = ""
    # Lời nhắc hệ thống tuỳ chỉnh (nếu trống dùng mặc định).
    system: str = ""
    # Ngôn ngữ đầu ra mong muốn cho các trường text.
    language: str = "English"
    # Các lát cắt chủ đề để luân phiên -> bao phủ rộng, ít trùng.
    facets: list[str] = field(default_factory=list)
    # Các cột ghép thành "chữ ký ngữ nghĩa" để nhúng vector (chống trùng ngữ
    # nghĩa). Để trống -> tự chọn khoá + cột text dài nhất.
    semantic_fields: list[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def column(self, name: str) -> Optional[Column]:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    @property
    def effective_dedup_key(self) -> str:
        """Khoá chống trùng: ưu tiên cấu hình, không có thì lấy cột đầu."""
        if self.dedup_key and self.column(self.dedup_key):
            return self.dedup_key
        return self.columns[0].name if self.columns else ""

    # -------------------------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "Domain":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if "columns" not in data or not data["columns"]:
            raise ValueError(f"Domain '{path}' thiếu danh sách 'columns'.")

        columns = [Column(**col) for col in data["columns"]]
        return cls(
            name=data.get("name", "dataset"),
            topic=data.get("topic", data.get("name", "")),
            columns=columns,
            dedup_key=data.get("dedup_key", ""),
            system=data.get("system", ""),
            language=data.get("language", "English"),
            facets=data.get("facets", []) or [],
            semantic_fields=data.get("semantic_fields", []) or [],
        )
