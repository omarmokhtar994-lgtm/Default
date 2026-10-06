#!/usr/bin/env python3
"""Phase D3 stage 1: build a seed week for a workbook from the workbook alone.

The engine keeps a perfect seed perfect (D2b: R10 skill 1, 504/504 seeded vs
294/292 unseeded), so a better seed is a better schedule. Its per-associate
Stage-1 search, however, rarely finds the week an aggregated model finds in
seconds. This tool computes that week and writes it into the Schedule sheet,
which the engine reads as a seed (--use-input-schedule-as-seed, the
production runner's default). A seed is a hint, never a constraint: every rule
is still enforced by the engine and checked by the validator.

Changes no engine file. Uses the engine only to read the workbook (parse,
shifts, legal break patterns, carry-in) and to run its own aggregate guide.

Steps:
  1. candidate shifts = the shifts the engine's aggregate guide gives a
     positive count (the D3a switch is set on the parsed copy when shifts are
     mixed, so the guide runs), capped at the busiest --max-shifts;
  2. exact aggregated CP-SAT model over legal weekly tours (OFF rule, rest
     gap, at most the workbook's number of different shifts) with break starts
     from the engine's legal patterns and its concurrent-break cap, maximising
     intervals at target in the engine's metric (shrinkage, target, carry-in);
  3. tours dealt to associates (carry-in associates get tours that respect
     the rest gap after last Saturday), written to the Schedule sheet.

Stage 1 scope: single-language workbooks with no leave, hard OFF or fixed
requests, strict OFF count, no 11H/3OFF. Anything else is refused with a reason.

    python3 tools/aggregate_seed.py --engine engine/_tools/l632_universal_scheduler.py \
        --out-dir DIR WORKBOOK.xlsx [...]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_synthetic_suite as S  # noqa: E402


def engine_break_cap(staffed: int, ratio: float, absolute: int) -> int:
    """The engine's maximum_concurrent_breaks for one quarter, restated."""
    if staffed <= 1:
        return 0
    return max(0, min(staffed - 1, max(1, int(math.floor(staffed * ratio + 1e-9))), max(1, int(absolute))))


def add_break_cap(m, b, staffed, ratio: float, absolute: int, slack=None, max_staffed: int = 200) -> None:
    """Concurrent-break cap on one quarter: breaks `b` among `staffed` heads (on
    floor + on break + carry-in), equal to the engine's maximum_concurrent_breaks:
    min(staffed - 1, max(1, floor(ratio * staffed)), max(1, absolute)), 0 when
    staffed <= 1. `slack` (IntVar) lets b exceed that cap by at most slack.
    Encoded as a table lookup on the staffed count (no reified switches: with a
    pinned week the count is a constant and presolve folds the lookup away)."""
    table = [engine_break_cap(n, ratio, absolute) for n in range(max_staffed + 1)]
    s_var = m.NewIntVar(0, max_staffed, "")
    m.Add(s_var == staffed)
    cap = m.NewIntVar(0, max(table), "")
    m.AddElement(s_var, table, cap)
    m.Add(b <= cap + (0 if slack is None else slack))


def scope_refusal(E, p) -> Optional[str]:
    if p.use_11h_3off:
        return "11H/3OFF contracts are out of stage-1 scope"
    if not p.strict_off:
        return "non-strict OFF count is out of stage-1 scope"
    if len({a.language for a in p.associates}) > 1 or len(p.language_rules) > 1:
        return "multi-language workbooks need stage 2 (class-aware aggregation)"
    for a in p.associates:
        for v in list(a.preferences) + list(a.fixed_schedule):
            if E.preference_kind(v) in ("leave", "off", "shift"):
                return "leave, hard-OFF or fixed requests need stage 2"
    return None


def candidate_shifts(E, p, max_shifts: int, guide_seconds: float) -> Tuple[List[int], Dict[str, Any]]:
    import copy
    q = copy.copy(p)
    q.aggregate_guide_mixed_durations = True
    g = E.aggregate_pattern_mix_guidance(q, time_limit_sec=guide_seconds)
    totals: Dict[int, int] = {}
    for key, v in (g.get("shift_count_targets") or {}).items():
        s = int(key.split(":")[1])
        totals[s] = totals.get(s, 0) + int(v)
    chosen = sorted(totals, key=lambda s: (-totals[s], s))[:max_shifts]
    return sorted(chosen), {"guide_status": g.get("status"), "guide_shift_totals": totals}


