"""DEEP / OVERNIGHT run as seed portfolios of 1 h QUICK runs.

Registered measurement (evidence/seed_portfolio_ab/RESULT.txt, rule
PREREGISTERED_RULE.txt written before the runs): best of 4 x 3600 s QUICK
seeds (E) against one 14,400 s DEEP run (F), same frozen engine, Chat, Voice,
NMG_SP, H1. Summed after-breaks target E 692, F 370: F tied E where it
finished (Voice 248, NMG_SP 122) and produced no schedule on Chat and H1
(killed at 13.0 / 13.9 GB in joint refinement); no before-breaks sheet lower
under E. The rule then makes DEEP = best of 4 x 3600 s and OVERNIGHT = best of
6 x 3600 s.

These tests pin that mapping in both entry points (engine/RUN_PORTFOLIO.py
--preset and the Colab runner's --mode), the overrides (--seeds count,
--time-limit per seed, --single-run for the old long run), and that QUICK and
SMOKE are unchanged.
"""
import argparse
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PF = load("portfolio_presets", ROOT / "engine" / "RUN_PORTFOLIO.py")
_runner_candidates = [ROOT / "runners" / "rc921_runner.py",
                      REPO / "packages" / "rc9_2_2_production" / "runners" / "rc921_runner.py"]
RUNNER_PATH = next((p for p in _runner_candidates if p.exists()), None)
RUNNER = load("rc921_runner_presets", RUNNER_PATH) if RUNNER_PATH else None


class PortfolioPreset(unittest.TestCase):
    def run_main(self, argv):
        calls = []

        def fake_run_seed(seed, schedule_id, seeds_root, passthrough, log_dir):
            calls.append((seed, list(passthrough)))
            d = Path(seeds_root) / f"{schedule_id}_S{seed}"
            d.mkdir(parents=True)
            return d

        saved = PF.run_seed
        PF.run_seed = fake_run_seed
        try:
            rc = PF.main(argv + ["--output-root", tempfile.mkdtemp(), "--schedule-id", "CASE"])
        finally:
            PF.run_seed = saved
        return rc, calls

    def test_deep_is_four_one_hour_quick_seeds(self):
        _, calls = self.run_main(["--preset", "DEEP", "--input", "x.xlsx"])
        self.assertEqual([s for s, _ in calls], [9000, 9001, 9002, 9003])
        for _, passthrough in calls:
            self.assertEqual(passthrough, ["--input", "x.xlsx", "--mode", "QUICK", "--time-limit", "3600"])

    def test_overnight_is_six(self):
        _, calls = self.run_main(["--preset", "OVERNIGHT"])
        self.assertEqual(len(calls), 6)

    def test_seed_count_can_be_overridden(self):
        _, calls = self.run_main(["--preset", "DEEP", "--seeds", "3"])
        self.assertEqual(len(calls), 3)

    def test_the_preset_owns_mode_and_time_limit(self):
        for clash in (["--mode", "DEEP"], ["--time-limit", "14400"]):
            with self.assertRaises(SystemExit):
                self.run_main(["--preset", "DEEP", *clash])

    def test_without_a_preset_nothing_changes(self):
        _, calls = self.run_main(["--mode", "QUICK"])
        self.assertEqual(calls, [(9000, ["--mode", "QUICK"])])


@unittest.skipIf(RUNNER is None, "Colab runner not present")
class ColabRunnerDepthPlan(unittest.TestCase):
    def args(self, **kw):
        base = dict(mode=None, seeds=0, single_run=False, time_limit=0)
        base.update(kw)
        return argparse.Namespace(**base)

    ROW = {"scenario_id": "X", "mode": "DEEP", "time_limit_sec": 14400}

    def test_deep_and_overnight_are_seed_portfolios(self):
        self.assertEqual(RUNNER.depth_plan(self.args(mode="DEEP"), self.ROW), ("QUICK", 3600, 4))
        self.assertEqual(RUNNER.depth_plan(self.args(mode="OVERNIGHT"), self.ROW), ("QUICK", 3600, 6))

    def test_the_manifest_default_depth_follows_the_same_rule(self):
        self.assertEqual(RUNNER.depth_plan(self.args(), self.ROW), ("QUICK", 3600, 4))

    def test_overrides(self):
        self.assertEqual(RUNNER.depth_plan(self.args(mode="DEEP", seeds=2), self.ROW), ("QUICK", 3600, 2))
        self.assertEqual(RUNNER.depth_plan(self.args(mode="DEEP", time_limit=1800), self.ROW), ("QUICK", 1800, 4))
        self.assertEqual(RUNNER.depth_plan(self.args(mode="DEEP", single_run=True), self.ROW), ("DEEP", 14400, 1))
        self.assertEqual(RUNNER.depth_plan(self.args(mode="OVERNIGHT", single_run=True), self.ROW), ("OVERNIGHT", 21600, 1))
        self.assertEqual(RUNNER.depth_plan(self.args(single_run=True), self.ROW), ("DEEP", 14400, 1))

    def test_quick_and_smoke_are_unchanged(self):
        self.assertEqual(RUNNER.depth_plan(self.args(mode="QUICK"), self.ROW), ("QUICK", 3600, 1))
        self.assertEqual(RUNNER.depth_plan(self.args(mode="QUICK", seeds=2), self.ROW), ("QUICK", 3600, 2))
        self.assertEqual(RUNNER.depth_plan(self.args(mode="SMOKE"), self.ROW), ("SMOKE", 900, 1))

    def test_run_one_sends_the_planned_mode_to_the_portfolio(self):
        captured = {}

        def fake_portfolio(root, results_root, row, args, command, budget, seeds):
            captured.update(command=command, budget=budget, seeds=seeds)
            return {}

        saved = RUNNER.run_portfolio
        RUNNER.run_portfolio = fake_portfolio
        try:
            args = argparse.Namespace(mode="DEEP", seeds=0, single_run=False, time_limit=0, num_workers=4,
                                      stage=None, language_working_window=None, resume=False, parallel=0)
            RUNNER.run_one(Path("."), Path(tempfile.mkdtemp()), dict(self.ROW, input="x.xlsx"), args)
        finally:
            RUNNER.run_portfolio = saved
        command = captured["command"]
        self.assertEqual(command[command.index("--mode") + 1], "QUICK")
        self.assertEqual(command[command.index("--time-limit") + 1], "3600")
        self.assertEqual((captured["budget"], captured["seeds"]), (3600, 4))


if __name__ == "__main__":
    unittest.main(verbosity=2)
