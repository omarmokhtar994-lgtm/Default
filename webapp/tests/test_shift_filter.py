# © 2026 Omar Mokhtar. All rights reserved.
"""Phase W task 4: the RTA Timeline by shift start (owner, 2026-10-09: "a filter RTA Timeline to filter by shift so
we can mark attendance per shift easily"), and a note for records of people who are not in the schedule in use.

Chips group the day's people by the start of their own shift that day (last night's people under "From
yesterday"), each with how many are late, off and in aux; the filter is in the address, so the page that reloads
after each attendance change keeps it."""
import html
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from webapp.attendance import DayBook
from webapp.day import shift_groups
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_runs import make_app, sign_in
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED = date(2026, 10, 14)
PROGRAM = "AE/AR B2B"


class _Day(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        store.add_run("aaaaaaaaaaaa", cls.sara, "AR_week.xlsx", "QUICK", "DONE", program=PROGRAM,
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
        self.days = DayBook(self.store, ScheduleBook(self.store, self.data, REPO))


class TheRecordsNotShown(_Day):
    def test_records_of_people_not_in_the_schedule_are_said(self):
        # kept from an earlier schedule of the week, in which these two were working
        self.store.set_attendance(program=PROGRAM, shift_date=WED.isoformat(), associate="Associate 041",
                                  status="Sick", from_min=None, to_min=None, billable=0, user_id=self.sara)
        self.store.set_attendance(program=PROGRAM, shift_date=WED.isoformat(), associate="Associate 042",
                                  status="Late", from_min=None, to_min=560, billable=0, user_id=self.sara)
        self.days.set_status(PROGRAM, WED, "Associate 001", "Late", self.sara, end="13:00")  # on the schedule
        page = self.days.page(PROGRAM, WED)
        self.assertEqual(page["unlisted"], [{"name": "Associate 041", "what": "Sick"},
                                            {"name": "Associate 042", "what": "Late, arrived 09:20"}])

    def test_nobody_is_said_when_everyone_is_shown(self):
        self.days.set_status(PROGRAM, WED, "Associate 001", "Late", self.sara, end="13:00")
        self.assertEqual(self.days.page(PROGRAM, WED)["unlisted"], [])


class TheShiftGroups(_Day):
    def test_shift_groups_count_people_late_and_off(self):
        self.days.set_status(PROGRAM, WED, "Associate 001", "Late", self.sara, end="13:00")
        view = self.days.page(PROGRAM, WED)["view"]
        groups = shift_groups(view)
        self.assertEqual(sum(g["people"] for g in groups), len(view["lanes"]))
        eight = next(g for g in groups if g["key"] == "08:00")
        self.assertEqual((eight["label"], eight["people"]), ("08:00", 3))
        noon = next(g for g in groups if "Associate 001" in g["names"])
        self.assertEqual((noon["key"], noon["late"], noon["off"]), ("12:00", 1, 0))
        self.assertEqual([g["key"] for g in groups if g["key"] != "earlier"],
                         sorted(g["key"] for g in groups if g["key"] != "earlier"))

    def test_overnight_people_are_under_from_yesterday(self):
        groups = shift_groups(self.days.page(PROGRAM, WED)["view"])
        self.assertEqual((groups[0]["key"], groups[0]["label"], groups[0]["people"]), ("earlier", "From yesterday", 2))

    def test_the_next_start_is_marked_on_today_only(self):
        view = self.days.page(PROGRAM, WED)["view"]
        self.assertEqual([g["key"] for g in shift_groups(view, 10 * 60 + 5) if g["next"]], ["11:00"])
        self.assertEqual([g for g in shift_groups(view) if g["next"]], [])


class TheTimelineFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, cls.base, _ = make_app(VALIDATOR_ROOT=str(REPO))
        uid = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.store.add_run("aaaaaaaaaaaa", uid, "AR_week.xlsx", "QUICK", "DONE", program=PROGRAM, week_start="2026-10-11")
        cls.app.extensions["schedules"].ensure(cls.store.get_run("aaaaaaaaaaaa"), INPUT, AFTER, None)
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def timeline(self, **args):
        query = urlencode({"program": PROGRAM, "date": WED.isoformat(), **args})
        return html.unescape(self.client.get(f"/day?{query}").get_data(as_text=True))

    def lanes(self, page):
        return re.findall(r'<select class="att[^"]*" data-name="([^"]+)"', page)

    def test_the_timeline_keeps_only_the_chosen_start(self):
        page = self.timeline(shift="08:00")
        self.assertEqual(len(self.lanes(page)), 3)
        self.assertIn('aria-label="Filter by shift start"', page)
        self.assertRegex(page, r'<a href="[^"]*shift=08(?::|%3A)00[^"]*"[^>]*aria-current="true"><b>08:00</b><small>3 people')
        self.assertIn("Showing the 3 of 28 people whose shift starts at 08:00.", page)
        self.assertEqual(len(self.lanes(self.timeline())), 28)
        self.assertEqual(len(self.lanes(self.timeline(shift="earlier"))), 2)

    def test_a_start_no_one_has_says_so(self):
        page = self.timeline(shift="02:00")
        self.assertEqual(self.lanes(page), [])
        self.assertIn("Nobody's shift starts at 02:00 on this day.", page)
        self.assertRegex(page, r'<a href="[^"]*">Show all shifts</a>')


if __name__ == "__main__":
    unittest.main()
