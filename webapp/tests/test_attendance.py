# © 2026 Omar Mokhtar. All rights reserved.
"""Phase N task 4: attendance and actual breaks kept per program and shift date.

The day is read from the version in use for its week (the tool's own version,
with a note, when none is). Statuses and break moves are checked before they
are kept, and every one is logged with who and when."""
import shutil
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

from webapp.attendance import DayBook
from webapp.day import BreakRefused
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.versions import shift_span
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED = date(2026, 10, 14)  # the run's week starts Sunday 11 October
SAT = date(2026, 10, 17)


class TheAttendance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """One run with its tool version (the validator runs once); each test gets a copy."""
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        store.add_run("aaaaaaaaaaaa", cls.sara, "AR_week.xlsx", "QUICK", "DONE", program="AE/AR B2B",
                      week_start="2026-10-11")
        ScheduleBook(store, cls.base, REPO).ensure(store.get_run("aaaaaaaaaaaa"), INPUT, AFTER, None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.tool = self.book.versions("aaaaaaaaaaaa")[0]
        self.days = DayBook(self.store, self.book)

    def lane(self, page, name):
        return next(l for l in page["view"]["lanes"] if l["name"] == name)

    def test_tool_version_with_a_note_until_one_is_in_use(self):
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual(page["version"]["id"], self.tool["id"])
        self.assertIn("No version is marked in use", page["note"])
        draft = self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "10:00 - 19:00", "swap")
        self.book.set_in_use(draft, self.sara)
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual((page["version"]["id"], page["note"]), (draft, ""))
        self.assertEqual(self.lane(page, "Associate 001")["segments"][0]["label"], "10:00 - 19:00")
        self.assertEqual(self.days.programs(), ["AE/AR B2B"])
        self.assertIsNone(self.days.page("AE/AR B2B", date(2026, 11, 4)))  # no schedule that week

    def test_status_kept_and_logged(self):
        before = self.days.page("AE/AR B2B", WED)["view"]["tiles"]
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Unplanned leave", self.sara)
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual(page["view"]["tiles"]["absent"], before["absent"] + 1)
        self.assertEqual(self.lane(page, "Associate 001")["segments"][0]["status"], "Unplanned leave")
        self.assertEqual([(e["by_name"], e["associate"], e["what"]) for e in page["log"]],
                         [("Sara", "Associate 001", "Unplanned leave")])
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Present", self.sara)
        self.assertEqual(self.days.page("AE/AR B2B", WED)["view"]["tiles"]["absent"], before["absent"])

    def test_timed_statuses_need_times_inside_the_shift(self):
        with self.assertRaises(ValueError):  # a late arrival needs the time they arrived
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Late", self.sara)
        with self.assertRaises(ValueError):  # Wednesday is 12:00 - 21:00
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Late", self.sara, end="22:00")
        with self.assertRaises(ValueError):
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Meeting", self.sara, start="15:00", end="14:00")
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Late", self.sara, end="13:00")
        seg = self.lane(self.days.page("AE/AR B2B", WED), "Associate 001")["segments"][0]
        self.assertEqual((seg["status"], seg["away"]), ("Late", (12 * 60, 13 * 60)))
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Meeting", self.sara, start="15:00", end="16:00")
        self.assertEqual(self.lane(self.days.page("AE/AR B2B", WED), "Associate 001")["segments"][0]["away"],
                         (15 * 60, 16 * 60))

    def test_unknown_status_or_person_refused(self):
        with self.assertRaises(ValueError):
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Holiday", self.sara)
        with self.assertRaises(ValueError):
            self.days.set_status("AE/AR B2B", WED, "Nobody", "Sick", self.sara)
        with self.assertRaises(ValueError):  # Associate 001 is off on Saturday
            self.days.set_status("AE/AR B2B", SAT, "Associate 001", "Sick", self.sara)
        self.assertEqual(self.days.page("AE/AR B2B", WED)["log"], [])

    def test_break_moved_then_back_to_plan(self):
        # Wednesday 12:00 - 21:00: Break 1 13:45, Lunch 16:30, Break 2 19:30
        self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, "17:05", self.sara)
        page = self.days.page("AE/AR B2B", WED)
        lunch = self.lane(page, "Associate 001")["segments"][0]["breaks"][1]
        self.assertEqual((lunch["kind"], lunch["start"], lunch["planned_start"], lunch["moved"]),
                         ("Lunch", 17 * 60 + 5, 16 * 60 + 30, True))
        self.assertEqual(page["log"][-1]["what"], "Lunch moved 16:30 to 17:05")
        self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, None, self.sara)
        page = self.days.page("AE/AR B2B", WED)
        lunch = self.lane(page, "Associate 001")["segments"][0]["breaks"][1]
        self.assertEqual((lunch["start"], lunch["moved"]), (16 * 60 + 30, False))
        self.assertEqual(page["log"][-1]["what"], "Lunch back to plan (16:30)")

    def test_refused_break_is_not_kept(self):
        for at in ("17:07", "20:50", "19:30", "bad"):  # not a 5-minute step, past 21:00, on Break 2, not a time
            with self.assertRaises((BreakRefused, ValueError)):
                self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, at, self.sara)
        self.assertFalse(any(b["moved"] for b in self.lane(self.days.page("AE/AR B2B", WED),
                                                           "Associate 001")["segments"][0]["breaks"]))
        self.assertEqual(self.days.page("AE/AR B2B", WED)["log"], [])

    def test_a_move_that_no_longer_matches_the_plan_is_reported_not_applied(self):
        self.store.set_actual_break(program="AE/AR B2B", shift_date=WED.isoformat(), associate="Associate 001",
                                    idx=1, kind="Break 9", start=16 * 60, user_id=self.sara)
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual(page["stale"], 1)
        self.assertFalse(self.lane(page, "Associate 001")["segments"][0]["breaks"][1]["moved"])

    def test_overnight_status_belongs_to_the_shift_date(self):
        tue = date(2026, 10, 13)
        person = next(a for a in self.book.view(self.tool["id"])["week"]["associates"]
                      if (shift_span(a["days"][2]) or (0, 0))[1] > 1440)  # Tuesday night into Wednesday
        self.days.set_status("AE/AR B2B", tue, person["name"], "Sick", self.sara)
        carry = [s for s in self.lane(self.days.page("AE/AR B2B", WED), person["name"])["segments"] if s["offset"] == -1]
        self.assertEqual(carry[0]["status"], "Sick")

    def test_day_records_deleted_after_13_months(self):
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.sara)
        self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, "17:05", self.sara)
        self.assertEqual(self.days.cleanup(now=time.time() + 300 * 86400), 0)
        # the status, the break move and their two log lines
        self.assertEqual(self.days.cleanup(now=time.mktime((2027, 11, 20, 0, 0, 0, 0, 0, -1))), 4)
        self.assertEqual(self.store.list_attendance("AE/AR B2B", [WED.isoformat()]), [])


if __name__ == "__main__":
    unittest.main()
