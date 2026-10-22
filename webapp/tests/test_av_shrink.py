# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: a shrinkage tab for out of office, in office or both, day over day, week over week and
per interval, for any period, everything adjustable). Made-up "Associate NN" data, Wednesday 14 and Thursday 15 Oct."""
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp import insights, shrink_view as sv
from webapp.attendance import DayBook
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED, THU = date(2026, 10, 14), date(2026, 10, 15)
KEY = "AE/AR B2B"


class _Base(unittest.TestCase):
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
        self.days.set_status(KEY, WED, "Associate 008", "Sick", self.sara)
        self.days.set_status(KEY, THU, "Associate 021", "Unplanned leave", self.sara)

    def facts(self, out, inn):
        return insights.collect(self.days, self.store, None, {KEY: ("AE", "AR B2B")}, WED, THU, "interval",
                                mapping_override=sv.mapping_of(out, inn))


class TheTicks(_Base):
    def test_sick_is_out_of_office_only_when_ticked(self):
        with_sick = sv.periods(self.facts(("unplanned", "sick"), ()), "day")
        without = sv.periods(self.facts(("unplanned",), ()), "day")
        self.assertGreater(with_sick[0]["out_n"], without[0]["out_n"])  # Wednesday has the sick one
        self.assertEqual(with_sick[1]["out_n"], without[1]["out_n"])    # Thursday's is unplanned either way

    def test_in_office_follows_what_is_ticked(self):
        none = sv.periods(self.facts((), ()), "day")
        breaks = sv.periods(self.facts((), ("breaks",)), "day")
        self.assertEqual(none[0]["in_min"], 0)
        self.assertGreater(breaks[0]["in_min"], 0)

    def test_ticks_fall_back_to_the_programs_mapping(self):
        out, inn = sv.ticks_from(None, (), ())
        self.assertIn("unplanned", out)
        self.assertNotIn("holiday", out)
        self.assertIn("breaks", inn)
        self.assertEqual(sv.ticks_from(None, ["sick", "x"], []), (("sick",), ()))


class ThePeriods(_Base):
    def test_day_over_day_has_a_point_per_day(self):
        rows = sv.periods(self.facts(("unplanned", "sick"), ("breaks",)), "day")
        self.assertEqual([r["key"] for r in rows], ["2026-10-14", "2026-10-15"])

    def test_week_over_week_sums_days_not_averages_percentages(self):
        facts = self.facts(("unplanned", "sick"), ("breaks",))
        week = sv.periods(facts, "week")
        self.assertEqual([r["key"] for r in week], ["2026-10-11"])  # Sunday's week
        days = sv.periods(facts, "day")
        self.assertEqual(week[0]["out_n"], sum(d["out_n"] for d in days))
        self.assertEqual(week[0]["in_min"], sum(d["in_min"] for d in days))


class TheIntervals(_Base):
    def rows(self, out=("unplanned", "sick"), inn=("breaks",), step=30):
        return sv.collect_intervals(self.days, [KEY], WED, THU, "interval", out, inn, step)

    def test_each_interval_has_scheduled_minutes_and_some_off_floor_time(self):
        per_day = self.rows()
        self.assertEqual(sorted(per_day), ["2026-10-14", "2026-10-15"])
        series = sv.interval_series(per_day)
        self.assertTrue(all(0 <= (s["inn"] or 0) <= 100 for s in series))
        self.assertGreater(max(s["inn"] or 0 for s in series), 0)
        self.assertGreater(max(s["out"] or 0 for s in series), 0)  # the sick one is out for their whole shift

    def test_the_sick_ones_shift_is_out_in_every_interval_it_covers(self):
        per_day = self.rows(inn=())
        sick = [v for t, v in per_day["2026-10-14"].items() if 480 <= t < 1020]  # Associate 008: 08:00 to 17:00
        self.assertTrue(all(v[0] >= 30 * 1 for v in sick))  # at least one person-interval of 30 minutes

    def test_the_window_trims_the_series_and_the_grid(self):
        per_day = self.rows()
        series = sv.interval_series(per_day, 600, 720)
        self.assertEqual([s["t"] for s in series], [600, 630, 660, 690])
        cols, grid = sv.interval_grid(per_day, "inn", 600, 720)
        self.assertEqual(cols, [600, 630, 660, 690])
        self.assertEqual([r["day"] for r in grid], ["2026-10-14", "2026-10-15"])
        self.assertTrue(all(len(r["cells"]) == 4 for r in grid))

    def test_a_larger_interval_gives_fewer_columns(self):
        self.assertLess(len(sv.interval_series(self.rows(step=60))), len(sv.interval_series(self.rows(step=30))))

    def test_the_daily_in_office_figure_matches_the_intervals_added_up(self):
        facts = self.facts((), ("breaks",))
        day = next(r for r in sv.periods(facts, "day") if r["key"] == "2026-10-14")
        rows = self.rows(out=(), inn=("breaks",))["2026-10-14"]
        self.assertEqual(round(sum(v[2] for v in rows.values())), day["in_min"])


if __name__ == "__main__":
    unittest.main()
