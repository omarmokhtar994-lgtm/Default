#!/usr/bin/env python3
"""How does the Python-side cost grow with roster size and interval granularity?

Builds 24/7 workbooks of increasing size (make_case.build), then times the
pre-solver work every run does (parse, capacity diagnostics, contract) and one
Stage-1 model build with a 1-second solve, so the time is dominated by model
construction in Python, not by CP-SAT search.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import make_case  # noqa: E402
import l632_universal_scheduler as E  # noqa: E402


def case(n_assoc: int, step: int, start_step: int):
    names = [f"Agent {i:03d}" for i in range(n_assoc)]
    shifts = [f"{m // 60:02d}:{m % 60:02d} - {((m + 540) % 1440) // 60:02d}:{(m + 540) % 60:02d}"
              for m in range(0, 1440, start_step)]
    per_assoc_hours = 5 * 7.5
    level = max(1.0, round(n_assoc * per_assoc_hours / (7 * 24) * 0.9, 1))
    return {"roster": [(n, "English") for n in names], "step": step, "shifts": shifts,
            "demand": lambda d, m: level, "instructions": {"Count of Associates": n_assoc}}


def main():
    rows = []
    grid = [(30, 60, 60), (60, 60, 60), (60, 30, 30), (120, 30, 30), (60, 15, 15), (120, 15, 15)]
    for n_assoc, step, start_step in grid:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scale.xlsx"
            make_case.build(case(n_assoc, step, start_step), path)
            t0 = time.time(); parsed = E.parse_input(path); t_parse = time.time() - t0
            t0 = time.time(); cap = E.capacity_diagnostics(parsed); t_cap = time.time() - t0
            t0 = time.time(); E.validate_input_contract(parsed, cap); t_contract = time.time() - t0
            profile = E.skeleton_profiles()[0]
            t0 = time.time()
            sk = E.build_skeleton(parsed, profile, E.HardConfig(), 1.0, 2, open("/dev/null", "w"))
            t_build = time.time() - t0
            row = {"associates": n_assoc, "interval_min": step, "shift_starts": len(parsed.shifts),
                   "x_vars": n_assoc * 7 * len(parsed.shifts), "parse_s": round(t_parse, 1),
                   "capacity_s": round(t_cap, 1), "contract_s": round(t_contract, 1),
                   "stage1_build_plus_1s_solve_s": round(t_build, 1), "stage1_status": sk.cp_status}
            rows.append(row)
            print(json.dumps(row), flush=True)
    (HERE / "SCALE_PROBE_RESULT.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