def tour_patterns(p, shifts) -> List[Tuple[int, Tuple[Optional[int], ...]]]:
    """(OFF key, shift index per day or None). Exactly 5 working days."""
    if p.separate_off_days:
        off_sets = [frozenset(c) for c in itertools.combinations(range(7), 2)]
    else:
        off_sets = [frozenset({k, (k + 1) % 7}) for k in range(7)]
    rest_min = int(round(p.rest_gap_hours * 60))
    max_diff = max(1, int(p.max_different_shifts))
    out = []
    for key, off in enumerate(off_sets):
        work = [d for d in range(7) if d not in off]
        for combo in itertools.product(range(len(shifts)), repeat=len(work)):
            if len(set(combo)) > max_diff:
                continue
            row: List[Optional[int]] = [None] * 7
            for d, j in zip(work, combo):
                row[d] = j
            ok = True
            for d in range(7):  # the engine also checks Saturday -> Sunday of the same week (cyclic)
                a, b = row[d], row[(d + 1) % 7]
                if a is not None and b is not None:
                    s1, s2 = shifts[a], shifts[b]
                    if 1440 + s2.start_min - (s1.start_min + s1.duration_min) < rest_min:
                        ok = False
                        break
            if ok:
                out.append((key, tuple(row)))
    return out


