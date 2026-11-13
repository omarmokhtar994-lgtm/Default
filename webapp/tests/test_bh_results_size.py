# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BH (owner, 2026-11-03: "the schedules are taking very very large size on the server, can't we remove unnecessary files?").
A finished run kept the engine's working files (a candidate pool checkpoint, skeleton checkpoints, raw outputs: about 17 of 28 MB on a
five-minute run, hundreds of MB on a long one), the engine's own split packages, and then a zip of all of it. Once a run has finished
(DONE or REVIEW) those are removed and the zip is made without them. What a person uses stays: the schedules, the outcome, the validator's
verdict, the audit, the log. A run that failed or was stopped keeps everything, because someone has to find out why."""
import json
import unittest
import zipfile

from webapp.tests.test_runs import REPO, client_for, make_app, run_id_of, upload, wait


def case_of(runs, run_id):
    return next(p for p in runs.results_dir(run_id).iterdir() if p.is_dir() and not p.name.startswith("_"))


class TheFinishedRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.runs = cls.app.extensions["runs"]

    def make(self, name):
        run_id = run_id_of(upload(self.client, name=name, program="AE/AR B2B", week_start="2026-10-11"))
        wait(self.store, run_id)
        return run_id

    def test_working_files_and_split_packages_are_gone_and_the_schedules_stay(self):
        run_id = self.make("LEAN_week.xlsx")
        self.assertEqual(self.store.get_run(run_id)["status"], "DONE")
        case = case_of(self.runs, run_id)
        self.assertFalse((case / "debug").exists())
        self.assertFalse((case / "packages").exists())
        self.assertTrue(any(case.glob("*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx")))
        self.assertTrue(any(case.glob("*BEST_BEFORE_BREAKS_SCHEDULE.xlsx")))
        self.assertTrue(any(case.glob("*solver_audit.json")))
        self.assertIsNotNone(self.runs.final_schedule(run_id))

    def test_the_download_is_made_without_them_and_keeps_the_log(self):
        run_id = self.make("LEAN_download.xlsx")
        with zipfile.ZipFile(self.runs.zip_path(run_id)) as archive:
            names = archive.namelist()
        self.assertFalse([n for n in names if "/debug/" in n or "/packages/" in n], names)
        self.assertIn("run.log", names)
        self.assertTrue([n for n in names if n.endswith("BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx")])

    def test_the_log_says_what_was_removed(self):
        run_id = self.make("LEAN_log.xlsx")
        self.assertIn("removed", self.runs.log_path(run_id).read_text(encoding="utf-8").lower())

    def test_a_run_that_failed_keeps_everything(self):
        run_id = self.make("LEANFAILS_week.xlsx")
        self.assertEqual(self.store.get_run(run_id)["status"], "FAILED")
        case = case_of(self.runs, run_id)
        self.assertTrue((case / "debug" / "CANDIDATE_POOL_CHECKPOINT.json").is_file())
        self.assertTrue(any((case / "packages").iterdir()))

    def test_runs_finished_before_this_existed_are_slimmed_once(self):
        run_id = self.make("plain_week.xlsx")  # no working files from the fake runner
        case = case_of(self.runs, run_id)
        (case / "debug").mkdir()
        (case / "debug" / "SKELETON_CHECKPOINTS.json").write_bytes(b"y" * 120_000)
        (case / "packages").mkdir()
        (case / "packages" / "x_01_PRODUCTION_ONLY.zip").write_bytes(b"z" * 30_000)
        self.runs._zip(run_id)  # the old zip held them
        before = self.runs.zip_path(run_id).stat().st_size
        freed = self.runs.slim_finished_runs()
        self.assertGreaterEqual(freed, 150_000)
        self.assertFalse((case / "debug").exists())
        self.assertFalse((case / "packages").exists())
        with zipfile.ZipFile(self.runs.zip_path(run_id)) as archive:
            self.assertFalse([n for n in archive.namelist() if "/debug/" in n or "/packages/" in n])
        self.assertLessEqual(self.runs.zip_path(run_id).stat().st_size, before)
        self.assertEqual(self.runs.slim_finished_runs(), 0)  # nothing left to remove: no second pass of work

    def test_an_expired_or_running_run_is_left_alone(self):
        run_id = self.make("LEAN_expired.xlsx")
        self.store.update_run(run_id, status="EXPIRED")
        case = case_of(self.runs, run_id) if self.runs.results_dir(run_id).is_dir() else None
        self.assertEqual(self.runs.slim_finished_runs(), 0)
        self.store.update_run(run_id, status="DONE")


if __name__ == "__main__":
    unittest.main()
