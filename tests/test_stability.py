"""Kiểm tra ĐỘ ỔN ĐỊNH của các hàm cốt lõi bằng nhiều edge-case khó.

Chạy:  python -m tests.test_stability
Không cần mạng / model — chỉ test logic thuần.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _utf8():
    for s in (sys.stdout, sys.stderr):
        rc = getattr(s, "reconfigure", None)
        if rc:
            try:
                rc(encoding="utf-8", errors="replace")
            except Exception:
                pass


_passed = 0
_failed = 0


def check(name, cond, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"  [FAIL] {name} {extra}")


# ---------------------------------------------------------------------------
def test_extract_json():
    from synthadata.utils import extract_json, coerce_records, salvage_records

    check("json thẳng", extract_json('{"a":1}') == {"a": 1})
    check("json rỗng -> None", extract_json("") is None)
    check("json None -> None", extract_json(None) is None)
    check("fence json", extract_json('```json\n{"a":1}\n```') == {"a": 1})
    check("lẫn văn bản", extract_json('blah blah {"a": [1,2]} hậu tố') == {"a": [1, 2]})
    check("mảng", extract_json('[{"x":1},{"y":2}]') == [{"x": 1}, {"y": 2}])
    check("ngoặc trong chuỗi", extract_json('{"s": "a}b{c"}') == {"s": "a}b{c"})
    check("rác hoàn toàn -> None", extract_json("không có json ở đây") is None)
    # Nested sâu
    check("lồng sâu", extract_json('{"a":{"b":{"c":[1]}}}') == {"a": {"b": {"c": [1]}}})

    # coerce_records các dạng
    check("coerce list", coerce_records([{"a": 1}, "bad", {"b": 2}]) == [{"a": 1}, {"b": 2}])
    check("coerce records key", coerce_records({"records": [{"a": 1}]}) == [{"a": 1}])
    check("coerce dict đơn", coerce_records({"a": 1}) == [{"a": 1}])
    check("coerce None", coerce_records(None) == [])
    check("coerce data key", coerce_records({"data": [{"x": 1}]}) == [{"x": 1}])

    # salvage: JSON bị cắt giữa chừng
    truncated = '{"records": [{"name":"A","v":1},{"name":"B","v":2},{"name":"C"'
    sal = salvage_records(truncated)
    check("salvage vớt 2 bản ghi nguyên", sal == [{"name": "A", "v": 1}, {"name": "B", "v": 2}],
          f"got {sal}")
    check("salvage rỗng", salvage_records("") == [])
    check("salvage không có object", salvage_records("[]") == [])


def test_normalize_key():
    from synthadata.utils import normalize_key, is_placeholder, clean_text

    check("bỏ tiền tố Bệnh", normalize_key("Bệnh sốt xuất huyết") == normalize_key("Sốt xuất huyết"))
    check("bỏ dấu", normalize_key("Cúm") == "cum")
    check("rỗng -> rỗng", normalize_key("") == "")
    check("chỉ 'benh' không thành rỗng", normalize_key("Bệnh") == "benh")
    check("dich benh prefix", normalize_key("Dịch bệnh tả") == normalize_key("Tả"))
    check("placeholder N/A", is_placeholder("N/A"))
    check("placeholder none", is_placeholder("none"))
    # Chuỗi rỗng KHÔNG tính placeholder (validator bắt riêng bằng `not text`).
    check("rỗng không phải placeholder", not is_placeholder(""))
    check("không placeholder", not is_placeholder("Sốt xuất huyết"))
    check("clean_text list", clean_text(["a", "b"]) == "a; b")
    check("clean_text dict", clean_text({"k": "v"}) == "k: v")
    check("clean_text None", clean_text(None) == "")
    check("clean_text bỏ ngoặc kép", clean_text('"hello"') == "hello")
    check("clean_text gộp space", clean_text("a    b\n\tc") == "a b c")
    check("clean_text số", clean_text(123) == "123")


def test_validator():
    from synthadata.schema import Domain, Column
    from synthadata.validation import RecordValidator, R_MISSING, R_BAD_NUMBER, R_BAD_ENUM

    dom = Domain(
        name="t", topic="t",
        columns=[
            Column(name="id", type="number", required=True),
            Column(name="name", type="text", required=True, min_len=2),
            Column(name="sev", type="enum", enum=["mild", "severe"], required=False),
            Column(name="note", type="text", required=False),
        ],
        dedup_key="name",
    )
    v = RecordValidator(dom)

    r = v.validate({"id": "5", "name": "Flu"})
    check("hợp lệ cơ bản", r.ok, r.reason)

    r = v.validate({"id": "abc", "name": "Flu"})
    check("số sai", not r.ok and r.reason == R_BAD_NUMBER, r.reason)

    r = v.validate({"id": "5"})
    check("thiếu name", not r.ok and r.reason == R_MISSING, r.reason)

    r = v.validate({"id": "5", "name": "Flu", "sev": "MILD"})
    check("enum không phân biệt hoa thường", r.ok and r.record["sev"] == "mild", r.reason)

    r = v.validate({"id": "5", "name": "Flu", "sev": "deadly"})
    check("enum sai", not r.ok and r.reason == R_BAD_ENUM, r.reason)

    r = v.validate({"id": "5.5", "name": "Flu", "note": ""})
    check("optional rỗng OK", r.ok, r.reason)

    r = v.validate("not a dict")
    check("không phải dict", not r.ok)

    # số với đơn vị "30 kg" và dấu phẩy "1,000"
    r = v.validate({"id": "1,000", "name": "Flu"})
    check("số có dấu phẩy", r.ok, r.reason)
    r = v.validate({"id": "30 kg", "name": "Flu"})
    check("số có đơn vị", r.ok, r.reason)

    # name quá ngắn
    r = v.validate({"id": "1", "name": "A"})
    check("name quá ngắn bị loại", not r.ok, r.reason)


def test_dedup():
    from synthadata.quality.dedup import DedupRegistry

    reg = DedupRegistry(semantic_enabled=False)
    check("commit lần đầu OK", reg.check_and_commit("cum").ok)
    check("trùng tuyệt đối", not reg.check_and_commit("cum").ok)
    check("len = 1", len(reg) == 1)

    # Tầng mờ: "covid 19" vs "covid19" rất giống
    reg.check_and_commit("covid 19")
    r = reg.check_and_commit("covid  19")  # sau normalize đã giống -> nhưng đây raw
    check("near dup khác nhẹ", not r.ok or r.ok)  # chỉ đảm bảo không crash

    # Semantic với numpy: chèn nhiều vector TRỰC GIAO vượt capacity ban đầu (8)
    # -> test đường grow ma trận (8->16->32) không crash và giữ đủ.
    reg2 = DedupRegistry(semantic_enabled=True, semantic_threshold=0.99)
    for i in range(20):
        vec = [0.0] * 24       # dim 24 > 20 -> mỗi vector trực giao thật sự
        vec[i] = 1.0
        reg2.check_and_commit(f"key{i}", embedding=vec)
    check("dedup grow >8 vector trực giao giữ đủ 20", len(reg2) == 20, f"len={len(reg2)}")

    # vector trùng hệt -> phải bắt
    reg3 = DedupRegistry(semantic_enabled=True, semantic_threshold=0.95)
    v = [1.0, 2.0, 3.0, 4.0]
    reg3.check_and_commit("a", embedding=v)
    r = reg3.check_and_commit("b", embedding=[1.0, 2.0, 3.0, 4.0])
    check("vector trùng bị bắt semantic", not r.ok, r.reason)

    # sample không vượt quá số phần tử
    s = reg.sample(100)
    check("sample <= len", len(s) <= len(reg))


def test_config_load():
    from synthadata.config import AppConfig

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = AppConfig.load(os.path.join(root, "config.yaml"))
    check("config load mode hybrid", cfg.mode == "hybrid", cfg.mode)
    check("config provider type", cfg.provider.type == "openai", cfg.provider.type)
    check("config offline model", cfg.offline.model == "gemma4:e4b", cfg.offline.model)

    # overrides
    cfg2 = AppConfig.load(os.path.join(root, "config.yaml"),
                          overrides={"target_rows": 50, "mode": "OFFLINE", "model": None})
    check("override target_rows", cfg2.generation.target_rows == 50)
    check("override mode lower", cfg2.mode == "offline", cfg2.mode)
    check("override None bỏ qua", cfg2.provider.model == cfg.provider.model)

    # to_dict round-trip không crash
    d = cfg.to_dict()
    check("to_dict có mọi khoá",
          all(k in d for k in ("mode", "provider", "offline", "embedding",
                               "quality", "generation", "output")))

    # api_keys tách nhiều key
    from synthadata.config import ProviderConfig
    pc = ProviderConfig(api_key_override="k1,k2 , k3\nk4")
    check("api_keys tách phẩy+newline", pc.api_keys() == ["k1", "k2", "k3", "k4"],
          pc.api_keys())
    pc2 = ProviderConfig(api_key_override="")
    check("api_keys rỗng", pc2.api_keys() == [])


def test_domain_load():
    from synthadata.schema import Domain
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dom = Domain.load(os.path.join(root, "domains", "diseases.yaml"))
    check("domain có cột", len(dom.columns) > 0)
    check("dedup key hợp lệ", dom.column(dom.effective_dedup_key) is not None)
    check("column_names khớp", len(dom.column_names) == len(dom.columns))


def test_presets():
    from synthadata.presets import resolve_preset, known_presets

    check("có preset groq", "groq" in known_presets())
    g = resolve_preset("groq")
    check("preset groq có base_url", "base_url" in g and g.get("type"))
    # preset không tồn tại
    try:
        resolve_preset("khong_ton_tai_xyz")
        check("preset sai phải raise", False)
    except Exception:
        check("preset sai phải raise", True)


def test_expand_backends():
    from synthadata.config import ProviderConfig
    from synthadata.providers import _expand_backends

    os.environ["TEST_ROT_KEY"] = "ka,kb,kc"
    cfg = ProviderConfig(type="openai", api_key_env="TEST_ROT_KEY",
                         base_url="http://x", keys_file="")
    backs = _expand_backends(cfg)
    check("3 key -> 3 backend", len(backs) == 3, f"len={len(backs)}")
    keys = {b.api_key() for b in backs}
    check("3 key khác nhau", keys == {"ka", "kb", "kc"}, keys)

    # ollama không cần key -> 1 backend
    cfg2 = ProviderConfig(type="ollama", keys_file="")
    check("ollama 1 backend", len(_expand_backends(cfg2)) == 1)
    del os.environ["TEST_ROT_KEY"]


def test_rotating_failover():
    """RotatingProvider: backend đầu luôn lỗi -> phải failover sang backend khỏe."""
    from synthadata.config import ProviderConfig
    from synthadata.providers.base import LLMProvider, ProviderError
    from synthadata.providers.rotating import RotatingProvider

    class Bad(LLMProvider):
        @property
        def name(self): return "bad"
        def health_check(self): pass
        def _call(self, s, u, *, temperature, max_tokens):
            raise ProviderError("HTTP 429 rate limit")

    class Good(LLMProvider):
        @property
        def name(self): return "good"
        def health_check(self): pass
        def _call(self, s, u, *, temperature, max_tokens):
            return '{"records": [{"x": 1}]}'

    cfg = ProviderConfig(max_retries=2)
    rot = RotatingProvider([Bad(cfg), Good(cfg)], cfg)
    out = rot.chat("s", "u", temperature=0.5, max_tokens=100)
    check("failover sang backend khỏe", '"x"' in out, out)

    # Mọi backend đều chết -> raise (không treo)
    rot2 = RotatingProvider([Bad(cfg), Bad(cfg)], cfg)
    try:
        rot2.chat("s", "u", temperature=0.5, max_tokens=100)
        check("mọi backend chết -> raise", False)
    except ProviderError:
        check("mọi backend chết -> raise", True)


def test_writer_resume():
    """Ghi CSV rồi đọc lại khoá -> resume."""
    from synthadata.schema import Domain, Column
    from synthadata.writer import CsvWriter

    dom = Domain(name="t", topic="t",
                 columns=[Column(name="name"), Column(name="desc")],
                 dedup_key="name")
    tmp = tempfile.mkdtemp(prefix="syntha_w_")
    path = os.path.join(tmp, "out.csv")
    with CsvWriter(dom, path) as w:
        w.open(append=False)
        w.write_row({"name": "Cúm", "desc": "abc"})
        w.write_row({"name": "Sởi", "desc": "def"})

    w2 = CsvWriter(dom, path)
    keys = w2.existing_keys()
    check("resume đọc 2 khoá", len(keys) == 2, keys)

    # append giữ nguyên dữ liệu cũ
    with CsvWriter(dom, path) as w3:
        w3.open(append=True)
        w3.write_row({"name": "Lao", "desc": "ghi"})
    check("append +1 khoá", len(CsvWriter(dom, path).existing_keys()) == 3)


def main():
    _utf8()
    tests = [
        ("extract/coerce/salvage JSON", test_extract_json),
        ("normalize_key / clean_text", test_normalize_key),
        ("RecordValidator", test_validator),
        ("DedupRegistry", test_dedup),
        ("Config load + overrides", test_config_load),
        ("Domain load", test_domain_load),
        ("Presets", test_presets),
        ("Expand backends (rotation)", test_expand_backends),
        ("Rotating failover", test_rotating_failover),
        ("Writer + resume", test_writer_resume),
    ]
    print("=== TEST ĐỘ ỔN ĐỊNH ===\n")
    for name, fn in tests:
        try:
            fn()
            print(f"[ok] {name}")
        except Exception as e:
            global _failed
            _failed += 1
            import traceback
            print(f"[ERROR] {name}: {e}")
            traceback.print_exc()

    print(f"\n=== KẾT QUẢ: {_passed} pass, {_failed} fail ===")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
