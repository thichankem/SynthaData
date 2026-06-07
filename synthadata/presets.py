"""Preset các dịch vụ API chatbot phổ biến (gọi theo TÊN NGẮN, khỏi nhớ URL).

Hầu hết các dịch vụ đều có endpoint TƯƠNG THÍCH OPENAI nên dùng chung
OpenAIProvider, chỉ khác `base_url` + biến môi trường chứa key. Claude (Anthropic)
có giao thức riêng -> type "anthropic".

Dùng trong config.yaml:
    provider:
      preset: groq                      # tự điền type/base_url/api_key_env/model
    # hoặc trong danh sách xoay vòng:
      rotation:
        - { preset: gemini }
        - { preset: deepseek, model: deepseek-chat }

Mỗi preset chỉ là GIÁ TRỊ MẶC ĐỊNH — khai báo tường minh (model, api_key_env...)
luôn ĐÈ LÊN preset. Tên model có thể đổi theo thời gian; chỉnh lại nếu cần.

Module này KHÔNG import gì trong gói -> tránh vòng lặp import (config + providers
đều nạp được an toàn).
"""

from __future__ import annotations

# Cờ riêng: `json_mode: False` cho dịch vụ KHÔNG nhận response_format=json_object.
PRESETS: dict[str, dict] = {
    # ----- Miễn phí / có bậc free rộng (khuyến nghị cho dự án này) -----
    "groq": {
        "type": "openai", "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY", "model": "llama-3.3-70b-versatile",
    },
    "gemini": {  # Google AI Studio — endpoint tương thích OpenAI
        "type": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY", "model": "gemini-2.0-flash",
    },
    "openrouter": {  # nhiều model gắn nhãn ":free"
        "type": "openai", "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "cerebras": {
        "type": "openai", "base_url": "https://api.cerebras.ai/v1",
        "api_key_env": "CEREBRAS_API_KEY", "model": "gpt-oss-120b",
    },
    "together": {
        "type": "openai", "base_url": "https://api.together.xyz/v1",
        "api_key_env": "TOGETHER_API_KEY",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    },
    # ----- Trả phí / freemium -----
    "deepseek": {
        "type": "openai", "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY", "model": "deepseek-chat",
    },
    "mistral": {
        "type": "openai", "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY", "model": "mistral-small-latest",
    },
    "xai": {  # Grok của xAI
        "type": "openai", "base_url": "https://api.x.ai/v1",
        "api_key_env": "XAI_API_KEY", "model": "grok-2-latest",
    },
    "fireworks": {
        "type": "openai", "base_url": "https://api.fireworks.ai/inference/v1",
        "api_key_env": "FIREWORKS_API_KEY",
        "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    },
    "perplexity": {
        "type": "openai", "base_url": "https://api.perplexity.ai",
        "api_key_env": "PERPLEXITY_API_KEY", "model": "sonar",
        "json_mode": False,  # Perplexity không nhận response_format=json_object
    },
    "openai": {
        "type": "openai", "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY", "model": "gpt-4o-mini",
    },
    "anthropic": {  # Claude — giao thức riêng
        "type": "anthropic", "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-3-5-haiku-latest",
    },
    # ----- Cục bộ -----
    "ollama": {
        "type": "ollama", "host": "http://localhost:11434",
        "model": "qwen2.5-coder:7b",
    },
}


def known_presets() -> list[str]:
    return sorted(PRESETS)


def resolve_preset(name: str) -> dict:
    """Trả bản SAO cấu hình của preset (dict các trường ProviderConfig)."""
    key = (name or "").lower().strip()
    if key not in PRESETS:
        raise ValueError(
            f"Preset không biết: '{name}'. Hỗ trợ: {', '.join(known_presets())}."
        )
    return dict(PRESETS[key])
