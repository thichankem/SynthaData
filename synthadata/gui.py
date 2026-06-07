"""Giao diện đồ hoạ (GUI) cho SynthaData.

Bọc lại toàn bộ dây chuyền sinh dữ liệu (provider + embedding + QA + ghi CSV)
trong một cửa sổ Tkinter — KHÔNG cần cài thêm thư viện (Tkinter có sẵn trong
Python chuẩn). Việc sinh chạy ở luồng nền nên cửa sổ không bị treo; có nút Dừng,
thanh tiến trình và log thời gian thực.

Chạy:  python -m synthadata.gui      (hoặc:  python -m synthadata --gui)
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from typing import Optional

import requests

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

try:
    from dotenv import load_dotenv

    load_dotenv()  # nạp API key từ .env nếu có
except ImportError:
    pass

from .config import AppConfig
from .embeddings import build_embedder
from .embeddings.hashing import HashingEmbedder
from .generator import DataGenerator
from .modes import build_generation_provider, build_phase2_provider
from .providers.base import ProviderError
from .schema import Domain
from .writer import CsvWriter

# Gợi ý model + biến môi trường key theo từng provider (đổ vào form khi chọn).
_PROVIDER_DEFAULTS = {
    "ollama": {"model": "llama3.1", "api_key_env": "OPENAI_API_KEY"},
    "openai": {"model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
    "anthropic": {"model": "claude-sonnet-4-6", "api_key_env": "ANTHROPIC_API_KEY"},
}

# Gợi ý sẵn trong dropdown model cho provider API (vẫn gõ tay được).
_SUGGESTED_MODELS = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
}

# --- Bảng màu cho giao diện (theme clam, phẳng & sắc nét) ------------------
_BG = "#f3f4f6"        # nền cửa sổ
_CARD = "#ffffff"      # nền ô nhập
_FG = "#1f2937"        # chữ chính
_MUTED = "#6b7280"     # chữ phụ / disabled
_BORDER = "#d1d5db"    # viền
_ACCENT = "#2563eb"    # xanh nhấn
_ACCENT_ACT = "#1d4ed8"
_DANGER = "#dc2626"    # đỏ (nút Dừng)
_DANGER_ACT = "#b91c1c"
_DISABLED_BG = "#eceef1"


def _list_ollama_models(host: str, timeout: float = 5.0) -> list[str]:
    """Trả về tên các model Ollama đã cài trên máy (gọi /api/tags). Raise nếu lỗi."""
    url = host.rstrip("/") + "/api/tags"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    models = resp.json().get("models", [])
    return sorted(m.get("name", "") for m in models if m.get("name"))


def _enable_hidpi() -> None:
    """Bật DPI-aware trên Windows để chữ/đường nét sắc, không bị kéo mờ trên
    màn hình tỉ lệ cao (125%/150%...). Gọi TRƯỚC khi tạo cửa sổ Tk."""
    if sys.platform != "win32":
        return
    import ctypes
    try:  # System DPI aware (tương thích rộng nhất)
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass


def _apply_style(root: tk.Tk) -> None:
    """Phối theme clam + font Segoe UI + tỉ lệ theo DPI cho nét và đồng nhất."""
    try:
        dpi = float(root.winfo_fpixels("1i"))
    except tk.TclError:
        dpi = 96.0
    if dpi > 0:
        root.tk.call("tk", "scaling", dpi / 72.0)

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family="Segoe UI", size=10)
        except tk.TclError:
            pass

    root.configure(bg=_BG)
    # Màu danh sách xổ xuống của combobox (Listbox dùng option database).
    root.option_add("*TCombobox*Listbox.background", _CARD)
    root.option_add("*TCombobox*Listbox.foreground", _FG)
    root.option_add("*TCombobox*Listbox.selectBackground", _ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass

    st.configure(".", background=_BG, foreground=_FG, font=("Segoe UI", 10))
    st.configure("TFrame", background=_BG)
    st.configure("TLabel", background=_BG, foreground=_FG)
    st.configure("Muted.TLabel", foreground=_MUTED)
    st.configure("Title.TLabel", font=("Segoe UI Semibold", 16), foreground=_FG)
    st.configure("TCheckbutton", background=_BG, foreground=_FG)
    st.map("TCheckbutton", background=[("active", _BG)])

    st.configure("TLabelframe", background=_BG, bordercolor=_BORDER,
                 relief="solid", borderwidth=1, padding=8)
    st.configure("TLabelframe.Label", background=_BG, foreground=_ACCENT,
                 font=("Segoe UI Semibold", 10))

    # Nút thường
    st.configure("TButton", background="#e5e7eb", foreground=_FG,
                 bordercolor=_BORDER, relief="flat", padding=(12, 6))
    st.map("TButton",
           background=[("active", "#d1d5db"), ("disabled", "#f0f1f3")],
           foreground=[("disabled", _MUTED)])
    # Nút nhấn (Bắt đầu sinh)
    st.configure("Accent.TButton", background=_ACCENT, foreground="#ffffff",
                 font=("Segoe UI Semibold", 10), padding=(16, 7), relief="flat")
    st.map("Accent.TButton",
           background=[("active", _ACCENT_ACT), ("disabled", "#a9c0f5")],
           foreground=[("disabled", "#eef2ff")])
    # Nút Dừng
    st.configure("Danger.TButton", background=_DANGER, foreground="#ffffff",
                 padding=(14, 7), relief="flat")
    st.map("Danger.TButton",
           background=[("active", _DANGER_ACT), ("disabled", "#e6a6a6")],
           foreground=[("disabled", "#fff0f0")])

    # Ô nhập liệu
    for elem in ("TEntry", "TCombobox", "TSpinbox"):
        st.configure(elem, fieldbackground=_CARD, background=_CARD,
                     bordercolor=_BORDER, foreground=_FG, padding=4)
        st.map(elem,
               fieldbackground=[("disabled", _DISABLED_BG), ("readonly", _CARD)],
               foreground=[("disabled", _MUTED)],
               bordercolor=[("focus", _ACCENT)])
    st.configure("TSpinbox", arrowsize=13)
    st.configure("TCombobox", arrowsize=13)

    st.configure("Horizontal.TProgressbar", background=_ACCENT,
                 troughcolor="#e5e7eb", bordercolor=_BG, thickness=16)


class _QueueWriter:
    """File-like: gom stdout/stderr trong lúc sinh rồi đẩy từng DÒNG vào queue
    để luồng GUI hiển thị. An toàn cho việc redirect tạm thời sys.stdout."""

    def __init__(self, q: "queue.Queue"):
        self._q = q
        self._buf = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._q.put(("log", line))
        return len(text)

    def flush(self) -> None:
        if self._buf:
            self._q.put(("log", self._buf))
            self._buf = ""


class SynthaDataGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SynthaData — Sinh dữ liệu tổng hợp")
        self.root.minsize(820, 720)

        self._queue: "queue.Queue" = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._config_path = "config.yaml"

        # Nạp giá trị mặc định từ config.yaml (nếu có) để đổ vào form.
        seed = AppConfig.load(self._config_path)
        self._build_vars(seed)
        self._build_ui()
        self._apply_provider_state()  # đồng bộ trạng thái bật/tắt ô theo provider
        # Luôn nạp model Ollama trên máy khi mở (dropdown offline cần, kể cả khi
        # provider là API). Lỗi (Ollama chưa chạy) chỉ hiện status, không sao.
        self.root.after(250, self._refresh_ollama_models)

        # Bơm tin nhắn từ luồng nền về GUI mỗi 80ms.
        self.root.after(80, self._drain_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ vars
    def _build_vars(self, cfg: AppConfig) -> None:
        # Chế độ chạy + model offline
        self.v_mode = tk.StringVar(value=cfg.mode)
        self.v_offline_model = tk.StringVar(value=cfg.offline.model)
        # Domain + provider
        self.v_domain = tk.StringVar(value="domains/diseases.yaml")
        self.v_provider = tk.StringVar(value=cfg.provider.type)
        self.v_model = tk.StringVar(value=cfg.provider.model)
        self.v_host = tk.StringVar(value=cfg.provider.host)
        self.v_base_url = tk.StringVar(value=cfg.provider.base_url or "")
        self.v_key_env = tk.StringVar(value=cfg.provider.api_key_env)
        self.v_api_key = tk.StringVar(value="")

        # Embedding + chống trùng
        self.v_embed_type = tk.StringVar(value=cfg.embedding.type)
        self.v_embed_model = tk.StringVar(value=cfg.embedding.model)
        self.v_embed_host = tk.StringVar(value=cfg.embedding.host)
        self.v_semantic = tk.BooleanVar(value=cfg.quality.semantic_enabled)
        self.v_sem_thr = tk.StringVar(value=str(cfg.quality.semantic_threshold))
        self.v_fuzzy_thr = tk.StringVar(value=str(cfg.quality.fuzzy_threshold))

        # Sinh
        self.v_target = tk.StringVar(value=str(cfg.generation.target_rows))
        self.v_batch = tk.StringVar(value=str(cfg.generation.batch_size))
        self.v_workers = tk.StringVar(value=str(cfg.generation.workers))
        self.v_temp = tk.StringVar(value=str(cfg.generation.temperature))
        self.v_max_tokens = tk.StringVar(value=str(cfg.generation.max_tokens))

        # Đầu ra
        self.v_out = tk.StringVar(value=cfg.output.path)
        self.v_resume = tk.BooleanVar(value=True)
        self.v_rejects = tk.BooleanVar(value=cfg.output.write_rejects)

        self.v_status = tk.StringVar(value="Sẵn sàng.")

    # -------------------------------------------------------------------- ui
    def _build_ui(self) -> None:
        pad = {"padx": 6, "pady": 3}
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        # ---- Tiêu đề --------------------------------------------------------
        head = ttk.Frame(outer)
        head.pack(fill="x", pady=(0, 10))
        ttk.Label(head, text="SynthaData", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="Sinh dữ liệu tổng hợp · xuất CSV",
                  style="Muted.TLabel").pack(side="left", padx=(10, 0), pady=(6, 0))

        # ---- Domain + đầu ra ------------------------------------------------
        g_io = ttk.LabelFrame(outer, text="Domain & Đầu ra", padding=8)
        g_io.pack(fill="x")
        g_io.columnconfigure(1, weight=1)

        ttk.Label(g_io, text="File domain (YAML):").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(g_io, textvariable=self.v_domain).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(g_io, text="Chọn…", command=self._pick_domain).grid(row=0, column=2, **pad)

        ttk.Label(g_io, text="File CSV đầu ra:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(g_io, textvariable=self.v_out).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(g_io, text="Chọn…", command=self._pick_output).grid(row=1, column=2, **pad)

        opts = ttk.Frame(g_io)
        opts.grid(row=2, column=1, sticky="w", **pad)
        ttk.Checkbutton(opts, text="Chạy tiếp (resume) nếu đã có file",
                        variable=self.v_resume).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(opts, text="Ghi file *_rejects.csv",
                        variable=self.v_rejects).pack(side="left")

        # ---- Chế độ chạy ----------------------------------------------------
        g_mode = ttk.LabelFrame(outer, text="Chế độ chạy", padding=8)
        g_mode.pack(fill="x", pady=(8, 0))
        ttk.Label(g_mode, text="Chế độ:").pack(side="left", **pad)
        self.cb_mode = ttk.Combobox(
            g_mode, textvariable=self.v_mode, state="readonly", width=9,
            values=["api", "offline", "hybrid", "augment"])
        self.cb_mode.pack(side="left", **pad)
        ttk.Label(g_mode, text="(api · offline · hybrid · augment)").pack(side="left", **pad)
        ttk.Label(g_mode, text="Model Ollama offline:").pack(side="left", padx=(12, 2))
        # Dropdown LIỆT KÊ MỌI model Ollama đã cài (vẫn gõ tay được).
        self.cb_offline_model = ttk.Combobox(g_mode, textvariable=self.v_offline_model, width=22)
        self.cb_offline_model.pack(side="left")
        ttk.Button(g_mode, text="⟳", width=3,
                   command=self._refresh_ollama_models).pack(side="left", padx=(4, 0))

        # ---- Provider (LLM) -------------------------------------------------
        g_p = ttk.LabelFrame(outer, text="Nguồn sinh văn bản (LLM) — dùng khi có API", padding=8)
        g_p.pack(fill="x", pady=(8, 0))
        g_p.columnconfigure(1, weight=1)
        g_p.columnconfigure(3, weight=1)

        ttk.Label(g_p, text="Provider:").grid(row=0, column=0, sticky="w", **pad)
        self.cb_provider = ttk.Combobox(g_p, textvariable=self.v_provider, state="readonly",
                                        values=["ollama", "openai", "anthropic"], width=14)
        self.cb_provider.grid(row=0, column=1, sticky="w", **pad)
        self.cb_provider.bind("<<ComboboxSelected>>", lambda _e: self._on_provider_change())

        ttk.Label(g_p, text="Model:").grid(row=0, column=2, sticky="e", **pad)
        mf = ttk.Frame(g_p)
        mf.grid(row=0, column=3, sticky="ew", **pad)
        mf.columnconfigure(0, weight=1)
        self.cb_model = ttk.Combobox(mf, textvariable=self.v_model)
        self.cb_model.grid(row=0, column=0, sticky="ew")
        self.btn_refresh_models = ttk.Button(mf, text="⟳", width=3,
                                             command=self._refresh_ollama_models)
        self.btn_refresh_models.grid(row=0, column=1, padx=(4, 0))

        self.lbl_host = ttk.Label(g_p, text="Host Ollama:")
        self.lbl_host.grid(row=1, column=0, sticky="w", **pad)
        self.ent_host = ttk.Entry(g_p, textvariable=self.v_host)
        self.ent_host.grid(row=1, column=1, sticky="ew", **pad)

        self.lbl_base = ttk.Label(g_p, text="Base URL (API):")
        self.lbl_base.grid(row=1, column=2, sticky="e", **pad)
        self.ent_base = ttk.Entry(g_p, textvariable=self.v_base_url)
        self.ent_base.grid(row=1, column=3, sticky="ew", **pad)

        self.lbl_keyenv = ttk.Label(g_p, text="Tên biến môi trường key:")
        self.lbl_keyenv.grid(row=2, column=0, sticky="w", **pad)
        self.ent_keyenv = ttk.Entry(g_p, textvariable=self.v_key_env)
        self.ent_keyenv.grid(row=2, column=1, sticky="ew", **pad)

        self.lbl_key = ttk.Label(g_p, text="API key (tuỳ chọn):")
        self.lbl_key.grid(row=2, column=2, sticky="e", **pad)
        self.ent_key = ttk.Entry(g_p, textvariable=self.v_api_key, show="•")
        self.ent_key.grid(row=2, column=3, sticky="ew", **pad)

        # ---- Embedding / chống trùng ngữ nghĩa ------------------------------
        g_e = ttk.LabelFrame(outer, text="Chống trùng ngữ nghĩa (embedding)", padding=8)
        g_e.pack(fill="x", pady=(8, 0))
        g_e.columnconfigure(1, weight=1)
        g_e.columnconfigure(3, weight=1)

        ttk.Checkbutton(g_e, text="Bật chống trùng ngữ nghĩa (vector)",
                        variable=self.v_semantic,
                        command=self._on_semantic_toggle).grid(
            row=0, column=0, columnspan=2, sticky="w", **pad)

        ttk.Label(g_e, text="Nguồn embedding:").grid(row=1, column=0, sticky="w", **pad)
        self.cb_embed = ttk.Combobox(g_e, textvariable=self.v_embed_type, state="readonly",
                                     values=["ollama", "openai", "hashing", "none"], width=14)
        self.cb_embed.grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(g_e, text="Model embedding:").grid(row=1, column=2, sticky="e", **pad)
        self.ent_embed_model = ttk.Entry(g_e, textvariable=self.v_embed_model)
        self.ent_embed_model.grid(row=1, column=3, sticky="ew", **pad)

        ttk.Label(g_e, text="Host embedding:").grid(row=2, column=0, sticky="w", **pad)
        self.ent_embed_host = ttk.Entry(g_e, textvariable=self.v_embed_host)
        self.ent_embed_host.grid(row=2, column=1, sticky="ew", **pad)

        ttk.Label(g_e, text="Ngưỡng ngữ nghĩa:").grid(row=2, column=2, sticky="e", **pad)
        ttk.Spinbox(g_e, textvariable=self.v_sem_thr, from_=0.5, to=1.0, increment=0.01,
                    width=8).grid(row=2, column=3, sticky="w", **pad)

        # ---- Tham số sinh ---------------------------------------------------
        g_g = ttk.LabelFrame(outer, text="Tham số sinh", padding=8)
        g_g.pack(fill="x", pady=(8, 0))
        for c in (1, 3, 5):
            g_g.columnconfigure(c, weight=1)

        ttk.Label(g_g, text="Số dòng cần sinh:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Spinbox(g_g, textvariable=self.v_target, from_=1, to=1_000_000, increment=100,
                    width=10).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(g_g, text="Batch:").grid(row=0, column=2, sticky="e", **pad)
        ttk.Spinbox(g_g, textvariable=self.v_batch, from_=1, to=200, width=8).grid(
            row=0, column=3, sticky="w", **pad)
        ttk.Label(g_g, text="Workers:").grid(row=0, column=4, sticky="e", **pad)
        ttk.Spinbox(g_g, textvariable=self.v_workers, from_=1, to=64, width=8).grid(
            row=0, column=5, sticky="w", **pad)

        ttk.Label(g_g, text="Nhiệt độ (0..2):").grid(row=1, column=0, sticky="w", **pad)
        ttk.Spinbox(g_g, textvariable=self.v_temp, from_=0.0, to=2.0, increment=0.1,
                    width=10).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(g_g, text="Max tokens:").grid(row=1, column=2, sticky="e", **pad)
        ttk.Spinbox(g_g, textvariable=self.v_max_tokens, from_=256, to=32768, increment=256,
                    width=8).grid(row=1, column=3, sticky="w", **pad)

        # ---- Nút điều khiển -------------------------------------------------
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(12, 4))
        self.btn_dry = ttk.Button(bar, text="Kiểm tra (dry-run)",
                                  command=lambda: self._start(dry_run=True))
        self.btn_dry.pack(side="left")
        self.btn_run = ttk.Button(bar, text="▶  Bắt đầu sinh", style="Accent.TButton",
                                  command=lambda: self._start(dry_run=False))
        self.btn_run.pack(side="left", padx=8)
        self.btn_stop = ttk.Button(bar, text="■  Dừng", style="Danger.TButton",
                                   command=self._stop, state="disabled")
        self.btn_stop.pack(side="left")
        ttk.Button(bar, text="Mở thư mục đầu ra",
                   command=self._open_output_dir).pack(side="right")

        # ---- Tiến trình + log ----------------------------------------------
        prog = ttk.Frame(outer)
        prog.pack(fill="x")
        self.progress = ttk.Progressbar(prog, mode="determinate", maximum=100,
                                        style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", side="left", expand=True)
        ttk.Label(prog, textvariable=self.v_status, width=42, anchor="w").pack(
            side="left", padx=(10, 0))

        logwrap = tk.Frame(outer, bg=_BORDER, bd=0)
        logwrap.pack(fill="both", expand=True, pady=(10, 0))
        self.log = ScrolledText(logwrap, height=14, wrap="word", state="disabled",
                                font=("Consolas", 10), relief="flat", bd=0,
                                bg="#0f172a", fg="#e2e8f0", insertbackground="#e2e8f0",
                                padx=10, pady=8)
        self.log.pack(fill="both", expand=True, padx=1, pady=1)

    # ------------------------------------------------------- event handlers
    def _apply_provider_state(self) -> None:
        """Bật/tắt ô + đổ gợi ý model theo provider (KHÔNG gọi mạng)."""
        kind = self.v_provider.get()
        is_ollama = kind == "ollama"
        self.ent_host.configure(state="normal" if is_ollama else "disabled")
        for w in (self.ent_base, self.ent_keyenv, self.ent_key):
            w.configure(state="disabled" if is_ollama else "normal")
        self.btn_refresh_models.configure(state="normal" if is_ollama else "disabled")

        d = _PROVIDER_DEFAULTS.get(kind, {})
        if d.get("api_key_env"):
            self.v_key_env.set(d["api_key_env"])
        if not is_ollama:
            # Provider API: gợi ý sẵn vài model (vẫn gõ tay được).
            self.cb_model.configure(values=_SUGGESTED_MODELS.get(kind, []))
            if not self.v_model.get().strip() and d.get("model"):
                self.v_model.set(d["model"])

    def _on_provider_change(self) -> None:
        self._apply_provider_state()
        if self.v_provider.get() == "ollama":
            self._refresh_ollama_models()  # tự nạp model đã cài trên máy

    def _refresh_ollama_models(self) -> None:
        """Nạp danh sách model Ollama trên máy ở luồng nền rồi đổ vào dropdown."""
        if self._worker and self._worker.is_alive():
            return
        host = self.v_host.get().strip() or "http://localhost:11434"
        self.v_status.set("Đang tải danh sách model Ollama…")

        def work():
            try:
                names = _list_ollama_models(host)
                self._queue.put(("models", names, None))
            except Exception as err:  # noqa: BLE001
                self._queue.put(("models", [], str(err)))

        threading.Thread(target=work, daemon=True).start()

    def _on_semantic_toggle(self) -> None:
        state = "normal" if self.v_semantic.get() else "disabled"
        self.cb_embed.configure(state="readonly" if self.v_semantic.get() else "disabled")
        for w in (self.ent_embed_model, self.ent_embed_host):
            w.configure(state=state)

    def _pick_domain(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn file domain YAML",
            filetypes=[("YAML", "*.yaml *.yml"), ("Tất cả", "*.*")],
            initialdir=self._dir_of(self.v_domain.get(), "domains"),
        )
        if path:
            self.v_domain.set(path)

    def _pick_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Chọn nơi lưu CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tất cả", "*.*")],
            initialdir=self._dir_of(self.v_out.get(), "output"),
            initialfile=os.path.basename(self.v_out.get() or "dataset.csv"),
        )
        if path:
            self.v_out.set(path)

    @staticmethod
    def _dir_of(path: str, fallback: str) -> str:
        d = os.path.dirname(os.path.abspath(path)) if path else ""
        return d if d and os.path.isdir(d) else (fallback if os.path.isdir(fallback) else ".")

    def _open_output_dir(self) -> None:
        out = self.v_out.get().strip()
        folder = os.path.dirname(os.path.abspath(out)) if out else os.getcwd()
        if not os.path.isdir(folder):
            messagebox.showinfo("Chưa có", f"Thư mục chưa tồn tại:\n{folder}")
            return
        try:
            os.startfile(folder)  # Windows
        except AttributeError:  # pragma: no cover - macOS/Linux
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])

    # ------------------------------------------------------------ run / stop
    def _start(self, *, dry_run: bool) -> None:
        if self._worker and self._worker.is_alive():
            return
        try:
            cfg = self._collect_config()
        except ValueError as err:
            messagebox.showerror("Cấu hình chưa hợp lệ", str(err))
            return

        domain_path = self.v_domain.get().strip()
        if not domain_path or not os.path.exists(domain_path):
            messagebox.showerror("Thiếu domain", "Hãy chọn một file domain YAML hợp lệ.")
            return

        self._clear_log()
        self._stop_event.clear()
        self._set_running(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(15)
        self.v_status.set("Đang kiểm tra cấu hình…")

        resume = self.v_resume.get()
        self._worker = threading.Thread(
            target=self._run_generation,
            args=(cfg, domain_path, dry_run, resume),
            daemon=True,
        )
        self._worker.start()

    def _stop(self) -> None:
        if self._worker and self._worker.is_alive():
            self._stop_event.set()
            self.v_status.set("Đang dừng… (chờ các luồng kết thúc)")
            self.btn_stop.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self.btn_run.configure(state="disabled" if running else "normal")
        self.btn_dry.configure(state="disabled" if running else "normal")
        self.btn_stop.configure(state="normal" if running else "disabled")
        self.cb_provider.configure(state="disabled" if running else "readonly")
        if running:
            self.btn_refresh_models.configure(state="disabled")
        else:
            self._apply_provider_state()  # khôi phục bật/tắt ô theo provider

    # ---------------------------------------------------------- build config
    def _collect_config(self) -> AppConfig:
        cfg = AppConfig.load(self._config_path)

        cfg.mode = self.v_mode.get().strip() or "api"
        if self.v_offline_model.get().strip():
            cfg.offline.model = self.v_offline_model.get().strip()

        cfg.provider.type = self.v_provider.get()
        cfg.provider.model = self.v_model.get().strip()
        if self.v_host.get().strip():
            cfg.provider.host = self.v_host.get().strip()
        cfg.provider.base_url = self.v_base_url.get().strip() or None
        if self.v_key_env.get().strip():
            cfg.provider.api_key_env = self.v_key_env.get().strip()

        cfg.embedding.type = self.v_embed_type.get()
        cfg.embedding.model = self.v_embed_model.get().strip()
        if self.v_embed_host.get().strip():
            cfg.embedding.host = self.v_embed_host.get().strip()

        cfg.quality.semantic_enabled = self.v_semantic.get()
        cfg.quality.semantic_threshold = self._as_float(self.v_sem_thr, "Ngưỡng ngữ nghĩa")
        cfg.quality.fuzzy_threshold = self._as_float(self.v_fuzzy_thr, "Ngưỡng mờ")

        cfg.generation.target_rows = self._as_int(self.v_target, "Số dòng cần sinh", lo=1)
        cfg.generation.batch_size = self._as_int(self.v_batch, "Batch", lo=1)
        cfg.generation.workers = self._as_int(self.v_workers, "Workers", lo=1)
        cfg.generation.temperature = self._as_float(self.v_temp, "Nhiệt độ")
        cfg.generation.max_tokens = self._as_int(self.v_max_tokens, "Max tokens", lo=1)

        cfg.output.path = self.v_out.get().strip() or "output/dataset.csv"
        cfg.output.write_rejects = self.v_rejects.get()

        return cfg

    @staticmethod
    def _as_int(var: tk.StringVar, label: str, *, lo: Optional[int] = None) -> int:
        try:
            val = int(float(var.get()))
        except (TypeError, ValueError):
            raise ValueError(f"'{label}' phải là số nguyên.")
        if lo is not None and val < lo:
            raise ValueError(f"'{label}' phải ≥ {lo}.")
        return val

    @staticmethod
    def _as_float(var: tk.StringVar, label: str) -> float:
        try:
            return float(var.get())
        except (TypeError, ValueError):
            raise ValueError(f"'{label}' phải là số.")

    # ----------------------------------------------------- worker (nền)
    def _run_generation(self, cfg: AppConfig, domain_path: str,
                        dry_run: bool, resume: bool) -> None:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = _QueueWriter(self._queue)
        sys.stderr = _QueueWriter(self._queue)
        try:
            # Đặt API key vào môi trường nếu người dùng nhập tay.
            key = self.v_api_key.get().strip()
            if key:
                os.environ[cfg.provider.api_key_env] = key

            domain = Domain.load(domain_path)

            sem = "bật" if cfg.quality.semantic_enabled else "tắt"
            print("=" * 60)
            print(f"  Domain    : {domain.name}  ({len(domain.columns)} cột, "
                  f"{len(domain.facets)} facet)")
            print(f"  Chế độ    : {cfg.mode}"
                  + (f" (offline: {cfg.offline.model})" if cfg.mode != "api" else ""))
            print(f"  Embedding : {cfg.embedding.type} / {cfg.embedding.model} "
                  f"(chống trùng ngữ nghĩa: {sem})")
            print(f"  Mục tiêu  : {cfg.generation.target_rows} dòng, "
                  f"batch={cfg.generation.batch_size}, workers={cfg.generation.workers}")
            print(f"  Đầu ra    : {cfg.output.path}")
            print("=" * 60)

            provider = build_generation_provider(cfg)
            provider.health_check()
            print(f"[ok] Provider sẵn sàng: {provider.name}")
            phase2 = build_phase2_provider(cfg)
            if phase2 is not None:
                phase2.health_check()
                print(f"[ok] Provider nhân bản (pha 2): {phase2.name}")

            embedder = self._setup_embedder(cfg)

            if dry_run:
                print("[dry-run] Cấu hình hợp lệ. Provider + embedder sẵn sàng.")
                self._queue.put(("done", "Kiểm tra xong — cấu hình hợp lệ."))
                return

            self._queue.put(("phase", "running", cfg.generation.target_rows))

            writer = CsvWriter(domain, cfg.output.path, encoding=cfg.output.encoding,
                               write_rejects=cfg.output.write_rejects)
            gen = DataGenerator(provider, domain, cfg.generation, writer,
                                embedder=embedder, quality_cfg=cfg.quality,
                                on_progress=self._on_progress,
                                stop_event=self._stop_event, show_bar=False,
                                phase2_provider=phase2,
                                seed_rows=cfg.generation.seed_rows)
            with writer:
                writer.open(append=cfg.output.checkpoint and resume)
                outcome = gen.run()

            print("\n" + "=" * 60)
            print("  KẾT QUẢ")
            print("=" * 60)
            for line in outcome.report.summary_lines():
                print(line)
            rate = (outcome.accepted_this_run / outcome.elapsed_sec
                    if outcome.elapsed_sec else 0)
            print(f"  Tổng dòng trong file: {outcome.total_rows}")
            print(f"  Số lần gọi model    : {outcome.calls}")
            print(f"  Thời gian           : {outcome.elapsed_sec:.1f}s "
                  f"({rate:.1f} dòng/giây)")
            print(f"  File CSV            : {cfg.output.path}")
            print("=" * 60)

            if self._stop_event.is_set():
                msg = f"Đã dừng. {outcome.total_rows} dòng đã lưu vào file."
            elif outcome.stalled and outcome.total_rows < cfg.generation.target_rows:
                msg = (f"Dừng sớm: chủ đề có thể đã 'cạn'. {outcome.total_rows} dòng. "
                       "Thử tăng nhiệt độ / đổi model / thêm facet.")
            else:
                msg = f"Hoàn tất! {outcome.total_rows} dòng trong {cfg.output.path}"
            self._queue.put(("done", msg))

        except (ProviderError, ValueError, OSError) as err:
            print(f"\n[lỗi] {err}")
            self._queue.put(("error", str(err)))
        except Exception as err:  # noqa: BLE001
            print("\n[lỗi không mong đợi]\n" + traceback.format_exc())
            self._queue.put(("error", str(err)))
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def _setup_embedder(self, cfg: AppConfig):
        """Bản sao gọn của cli._setup_embedder: lùi về hashing nếu embedder hỏng."""
        if not cfg.quality.semantic_enabled:
            return None
        try:
            embedder = build_embedder(cfg.embedding)
        except ValueError as err:
            print(f"[cảnh báo] Embedding lỗi cấu hình: {err}")
            embedder = None
        if embedder is None:
            cfg.quality.semantic_enabled = False
            return None
        try:
            embedder.health_check()
            print(f"[ok] Embedder sẵn sàng: {embedder.name}")
            return embedder
        except Exception as err:  # noqa: BLE001
            print(f"[cảnh báo] Embedder '{embedder.name}' không sẵn sàng: {err}")
            if cfg.embedding.fallback_to_hashing and cfg.embedding.type != "hashing":
                print("           -> Lùi về embedder 'hashing' (lexical).")
                return HashingEmbedder(cfg.embedding)
            cfg.quality.semantic_enabled = False
            print("           -> Tắt chống trùng ngữ nghĩa (vẫn giữ tuyệt đối + mờ).")
            return None

    def _on_progress(self, total: int, target: int, rejected: int, temp: float) -> None:
        # Gọi từ luồng nền -> chỉ đẩy vào queue, GUI tự cập nhật.
        self._queue.put(("progress", total, target, rejected, temp))

    # --------------------------------------------------- pump queue -> GUI
    def _drain_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self._append_log(msg[1])
                elif kind == "phase" and msg[1] == "running":
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=max(1, msg[2]))
                    self.progress["value"] = 0
                    self.v_status.set(f"Đang sinh… 0 / {msg[2]}")
                elif kind == "progress":
                    _, total, target, rejected, temp = msg
                    self.progress.configure(maximum=max(1, target))
                    self.progress["value"] = total
                    self.v_status.set(
                        f"{total} / {target} dòng | loại {rejected} | nhiệt {temp:.2f}")
                elif kind == "models":
                    self._update_model_list(msg[1], msg[2])
                elif kind == "done":
                    self._finish(msg[1], ok=True)
                elif kind == "error":
                    self._finish("Lỗi: " + msg[1], ok=False)
        except queue.Empty:
            pass
        self.root.after(80, self._drain_queue)

    def _update_model_list(self, names: list, err: Optional[str]) -> None:
        """Đổ danh sách model Ollama vào dropdown (gọi trên luồng GUI)."""
        running = bool(self._worker and self._worker.is_alive())
        if err is not None:
            if not running:
                self.v_status.set("Không tải được model Ollama — Ollama đã chạy chưa?")
            return
        self.cb_model.configure(values=names)
        # Đổ MỌI model đã cài vào dropdown "Model Ollama offline" (mode offline/hybrid/augment).
        self.cb_offline_model.configure(values=names)
        if names and self.v_offline_model.get().strip() not in names:
            self.v_offline_model.set(names[0])
        if names:
            if self.v_model.get().strip() not in names:
                self.v_model.set(names[0])
            if not running:
                self.v_status.set(f"Đã tìm thấy {len(names)} model Ollama.")
        elif not running:
            self.v_status.set("Chưa có model Ollama nào. Hãy:  ollama pull llama3.1")

    def _finish(self, status: str, *, ok: bool) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        if ok and self.progress["maximum"]:
            self.progress["value"] = self.progress["maximum"]
        else:
            self.progress["value"] = 0
        self.v_status.set(status)
        self._set_running(False)
        if not ok:
            messagebox.showerror("Có lỗi", status)

    # ----------------------------------------------------------- log helpers
    def _append_log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _on_close(self) -> None:
        if self._worker and self._worker.is_alive():
            if not messagebox.askokcancel(
                    "Đang chạy", "Đang sinh dữ liệu. Dừng và thoát?"):
                return
            self._stop_event.set()
        self.root.destroy()


def main() -> int:
    _enable_hidpi()              # phải gọi TRƯỚC khi tạo Tk() để chữ sắc nét
    root = tk.Tk()
    _apply_style(root)
    SynthaDataGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
