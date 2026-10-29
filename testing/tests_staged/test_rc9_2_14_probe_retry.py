"""The hard-feasibility probe retries an UNKNOWN before the run gives up.

SYNTH_X1 (120 associates, 15-minute grid, 24/7, a planted feasible schedule
certified by the engine's own metric) ended its 30s probe UNKNOWN and the run
stopped FAIL_HARD_CONTRACT_UNKNOWN with 1,123 of 1,200 seconds unspent.
UNKNOWN is not INFEASIBLE; the retry borrows from the Stage-1 window, which
cannot start without a feasible skeleton anyway.
"""
import ast
import inspect
import os
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("CANDIDATE_ENGINE", ".")).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402


class RetrySliceArithmetic(unittest.TestCase):
    def test_half_the_stage1_window(self):
        self.assertAlmostEqual(E.preflight_probe_retry_seconds(612.0), 306.0)

    def test_capped(self):
        self.assertEqual(E.preflight_probe_retry_seconds(5000.0), E.PREFLIGHT_PROBE_RETRY_MAX_SEC)

    def test_no_retry_shorter_than_the_first_probe_floor(self):
        for window in (0.0, 10.0, 59.9):
            with self.subTest(window=window):
                self.assertEqual(E.preflight_probe_retry_seconds(window), 0.0)
        self.assertEqual(E.preflight_probe_retry_seconds(60.0), 30.0)

    def test_never_more_than_the_window(self):
        for window in (60.0, 100.0, 1199.0, 1e6):
            with self.subTest(window=window):
                self.assertLessEqual(E.preflight_probe_retry_seconds(window), window)

    def test_negative_window_is_zero(self):
        self.assertEqual(E.preflight_probe_retry_seconds(-5.0), 0.0)


class RetryControlFlow(unittest.TestCase):
    """Where the retry sits in the run, read from the source of the real code path."""

    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(E)
        start = cls.src.index("probe = resumed_skeletons[0] if resumed_skeletons else build_skeleton(")
        end = cls.src.index('audit["hard_feasibility_probe"] = {"cp_status": probe.cp_status')
        cls.block = cls.src[start:end]

    def test_retry_only_on_unknown_and_not_on_resume(self):
        self.assertIn('if not resumed_skeletons and probe.cp_status == "UNKNOWN":', self.block)

    def test_retry_is_sized_from_the_stage1_window(self):
        self.assertIn('preflight_probe_retry_seconds(budget_manager.remaining_in_phase("stage1_search"))',
                      self.block)

    def test_an_unknown_retry_does_not_replace_the_first_probe(self):
        self.assertIn('if retry.cp_status != "UNKNOWN":', self.block)

    def test_retry_precedes_the_give_up_branch(self):
        give_up = self.src.index('if probe.cp_status not in {"OPTIMAL", "FEASIBLE"}:')
        retry = self.src.index("preflight_probe_retry_seconds(budget_manager")
        self.assertLess(retry, give_up)

    def test_retry_is_audited(self):
        self.assertIn('audit["hard_feasibility_probe"]["retry"] = probe_retry', self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
