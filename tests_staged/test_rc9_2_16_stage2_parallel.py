"""S2-PAR: break solves use every worker; the infeasibility core survives.

With break_infeasibility_core_enabled (default Yes) every break model carried
assumption literals, and assumption solves are single-worker, so Stage-2 ran
on one worker whatever --num-workers said. With more than one worker the solve
now runs on a clone with the literals fixed true; only an INFEASIBLE result is
re-solved with assumptions to name the core. End-to-end A/B (900s, 2 workers,
pre-registered): Chat 155 -> 179, Voice 227 -> 246, AE_AR 166 -> 167, NMG_SP
121 = 121, SYNTH_M2 82 -> 109, SYNTH_H3 76 -> 91; every run validator-clean.
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
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
WB = REPO / "fixtures" / "synthetic_suite" / "SYNTH_E2_SINGLE_SHIFT_WITH_BREAKS.xlsx"


def with_metrics(parsed, sk):
    sk.diagnostics["no_break_metrics"] = E.calculate_metrics(
        parsed, sk, {(a, d): None for a, d, _ in E.scheduled_cells(sk)}, [])
    return sk


class Stage2UsesAllWorkers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = E.parse_input(WB)
        case = {c["id"]: c for c in B.case_defs()}["SYNTH_E2_SINGLE_SHIFT_WITH_BREAKS"]
        cls.planted, _, _ = B.plant(case, cls.parsed, E)
        with_metrics(cls.parsed, cls.planted)
        # One person alone on Monday: any break empties the floor -> INFEASIBLE.
        n = len(cls.parsed.associates)
        label = cls.planted.assignment[0][1]
        idx = cls.planted.selected_shift_index[0][1]
        assign = [["OFF"] * 7 for _ in range(n)]
        sel = [[None] * 7 for _ in range(n)]
        assign[0][1], sel[0][1] = label, idx
        cls.alone = with_metrics(cls.parsed, E.SkeletonSolution("alone", "FEASIBLE", 0, 0, assign, sel, {}))

    def solve(self, sk, workers):
        return E.solve_breaks(self.parsed, sk, 115, False, 20, workers, io.StringIO(),
                              objective_mode="target_priority", random_seed=9000)

    def test_core_is_on_by_default(self):
        self.assertTrue(self.parsed.break_infeasibility_core_enabled)

    def test_multi_worker_solve_uses_every_worker(self):
        b = self.solve(self.planted, 2)
        self.assertIn(b.cp_status, {"OPTIMAL", "FEASIBLE"})
        self.assertEqual(b.diagnostics["solver_workers"], 2)
        self.assertTrue(b.diagnostics["stage2_parallel_without_assumptions"])

    def test_one_worker_path_is_unchanged(self):
        b = self.solve(self.planted, 1)
        self.assertEqual(b.diagnostics["solver_workers"], 1)
        self.assertFalse(b.diagnostics["stage2_parallel_without_assumptions"])
        self.assertTrue(b.diagnostics["break_assumption_core_single_worker"])

    def test_infeasible_core_is_still_named_with_many_workers(self):
        one = self.solve(self.alone, 1)
        many = self.solve(self.alone, 2)
        self.assertEqual(one.cp_status, "INFEASIBLE")
        self.assertEqual(many.cp_status, "INFEASIBLE")
        self.assertTrue(many.diagnostics["break_infeasibility_core_families"])
        self.assertEqual(sorted(many.diagnostics["break_infeasibility_core_families"]),
                         sorted(one.diagnostics["break_infeasibility_core_families"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
