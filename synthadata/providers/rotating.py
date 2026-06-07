"""Provider XOAY VÒNG: luân phiên nhiều backend (nhiều key / nhiều endpoint).

Mục đích: gom nhiều key free (vd nhiều key Groq) hoặc nhiều dịch vụ (Groq +
Gemini + OpenRouter...) để NHÂN throughput và TỰ NÉ rate-limit của bản miễn phí.

Cơ chế:
  - Mỗi lần gọi chọn backend kế tiếp theo VÒNG TRÒN (round-robin) -> chia tải đều.
  - Backend nào lỗi/đụng rate-limit (429) -> bị cho NGHỈ TẠM (cooldown) một lúc và
    bỏ qua trong các lần gọi kế, dồn lưu lượng sang cái đang khỏe. Hết cooldown
    thì tự quay lại vòng. Nếu mọi backend đều đang nghỉ -> chọn cái sắp hết nghỉ
    sớm nhất.
An toàn đa luồng: chỉ số xoay vòng + bảng cooldown được bảo vệ bằng khoá.
"""

from __future__ import annotations

import threading
import time

from ..config import ProviderConfig
from .base import LLMProvider, ProviderError, RateLimitError

# Backend dính 429 nhưng KHÔNG có header thời gian -> nghỉ tạm chừng này; lỗi
# khác (mạng, 5xx) -> nghỉ ngắn. Nếu có header Retry-After thì dùng đúng nó.
_COOLDOWN_RATELIMIT = 20.0
_COOLDOWN_OTHER = 8.0
_COOLDOWN_MAX = 120.0


def _is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return ("429" in s or "rate limit" in s or "too many requests" in s
            or "quota" in s or "resource_exhausted" in s or "insufficient balance" in s
            or "402" in s)


class RotatingProvider(LLMProvider):
    def __init__(self, backends: list[LLMProvider], cfg: ProviderConfig,
                 fallback: list[bool] | None = None):
        super().__init__(cfg)
        if not backends:
            raise ValueError("RotatingProvider cần ít nhất 1 backend.")
        self._backends = list(backends)
        # fallback[i] = True -> backend dự phòng, CHỈ dùng khi mọi backend chính
        # đang nghỉ (vd Ollama offline làm phao cứu sinh khi API hết quota).
        self._fallback = list(fallback) if fallback else [False] * len(self._backends)
        self._cooldown_until = [0.0] * len(self._backends)
        self._i = 0
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        extra = len(self._backends) - 1
        suffix = f" +{extra}" if extra > 0 else ""
        return f"rotating[{len(self._backends)}]:{self._backends[0].name}{suffix}"

    # ------------------------------------------------------------------
    def _rr(self, candidates: list[int]) -> int:
        """Lấy ứng viên kế tiếp theo VÒNG TRÒN trong danh sách cho trước."""
        cands = set(candidates)
        n = len(self._backends)
        for _ in range(n):
            i = self._i
            self._i = (self._i + 1) % n
            if i in cands:
                return i
        return candidates[0]

    def _pick(self) -> tuple[int, float]:
        """Chọn backend: ưu tiên CHÍNH đang rảnh -> DỰ PHÒNG đang rảnh -> (nếu tất
        cả đang nghỉ) cái sắp hồi sớm nhất + số giây cần chờ."""
        with self._lock:
            n = len(self._backends)
            now = time.monotonic()
            primary = [j for j in range(n)
                       if not self._fallback[j] and self._cooldown_until[j] <= now]
            if primary:
                return self._rr(primary), 0.0
            fb = [j for j in range(n)
                  if self._fallback[j] and self._cooldown_until[j] <= now]
            if fb:
                return self._rr(fb), 0.0
            i = min(range(n), key=lambda j: (self._cooldown_until[j], self._fallback[j]))
            return i, max(0.0, self._cooldown_until[i] - now)

    def _penalize(self, i: int, err: Exception) -> None:
        if isinstance(err, RateLimitError) and err.retry_after is not None:
            cd = min(err.retry_after + 0.5, _COOLDOWN_MAX)   # đợi đúng lúc bucket hồi
        elif _is_rate_limit(err):
            cd = _COOLDOWN_RATELIMIT
        else:
            cd = _COOLDOWN_OTHER
        with self._lock:
            self._cooldown_until[i] = time.monotonic() + cd

    # ------------------------------------------------------------------
    def health_check(self) -> None:
        """Kiểm tra từng backend; loại cái hỏng, giữ cái khoẻ. Raise nếu KHÔNG
        còn cái nào sống."""
        healthy: list[LLMProvider] = []
        healthy_fb: list[bool] = []
        errors: list[str] = []
        for b, fb in zip(self._backends, self._fallback):
            try:
                b.health_check()
                healthy.append(b)
                healthy_fb.append(fb)
            except Exception as err:  # noqa: BLE001 - gom để báo cáo, không sập
                errors.append(f"{b.name}: {err}")
        if not healthy:
            raise ProviderError(
                "Không backend nào sẵn sàng để xoay vòng:\n  - "
                + "\n  - ".join(errors)
            )
        if errors:
            print(f"[cảnh báo] {len(errors)} backend bị loại khỏi xoay vòng:")
            for e in errors:
                print(f"           - {e}")
        with self._lock:
            self._backends = healthy
            self._fallback = healthy_fb
            self._cooldown_until = [0.0] * len(healthy)
            self._i = 0
        print(f"[ok] Xoay vòng {len(healthy)} backend: "
              + ", ".join(b.name for b in healthy))

    # ------------------------------------------------------------------
    def _call(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        # Lớp cha yêu cầu cài _call; ở đây ta override chat() nên _call chỉ là
        # đường dự phòng -> uỷ quyền cho backend kế tiếp.
        i, _ = self._pick()
        return self._backends[i]._call(
            system, user, temperature=temperature, max_tokens=max_tokens)

    def chat(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        n = len(self._backends)
        attempts = max(self.cfg.max_retries, 1) * n + n
        last_err: Exception | None = None
        slept = 0.0
        for _ in range(attempts):
            i, wait = self._pick()
            if wait > 0:                    # mọi backend đang nghỉ -> chờ cái sắp hồi sớm nhất
                if slept >= 90.0:           # đã chờ quá lâu trong một lần gọi -> bỏ cuộc
                    break
                s = min(wait, 30.0)
                time.sleep(s)
                slept += s
            try:
                content = self._backends[i]._call(
                    system, user, temperature=temperature, max_tokens=max_tokens)
                if content and content.strip():
                    return content
                # Phản hồi RỖNG (vd model reasoning tiêu hết token cho phần suy luận)
                # -> coi như lỗi mềm: phạt cooldown để TỰ LOẠI backend vô dụng.
                last_err = ProviderError(f"{self._backends[i].name}: phản hồi rỗng")
                self._penalize(i, last_err)
            except Exception as err:  # noqa: BLE001 - lỗi/429 -> phạt cooldown, thử cái khác
                last_err = err
                self._penalize(i, err)
        raise ProviderError(
            f"{self.name}: tất cả {n} backend đều lỗi sau {attempts} lần thử: {last_err}"
        )
