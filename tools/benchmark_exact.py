#!/usr/bin/env python3
"""Exact reference solutions for the published benchmarks, independent of the engine.

Two textbook instances with published optima, both re-derived here by an exact
CP-SAT model written from the problem statements -- none of the engine's code
is used -- so the published number is checked, not copied:

  WINSTON  post office (Winston, Operations Research, Ch. 3): daily need
           Mon 17, Tue 13, Wed 15, Thu 19, Fri 14, Sat 16, Sun 11; each
           employee works 5 consecutive days then 2 off.
           Published optimum: 23 employees (LP bound 22 1/3).
  UNION    Union Airways (Hillier & Lieberman, Intro. to OR, Sec. 3.4): agents
           needed per 2-hour period 48/79/65/87/64/73/82/43/52 (06:00-24:00)
           and 15 (00:00-06:00); shifts 06-14, 08-16, 12-20, 16-24, 22-06 at
           $170/160/175/180/195. Published optimum: $30,610 with
           (48, 31, 39, 43, 15) agents per shift.

The engine does not minimise cost or headcount: it takes a fixed roster and
maximises intervals that meet demand. So each benchmark is also solved in the
engine's terms: for a roster of N, the most (day, hour) intervals that can be
fully covered. `relaxed` uses only the benchmark's own rules (days-off pattern,
one shift a day); `engine_rules` adds the engine's hard rules this translation
enables (12h rest between consecutive days, at most 2 different shifts a week).
A relaxed optimum bounds anything the engine can reach; a matching
engine_rules plan shows the bound is attainable.
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List, Optional, Sequence, Tuple

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# ------------------------------------------------------------------ WINSTON
WINSTON_DAILY = {"Mon": 17, "Tue": 13, "Wed": 15, "Thu": 19, "Fri": 14, "Sat": 16, "Sun": 11}


def winston_min_employees() -> Tuple[int, float, List[int]]:
    """x_d = employees starting their 5-day block on day d. Returns (IP, LP, x)."""
    req = [WINSTON_DAILY[d] for d in DAYS]
    out = {}
    for integer in (True, False):
        s = pywraplp.Solver.CreateSolver("CBC" if integer else "GLOP")
        x = [s.IntVar(0, 100, "x%d" % d) if integer else s.NumVar(0, 100, "x%d" % d) for d in range(7)]
        for d in range(7):
            # Working on d: started on d, d-1, ..., d-4.
            s.Add(sum(x[(d - k) % 7] for k in range(5)) >= req[d])
        s.Minimize(sum(x))
        assert s.Solve() == pywraplp.Solver.OPTIMAL
        out[integer] = (s.Objective().Value(), [v.solution_value() for v in x])
    return int(round(out[True][0])), out[False][0], [int(round(v)) for v in out[True][1]]


# -------------------------------------------------------------------- UNION
UNION_PERIODS = [  # (start hour, end hour, agents)
    (6, 8, 48), (8, 10, 79), (10, 12, 65), (12, 14, 87), (14, 16, 64),
    (16, 18, 73), (18, 20, 82), (20, 22, 43), (22, 24, 52), (0, 6, 15)]
UNION_SHIFTS = [(6, 170), (8, 160), (12, 175), (16, 180), (22, 195)]   # start hour, $ ; 8h each


def union_hourly() -> List[int]:
    h = [0] * 24
    for a, b, n in UNION_PERIODS:
        for x in range(a, b):
            h[x] = n
    return h


def union_min_cost() -> Tuple[int, List[int], int]:
    s = pywraplp.Solver.CreateSolver("CBC")
    x = [s.IntVar(0, 500, "x%d" % k) for k in range(5)]
    need = union_hourly()
    for hour in range(24):
        s.Add(sum(x[k] for k, (st, _) in enumerate(UNION_SHIFTS) if (hour - st) % 24 < 8) >= need[hour])
    s.Minimize(sum(c * x[k] for k, (_, c) in enumerate(UNION_SHIFTS)))
    assert s.Solve() == pywraplp.Solver.OPTIMAL
    xs = [int(round(v.solution_value())) for v in x]
    # Minimum daily HEADCOUNT (the engine's roster is headcount, not cost).
    s2 = pywraplp.Solver.CreateSolver("CBC")
    y = [s2.IntVar(0, 500, "y%d" % k) for k in range(5)]
    for hour in range(24):
        s2.Add(sum(y[k] for k, (st, _) in enumerate(UNION_SHIFTS) if (hour - st) % 24 < 8) >= need[hour])
    s2.Minimize(sum(y))
    assert s2.Solve() == pywraplp.Solver.OPTIMAL
    return int(round(s.Objective().Value())), xs, int(round(s2.Objective().Value()))


# ------------------------------------------------- weekly roster, engine metric
def weekly_max_hits(n: int, starts_min: Sequence[int], shift_min: int,
                    demand: List[List[int]], engine_rules: bool, rest_hours: int = 12,
                    max_variety: int = 2, time_limit: float = 120.0,
                    all_hit: bool = False) -> Dict:
    """Max (day, hour) intervals with headcount >= demand, cyclic week.

    demand[d][h] in whole people (shrinkage 0, no breaks). A shift starting on
    day d at minute m covers hour slots m//60 .. of day d and spills into d+1
    (cyclic: Saturday night into Sunday, the steady-state week).
    """
    m = cp_model.CpModel()
    S = len(starts_min)
    w = {(a, d, s): m.NewBoolVar("w%d_%d_%d" % (a, d, s)) for a in range(n) for d in range(7) for s in range(S)}
    for a in range(n):
        off = []
        for d in range(7):
            m.Add(sum(w[a, d, s] for s in range(S)) <= 1)
            o = m.NewBoolVar("off%d_%d" % (a, d))
            m.Add(o == 1 - sum(w[a, d, s] for s in range(S)))
            off.append(o)
        m.Add(sum(off) == 2)
        pairs = []
        for d in range(7):
            p = m.NewBoolVar("pair%d_%d" % (a, d))
            m.AddImplication(p, off[d]); m.AddImplication(p, off[(d + 1) % 7])
            pairs.append(p)
        m.Add(sum(pairs) >= 1)
        if engine_rules:
            for d in range(7):
                for s in range(S):
                    end = starts_min[s] + shift_min
                    for t in range(S):
                        gap = 1440 + starts_min[t] - end
                        if gap < rest_hours * 60:
                            m.Add(w[a, d, s] + w[a, (d + 1) % 7, t] <= 1)
            y = [m.NewBoolVar("y%d_%d" % (a, s)) for s in range(S)]
            for s in range(S):
                for d in range(7):
                    m.AddImplication(w[a, d, s], y[s])
            m.Add(sum(y) <= max_variety)
    hits = []
    for d in range(7):
        for h in range(24):
            if not demand[d][h]:
                continue
            cover = []
            for sd in range(7):
                for s in range(S):
                    rel = (d - sd) % 7 * 1440 + h * 60 - starts_min[s]
                    if 0 <= rel < shift_min:
                        cover.extend(w[a, sd, s] for a in range(n))
            hit = m.NewBoolVar("hit%d_%d" % (d, h))
            m.Add(sum(cover) >= demand[d][h]).OnlyEnforceIf(hit)
            hits.append(hit)
    if all_hit:
        for h in hits:
            m.Add(h == 1)
    m.Maximize(sum(hits))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 4
    st = solver.Solve(m)
    res = {"n": n, "engine_rules": engine_rules, "status": solver.StatusName(st),
           "active": len(hits)}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res["hits"] = int(round(solver.ObjectiveValue()))
        res["bound"] = int(round(solver.BestObjectiveBound()))
        plan = []
        for a in range(n):
            row = []
            for d in range(7):
                ss = [s for s in range(S) if solver.Value(w[a, d, s])]
                row.append(ss[0] if ss else None)
            plan.append(row)
        res["plan"] = plan
    return res


def winston_demand() -> List[List[int]]:
    """09:00-17:00 each day at that day's requirement (one 8h shift)."""
    return [[WINSTON_DAILY[DAYS[d]] if 9 <= h < 17 else 0 for h in range(24)] for d in range(7)]


