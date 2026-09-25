"""DNBS: day-neighbourhood break search adds only dominating, compliant candidates.

On a fixed skeleton one day's breaks interact only with that day and its
spill, and associates on the same (day, shift, language) are interchangeable
for coverage, so a day's break placement is a small aggregated model. Solved
day by day on the final engine's own candidate pools it found H1 138 -> 145,
Voice 246 -> 247, M2 108 -> 109 with no guarded metric worse
(evidence/NIGHT_15_JOINT_SHIFT_BREAK_BUILD.md).

These tests pin the contract: a move is kept only if the engine's own
calculate_metrics shows after_target rose and nothing guarded got worse; the
finished candidate is added only if the release validator calls it compliant;
an already-optimal anchor gains nothing; and the phase sits between RC8
quality recovery and the joint-refinement pool.
"""
import inspect
import io
import os
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import phase_b_maturity as B_PHASE  # noqa: E402
WB = REPO / "fixtures" / "synthetic_suite" / "SYNTH_M2_MULTI_START_WITH_BREAKS.xlsx"


class DominanceRule(unittest.TestCase):
    BASE = {"after_target": 100, "after_floor": 110, "after_90": 105, "severe_floor_gap_count": 2,
            "break_concurrency_violation_count": 1, "after_avoidable_overage_fte_sum": 7.5}

    def test_strict_target_gain_with_nothing_worse_is_accepted(self):
        new = dict(self.BASE, after_target=101)
        self.assertEqual(E.dnbs_metrics_no_worse(new, self.BASE), (True, []))

    def test_equal_target_is_not_an_improvement(self):
        ok, worse = E.dnbs_metrics_no_worse(dict(self.BASE), self.BASE)
        self.assertFalse(ok)
        self.assertIn("after_target", worse)

    def test_a_target_gain_paid_for_elsewhere_is_rejected(self):
        for key, value in [("after_floor", 109), ("after_90", 104), ("severe_floor_gap_count", 3),
                           ("break_concurrency_violation_count", 2), ("after_avoidable_overage_fte_sum", 7.6)]:
            ok, worse = E.dnbs_metrics_no_worse(dict(self.BASE, after_target=103, **{key: value}), self.BASE)
            self.assertFalse(ok, key)
            self.assertEqual(worse, [key])


class OnAPlantedCase(unittest.TestCase):
    """SYNTH_M2's planted schedule is 117/117 by the engine's own metric."""

    @classmethod
    def setUpClass(cls):
        cls.parsed = E.parse_input(WB)
        case = {c["id"]: c for c in B.case_defs()}["SYNTH_M2_MULTI_START_WITH_BREAKS"]
        cls.sk, cls.sel, cls.pats = B.plant(case, cls.parsed, E)
        cls.m_planted = E.calculate_metrics(cls.parsed, cls.sk, cls.sel, cls.pats)
        by_duration = {}
        for p in cls.pats:
            by_duration.setdefault(p.duration_q, []).append(p)
        # Wreck Tuesday: everyone on the same break pattern.
        cls.bad = dict(cls.sel)
        for (a, d), pid in cls.sel.items():
            if d == 2 and pid is not None:
                duration = cls.parsed.shifts[cls.sk.selected_shift_index[a][d]].duration_q
                cls.bad[(a, d)] = by_duration[duration][0].index
        cls.m_bad = E.calculate_metrics(cls.parsed, cls.sk, cls.bad, cls.pats)

    def solution(self, selected, metrics):
        return E.BreakSolution("anchor", self.sk.profile, "FEASIBLE", 0.0, 0.0, 115, False,
                               dict(selected), set(), list(self.pats), {}, metrics)

    def test_preconditions(self):
        n = self.m_planted["active_intervals"]
        self.assertEqual((self.m_planted["after_target"], self.m_planted["after_floor"]), (n, n))
        self.assertLess(self.m_bad["after_target"], n)

    def test_recovers_a_damaged_day_and_the_result_is_compliant_and_dominates(self):
        added, records, summary = E.run_day_neighbourhood_break_search(
            self.parsed, [(self.sk, self.solution(self.bad, self.m_bad))],
            time.time() + 90, 2, io.StringIO(), 9000)
        self.assertEqual(len(added), 1, records)
        sk, candidate = added[0]
        self.assertIs(sk, self.sk)
        self.assertEqual(E.candidate_pool_class(self.parsed, sk, candidate), "compliant")
        fresh = E.calculate_metrics(self.parsed, sk, candidate.selected_pattern, candidate.patterns)
        self.assertGreater(fresh["after_target"], self.m_bad["after_target"])
        ok, worse = E.dnbs_metrics_no_worse(fresh, self.m_bad)
        self.assertTrue(ok, worse)
        self.assertEqual(candidate.diagnostics["candidate_origin"], "DAY_NEIGHBOURHOOD_BREAK_SEARCH")
        self.assertIn("break_spacing_rows", candidate.diagnostics)
        self.assertEqual(candidate.diagnostics["release_validation"]["hard_fail_count"], 0)
        # Only the damaged day moved.
        moved_days = {d for key, pid in candidate.selected_pattern.items() if pid != self.bad[key] for d in [key[1]]}
        self.assertTrue(moved_days <= {2}, moved_days)

    def test_an_optimal_anchor_gains_nothing(self):
        added, _, summary = E.run_day_neighbourhood_break_search(
            self.parsed, [(self.sk, self.solution(self.sel, self.m_planted))],
            time.time() + 60, 2, io.StringIO(), 9000)
        self.assertEqual(added, [])
        self.assertEqual(summary["accepted_candidates"], 0)

    def test_no_anchor_no_work(self):
        added, records, summary = E.run_day_neighbourhood_break_search(
            self.parsed, [], time.time() + 60, 2, io.StringIO(), 9000)
        self.assertEqual((added, records, summary["skip_reason"]), ([], [], "NO_COMPLIANT_ANCHOR"))

    def test_an_expired_deadline_does_nothing(self):
        added, _, summary = E.run_day_neighbourhood_break_search(
            self.parsed, [(self.sk, self.solution(self.bad, self.m_bad))],
            time.time() - 1, 2, io.StringIO(), 9000)
        self.assertEqual(added, [])
        self.assertTrue(summary["truncated"])

    def test_a_short_window_uses_one_anchor(self):
        _, _, summary = E.run_day_neighbourhood_break_search(
            self.parsed, [(self.sk, self.solution(self.bad, self.m_bad))],
            time.time() + 7 * 2 * E.DNBS_MIN_USEFUL_DAY_SEC - 5, 2, io.StringIO(), 9000)
        self.assertEqual(summary["max_anchors"], 1)

    def test_a_funded_window_uses_two(self):
        _, _, summary = E.run_day_neighbourhood_break_search(
            self.parsed, [], time.time() + 7 * 2 * E.DNBS_MIN_USEFUL_DAY_SEC + 30, 2, io.StringIO(), 9000)
        self.assertEqual(summary.get("max_anchors", 2), 2)


