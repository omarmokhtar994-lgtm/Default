#!/usr/bin/env python3
"""Run DEEP only with a recorded unresolved-defect reason."""
from __future__ import annotations
import sys
from pathlib import Path
from rc922_runner import main

args = list(sys.argv[1:])
help_requested = any(value in args for value in ("-h", "--help"))
if not help_requested and "--reason" not in args:
    raise SystemExit("DEEP requires --reason 'specific unresolved defect'")
if not help_requested:
    index = args.index("--reason")
    if index + 1 >= len(args) or not args[index + 1].strip():
        raise SystemExit("--reason must be nonblank")
    reason = args[index + 1]
    del args[index:index + 2]
    print(f"DEEP ESCALATION REASON: {reason}", flush=True)
if "--package-root" not in args:
    args += ["--package-root", str(Path(__file__).resolve().parents[1])]
if "--mode" not in args: args += ["--mode", "DEEP"]
if "--stage" not in args: args += ["--stage", "FULL_SCHEDULE"]

if __name__ == "__main__":
    sys.argv = [sys.argv[0], *args]
    raise SystemExit(main())
