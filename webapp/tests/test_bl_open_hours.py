# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 4 (owner, 2026-11-07): "add in the settings our working hours per day, because some intervals we are operating
despite not receiving calls".

Per channel the Settings tab holds the hours the channel is worked, for each weekday, and a minimum cover (default 1):
- a day with hours: inside them every interval needs at least the minimum cover, even with no volume; outside them it needs nobody;
- a day marked closed needs nobody; hours may run past midnight (22:00 to 06:00 belongs to the day that starts it);
- a day with nothing set is as before: no minimum, no limit (so a program that sets nothing sees no change);
- Email has the closing rule but no minimum cover (its service level is 24 hours, the work is volume based).
Hours are kept with the settings, and saving the settings keeps them (and the zone) intact.
Made-up data only."""
import html
import unittest

from webapp import open_hours as H
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_runs import sign_in, token
from webapp.tests.test_bi_volumes import KEY, SUN, book, history
from webapp.tests.test_bj_volumes_book import scaled


class TheHoursOfOneChannel(unittest.TestCase):
    def test_nothing_set_is_open_all_day_with_no_minimum(self):
        self.assertIsNone(H.ranges({}, 3))
        self.assertEqual(H.apply([0, 0, 2, 0], None, 360, 1), [0, 0, 2, 0])

    def test_an_unset_day_after_an_overnight_day_keeps_its_volume_after_the_spill(self):
        """Found by the fuzz test (audit, 2026-11-08): Monday 11:45 to Tuesday 09:30 with Tuesday unset zeroed the rest of Tuesday, as if
        an unset day had become closed. The spill gets the minimum cover; the rest of the unset day is left alone, as an unset day always is."""
        hours = H.read({"days": {"1": [705, 2011]}, "min_cover": 1})
        ranges = H.ranges(hours, 2)
        free = H.free_from(hours, 2)
        self.assertEqual((ranges, free), ([(0, 571)], 571))
        needs = [0.0] * 24
        needs[3], needs[9], needs[14] = 0, 4, 2          # 03:00 inside the spill and quiet, 09:00 straddles its end, 14:00 after it
        got = H.apply(needs, ranges, 60, 1, free)
        self.assertEqual([got[3], got[9], got[14], got[20]], [1, 4, 2, 0])
        self.assertIsNone(H.free_from(hours, 1))          # a day with its own hours has none
        self.assertIsNone(H.free_from(H.read({"days": {"1": [705, 2011], "2": None}, "min_cover": 1}), 2))  # a closed day is closed

    def test_a_day_closed_needs_nobody(self):
        hours = H.read({"days": {"0": None}, "min_cover": 1})
        self.assertEqual(H.ranges(hours, 0), [])
        self.assertEqual(H.apply([3, 2, 1, 0], H.ranges(hours, 0), 360, 1), [0, 0, 0, 0])

    def test_inside_the_hours_a_quiet_interval_keeps_the_minimum_and_outside_needs_nobody(self):
        hours = H.read({"days": {"1": [9 * 60, 21 * 60]}, "min_cover": 1})
        ranges = H.ranges(hours, 1)
        self.assertEqual(ranges, [(540, 1260)])
        needs = [0.0] * 24  # one interval an hour
        needs[3], needs[12], needs[22] = 4, 0.4, 5  # 03:00 outside, 12:00 inside and quiet, 22:00 outside
        got = H.apply(needs, ranges, 60, 1)
        self.assertEqual([got[3], got[12], got[22]], [0, 1, 0])
        self.assertEqual([got[h] for h in (9, 10, 20)], [1, 1, 1])
        self.assertEqual([got[h] for h in (8, 21)], [0, 0])

    def test_the_minimum_never_lowers_what_the_volume_needs(self):
        hours = H.read({"days": {"1": [0, 1440]}, "min_cover": 2})
        self.assertEqual(H.apply([5, 1, 0], H.ranges(hours, 1), 480, 2), [5, 2, 2])

    def test_no_minimum_cover_applies_only_the_closing_rule(self):
        self.assertEqual(H.apply([5, 1, 0], [(0, 480)], 480, 0), [5, 0, 0])

    def test_hours_past_midnight_belong_to_the_day_that_starts_them(self):
        hours = H.read({"days": {"1": [22 * 60, 6 * 60 + 1440]}, "min_cover": 1})
        self.assertEqual(H.ranges(hours, 1), [(1320, 1440)])
        self.assertEqual(H.ranges(hours, 2), [(0, 360)])  # Tuesday's first six hours are Monday night's
        self.assertEqual(H.ranges(hours, 0), None)        # Sunday has nothing set

    def test_a_week_wraps_saturday_into_sunday(self):
        hours = H.read({"days": {"6": [20 * 60, 2 * 60 + 1440]}, "min_cover": 1})
        self.assertEqual(H.ranges(hours, 0), [(0, 120)])

    def test_a_damaged_value_is_ignored_not_trusted(self):
        hours = H.read({"days": {"1": ["x", 5], "9": [0, 60], "2": [600, 600]}, "min_cover": "many"})
        self.assertEqual(hours, {"min_cover": 1, "days": {}})


class TheFormIsCheckedWhole(unittest.TestCase):
    def form(self, **kw):
        values = {"min_cover": "1"}
        for d in range(7):
            values[f"{d}.from"], values[f"{d}.to"], values[f"{d}.closed"] = "", "", ""
        values.update(kw)
        return values

    def test_a_typed_week(self):
        got = H.from_form(self.form(**{"1.from": "09:00", "1.to": "21:00", "2.from": "22:00", "2.to": "06:00", "3.closed": "1"}), "Phone")
        self.assertEqual(got["days"], {"1": [540, 1260], "2": [1320, 1800], "3": None})
        self.assertEqual(got["min_cover"], 1)

    def test_midnight_to_midnight_is_the_whole_day(self):
        self.assertEqual(H.from_form(self.form(**{"1.from": "00:00", "1.to": "24:00"}), "Phone")["days"], {"1": [0, 1440]})

    def test_refusals_are_in_words_and_name_the_day(self):
        for kw, word in ((  {"1.from": "9am", "1.to": "21:00"}, "Mon"), ({"1.from": "09:00"}, "Mon"), ({"1.from": "09:00", "1.to": "09:00"}, "Mon"),
                         ({"4.from": "25:00", "4.to": "26:00"}, "Thu"), ({"min_cover": "-1"}, "minimum"), ({"min_cover": "x"}, "minimum"),
                         ({"min_cover": "99"}, "minimum")):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError) as caught:
                    H.from_form(self.form(**kw), "Phone")
                self.assertIn(word, str(caught.exception))


class TheHoursInTheBook(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {})

    def needs(self, channel="Phone", total=8000):
        return self.vb.forecast(KEY, channel, SUN, total=total)["needs"]

    def test_nothing_set_changes_nothing(self):
        before = self.needs()
        self.vb.set_settings(KEY, {"Phone": {"forecast_weeks": 6}}, 1)  # saving other settings is not setting hours
        self.assertEqual(self.vb.open_hours(KEY)["Phone"], {"min_cover": 1, "days": {}})
        self.assertEqual(self.needs(), before)

    def test_hours_close_the_night_and_keep_a_person_on_a_quiet_interval(self):
        before = self.needs()
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 2, "days": {"1": [9 * 60, 21 * 60]}}}, 1)
        after = self.needs()
        self.assertEqual(after[1][3], 0)                       # Monday 03:00: closed, whatever the volume
        self.assertGreaterEqual(min(after[1][9:21]), 2)        # Monday 09:00 to 21:00: at least the minimum cover
        self.assertTrue(all(after[1][h] >= before[1][h] for h in range(9, 21)))   # never fewer than the volume needs
        self.assertEqual(after[2], before[2])                  # Tuesday is not set: as before

    def test_a_closed_day_needs_nobody(self):
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 1, "days": {"0": None}}}, 1)
        self.assertEqual(sum(self.needs()[0]), 0)

    def test_the_service_level_is_not_shown_where_nobody_is_needed(self):
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 1, "days": {"1": [9 * 60, 21 * 60]}}}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertTrue(all(f["service"][1][h] is None for h in range(0, 9)))

    def test_email_has_the_closing_rule_but_no_minimum_cover(self):
        scaled(self.store, {}, channel="Email", per_week=700, aht=600.0)
        self.vb.set_open_hours(KEY, {"Email": {"min_cover": 5, "days": {"1": [9 * 60, 17 * 60]}}}, 1)
        got = self.needs("Email", 700)
        self.assertEqual(got[1][3], 0)
        self.assertLess(max(got[1][9:17]), 5)                  # the minimum is ignored for email

    def test_saving_the_settings_keeps_the_hours_and_the_zone(self):
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 1, "days": {"1": [540, 1260]}}}, 1)
        self.vb.set_zone(KEY, "America/New_York", 1)
        self.vb.set_settings(KEY, {"Chat": {"occupancy": 80}}, 1)
        self.assertEqual(self.vb.open_hours(KEY)["Phone"]["days"], {"1": [540, 1260]})
        self.assertEqual(self.vb.zone(KEY), "America/New_York")
        self.vb.set_open_hours(KEY, {"Chat": {"min_cover": 1, "days": {}}}, 1)   # and saving hours keeps the settings
        self.assertEqual(self.vb.settings(KEY)["Chat"]["occupancy"], 80)
        self.assertEqual(self.vb.open_hours(KEY)["Phone"]["days"], {"1": [540, 1260]})

    def test_a_channel_that_does_not_exist_is_refused(self):
        with self.assertRaises(ValueError):
            self.vb.set_open_hours(KEY, {"Fax": {"min_cover": 1, "days": {}}}, 1)


class TheHoursOnTheSettingsTab(_Volumes):
    def tearDown(self):
        self.store.set_volume_settings(self.alpha, {}, 1)

    def save(self, client, **fields):
        return client.post("/volumes/settings", data={"program": self.alpha, "csrf_token": token(client), **fields}, follow_redirects=True)

    def page(self, client):
        return html.unescape(client.get("/volumes", query_string={"program": self.alpha, "tab": "settings"}).get_data(as_text=True))

    def test_hours_are_typed_saved_and_shown_again(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = self.save(client, **{"hours.Phone.min_cover": "2", "hours.Phone.1.from": "09:00", "hours.Phone.1.to": "21:00",
                                   "hours.Phone.2.from": "22:00", "hours.Phone.2.to": "06:00", "hours.Phone.0.closed": "1"})
        self.assertIn("Saved the settings", html.unescape(got.get_data(as_text=True)))
        self.assertEqual(self.vb.open_hours(self.alpha)["Phone"],
                         {"min_cover": 2, "days": {"0": None, "1": [540, 1260], "2": [1320, 1800]}})
        page = self.page(client)
        self.assertIn('name="hours.Phone.1.from" value="09:00"', page)
        self.assertIn('name="hours.Phone.2.to" value="06:00"', page)
        self.assertRegex(page, r'name="hours.Phone.0.closed"[^>]*checked')
        self.assertIn('name="hours.Phone.min_cover" value="2"', page)

    def test_one_bad_hour_saves_nothing_at_all_and_says_which(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = self.save(client, **{"Phone.sl_target": "95", "hours.Phone.1.from": "9am", "hours.Phone.1.to": "21:00"})
        self.assertIn("Phone, Mon", html.unescape(got.get_data(as_text=True)))
        self.assertEqual(self.vb.open_hours(self.alpha)["Phone"], {"min_cover": 1, "days": {}})
        self.assertEqual(self.vb.settings(self.alpha)["Phone"]["sl_target"], 80)

    def test_a_form_without_hours_leaves_the_hours_alone(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.save(client, **{"hours.Chat.1.from": "08:00", "hours.Chat.1.to": "16:00"})
        self.save(client, **{"Phone.sl_target": "90"})
        self.assertEqual(self.vb.open_hours(self.alpha)["Chat"]["days"], {"1": [480, 960]})
        self.assertEqual(self.vb.settings(self.alpha)["Phone"]["sl_target"], 90)

    def test_clearing_a_day_unsets_it(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.save(client, **{"hours.Chat.1.from": "08:00", "hours.Chat.1.to": "16:00"})
        self.save(client, **{"hours.Chat.min_cover": "1", "hours.Chat.1.from": "", "hours.Chat.1.to": ""})
        self.assertEqual(self.vb.open_hours(self.alpha)["Chat"]["days"], {})


if __name__ == "__main__":
    unittest.main()
