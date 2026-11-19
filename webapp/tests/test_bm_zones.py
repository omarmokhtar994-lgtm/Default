# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BM, task 3 (owner, 2026-11-10: "time zones is working bad!! We need zones to be an option in each place actuals/forecast part so here which
timezone is used? And why cant be changed").

Volumes are kept in the program's zone; every place can be read in another one without any right to change things. A forecast read in another zone
takes the hours past the week's edge from the neighbouring weeks' saved forecasts (it used to wrap them round to the other end of the same week); the
week's report is read from the real neighbouring days; hours worked can be typed in another zone and are kept in the program's. Made-up data."""
import unittest
from datetime import date, timedelta

from webapp import volumes_zone as Z
from webapp.tests.test_bi_volumes import KEY, SUN
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_bm_every import book
from webapp.tests.test_runs import sign_in, token

NY = "America/New_York"          # seven hours behind Cairo in November


def flat(value, slots=48):
    return [[value] * slots for _ in range(7)]


class TheWeekStitchedFromItsNeighbours(unittest.TestCase):
    def test_the_first_hours_come_from_the_week_before(self):
        # Cairo Sunday 00:00 to 07:00 is New York Saturday evening: it belongs to the week before in New York time, and New York's own
        # Saturday evening is the start of next week's Cairo Sunday
        got = Z.stitch(flat(1), flat(10), flat(100), SUN, "Africa/Cairo", NY, 30, "sum")
        self.assertEqual(got[0][:14], [10] * 14)                      # Sunday 00:00 to 07:00 New York = Cairo Sunday 07:00 on: this week
        self.assertEqual(got[6][-14:], [100] * 14)                    # Saturday 17:00 on in New York = Cairo next Sunday: the week after
        self.assertEqual(sum(map(sum, got)), 10 * (336 - 14) + 100 * 14)

    def test_without_neighbours_it_is_the_old_rotation(self):
        week = [[d * 100 + i for i in range(48)] for d in range(7)]
        self.assertEqual(Z.stitch(None, week, None, SUN, "Africa/Cairo", NY, 30, "sum"), Z.rotate_grid(week, SUN, "Africa/Cairo", NY, 30, "sum"))

    def test_the_same_zone_is_the_week_itself(self):
        self.assertEqual(Z.stitch(flat(1), flat(10), flat(100), SUN, NY, NY, 30, "sum"), flat(10))


class TheForecastInAnotherZone(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book(30)

    def test_saved_neighbours_fill_the_edge_and_the_page_can_say_so(self):
        self.vb.save_forecast(KEY, "Phone", SUN + timedelta(weeks=1), 14000, {}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN, total=7000)
        seen = self.vb.view_in(KEY, f, SUN, NY)
        after = self.vb.forecast(KEY, "Phone", SUN + timedelta(weeks=1))
        self.assertEqual(seen["calls"][6][-14:], after["calls"][0][:14])   # New York Saturday evening is next week's Cairo Sunday morning
        self.assertEqual(seen["edge"], "mixed")                             # the week after is saved, the week before is not
        self.assertEqual(seen["day_totals"], {d: sum(seen["calls"][d]) for d in range(7)})

    def test_with_nothing_saved_beside_it_the_weeks_own_pattern_fills_the_edge(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=7000)
        seen = self.vb.view_in(KEY, f, SUN, NY)
        self.assertEqual(seen["edge"], "pattern")
        self.assertEqual(sum(map(sum, seen["calls"])), 7000)

    def test_the_programs_own_zone_is_the_forecast_itself(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=7000)
        self.assertIs(self.vb.view_in(KEY, f, SUN, "Africa/Cairo"), f)


class TheReportInAnotherZone(unittest.TestCase):
    def test_it_reads_the_real_neighbouring_days(self):
        store, vb = book(30)
        week = SUN - timedelta(weeks=1)
        nxt = (week + timedelta(days=7)).isoformat()
        store.replace_volume_rows(KEY, "Phone", [(nxt, m, 5.0, 300.0) for m in range(0, 420, 30)], 1)   # the Sunday after, 00:00 to 07:00 Cairo
        own = vb.report(KEY, "Phone", week)
        seen = vb.report(KEY, "Phone", week, zone=NY)
        self.assertEqual(seen["actual"][6][-14:], [5] * 14)             # that morning is the last evening of this week in New York
        self.assertEqual(seen["show_zone"], NY)
        self.assertEqual(sum(seen["actual"][0][:14]), sum(own["actual"][0][14:28]))
        self.assertIs(vb.report(KEY, "Phone", week, zone="Africa/Cairo")["actual"][0].__class__, list)
        self.assertNotIn("show_zone", vb.report(KEY, "Phone", week))


class TheHoursTypedInAnotherZone(unittest.TestCase):
    def test_a_window_moves_and_keeps_its_length(self):
        got = Z.shift_hours({"0": [960, 1680], "1": None}, 420)               # Sunday 16:00 to 04:00, seven hours later
        self.assertEqual(got["0"], [1380, 2100])                              # Sunday 23:00 to 11:00
        self.assertIsNone(got["1"])

    def test_an_opening_past_midnight_moves_to_the_next_weekday(self):
        got = Z.shift_hours({"6": [1200, 1500]}, 420)                         # Saturday 20:00 to 01:00 becomes Sunday 03:00 to 08:00
        self.assertEqual(got["0"], [180, 480])
        self.assertIsNone(got["6"])                                           # its hours left and none arrived: closed, not "open all day"

    def test_moving_back_goes_to_the_weekday_before(self):
        self.assertEqual(Z.shift_hours({"0": [120, 600]}, -420)["6"], [1140, 1620])

    def test_two_windows_landing_on_one_day_are_refused_in_words(self):
        with self.assertRaises(ValueError) as caught:
            Z.shift_hours({"0": [1200, 1380], "1": [60, 600]}, 420)           # Sunday 20:00 lands on Monday, where Monday 01:00 already lands
        self.assertIn("Mon", str(caught.exception))

    def test_no_move_and_unset_days_stay_as_they_are(self):
        days = {"2": [540, 1260]}
        self.assertEqual(Z.shift_hours(days, 0), days)
        self.assertNotIn("3", Z.shift_hours(days, 420))


class ThePages(_Volumes):
    def test_a_reader_switches_zone_on_the_forecast_and_the_report(self):
        self.history(self.alpha)
        client = sign_in(self.app, "plan_a", PASSWORD)
        page = client.get("/volumes", query_string={"program": self.alpha, "tab": "forecast", "total": "7000", "show_tz": NY}).get_data(as_text=True)
        self.assertIn("Shown in New York time", page)
        self.assertIn("this week's own pattern", page)
        how = client.get("/volumes", query_string={"program": self.alpha, "tab": "how", "show_tz": NY}).get_data(as_text=True)
        self.assertIn('name="show_tz"', how)
        self.assertIn("New York time", how)

    def test_every_tab_says_which_zone_its_numbers_are_in(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for tab in ("actuals", "forecast", "how", "outlook", "settings"):
            page = client.get("/volumes", query_string={"program": self.alpha, "tab": tab}).get_data(as_text=True)
            self.assertIn('id="zone-note"', page, tab)
            self.assertIn("Cairo time", page, tab)

    def test_hours_typed_in_new_york_are_kept_in_cairo_time(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        shift = Z.minutes_between(NY, "Africa/Cairo", date.today())
        data = {"csrf_token": token(client), "program": self.alpha, "hours_tz": NY, "hours.Phone.min_cover": "1",
                "hours.Phone.0.from": "09:00", "hours.Phone.0.to": "17:00"}
        reply = client.post("/volumes/settings", data=data)
        self.assertEqual(reply.status_code, 303)
        kept = self.vb.open_hours(self.alpha)["Phone"]["days"]
        self.assertEqual(kept["0"], [540 + shift, 1020 + shift])
        page = client.get("/volumes", query_string={"program": self.alpha, "tab": "settings"}).get_data(as_text=True)
        self.assertIn('name="hours_tz"', page)


if __name__ == "__main__":
    unittest.main()
