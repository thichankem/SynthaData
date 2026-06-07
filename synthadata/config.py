"""Lớp cấu hình.

Gộp cấu hình từ 3 nguồn (ưu tiên tăng dần):
    1. Giá trị mặc định trong code
    2. File config.yaml
    3. Tham số override truyền vào (thường từ CLI)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import yaml

from .presets import resolve_preset


# ---------------------------------------------------------------------------
# Cấu hình provider sinh văn bản (LLM)
# ---------------------------------------------------------------------------
@dataclass
class ProviderConfig:
    # "openai" (mọi endpoint tương thích OpenAI), "anthropic", hoặc "ollama"
    type: str = "ollama"

    # Tên model. Tuỳ provider:
    #   openai     -> ví dụ "gpt-4o-mini"
    #   anthropic  -> ví dụ "claude-sonnet-4-6"
    #   ollama     -> ví dụ "llama3.1", "qwen2.5", "mistral"
    model: str = "llama3.1"

    # --- Dùng cho provider API ngoài (openai / anthropic) ---
    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None

    # --- Dùng cho Ollama offline ---
    host: str = "http://localhost:11434"

    max_retries: int = 4
    timeout: int = 180

    # Buộc model trả JSON (response_format=json_object). Tắt cho vài dịch vụ
    # KHÔNG hỗ trợ (vd Perplexity) -> tránh lỗi 400.
    json_mode: bool = True

    # XOAY VÒNG API: danh sách endpoint phụ để luân phiên khi rate-limit/lỗi.
    # Mỗi mục là dict ghi đè vài trường của provider chính (kế thừa phần còn lại),
    # ví dụ chỉ cần {api_key_env: GROQ_API_KEY_2} hoặc đổi cả base_url/model.
    rotation: list = field(default_factory=list)
    # File chứa SIÊU NHIỀU key (mỗi dòng 1 key, có thể ghi tên preset đứng trước).
    # Nếu file tồn tại sẽ tự nạp và gộp vào vòng xoay. Để "" để tắt.
    keys_file: str = "keys.txt"
    # Dùng NỘI BỘ khi tách nhiều key: ép một key cụ thể cho backend đã nhân bản.
    api_key_override: Optional[str] = field(default=None, repr=False)

    def api_key(self) -> Optional[str]:
        if self.api_key_override is not None:
            return self.api_key_override
        return os.environ.get(self.api_key_env)

    def api_keys(self) -> list[str]:
        """Tách NHIỀU key từ biến môi trường (ngăn cách bởi dấu phẩy/xuống dòng).
        Cho phép gom nhiều key free vào 1 biến để xoay vòng, vd:
            GROQ_API_KEY=gsk_aaa,gsk_bbb,gsk_ccc
        """
        raw = self.api_key_override if self.api_key_override is not None else (
            os.environ.get(self.api_key_env) or "")
        keys: list[str] = []
        for chunk in raw.replace("\n", ",").split(","):
            k = chunk.strip()
            if k:
                keys.append(k)
        return keys


# ---------------------------------------------------------------------------
# Cấu hình embeddings (phục vụ chống TRÙNG NGỮ NGHĨA)
# ---------------------------------------------------------------------------
@dataclass
class EmbeddingConfig:
    # "ollama" | "openai" | "hashing" (lexical fallback, không cần model) | "none"
    type: str = "ollama"
    model: str = "nomic-embed-text"
    host: str = "http://localhost:11434"
    base_url: Optional[str] = None
    api_key_env: str = "OPENAI_API_KEY"
    timeout: int = 120
    max_retries: int = 3
    # Nếu embedder thật không sẵn sàng, tự lùi về hashing (lexical) để vẫn
    # có một lớp chống trùng "gần ngữ nghĩa" chạy liên tục.
    fallback_to_hashing: bool = True

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


# ---------------------------------------------------------------------------
# Cấu hình lớp kiểm tra chất lượng (QA) chạy liên tục
# ---------------------------------------------------------------------------
@dataclass
class QualityConfig:
    # Ngưỡng tương đồng chuỗi (0..1) để coi là trùng MỜ (lexical).
    fuzzy_threshold: float = 0.92
    # Bật chống trùng NGỮ NGHĨA bằng vector.
    semantic_enabled: bool = True
    # Ngưỡng cosine (0..1) để coi 2 bản ghi là trùng ngữ nghĩa.
    semantic_threshold: float = 0.90
    # In "snapshot" giám sát mỗi khi nhận thêm chừng này dòng.
    monitor_every: int = 100
    # Cửa sổ trượt để tính tỉ lệ chấp nhận gần đây.
    rolling_window: int = 200
    # Sinh THÍCH ỨNG: khi tỉ lệ chấp nhận tụt thấp -> tăng nhiệt để đa dạng hơn.
    adaptive: bool = True
    min_rolling_accept: float = 0.25
    temp_boost_step: float = 0.15
    temp_max: float = 1.3


# ---------------------------------------------------------------------------
# Cấu hình quá trình sinh dữ liệu
# ---------------------------------------------------------------------------
@dataclass
class GenerationConfig:
    target_rows: int = 1000          # số dòng hợp lệ cần đạt
    batch_size: int = 15             # số bản ghi xin model mỗi lần gọi
    workers: int = 4                 # số luồng gọi song song
    temperature: float = 0.9         # độ "sáng tạo" -> tăng đa dạng
    max_tokens: int = 4096           # giới hạn token đầu ra mỗi lần gọi
    # Dừng an toàn: tổng số lần gọi tối đa = target_rows * factor / batch_size
    max_attempts_factor: float = 6.0
    # Số mục đã sinh được lấy mẫu để nhắc model "đừng lặp lại".
    avoid_sample_size: int = 40
    # Số vòng liên tiếp không thêm được dòng mới thì coi như "cạn" và dừng.
    stall_rounds: int = 6
    # CHẾ ĐỘ augment: số dòng "hạt giống" sinh bằng API trước khi chuyển sang
    # Ollama offline để nhân bản phần còn lại (chỉ dùng khi mode = augment).
    seed_rows: int = 200


# ---------------------------------------------------------------------------
# Cấu hình đầu ra
# ---------------------------------------------------------------------------
@dataclass
class OutputConfig:
    path: str = "output/dataset.csv"
    checkpoint: bool = True
    write_rejects: bool = True
    encoding: str = "utf-8-sig"


def _default_offline() -> ProviderConfig:
    """Provider Ollama offline mặc định (dùng cho mode offline/hybrid/augment).
    Model GENERAL cho nội dung tự nhiên tốt hơn model coding/reasoning."""
    return ProviderConfig(type="ollama", model="gemma4:e4b")


@dataclass
class AppConfig:
    # CHẾ ĐỘ chạy: api | offline | hybrid | augment (xem README).
    mode: str = "api"
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    # Provider Ollama OFFLINE — dùng làm dự phòng (hybrid) hoặc nhân bản (augment).
    offline: ProviderConfig = field(default_factory=_default_offline)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    # -------------------------------------------------------------------
    @classmethod
    def load(cls, path: Optional[str] = None, overrides: Optional[dict] = None) -> "AppConfig":
        data: dict[str, Any] = {}
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        offline_data = data.get("offline")
        offline = (ProviderConfig(**cls._resolve_provider_dict(offline_data))
                   if offline_data else _default_offline())

        cfg = cls(
            mode=(data.get("mode") or "api").lower().strip(),
            provider=ProviderConfig(**cls._resolve_provider_dict(data.get("provider"))),
            offline=offline,
            embedding=EmbeddingConfig(**(data.get("embedding") or {})),
            quality=QualityConfig(**(data.get("quality") or {})),
            generation=GenerationConfig(**(data.get("generation") or {})),
            output=OutputConfig(**(data.get("output") or {})),
        )
        if overrides:
            cfg._apply_overrides(overrides)
        return cfg

    @staticmethod
    def _resolve_provider_dict(d: Optional[dict]) -> dict:
        """Mở 'preset' (nếu có) của provider chính: lấy mặc định từ preset rồi để
        các khai báo tường minh ĐÈ LÊN. Bỏ qua khoá 'preset' sau khi giải."""
        d = dict(d or {})
        preset = d.pop("preset", None)
        if preset:
            base = resolve_preset(preset)
            base.update(d)          # khai báo tường minh thắng preset
            d = base
        return d

    def _apply_overrides(self, overrides: dict) -> None:
        """Áp các override dạng phẳng từ CLI (bỏ qua giá trị None)."""
        gen_keys = {"target_rows", "batch_size", "workers", "temperature", "seed_rows"}
        for key, value in overrides.items():
            if value is None:
                continue
            if key == "mode":
                self.mode = str(value).lower().strip()
            elif key == "offline_model":
                self.offline.model = value
            elif key == "provider":
                self.provider.type = value
            elif key == "model":
                self.provider.model = value
            elif key == "base_url":
                self.provider.base_url = value
            elif key == "host":
                self.provider.host = value
            elif key == "output_path":
                self.output.path = value
            elif key == "embed_provider":
                self.embedding.type = value
            elif key == "embed_model":
                self.embedding.model = value
            elif key == "semantic_enabled":
                self.quality.semantic_enabled = value
            elif key in gen_keys:
                setattr(self.generation, key, value)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "provider": asdict(self.provider),
            "offline": asdict(self.offline),
            "embedding": asdict(self.embedding),
            "quality": asdict(self.quality),
            "generation": asdict(self.generation),
            "output": asdict(self.output),
        }
