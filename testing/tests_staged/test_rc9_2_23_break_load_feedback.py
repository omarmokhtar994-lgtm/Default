"""Break-load feedback (Stage 2 -> Stage 1): contract and wiring.

On saved 3,600 s pools the loop took SYNTH_H1 from 142 to 150 target intervals
(Chat and M2 unchanged; evidence/feedback_loop). It is off by default until
its registered end-to-end A/B. These tests pin: the load is taken only from
intervals breaks pushed below target; an addition is kept only if it is
compliant and dominates the incumbent by the engine's own metrics; nothing
happens without an anchor or time; when on, the phase takes coordinated
repair's slot plus 8% from break search and coordinated repair does not run.
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
import phase_b_maturity as P  # noqa: E402
WB = REPO / "fixtures" / "synthetic_suite" / "SYNTH_M2_MULTI_START_WITH_BREAKS.xlsx"


class OnPlantedM2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = E.parse_input(WB)
        case = {c["id"]: c for c in B.case_defs()}["SYNTH_M2_MULTI_START_WITH_BREAKS"]
        cls.sk, cls.sel, cls.pats = B.plant(case, cls.parsed, E)
        cls.m_planted = E.calculate_metrics(cls.parsed, cls.sk, cls.sel, cls.pats)
        by_duration = {}
        for p in cls.pats:
            by_duration.setdefault(p.duration_q, []).append(p)
        cls.bad = dict(cls.sel)
        for (a, d), pid in cls.sel.items():
            if d == 2 and pid is not None:
                duration = cls.parsed.shifts[cls.sk.selected_shift_index[a][d]].duration_q
                cls.bad[(a, d)] = by_duration[duration][0].index
        cls.m_bad = E.calculate_metrics(cls.parsed, cls.sk, cls.bad, cls.pats)

    def solution(self, selected, metrics):
        return E.BreakSolution("anchor", self.sk.profile, "FEASIBLE", 0.0, 0.0, 115, False,
                               dict(selected), set(), list(self.pats), {}, metrics)

    def test_load_only_on_intervals_breaks_pushed_below_target(self):
        self.assertEqual(E.break_load_by_interval(self.parsed, self.m_planted), {})
        load = E.break_load_by_interval(self.parsed, self.m_bad)
        damaged = {(r["day_index"], r["interval_index"]) for r in self.m_bad["interval_rows"]
                   if r["target_hit_before"] and not r["target_hit_after"]}
        self.assertTrue(load)
        self.assertTrue(set(load) <= damaged)
        self.assertTrue(all(v > 0 for v in load.values()))

    def test_nothing_to_feed_back_on_an_undamaged_plan(self):
        added, _, summary = E.run_break_load_feedback(
            self.parsed, [(self.sk, self.solution(self.sel, self.m_planted))], E.HardConfig(),
            115, time.time() + 90, 2, io.StringIO(), 9000)
        self.assertEqual(added, [])
        self.assertEqual(summary["skip_reason"], "NO_BREAK_DAMAGED_INTERVAL")

    def test_no_anchor_and_no_time_do_nothing(self):
        added, _, summary = E.run_break_load_feedback(self.parsed, [], E.HardConfig(), 115,
                                                      time.time() + 90, 2, io.StringIO(), 9000)
        self.assertEqual((added, summary["skip_reason"]), ([], "NO_COMPLIANT_ANCHOR"))
        added, records, _ = E.run_break_load_feedback(
            self.parsed, [(self.sk, self.solution(self.bad, self.m_bad))], E.HardConfig(), 115,
            time.time() - 1, 2, io.StringIO(), 9000)
        self.assertEqual((added, records), ([], []))

    def test_on_a_real_engine_candidate_it_attempts_and_only_keeps_dominating_compliant_results(self):
        """The best compliant candidate of a real 3,600 s M2 run (111 after breaks,
        117 before): breaks leave intervals under target, so there is load to feed."""
        import json
        fixture = json.loads((REPO / "fixtures" / "feedback_loop" / "M2_BEST_COMPLIANT_CANDIDATE.json").read_text())
        sk, br = E.deserialize_break_candidate(self.parsed, fixture["candidate"])
        br.metrics = E.calculate_metrics(self.parsed, sk, br.selected_pattern, br.patterns)
        self.assertEqual(br.metrics["after_target"], fixture["after_target"])
        self.assertEqual(E.candidate_pool_class(self.parsed, sk, br), "compliant")
        self.assertTrue(E.break_load_by_interval(self.parsed, br.metrics))
        added, records, summary = E.run_break_load_feedback(
            self.parsed, [(sk, br)], E.HardConfig(hard_floor=(self.parsed.floor_mode == "hard")),
            115, time.time() + 150, 2, io.StringIO(), 9000)
        self.assertGreaterEqual(summary["attempts"], 1, records)
        previous = br.metrics
        for new_sk, candidate in added:
            self.assertEqual(E.candidate_pool_class(self.parsed, new_sk, candidate), "compliant")
            fresh = E.calculate_metrics(self.parsed, new_sk, candidate.selected_pattern, candidate.patterns)
            ok, worse = E.dnbs_metrics_no_worse(fresh, previous)
            self.assertTrue(ok, worse)
            previous = fresh
        for record in records:
            self.assertIn(record["status"], {"ACCEPTED", "REJECTED", "STAGE1_NOT_FEASIBLE", "STAGE1_HARD_GATE",
                                             "STAGE2_NOT_FEASIBLE", "NO_BREAK_BUDGET"})


class Budget(unittest.TestCase):
    KW = dict(allow_exceptions=False, coordinated_repair=True, joint_refinement=False,
              target_lock_recovery=True, day_neighbourhood_break_search=True)

    def test_takes_coordinated_slot_plus_eight_percent_of_break_search(self):
        for total in (1800, 3600, 14400):
            off = P.build_global_budget_plan(total, **self.KW)
            on = P.build_global_budget_plan(total, break_load_feedback=True, **self.KW)
            self.assertEqual(sum(on.values()), total)
            self.assertEqual(on["coordinated_repair"], 0)
            extra = off["break_search"] - on["break_search"]
            self.assertEqual(on["break_load_feedback"], off["coordinated_repair"] + extra)
            self.assertEqual(on["stage1_search"], off["stage1_search"])
        self.assertEqual(P.build_global_budget_plan(3600, break_load_feedback=True, **self.KW)["break_load_feedback"], 540)

    def test_off_by_default(self):
        self.assertEqual(P.build_global_budget_plan(3600, **self.KW)["break_load_feedback"], 0)
        self.assertFalse(E.BREAK_LOAD_FEEDBACK_ENABLED)


class Wiring(unittest.TestCase):
    def test_replaces_coordinated_repair_when_on(self):
        src = inspect.getsource(E)
        fbl = src.index("fbl_added, fbl_records, fbl_execution = run_break_load_feedback(")
        coordinated = src.index("coordinated_added, coordinated_records, coordinated_execution = run_coordinated_shift_off_break_loop(")
        self.assertLess(fbl, coordinated)
        self.assertIn("if (coordinated_repair and not break_load_feedback_on and coordinated_pool", src)
        self.assertIn("break_load_feedback=BREAK_LOAD_FEEDBACK_ENABLED and coordinated_repair and not skeleton_only", src)
        self.assertTrue(E.build_arg_parser().parse_args(["--enable-break-load-feedback", "--selfcheck"]).enable_break_load_feedback)


if __name__ == "__main__":
    unittest.main(verbosity=2)
