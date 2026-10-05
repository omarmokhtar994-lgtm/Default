"""Audit F-37: a workbook name with spaces lost every schedule of a multi-seed run.

Found on two real Colab runs (2026-10-05, "AE_AR_Choice_WEEKLY_INPUT - Copy.xlsx" and
"AE_IT_Choice_WEEKLY_INPUT - Copy - Copy.xlsx", QUICK, 2 seeds each). Every seed exited 0
with a validated, production-eligible schedule, and the run reported "no seed produced a
validated final schedule" and exit 1.

Cause: the production runner stores a run under safe_id(schedule id) - spaces become
"_" (RUN_UNIVERSAL_PRODUCTION.safe_id). The best-of-seeds runner then read
<seeds>/<raw id>_S<seed> (with the spaces), found no files, marked both seeds
unfinished and published nothing. The Colab wrapper derives the id from the file name
and reads the winner back the same raw way, so it would have missed it too.

Now: the wrapper and the portfolio use the runner's own folder name, and a seed that
exits 0 without its folder is reported as such, never as "no validated schedule".

Written to FAIL on the code before the fix and pass after.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
RUNNERS = next(p for p in (ROOT / "runners", REPO / "packages" / "rc9_2_2_production" / "runners") if p.exists())


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(ROOT / "engine"))
RUNNER = load(ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py", "runner_c41")
PORTFOLIO = load(ROOT / "engine" / "RUN_PORTFOLIO.py", "portfolio_c41")
NAMES = ["AE_AR_CHOICE_WEEKLY_INPUT - COPY", "AE_IT_CHOICE_WEEKLY_INPUT - COPY - COPY",
         "Voice week 42 (final)", "plain_name", "NMG EN&SP"]


class TheSeedIsFoundWhereTheRunnerWroteIt(unittest.TestCase):
    def test_run_seed_returns_the_folder_the_runner_creates(self):
        for name in NAMES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                seeds_root, logs = Path(tmp) / "seeds", Path(tmp) / "logs"
                seeds_root.mkdir()
                logs.mkdir()

                def fake_runner(cmd, **_kwargs):
                    # What RUN_UNIVERSAL_PRODUCTION does with --schedule-id.
                    sid = cmd[cmd.index("--schedule-id") + 1]
                    (seeds_root / RUNNER.safe_id(sid)).mkdir()
                    return 0

                with mock.patch.object(PORTFOLIO.subprocess, "call", side_effect=fake_runner):
                    run_dir, rc = PORTFOLIO.run_seed(9000, name, seeds_root, [], logs)
                self.assertEqual(rc, 0)
                self.assertTrue(run_dir.is_dir(), f"{run_dir} is not where the runner wrote")

    def test_the_portfolio_names_folders_exactly_as_the_runner_does(self):
        for name in NAMES + ["", "___", "a/b\\c", "Ü-name"]:
            self.assertEqual(PORTFOLIO.safe_id(name), RUNNER.safe_id(name), name)

    def test_a_seed_that_exits_0_without_its_folder_is_named_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = PORTFOLIO.read_seed_result(Path(tmp) / "missing_S9000", 0)
        self.assertEqual(result.get("problem"), "RUN_FOLDER_MISSING")
        source = (ROOT / "engine" / "RUN_PORTFOLIO.py").read_text()
        self.assertIn('"NO_VALIDATED_FINAL_SCHEDULE_RUN_FOLDER_MISSING"', source)


class TheColabWrapperUsesTheSameName(unittest.TestCase):
    def test_an_ad_hoc_workbook_name_becomes_the_runners_folder_name(self):
        wrapper = load(RUNNERS / "rc921_runner.py", "rc921_c41")
        for stem in ["AE_AR_Choice_WEEKLY_INPUT - Copy", "AE_IT_Choice_WEEKLY_INPUT - Copy - Copy"]:
            with self.subTest(stem=stem):
                sid = wrapper.ad_hoc_scenario_id(stem)
                self.assertEqual(sid, RUNNER.safe_id(sid))
                self.assertNotIn(" ", sid)
                self.assertTrue(sid.startswith("AE_"))


if __name__ == "__main__":
    unittest.main()
