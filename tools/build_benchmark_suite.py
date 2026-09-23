#!/usr/bin/env python3
"""Translate the two published benchmarks into engine workbooks, with exact expectations.

Run after `benchmark_exact.py`, whose JSON holds the independently re-derived
optima and plans. Translation, stated so nothing is hidden:

  * shrinkage 0 and no breaks: neither textbook problem has either;
  * demand is whole people per hour; the engine's Target is 100%, so an
    interval is "hit" exactly when headcount >= the textbook requirement;
  * WINSTON: one 8h shift 09:00-17:00, the day's requirement at every hour;
  * UNION: the five 8h shifts, the hourly requirement every day. The problem is
    daily; the engine plans a week in which each associate works 5 consecutive
    days, so the roster is the smallest weekly one the exact model finds;
  * UNION previous Saturday: the engine needs last Saturday's shifts for Sunday
    carry-in and rest. It is taken from the exact plan's own Saturday (the
    steady-state week). That tells the engine who worked last Saturday -- data
    it always has in production -- not what to schedule this week.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_synthetic_suite as S  # noqa: E402
import benchmark_exact as X  # noqa: E402


def base_case(cid, n, starts_min, purpose):
    names, langs = S.english(n)
    return dict(id=cid, tier="benchmark", associates=n, shift_starts=starts_min, shift_minutes=480,
                shrinkage=0.0, interval_minutes=60, names=names, languages=langs,
                language_rules=S.ENGLISH_RULE, purpose=purpose,
                settings={"Short Break Count": 0, "Lunch Count": 0,
                          "Allowed Shift Durations Hours": "8"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--template", type=Path, required=True)
    ap.add_argument("--exact", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    E = S.load_engine(a.engine)
    ex = json.load(open(a.exact))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    def emit(case, demand, expected, source):
        out = a.out_dir / (case["id"] + ".xlsx")
        S.build_workbook(a.template, out, case, E, [[v if v else None for v in row] for row in demand])
        parsed = E.parse_input(out)
        contract = E.validate_input_contract(parsed)
        active = sum(1 for d in range(7) for i in range(24) if parsed.active[d][i])
        manifest.append({"id": case["id"], "tier": "benchmark", "workbook": out.name,
                         "purpose": case["purpose"], "associates": case["associates"],
                         "source": source, "contract_status": contract.get("status"),
                         "contract_failures": [f.get("code") for f in contract.get("failures", [])],
                         "certificate": {"active_intervals": active}, "expected": expected})
        print("%-28s N=%-4d active=%-4d contract=%s expected=%s" % (case["id"], case["associates"], active,
              contract.get("status"), expected.get("optimum_after_target")))

    src_w = ("Winston, Operations Research: Applications and Algorithms, Ch. 3 (post office); "
             "published optimum 23 employees, re-derived: IP %d, LP %.4f"
             % (ex["winston_published_check"]["ip_min_employees"], ex["winston_published_check"]["lp_bound"]))
    wd = X.winston_demand()
    for n in (23, 22):
        best = ex["winston_N%d_relaxed" % n]
        assert best["status"] == "OPTIMAL", best["status"]
        case = base_case("BENCH_WINSTON_N%d" % n, n, [9 * 60],
                         "Post office days-off problem, %d employees (published minimum is 23)." % n)
        emit(case, wd, {"optimum_after_target": best["hits"], "optimum_before_target": best["hits"],
                        "optimum_proof": "exact CP-SAT, OPTIMAL, benchmark rules only (a relaxation of the engine's)"},
             src_w)

    src_u = ("Hillier & Lieberman, Introduction to Operations Research, Sec. 3.4 (Union Airways); "
             "published optimum $30,610 with (48,31,39,43,15), re-derived: $%d %s; min daily headcount %d"
             % (ex["union_published_check"]["min_cost"], ex["union_published_check"]["agents_per_shift"],
                ex["union_published_check"]["min_daily_headcount"]))
    ud = X.union_demand()
    starts = [st * 60 for st, _ in X.UNION_SHIFTS]
    n0 = ex["union_min_weekly_roster_engine_rules"]
    for n, key in ((n0, "union_N_plan"), (n0 - 1, "union_N%d_engine" % (n0 - 1))):
        res = ex[key]
        relaxed = ex.get("union_N%d_relaxed" % n)
        case = base_case("BENCH_UNION_N%d" % n, n, starts,
                         "Union Airways shift problem as a weekly roster of %d (smallest full-cover roster is %d)." % (n, n0))
        # Previous Saturday = the exact plan's Saturday (steady state).
        plan = res["plan"]
        prev = {}
        for a_, row in enumerate(plan):
            s_ = row[6]
            if s_ is not None:
                st = starts[s_]
                prev[a_] = "%s - %s" % (S.hhmm(st), S.hhmm(st + 480))
        case["previous_saturday"] = prev
        if n == n0:
            exp = {"optimum_after_target": res["active"], "optimum_before_target": res["active"],
                   "optimum_proof": "exact CP-SAT plan covering every interval under the engine's rest/variety rules"}
        else:
            exp = {"optimum_after_target": res["hits"],
                   "upper_bound": relaxed["bound"] if relaxed else None,
                   "optimum_proof": "exact CP-SAT (%s, bound %s) under engine rules; relaxed bound %s"
                                    % (res["status"], res["bound"], relaxed and relaxed["bound"])}
        emit(case, ud, exp, src_u)
    (a.out_dir / "cases.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
