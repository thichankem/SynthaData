"""Entrypoint to launch the SynthaData graphical user interface (GUI)."""

import os
import sys

# Ensure relative paths resolve accurately from project root
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from synthadata.cli import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--gui"]
    raise SystemExit(main())
