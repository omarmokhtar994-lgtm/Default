#!/usr/bin/env python3
"""Resume one exact-identity run from its checkpoints."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
args = list(sys.argv[1:])
if "--resume" not in args: args.append("--resume")
if "--mode" not in args: args += ["--mode", "QUICK"]
sys.path.insert(0, str(ROOT / "engine"))
from RUN_UNIVERSAL_PRODUCTION import main  # noqa: E402

if __name__ == "__main__":
    sys.argv = [sys.argv[0], *args]
    raise SystemExit(main())
