"""Break-capacity advisory on the metric's averaging; Stage-1 basis on a starved budget.

Both found by the synthetic suite (tools/build_synthetic_suite.py), whose
planted cases carry a schedule certified at 100% by the engine's own metric.

1. break_capacity_headcount_requirement counted room per 15-minute quarter
   against ceil(requirement). The metric averages an interval's quarters, so on
   30/60-minute grids it reported shortages that do not exist: SYNTH_E2 (60-min)
   was told "1 more associate" while 14 people met target in 63/63 intervals
   with zero break losses. Its docstring promised "a deficit is proof".
2. On a budget-starved run the only Stage-1 skeleton could come from a
   productive-basis profile, whose even-spread break assumption stacked 11 on
   some days and 7 on others (45/63). A before-basis profile solves the same
   case optimally in 0.2s; the portfolio's 45s floor refused the 19s left.
"""
import copy
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ENGINE)
TEMPLATE = REPO / "fixtures" / "SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx"
CASES = {c["id"]: c for c in B.case_defs()}


def planted(case_id, demand_multiplier=None, interval_minutes=None):
    """Build a planted case into a temp workbook; return (parsed, skeleton, selected, patterns)."""
    case = copy.deepcopy(CASES[case_id])
    if interval_minutes:
        case["interval_minutes"] = interval_minutes
    tmp = Path(tempfile.mkdtemp()) / (case["id"] + ".xlsx")
    per_day = 1440 // case["interval_minutes"]
    B.build_workbook(TEMPLATE, tmp, case, E, [[1.0] * per_day for _ in range(7)])
    parsed = E.parse_input(tmp)
    sk, sel, pat = B.plant(case, parsed, E)
    before, after = B.after_coverage(parsed, sk, sel, pat, E)
    mult = demand_multiplier if demand_multiplier is not None else case.get("demand_multiplier", 1.0)
    s = case["shrinkage"]
    demand = [[(int(after[d][i] * (1 - s) * mult * 100 + 1e-9) / 100 if before[d][i] > 0 else None)
               for i in range(per_day)] for d in range(7)]
    B.build_workbook(TEMPLATE, tmp, case, E, demand)
    parsed = E.parse_input(tmp)
    sk, sel, pat = B.plant(case, parsed, E)
    return parsed, sk, sel, pat


class CapacityAdvisoryMatchesTheMetric(unittest.TestCase):
    def test_no_false_shortage_on_a_60_minute_plan_that_meets_target(self):
        parsed, sk, sel, pat = planted("SYNTH_E2_SINGLE_SHIFT_WITH_BREAKS")
        metrics = E.calculate_metrics(parsed, sk, sel, pat)
        self.assertEqual(metrics["after_target"], metrics["active_intervals"],
                         "precondition: the planted plan meets target everywhere after breaks")
        report = E.break_capacity_headcount_requirement(parsed, sk)
        self.assertEqual(report["status"], "BREAK_CAPACITY_SUFFICIENT", report)
        self.assertEqual(report["estimated_additional_headcount_for_breaks"], 0)

    def test_room_is_at_least_what_the_plan_actually_used(self):
        """Every break quarter the certified plan placed was lossless, so the
        advisory's room must be at least the plan's break demand."""
        parsed, sk, sel, pat = planted("SYNTH_M2_MULTI_START_WITH_BREAKS")
        report = E.break_capacity_headcount_requirement(parsed, sk)
        self.assertGreaterEqual(report["lossless_break_capacity"], report["break_quarters_required"])

    def test_a_real_shortage_is_still_reported(self):
        parsed, sk, _, _ = planted("SYNTH_H2_HARD_FLOOR_OVERDEMAND")
        report = E.break_capacity_headcount_requirement(parsed, sk)
        self.assertEqual(report["status"], "BREAK_CAPACITY_SHORT")
        self.assertGreater(report["estimated_additional_headcount_for_breaks"], 0)


