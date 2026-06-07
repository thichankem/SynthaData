"""Lớp providers: trừu tượng hoá nguồn sinh văn bản (LLM).

Hai trường hợp theo yêu cầu:
    1. Gọi API ngoài  -> OpenAIProvider / AnthropicProvider
    2. Chạy offline   -> OllamaProvider (model cục bộ trên máy)

Hỗ trợ XOAY VÒNG: nếu cấu hình có nhiều key (1 biến chứa nhiều key ngăn bởi dấu
phẩy) hoặc có danh sách `rotation`, build_provider trả về RotatingProvider luân
phiên các backend (xem rotating.py).
"""

from __future__ import annotations

import os
import re
from dataclasses import replace
from typing import Optional

from ..config import ProviderConfig
from ..presets import known_presets, resolve_preset
from .base import LLMProvider
from .openai_api import OpenAIProvider
from .anthropic_api import AnthropicProvider
from .ollama import OllamaProvider
from .rotating import RotatingProvider

# Các trường một mục `rotation` có thể mang/ghi đè (cũng là phần kế thừa từ provider chính).
_PROVIDER_FIELDS = ("type", "model", "api_key_env", "base_url", "host",
                    "max_retries", "timeout", "json_mode")
# Trường CHUNG (không đặc thù endpoint) -> preset thiếu thì mượn của provider chính.
_GENERIC_FIELDS = ("max_retries", "timeout")
_API_KINDS = ("openai", "openai-compatible", "compatible", "anthropic", "claude")


def _build_single(cfg: ProviderConfig) -> LLMProvider:
    """Tạo một provider ĐƠN đúng loại từ cấu hình."""
    kind = (cfg.type or "").lower().strip()
    if kind in ("openai", "openai-compatible", "compatible"):
        return OpenAIProvider(cfg)
    if kind in ("anthropic", "claude"):
        return AnthropicProvider(cfg)
    if kind in ("ollama", "local", "offline"):
        return OllamaProvider(cfg)
    raise ValueError(
        f"Provider không hỗ trợ: '{cfg.type}'. "
        f"Chọn một trong: openai | anthropic | ollama."
    )


def _merge_entry(parent: ProviderConfig, entry: dict) -> ProviderConfig:
    """Dựng cấu hình cho MỘT mục `rotation`.

    - Có `preset`: lấy mặc định từ preset, mượn trường chung (timeout...) của
      provider chính, rồi để khai báo tường minh trong mục ĐÈ LÊN.
    - Không `preset`: kế thừa toàn bộ provider chính, chỉ ghi đè phần khai báo.
    """
    entry = dict(entry or {})
    preset = entry.pop("preset", None)
    if preset:
        data = resolve_preset(preset)
        for f in _GENERIC_FIELDS:
            data.setdefault(f, getattr(parent, f))
    else:
        data = {f: getattr(parent, f) for f in _PROVIDER_FIELDS}
    for key, value in entry.items():
        if key in _PROVIDER_FIELDS:
            data[key] = value
    return ProviderConfig(**{k: v for k, v in data.items() if k in _PROVIDER_FIELDS})


def _read_keys_file(path: str) -> list[tuple[Optional[str], str]]:
    """Đọc file 'siêu nhiều key'. Mỗi dòng (bỏ qua dòng trống và dòng bắt đầu '#'):
        gsk_aaa                 -> key cho PROVIDER CHÍNH
        groq gsk_bbb            -> key cho dịch vụ 'groq' (tên preset đứng trước)
        gemini: AIza...         -> ngăn cách bằng khoảng trắng / ':' / '=' / ','
    Trả danh sách (preset|None, key)."""
    if not path or not os.path.exists(path):
        return []
    known = set(known_presets())
    out: list[tuple[Optional[str], str]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = re.split(r"[\s:=,]+", line, maxsplit=1)
                if len(parts) == 2 and parts[0].lower() in known:
                    out.append((parts[0].lower(), parts[1].strip()))
                else:
                    out.append((None, line))         # cả dòng là 1 key
    except OSError:
        return []
    return out


def _expand_backends(cfg: ProviderConfig) -> list[ProviderConfig]:
    """Bung provider chính + các mục rotation + file keys thành danh sách backend.
    Mỗi key (trong biến môi trường, hoặc file) -> một backend riêng. Khử trùng theo
    (type, base_url, model, key) để không tạo backend lặp."""
    backends: list[ProviderConfig] = []
    seen: set = set()

    def add(entry: ProviderConfig, key: Optional[str]) -> None:
        c = replace(entry, api_key_override=key, rotation=[], keys_file="")
        sig = (c.type, c.base_url, c.model, c.api_key())
        if sig in seen:
            return
        seen.add(sig)
        backends.append(c)

    # 1) Provider chính + các mục rotation, mỗi cái nhân theo key trong biến môi trường.
    entries = [cfg] + [_merge_entry(cfg, e) for e in (cfg.rotation or [])]
    for entry in entries:
        kind = (entry.type or "").lower().strip()
        if kind in _API_KINDS:
            keys = entry.api_keys()
            if keys:
                for k in keys:
                    add(entry, k)
            else:
                add(entry, None)                     # chưa có key -> health_check sẽ báo
        else:
            add(entry, None)                          # ollama (không cần key)

    # 2) File 'siêu nhiều key' -> gộp thêm vào vòng.
    for preset, key in _read_keys_file(cfg.keys_file):
        entry = _merge_entry(cfg, {"preset": preset}) if preset else cfg
        add(entry, key)

    return backends


def build_provider(cfg: ProviderConfig) -> LLMProvider:
    """Factory: tạo provider đơn, hoặc provider XOAY VÒNG nếu có nhiều backend."""
    backend_cfgs = _expand_backends(cfg)
    providers = [_build_single(c) for c in backend_cfgs]
    if len(providers) == 1:
        return providers[0]
    return RotatingProvider(providers, cfg)


__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "RotatingProvider",
    "build_provider",
]
