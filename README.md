# SynthaData

<p align="center">
  <img src="synthadata.ico" alt="SynthaData Logo" width="96" height="96">
</p>

<p align="center">
  <strong>Production-Grade Synthetic Data Generation Engine</strong><br>
  Continuous Multi-Layer QA • 3-Tier Semantic Vector Deduplication • Multi-Provider API Rotation • Offline Local LLM Fallback
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+"></a>
  <a href="#-license"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square" alt="Cross-Platform">
  <img src="https://img.shields.io/badge/UI-Tkinter%20GUI%20%2B%20CLI-blueviolet?style=flat-square" alt="GUI and CLI">
  <img src="https://img.shields.io/badge/QA%20Pipeline-Continuous%20Validation-orange?style=flat-square" alt="Continuous QA">
</p>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Installation](#-installation)
- [Usage Guide](#-usage-guide)
  - [Graphical User Interface (GUI)](#graphical-user-interface-gui)
  - [Command-Line Interface (CLI)](#command-line-interface-cli)
  - [Execution Modes](#execution-modes)
- [Multi-Provider API Rotation & Fallback](#-multi-provider-api-rotation--fallback)
- [Continuous Quality Assurance (QA) Pipeline](#-continuous-quality-assurance-qa-pipeline)
  - [Sanitization & Schema Validation](#sanitization--schema-validation)
  - [3-Tier Deduplication Pipeline](#3-tier-deduplication-pipeline)
  - [Real-Time Monitoring & Adaptive Sampling](#real-time-monitoring--adaptive-sampling)
- [Defining Custom Domains](#-defining-custom-domains)
- [Output Format & Checkpoints](#-output-format--checkpoints)
- [Testing](#-testing)
- [Security & Privacy](#-security--privacy)
- [Disclaimer](#-disclaimer)
- [License](#-license)

---

## 🌟 Overview

**SynthaData** is a high-throughput synthetic data generation framework designed to synthesize rich, diverse, and domain-accurate tabular datasets (formatted as RFC 4180 CSV with UTF-8 BOM). It provides the foundational data needed to train, fine-tune, or benchmark modern Machine Learning models and LLMs.

SynthaData bridges the gap between cloud API speed and local execution sovereignty:
1. **Cloud API Services:** Seamless integration with OpenAI, Anthropic (Claude), Google Gemini, Groq, OpenRouter, Cerebras, Together AI, DeepSeek, Mistral, xAI, Fireworks, and Perplexity.
2. **Local Offline Inference:** First-class support for **Ollama** running locally on CPU/GPU without external network dependencies, ensuring zero operational costs and strict data sovereignty.

---

## ✨ Key Features

- **3-Tier Deduplication Engine:**
  - *Tier 1 (Exact Match):* Normalized key hashing for $O(1)$ duplicate rejection.
  - *Tier 2 (Fuzzy Lexical):* String similarity matching via RapidFuzz / Levenshtein distance.
  - *Tier 3 (Semantic Vector Cosine):* Text signature embedding via vector models (e.g., `bge-m3`, `nomic-embed-text`) with cosine distance filtering to catch conceptual duplicates that lexical checks miss (e.g., *"Hansen's Disease"* vs. *"Leprosy"*).
- **Automated API Rotation & Fault Tolerance:**
  - Distributes workload across multiple API keys or heterogeneous providers to prevent rate-limiting (`429 Too Many Requests`).
  - Auto-ejects dead endpoints upon startup and seamlessly fails over to healthy backends.
- **Hybrid Auto-Fallback:**
  - Automatically transitions from cloud APIs to local Ollama inference if all cloud quotas expire.
- **Adaptive Generation & Mode-Collapse Mitigation:**
  - Real-time rolling window tracker monitors acceptance ratios.
  - Automatically increases generation temperature when duplicate collisions surge, preventing topic depletion.
- **Dual Interface:**
  - **Tkinter GUI:** High-DPI aware, real-time streaming logs, live progress meters, and dynamic Ollama model discovery.
  - **CLI:** Highly configurable, scriptable, and multithreaded.
- **Incremental Checkpointing:**
  - Automatically resumes interrupted jobs; rejects are isolated into `*_rejects.csv` with structured diagnostic reason codes.

---

## 🏗 System Architecture

```
synthadata/
├── config.py             # Configuration layer (providers, embeddings, QA, generation)
├── schema.py             # Domain parser & YAML schema validator
├── prompts.py            # Prompt engineering & system instruction synthesizer
├── generator.py          # Parallel execution coordinator & adaptive sampling engine
├── validation.py         # Unicode sanitization & structural record validator
├── writer.py             # CSV output manager with incremental checkpointing
├── cli.py                # Command-Line Interface entrypoint
├── gui.py                # Graphical User Interface (Tkinter)
├── providers/            # LLM provider abstractions
│   ├── base.py           # Unified interface, exponential backoff & retry mechanics
│   ├── openai_api.py     # OpenAI-compatible API clients (Groq, Together, DeepSeek)
│   ├── anthropic_api.py  # Anthropic Claude API integration
│   ├── ollama.py         # Local Ollama client
│   └── rotating.py       # Load-balancing provider rotator with failover
├── embeddings/           # Vector representation interfaces
│   ├── base.py           # Embedder base interface
│   ├── ollama_embed.py   # Local offline embeddings (bge-m3, nomic-embed-text)
│   ├── openai_embed.py   # OpenAI embedding endpoints (text-embedding-3-small)
│   └── hashing.py        # Deterministic fallback lexical hash embedder
└── quality/              # Continuous Quality Assurance (QA) assembly line
    ├── checks.py         # Modular checks (Structure, Schema, Consistency, Placeholders)
    ├── dedup.py          # 3-tier deduplication registry (Exact, Fuzzy, Semantic)
    ├── monitor.py        # Real-time metrics collector & mode-collapse detector
    └── pipeline.py       # End-to-end QA pipeline processor
```

### Batch Data Flow:

```
[LLM Call] ──> [JSON Extraction & Coercion] ──> [StructureCheck]
                                                        │
                                                        ▼
[3-Tier Dedup] <── [Batch Vector Embedding] <── [Schema & Consistency Check]
      │
      ├──> (Accepted) ──> [Write to Output CSV] ──> [Update Rolling Monitor]
      │
      └──> (Rejected) ──> [Write to Rejects CSV with Reason Code]
```

---

## 💻 Installation

### Prerequisites:
- **Python:** Version 3.9 or higher (tested on 3.10, 3.11, 3.12, and 3.13).
- **Git**

### Setup:

```bash
# Clone the repository
git clone https://github.com/your-username/SynthaData.git
cd SynthaData

# Create and activate a virtual environment (recommended)
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

> **Note:** `rapidfuzz`, `tqdm`, and `python-dotenv` are optional optimizations. If absent, the engine automatically falls back to standard library equivalents (`difflib`, internal logging).

---

## 🚀 Usage Guide

### Graphical User Interface (GUI)

Launch the desktop application via:

```bash
python -m synthadata --gui
# or alternatively:
python run_gui.py
```

Features included in the GUI:
- Dropdown auto-populated with all locally available Ollama models (`ollama list`).
- Real-time generation progress bar and throughput monitor.
- Live console logging window with auto-scroll.
- One-click dry run mode to validate configurations before launching mass generation.

---

### Command-Line Interface (CLI)

#### 1. Local Offline Generation (Ollama)
Requires no API keys, no network access, and zero expense:

```bash
# 1. Download desired model via Ollama
ollama pull qwen2.5

# 2. Synthesize 1,000 disease records locally
python -m synthadata --domain domains/diseases.yaml --provider ollama --model qwen2.5 --target 1000
```

#### 2. Cloud API Generation
Export your API key and trigger the pipeline:

```bash
# Using OpenAI
export OPENAI_API_KEY="sk-..."
python -m synthadata --domain domains/diseases.yaml --provider openai --model gpt-4o-mini --target 1000

# Using Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..."
python -m synthadata --domain domains/diseases.yaml --provider anthropic --model claude-sonnet-4-6 --target 1000
```

*(On Windows PowerShell, use `$env:OPENAI_API_KEY = "sk-..."`)*

---

### Execution Modes

Configure `--mode` on the CLI or specify `mode` in `config.yaml`:

| Mode | Generation Engine | Best For | CLI Example |
|---|---|---|---|
| `api` | Cloud APIs with key rotation | Maximum throughput, when quota is available | `--mode api` |
| `offline` | Local Ollama models | Air-gapped environments, zero cost, sensitive data | `--mode offline --offline-model gemma4:e4b` |
| `hybrid` ⭐ *(Default)* | Primary Cloud API ➔ Ollama Fallback | Resilient generation; never halts if rate-limited | `--mode hybrid` |
| `augment` | API Seeds ➔ Ollama Expansion | Cost-efficient scaling using few-shot seeds | `--mode augment --seed-rows 200 --target 1000` |

---

## 🔄 Multi-Provider API Rotation & Fallback

To bypass stringent free-tier rate limits, configure rotation in `config.yaml` or `.env`:

### Strategy A: Distribute Across Multiple Keys (Same Provider)
Populate comma-separated tokens in your `.env` file:
```env
GROQ_API_KEY=gsk_key1,gsk_key2,gsk_key3
```

### Strategy B: Rotate Across Multiple Disparate Providers
Define endpoints in `config.yaml` using pre-configured presets:
```yaml
provider:
  preset: groq
  rotation:
    - { preset: gemini }                          # Google Gemini
    - { preset: openrouter }                      # OpenRouter (:free models)
    - { preset: cerebras }                        # Cerebras Ultra-Fast Inference
    - { preset: deepseek, model: deepseek-chat }  # DeepSeek API
```

Supported built-in presets: `groq`, `gemini`, `openrouter`, `cerebras`, `together`, `deepseek`, `mistral`, `xai`, `fireworks`, `perplexity`, `openai`, `anthropic`, and `ollama`.

---

## 🛡 Continuous Quality Assurance (QA) Pipeline

Every synthesized record batch passes through an in-memory validation gauntlet:

### Sanitization & Schema Validation
- **Unicode Normalization:** Enforces NFC standard, removes illegal non-printable control characters, trims extraneous whitespace.
- **Schema Adherence:** Validates data types (`text`, `number`, `enum`, `bool`), boundary conditions (`min_len`, `max_len`, `min`, `max`), and required fields.
- **Placeholder Elimination:** Rejects canned dummy patterns (`N/A`, `unknown`, `null`, `lorem ipsum`, `...`).

### 3-Tier Deduplication Pipeline
1. **Exact Deduplication:** Strips punctuation, diacritics, and case; evaluates key uniqueness via hashed sets.
2. **Fuzzy String Similarity:** Evaluates edit distance via RapidFuzz (`quality.fuzzy_threshold: 0.92`).
3. **Semantic Vector Cosine:** Computes cosine similarity across dense vector embeddings (`quality.semantic_threshold: 0.96`). Effectively identifies synonyms and alternate medical terminology (e.g., *"Hansen's Disease"* vs. *"Leprosy"* at cosine $\approx 0.96$).

```yaml
embedding:
  type: ollama                 # ollama | openai | hashing | none
  model: bge-m3                # Multilingual SOTA model (or nomic-embed-text)
  fallback_to_hashing: true    # Gracefully falls back to lexical hashing if offline
```

### Real-Time Monitoring & Adaptive Sampling
- **Quality Monitor:** Emits acceptance rate snapshots every $N$ records. Detects **mode collapse** when categorical enum distributions skew unnaturally.
- **Dynamic Temperature Boost:** When acceptance rates drop below `min_rolling_accept`, the engine autonomously increments model temperature (up to `temp_max`), forcing greater exploration of the latent space.

---

## 📝 Defining Custom Domains

To create a new dataset domain, specify a YAML configuration under `domains/` (see [`domains/diseases.yaml`](file:///domains/diseases.yaml) for a complete example):

```yaml
name: consumer_electronics
topic: Real-world consumer electronic devices with accurate technical specs.
language: English
dedup_key: product_name

facets:
  - Flagship Smartphones
  - Ultralight Laptops
  - Noise-Cancelling Headphones

columns:
  - name: product_name
    type: text
    description: Full commercial product name.
    required: true
    max_len: 120

  - name: release_year
    type: number
    description: Product launch year (2018 - 2026).
    min: 2018
    max: 2026

  - name: category
    type: enum
    description: Category classification.
    enum: ["smartphone", "laptop", "audio", "wearable"]

  - name: description
    type: text
    description: Summary of technical specifications and key innovations.
    min_len: 20
    max_len: 500
```

---

## 💾 Output Format & Checkpoints

- **`output/<domain>.csv`:** Validated synthetic records with standard **UTF-8 with BOM** encoding for full Excel and Pandas compatibility.
- **`output/<domain>_rejects.csv`:** Detailed ledger of dropped records annotated with specific failure causes (`DUPLICATE_SEMANTIC`, `SCHEMA_VIOLATION`, `PLACEHOLDER`, etc.).
- **Automatic Resume:** Interrupted jobs resume seamlessly from the last recorded state. Pass `--no-resume` to overwrite existing files.

---

## 🧪 Testing

SynthaData includes a comprehensive test suite that runs without active API keys or network calls:

```bash
# 1. Run core logic, JSON parsing, validator, and edge-case tests
python -m tests.test_stability

# 2. Run mock pipeline integration test
python -m tests.test_pipeline

# 3. (Optional) Validate live connectivity for configured API keys
python -m tests.test_apis_live
```

---

## 🔒 Security & Privacy

- **Credential Isolation:** Never commit `.env` or API credentials. Both `.env` and `keys.txt` are excluded via [`.gitignore`](file:///.gitignore).
- **Template Security:** Only `.env.example` is committed, providing placeholder variables without live secrets.
- **Log Key Masking:** Diagnostics mask sensitive keys (e.g., displaying `gsk_12…ab34`) to prevent exposure during demonstrations or log sharing.
- **Air-Gapped Privacy:** In `offline` mode, all data generation and semantic deduplication remain strictly on the host system. No outbound network requests are dispatched.
- **Zero PII Exposure:** The codebase is scrubbed of all developer identities, internal hostnames, and private absolute file paths.

---

## ⚠️ Disclaimer

The sample medical domain [`domains/diseases.yaml`](file:///domains/diseases.yaml) is provided solely for **machine learning benchmarking, educational research, and technical evaluation**. Data generated by synthetic models may contain inaccuracies, hallucinations, or obsolete medical claims. **Never use generated synthetic medical data as a substitute for professional clinical advice, diagnoses, or treatment plans.**

---

## 📄 License

This project is licensed under the terms of the **MIT License**.

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
