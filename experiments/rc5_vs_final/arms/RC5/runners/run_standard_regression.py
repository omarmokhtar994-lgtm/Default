#!/usr/bin/env python3
"""Run the manifest regression set with bounded Quick budgets."""
from __future__ import annotations
import sys
from pathlib import Path
from rc922_runner import main

args = list(sys.argv[1:])
if "--package-root" not in args:
    args += ["--package-root", str(Path(__file__).resolve().parents[1])]
if "--mode" not in args: args += ["--mode", "QUICK"]
if "--stage" not in args: args += ["--stage", "FULL_SCHEDULE"]

if __name__ == "__main__":
    sys.argv = [sys.argv[0], *args]
    raise SystemExit(main())
