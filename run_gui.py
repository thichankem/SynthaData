"""Entrypoint để PyInstaller đóng gói thành SynthaData.exe (mở GUI)."""

import os
import sys

# Khi chạy dạng .exe đóng gói, đặt thư mục làm việc về cạnh file .exe
# để config.yaml / domains / keys.txt / output được tìm theo đường dẫn tương đối.
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from synthadata.cli import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--gui"]
    raise SystemExit(main())
