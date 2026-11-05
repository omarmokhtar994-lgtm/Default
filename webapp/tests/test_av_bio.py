# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: add Bio break as an aux, counted as in-office shrinkage and in the incident counts and
durations). It needs no who or why, is never billable, takes the person off the queue and is counted everywhere an aux is.
Made-up "Associate NN" data, Wednesday 14 Oct 2026 (Associate 008's shift is 08:00 to 17:00)."""
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp import insights, shrink_view as sv
from webapp.attendance import DayBook
from webapp.day import AUX, BIO, STATUSES
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED = date(2026, 10, 14)
KEY = "AE/AR B2B"


class TheBioBreak(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        store.add_run("aaaaaaaaaaaa", cls.sara, "AR_week.xlsx", "QUICK", "DONE", program=KEY, week_start="2026-10-11")
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

    def add(self, billable=True):
        return self.days.add_activity(KEY, WED, "Associate 008", BIO, "11:00", "11:10", self.sara, billable=billable)

    def seg(self):
        lane = next(l for l in self.days.page(KEY, WED)["view"]["lanes"] if l["name"] == "Associate 008")
        return next(s for s in lane["segments"] if s["offset"] == 0)

    def test_it_is_an_aux_and_a_status(self):
        self.assertIn(BIO, AUX)
        self.assertIn(BIO, STATUSES)

    def test_it_needs_no_who_or_why_and_is_never_billable(self):
        self.add(billable=True)
        row = self.store.list_activities(KEY, [WED.isoformat()])[0]
        self.assertEqual((row["kind"], row["billable"], row["with_whom"], row["why"]), (BIO, 0, "", ""))
        self.assertEqual(self.days.page(KEY, WED)["log"][-1]["what"], "Bio break 11:00 to 11:10")

    def test_it_can_be_the_attendance_status_without_who_or_why(self):
        self.days.set_status(KEY, WED, "Associate 008", BIO, self.sara, start="11:00", end="11:10", billable=True)
        row = self.store.list_attendance(KEY, [WED.isoformat()])[0]
        self.assertEqual((row["status"], row["billable"], row["why"]), (BIO, 0, ""))

    def cell(self):
        return next(c for c in self.days.page(KEY, WED)["view"]["cells"] if c["t"] <= 660 < c["t"] + 60)

    def test_it_takes_the_person_off_the_queue(self):
        before = self.cell()["now"]
        self.add()
        self.assertLess(self.cell()["now"], before)

    def test_it_counts_as_in_office_shrinkage_when_aux_is_ticked(self):
        mapping = sv.mapping_of((), ("aux",))
        with_bio = self.facts_in(mapping)
        self.add()
        self.assertEqual(self.facts_in(mapping) - with_bio, 10)
        breaks_only = sv.mapping_of((), ("breaks",))
        self.assertEqual(self.facts_in(breaks_only), self.facts_in(sv.mapping_of((), ("breaks", "aux_billable"))))

    def facts_in(self, mapping):
        facts = insights.collect(self.days, self.store, None, {KEY: ("AE", "AR B2B")}, WED, WED, "interval",
                                 mapping_override=mapping)
        return sum(r["in_off"] for r in facts if r["name"] == "Associate 008")

    def test_it_has_its_own_incident_count_and_duration(self):
        self.add()
        facts = insights.collect(self.days, self.store, None, {KEY: ("AE", "AR B2B")}, WED, WED, "interval")
        mine = next(r for r in facts if r["name"] == "Associate 008")
        self.assertEqual(mine["inc"]["bio_break"], [1, 10])
        self.assertEqual(dict(insights.KINDS)["bio_break"], "Bio breaks")

    def test_the_interval_view_counts_it_in_its_half_hour(self):
        self.add()
        per_day = sv.collect_intervals(self.days, [KEY], WED, WED, "interval", (), ("aux",), 30)
        self.assertGreaterEqual(per_day["2026-10-14"][660][2], 10)  # the 11:00 interval holds the 10 minutes


if __name__ == "__main__":
    unittest.main()
