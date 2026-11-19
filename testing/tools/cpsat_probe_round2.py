#!/usr/bin/env python3
"""Round 2: probe the rules the first pass could not reach.

Same binding-constraint method. Each rule is made genuinely impossible through
a route the contract actually supports, then released through the switch that
claims to control it.
"""
import argparse, importlib.util, io, sys, time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--stage1-input", type=Path, required=True)
    ap.add_argument("--break-input", type=Path, required=True)
    ap.add_argument("--time-limit", type=float, default=10.0)
    ap.add_argument("--width", type=int, default=60)
    a = ap.parse_args()
    sys.path.insert(0, str(a.engine.parent))
    spec = importlib.util.spec_from_file_location("E", a.engine)
    E = importlib.util.module_from_spec(spec); sys.modules["E"] = E
    spec.loader.exec_module(E)

    def sk_solve(inp, mutate=None, hard=None, **kw):
        p = E.parse_input(inp)
        if mutate:
            r = mutate(p)
            if r == "SKIP":
                return "SKIP", p
        s = E.build_skeleton(p, E.skeleton_profiles()[0], hard or E.HardConfig(),
                             a.time_limit, 1, io.StringIO(), random_seed=17, **kw)
        return s.cp_status, p

    print("=" * 92)
    print("ROUND 2 — the rules the first pass could not reach")
    print("=" * 92)
    base, bp = sk_solve(a.stage1_input)
    print("\npositive control (%s): %s\n" % (a.stage1_input.name, base))
    if base not in ("OPTIMAL", "FEASIBLE"):
        return 2

    active = sum(1 for d in range(7) for i in range(bp.intervals_per_day) if bp.active[d][i])

    # ---- constructions -----------------------------------------------------
    def wb_floor_impossible(p):
        """Next-Sunday floor needs more staff than the roster can supply."""
        for i in range(p.intervals_per_day):
            if p.active[0][i]:
                p.requirements[0][i] = float(len(p.associates) * 50)

    def blank_vs_fixed(p):
        """A blank interval must carry zero staff, while a fixed request works it."""
        if p.blank_requirement_mode != "hard_no_current_week_staffing":
            return "SKIP"
        p.fixed_enabled = True
        for i in range(p.intervals_per_day):
            p.active[1][i] = False
        p.associates[0].fixed_schedule = ["", p.shifts[0].label] + [""] * 5

    def blank_allow(p):
        blank_vs_fixed(p)
        p.blank_requirement_mode = "allow"

    def nesting_mixed_leave(p):
        p.fixed_enabled = True
        p.associates[0].preferences = ["Leave"] + [""] * 6
        p.associates[1].preferences = [""] * 7
        p.associates[0].nesting_group = "G"
        p.associates[1].nesting_group = "G"

    def hard_floor_impossible(p):
        p.floor_mode = "hard"
        p.hard_floor_ratio = 50.0

    rows = []

    # 1. week-boundary carry-out
    on, _ = sk_solve(a.stage1_input, wb_floor_impossible)
    off, _ = sk_solve(a.stage1_input, wb_floor_impossible,
                      E.HardConfig(week_boundary=False))
    rows.append(("week-boundary carry-out floor", on, off, "hard.week_boundary"))

    # 2. blank-interval staffing
    on, _ = sk_solve(a.stage1_input, blank_vs_fixed)
    off, _ = sk_solve(a.stage1_input, blank_allow)
    rows.append(("blank interval must carry no staff", on, off,
                 "blank_requirement_mode='allow'"))

    # 3. nesting group equality
    on, _ = sk_solve(a.stage1_input, nesting_mixed_leave)
    off, _ = sk_solve(a.stage1_input, nesting_mixed_leave, E.HardConfig(fixed=False))
    rows.append(("nesting group shares OFF/leave", on, off, "hard.fixed"))

    # 4. hard floor mode
    on, _ = sk_solve(a.stage1_input, hard_floor_impossible)
    off, _ = sk_solve(a.stage1_input, hard_floor_impossible,
                      E.HardConfig(hard_floor=False))
    rows.append(("hard floor solver constraint", on, off, "hard.hard_floor"))

    # 5. explicit tier lock -- every active interval at 100%
    on, _ = sk_solve(a.stage1_input, None, None, minimum_tier_hits={100: active})
    off, _ = sk_solve(a.stage1_input, None, None, minimum_tier_hits=None)
    rows.append(("minimum tier lock binds", on, off, "minimum_tier_hits=None"))

    # 6. tier lock asking for MORE than exists -- must clamp, not fail
    huge, _ = sk_solve(a.stage1_input, None, None,
                       minimum_tier_hits={100: active * 100})
    print("%-38s %-14s %-14s %s" % ("rule", "rule ON", "rule OFF", "released by"))
    print("-" * 92)
    bad = 0
    for name, on, off, switch in rows:
        if on == "SKIP":
            print("%-38s %-14s %-14s %s" % (name, "-", "-", "skipped")); continue
        enforced = on in ("INFEASIBLE", "MODEL_INVALID")
        released = off in ("OPTIMAL", "FEASIBLE")
        verdict = ("ENFORCED, switch controls it" if enforced and released
                   else "*** NOT ENFORCED ***" if not enforced
                   else "enforced, switch did not release")
        if not (enforced and released):
            bad += 1
        print("%-38s %-14s %-14s %-28s %s" % (name, on, off, switch, verdict))

    print("\ntier lock asking for %dx more than exists -> %s  (%s)"
          % (100, huge,
             "clamped, as the code intends" if huge in ("OPTIMAL", "FEASIBLE")
             else "NOT clamped"))
    print("\n%d rule(s) did not behave as the contract claims" % bad)

    # ---- break concurrency, with a cap that is legal and binding -----------
    print("\n" + "=" * 92)
    print("break concurrency — legal cap made binding (not forced to zero)")
    print("=" * 92)
    p = E.parse_input(a.break_input)
    sk = E.build_skeleton(p, E.skeleton_profiles()[0], E.HardConfig(),
                          a.time_limit, 1, io.StringIO(), random_seed=17)
    print("skeleton: %s" % sk.cp_status)

    def br(mode, absolute):
        q = E.parse_input(a.break_input)
        q.break_concurrency_gate_mode = mode
        q.break_max_concurrent_absolute = absolute
        q.break_max_concurrent_ratio = 0.01
        s = E.solve_breaks(q, sk, a.width, False, a.time_limit, 1, io.StringIO(),
                           random_seed=17)
        return s.cp_status

    ctrl = br("warn", 99)
    tight_fail = br("fail", 1)
    tight_warn = br("warn", 1)
    print("  control (cap 99, warn)          : %s" % ctrl)
    print("  cap 1, mode=fail                : %s" % tight_fail)
    print("  cap 1, mode=warn                : %s" % tight_warn)
    if tight_fail == "INFEASIBLE" and tight_warn in ("OPTIMAL", "FEASIBLE"):
        print("  -> ENFORCED: fail forbids, warn permits and penalises")
    elif tight_fail in ("OPTIMAL", "FEASIBLE"):
        print("  -> cap 1 was satisfiable; not a binding probe")
    else:
        print("  -> inconclusive (%s / %s)" % (tight_fail, tight_warn))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
