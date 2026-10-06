#!/usr/bin/env python3
"""Upper bound on the engine's headline metric (intervals at target after breaks)
for a real program workbook. Report-only: changes nothing in the engine.

Why: the public benchmark showed the engine far from a proven optimum on an
instance with 141 shift options; real programs have 1-24. Whether real
programs have headroom was unknown: only AE_AR_B2B had a proven bound.

What is modelled (from the engine's own parse of the workbook, i.e. the
input as the engine reads it, never its search):
  * requirements, shrinkage, active intervals, target ratio, interval length;
  * the shift library and the engine's own legal break patterns per shift;
  * last Saturday's carry-in coverage (fixed input);
  * the metric exactly as calculate_metrics defines it: an active interval is
    hit when mean over its quarters of on-floor heads x (1 - shrinkage)
    >= target x requirement.

What is deliberately left out, so the result is an UPPER bound on any
schedule the engine can publish: language minimums, coverage split, rest
gaps, shift-variety limits, preferences, leave, fixed requests, opening
guard, overage caps, break-concurrency caps, the blank-interval rule, and
which associate works which day beyond "at most N per day and at most 5N
shifts in the week". Any engine schedule is feasible here, so its
after_target <= this model's optimum <= the solver's proven bound.

Rounding is conservative in the bound's favour (requirements rounded down by
1e-4 FTE), so it can only overstate, never understate, the ceiling.

    python3 tools/real_program_bounds.py --engine engine/_tools/l632_universal_scheduler.py \
        --out bounds.json WORKBOOK.xlsx [...]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_synthetic_suite as S  # noqa: E402

SCALE = 10_000


def bound_for(E, wb: Path, time_limit: float, workers: int, days_per_week: int) -> dict:
    from ortools.sat.python import cp_model
    t0 = time.time()
    p = E.parse_input(wb)
    qpi = p.qslots_per_interval
    n = len(p.associates)
    patterns = E.generate_break_patterns(p)
    m = cp_model.CpModel()
    onfloor = [[] for _ in range(7 * 96)]  # current-week quarters only
    per_day = [[] for _ in range(7)]
    for d in range(7):
        for sh in p.shifts:
            legal = [pt for pt in patterns if pt.duration_q == sh.duration_q] or [None]
            for pt in legal:
                y = m.NewIntVar(0, n, "y_%d_%d_%s" % (d, sh.index, pt.index if pt else "nb"))
                per_day[d].append(y)
                broken = set(pt.broken_offsets) if pt else set()
                base = d * 96 + sh.start_min // 15
                for o in range(sh.duration_q):
                    t = base + o
                    if t < 7 * 96 and o not in broken:
                        onfloor[t].append(y)
    for d in range(7):
        m.Add(sum(per_day[d]) <= n)
    m.Add(sum(sum(v) for v in per_day) <= days_per_week * n)
    prior = [len(E.prior_covering_associates(p, q)) for q in range(7 * 96)]
    hits, active = [], 0
    for d in range(7):
        for i in range(p.intervals_per_day):
            if not p.active[d][i]:
                continue
            active += 1
            req = float(p.requirements[d][i] or 0.0)
            eff = 1.0 - float(p.shrinkage[d][i])
            need = p.target_ratio * req * qpi  # sum over quarters of heads*eff must reach this
            if need <= 1e-9:
                hits.append(1)
                continue
            if eff <= 0:
                continue  # unreachable: no head counts
            coef = int(round(eff * SCALE))
            rhs = int(math.floor((need - 1e-4) * SCALE))
            qs = [d * 96 + i * qpi + k for k in range(qpi)]
            lhs = sum(coef * prior[q] for q in qs)
            h = m.NewBoolVar("h_%d_%d" % (d, i))
            m.Add(coef * sum(sum(onfloor[q]) for q in qs) + lhs >= rhs).OnlyEnforceIf(h)
            hits.append(h)
    m.Maximize(sum(hits))
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = time_limit
    sv.parameters.num_workers = workers
    sv.parameters.random_seed = 1
    st = sv.Solve(m)
    return {
        "workbook": wb.name, "associates": n, "shifts": len(p.shifts), "interval_minutes": p.interval_minutes,
        "target_ratio": p.target_ratio, "active_intervals": active, "status": sv.StatusName(st),
        "best_feasible_hits": int(sv.ObjectiveValue()) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "upper_bound": int(math.floor(sv.BestObjectiveBound() + 1e-6)),
        "solve_seconds": round(sv.WallTime(), 1), "total_seconds": round(time.time() - t0, 1),
        "relaxed": "languages, coverage split, rest, variety, preferences, leave, fixed, opening, overage caps, "
                   "break-concurrency caps, blank rule, per-associate day assignment",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--time-limit", type=float, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--days-per-week", type=int, default=5)
    ap.add_argument("workbooks", nargs="+", type=Path)
    a = ap.parse_args()
    E = S.load_engine(a.engine)
    out = json.loads(a.out.read_text()) if a.out.exists() else {}
    for wb in a.workbooks:
        row = bound_for(E, wb, a.time_limit, a.workers, a.days_per_week)
        out[wb.name] = row
        print(json.dumps(row), flush=True)
        a.out.write_text(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