def union_demand() -> List[List[int]]:
    h = union_hourly()
    return [list(h) for _ in range(7)]


def main() -> int:
    out: Dict = {}
    ip, lp, x = winston_min_employees()
    out["winston_published_check"] = {"ip_min_employees": ip, "lp_bound": round(lp, 4),
                                      "starts_by_day": dict(zip(DAYS, x)),
                                      "published": 23, "agrees": ip == 23}
    print("WINSTON  IP min employees=%d  LP=%.4f  published=23" % (ip, lp))
    cost, xs, heads = union_min_cost()
    out["union_published_check"] = {"min_cost": cost, "agents_per_shift": xs, "published_cost": 30610,
                                    "published_agents": [48, 31, 39, 43, 15],
                                    "agrees": cost == 30610, "min_daily_headcount": heads}
    print("UNION    min cost=%d agents=%s published=30610  min daily headcount=%d" % (cost, xs, heads))

    wd = winston_demand()
    for n in (23, 22):
        for rules in (False, True):
            r = weekly_max_hits(n, [9 * 60], 480, wd, rules, time_limit=60)
            print("WINSTON  N=%d engine_rules=%s  %s hits=%s/%s bound=%s" % (n, rules, r["status"], r.get("hits"), r["active"], r.get("bound")))
            out["winston_N%d_%s" % (n, "engine" if rules else "relaxed")] = r

    ud = union_demand()
    starts = [st * 60 for st, _ in UNION_SHIFTS]
    lower = -(-heads * 7 // 5)
    out["union_weekly_lower_bound"] = lower
    print("UNION    weekly roster lower bound ceil(%d*7/5)=%d" % (heads, lower))
    found = None
    for n in range(lower, lower + 8):
        r = weekly_max_hits(n, starts, 480, ud, True, time_limit=180, all_hit=True)
        print("UNION    N=%d engine_rules all-hit: %s" % (n, r["status"]))
        if r["status"] in ("OPTIMAL", "FEASIBLE"):
            found = r
            break
    out["union_min_weekly_roster_engine_rules"] = found["n"] if found else None
    out["union_N_plan"] = found
    if found:
        n0 = found["n"]
        for rules in (False, True):
            r = weekly_max_hits(n0 - 1, starts, 480, ud, rules, time_limit=300)
            print("UNION    N=%d engine_rules=%s  %s hits=%s/%s bound=%s" % (n0 - 1, rules, r["status"], r.get("hits"), r["active"], r.get("bound")))
            out["union_N%d_%s" % (n0 - 1, "engine" if rules else "relaxed")] = r
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "benchmark_exact.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
