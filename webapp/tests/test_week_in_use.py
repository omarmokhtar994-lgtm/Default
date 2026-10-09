# © 2026 Omar Mokhtar. All rights reserved.
"""Phase W task 3: which schedule counts for a week (owner, 2026-10-09: two schedules for the same LOB and week).

The schedule in use counts everywhere: the RTA, the Week page, the program's history and analytics. With none in
use the newest schedule counts (an engine run's "after breaks" before its own "before breaks"), and an upload for a
week that already has schedules says so, before and after it is sent."""
import html
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.analytics import program_weeks
from webapp.attendance import pick_version
from webapp.programs import ProgramBook
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait


def version(vid, run_id, kind, created, in_use=0, week="2026-10-11"):
    return {"id": vid, "run_id": run_id, "kind": kind, "created": created, "in_use": in_use, "week_start": week}


class ThePick(unittest.TestCase):
    def test_the_newest_schedule_counts_when_none_is_in_use(self):
        engine = [version(1, "run-a", "tool_after", 100.0), version(2, "run-a", "tool_before", 100.4)]
        uploaded = [version(3, "run-b", "ready", 200.0)]
        chosen, note = pick_version(engine + uploaded)
        self.assertEqual(chosen["id"], 3)
        self.assertIn("uploaded ready schedule", note)
        chosen, _ = pick_version(uploaded + engine + [version(4, "run-c", "tool_after", 300.0)])
        self.assertEqual(chosen["id"], 4)

    def test_one_runs_after_breaks_beats_its_before_breaks(self):
        chosen, note = pick_version([version(1, "run-a", "tool_after", 100.0), version(2, "run-a", "tool_before", 100.4)])
        self.assertEqual(chosen["id"], 1)
        self.assertIn("tool's own schedule", note)

    def test_the_one_in_use_still_wins(self):
        chosen, note = pick_version([version(1, "run-a", "tool_after", 100.0, in_use=1),
                                     version(3, "run-b", "ready", 200.0)])
        self.assertEqual((chosen["id"], note), (1, ""))


class TheAnalytics(unittest.TestCase):
    def test_analytics_follow_the_schedule_in_use(self):
        metrics = json.dumps({"active": 168, "fully_covered": 160, "associates": 30})
        runs = [{"id": "old", "program": "SAKS", "week_start": "2026-10-11", "status": "DONE", "finished": 100,
                 "created": 90, "metrics": metrics, "workbook": "a.xlsx"},
                {"id": "new", "program": "SAKS", "week_start": "2026-10-11", "status": "DONE", "finished": 200,
                 "created": 190, "metrics": metrics, "workbook": "b.xlsx"}]
        self.assertEqual(program_weeks(runs)["SAKS"][0]["run_id"], "new")  # none in use: the latest, as before
        row = program_weeks(runs, {("SAKS", "2026-10-11"): "old"})["SAKS"][0]
        self.assertEqual((row["run_id"], row["runs_that_week"], row["in_use"]), ("old", 2, True))


class TheWeekAndTheUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.omar = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.first = cls.upload("week_v1.xlsx")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    @classmethod
    def upload(cls, name):
        got = cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                             "program": cls.key, "week_start": "2026-10-11",
                                             "workbook": (io.BytesIO(cls.ready.read_bytes()), name)},
                              content_type="multipart/form-data", follow_redirects=True)
        run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, run_id, statuses=("DONE", "REJECTED", "FAILED"))
        return run_id, html.unescape(got.get_data(as_text=True))

    def test_the_week_page_shows_an_uploaded_schedule(self):
        page = html.unescape(self.client.get(f"/week?program={self.key}&week=2026-10-11").get_data(as_text=True))
        self.assertNotIn("No finished run", page)
        self.assertIn("Achieved every", page)
        self.assertRegex(page, r"From the schedule in use|No version is marked in use for this week")
        self.assertIn("week_v1.xlsx", page)

    def test_the_week_page_says_who_put_it_in_use(self):
        book = self.app.extensions["schedules"]
        book.set_in_use(book.versions(self.first[0])[0]["id"], self.omar)
        page = html.unescape(self.client.get(f"/week?program={self.key}&week=2026-10-14").get_data(as_text=True))
        self.assertRegex(page, r"From the schedule in use: <a [^>]+>Ready schedule \(uploaded\)</a>, workbook "
                               r"week_v1\.xlsx, set in use by Omar on \w{3} \d\d \w{3}\.")

    def test_the_upload_says_the_week_already_has_schedules(self):
        said = self.client.get(f"/runs/week-check?program={self.key}&week=2026-10-11").get_json()
        self.assertEqual(said["count"], 1)
        self.assertIn("1 schedule for the week of Sun 11 Oct", said["text"])
        self.assertIn("None is in use; the RTA reads the newest.", said["text"])
        book = self.app.extensions["schedules"]
        book.set_in_use(book.versions(self.first[0])[0]["id"], 1)
        said = self.client.get(f"/runs/week-check?program={self.key}&week=2026-10-11").get_json()
        self.assertIn("In use: Ready schedule (uploaded) from week_v1.xlsx.", said["text"])
        _, page = self.upload("week_v2.xlsx")
        self.assertIn("for the week of Sun 11 Oct. In use: Ready schedule (uploaded) from week_v1.xlsx. Yours is "
                      "kept next to it.", page)
        nothing = self.client.get(f"/runs/week-check?program={self.key}&week=2026-11-01").get_json()
        self.assertEqual((nothing["count"], nothing["text"]), (0, ""))


if __name__ == "__main__":
    unittest.main()
