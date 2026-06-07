"""Smoke test: chạy toàn bộ dây chuyền với provider + embedder GIẢ LẬP (offline).

Chứng minh:
  - các lớp config/schema/quality/generator/writer ráp đúng,
  - QA loại đúng: thiếu trường, placeholder, trùng TUYỆT ĐỐI,
  - chống trùng NGỮ NGHĨA bắt được cặp "Leprosy" vs "Hansen's Disease" (khác mặt
    chữ nhưng cùng khái niệm) — thứ mà trùng tuyệt đối/mờ bỏ sót.

Chạy:  python -m tests.test_pipeline
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthadata.config import GenerationConfig, ProviderConfig, QualityConfig
from synthadata.generator import DataGenerator
from synthadata.providers.base import LLMProvider
from synthadata.schema import Domain
from synthadata.writer import CsvWriter

_ADJ = ["cardiac", "hepatic", "renal", "pulmonary", "gastric", "cerebral",
        "spinal", "ocular", "dermal", "skeletal", "vascular", "thyroid"]
_NOUN = ["fibrosis", "syndrome", "dysplasia", "necrosis", "atrophy",
         "carcinoma", "stenosis", "edema", "sclerosis", "neuropathy"]


class FakeEmbedder:
    """Embedder giả: ánh xạ văn bản -> vector one-hot theo 'khái niệm'.
    Hai cách viết của BỆNH PHONG ("leprosy"/"hansen") -> cùng một vector."""

    name = "fake-embed"
    dim = 4096

    def health_check(self) -> None:
        pass

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            low = t.lower()
            concept = "leprosy" if ("leprosy" in low or "hansen" in low) else low
            idx = int(hashlib.md5(concept.encode()).hexdigest(), 16) % self.dim
            vec = [0.0] * self.dim
            vec[idx] = 1.0
            out.append(vec)
        return out


class FakeProvider(LLMProvider):
    def __init__(self):
        super().__init__(ProviderConfig(max_retries=1, timeout=5))
        self._combos = itertools.cycle(
            f"{a} {n}" for a, n in itertools.product(_ADJ, _NOUN)
        )
        self._first_name: str | None = None
        self._emitted_pair = False
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "fake:test"

    def health_check(self) -> None:
        pass

    def _record(self, name: str, desc: str | None = None) -> dict:
        return {
            "disease_name": name,
            "icd11_or_icd10_code": "T01",
            "category": "infectious",
            "affected_system": "immune system",
            "description": desc or f"A synthetic condition '{name}' for validation.",
            "common_symptoms": "fever; fatigue; headache",
            "causes": "Synthetic test pathogen.",
            "risk_factors": "being a test case",
            "transmission": "Non-communicable",
            "diagnosis": "Unit test assertion.",
            "treatment": "Run the test again.",
            "prevention": "Write better code",
            "severity": "mild",
            "is_contagious": "no",
            "typical_age_group": "any",
            "global_prevalence": "rare",
        }

    def _call(self, system, user, *, temperature, max_tokens) -> str:
        records = []
        with self._lock:
            for _ in range(15):
                name = next(self._combos)
                if self._first_name is None:
                    self._first_name = name
                records.append(self._record(name))
            # TRÙNG TUYỆT ĐỐI (tên đã sinh) -> bị loại.
            records.append(self._record(self._first_name))
            # Thiếu trường bắt buộc -> bị loại.
            records.append({"disease_name": "", "description": ""})
            # Placeholder -> bị loại.
            records.append(self._record("N/A"))
            # Cặp TRÙNG NGỮ NGHĨA (khác mặt chữ, cùng khái niệm) -> bản 2 bị loại.
            if not self._emitted_pair:
                self._emitted_pair = True
                desc = "A chronic infection caused by Mycobacterium leprae affecting skin and nerves."
                records.append(self._record("Leprosy", desc))
                records.append(self._record("Hansen's Disease", desc))
        return json.dumps({"records": records})


def _ensure_utf8_console() -> None:
    """Ép stdout/stderr về UTF-8 để không crash khi in tiếng Việt trên console
    Windows mặc định (cp1252). An toàn nếu stream không hỗ trợ reconfigure."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> int:
    _ensure_utf8_console()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    domain = Domain.load(os.path.join(root, "domains", "diseases.yaml"))
    target = 40
    gcfg = GenerationConfig(target_rows=target, batch_size=15, workers=3,
                            temperature=0.0, stall_rounds=10)
    qcfg = QualityConfig(semantic_enabled=True, semantic_threshold=0.90,
                         monitor_every=1000, adaptive=False)

    tmp = tempfile.mkdtemp(prefix="synthadata_test_")
    out = os.path.join(tmp, "out.csv")
    writer = CsvWriter(domain, out, write_rejects=True)
    gen = DataGenerator(FakeProvider(), domain, gcfg, writer,
                        embedder=FakeEmbedder(), quality_cfg=qcfg)

    with writer:
        writer.open(append=False)
        outcome = gen.run()

    with open(out, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    names = [r["disease_name"] for r in rows]
    lname = {n.lower() for n in names}

    assert len(rows) >= target, f"Cần >= {target} dòng, có {len(rows)}"
    assert len(names) == len(set(names)), "Có dòng TRÙNG lọt qua!"
    assert all(n and n.upper() != "N/A" for n in names), "Có placeholder lọt qua!"
    assert list(rows[0].keys()) == domain.column_names, "Header CSV sai cột."
    for reason in ("duplicate_exact", "missing_required", "placeholder_value",
                   "duplicate_semantic"):
        assert outcome.report.rejects.get(reason, 0) > 0, f"QA bỏ sót lỗi: {reason}"
    # Chỉ MỘT trong hai cách viết bệnh phong được giữ lại.
    assert not ("leprosy" in lname and "hansen's disease" in lname), \
        "Chống trùng ngữ nghĩa KHÔNG bắt được cặp Leprosy/Hansen's Disease!"

    leprosy_kept = [n for n in names if n.lower() in ("leprosy", "hansen's disease")]
    print("\n[PASS] Dây chuyền + chống trùng NGỮ NGHĨA hoạt động đúng.")
    print(f"       Dòng hợp lệ : {len(rows)} (đều duy nhất)")
    print(f"       Đã loại     : {outcome.report.total_rejected} "
          f"({dict(outcome.report.rejects)})")
    print(f"       Bệnh phong giữ lại: {leprosy_kept}")
    print(f"       CSV mẫu     : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
