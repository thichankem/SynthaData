"""Dựng provider theo CHẾ ĐỘ chạy (mode).

    api      : chỉ dùng API online (xoay vòng nhiều key/dịch vụ).
    offline  : chỉ dùng Ollama cục bộ (không mạng, không quota).
    hybrid   : API là chính; Ollama offline làm DỰ PHÒNG khi API hết quota/kẹt.
    augment  : pha 1 dùng API sinh "hạt giống" chất lượng -> pha 2 Ollama offline
               nhân bản thêm cho đông (generator tự chuyển provider giữa chừng).
"""

from __future__ import annotations

from dataclasses import replace

from .config import AppConfig, ProviderConfig
from .providers import _build_single, _expand_backends, build_provider
from .providers.base import LLMProvider
from .providers.rotating import RotatingProvider

VALID_MODES = ("api", "offline", "hybrid", "augment")


def _pure_offline(cfg: AppConfig) -> ProviderConfig:
    """Cấu hình Ollama THUẦN: bỏ keys_file/rotation để KHÔNG kéo nhầm backend API."""
    return replace(cfg.offline, keys_file="", rotation=[])


def build_generation_provider(cfg: AppConfig) -> LLMProvider:
    """Provider dùng để SINH ở pha CHÍNH, tuỳ mode."""
    mode = cfg.mode
    if mode == "offline":
        return build_provider(_pure_offline(cfg))
    if mode == "hybrid":
        return build_hybrid_provider(cfg)
    # api | augment (augment: pha 1 = API; pha 2 do generator tự chuyển sang Ollama)
    return build_provider(cfg.provider)


def build_hybrid_provider(cfg: AppConfig) -> LLMProvider:
    """API (xoay vòng) + Ollama offline làm DỰ PHÒNG khi mọi API đang kẹt."""
    api_backends = [_build_single(c) for c in _expand_backends(cfg.provider)]
    ollama = _build_single(_pure_offline(cfg))
    backends = api_backends + [ollama]
    fallback = [False] * len(api_backends) + [True]
    return RotatingProvider(backends, cfg.provider, fallback=fallback)


def build_phase2_provider(cfg: AppConfig) -> LLMProvider | None:
    """Provider PHA 2 cho mode augment: Ollama offline nhân bản phần còn lại."""
    if cfg.mode == "augment":
        return build_provider(_pure_offline(cfg))
    return None
