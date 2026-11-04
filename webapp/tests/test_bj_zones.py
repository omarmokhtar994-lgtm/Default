# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "I may add actuals in EST and request required associates in Egypt time"): volumes in one time zone, kept in the program's, shown in
either. Uploaded actuals are converted by the clock (clock changes included) and refused when a time cannot be placed; a forecast grid is turned to another zone by
the same clock. Made-up numbers."""
import unittest
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from webapp import volumes_zone as Z

NY, CAIRO, LONDON = "America/New_York", "Africa/Cairo", "Europe/London"


def converted_first(day, minute, src, dst):
    """The reading a person expects of an hour that happens twice: the first one."""
    from datetime import datetime, time, timezone
    wall = datetime.combine(day, time()) + timedelta(minutes=minute)
    there = wall.replace(tzinfo=ZoneInfo(src), fold=0).astimezone(timezone.utc).astimezone(ZoneInfo(dst))
    return there.hour * 60 + there.minute


class TheUploadedRows(unittest.TestCase):
    def test_a_winter_day_in_new_york_in_cairo_time(self):
        rows = [("2026-12-06", 9 * 60, 10.0, 300.0), ("2026-12-06", 22 * 60, 4.0, None)]
        out, problems = Z.convert_rows(rows, NY, CAIRO, 60)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(out), [("2026-12-06", 16 * 60, 10.0, 300.0), ("2026-12-07", 5 * 60, 4.0, None)])      # +7 h: 22:00 is 05:00 the next day

    def test_the_offset_follows_each_regions_clock_changes_day_by_day(self):
        # Cairo went back an hour on Thu 29 Oct 2026; New York on Sun 1 Nov 2026: the gap is 6 h in between and 7 h after.
        for day, hours in (("2026-10-28", 7), ("2026-10-30", 6), ("2026-10-31", 6), ("2026-11-02", 7)):
            out, problems = Z.convert_rows([(day, 12 * 60, 1.0, None)], NY, CAIRO, 60)
            self.assertEqual(problems, [], day)
            moved = date.fromisoformat(day)
            self.assertEqual(out[0][1], (12 + hours) * 60 % 1440, day)
            self.assertEqual(out[0][0], (moved + timedelta(days=(12 + hours) // 24)).isoformat(), day)

    def test_the_same_zone_is_left_alone(self):
        rows = [("2026-12-06", 540, 3.0, 100.0)]
        self.assertEqual(Z.convert_rows(rows, CAIRO, CAIRO, 30), (rows, []))

    def test_the_hour_a_region_repeats_is_read_as_its_first_and_said(self):
        # Owner, 2026-11-04: an export by local day has one 01:00 row on 1 Nov in New York; it is read as the first 01:00 (summer time), not refused.
        notes: list = []
        out, problems = Z.convert_rows([("2026-11-01", 60 + 30, 5.0, None), ("2026-11-01", 9 * 60, 7.0, None)], NY, CAIRO, 30, notes)
        self.assertEqual(problems, [])
        self.assertEqual(len(out), 2)
        first = converted_first(date(2026, 11, 1), 90, NY, CAIRO)
        self.assertIn(("2026-11-01", first), [(d, m) for d, m, _o, _a in out])
        self.assertEqual(len(notes), 1)
        self.assertIn("2026-11-01", notes[0])
        self.assertIn("twice", notes[0])

    def test_the_hour_a_region_skips_is_dropped_when_empty_and_refused_when_it_has_volume(self):
        notes: list = []
        out, problems = Z.convert_rows([("2027-03-14", 2 * 60 + 30, 0.0, None), ("2027-03-14", 9 * 60, 7.0, None)], NY, CAIRO, 30, notes)
        self.assertEqual((problems, len(out)), ([], 1))
        self.assertEqual(len(notes), 1)
        self.assertIn("2027-03-14", notes[0])
        _, gap = Z.convert_rows([("2027-03-14", 2 * 60 + 30, 5.0, None)], NY, CAIRO, 30)
        self.assertEqual(len(gap), 1)
        self.assertIn("2027-03-14", gap[0])
        self.assertIn("does not exist", gap[0])

    def test_an_ordinary_day_near_a_change_is_fine_and_says_nothing(self):
        notes: list = []
        out, problems = Z.convert_rows([("2026-11-03", 90, 5.0, None)], NY, CAIRO, 30, notes)
        self.assertEqual((problems, notes, len(out)), ([], [], 1))

    def test_one_problem_and_one_note_per_day_not_one_per_row(self):
        _, problems = Z.convert_rows([("2027-03-14", m, 1.0, None) for m in (150, 180 - 30, 120)], NY, CAIRO, 30)
        self.assertEqual(len(problems), 1)
        notes: list = []
        Z.convert_rows([("2026-11-01", m, 1.0, None) for m in (60, 90)], NY, CAIRO, 30, notes)
        self.assertEqual(len(notes), 1)

    def test_fixed_eastern_time_has_no_repeated_or_skipped_hour(self):
        self.assertIn("Etc/GMT+5", Z.NAMES)
        for day in ("2026-11-01", "2027-03-14"):
            notes: list = []
            out, problems = Z.convert_rows([(day, 90, 5.0, None), (day, 150, 5.0, None)], "Etc/GMT+5", CAIRO, 30, notes)
            self.assertEqual((problems, notes, len(out)), ([], [], 2), day)
        out, _ = Z.convert_rows([("2026-12-06", 9 * 60, 1.0, None)], "Etc/GMT+5", CAIRO, 30)
        self.assertEqual(out[0][1], 16 * 60)                                                  # UTC-5 to Cairo (UTC+2 in winter) is 7 h

    def test_totals_are_kept_and_collisions_add_up_with_the_handle_time_weighted(self):
        # London goes back at 02:00 on Sun 25 Oct 2026, so two instants of source UTC read 01:00 there.
        rows = [("2026-10-25", 3 * 60, 10.0, 100.0), ("2026-10-25", 4 * 60, 30.0, 200.0)]          # 00:00 and 01:00 UTC (Egypt is UTC+3 until the 29th)
        out, problems = Z.convert_rows(rows, CAIRO, LONDON, 60)
        self.assertEqual(problems, [])
        self.assertEqual(round(sum(r[2] for r in out), 6), 40.0)
        merged = [r for r in out if r[2] == 40.0]
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0][3], (10 * 100 + 30 * 200) / 40, places=6)

    def test_an_unknown_zone_or_a_bad_row_is_refused(self):
        for bad in ("Mars/Olympus", "", "EST5EDT; drop", None):
            with self.assertRaises(ValueError, msg=bad):
                Z.convert_rows([("2026-12-06", 0, 1.0, None)], bad, CAIRO, 60)
        with self.assertRaises(ValueError):
            Z.convert_rows([("2026-12-06", 0, 1.0, None)], NY, "nowhere", 60)

    def test_every_zone_offered_is_whole_hours_so_every_interval_lines_up(self):
        for key, _name in Z.ZONES:
            for day in (date(2026, 1, 15), date(2026, 7, 15)):
                for step in (5, 10, 15, 20, 30, 60):
                    out, problems = Z.convert_rows([(day.isoformat(), 0, 1.0, None)], key, CAIRO, step)
                    self.assertEqual((problems, out[0][1] % step), ([], 0), (key, day, step))


SUN = date(2026, 12, 6)


def grid(step=60, fill=lambda d, i: d * 100 + i):
    return [[fill(d, i) for i in range(1440 // step)] for d in range(7)]


class TheGridInAnotherZone(unittest.TestCase):
    def test_the_same_zone_is_the_same_grid(self):
        g = grid()
        self.assertEqual(Z.rotate_grid(g, SUN, CAIRO, CAIRO, 60), g)

    def test_each_cell_lands_where_the_clock_says(self):
        g = grid()
        out = Z.rotate_grid(g, SUN, CAIRO, NY, 60)                                                # Cairo is 7 h ahead of New York in winter
        self.assertEqual(out[1][2], g[1][9])                                                      # Monday 09:00 Cairo is Monday 02:00 in New York
        self.assertEqual(out[2][0], g[2][7])                                                      # Tuesday 07:00 Cairo is Tuesday 00:00 in New York

    def test_the_hours_that_spill_over_the_edge_of_the_week_wrap_to_the_other_end(self):
        g = grid()
        out = Z.rotate_grid(g, SUN, CAIRO, NY, 60)
        self.assertEqual(out[6][17], g[0][0])                                                     # Cairo Sunday 00:00 is Saturday 17:00 in New York: placed at the end of this week
        out2 = Z.rotate_grid(g, SUN, NY, CAIRO, 60)
        self.assertEqual(out2[0][3], g[6][20])                                                    # New York Saturday 20:00 is Sunday 03:00 in Cairo: placed at the start of this week

    def test_nothing_is_lost_or_made_up(self):
        for src, dst in ((CAIRO, NY), (NY, CAIRO), (LONDON, "Asia/Dubai")):
            for step in (30, 60):
                g = grid(step, lambda d, i: 1 + (d * 7 + i) % 5)
                out = Z.rotate_grid(g, SUN, src, dst, step)
                self.assertEqual(sum(map(sum, out)), sum(map(sum, g)), (src, dst, step))
                self.assertEqual((len(out), {len(r) for r in out}), (7, {1440 // step}))

    def test_there_and_back_gives_the_grid_again_in_a_week_without_clock_changes(self):
        g = grid(30)
        self.assertEqual(Z.rotate_grid(Z.rotate_grid(g, SUN, CAIRO, NY, 30), SUN, NY, CAIRO, 30), g)

    def test_a_week_with_a_clock_change_still_keeps_its_total(self):
        g = grid(60, lambda d, i: 3)
        for week in (date(2026, 10, 25), date(2027, 3, 7), date(2027, 3, 14)):
            out = Z.rotate_grid(g, week, CAIRO, NY, 60)
            self.assertEqual(sum(map(sum, out)), sum(map(sum, g)), week)

    def test_people_needed_take_the_larger_where_two_hours_share_a_cell(self):
        needs = grid(60, lambda d, i: float(i))
        out = Z.rotate_grid(needs, date(2026, 10, 25), CAIRO, LONDON, 60, combine="max")
        self.assertLessEqual(max(map(max, out)), 23.0)

    def test_blanks_stay_blank(self):
        service = grid(60, lambda d, i: None if i < 8 else 90.0)
        out = Z.rotate_grid(service, SUN, CAIRO, NY, 60, combine="first")
        self.assertTrue(any(v is None for r in out for v in r))
        self.assertTrue(all(v in (None, 90.0) for r in out for v in r))

    def test_a_bad_zone_or_a_bad_shape_is_refused(self):
        with self.assertRaises(ValueError):
            Z.rotate_grid(grid(), SUN, CAIRO, "Mars/Olympus", 60)
        with self.assertRaises(ValueError):
            Z.rotate_grid([[1, 2]], SUN, CAIRO, NY, 60)


class TheFastPathEqualsTheStrictClock(unittest.TestCase):
    def test_every_pair_of_zones_on_every_day_of_a_year(self):
        import random
        from datetime import datetime, time, timezone
        from webapp.clock import ZONES
        rng = random.Random(4)
        keys = [k for k, _ in ZONES]
        checked = 0
        for _ in range(4000):
            a, b = rng.sample(keys, 2)
            day = date(2026, 1, 1) + timedelta(days=rng.randint(0, 364))
            minute = rng.choice(range(0, 1440, 30))
            out, problems = Z.convert_rows([(day.isoformat(), minute, 1.0, None)], a, b, 30)
            wall = datetime.combine(day, time()) + timedelta(minutes=minute)
            aware = wall.replace(tzinfo=ZoneInfo(a), fold=0)
            if aware.astimezone(timezone.utc).astimezone(ZoneInfo(a)).replace(tzinfo=None) != wall:
                self.assertEqual(len(problems), 1, (a, b, day, minute))                       # an hour that does not exist, with volume: refused
                continue
            want = aware.astimezone(ZoneInfo(b))                                              # an hour that happens twice is read as its first
            self.assertEqual(problems, [], (a, b, day, minute))
            self.assertEqual((out[0][0], out[0][1]), (want.date().isoformat(), want.hour * 60 + want.minute), (a, b, day, minute))
            checked += 1
        self.assertGreater(checked, 3500)


if __name__ == "__main__":
    unittest.main()
