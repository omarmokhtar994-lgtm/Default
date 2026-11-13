#!/usr/bin/env python3
"""Does the CP-SAT model actually encode each business rule?

Reading the constraint construction proves a line exists. It does not prove the
constraint BINDS, nor that the flag which claims to control it does.

Method -- binding-constraint probing. For each rule:

  positive control : the base contract must solve            -> FEASIBLE
  binding probe    : make the rule impossible to satisfy     -> INFEASIBLE
  relaxation ctrl  : same contract, rule switched off        -> FEASIBLE

All three together prove the constraint is present, that it binds, and that the
HardConfig switch controls exactly it. A binding probe that comes back FEASIBLE
means the rule is NOT enforced -- that is the defect this looks for.
"""
import argparse
import importlib.util
import io
import sys
import time
from pathlib import Path


def load_engine(path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("E", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["E"] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--time-limit", type=float, default=8.0)
    args = ap.parse_args()

    E = load_engine(args.engine)
    base = E.parse_input(args.input)
    A, D = len(base.associates), 7
    print("base: %s  associates=%d shifts=%d active=%d rest=%.1fh\n"
          % (args.input.name, A, len(base.shifts), args.time_limit and
             sum(1 for d in range(D) for i in range(base.intervals_per_day)
                 if base.active[d][i]), base.rest_gap_hours))

    def solve(mutate=None, hard=None):
        p = E.parse_input(args.input)
        if mutate:
            mutate(p)
        log = io.StringIO()
        t = time.time()
        sk = E.build_skeleton(p, E.skeleton_profiles()[0], hard or E.HardConfig(),
                              args.time_limit, 1, log, random_seed=17)
        return sk.cp_status, time.time() - t

    # ---- rule constructions -------------------------------------------------
    def all_leave_day0(p):
        for a in p.associates:
            a.preferences = ["Leave"] + [""] * 6

    def all_off_day0(p):
        for a in p.associates:
            a.preferences = ["OFF"] + [""] * 6

    def three_off_for_one(p):
        p.associates[0].preferences = ["OFF", "OFF", "OFF"] + [""] * 4

    def no_shift_variety(p):
        p.max_different_shifts = 0

    def impossible_rest(p):
        p.rest_gap_hours = 40.0

    def impossible_language(p):
        if not p.language_rules:
            return "SKIP"
        for r in p.language_rules:
            r.minimum = len(p.associates) + 5

    def impossible_opening(p):
        p.opening_guard_enabled = True
        p.opening_minimum = len(p.associates)
        p.opening_intervals = 2
        p.associates[0].preferences = ["Leave"] + [""] * 6

    def unknown_fixed_shift(p):
        """A WELL-FORMED time that is not one of the contract's shifts.

        My first attempt used "99:99 - 99:99", which preference_kind classes as
        "other", so the legality check at 5525 (guarded by kind == "shift") was
        never reached and the probe was invalid. That miss is itself a finding
        and is probed separately below.
        """
        p.fixed_enabled = True
        labels = {E.norm(s.label) for s in p.shifts}
        for cand in ("03:00 - 12:00", "02:00 - 11:00", "01:00 - 10:00"):
            if E.norm(cand) not in labels:
                p.associates[0].fixed_schedule = [cand] + [""] * 6
                return
        raise AssertionError("no well-formed non-contract shift available")

    def malformed_fixed_shift(p):
        """Unparseable text in a fixed-request cell."""
        p.fixed_enabled = True
        p.associates[0].fixed_schedule = ["Morning"] + [""] * 6

    RULES = [
        ("leave blocks work",            all_leave_day0,     dict(leave=False)),
        ("hard OFF blocks work",         all_off_day0,       dict(hard_off=False)),
        ("strict OFF count == 2",        three_off_for_one,  dict(strict_off=False)),
        ("max shift variety",            no_shift_variety,   dict(max_shift_variety=False)),
        ("rest gap between days",        impossible_rest,    dict(rest=False)),
        ("language minimum per interval", impossible_language, dict(language=False)),
        ("opening minimum FTE",          impossible_opening, dict(opening=False)),
        ("fixed shift must be legal",    unknown_fixed_shift, dict(fixed=False)),
        ("malformed fixed shift rejected", malformed_fixed_shift, dict(fixed=False)),
    ]

    status, secs = solve()
    print("%-34s %-14s %5.1fs   %s" % ("POSITIVE CONTROL (base)", status, secs,
          "ok" if status in ("OPTIMAL", "FEASIBLE") else "*** base must solve ***"))
    if status not in ("OPTIMAL", "FEASIBLE"):
        return 2
    print()
    print("%-34s %-14s %-14s %s" % ("rule", "rule ON", "rule OFF", "verdict"))
    print("-" * 84)
    bad = 0
    for name, mutate, relax in RULES:
        probe = E.parse_input(args.input)
        if mutate(probe) == "SKIP":
            print("%-34s %-14s %-14s %s" % (name, "-", "-", "skipped (not in this contract)"))
            continue
        on, _ = solve(mutate)
        off, _ = solve(mutate, E.HardConfig(**relax))
        enforced = on in ("INFEASIBLE", "MODEL_INVALID")
        released = off in ("OPTIMAL", "FEASIBLE")
        if enforced and released:
            verdict = "ENFORCED, and the switch controls it"
        elif not enforced:
            verdict = "*** NOT ENFORCED -- model accepted a violation ***"
            bad += 1
        else:
            verdict = "enforced, but the switch did not release it"
            bad += 1
        print("%-34s %-14s %-14s %s" % (name, on, off, verdict))
    print("\n%d rule(s) did not behave as the contract claims" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
