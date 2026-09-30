#!/usr/bin/env python3
"""Canonical RC9.2.2 scenario runner entry point.

Use this filename for RC9.2.2/RC5 runs. ``rc921_runner.py`` is retained only
as the compatibility implementation name for older automation.
"""
from __future__ import annotations

import sys
from pathlib import Path

from rc921_runner import main

if __name__ == "__main__":
    args = list(sys.argv[1:])
    if "--package-root" not in args:
        args += ["--package-root", str(Path(__file__).resolve().parents[1])]
    sys.argv = [sys.argv[0], *args]
    raise SystemExit(main())
