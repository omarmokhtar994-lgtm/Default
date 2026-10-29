"""The public shift-design benchmark tooling (tools/public_shift_design_suite.py).

Pins the three things the benchmark's conclusions rest on:
  * the translation reads the published instances the way the authors'
    validator does: every published optimum scores 0 understaffing and 0
    overstaffing under our cyclic scorer;
  * the exact reference: the proven minimum full-cover roster for R10 skill 2
    is FEASIBLE at 20 and INFEASIBLE at 19 under the engine's tour rules;
  * the engine's own metric scores a proven-perfect week as perfect (D2a).
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import public_shift_design_suite as P  # noqa: E402

DATA = REPO / "evidence" / "public_benchmarks" / "bonutti_2017"
INST, SOLS = DATA / "instances", DATA / "solutions"


class TheScorerReadsInstancesLikeTheAuthorsValidator(unittest.TestCase):
    def test_every_translated_published_optimum_is_exact(self):
        for iid in P.TRANSLATED:
            inst = P.parse_instance(INST / (iid + ".txt"))
            opt = P.parse_solution(SOLS / (iid + "-opt.txt"), inst["skills"])
            for sk in range(inst["skills"]):
                shifts, breaks, w = {}, {}, 0
                for s in opt:
                    for d in range(7):
                        for _ in range(s["counts"][d][sk]):
                            shifts[(w, d)] = (s["start"], s["len"])
                            if s["brk_at"] is not None:
                                breaks[(w, d)] = [(s["brk_at"] % 1440, 60)]
                            w += 1
                score = P.cyclic_score(inst["req"][sk], shifts, breaks)
                with self.subTest(instance=iid, skill=sk + 1):
                    self.assertEqual((score["under_slots"], score["over_slots"]), (0, 0))
                    self.assertEqual(score["hit"], score["active"])

    def test_every_optimum_shift_is_in_the_translated_library(self):
        for iid in P.TRANSLATED:
            P.cases_for(INST, SOLS, iid)  # asserts internally


class TheExactReferenceIsTight(unittest.TestCase):
    def test_r10_skill2_full_cover_needs_exactly_20(self):
        from ortools.sat.python import cp_model
        inst = P.parse_instance(INST / "R10.txt")
        opt = P.parse_solution(SOLS / "R10-opt.txt", inst["skills"])
        case = P.cases_for(INST, SOLS, "R10")[1]
        a = types.SimpleNamespace(time_limit=120, workers=2)
        self.assertEqual(P._full_cover_feasible(cp_model, case, opt, 19, set(), a)[0], "INFEASIBLE")
        self.assertIn(P._full_cover_feasible(cp_model, case, opt, 20, set(), a)[0], ("OPTIMAL", "FEASIBLE"))


class TheEngineMetricScoresAPerfectWeekAsPerfect(unittest.TestCase):
    def test_r10_skill1_perfect_week(self):
        out = Path(tempfile.mkdtemp())
        a = types.SimpleNamespace(
            instances=INST, solutions=SOLS, engine=ROOT / "engine" / "_tools" / "l632_universal_scheduler.py",
            template=REPO / "fixtures" / "SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx",
            reference=REPO / "evidence" / "public_benchmarks" / "REFERENCE_FULL_COVER_ROSTERS.json",
            out_dir=out, only="PUB_SDB_R10_SKILL1", time_limit=120, workers=2)
        P.cmd_perfect(a)
        import json
        row = json.loads((out / "PERFECT_SEED_SCORES.json").read_text())["PUB_SDB_R10_SKILL1"]
        self.assertEqual(row["engine_after_target"], row["active"])
        self.assertEqual(row["break_patterns_unmatched"], 0)
        self.assertEqual(row["break_concurrency_violations"], 0)


if __name__ == "__main__":
    unittest.main()
