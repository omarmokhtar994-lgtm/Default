# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04): the volume book across time zones: the program's zone, actuals converted into it and saved cell by cell, and a forecast shown in
another zone. Made-up numbers."""
import unittest
from datetime import date, timedelta

from webapp.tests.test_bi_volumes import KEY, STEP, SUN, book, history
from webapp.volumes_io import ParsedVolumes, parse_grid

NY, CAIRO = "America/New_York", "Africa/Cairo"
WEEK = date(2026, 10, 25)                       # a Sunday with no clock change in either region until the 29th and the 1st
TODAY = date(2026, 12, 20)


def grid_text(rows):
    return [["Interval", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]] + rows


def day_of(overrides, fill=0):
    """Every hour of the day, ``fill`` in each cell except the rows named: {"09:00": [7 numbers]}."""
    return [[f"{h:02d}:00"] + list(overrides.get(f"{h:02d}:00", [fill] * 7)) for h in range(24)]


class TheProgramsZone(unittest.TestCase):
    def test_cairo_unless_set_and_only_a_listed_zone_can_be_set(self):
        _, vb = book()
        self.assertEqual(vb.zone(KEY), CAIRO)
        vb.set_zone(KEY, NY, 1)
        self.assertEqual(vb.zone(KEY), NY)
        for bad in ("Mars/Olympus", "", None, "UTC; drop table", 5):
            with self.assertRaises(ValueError, msg=bad):
                vb.set_zone(KEY, bad, 1)
        self.assertEqual(vb.zone(KEY), NY)

    def test_saving_the_settings_keeps_the_zone(self):
        _, vb = book()
        vb.set_zone(KEY, NY, 1)
        vb.set_settings(KEY, {"Phone": {"sl_target": 90}}, 1)
        self.assertEqual((vb.zone(KEY), vb.settings(KEY)["Phone"]["sl_target"]), (NY, 90))
        vb.set_zone(KEY, CAIRO, 1)
        self.assertEqual(vb.settings(KEY)["Phone"]["sl_target"], 90)

    def test_a_zone_is_per_program(self):
        _, vb = book()
        vb.set_zone(KEY, NY, 1)
        self.assertEqual(vb.zone("Program 02 Other"), CAIRO)


class TheActualsInAnotherZone(unittest.TestCase):
    def parsed(self, vb, rows, week=WEEK):
        return parse_grid(grid_text(rows), week, "Phone", None, STEP, TODAY)

    def test_new_york_actuals_become_cairo_rows(self):
        store, vb = book()
        got = vb.convert_actuals(KEY, self.parsed(vb, day_of({"09:00": [10, 20, 30, 40, 50, 60, 70], "22:00": [1, 2, 3, 4, 5, 6, 7]})), NY)
        self.assertEqual(got.problems, [])
        rows = {(d, m): o for d, m, o, _ in got.rows["Phone"]}
        self.assertEqual(rows[("2026-10-26", 16 * 60)], 20)                       # Monday 09:00 in New York (UTC-4) is 16:00 in Cairo (UTC+3)
        self.assertEqual(rows[("2026-10-27", 5 * 60)], 2)                         # ... and Monday 22:00 there is 05:00 the next day here
        self.assertTrue(any("New York" in n and "Cairo" in n for n in got.notes))
        self.assertEqual(got.summary["Phone"]["rows"], 24 * 7 - 1)               # Egypt goes back on Thu 29 Oct: its Thursday 23:00 happens twice, and two New York hours add into one cell
        self.assertEqual(sum(r[2] for r in got.rows["Phone"]), 280 + 28)         # nothing is lost

    def test_the_zone_of_the_program_is_the_one_converted_to(self):
        _, vb = book()
        vb.set_zone(KEY, NY, 1)
        got = vb.convert_actuals(KEY, self.parsed(vb, [["09:00", 10, 20, 30, 40, 50, 60, 70]]), CAIRO)
        rows = {(d, m): o for d, m, o, _ in got.rows["Phone"]}
        self.assertEqual(rows[("2026-10-26", 2 * 60)], 20)                        # Cairo 09:00 is 02:00 in New York

    def test_the_same_zone_changes_nothing(self):
        _, vb = book()
        p = self.parsed(vb, [["09:00", 1, 2, 3, 4, 5, 6, 7]])
        self.assertIs(vb.convert_actuals(KEY, p, CAIRO), p)

    def test_a_time_the_clocks_cannot_place_refuses_the_whole_upload(self):
        _, vb = book()
        p = parse_grid(grid_text(day_of({"02:00": [1] * 7, "09:00": [5] * 7}, fill=2)), date(2027, 3, 14), "Phone", None, 60, date(2027, 4, 1))
        got = vb.convert_actuals(KEY, p, NY)
        self.assertEqual(got.rows, {})
        self.assertTrue(got.problems and all(x.startswith("Phone:") for x in got.problems))
        self.assertTrue(any("2027-03-14" in x for x in got.problems))

    def test_a_bad_zone_is_refused(self):
        _, vb = book()
        with self.assertRaises(ValueError):
            vb.convert_actuals(KEY, self.parsed(vb, [["09:00", 1, 2, 3, 4, 5, 6, 7]]), "Mars/Olympus")

    def test_a_file_with_problems_is_not_converted(self):
        _, vb = book()
        bad = ParsedVolumes(problems=["Row 2: nope"])
        self.assertEqual(vb.convert_actuals(KEY, bad, NY).problems, ["Row 2: nope"])


class TheSavingCellByCell(unittest.TestCase):
    def test_a_converted_upload_changes_only_the_cells_it_holds(self):
        store, vb = book()
        store.replace_volume_rows(KEY, "Phone", [("2026-10-26", m, 7.0, 300.0) for m in range(0, 1440, 60)], 1)         # a whole Cairo Monday already held
        p = parse_grid(grid_text([["09:00", 0, 20, 0, 0, 0, 0, 0]]), WEEK, "Phone", None, 60, TODAY)
        got = vb.convert_actuals(KEY, p, NY)
        done = vb.save_actuals(KEY, got, 1, cells=True)
        self.assertEqual(done["Phone"]["rows"], len(got.rows["Phone"]))
        held = {r["minute"]: r["offered"] for r in store.volume_rows(KEY, "Phone", "2026-10-26", "2026-10-26")}
        self.assertEqual(len(held), 24)                                              # the other 23 intervals of that day are still there
        self.assertEqual(held[16 * 60], 20.0)                                        # the one that came in replaced its cell
        self.assertEqual(held[3 * 60], 7.0)

    def test_the_usual_save_still_replaces_a_day_as_a_whole(self):
        store, vb = book()
        store.replace_volume_rows(KEY, "Phone", [("2026-10-26", m, 7.0, None) for m in range(0, 1440, 60)], 1)
        p = parse_grid(grid_text([["09:00", 0, 20, 0, 0, 0, 0, 0]]), WEEK, "Phone", None, 60, TODAY)
        vb.save_actuals(KEY, p, 1)
        self.assertEqual(len(store.volume_rows(KEY, "Phone", "2026-10-26", "2026-10-26")), 1)

    def test_the_store_counts_the_days_it_touched_that_were_already_held(self):
        store, _ = book()
        store.replace_volume_rows(KEY, "Phone", [("2026-10-26", 60, 1.0, None)], 1)
        done = store.upsert_volume_cells(KEY, "Phone", [("2026-10-26", 60, 5.0, None), ("2026-10-26", 120, 6.0, None), ("2026-10-27", 60, 2.0, None)], 1)
        self.assertEqual(done, {"rows": 3, "days": 2, "replaced_days": 1})
        self.assertEqual({r["minute"]: r["offered"] for r in store.volume_rows(KEY, "Phone", "2026-10-26", "2026-10-26")}, {60: 5.0, 120: 6.0})

    def test_a_failed_save_changes_nothing(self):
        store, _ = book()
        store.replace_volume_rows(KEY, "Phone", [("2026-10-26", 60, 1.0, None)], 1)
        with self.assertRaises(Exception):
            store.upsert_volume_cells(KEY, "Phone", [("2026-10-26", 60, 5.0, None), ("2026-10-26", 120, "x", None)], 1)
        self.assertEqual([r["offered"] for r in store.volume_rows(KEY, "Phone", "2026-10-26", "2026-10-26")], [1.0])


class TheForecastInAnotherZone(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        history(self.store)
        self.f = self.vb.forecast(KEY, "Phone", SUN, total=8000)

    def test_a_grid_shown_in_new_york_keeps_its_total_and_its_shape_moved(self):
        v = self.vb.view_in(KEY, self.f, SUN, NY)
        self.assertEqual(sum(map(sum, v["calls"])), 8000)
        self.assertEqual(v["show_zone"], NY)
        self.assertEqual(sum(v["day_totals"].values()), 8000)
        self.assertNotEqual(v["calls"], self.f["calls"])
        self.assertEqual(self.f["show_zone"] if "show_zone" in self.f else None, None)      # the original is not changed

    def test_the_peak_of_the_people_needed_is_kept(self):
        v = self.vb.view_in(KEY, self.f, SUN, NY)
        self.assertEqual(max(map(max, v["needs"])), max(map(max, self.f["needs"])))

    def test_the_programs_own_zone_or_no_grid_gives_the_same_forecast(self):
        self.assertIs(self.vb.view_in(KEY, self.f, SUN, CAIRO), self.f)
        empty = self.vb.forecast(KEY, "Phone", SUN)
        self.assertIs(self.vb.view_in(KEY, empty, SUN, NY), empty)

    def test_a_bad_zone_is_refused(self):
        with self.assertRaises(ValueError):
            self.vb.view_in(KEY, self.f, SUN, "Mars/Olympus")

    def test_there_and_back_through_the_programs_own_zone_is_the_grid_again(self):
        self.vb.set_zone(KEY, NY, 1)
        v = self.vb.view_in(KEY, self.f, SUN, CAIRO)
        self.assertEqual(sum(map(sum, v["calls"])), 8000)


if __name__ == "__main__":
    unittest.main()
