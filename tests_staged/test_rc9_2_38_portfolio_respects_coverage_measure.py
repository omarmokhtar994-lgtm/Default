"""Audit F-36: best-of-seeds must rank by the coverage measure the program chose.

RUN_PORTFOLIO keeps the best validated seed. It ranked seeds by after-break
intervals at target whatever the run optimised, so a program that chose
Volume Weighted had every step optimise requirement covered, and then the
final pick across seeds quietly went back to counting intervals. The C4 A/B
showed the seed is the largest source of variation (Chat: -32 and +35 FTE
covered on two seeds), so the pick across seeds is where the choice matters
most.

Now: when every seed ran Volume Weighted (from each run's audit), seeds are
ranked first by the requirement covered at target, computed from the
independent validator's interval rows (not the engine's own claim), then by
the old order. Interval Count ranks exactly as before. Eligibility (exit 0,
validator PASS, 0 hard failures, parity PASS, production eligible) does not
change.

Written to FAIL on the runner before this change and pass after.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
spec = importlib.util.spec_from_file_location("portfolio_c38", ROOT / "engine" / "RUN_PORTFOLIO.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def seed_run(root: Path, name: str, after_target: int, rows, measure="interval_count", target=1.0):
    """A finished, eligible seed run with the artifacts RUN_PORTFOLIO reads."""
    run = root / name
    (run / "production").mkdir(parents=True)
    (run / "production" / f"{name}_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx").write_bytes(b"x")
    (run / "production" / f"{name}_L6_3_2_3_BEST_BEFORE_BREAKS_SCHEDULE.xlsx").write_bytes(b"x")
    summary = {"after_target": after_target, "after_floor": 50, "after90": 50, "after80": 50,
               "after_severe_overage_count": 0, "after_avoidable_overage_fte_sum": 0,
               "best_before_target": 60, "best_before_floor": 60, "before_target": 60, "before_floor": 60,
               "status": "PASS", "production_eligible": "TRUE", "target_ratio": target}
    with open(run / f"{name}.l6_3_2_3_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary))
        w.writeheader()
        w.writerow(summary)
    validation = {"status": "PASS", "hard_fail_count": 0, "metric_parity": {"status": "PASS"},
                  "interval_rows": [{"required": req, "after_pct": pct, "after_effective": req * pct}
                                    for req, pct in rows]}
    (run / "INDEPENDENT_VALIDATION.json").write_text(json.dumps(validation))
    (run / f"{name}.l6_3_2_3_solver_audit.json").write_text(
        json.dumps({"coverage_measure": {"mode": measure, "source": "run override"}}))
    result = P.read_seed_result(run, 0)
    result["seed"] = name
    return result


# Seed A: more intervals at target (3), less requirement covered (1+1+1 = 3 FTE).
A_ROWS = [(1.0, 1.0), (1.0, 1.0), (1.0, 1.0), (10.0, 0.5)]
# Seed B: fewer intervals at target (2), more requirement covered (1 + 10 = 11 FTE).
B_ROWS = [(1.0, 1.0), (10.0, 1.0), (1.0, 0.5), (1.0, 0.5)]


class TheValidatorMeasuresRequirementCovered(unittest.TestCase):
    def test_requirement_covered_at_target_comes_from_the_validator_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = seed_run(Path(tmp), "A", 3, A_ROWS)
            b = seed_run(Path(tmp), "B", 2, B_ROWS)
        self.assertEqual(a["summary"]["req_covered_at_target"], 3.0)
        self.assertEqual(b["summary"]["req_covered_at_target"], 11.0)
        self.assertEqual(a["coverage_measure"], "interval_count")


class TheWinnerFollowsTheMeasure(unittest.TestCase):
    def test_interval_count_ranks_exactly_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = [seed_run(Path(tmp), "A", 3, A_ROWS), seed_run(Path(tmp), "B", 2, B_ROWS)]
        winners = P.choose_winners(results)
        self.assertEqual(winners["after"]["seed"], "A")
        self.assertEqual(winners["ranking"], "INTERVAL_COUNT")
        self.assertEqual(P.after_ranking_key("INTERVAL_COUNT"), P.AFTER_KEY)

    def test_volume_weighted_ranks_requirement_covered_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = [seed_run(Path(tmp), "A", 3, A_ROWS, "volume_weighted"),
                       seed_run(Path(tmp), "B", 2, B_ROWS, "volume_weighted")]
        winners = P.choose_winners(results)
        self.assertEqual(winners["after"]["seed"], "B")
        self.assertEqual(winners["ranking"], "VOLUME_WEIGHTED")
        self.assertEqual(P.after_ranking_key("VOLUME_WEIGHTED")[0], ("req_covered_at_target", +1))
        self.assertEqual(P.after_ranking_key("VOLUME_WEIGHTED")[1:], P.AFTER_KEY)

    def test_seeds_that_disagree_on_the_measure_fall_back_and_say_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = [seed_run(Path(tmp), "A", 3, A_ROWS, "interval_count"),
                       seed_run(Path(tmp), "B", 2, B_ROWS, "volume_weighted")]
        winners = P.choose_winners(results)
        self.assertEqual(winners["after"]["seed"], "A")
        self.assertEqual(winners["ranking"], "INTERVAL_COUNT_MIXED_MEASURES")

    def test_eligibility_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = seed_run(Path(tmp), "B", 2, B_ROWS, "volume_weighted")
            a = seed_run(Path(tmp), "A", 3, A_ROWS, "volume_weighted")
        b["after_eligible"] = False  # e.g. parity failed
        self.assertEqual(P.choose_winners([a, b])["after"]["seed"], "A")


class TheSummaryRecordsTheRanking(unittest.TestCase):
    def test_the_portfolio_summary_names_the_ranking_used(self):
        source = (ROOT / "engine" / "RUN_PORTFOLIO.py").read_text()
        self.assertIn('"after_ranking_measure": winners["ranking"]', source)
        self.assertIn('"after_ranking": [k for k, _ in after_ranking_key(winners["ranking"])]', source)


if __name__ == "__main__":
    unittest.main()
