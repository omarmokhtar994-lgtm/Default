# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AO (owner, 2026-10-20: leave "can be for future dates even if schedule was not raised ... it can be considered
automatically moving forward while building the schedule once we upload the sheet ... but if failed to be a warning not
to stop the schedule building like if associate name for example is not part of the roster uploaded ... or at least to
store them to be exported for that week later on from export"; answer: B). Leave approved for a week with no schedule
is kept; when that week's schedule is kept, the approved days the person works are marked Leave in a new version set in
use, a name not on the roster or a day already off is said and never stops anything, and Exports lists approved leave."""
import io
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp.programs import ProgramBook
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait

WED = date(2026, 10, 28)     # Wednesday of the week of 25 Oct
WORKS, OFF = "Associate 021", "Associate 009"   # 08:00 - 17:00 on Wednesdays; off on Wednesdays (the ready fixture)


class LeaveBeforeTheWeekIsPlanned(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.omar = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        for name in (WORKS, OFF, "Associate 999"):
            cls.store.add_leave(program=cls.key, associate=name, user_id=cls.omar, kind="Planned leave",
                                first_day=WED.isoformat(), last_day=WED.isoformat(), note="", status="approved",
                                outcome="Wed 28 Oct has no schedule yet: it is kept, and marked Leave when that week's schedule is uploaded.",
                                rta_id=cls.omar)
        client = cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": cls.key,
                                   "week_start": "2026-10-25",
                                   "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                    content_type="multipart/form-data")
        cls.run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, cls.run_id, statuses=("DONE", "REJECTED", "FAILED"))
        cls.days, cls.leave = cls.app.extensions["days"], cls.app.extensions["leave"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def cell(self, name):
        return dict(self.days.roster(self.key, WED)).get(name, "")

    def test_the_run_still_finishes(self):
        self.assertEqual(self.store.get_run(self.run_id)["status"], "DONE")

    def test_the_approved_day_a_person_works_is_marked_leave_in_a_version_in_use(self):
        self.assertEqual(self.cell(WORKS), "Leave")
        version = self.days.version(self.key, WED)[0]
        self.assertTrue(version["in_use"])
        self.assertIn("Approved leave", version["label"])

    def test_a_day_off_is_left_and_a_name_not_on_the_roster_only_warns(self):
        self.assertEqual(self.cell(OFF), "OFF")
        said = self.leave.last_applied(self.run_id)
        self.assertEqual([(a["name"], a["dates"]) for a in said["applied"]], [(WORKS, ["2026-10-28"])])
        self.assertEqual([s["name"] for s in said["skipped"]], ["Associate 999"])
        self.assertIn("not on the schedule", said["skipped"][0]["why"])
        self.assertEqual([n["name"] for n in said["notes"]], [OFF])

    def test_running_it_again_changes_nothing(self):
        before = len(self.store.list_schedules(run_id=self.run_id))
        self.leave.apply_waiting(self.store.get_run(self.run_id))
        self.assertEqual(len(self.store.list_schedules(run_id=self.run_id)), before)

    def test_the_schedules_page_says_what_was_applied_and_what_was_not(self):
        page = self.client.get(f"/runs/{self.run_id}/schedules").get_data(as_text=True)
        self.assertIn("Approved leave and this schedule", page)
        self.assertIn(f"<b>{WORKS}</b>: Leave on 28 Oct", page)
        self.assertIn("Associate 999 is not on the schedule uploaded", page)

    def test_exports_lists_approved_leave(self):
        from webapp.exports import TABLES
        rows = list(TABLES["leave"](self.store, self.days, None, date(2026, 10, 25), date(2026, 10, 31), None, None,
                                    "interval"))
        self.assertEqual(rows[0][:4], ["Program", "Name", "Kind", "First day"])
        self.assertEqual(sorted(r[1] for r in rows[1:]), sorted([WORKS, OFF, "Associate 999"]))


if __name__ == "__main__":
    unittest.main()
