# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: an analysis tab per associate, LOB and program with the count and duration of each
incident, absenteeism, shrinkage and in-office shrinkage). The sums behind the Incidents page, on made-up data: Wednesday
14 Oct has Associate 001 late 60 minutes, Associate 008's break 2 moved and missed, Associate 021 out from 15:00 and a
coaching session; Thursday 15 Oct has Associate 001 sick."""
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp import insights
from webapp.attendance import DayBook
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED, THU = date(2026, 10, 14), date(2026, 10, 15)
KEY = "AE/AR B2B"


class TheInsights(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        cls.lina = store.add_user("lina", "Lina", "Lina-pass-1", must_change=False)
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
        self.days.set_status(KEY, WED, "Associate 001", "Late", self.sara, end="13:00")
        self.days.set_status(KEY, THU, "Associate 001", "Sick", self.lina)
        self.days.move_break(KEY, WED, "Associate 008", 1, "13:10", self.lina, missed=True)
        self.days.set_status(KEY, WED, "Associate 021", "Left early", self.sara, start="15:00")
        self.leave = None
        self.facts = insights.collect(self.days, self.store, self.leave, {KEY: ("AE", "AR B2B")}, WED, THU, "interval")

    def of(self, name, on=None):
        return [r for r in self.facts if r["name"] == name and (on is None or r["date"] == on.isoformat())]

    def test_late_counts_with_its_minutes(self):
        r = self.of("Associate 001", WED)[0]
        self.assertEqual(r["inc"]["late"], [1, 60])

    def test_left_early_counts_with_its_minutes(self):
        self.assertEqual(self.of("Associate 021", WED)[0]["inc"]["early"], [1, 120])

    def test_a_missed_break_counts_with_the_break_length(self):
        n, minutes = self.of("Associate 008", WED)[0]["inc"]["missed_break"]
        self.assertEqual(n, 1)
        self.assertGreater(minutes, 0)

    def test_sick_is_a_day_with_the_shift_length(self):
        n, minutes = self.of("Associate 001", THU)[0]["inc"]["sick"]
        self.assertEqual((n, minutes), (1, 9 * 60))  # 12:00 - 21:00

    def test_a_coaching_session_counts_as_coaching(self):
        names = ["Associate 021", "Associate 037"]
        start = next(s["start"] for s in self.days.meeting_slots(KEY, WED, names, 30, "09:00", "14:00"))
        self.days.book_session(KEY, WED, names, start, 30, "Coaching", self.sara, with_whom="Team lead", why="Weekly")
        facts = insights.collect(self.days, self.store, None, {KEY: ("AE", "AR B2B")}, WED, WED, "interval")
        got = {r["name"]: r["inc"]["coaching"] for r in facts if r["name"] in names}
        self.assertEqual(got, {n: [1, 30] for n in names})

    def test_figures_sum_the_rows(self):
        f = insights.figures(self.facts)
        self.assertEqual(f["incidents"]["late"], {"n": 1, "min": 60})
        self.assertEqual(f["incidents"]["sick"], {"n": 1, "min": 540})
        self.assertEqual(f["absenteeism"], round(100 * 1 / f["shifts"], 1))
        self.assertTrue(0 <= f["adherence"] <= 100)
        self.assertGreater(f["shrink_in"], 0)

    def test_grouping_by_associate_puts_the_most_incidents_first(self):
        rows = insights.grouped(self.facts, "associates")
        self.assertEqual(rows[0]["total"], max(r["total"] for r in rows))
        self.assertEqual({r["name"] for r in rows}, {r["name"] for r in self.facts})

    def test_grouping_by_lob_and_program_each_give_one_row_here(self):
        self.assertEqual([r["name"] for r in insights.grouped(self.facts, "lobs")], ["AR B2B"])
        self.assertEqual([r["name"] for r in insights.grouped(self.facts, "programs")], ["AE"])

    def test_the_trend_has_a_point_per_day_with_records(self):
        self.assertEqual([d["date"] for d in insights.trend(self.facts)], ["2026-10-14", "2026-10-15"])

    def test_one_person_lists_their_days(self):
        p = insights.person(self.facts, "Associate 001")
        self.assertEqual([d["date"] for d in p["days"]], ["2026-10-15", "2026-10-14"])
        self.assertEqual(p["incidents"]["late"]["n"], 1)


class ThePlannedLeave(unittest.TestCase):
    """Associate 090 has Leave on the schedule and Associate 091 has an approved public holiday there: only the first is
    planned leave (a public holiday counts for the client's shrinkage, not as an incident)."""
    def page(self):
        week = {"associates": [{"name": "Associate 090", "days": ["Leave"] * 7},
                               {"name": "Associate 091", "days": ["Leave"] * 7}]}
        return {"view": {"lanes": [], "measure": "interval", "interval": 30}, "week": week, "day": 3, "date": WED}

    def test_leave_cells_are_planned_leave_unless_they_are_a_holiday(self):
        rows = insights.day_facts(self.page(), "K", "P", "L", insights.read_mapping(None),
                                  {"Associate 091": "Public holiday"}, [])
        self.assertEqual([r["name"] for r in rows], ["Associate 090"])
        self.assertEqual(rows[0]["inc"]["planned"], [1, 0])
        self.assertEqual(rows[0]["out"], 1)  # planned leave counts toward out-of-office shrinkage


if __name__ == "__main__":
    unittest.main()
