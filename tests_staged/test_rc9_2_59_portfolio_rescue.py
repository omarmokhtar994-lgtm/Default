"""Phase AY (owner, 2026-10-23: a real Quick run was stopped at its time cap after both seeds had finished valid schedules, and
the run said "Not approved" with nothing kept): when the cap is hit, the runner keeps the seeds that had finished.

RUN_PORTFOLIO.py --collect-only reads the seed folders that are already there and does what the portfolio does after its seeds:
choose the winners, publish them, write PORTFOLIO_SUMMARY. A seed counts as finished only when the engine wrote its last file,
UNIVERSAL_RUN_STATUS.json with the top-level copies in it, and its return code is the one in that file. A seed that was
stopped part way has no such file and is ignored; every other rule for a winner (validator PASS, 0 hard failures, parity PASS,
production_eligible TRUE) is unchanged. The Colab runner calls it when its own timeout fires (rc921_runner.run_portfolio).
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_rc9_2_18_seed_portfolio import PF, make_run  # noqa: E402

SCHEDULE = "TEST_WEEK"


def seed_folder(case_root, seed, after_target, best_before, finished=True, **kw):
    """A seed's run folder as the engine leaves it; ``finished`` says whether its last file was written."""
    d = make_run(case_root / "seeds", f"{SCHEDULE}_S{seed}", after_target, best_before, **kw)
    if finished:
        (d / "UNIVERSAL_RUN_STATUS.json").write_text(json.dumps({"return_code": 0, "top_level_copies": ["a.xlsx"]}))
    return d


class TheFinishMarker(unittest.TestCase):
    def test_a_seed_is_finished_when_the_engine_wrote_its_last_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = seed_folder(Path(tmp), 9000, 170, 190)
            self.assertEqual(PF.seed_return_code(d), 0)

    def test_the_return_code_is_the_one_the_engine_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = seed_folder(Path(tmp), 9000, 170, 190)
            (d / "UNIVERSAL_RUN_STATUS.json").write_text(json.dumps({"return_code": 2, "top_level_copies": []}))
            self.assertEqual(PF.seed_return_code(d), 2)

    def test_a_seed_stopped_part_way_has_no_return_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = seed_folder(Path(tmp), 9000, 170, 190, finished=False)
            self.assertIsNone(PF.seed_return_code(d))
            # the engine writes the status before packaging and again after: the first one is not the end
            (d / "UNIVERSAL_RUN_STATUS.json").write_text(json.dumps({"return_code": 0}))
            self.assertIsNone(PF.seed_return_code(d))
            (d / "UNIVERSAL_RUN_STATUS.json").write_text("{not json")
            self.assertIsNone(PF.seed_return_code(d))
        self.assertIsNone(PF.seed_return_code(Path("/no/such/folder")))


