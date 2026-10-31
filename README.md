# SynthaData

<p align="center">
  <img src="synthadata.ico" alt="SynthaData Logo" width="96" height="96">
</p>

<p align="center">
  <strong>Hệ thống sinh dữ liệu tổng hợp (Synthetic Data) chất lượng cao chuẩn công nghiệp</strong><br>
  Kiểm tra chất lượng (QA) liên tục • Chống trùng lặp ngữ nghĩa (Semantic Vector) • Xoay vòng & Fallback API ↔ Ollama
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/UI-Tkinter%20GUI%20%2B%20CLI-blueviolet?style=flat-square" alt="Interface">
  <img src="https://img.shields.io/badge/Deduplication-3--Tier%20Semantic-orange?style=flat-square" alt="Deduplication">
</p>

---

## 📖 Mục lục

- [Tổng quan](#-tổng-quan)
- [Tính năng nổi bật](#-tính-năng-nổi-bật)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Cài đặt](#-cài-đặt)
- [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
  - [Giao diện đồ họa (GUI)](#giao-diện-đồ-họa-gui)
  - [Các chế độ hoạt động (CLI Modes)](#các-chế-độ-hoạt-động-cli-modes)
  - [Xoay vòng API & Phục hồi lỗi (Rotation & Fallback)](#xoay-vòng-api--phục-hồi-lỗi-rotation--fallback)
- [Dây chuyền kiểm tra chất lượng (QA Pipeline)](#-dây-chuyền-kiểm-tra-chất-lượng-qa-pipeline)
- [Cấu hình Domain dữ liệu mới](#-cấu-hình-domain-dữ-liệu-mới)
- [Đầu ra dữ liệu & Checkpoint](#-đầu-ra-dữ-liệu--checkpoint)
- [Kiểm thử (Testing)](#-kiểm-thử-testing)
- [Bảo mật & Quản lý API Key](#-bảo-mật--quản-lý-api-key)
- [Tuyên bố miễn trừ trách nhiệm (Disclaimer)](#-tuyên-bố-miễn-trừ-trách-nhiệm-disclaimer)
- [Giấy phép (License)](#-giấy-phép-license)

---

## 🌟 Tổng quan

**SynthaData** là công cụ mã nguồn mở chuyên dụng cho việc **sinh dữ liệu tổng hợp (synthetic data)** có độ phong phú cao, phục vụ tiền xử lý và huấn luyện các mô hình Machine Learning / LLM. Dữ liệu được xuất ra định dạng **CSV** tiêu chuẩn (tương thích hoàn hảo với Excel và các thư viện phân tích dữ liệu như Pandas).

Hệ thống hỗ trợ linh hoạt 2 môi trường:
1. **API đám mây:** Hỗ trợ OpenAI, Anthropic (Claude), Google Gemini, Groq, OpenRouter, Cerebras, Together, DeepSeek, Mistral, xAI...
2. **Offline cục bộ:** Sử dụng **Ollama** trực tiếp trên phần cứng máy tính (hoạt động 100% không cần kết nối mạng, chi phí 0đ, bảo mật tuyệt đối dữ liệu nội bộ).

---

## ✨ Tính năng nổi bật

- **Chống trùng lặp 3 tầng (3-Tier Deduplication):**
  - *Tầng 1 (Exact):* So sánh khóa chuẩn hóa nhanh bằng băm.
  - *Tầng 2 (Fuzzy Lexical):* So khớp mờ khoảng cách chuỗi (sử dụng RapidFuzz hoặc difflib).
  - *Tầng 3 (Semantic Vector Cosine):* Vector hóa chữ ký bản ghi bằng mô hình embedding (như `bge-m3` hoặc `nomic-embed-text`) và so sánh khoảng cách Cosine, phát hiện các bản ghi trùng lặp về mặt ngữ nghĩa mà so khớp chuỗi bỏ sót (ví dụ: *"Leprosy"* vs *"Hansen's Disease"*).
- **Điều phối sinh thích ứng (Adaptive Generation):**
  - Tự động giám sát tỷ lệ chấp nhận theo cửa sổ trượt (*rolling window*).
  - Tự động phát hiện hiện tượng sụp đổ phân bố (*mode collapse*).
  - Tự động tăng nhiệt độ (*temperature boost*) khi tỷ lệ trùng lặp tăng cao để mở rộng không gian tìm kiếm.
- **Xoay vòng API & Chống Rate-limit thông minh:**
  - Tự động phân bổ lưu lượng trên nhiều API key hoặc nhiều nhà cung cấp khác nhau.
  - Tự động loại bỏ key lỗi khi khởi động và chuyển đổi tức thì sang backend khác khi gặp lỗi `429` (Too Many Requests).
- **Cơ chế Hybrid & Tự phục hồi:**
  - Khi toàn bộ quota API trực tuyến bị cạn kiệt, hệ thống tự động fallback về mô hình Ollama offline mà không làm gián đoạn phiên làm việc.
- **Giao diện thân thiện & Đa nền tảng:**
  - Hỗ trợ cả **GUI Tkinter** (hỗ trợ hiển thị sắc nét DPI-aware trên Windows) lẫn **CLI** mạnh mẽ cho tự động hóa.
  - Cơ chế **Checkpoint & Auto-resume**: Chạy lại cùng tham số sẽ tự động đọc dữ liệu cũ và sinh tiếp cho đến khi đủ số lượng.
  - Tách riêng dữ liệu đạt chuẩn và dữ liệu bị loại (kèm chi tiết lý do từ chối vào file `*_rejects.csv`).

---

## 🏗 Kiến trúc hệ thống

```
synthadata/
├── config.py             # Lớp cấu hình (provider, embedding, quality, generation...)
├── schema.py             # Phân tích cú pháp schema & định nghĩa domain từ YAML
├── prompts.py            # Dựng prompt ngữ cảnh và định dạng cho model
├── providers/            # Trừu tượng hóa nhà cung cấp LLM
│   ├── base.py           # Interface chung + cơ chế retry / backoff
│   ├── openai_api.py     # Endpoint chuẩn tương thích OpenAI (Groq, Together, DeepSeek...)
│   ├── anthropic_api.py  # Endpoint Anthropic Claude
│   ├── ollama.py         # Endpoint Ollama offline cục bộ
│   └── rotating.py       # Bộ điều phối xoay vòng API và failover
├── embeddings/           # Trừu tượng hóa module Vector Embeddings
│   ├── base.py           # Interface embedder chung
│   ├── ollama_embed.py   # Embedding offline (bge-m3, nomic-embed-text...)
│   ├── openai_embed.py   # Embedding qua API (text-embedding-3-small)
│   └── hashing.py        # Fallback lexical thuần (không cần model ngoài)
├── quality/              # Dây chuyền kiểm tra chất lượng (QA Pipeline)
│   ├── checks.py         # Bộ quy tắc kiểm tra (Structure, Schema, Consistency...)
│   ├── dedup.py          # Bộ lọc chống trùng lặp 3 tầng (Exact, Fuzzy, Semantic)
│   ├── monitor.py        # Giám sát thời gian thực & phát hiện mode-collapse
│   └── pipeline.py       # Tích hợp toàn diện các thành phần kiểm tra
├── validation.py         # Làm sạch dữ liệu, chuẩn hóa Unicode và validate bản ghi
├── writer.py             # Quản lý ghi file CSV, checkpoint và ghi log rejects
├── generator.py          # Bộ điều phối sinh dữ liệu song song & thích ứng
├── cli.py                # Giao diện dòng lệnh (CLI)
└── gui.py                # Giao diện đồ họa (Tkinter GUI)
```

### Luồng xử lý một lô bản ghi:

```
[Gọi Model LLM] ──> [Trích xuất JSON] ──> [StructureCheck]
                                              │
                                              ▼
[Chống trùng 3 tầng] <── [Nhúng Embedding] <── [Schema & Consistency Check]
        │
        ├──> (Hợp lệ) ──> [Ghi CSV chính] ──> [Cập nhật giám sát chất lượng]
        │
        └──> (Lỗi/Trùng) ──> [Ghi vào CSV Rejects kèm mã lý do]
```

---

## 💻 Cài đặt

### Yêu cầu tiên quyết:
- **Python:** Phiên bản 3.9 trở lên (đã kiểm thử thành công trên Python 3.10 - 3.13).
- Khuyến nghị sử dụng môi trường Python tiêu chuẩn hoặc Anaconda / Miniconda.

### Cài đặt thư viện:

```bash
git clone https://github.com/your-username/SynthaData.git
cd SynthaData
pip install -r requirements.txt
```

> **Lưu ý:** Các thư viện `rapidfuzz`, `tqdm`, `python-dotenv` được thiết kế linh hoạt — nếu thiếu, hệ thống sẽ tự động fallback về thư viện chuẩn trong Python, nhưng cài đặt đầy đủ theo `requirements.txt` sẽ mang lại hiệu năng cao nhất.

---

## 🚀 Hướng dẫn sử dụng

### Giao diện đồ họa (GUI)

Khởi động giao diện GUI trực tiếp qua dòng lệnh:

```bash
python -m synthadata --gui
```

#### Tiện ích khởi chạy nhanh trên Windows:
- **`SynthaData-GUI.bat`**: Nhấp đúp để mở ứng dụng ngay lập tức. Bộ launcher thông minh sẽ tự dò tìm môi trường Python phù hợp trên máy.
- **`Tao-Shortcut-Desktop.bat`**: Nhấp đúp chạy **1 lần** để tự động tạo lối tắt (shortcut) **"SynthaData GUI"** ngay trên màn hình Desktop của máy bạn, tích hợp sẵn icon và mở ẩn không hiện cửa sổ console màu đen.

---

### Các chế độ hoạt động (CLI Modes)

Bạn có thể thiết lập chế độ qua thuộc tính `mode` trong `config.yaml` hoặc truyền cờ `--mode` trên CLI:

| Chế độ (`--mode`) | Nguồn sinh chính | Trường hợp sử dụng | Ví dụ lệnh |
|---|---|---|---|
| `api` | API trực tuyến (xoay vòng key) | Khi có quota, cần tốc độ sinh cực nhanh | `python -m synthadata --domain domains/diseases.yaml --mode api` |
| `offline` | **Ollama cục bộ** | Không có mạng / hết quota / dữ liệu nội bộ | `python -m synthadata --domain domains/diseases.yaml --mode offline --offline-model gemma4:e4b` |
| `hybrid` ⭐ *(Mặc định)* | API trực tuyến ➔ Ollama | Vừa nhanh vừa đảm bảo không gián đoạn | `python -m synthadata --domain domains/diseases.yaml --mode hybrid` |
| `augment` | API (hạt giống) ➔ Ollama nhân bản | Tạo lượng dữ liệu lớn với chi phí tối thiểu | `python -m synthadata --domain domains/diseases.yaml --mode augment --seed-rows 200 --target 1000` |

#### 1. Chạy hoàn toàn Offline với Ollama:
```bash
# Bước 1: Cài đặt mô hình Ollama trên máy
ollama pull qwen2.5

# Bước 2: Bắt đầu sinh 1000 dòng dữ liệu
python -m synthadata --domain domains/diseases.yaml --provider ollama --model qwen2.5 --target 1000
```

#### 2. Chạy với API đám mây:
```bash
# Sử dụng OpenAI
export OPENAI_API_KEY="sk-..."       # Trên Windows PowerShell: $env:OPENAI_API_KEY="sk-..."
python -m synthadata --domain domains/diseases.yaml --provider openai --model gpt-4o-mini --target 1000

# Sử dụng Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..." # Trên Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python -m synthadata --domain domains/diseases.yaml --provider anthropic --model claude-sonnet-4-6 --target 1000
```

---

### Xoay vòng API & Phục hồi lỗi (Rotation & Fallback)

Để tránh bị ngắt quãng do giới hạn tốc độ (Rate Limit) của gói miễn phí, SynthaData hỗ trợ 2 cơ chế xoay vòng song song:

#### Cách 1: Nhiều key cho cùng một dịch vụ
Tạo file `.env` (từ `.env.example`) và phân tách các key bằng dấu phẩy:
```env
GROQ_API_KEY=gsk_key1,gsk_key2,gsk_key3
```

#### Cách 2: Phối hợp nhiều dịch vụ khác nhau
Cấu hình danh sách trong `config.yaml` bằng các `preset` định nghĩa sẵn:
```yaml
provider:
  preset: groq
  rotation:
    - { preset: gemini }                          # Google Gemini
    - { preset: openrouter }                      # OpenRouter (nhiều model :free)
    - { preset: cerebras }                        # Cerebras tốc độ cao
    - { preset: deepseek, model: deepseek-chat }  # DeepSeek
```

Các preset có sẵn: `groq`, `gemini`, `openrouter`, `cerebras`, `together`, `deepseek`, `mistral`, `xai`, `fireworks`, `perplexity`, `openai`, `anthropic`, `ollama`.

---

## 🛡️ Dây chuyền kiểm tra chất lượng (QA Pipeline)

Hệ thống tích hợp quy trình lọc và chuẩn hóa dữ liệu tự động theo thời gian thực:
- **Chuẩn hóa chuỗi:** Chuyển đổi Unicode NFC, gộp khoảng trắng thừa, loại bỏ ký tự điều khiển và ngoặc kép vô hiệu.
- **Schema Validation:** Đảm bảo đủ các trường bắt buộc, kiểm tra kiểu dữ liệu (text, number, enum, boolean) và giới hạn độ dài.
- **Loại bỏ Placeholder:** Tự động phát hiện và loại bỏ các giá trị vô nghĩa (`N/A`, `unknown`, `null`, `...`, `lorem ipsum`).
- **Chống trùng lặp đa tầng:** So sánh chính xác ➔ So khớp mờ ➔ So sánh Cosine khoảng cách ngữ nghĩa vector.
- **Cấu hình Vector Embedding:**
  ```yaml
  embedding:
    type: ollama                 # ollama | openai | hashing | none
    model: bge-m3                # ollama pull bge-m3 (hoặc nomic-embed-text)
    fallback_to_hashing: true    # Tự động lùi về hashing nếu model gặp sự cố
  ```

---

## 📝 Cấu hình Domain dữ liệu mới

Để định nghĩa một chủ đề dữ liệu mới, bạn chỉ cần tạo một file YAML trong thư mục `domains/` (tham khảo `domains/diseases.yaml`):

```yaml
name: consumer_electronics
topic: Real-world consumer electronic devices with accurate technical specs.
language: Vietnamese
dedup_key: product_name

facets:
  - Điện thoại thông minh
  - Laptop văn phòng & gaming
  - Tai nghe không dây

columns:
  - name: product_name
    type: text
    description: Tên thương mại của sản phẩm.
    required: true
    max_len: 120

  - name: release_year
    type: number
    description: Năm ra mắt sản phẩm (2018 - 2026).
    min: 2018
    max: 2026

  - name: category
    type: enum
    description: Phân loại sản phẩm.
    enum: ["smartphone", "laptop", "audio", "accessory"]

  - name: description
    type: text
    description: Mô tả ngắn gọn tính năng nổi bật.
    min_len: 20
    max_len: 500
```

---

## 💾 Đầu ra dữ liệu & Checkpoint

- **`output/<tên_domain>.csv`**: File kết quả chính chứa các dòng dữ liệu sạch, mã hóa chuẩn **UTF-8 with BOM** (hiển thị tiếng Việt hoàn hảo trên Excel).
- **`output/<tên_domain>_rejects.csv`**: File lưu các bản ghi bị loại bỏ kèm lý do chi tiết (giúp bạn tinh chỉnh prompt hoặc điều chỉnh ngưỡng kiểm tra).
- **Checkpoint thông minh**: Nếu phiên chạy bị dừng đột ngột (tắt máy, ngắt mạng), khi chạy lại lệnh cũ hệ thống sẽ **tự động đọc dữ liệu đã sinh và tiếp tục tích lũy** cho đến khi đạt đủ mục tiêu (sử dụng cờ `--no-resume` nếu muốn ghi đè từ đầu).

---

## 🧪 Kiểm thử (Testing)

SynthaData đi kèm bộ kiểm thử toàn diện:

```bash
# 1. Kiểm tra tính ổn định, parser JSON, validator và dedup (không cần mạng)
python -m tests.test_stability

# 2. Kiểm tra toàn bộ luồng pipeline với provider giả lập
python -m tests.test_pipeline

# 3. Kiểm tra kết nối thực tế tới các API endpoint đã cấu hình
python -m tests.test_apis_live
```

---

## 🔒 Bảo mật & Quản lý API Key

- **Không commit API Key:** Mọi API key cần được lưu trữ trong `.env` hoặc `keys.txt`. Cả hai file này đều đã được cấu hình trong `.gitignore`.
- **Mẫu cấu hình an toàn:** Sử dụng file `.env.example` và `keys.example.txt` làm mẫu hướng dẫn, không nhập key thật vào các file mẫu.
- **Che giấu khóa trong log (Key Masking):** Các lệnh kiểm thử kết nối tự động che giấu ký tự bí mật của key khi in ra màn hình.
- **Bảo mật dữ liệu với chế độ Offline:** Khi làm việc với dữ liệu nhạy cảm hoặc nội bộ, sử dụng chế độ `offline` kết hợp mô hình Ollama cục bộ để đảm bảo 100% dữ liệu không rời khỏi thiết bị cá nhân.

---

## ⚠️ Tuyên bố miễn trừ trách nhiệm (Disclaimer)

Dữ liệu domain mẫu y khoa (`domains/diseases.yaml`) chỉ nhằm mục đích **thử nghiệm kỹ thuật, nghiên cứu và giáo dục**. Dữ liệu do các mô hình AI tổng hợp có thể chứa thông tin không chính xác hoặc lỗi thời. **Tuyệt đối không sử dụng dữ liệu này để thay thế cho chẩn đoán y khoa, điều trị hoặc bất kỳ tư vấn y tế chuyên môn nào.**

---

## 📄 Giấy phép (License)

Dự án được phân phối dưới giấy phép mã nguồn mở **MIT License**. Bạn có toàn quyền sử dụng, sửa đổi, phân phối cho mục đích cá nhân cũng như thương mại.

```text
MIT License

Copyright (c) 2026 SynthaData Project Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