def build_seed(E, wb: Path, out_dir: Path, max_shifts: int, time_limit: float, workers: int) -> Dict[str, Any]:
    from ortools.sat.python import cp_model
    t0 = time.time()
    p = E.parse_input(wb)
    why = scope_refusal(E, p)
    if why:
        return {"workbook": wb.name, "status": "REFUSED", "reason": why}
    cand, guide_info = candidate_shifts(E, p, max_shifts, guide_seconds=min(45.0, time_limit / 4))
    if not cand:
        return {"workbook": wb.name, "status": "REFUSED", "reason": "aggregate guide gave no shift counts", **guide_info}
    shifts = [p.shifts[i] for i in cand]
    tours = tour_patterns(p, shifts)
    n = len(p.associates)
    qpi = p.qslots_per_interval
    patterns = E.generate_break_patterns(p)
    m = cp_model.CpModel()
    tv = [m.NewIntVar(0, n, "t%d" % i) for i in range(len(tours))]
    m.Add(sum(tv) == n)
    onfloor = [[] for _ in range(7 * 96)]
    onbreak = [[] for _ in range(7 * 96)]
    zlist = []
    for d in range(7):
        for j, sh in enumerate(shifts):
            users = [tv[i] for i, (_, row) in enumerate(tours) if row[d] == j]
            if not users:
                continue
            legal = [pt for pt in patterns if pt.duration_q == sh.duration_q] or [None]
            zs = []
            for pt in legal:
                z = m.NewIntVar(0, n, "z%d_%d_%s" % (d, j, pt.index if pt else "nb"))
                zs.append(z)
                zlist.append(z)
                broken = set(pt.broken_offsets) if pt else set()
                base = d * 96 + sh.start_min // 15
                for o in range(sh.duration_q):
                    t = base + o
                    if t >= 7 * 96:
                        break
                    (onbreak if o in broken else onfloor)[t].append(z)
            m.Add(sum(zs) == sum(users))
    prior = [len(E.prior_covering_associates(p, q)) for q in range(7 * 96)]
    ratio, absolute = float(p.break_max_concurrent_ratio), int(p.break_max_concurrent_absolute)
    for t in range(7 * 96):
        if onbreak[t]:
            b, f = sum(onbreak[t]), sum(onfloor[t])
            add_break_cap(m, b, b + f + prior[t], ratio, absolute)
    # Phase 1: minimise total shortfall (linear, LP-friendly); zero shortfall
    # means every active interval is at target. Phase 2: maximise intervals at
    # target, hinted with phase 1's solution, for the rest of the budget.
    rows_ = []
    for d in range(7):
        for i in range(p.intervals_per_day):
            if not p.active[d][i]:
                continue
            req = float(p.requirements[d][i] or 0.0)
            eff = 1.0 - float(p.shrinkage[d][i])
            need = p.target_ratio * req * qpi
            if need <= 1e-9 or eff <= 0:
                continue
            coef = int(round(eff * SCALE))
            rhs = int(math.ceil(need * SCALE - 1e-6))
            qs = [d * 96 + i * qpi + k for k in range(qpi)]
            lhs = coef * sum(sum(onfloor[q]) for q in qs) + coef * sum(prior[q] for q in qs)
            rows_.append((lhs, rhs))
    short = []
    for k, (lhs, rhs) in enumerate(rows_):
        sh_ = m.NewIntVar(0, rhs, "s%d" % k)
        m.Add(sh_ >= rhs - lhs)
        short.append(sh_)
    m.Minimize(sum(short))
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = time_limit * 0.5
    sv.parameters.num_workers = workers
    sv.parameters.random_seed = 1
    st1 = sv.Solve(m)
    phase1 = {"status": sv.StatusName(st1), "seconds": round(sv.WallTime(), 1)}
    p1_values = None
    if st1 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        phase1["shortfall_zero_intervals"] = sum(1 for x in short if sv.Value(x) == 0)
        p1_values = [sv.Value(v) for v in tv]
        phase1_zero = [sv.Value(x) == 0 for x in short]
        for v in tv + zlist:
            m.AddHint(v, sv.Value(v))
    m.ClearObjective()
    hits = []
    for k, (lhs, rhs) in enumerate(rows_):
        h = m.NewBoolVar("h%d" % k)
        m.Add(lhs >= rhs).OnlyEnforceIf(h)
        if p1_values is not None:
            m.AddHint(h, 1 if short[k] is not None and phase1_zero[k] else 0)
        hits.append(h)
    m.Maximize(sum(hits))
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = time_limit * 0.5
    sv.parameters.num_workers = workers
    sv.parameters.random_seed = 1
    st = sv.Solve(m)
    row = {"workbook": wb.name, "status": sv.StatusName(st), "candidate_shifts": [p.shifts[i].label for i in cand],
           "tour_types": len(tours), "associates": n, "model_hits": int(sv.ObjectiveValue()) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
           "model_bound": int(math.floor(sv.BestObjectiveBound() + 1e-6)), "solve_seconds": round(sv.WallTime(), 1),
           "phase1": phase1, **guide_info}
    p2_ok = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not p2_ok and p1_values is None:
        return row
    p2_hits = int(sv.ObjectiveValue()) if p2_ok else -1
    p1_hits = phase1.get("shortfall_zero_intervals", -1)
    use_p1 = p1_values is not None and p1_hits >= p2_hits
    row["seed_from_phase"] = 1 if use_p1 else 2
    row["seed_model_hits"] = p1_hits if use_p1 else p2_hits
    counts = p1_values if use_p1 else [sv.Value(v) for v in tv]
    week = []
    for i, c in enumerate(counts):
        week.extend([tours[i][1]] * c)
    labels = [[shifts[j].label if j is not None else "OFF" for j in r] for r in week]
    # Deal tours: carry-in associates first, each to a tour whose Sunday start
    # respects the rest gap after last Saturday's shift.
    by_label = {E.norm(s.label): s for s in p.shifts}
    rest_min = int(round(p.rest_gap_hours * 60))
    pool = list(range(len(labels)))

    def fits(a, t):
        prev = by_label.get(E.norm(p.associates[a].previous_saturday or ""))
        if prev is None or labels[t][0] == "OFF":
            return True
        sun = by_label[E.norm(labels[t][0])]
        return 1440 + sun.start_min - (prev.start_min + prev.duration_min) >= rest_min
    order = sorted(range(n), key=lambda a: 0 if by_label.get(E.norm(p.associates[a].previous_saturday or "")) else 1)
    assign: Dict[int, int] = {}
    unfit = 0
    for a in order:
        t = next((t for t in pool if fits(a, t)), None)
        if t is None:
            t = pool[0]
            unfit += 1
        assign[a] = t
        pool.remove(t)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (wb.stem + "_AGGSEED.xlsx")
    shutil.copy(wb, out)
    import openpyxl
    book = openpyxl.load_workbook(out)
    ws = book["Schedule"]
    hdr_row = next(r for r in range(1, 6) if any(str(ws.cell(r, c).value or "").strip() == "Sun" for c in range(1, 20)))
    col = {str(ws.cell(hdr_row, c).value or "").strip(): c for c in range(1, 30)}
    name_col = col.get("SF Name") or col.get("Name")
    row_of = {}
    for r in range(hdr_row + 1, ws.max_row + 1):
        v = ws.cell(r, name_col).value
        if v:
            row_of[E.norm(str(v))] = r
    for a, t in assign.items():
        r = row_of[E.norm(p.associates[a].name)]
        for d, dn in enumerate(DAY_COLS):
            ws.cell(r, col[dn]).value = labels[t][d]
    book.save(out)
    seed = E.load_seed_skeleton(E.parse_input(out), out, "input_schedule_seed")
    row.update({"seed_workbook": out.name, "carry_in_rest_conflicts": unfit,
                "seed_valid_cells": seed.diagnostics.get("valid_seed_cells") if seed else 0,
                "seed_invalid_cells": seed.diagnostics.get("invalid_seed_cells") if seed else None,
                "total_seconds": round(time.time() - t0, 1)})
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-shifts", type=int, default=10)
    ap.add_argument("--time-limit", type=float, default=300)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("workbooks", nargs="+", type=Path)
    a = ap.parse_args()
    E = S.load_engine(a.engine)
    report = {}
    for wb in a.workbooks:
        row = build_seed(E, wb, a.out_dir, a.max_shifts, a.time_limit, a.workers)
        report[wb.name] = row
        print(json.dumps(row, default=str), flush=True)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "AGGREGATE_SEED_REPORT.json").write_text(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
