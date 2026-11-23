#!/usr/bin/env python3
"""Score a week + break plan with the engine's own calculate_metrics (Phase D).

The week comes from a workbook's Schedule sheet (engine output workbooks hold
the final week there). Breaks come either from that workbook's 'Break Schedule'
sheet (--engine-breaks: calibration, must reproduce the engine's figures) or
from a JSON plan written by `aggregate_seed_real.py --export-breaks`.

    python3 tools/score_break_plan.py --engine ENGINE --input INPUT.xlsx \
        --week OUTPUT.xlsx (--engine-breaks | --plan PLAN.json)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_synthetic_suite as S  # noqa: E402

DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def engine_break_selection(E, p, sk, week_path: Path):
    """The engine's own breaks from an output workbook's 'Break Schedule' sheet,
    as {(associate, day): pattern index}; break sets matching no legal pattern
    map to None and are listed in the second return value."""
    import openpyxl
    patterns = E.generate_break_patterns(p)
    by_offsets = {(pt.duration_q, frozenset(pt.broken_offsets)): pt.index for pt in patterns}
    a_of = {E.norm(x.name): i for i, x in enumerate(p.associates)}
    ws = openpyxl.load_workbook(week_path, read_only=True)["Break Schedule"]
    offs = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[0] or r[6] != "Scheduled":
            continue
        ai, d = a_of[E.norm(r[0])], DAYS.index(r[1])
        sh = p.shifts[sk.selected_shift_index[ai][d]]
        h, mi = (int(v) for v in str(r[4]).split(":")[:2])
        o0 = ((h * 60 + mi - sh.start_min) % 1440) // 15
        offs.setdefault((ai, d), set()).update(o0 + k for k in range(int(r[5]) // 15))
    selected, unmatched = {}, []
    for (ai, d), o in offs.items():
        sh = p.shifts[sk.selected_shift_index[ai][d]]
        idx = by_offsets.get((sh.duration_q, frozenset(o)))
        if idx is None:
            unmatched.append((p.associates[ai].name, DAYS[d]))
        selected[(ai, d)] = idx
    return selected, unmatched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--week", type=Path, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--engine-breaks", action="store_true")
    g.add_argument("--plan", type=Path)
    a = ap.parse_args()
    E = S.load_engine(a.engine)
    p = E.parse_input(a.input)
    sk = E.load_seed_skeleton(p, a.week, "scored_week")
    if sk is None or sk.diagnostics.get("invalid_seed_cells"):
        raise SystemExit(f"week not readable: {None if sk is None else sk.diagnostics}")
    patterns = E.generate_break_patterns(p)
    a_of = {E.norm(x.name): i for i, x in enumerate(p.associates)}
    selected = {}
    unmatched = []
    if a.engine_breaks:
        selected, unmatched = engine_break_selection(E, p, sk, a.week)
    else:
        for e in json.loads(a.plan.read_text()):
            ai = a_of[E.norm(e["name"])]
            sh = p.shifts[sk.selected_shift_index[ai][e["day"]]]
            if E.norm(sh.label) != E.norm(e["shift"]):
                raise SystemExit(f"plan shift {e['shift']} != week shift {sh.label} for {e['name']} day {e['day']}")
            selected[(ai, e["day"])] = e["pattern"]
    m = E.calculate_metrics(p, sk, selected, patterns)
    keys = ("active_intervals", "before_target", "after_target", "before_floor", "after_floor",
            "break_concurrency_violation_count", "max_concurrent_breaks_observed")
    out = {k: m.get(k) for k in keys if k in m}
    out.update(breaks_selected=sum(1 for v in selected.values() if v is not None), unmatched=unmatched[:10])
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
