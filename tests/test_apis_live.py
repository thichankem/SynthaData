"""Test GỌI THẬT từng backend API ngoài (groq/gemini/openrouter...) đang cấu hình.

Mỗi backend: health_check + 1 lần gọi sinh JSON nhỏ -> báo OK / lỗi + lý do.
Chạy:  python -m tests.test_apis_live
Cần mạng + key trong .env / keys.txt.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for s in (sys.stdout, sys.stderr):
    rc = getattr(s, "reconfigure", None)
    if rc:
        try:
            rc(encoding="utf-8", errors="replace")
        except Exception:
            pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from synthadata.config import AppConfig
from synthadata.providers import _expand_backends, _build_single

_SYS = "Bạn trả về JSON hợp lệ."
_USER = ('Trả về JSON dạng {"records":[...]} gồm ĐÚNG 2 bệnh, mỗi bệnh có khoá '
         '"disease_name" và "description" (tiếng Việt, ngắn). CHỈ JSON.')


def _mask(key):
    if not key:
        return "(không key)"
    return key[:6] + "…" + key[-4:] if len(key) > 12 else "(ngắn)"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = AppConfig.load(os.path.join(root, "config.yaml"))

    backend_cfgs = _expand_backends(cfg.provider)
    print(f"=== TEST {len(backend_cfgs)} BACKEND API NGOÀI (gọi thật) ===\n")

    ok = bad = 0
    for i, bc in enumerate(backend_cfgs, 1):
        prov = _build_single(bc)
        label = f"[{i}] {prov.name}  base={bc.base_url or bc.host}  key={_mask(bc.api_key())}"
        print(label)

        # 1) health_check
        try:
            prov.health_check()
            print("    health_check: OK")
        except Exception as e:
            print(f"    health_check: LỖI -> {str(e)[:150]}")

        # 2) gọi sinh thật
        t0 = time.time()
        try:
            content = prov._call(_SYS, _USER, temperature=0.5, max_tokens=400)
            dt = time.time() - t0
            from synthadata.utils import coerce_records, extract_json
            recs = coerce_records(extract_json(content))
            if recs:
                ok += 1
                print(f"    gọi sinh   : OK ({dt:.1f}s) -> {len(recs)} bản ghi, "
                      f"vd: {recs[0].get('disease_name','?')!r}")
            else:
                bad += 1
                print(f"    gọi sinh   : RỖNG/KHÔNG PARSE ĐƯỢC ({dt:.1f}s) "
                      f"raw[:120]={content[:120]!r}")
        except Exception as e:
            bad += 1
            dt = time.time() - t0
            print(f"    gọi sinh   : LỖI ({dt:.1f}s) -> {str(e)[:200]}")
        print()

    print(f"=== KẾT QUẢ: {ok} backend sinh được, {bad} lỗi/rỗng ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