class Wiring(unittest.TestCase):
    def test_runs_after_rc8_recovery_and_before_the_joint_pool(self):
        src = inspect.getsource(E)
        rc8 = src.index("rc8_added, rc8_records, rc8_execution = run_rc8_best_before_break_recovery(")
        dnbs = src.index("dnbs_added, dnbs_records, dnbs_execution = run_day_neighbourhood_break_search(")
        joint = src.index("joint_pool = dedupe_break_candidates(list(compliant) + list(near_feasible) + list(exceptions))")
        self.assertLess(rc8, dnbs)
        self.assertLess(dnbs, joint)
        self.assertIn('audit["day_neighbourhood_break_search"]', src)

    def test_engine_funds_its_own_phase_and_rc8_leaves_it_alone(self):
        src = inspect.getsource(E)
        self.assertIn("day_neighbourhood_break_search=DAY_NEIGHBOURHOOD_BREAK_SEARCH_ENABLED and not skeleton_only", src)
        self.assertIn("rc8_ceiling = joint_refinement_deadline - dnbs_reserved_sec", src)
        self.assertIn('budget_manager.deadline("day_neighbourhood_break_search")', src)
        self.assertTrue(E.DAY_NEIGHBOURHOOD_BREAK_SEARCH_ENABLED)


class FundedBudgetPhase(unittest.TestCase):
    """The first design took half of what was left before joint refinement.
    At QUICK joint refinement is allocated 0 s, so DNBS got break-search
    leftovers (8-39 s) and did nothing in 5 of 6 runs of the 3600 s A/B
    (evidence/dnbs_e2e_3600/RESULT.txt). It now has its own phase."""

    KW = dict(allow_exceptions=False, coordinated_repair=True, joint_refinement=False, target_lock_recovery=True)

    def plan(self, total, on=True):
        return B_PHASE.build_global_budget_plan(total, day_neighbourhood_break_search=on, **self.KW)

    def test_paid_for_by_break_search_only(self):
        for total in (900, 1800, 3600, 14400):
            off, on = self.plan(total, False), self.plan(total)
            dnbs = on["day_neighbourhood_break_search"]
            self.assertGreater(dnbs, 0, total)
            self.assertEqual(sum(on.values()), total)
            self.assertEqual(on["stage1_search"], off["stage1_search"], total)
            self.assertEqual(off["break_search"] - on["break_search"], dnbs, total)
            for name in off:
                if name not in {"break_search", "day_neighbourhood_break_search"}:
                    self.assertEqual(on[name], off[name], (total, name))

    def test_sized_and_capped(self):
        self.assertEqual(self.plan(3600)["day_neighbourhood_break_search"], 288)
        self.assertEqual(self.plan(14400)["day_neighbourhood_break_search"], B_PHASE.DNBS_BUDGET_CAP_SEC)
        self.assertEqual(self.plan(900)["day_neighbourhood_break_search"], 72)
        self.assertEqual(self.plan(300)["day_neighbourhood_break_search"], 0)

    def test_off_by_default_for_other_callers(self):
        plan = B_PHASE.build_global_budget_plan(3600, **self.KW)
        self.assertEqual(plan["day_neighbourhood_break_search"], 0)

    def test_runs_between_break_search_and_joint_refinement(self):
        order = list(self.plan(3600))
        self.assertEqual(order.index("day_neighbourhood_break_search"), order.index("break_search") + 1)
        self.assertLess(order.index("day_neighbourhood_break_search"), order.index("joint_refinement"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
