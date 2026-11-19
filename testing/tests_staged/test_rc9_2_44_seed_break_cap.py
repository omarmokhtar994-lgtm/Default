"""Phase D3: the seed builders' concurrent-break cap must equal the engine's.

The engine's ceiling (maximum_concurrent_breaks) lets one associate break as
soon as two are staffed: min(staffed - 1, max(1, floor(ratio * staffed)),
max(1, absolute)), and 0 when staffed <= 1. The seed models (tools/
aggregate_seed.py, tools/aggregate_seed_real.py) used ratio * staffed alone,
which forbids every break at 2-3 staffed heads (ratio 0.3). Found 2026-10-06:
pinned to the engine's own Cricut Chat week, the seed model scored it 191
before breaks (= engine) but only 126 after breaks (engine: 176).

Pinned here: for every staffed count and break count, the helper's model is
feasible exactly when the engine allows that many concurrent breaks; with a
slack variable it may exceed the cap by exactly the slack.
"""
import os
import sys
import types
import unittest
from pathlib import Path

from ortools.sat.python import cp_model

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import aggregate_seed as A  # noqa: E402
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
SETTINGS = [(0.3, 4), (0.2, 2), (0.5, 1), (1.0, 6), (0.25, 0)]


def feasible(staffed: int, breaks: int, ratio: float, absolute: int, slack_max=None) -> bool:
    m = cp_model.CpModel()
    b = m.NewIntVar(breaks, breaks, "b")
    s = m.NewIntVar(staffed, staffed, "s")
    sl = None if slack_max is None else m.NewIntVar(0, slack_max, "sl")
    A.add_break_cap(m, b, s, ratio, absolute, slack=sl)
    sv = cp_model.CpSolver()
    sv.parameters.num_workers = 1
    return sv.Solve(m) in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TheSeedBreakCapIsTheEngineCap(unittest.TestCase):
    def test_every_staffed_and_break_count(self):
        for ratio, absolute in SETTINGS:
            p = types.SimpleNamespace(break_max_concurrent_ratio=ratio, break_max_concurrent_absolute=absolute)
            for staffed in range(0, 16):
                cap = E.maximum_concurrent_breaks(p, staffed)
                for breaks in range(0, staffed + 1):
                    with self.subTest(ratio=ratio, absolute=absolute, staffed=staffed, breaks=breaks, engine_cap=cap):
                        self.assertEqual(feasible(staffed, breaks, ratio, absolute), breaks <= cap)

    def test_one_break_allowed_at_two_and_three_heads_with_ratio_0_3(self):
        self.assertTrue(feasible(2, 1, 0.3, 4))
        self.assertTrue(feasible(3, 1, 0.3, 4))


class TheSoftCapExceedsByAtMostTheSlack(unittest.TestCase):
    def test_slack_zero_is_the_hard_cap_and_slack_k_allows_k_more(self):
        p = types.SimpleNamespace(break_max_concurrent_ratio=0.3, break_max_concurrent_absolute=4)
        for staffed in range(0, 12):
            cap = E.maximum_concurrent_breaks(p, staffed)
            for breaks in range(0, staffed + 1):
                with self.subTest(staffed=staffed, breaks=breaks):
                    self.assertEqual(feasible(staffed, breaks, 0.3, 4, slack_max=0), breaks <= cap)
                    self.assertTrue(feasible(staffed, breaks, 0.3, 4, slack_max=staffed))


if __name__ == "__main__":
    unittest.main()
