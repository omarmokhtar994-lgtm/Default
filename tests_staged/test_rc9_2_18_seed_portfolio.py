"""Seed portfolio: keep the best validated after-breaks and best before-breaks sheet.

On identical input the engine's result varies with the solver seed more than
with extra time (Chat after_target 167-182 across seeds; 900 s -> 3,600 s left
the mean at 176). RUN_PORTFOLIO.py runs several seeds and keeps the best. These
tests pin its selection rules on synthetic run folders: an unvalidated final
can never win, the before-breaks sheet is chosen on its own, and PORTFOLIO_BEST
holds copies of exactly the winning workbooks.
"""
import csv
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
spec = importlib.util.spec_from_file_location("portfolio", ROOT / "engine" / "RUN_PORTFOLIO.py")
PF = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PF)

FIELDS = ["after_target", "after_floor", "after90", "after80", "after_severe_overage_count",
          "after_avoidable_overage_fte_sum", "best_before_target", "best_before_floor",
          "before_target", "before_floor", "status"]


def make_run(root, name, after_target, best_before, after_floor=100, validator="PASS", hard=0,
             parity="PASS", finished=True, final=True):
    d = Path(root) / name
    (d / "production").mkdir(parents=True)
    if not finished:
        return d
    with open(d / f"{name}.l6_3_2_3_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerow({"after_target": after_target, "after_floor": after_floor, "after90": 0, "after80": 0,
                    "after_severe_overage_count": 0, "after_avoidable_overage_fte_sum": 0,
                    "best_before_target": best_before, "best_before_floor": 0,
                    "before_target": best_before, "before_floor": 0, "status": "PASS"})
    (d / "INDEPENDENT_VALIDATION.json").write_text(json.dumps(
        {"status": validator, "hard_fail_count": hard, "metric_parity": {"status": parity}}))
    if final:
        (d / "production" / f"{name}_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx").write_text(f"final {name}")
    (d / "production" / f"{name}_L6_3_2_3_BEST_BEFORE_BREAKS_SCHEDULE.xlsx").write_text(f"before {name}")
    return d


class Selection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def results(self, *dirs):
        out = []
        for i, d in enumerate(dirs):
            r = PF.read_seed_result(d)
            r["seed"] = 9000 + i
            out.append(r)
        return out

    def test_best_after_and_best_before_are_chosen_independently(self):
        rs = self.results(make_run(self.tmp, "A", 170, 196), make_run(self.tmp, "B", 182, 188))
        w = PF.choose_winners(rs)
        self.assertEqual(w["after"]["seed"], 9001)
        self.assertEqual(w["before"]["seed"], 9000)

    def test_an_unvalidated_final_never_wins(self):
        for kwargs in ({"validator": "FAIL"}, {"hard": 1}, {"parity": "FAIL"}, {"final": False}):
            with self.subTest(**kwargs):
                tmp = tempfile.mkdtemp()
                rs = self.results(make_run(tmp, "A", 170, 190), make_run(tmp, "B", 999, 190, **kwargs))
                self.assertEqual(PF.choose_winners(rs)["after"]["seed"], 9000)

    def test_ties_on_target_fall_to_floor(self):
        rs = self.results(make_run(self.tmp, "A", 180, 190, after_floor=220),
                          make_run(self.tmp, "B", 180, 190, after_floor=225))
        self.assertEqual(PF.choose_winners(rs)["after"]["seed"], 9001)

    def test_an_unfinished_run_is_ignored(self):
        rs = self.results(make_run(self.tmp, "A", 0, 0, finished=False), make_run(self.tmp, "B", 150, 180))
        self.assertFalse(rs[0]["finished"])
        w = PF.choose_winners(rs)
        self.assertEqual((w["after"]["seed"], w["before"]["seed"]), (9001, 9001))

    def test_no_validated_final_means_no_winner(self):
        rs = self.results(make_run(self.tmp, "A", 170, 190, validator="FAIL"))
        w = PF.choose_winners(rs)
        self.assertIsNone(w["after"])
        self.assertEqual(w["before"]["seed"], 9000)

    def test_seed_list(self):
        self.assertEqual(PF.seed_list(3, 9000, None), [9000, 9001, 9002])
        self.assertEqual(PF.seed_list(1, 9000, None), [9000])
        self.assertEqual(PF.seed_list(5, 9000, "11,12"), [11, 12])


class EndToEnd(unittest.TestCase):
    def test_portfolio_best_holds_copies_of_the_winners_and_runs_are_untouched(self):
        tmp = tempfile.mkdtemp()
        scores = {9000: (170, 196), 9001: (182, 188), 9002: (999, 999)}

        def fake_run_seed(seed, schedule_id, seeds_root, passthrough, log_dir):
            at, bt = scores[seed]
            return make_run(seeds_root, f"{schedule_id}_S{seed}", at, bt,
                            validator="FAIL" if seed == 9002 else "PASS")

        saved = PF.run_seed
        PF.run_seed = fake_run_seed
        try:
            rc = PF.main(["--seeds", "3", "--output-root", tmp, "--schedule-id", "CASE", "--mode", "QUICK"])
        finally:
            PF.run_seed = saved
        self.assertEqual(rc, 0)
        best = Path(tmp) / "CASE" / "PORTFOLIO_BEST"
        names = sorted(p.name for p in best.iterdir())
        self.assertIn("CASE_S9001_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx", names)
        self.assertIn("CASE_S9002_L6_3_2_3_BEST_BEFORE_BREAKS_SCHEDULE.xlsx", names)
        self.assertIn("INDEPENDENT_VALIDATION_OF_BEST_FINAL.json", names)
        summary = json.loads((Path(tmp) / "CASE" / "PORTFOLIO_SUMMARY.json").read_text())
        self.assertEqual((summary["after_breaks_winner_seed"], summary["before_breaks_winner_seed"]), (9001, 9002))
        self.assertEqual(summary["passthrough_arguments"], ["--mode", "QUICK"])
        # the seed runs themselves are left as they were
        self.assertTrue((Path(tmp) / "CASE" / "seeds" / "CASE_S9000" / "INDEPENDENT_VALIDATION.json").exists())

    def test_reserved_arguments_are_refused(self):
        with self.assertRaises(SystemExit):
            PF.main(["--schedule-id", "X", "--solver-random-seed", "5"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
