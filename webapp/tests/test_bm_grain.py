# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BM, task 1 (owner, 2026-11-10: the forecast showed a number on the hour and 0 on the half hour; "Yea it's hourly").

History that is hourly, kept in a 30-minute program, used to sit whole in the first half of each hour, so the pattern learned that nobody calls at
half past. Now an hour's volume is shared over its intervals: when a file's rows are an hour apart, when a 30-minute sheet holds zeros on every half
hour, and (once, on request) for the days already held. A real half-hourly day is left alone. Made-up data."""
import unittest
from datetime import timedelta

from webapp import volumes_grain as G
from webapp.volumes_io import parse_long
from webapp.volumes import VolumeBook
from webapp.tests.test_bi_volumes import KEY, SUN, book as hourly_book
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_runs import sign_in, token


def book():
    """A program whose interval is 30 minutes (the shared helper's is hourly, which has nothing to spread)."""
    store, _ = hourly_book()
    return store, VolumeBook(store, measure_of=lambda key: "sl", step_of=lambda key: 30)


def hourly_day(hours=range(8, 20), each=21):
    slots = [0.0] * 48
    for h in hours:
        slots[h * 2] = each
    return slots


class TheGrain(unittest.TestCase):
    def test_a_day_with_volume_only_on_the_hour_is_hourly(self):
        self.assertTrue(G.looks_hourly(hourly_day(), 30))

    def test_a_quiet_day_is_not_called_hourly(self):
        self.assertFalse(G.looks_hourly(hourly_day(hours=(9, 10, 11)), 30))          # three hours prove nothing

    def test_one_real_half_hour_keeps_the_day_as_it_is(self):
        day = hourly_day()
        day[21] = 2
        self.assertFalse(G.looks_hourly(day, 30))

    def test_an_hourly_program_has_nothing_to_spread(self):
        self.assertFalse(G.looks_hourly([5.0] * 24, 60))

    def test_an_hour_is_shared_over_its_intervals_and_the_total_stays(self):
        got = G.spread_hour(hourly_day(each=21), 30)
        self.assertEqual((got[16], got[17]), (11, 10))                               # the odd one goes to the first half
        self.assertEqual(sum(got), 21 * 12)
        self.assertEqual(G.spread_hour([40.0, 0, 0, 0] + [0.0] * 92, 15)[:4], [10, 10, 10, 10])

    def test_a_grid_seen_at_a_coarser_interval(self):
        grid = [[1, 2, 3, 4], [0, 0, None, None]]
        self.assertEqual(G.regrid(grid, 30, 60, "sum"), [[3, 7], [0, None]])
        self.assertEqual(G.regrid(grid, 30, 60, "max"), [[2, 4], [0, None]])
        self.assertEqual(G.regrid([[80.0, 100.0]], 30, 60, "mean", weights=[[3, 1]]), [[85.0]])
        self.assertEqual(G.regrid([[80.0, None]], 30, 60, "mean", weights=[[0, 0]]), [[80.0]])
        self.assertIs(G.regrid(grid, 30, 30, "sum"), grid)
        with self.assertRaises(ValueError):
            G.regrid(grid, 30, 45, "sum")


class TheFilesThatAreHourly(unittest.TestCase):
    def table(self, minutes):
        day = (SUN - timedelta(days=7)).isoformat()
        return [["Date", "Interval", "Offered", "AHT"]] + [[day, f"{m // 60:02d}:{m % 60:02d}", 21, 300] for m in minutes]

    def test_rows_an_hour_apart_are_taken_and_shared_over_the_half_hours(self):
        parsed = parse_long(self.table([h * 60 for h in range(8, 20)]), "Phone", 30, SUN)
        self.assertEqual(parsed.problems, [])
        rows = parsed.rows["Phone"]
        self.assertEqual(len(rows), 24)
        self.assertEqual([r[2] for r in rows[:2]], [11, 10])
        self.assertEqual(sum(r[2] for r in rows), 21 * 12)
        self.assertEqual({r[3] for r in rows}, {300})
        self.assertTrue([n for n in parsed.notes if "hour" in n], parsed.notes)

    def test_a_half_hour_sheet_with_zeros_on_every_half_hour_is_shared_too(self):
        store, vb = book()
        minutes = [h * 60 + half for h in range(8, 20) for half in (0, 30)]
        table = self.table(minutes)
        for row in table[1:]:
            if row[1].endswith(":30"):
                row[2] = 0
        parsed = vb.as_hourly(KEY, parse_long(table, "Phone", 30, SUN))
        self.assertEqual([r[2] for r in parsed.rows["Phone"][:2]], [11, 10])
        self.assertTrue([n for n in parsed.notes if "1 day" in n and "hour" in n], parsed.notes)

    def test_a_real_half_hourly_file_is_left_as_it_is(self):
        store, vb = book()
        parsed = parse_long(self.table([h * 60 + half for h in range(8, 20) for half in (0, 30)]), "Phone", 30, SUN)
        again = vb.as_hourly(KEY, parsed)
        self.assertEqual([r[2] for r in again.rows["Phone"]], [21] * 24)
        self.assertEqual(again.notes, parsed.notes)


class TheDaysAlreadyHeld(unittest.TestCase):
    def test_they_are_listed_and_fixed_once(self):
        store, vb = book()
        days = [(SUN - timedelta(days=k)).isoformat() for k in (7, 8)]
        store.replace_volume_rows(KEY, "Phone", [(d, h * 60 + half, 21 if not half else 0, 300.0) for d in days for h in range(8, 20) for half in (0, 30)], 1)
        real = (SUN - timedelta(days=9)).isoformat()
        store.replace_volume_rows(KEY, "Phone", [(real, h * 60 + half, 9, 300.0) for h in range(8, 20) for half in (0, 30)], 1)
        self.assertEqual(vb.hourly_days(KEY, "Phone"), sorted(days))
        self.assertEqual(vb.spread_hourly(KEY, "Phone", 1), 2)
        rows = store.volume_rows(KEY, "Phone", days[1], days[0])
        self.assertEqual(sum(r["offered"] for r in rows), 2 * 12 * 21)
        self.assertEqual({r["offered"] for r in rows}, {10, 11})
        self.assertEqual({r["aht"] for r in rows}, {300.0})
        self.assertEqual(vb.hourly_days(KEY, "Phone"), [])
        self.assertEqual(vb.spread_hourly(KEY, "Phone", 1), 0)
        self.assertEqual({r["offered"] for r in store.volume_rows(KEY, "Phone", real, real)}, {9})


class ThePage(_Volumes):
    def hold(self):
        from datetime import date
        today = date.today()
        day = (today - timedelta(days=3)).isoformat()
        self.store.replace_volume_rows(self.alpha, "Phone", [(day, h * 60 + sub * self.step, 21 if not sub else 0, 300.0)
                                                             for h in range(8, 20) for sub in range(60 // self.step)], self.admin_id)
        return day

    def test_the_data_tab_says_so_and_a_planner_fixes_it(self):
        if self.step >= 60:
            self.skipTest("the example program is hourly: nothing to spread")
        day = self.hold()
        client = sign_in(self.app, "plan_a", PASSWORD)
        page = client.get("/volumes", query_string={"program": self.alpha, "tab": "actuals", "channel": "Phone"}).get_data(as_text=True)
        self.assertIn("look hourly", page)
        self.assertIn('action="/volumes/actuals/spread-hourly"', page)
        reply = client.post("/volumes/actuals/spread-hourly", data={"csrf_token": token(client), "program": self.alpha, "channel": "Phone"})
        self.assertEqual(reply.status_code, 303)
        rows = self.store.volume_rows(self.alpha, "Phone", day, day)
        self.assertEqual(sum(r["offered"] for r in rows), 12 * 21)
        self.assertFalse(self.vb.hourly_days(self.alpha, "Phone"))
        again = client.get("/volumes", query_string={"program": self.alpha, "tab": "actuals", "channel": "Phone"}).get_data(as_text=True)
        self.assertNotIn("look hourly", again)

    def test_it_needs_the_right_to_change_volumes_and_the_token(self):
        self.hold()
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(client.post("/volumes/actuals/spread-hourly", data={"program": self.alpha, "channel": "Phone"}).status_code, 400)
        other = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(other.post("/volumes/actuals/spread-hourly", data={"csrf_token": token(other), "program": self.bravo, "channel": "Phone"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
