#!/usr/bin/env python3
"""Stage-2 companion to cpsat_constraint_probe: do the BREAK rules bind?

Same method. Solve a skeleton once, then for each break rule make it impossible
and check the break model refuses, and that the contract switch releases it.
"""
import argparse, importlib.util, io, sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--time-limit", type=float, default=8.0)
    ap.add_argument("--width", type=int, default=60)
    args = ap.parse_args()
    sys.path.insert(0, str(args.engine.parent))
    spec = importlib.util.spec_from_file_location("E", args.engine)
    E = importlib.util.module_from_spec(spec); sys.modules["E"] = E
    spec.loader.exec_module(E)

    base = E.parse_input(args.input)
    log = io.StringIO()
    sk = E.build_skeleton(base, E.skeleton_profiles()[0], E.HardConfig(),
                          args.time_limit, 1, log, random_seed=17)
    print("skeleton for the break probes: %s" % sk.cp_status)
    if sk.cp_status not in ("OPTIMAL", "FEASIBLE"):
        return 2

    def breaks(mutate=None, allow_exceptions=False):
        p = E.parse_input(args.input)
        if mutate:
            mutate(p)
        out = io.StringIO()
        s = E.solve_breaks(p, sk, args.width, allow_exceptions, args.time_limit, 1, out,
                           random_seed=17)
        return s.cp_status

    status = breaks()
    print("%-38s %-14s %s\n" % ("POSITIVE CONTROL (base breaks)", status,
          "ok" if status in ("OPTIMAL", "FEASIBLE") else "*** must solve ***"))
    if status not in ("OPTIMAL", "FEASIBLE"):
        return 2

    def concurrency_zero_fail(p):
        p.break_concurrency_gate_mode = "fail"
        p.break_max_concurrent_ratio = 0.0
        p.break_max_concurrent_absolute = 0

    def concurrency_zero_warn(p):
        p.break_concurrency_gate_mode = "warn"
        p.break_max_concurrent_ratio = 0.0
        p.break_max_concurrent_absolute = 0

    def language_impossible(p):
        if not p.language_rules:
            return "SKIP"
        for r in p.language_rules:
            r.minimum = len(p.associates) + 5

    print("%-38s %-14s %s" % ("break rule", "status", "verdict"))
    print("-" * 82)
    bad = 0

    rows = [
        ("break concurrency cap, mode=fail", concurrency_zero_fail, "INFEASIBLE",
         "a zero cap must make every break placement illegal"),
        ("break concurrency cap, mode=warn", concurrency_zero_warn, "FEASIBLE",
         "warn mode must penalise, never forbid"),
        ("language minimum survives breaks", language_impossible, "INFEASIBLE",
         "breaks must not be allowed to drop a language below its minimum"),
    ]
    for name, mutate, expect, why in rows:
        probe = E.parse_input(args.input)
        if mutate(probe) == "SKIP":
            print("%-38s %-14s %s" % (name, "-", "skipped (not in this contract)"))
            continue
        got = breaks(mutate)
        ok = (got == expect) if expect == "INFEASIBLE" else (got in ("OPTIMAL", "FEASIBLE"))
        if not ok:
            bad += 1
        print("%-38s %-14s %s" % (name, got, "as expected -- " + why if ok
                                  else "*** UNEXPECTED (wanted %s) -- %s ***" % (expect, why)))
    print("\n%d break rule(s) did not behave as the contract claims" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
