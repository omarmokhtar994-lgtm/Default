# © 2026 Omar Mokhtar. All rights reserved.
"""Print a workbook's break rules as JSON, read by the engine's own parser (Phase R).

Run in a subprocess from the package root, exactly as engine/tools/independent_validator.py loads the
engine: the website never imports the engine into its own process, and the engine is not changed. The
rules are what the validator checks a version against: the break set per shift length, each break's
window, the edge margin, the gaps, and how many may be on a break at once. All times in minutes.

    python webapp/break_rules_cli.py --input WORKBOOK --engine engine/_tools/l632_universal_scheduler.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load(engine: Path):
    sys.path.insert(0, str(engine.parent))
    spec = importlib.util.spec_from_file_location("break_rules_parser", engine)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _minutes(q):
    return None if q is None else int(q) * 15


def rules(input_path: Path, engine: Path) -> dict:
    eng = _load(engine)
    parsed = eng.parse_input(input_path)
    segments = [[int(q) * 15, str(label)] for q, label in parsed.break_segments_q]
    by_length = [[int(threshold), [[int(q) * 15, str(label)] for q, label in sets]]
                 for threshold, sets in (getattr(parsed, "break_sets_by_shift_length", ()) or ())]
    windows = {str(k).strip().casefold(): {"earliest": _minutes(v.get("earliest_q")), "latest": _minutes(v.get("latest_q"))}
               for k, v in (parsed.break_window_rules_q or {}).items()}
    return {"segments": segments, "by_length": by_length, "windows": windows,
            "edge_margin": _minutes(parsed.break_edge_margin_q), "min_gap": _minutes(parsed.break_min_gap_q),
            "preferred_gap": _minutes(parsed.break_preferred_gap_q), "max_gap": _minutes(parsed.break_normal_max_gap_q),
            "back_to_back": bool(getattr(parsed, "allow_back_to_back_breaks", False)),
            "max_concurrent": int(getattr(parsed, "break_max_concurrent_absolute", 0) or 0),
            "max_concurrent_ratio": float(getattr(parsed, "break_max_concurrent_ratio", 0) or 0)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--engine", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(rules(args.input, args.engine)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
