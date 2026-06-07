# SynthaData

Phần mềm **sinh dữ liệu tổng hợp** (synthetic data) chất lượng cao, xuất ra
bảng **CSV** để huấn luyện các model AI khác. Kiến trúc nhiều lớp, hỗ trợ **2
trường hợp**:

1. **Gọi API ngoài** — OpenAI (và mọi endpoint tương thích OpenAI: OpenRouter,
   Together, vLLM, LM Studio…) hoặc **Anthropic (Claude)**.
2. **Chạy offline** bằng **Ollama** ngay trên máy (không cần mạng, không tốn phí).

Có lớp **kiểm tra chất lượng (QA) chạy liên tục**: chống trùng lặp **3 tầng**
(tuyệt đối + mờ + **NGỮ NGHĨA bằng vector**), làm sạch, validate schema, loại
placeholder, **giám sát thời gian thực** (tỉ lệ chấp nhận, phát hiện "mode
collapse") và **sinh thích ứng** (tự tăng nhiệt khi trùng nhiều) — sinh được
khối lượng lớn (mặc định **≥ 1000 dòng**) bằng nhiều luồng song song.

> ⚠️ **Lưu ý y khoa:** domain mẫu "các bệnh trên thế giới" chỉ phục vụ **huấn
> luyện/giáo dục**. Dữ liệu do model sinh ra **có thể sai** — hãy kiểm chứng
> bằng nguồn chuyên môn trước khi dùng cho mục đích thực tế. Không dùng thay
> thế tư vấn y tế.

---

## Kiến trúc các lớp

```
synthadata/
├── config.py        Lớp cấu hình (provider + embedding + quality + generation + output)
├── schema.py        Lớp định nghĩa domain / cột dữ liệu (nạp từ YAML)
├── prompts.py       Lớp dựng prompt cho model
├── providers/       Lớp nguồn LLM sinh văn bản (trừu tượng hoá)
│   ├── base.py          interface chung + retry/backoff
│   ├── openai_api.py    API ngoài tương thích OpenAI
│   ├── anthropic_api.py API ngoài Anthropic (Claude)
│   └── ollama.py        Ollama offline
├── embeddings/      Lớp vector hoá văn bản (cho chống trùng NGỮ NGHĨA)
│   ├── base.py          interface chung + retry
│   ├── ollama_embed.py  embedding offline (nomic-embed-text…)
│   ├── openai_embed.py  embedding qua API (text-embedding-3-small)
│   └── hashing.py       fallback lexical (không cần model)
├── quality/         Lớp QA dạng dây chuyền chạy LIÊN TỤC
│   ├── checks.py        các "check" cắm-rút: Structure, Schema, Consistency…
│   ├── dedup.py         chống trùng 3 tầng: tuyệt đối + mờ + NGỮ NGHĨA
│   ├── monitor.py       giám sát: tỉ lệ chấp nhận, phân bố, mode-collapse
│   └── pipeline.py      ráp checks + embedder + dedup + monitor
├── validation.py    Làm sạch + validate schema 1 bản ghi (RecordValidator)
├── writer.py        Lớp ghi CSV (checkpoint + file rejects)
├── generator.py     Lớp điều phối sinh song song + sinh thích ứng
├── cli.py           Giao diện dòng lệnh
└── gui.py           Giao diện đồ hoạ (Tkinter) — bọc lại toàn bộ dây chuyền
```

Dây chuyền mỗi LÔ bản ghi:

```
gọi model → trích JSON → [StructureCheck → SchemaCheck (làm sạch) → ConsistencyCheck]
          → nhúng embedding theo lô → chống trùng 3 tầng (exact → fuzzy → semantic)
          → ghi CSV  + cập nhật giám sát
```

Sai ở bước nào thì bị loại và ghi lý do vào file `*_rejects.csv`. Muốn thêm luật
kiểm tra mới chỉ cần viết một lớp `Check` rồi đăng ký vào pipeline — không đụng
phần lõi.

---

## Cài đặt

Yêu cầu Python 3.9+ (đã kiểm thử trên 3.13). Dùng bản Python **có `pip`**
(ví dụ Anaconda); một số bản Python tối giản trên máy không kèm pip.

```powershell
pip install -r requirements.txt
```

Các gói `rapidfuzz`, `tqdm`, `python-dotenv` là tuỳ chọn — thiếu vẫn chạy được
(tự fallback), nhưng nên cài để có chống-trùng-mờ nhanh + thanh tiến trình.

---

## Cách dùng

### Chế độ chạy (`--mode`) — chọn cách phối hợp API ↔ Ollama

Đặt trong `config.yaml` (`mode: ...`), hoặc thêm cờ `--mode` khi chạy, hoặc chọn ở
dropdown **Chế độ** trong GUI.

| Mode | Sinh bằng | Hợp khi | Lệnh |
|---|---|---|---|
| `api` | API online (xoay vòng key/dịch vụ) | Có quota, cần nhanh | `--mode api` |
| `offline` | **Ollama cục bộ** | Không mạng / hết quota / chạy thoải mái | `--mode offline` |
| `hybrid` ⭐ | API; **hết quota tất cả → tự chuyển Ollama** | Vừa nhanh vừa không bao giờ đứng | `--mode hybrid` |
| `augment` | API sinh "hạt giống" → **Ollama nhân bản thêm** | Tạo nhiều dữ liệu rẻ, vẫn đúng | `--mode augment --seed-rows 200` |

```powershell
# 1) Full offline (không cần key, không quota) — dùng model Ollama có sẵn
python -m synthadata --domain domains/diseases.yaml --mode offline --offline-model qwen2.5-coder:7b

# 2) Hybrid (mặc định): API chạy chính, hết quota tự rớt về Ollama
python -m synthadata --domain domains/diseases.yaml --mode hybrid

# 3) Augment: 200 dòng hạt giống bằng API, phần còn lại Ollama nhân bản
python -m synthadata --domain domains/diseases.yaml --mode augment --seed-rows 200 --target 1000
```

- **Model Ollama offline** lấy từ `offline.model` trong `config.yaml` (hoặc `--offline-model`).
  Xem model đã cài bằng `ollama list`.
- **Chống trùng ngữ nghĩa** vẫn chạy bằng Ollama cục bộ ở mọi mode (không tốn quota).
  Muốn *xịn hơn* cho tiếng Việt: `ollama pull bge-m3` rồi đặt `embedding.model: bge-m3`.
- Mọi mode đều **checkpoint/resume**: chạy lại cùng lệnh sẽ sinh tiếp, tích luỹ tới đủ `--target`.

### Giao diện đồ hoạ (GUI) — dễ nhất

Không cần nhớ tham số dòng lệnh. GUI dùng **Tkinter** có sẵn trong Python (không
phải cài thêm gì).

```powershell
python -m synthadata --gui        # hoặc:  python -m synthadata.gui
```

**Trên Windows — double-click để mở (không cần dòng lệnh):**

- `SynthaData-GUI.bat` — mở GUI ngay. Launcher **tự dò Python có đủ thư viện**
  (ưu tiên Anaconda, bỏ qua Python thiếu lib như msys2) nên **pull về máy khác vẫn chạy**.
- **Tạo icon ngoài Desktop:** chạy `Tao-Shortcut-Desktop.bat` **một lần** → xuất hiện
  shortcut **“SynthaData GUI”** (icon lưới xanh–tím) trên màn hình, mở app không hiện
  cửa sổ console.

> 🖥️ **Dùng trên máy khác:** `git clone`/`git pull` repo về, cài thư viện
> (`pip install -r requirements.txt`), rồi chạy `Tao-Shortcut-Desktop.bat`. Shortcut
> tạo ra **trỏ đúng đường dẫn của máy đó** (file `.lnk` không commit lên git vì gắn
> đường dẫn tuyệt đối — chỉ commit launcher `.bat`/`.vbs` + `synthadata.ico` để tái tạo).

Cửa sổ cho phép chọn file domain, đổi provider/model, đặt số dòng cần sinh, bật/tắt
chống trùng ngữ nghĩa… rồi bấm **Bắt đầu sinh**. Có **thanh tiến trình**, **log thời
gian thực**, nút **Kiểm tra (dry-run)** để thử cấu hình, và nút **Dừng** an toàn giữa
chừng. Form được nạp sẵn giá trị mặc định từ `config.yaml`.

- **Chọn model Ollama có sẵn:** khi provider là `ollama`, ô *Model* là một dropdown
  tự **liệt kê các model đã cài trên máy** (gọi `GET /api/tags`). Bấm nút **⟳** để
  nạp lại sau khi `ollama pull` thêm model. Với `openai`/`anthropic`, dropdown gợi ý
  sẵn vài model thông dụng (vẫn gõ tay được).
- **Giao diện sắc nét:** bật DPI-aware trên Windows (hết mờ trên màn hình tỉ lệ
  125%/150%) + theme phẳng, font Segoe UI.

### Trường hợp 2 — Ollama offline (mặc định, không cần key)

```powershell
# 1. Cài Ollama: https://ollama.com  rồi kéo 1 model
ollama pull qwen2.5            # hoặc llama3.1 / mistral / gemma2 ...

# 2. Sinh 1000 dòng bệnh
python -m synthadata --domain domains/diseases.yaml `
    --provider ollama --model qwen2.5 --target 1000
```

### Trường hợp 1 — API ngoài

```powershell
# OpenAI (hoặc endpoint tương thích)
$env:OPENAI_API_KEY = "sk-..."
python -m synthadata --domain domains/diseases.yaml `
    --provider openai --model gpt-4o-mini --target 1000

# Anthropic (Claude)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python -m synthadata --domain domains/diseases.yaml `
    --provider anthropic --model claude-sonnet-4-6 --target 1000
```

> Mẹo: tạo file `.env` (copy từ `.env.example`) để khỏi gõ key mỗi lần.

### Xoay vòng API (né rate-limit của bản free)

Gom **nhiều key** hoặc **nhiều dịch vụ** rồi luân phiên: mỗi key chỉ gánh ~1/N
lưu lượng (ít chạm giới hạn), và khi một backend lỗi/`429` thì **tự nhảy ngay**
sang cái khác. Tự bật khi có ≥2 backend — không cần cờ gì thêm.

- **Nhiều key cùng dịch vụ** — chỉ cần nhét vào 1 biến trong `.env`, ngăn bởi dấu phẩy:

  ```bash
  GROQ_API_KEY=gsk_key1,gsk_key2,gsk_key3
  ```

- **Nhiều dịch vụ chatbot khác nhau** — khai báo `rotation` trong `config.yaml`,
  gọi mỗi dịch vụ theo **tên `preset`** (khỏi nhớ URL), chỉ cần đặt key vào `.env`:

  ```yaml
  provider:
    preset: groq               # = type/base_url/api_key_env/model của Groq
    rotation:
      - { preset: gemini }                       # Google Gemini
      - { preset: openrouter }                   # OpenRouter (nhiều model :free)
      - { preset: cerebras }                     # Cerebras
      - { preset: deepseek, model: deepseek-chat }   # đổi model tuỳ ý
      - { api_key_env: GROQ_API_KEY_2 }          # hoặc chỉ thêm 1 key Groq nữa
  ```

  **Preset có sẵn:** `groq`, `gemini`, `openrouter`, `cerebras`, `together`,
  `deepseek`, `mistral`, `xai` (Grok), `fireworks`, `perplexity`, `openai`,
  `anthropic` (Claude), `ollama`. Trộn lẫn thoải mái — kể cả Claude (giao thức
  riêng) chung một vòng với các API tương thích OpenAI. Khai báo tường minh
  (`model`, `api_key_env`…) luôn **đè lên** giá trị của preset; dịch vụ nào không
  nhận JSON-mode thì đặt `json_mode: false`.

Lúc khởi động, các key/endpoint hỏng (sai key…) bị **loại khỏi vòng**, chỉ giữ cái
sống. Embedding vẫn chạy riêng (nên để local Ollama `nomic-embed-text` cho free).

### Các tham số CLI hữu ích

| Tham số | Ý nghĩa |
|---|---|
| `--target N` | số dòng cần sinh (mặc định 1000) |
| `--batch-size N` | số bản ghi xin model mỗi lần gọi |
| `--workers N` | số luồng gọi song song (giảm nếu máy yếu) |
| `--temperature T` | cao → đa dạng hơn, ít trùng hơn |
| `--out PATH` | đường dẫn CSV đầu ra |
| `--embed-provider` | nguồn embedding: `ollama`/`openai`/`hashing`/`none` |
| `--embed-model` | model embedding (vd `nomic-embed-text`) |
| `--no-semantic` | tắt chống trùng ngữ nghĩa |
| `--no-resume` | ghi đè file cũ thay vì chạy tiếp |
| `--dry-run` | chỉ kiểm tra cấu hình + provider + embedder rồi thoát |

Mọi tham số cũng đặt được trong `config.yaml`. CLI ưu tiên hơn config.

---

## Kiểm tra (smoke test)

Chạy thử toàn bộ dây chuyền **không cần mạng** (dùng provider giả lập):

```powershell
python -m tests.test_pipeline
```

Test xác minh: CSV đủ dòng, **không trùng**, không placeholder, và QA loại đúng
các bản ghi lỗi đã cài sẵn.

---

## Tự tạo domain mới

Chỉ cần viết 1 file YAML (xem `domains/diseases.yaml` làm mẫu). Ví dụ sinh dữ
liệu "sản phẩm thương mại điện tử", "câu hỏi–đáp", "giao dịch ngân hàng"…:

```yaml
name: products
topic: Real-world consumer electronics products with realistic specs.
language: Vietnamese          # ngôn ngữ cho các trường text
dedup_key: product_name       # cột chống trùng
facets:                       # các lát cắt để bao phủ rộng, ít trùng
  - Điện thoại thông minh
  - Laptop
  - Tai nghe
columns:
  - name: product_name
    description: Tên sản phẩm.
    required: true
    max_len: 120
  - name: price_usd
    type: number
    description: Giá tham khảo theo USD.
  - name: category
    type: enum
    enum: ["phone", "laptop", "audio"]
```

Các kiểu cột: `text`, `number`, `enum` (kèm `enum: [...]`), `bool`. Mỗi cột có
`required`, `min_len`, `max_len`.

---

## Lớp kiểm tra chất lượng (QA) — chạy liên tục

Mọi check chạy trong lúc sinh (an toàn đa luồng), loại ngay bản ghi xấu:

- **Làm sạch:** chuẩn hoá Unicode (NFC), gộp khoảng trắng, bỏ ký tự điều khiển,
  bỏ ngoặc kép dư.
- **Validate schema:** đủ trường bắt buộc, đúng kiểu (số/enum), trong giới hạn
  độ dài (tự cắt nếu quá dài).
- **Loại placeholder:** bắt giá trị rác `N/A`, `unknown`, `...`, `lorem ipsum`…
- **Chống trùng 3 tầng:**
  1. *Tuyệt đối* — so khoá đã chuẩn hoá (bỏ dấu, hạ chữ).
  2. *Mờ (lexical)* — độ tương đồng chuỗi (rapidfuzz/difflib), ngưỡng
     `quality.fuzzy_threshold` (0.92).
  3. **Ngữ nghĩa (vector)** — nhúng "chữ ký" của bản ghi thành vector rồi so
     **cosine**; ngưỡng `quality.semantic_threshold` (0.90). Đây là tầng bắt
     được "Leprosy" vs "Hansen's Disease", "Kala-Azar" vs "Leishmaniasis"… —
     thứ mà so chuỗi bỏ sót. (Thực nghiệm: bắt `Kala-Azar (Leishmaniasis)` ≈
     `leishmaniasis kala azar` ở cos=0.958.)
- **Giám sát liên tục (`QualityMonitor`):** in snapshot mỗi `monitor_every`
  dòng — tỉ lệ chấp nhận gần đây + cảnh báo **mode-collapse** (một giá trị enum
  chiếm ưu thế bất thường ⇒ model đang lặp).
- **Sinh thích ứng:** khi tỉ lệ chấp nhận tụt dưới `min_rolling_accept`, tự
  **tăng nhiệt độ** (tới `temp_max`) để đẩy đa dạng, chống "cạn" chủ đề.
- **Báo cáo:** cuối phiên in số dòng nhận/loại theo từng lý do + cảnh báo lệch.

### Cấu hình embedding (cho tầng ngữ nghĩa)

```yaml
embedding:
  type: ollama                 # ollama | openai | hashing (lexical) | none
  model: nomic-embed-text      # ollama pull nomic-embed-text
  fallback_to_hashing: true    # embedder thật hỏng -> tự lùi về lexical
```

- **Offline:** `ollama pull nomic-embed-text` (khuyến nghị, miễn phí).
- **API:** `type: openai`, `model: text-embedding-3-small`.
- **Không có model:** để `type: hashing` (lexical, chạy ngay) hoặc `none` (tắt).
- Nếu embedder thật không sẵn sàng, hệ thống **tự lùi về `hashing`** rồi vẫn
  chạy tiếp (không làm hỏng phiên sinh).

> Chỉnh `semantic_threshold` cao hơn (vd 0.94) nếu muốn GIỮ các phân nhóm gần
> nhau (vd ung thư phổi tế bào nhỏ vs không tế bào nhỏ); thấp hơn nếu muốn gộp
> mạnh tay hơn.

---

## Đầu ra

- `output/<tên>.csv` — dữ liệu sạch (UTF-8 BOM, mở đúng trong Excel).
- `output/<tên>_rejects.csv` — các bản ghi bị loại kèm **lý do** (để soi chất
  lượng / chỉnh prompt).
- **Checkpoint:** ghi tăng dần. Chạy lại cùng lệnh sẽ **đọc file cũ và sinh
  tiếp** mà không trùng (trừ khi dùng `--no-resume`).

---

## Mẹo trên Windows

Nếu console hiện chữ lỗi font, đặt UTF-8 trước khi chạy:

```powershell
$env:PYTHONUTF8 = "1"
```

(CLI đã tự ép stdout sang UTF-8 nên thường không cần, nhưng đặt thêm cho chắc.)