class TheCollectOnlyRun(unittest.TestCase):
    def collect(self, tmp, seeds):
        return PF.main(["--seeds", str(seeds), "--base-seed", "9000", "--output-root", str(tmp),
                        "--schedule-id", SCHEDULE, "--collect-only", "--mode", "QUICK"])

    def test_the_best_seed_that_finished_wins_and_the_one_stopped_part_way_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / SCHEDULE
            seed_folder(case, 9000, 170, 190)
            seed_folder(case, 9001, 999, 999, finished=False)  # better figures, but it never finished
            self.assertEqual(self.collect(tmp, 2), 0)
            summary = json.loads((case / "PORTFOLIO_SUMMARY.json").read_text())
            self.assertEqual(summary["after_breaks_winner_seed"], 9000)
            self.assertTrue(summary["collected_after_timeout"])
            self.assertEqual([r["seed"] for r in summary["runs"] if r["finished"] and r["after_eligible"]], [9000])
            self.assertTrue(list((case / "PORTFOLIO_BEST").glob("AFTER_BREAKS_BEST__S9000__*")))

    def test_two_finished_seeds_choose_as_the_portfolio_does(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / SCHEDULE
            seed_folder(case, 9000, 170, 196)
            seed_folder(case, 9001, 182, 188)
            self.assertEqual(self.collect(tmp, 2), 0)
            summary = json.loads((case / "PORTFOLIO_SUMMARY.json").read_text())
            self.assertEqual((summary["after_breaks_winner_seed"], summary["before_breaks_winner_seed"]), (9001, 9000))

    def test_an_unvalidated_seed_that_finished_still_never_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / SCHEDULE
            seed_folder(case, 9000, 999, 999, validator="FAIL")
            self.assertEqual(self.collect(tmp, 1), 1)
            summary = json.loads((case / "PORTFOLIO_SUMMARY.json").read_text())
            self.assertIsNone(summary["after_breaks_winner_seed"])

    def test_no_seed_finished_is_a_failure_with_no_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / SCHEDULE
            for seed in (9000, 9001, 9002, 9003):
                seed_folder(case, seed, 170, 190, finished=False)
            self.assertEqual(self.collect(tmp, 4), 1)
            self.assertIsNone(json.loads((case / "PORTFOLIO_SUMMARY.json").read_text())["after_breaks_winner_seed"])

    def test_four_and_six_seed_portfolios_keep_the_best_of_the_finished_ones(self):
        for seeds, finished in ((4, (0, 1, 2)), (6, (0, 1, 2, 3, 4))):
            with self.subTest(seeds=seeds), tempfile.TemporaryDirectory() as tmp:
                case = Path(tmp) / SCHEDULE
                for i in range(seeds):
                    seed_folder(case, 9000 + i, 150 + i, 190, finished=i in finished)
                self.assertEqual(self.collect(tmp, seeds), 0)
                winner = json.loads((case / "PORTFOLIO_SUMMARY.json").read_text())["after_breaks_winner_seed"]
                self.assertEqual(winner, 9000 + max(finished))  # the last seed (the best figures) never finished

    def test_a_normal_portfolio_does_not_say_it_was_collected(self):
        source = (ROOT / "engine" / "RUN_PORTFOLIO.py").read_text()
        self.assertTrue('"collected_after_timeout": bool(args.collect_only)' in source)


def load_runner():
    path = ROOT / "runners" / "rc921_runner.py"
    if not path.exists():
        path = REPO / "packages" / "rc9_2_2_production" / "runners" / "rc921_runner.py"
    spec = importlib.util.spec_from_file_location("rc921_runner_rescue", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()


class TheRunnerRescuesATimedOutPortfolio(unittest.TestCase):
    def run_portfolio(self, tmp, seeds, finished):
        results = Path(tmp) / "results"
        case = results / "_seeds" / SCHEDULE
        for i in range(seeds):
            seed_folder(case, 9000 + i, 150 + i, 190, finished=i in finished)
        args = argparse.Namespace(parallel=2, overwrite=False)
        row = {"scenario_id": SCHEDULE, "solver_random_seed": 9000}
        command = [sys.executable, "-u", "RUN_UNIVERSAL_PRODUCTION.py", "--input", "x.xlsx", "--output-root", str(results),
                   "--schedule-id", SCHEDULE, "--mode", "QUICK", "--time-limit", "3600", "--num-workers", "4"]

        def timed_out(cmd, logfile, timeout):
            Path(logfile).write_text("portfolio output so far\n")
            raise subprocess.TimeoutExpired(cmd, timeout)

        with mock.patch.object(RUNNER, "_run_engine", timed_out), mock.patch.object(RUNNER, "available_memory_mb", lambda: None):
            return RUNNER.run_portfolio(REPO, results, row, args, command, 3600, seeds), results

    def test_the_best_finished_seed_is_published_and_the_record_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            record, results = self.run_portfolio(tmp, 2, finished=(0, 1))
            self.assertEqual(record["exit_code"], 0)
            self.assertTrue(record["rescued_after_timeout"])
            self.assertEqual((record["seeds"], record["seeds_finished"]), (2, 2))
            self.assertEqual(record["after_breaks_winner_seed"], 9001)
            self.assertTrue((results / SCHEDULE).is_dir())  # published as the scenario, as a normal run does
            self.assertIn("[rescue]", (results / f"{SCHEDULE}.log").read_text())

    def test_one_finished_seed_of_two_is_enough(self):
        with tempfile.TemporaryDirectory() as tmp:
            record, _ = self.run_portfolio(tmp, 2, finished=(0,))
            self.assertEqual((record["exit_code"], record["seeds_finished"], record["after_breaks_winner_seed"]), (0, 1, 9000))

    def test_with_no_finished_seed_the_timeout_stands(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.run_portfolio(tmp, 2, finished=())

    def test_a_run_that_ends_in_time_is_not_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results"
            case = results / "_seeds" / SCHEDULE
            for i in range(2):
                seed_folder(case, 9000 + i, 150 + i, 190)

            def in_time(cmd, logfile, timeout):
                subprocess.run([*cmd, "--collect-only"], check=True, capture_output=True)  # stands in for the portfolio's own end
                return 0

            args = argparse.Namespace(parallel=2, overwrite=False)
            command = [sys.executable, "-u", "x.py", "--input", "x.xlsx", "--output-root", str(results),
                       "--schedule-id", SCHEDULE, "--mode", "QUICK", "--time-limit", "3600", "--num-workers", "4"]
            with mock.patch.object(RUNNER, "_run_engine", in_time), mock.patch.object(RUNNER, "available_memory_mb", lambda: None):
                record = RUNNER.run_portfolio(REPO, results, {"scenario_id": SCHEDULE}, args, command, 3600, 2)
            self.assertFalse(record["rescued_after_timeout"])


if __name__ == "__main__":
    unittest.main()