class StarvedStage1RunsOneBeforeBasisProfile(unittest.TestCase):
    PROFILES = [
        {"name": "target90_restore_champion", "coverage_basis": "before"},
        {"name": "target90_restore_productive", "coverage_basis": "productive"},
        {"name": "before_target_champion", "coverage_basis": "before"},
    ]

    def sk(self, profile):
        return E.SkeletonSolution(profile, "FEASIBLE", 0.0, 0.0, [], [], {})

    def test_picks_the_first_before_basis_profile_when_nothing_ran(self):
        got = E.stage1_starved_basis_profile(self.PROFILES, 0, [self.sk("deterministic_target_baseline")], 19.4)
        self.assertEqual(got["name"], "target90_restore_champion")

    def test_inert_once_any_portfolio_profile_ran(self):
        self.assertIsNone(E.stage1_starved_basis_profile(self.PROFILES, 1, [], 19.4))

    def test_inert_below_the_minimum(self):
        self.assertIsNone(E.stage1_starved_basis_profile(self.PROFILES, 0, [], 4.9))

    def test_inert_when_a_before_basis_skeleton_already_exists(self):
        got = E.stage1_starved_basis_profile(self.PROFILES, 0, [self.sk("before_target_champion")], 19.4)
        self.assertIsNone(got)

    def test_none_when_the_portfolio_has_no_before_basis_profile(self):
        only = [p for p in self.PROFILES if p["coverage_basis"] != "before"]
        self.assertIsNone(E.stage1_starved_basis_profile(only, 0, [], 19.4))

    def test_the_real_portfolio_has_a_before_basis_profile_first(self):
        profs = E.skeleton_profiles(["target90_restore_champion", "target90_restore_productive"])
        self.assertEqual(E.stage1_starved_basis_profile(profs, 0, [], 20.0)["name"], "target90_restore_champion")

    def test_the_before_basis_profile_solves_the_case_that_was_lost(self):
        """End to end on the model: E2's before-basis skeleton is balanced and meets target."""
        parsed, _, _, _ = planted("SYNTH_E2_SINGLE_SHIFT_WITH_BREAKS")
        prof = E.skeleton_profiles(["target90_restore_champion"])[0]
        sk = E.build_skeleton(parsed, prof, E.HardConfig(hard_floor=False), 20.0, 1, io.StringIO(), random_seed=9000)
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        m = E.calculate_metrics(parsed, sk, {(a, d): None for a, d, _ in E.scheduled_cells(sk)}, [])
        self.assertEqual(m["before_target"], m["active_intervals"])


class JointSearchStopsBeforeTheOomKiller(unittest.TestCase):
    """SYNTH_X1 was SIGKILLed at 13.9 GB inside the no-candidate joint endgame."""

    def test_live_reading_and_threshold(self):
        h = E.joint_memory_headroom()
        if h["source"] == "UNAVAILABLE":
            self.skipTest("no /proc/meminfo on this platform")
        self.assertGreaterEqual(h["required_mb"], E.JOINT_MIN_AVAILABLE_MEMORY_MB)
        self.assertEqual(h["ok"], h["available_mb"] >= h["required_mb"])

    def test_an_impossible_requirement_stops(self):
        saved = E.JOINT_MIN_AVAILABLE_MEMORY_MB
        try:
            E.JOINT_MIN_AVAILABLE_MEMORY_MB = 10 ** 12
            h = E.joint_memory_headroom()
            if h["source"] != "UNAVAILABLE":
                self.assertFalse(h["ok"])
        finally:
            E.JOINT_MIN_AVAILABLE_MEMORY_MB = saved

    def test_both_joint_loops_check_before_building_a_model(self):
        import inspect
        src = inspect.getsource(E)
        loop = src.index("for attempt_index in range(portfolio_attempt_budget):")
        self.assertLess(src.index("headroom = joint_memory_headroom()", loop), src.index("operator_name = portfolio.choose()", loop))
        endgame = src.index("and endgame_round < 6")
        self.assertLess(src.index("joint_memory_headroom()", endgame), src.index("endgame_round += 1", endgame))
        self.assertIn('"memory_headroom_stop": memory_stop', src)


class BlankStaffingCountsOnlyCurrentWeekStaffing(unittest.TestCase):
    """FA-7: NMG_SP failed engine/validator parity on blank_staffed_quarters, 16 vs 0.

    The rule is "no NEW staffing in blank intervals"; the validator counts
    current-week staffing. The engine also counted last Saturday's carry-in,
    which the solver cannot move.
    """

    WB = REPO / "packages" / "rc9_2_2_production" / "inputs" / "NMG_SP_RC9_1_READY_FIXED.xlsx"

    def test_carry_in_over_blank_quarters_is_not_blank_staffing(self):
        if not self.WB.exists():
            self.skipTest("packaged NMG_SP workbook not present")
        parsed = E.parse_input(self.WB)
        qpi = parsed.qslots_per_interval
        carry = sum(1 for d in range(7) for i in range(parsed.intervals_per_day) if not parsed.active[d][i]
                    for q in range(qpi) if E.prior_covering_associates(parsed, d * 96 + i * qpi + q))
        self.assertGreater(carry, 0, "precondition: carry-in covers blank quarters in this workbook")
        n = len(parsed.associates)
        empty = E.SkeletonSolution("empty", "FEASIBLE", 0.0, 0.0, [["OFF"] * 7 for _ in range(n)],
                                   [[None] * 7 for _ in range(n)], {})
        self.assertEqual(E.calculate_metrics(parsed, empty, {}, [])["blank_staffed_quarters"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
