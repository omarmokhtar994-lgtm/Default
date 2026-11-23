#!/usr/bin/env python3
"""Run only explicitly named affected scenarios under the Quick budget."""
from __future__ import annotations
import sys
from pathlib import Path
from rc922_runner import main

args = list(sys.argv[1:])
if "--package-root" not in args:
    args += ["--package-root", str(Path(__file__).resolve().parents[1])]
if not any(value in args for value in ("-h", "--help")) and "--only" not in args and "--input" not in args:
    raise SystemExit("Targeted regression requires --only ID[,ID...] or --input WORKBOOK.xlsx")
if "--mode" not in args: args += ["--mode", "QUICK"]
if "--stage" not in args: args += ["--stage", "FULL_SCHEDULE"]

if __name__ == "__main__":
    sys.argv = [sys.argv[0], *args]
    raise SystemExit(main())
