# © 2026 Omar Mokhtar. All rights reserved.
"""Phase W task 5: breaks planned automatically (owner, 2026-10-09: "if i did choose before breaks in use i need a
button to auto fill breaks for the selected schedule in case it doesnt have breaks in case it already has breaks we
needed it to be rescheduled breaks").

One click plans every break of the week inside the workbook's break rules (the Plan breaks page's own Suggest, day
after day) and saves a new version, checked like any other; the version clicked on stays as it is. A version that
already has breaks has them all planned again, and the result is put in use only when it is not worse (as many
intervals fully covered after breaks, no more broken rules): the owner's accepted rule, fixed before measuring."""
import html
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from webapp.break_plan import slots_for, suggest
from webapp.day import read_inputs
from webapp.programs import ProgramBook
from webapp.schedules import ScheduleBook, not_worse
from webapp.store import Store
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import make_app, sign_in, token, wait
from webapp.tests.test_schedules import REPO
from webapp.versions import DAYS, shift_span

WED = 3


class _Book(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        store.add_run("rrrrrrrrrrrr", cls.sara, "ready.xlsx", "READY", "DONE", program="SAKS NMG Tier 2",
                      week_start="2026-10-11")
        ScheduleBook(store, cls.base, REPO).ensure_ready(store.get_run("rrrrrrrrrrrr"), make_ready(cls.base / "up.xlsx"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.version = self.book.versions("rrrrrrrrrrrr")[0]
        self.rules = self.book.break_rules(self.version["id"])


class TheRule(unittest.TestCase):
    def test_not_worse_compares_covered_intervals_and_broken_rules(self):
        self.assertTrue(not_worse({"covered": 160, "broken": 2}, {"covered": 160, "broken": 2}))
        self.assertTrue(not_worse({"covered": 160, "broken": 2}, {"covered": 161, "broken": 1}))
        self.assertFalse(not_worse({"covered": 160, "broken": 2}, {"covered": 159, "broken": 2}))
        self.assertFalse(not_worse({"covered": 160, "broken": 2}, {"covered": 161, "broken": 3}))


class TheFill(_Book):
    def test_a_version_without_breaks_gets_every_break(self):
        found = self.book.auto_breaks(self.version["id"], self.sara, use=True)
        self.assertEqual((found["mode"], found["used"], found["empty"]), ("fill", True, 0))
        new = self.store.get_schedule(found["id"])
        self.assertNotEqual(new["id"], self.version["id"])
        self.assertTrue(new["in_use"])
        self.assertEqual(new["label"], f"Version {new['number']}: breaks planned automatically")
        week = json.loads(new["week"])
        for a in week["associates"]:
            for d, day in enumerate(DAYS):
                span = shift_span(a["days"][d])
                if span:
                    mine = [b for b in week["breaks"] if b["associate"] == a["name"] and b["day"] == day]
                    self.assertEqual(len(mine), len(slots_for(self.rules, span[1] - span[0])), (a["name"], day))
        self.assertEqual(found["placed"], len(week["breaks"]))
        self.assertEqual(json.loads(self.store.get_schedule(self.version["id"])["week"])["breaks"], [])
        view = self.book.view(found["id"])
        self.assertEqual({c["reason"] for c in view["changes"]}, {"Breaks planned automatically"})
        self.assertEqual([p["text"] for p in view["added"] if p["severity"] == "red"], [])
        self.assertIn(f"Breaks planned automatically for 7 days: {found['placed']} breaks placed for "
                      f"{len(week['associates'])} people, none left empty. Saved as {new['label']}, checked by the "
                      "validator, and in use for this week.", found["said"])

    def test_an_edited_draft_is_left_as_it_is(self):
        week = json.loads(self.version["week"])
        person = next(a for a in week["associates"] if shift_span(a["days"][WED]))
        draft = self.book.change(self.version["id"], self.sara, person["name"], "Wed", "OFF", "a day off")
        kept = self.store.get_schedule(draft)["week"]
        found = self.book.auto_breaks(draft, self.sara, use=False)
        self.assertNotEqual(found["id"], draft)
        self.assertEqual(self.store.get_schedule(draft)["week"], kept)
        self.assertFalse(self.store.get_schedule(found["id"])["in_use"])
        self.assertTrue(json.loads(self.store.get_schedule(found["id"])["week"])["breaks"])


class TheReplan(_Book):
    def setUp(self):
        super().setUp()
        week = json.loads(self.version["week"])  # a version with Wednesday's breaks only: a re-plan changes it
        wed = suggest(week, read_inputs(self.book.input_path("rrrrrrrrrrrr")), self.rules, WED, {})
        self.partial, _ = self.book.save_breaks(self.version["id"], self.sara, {"Wed": wed}, "by hand", use=True)

    def test_a_replan_that_is_worse_is_kept_but_not_used(self):
        with mock.patch("webapp.schedules.not_worse", return_value=False):
            found = self.book.auto_breaks(self.partial, self.sara, use=True)
        self.assertEqual((found["mode"], found["used"]), ("replan", False))
        self.assertNotEqual(found["id"], self.partial)
        self.assertFalse(self.store.get_schedule(found["id"])["in_use"])
        self.assertTrue(self.store.get_schedule(self.partial)["in_use"])
        self.assertIn("but not put in use", found["said"])
        self.assertIn("The schedule in use did not change.", found["said"])

    def test_a_replan_that_is_not_worse_is_used(self):
        with mock.patch("webapp.schedules.not_worse", return_value=True):
            found = self.book.auto_breaks(self.partial, self.sara, use=True)
        self.assertEqual((found["mode"], found["used"]), ("replan", True))
        self.assertTrue(self.store.get_schedule(found["id"])["in_use"])
        self.assertFalse(self.store.get_schedule(self.partial)["in_use"])
        self.assertIn("Breaks planned again for 7 days", found["said"])


class TheButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                       "program": cls.key, "week_start": "2026-10-11",
                                       "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                        content_type="multipart/form-data")
        cls.run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, cls.run_id, statuses=("DONE", "REJECTED", "FAILED"))
        cls.version = cls.app.extensions["schedules"].versions(cls.run_id)[0]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def page(self, url):
        return html.unescape(self.client.get(url).get_data(as_text=True))

    def test_the_buttons_say_fill_or_replan(self):
        before = self.page(f"/runs/{self.run_id}/schedules?v={self.version['id']}")
        self.assertIn("Plan breaks automatically", before)
        self.assertIn("This version has no breaks yet.", before)
        self.assertIn('name="use" value="1" checked', before)
        done = self.client.post(f"/schedules/{self.version['id']}/auto-breaks",
                                data={"csrf_token": token(self.client), "use": "1"}, follow_redirects=True)
        after = html.unescape(done.get_data(as_text=True))
        self.assertIn("Breaks planned automatically for 7 days", after)
        self.assertIn("Re-plan breaks automatically", after)
        week = self.page(f"/week?program={self.key}&week=2026-10-11")
        self.assertIn("Re-plan breaks automatically", week)
        self.assertIn("breaks planned automatically", week)  # the version shown is the one in use


if __name__ == "__main__":
    unittest.main()
