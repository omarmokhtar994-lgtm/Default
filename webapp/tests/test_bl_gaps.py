# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL audit: the cases the feature tests did not reach.

- a week with a clock change (Cairo, Thursday 29 October 2026): hours worked follow the clock the grids are kept in, and the grid read in another zone still
  has every interval;
- the months ahead for Chat and Email, and for a site, not only Phone;
- a program counted by interval compliance (no Erlang): the months ahead work, a site's share has no people-needed grid, and the requirement workbook says
  why it cannot be made;
- settings, events and drivers saved before Phase BL (no hours, no sites, no index) read and save exactly as before;
- the largest inputs allowed (six sites, sixty rules, two years of history, 24 months, five-minute intervals) finish in a fair time.
Made-up data only."""
import time
import unittest
from datetime import date, timedelta

from webapp import sites as S
from webapp.tests.test_bi_volumes import KEY, SUN, book
from webapp.tests.test_bj_volumes_book import scaled
from webapp.tests.test_bl_outlook import long_history, yearly

CLOCK_CHANGE_WEEK = date(2026, 10, 25)        # a Sunday; Cairo's clocks go back on the Thursday of it
THU = 4


class TheClockChangeWeek(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        long_history(self.store, 12, last=CLOCK_CHANGE_WEEK)

    def test_hours_worked_follow_the_clock_on_the_day_it_changes(self):
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 1, "days": {str(THU): [9 * 60, 21 * 60]}}}, 1)
        f = self.vb.forecast(KEY, "Phone", CLOCK_CHANGE_WEEK, total=8000)
        self.assertEqual(len(f["needs"][THU]), 24)
        self.assertEqual(sum(f["needs"][THU][:9]) + sum(f["needs"][THU][21:]), 0)
        self.assertGreaterEqual(min(f["needs"][THU][9:21]), 1)

    def test_the_grid_read_in_another_zone_keeps_every_interval(self):
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 1, "days": {str(THU): [9 * 60, 21 * 60]}}}, 1)
        f = self.vb.forecast(KEY, "Phone", CLOCK_CHANGE_WEEK, total=8000)
        for zone in ("America/New_York", "Europe/London", "Asia/Dubai", "Etc/GMT+5"):
            shown = self.vb.view_in(KEY, f, CLOCK_CHANGE_WEEK, zone)
            self.assertTrue(all(len(row) == 24 for row in shown["needs"]), zone)
            self.assertAlmostEqual(sum(sum(r) for r in shown["calls"]), sum(sum(r) for r in f["calls"]), delta=1, msg=zone)

    def test_a_holiday_on_the_clock_change_day_closes_it(self):
        day = (CLOCK_CHANGE_WEEK + timedelta(days=THU)).isoformat()
        self.vb.add_driver(KEY, "events", {"kind": "Holiday", "name": "Clock change", "channels": ["Phone"], "start": day, "end": day, "change": "",
                                           "hours": "closed"}, 1)
        f = self.vb.forecast(KEY, "Phone", CLOCK_CHANGE_WEEK, total=8000)
        self.assertEqual(sum(f["needs"][THU]), 0)

    def test_the_months_ahead_across_the_change_have_every_day_once(self):
        got = self.vb.outlook(KEY, "Phone", start=CLOCK_CHANGE_WEEK, months=2)
        days = [d["date"] for w in got["weeks"] for d in w["days"]]
        self.assertEqual(len(days), len(set(days)))
        self.assertIn("2026-10-29", days)


class TheOtherChannelsAndSites(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        long_history(self.store, 60, base=3000, channel="Chat", aht=420.0, season=yearly)
        long_history(self.store, 60, base=1400, channel="Email", aht=480.0)
        self.next = SUN + timedelta(weeks=1)

    def test_chat_and_email_months_ahead_add_up(self):
        for channel in ("Chat", "Email"):
            got = self.vb.outlook(KEY, channel, start=self.next, months=6)
            self.assertEqual(got["model"]["kind"], "seasonal", channel)
            self.assertEqual(sum(m["expected"] for m in got["months"]), got["total"]["expected"], channel)
            self.assertTrue(all(m["low"] <= m["expected"] <= m["high"] for m in got["months"]), channel)
            self.assertGreater(got["total"]["expected"], 0, channel)

    def test_the_sites_split_chat_and_email_months_and_they_add_up(self):
        doc = {"sites": [{"name": "Internal", "lob": ""}, {"name": "Sutherland", "lob": ""}],
               "rules": [{"channel": "Email", "days": [1, 2, 3, 4, 5], "from": 0, "to": 1440, "shares": {"Internal": 60, "Sutherland": 40}},
                         {"channel": "Chat", "days": list(range(7)), "from": 540, "to": 960, "shares": {"Internal": 100, "Sutherland": 0}},
                         {"channel": "Chat", "days": list(range(7)), "from": 960, "to": 1440, "shares": {"Internal": 0, "Sutherland": 100}}]}
        self.vb.set_sites(KEY, doc, 1)
        for channel in ("Chat", "Email"):
            whole = self.vb.outlook(KEY, channel, start=self.next, months=3)["total"]["expected"]
            parts = sum(self.vb.outlook(KEY, channel, start=self.next, months=3, site=n)["total"]["expected"] for n in ("Internal", "Sutherland"))
            self.assertAlmostEqual(parts, whole, delta=max(10, whole * 0.002), msg=channel)

    def test_email_months_ahead_with_a_closed_weekday_in_the_history(self):
        _, vb = book()
        # the history has no Sunday at all (a closed weekday): the whole weeks are the ones with the six other days
        long_history(vb.store, 60, base=1400, channel="Email", aht=480.0)
        rows = [r for r in vb.store.volume_rows(KEY, "Email", "2000-01-01", "2100-01-01") if date.fromisoformat(r["day"]).weekday() != 6]
        vb.store.delete_volume_days(KEY, "Email", "2000-01-01", "2100-01-01")
        vb.store.replace_volume_rows(KEY, "Email", [(r["day"], r["minute"], r["offered"], 480.0) for r in rows], 1)
        got = vb.outlook(KEY, "Email", start=self.next, months=3)
        self.assertEqual(got["model"]["kind"], "seasonal")
        sundays = [d for w in got["weeks"] for d in w["days"] if d["weekday"] == "Sun"]
        self.assertTrue(sundays and all(d["expected"] == 0 for d in sundays))


class TheProgramCountedByIntervalCompliance(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book(measure="interval")
        scaled(self.store, {})
        long_history(self.store, 60)
        self.vb.set_sites(KEY, {"sites": [{"name": "A", "lob": ""}, {"name": "B", "lob": ""}],
                                "rules": [{"channel": "Phone", "days": list(range(7)), "from": 0, "to": 1440, "shares": {"A": 70, "B": 30}}]}, 1)

    def test_the_months_ahead_do_not_need_erlang(self):
        got = self.vb.outlook(KEY, "Phone", start=SUN + timedelta(weeks=1), months=3)
        self.assertGreater(got["total"]["expected"], 0)

    def test_a_site_has_its_contacts_and_no_people_needed(self):
        f = self.vb.forecast(KEY, "Phone", SUN + timedelta(weeks=1), total=8000)
        self.assertIsNone(f.get("needs"))
        mine = self.vb.for_site(KEY, f, "A")
        self.assertIsNone(mine.get("needs"))
        self.assertEqual(sum(sum(r) for r in mine["calls"]) + sum(sum(r) for r in self.vb.for_site(KEY, f, "B")["calls"]), sum(sum(r) for r in f["calls"]))

    def test_the_requirement_workbook_says_why_it_cannot_be_made(self):
        f = self.vb.forecast(KEY, "Phone", SUN + timedelta(weeks=1), total=8000)
        with self.assertRaises(ValueError) as caught:
            self.vb.requirement_workbook(KEY, SUN + timedelta(weeks=1), {"Phone": f}, site="A")
        self.assertIn("interval compliance", str(caught.exception))


class TheSettingsSavedBeforePhaseBL(unittest.TestCase):
    OLD = {"Phone": {"aht": 280, "sl_target": 85, "sl_seconds": 25, "occupancy": 90, "shrinkage": 28, "concurrency": 1.0, "forecast_weeks": 8, "band_low": 90,
                     "band_high": 110}, "zone": "Africa/Cairo"}

    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {})
        self.store.set_volume_settings(KEY, dict(self.OLD), 1)

    def test_everything_new_reads_as_nothing_set(self):
        self.assertEqual(self.vb.open_hours(KEY), {c: {"min_cover": 1, "days": {}} for c in ("Phone", "Chat", "Email")})
        self.assertEqual(self.vb.sites(KEY), {"sites": [], "rules": []})
        self.assertEqual(self.vb.outlook_index(KEY, "Phone"), {})
        self.assertEqual(self.vb.settings(KEY)["Phone"]["aht"], 280)
        self.assertEqual(self.vb.zone(KEY), "Africa/Cairo")

    def test_the_forecast_is_what_it_was(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        _, plain = book()
        scaled(plain.store, {})
        plain.store.set_volume_settings(KEY, dict(self.OLD), 1)
        self.assertEqual(f["needs"], plain.forecast(KEY, "Phone", SUN, total=8000)["needs"])
        self.assertEqual(f["calls"], plain.forecast(KEY, "Phone", SUN, total=8000)["calls"])
        self.assertTrue(f["needs"] and f["service"])

    def test_saving_one_new_thing_keeps_the_old_settings(self):
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 2, "days": {"1": [540, 1260]}}}, 1)
        self.vb.set_sites(KEY, {"sites": [{"name": "A", "lob": ""}], "rules": []}, 1)
        self.vb.set_outlook_index(KEY, "Phone", {1: "120"}, 1)
        saved = self.store.volume_settings(KEY)
        self.assertEqual(saved["Phone"], self.OLD["Phone"])
        self.assertEqual(saved["zone"], "Africa/Cairo")
        self.assertEqual({k for k in saved} - {"Phone", "zone"}, {"hours", "sites", "outlook"})

    def test_an_event_saved_before_hours_existed_still_reads_and_works(self):
        old = {"kind": "Promotion", "name": "Sale", "channels": ["Phone"], "start": (SUN + timedelta(days=2)).isoformat(), "end": (SUN + timedelta(days=3)).isoformat(),
               "change": 20, "after_days": 0, "after_change": 0.0, "id": "e1"}
        self.store.set_volume_drivers(KEY, {"events": [old], "ai": [], "growth": {"yoy": {}, "method": "measured"}, "last_year": {}, "skip_weeks": [], "seq": 1}, 1)
        got = self.vb.drivers(KEY)["events"][0]
        self.assertEqual((got["hours"], got["window"], got["change"]), ("normal", None, 20.0))
        self.assertTrue(self.vb.forecast(KEY, "Phone", SUN, total=8000)["needs"])


class TheLargestInputsAllowed(unittest.TestCase):
    def test_six_sites_and_sixty_rules(self):
        names = [f"Site {i}" for i in range(6)]
        rules = []
        for i in range(60):
            day, band = divmod(i, 8)
            rules.append({"channel": ("Phone", "Chat", "Email")[i % 3], "days": [(day + i) % 7], "from": (band * 180) % 1440, "to": (band * 180) % 1440 + 180,
                          "shares": {n: (100.0 if j == i % 6 else 0.0) for j, n in enumerate(names)}})
        started = time.time()
        try:
            doc = S.clean({"sites": [{"name": n, "lob": "x" * 80} for n in names], "rules": rules})
        except ValueError as exc:
            self.assertIn("overlap", str(exc))                                     # a crowded random pile may overlap: said in words
            return
        for channel in ("Phone", "Chat", "Email"):
            S.table(doc, channel, 5)
            S.gaps(doc, channel)
        self.assertLess(time.time() - started, 5.0)

    def test_two_years_of_history_and_24_months_at_five_minute_intervals(self):
        store, vb = book()
        vb.step_of = lambda key: 5
        long_history(store, 104, season=yearly)
        started = time.time()
        got = vb.outlook(KEY, "Phone", start=SUN + timedelta(weeks=1), months=24)
        took = time.time() - started
        self.assertEqual(len(got["months"]), 24)
        self.assertLess(took, 20.0, f"took {took:.1f}s")


if __name__ == "__main__":
    unittest.main()
