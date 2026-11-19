# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 5 (owner, 2026-11-07): "for emails I can share historical day by day, not per interval, as it doesn't matter ... email
SL is 24 hours and it should be calculated not using Erlang but volume based: 10 emails requiring 80 minutes will schedule 1 agent".

- Email history may be a day total (Date, Emails, and an optional AHT) instead of a row per interval. A day total is kept spread evenly over
  the day's intervals; the whole number of emails is kept. Only email may be given this way.
- The email people-needed stays volume based (no Erlang): emails x handle time / (interval x occupancy). With no hours set it is worked out
  per interval as before. With hours set (Settings, or a holiday's reduced hours) the day's work is spread evenly over the intervals that are
  open, so none of it is lost to the hours the channel is closed; a day with email and no open interval says so.
Made-up numbers only."""
import unittest
from datetime import date, timedelta

from webapp import erlang
from webapp.tests.test_bi_volumes import KEY, SUN, book
from webapp.tests.test_bj_volumes_book import scaled
from webapp.tests.test_bi_volumes_routes import PASSWORD, TODAY as ROUTE_TODAY, _Volumes
from webapp.tests.test_runs import sign_in, token
from webapp.volumes_io import parse_long

TODAY = date(2026, 11, 7)
DAYS = [date(2026, 11, 1) + timedelta(days=k) for k in range(3)]


def table(rows, header=("Date", "Emails", "AHT")):
    return [list(header), *[list(r) for r in rows]]


class TheDayTotals(unittest.TestCase):
    def test_a_day_total_is_kept_spread_over_the_day_with_every_email(self):
        got = parse_long(table([(DAYS[0], 100), (DAYS[1], 7)]), "Email", 60, TODAY)
        self.assertEqual(got.problems, [])
        rows = got.rows["Email"]
        self.assertEqual(len(rows), 48)
        for day, total in ((DAYS[0].isoformat(), 100), (DAYS[1].isoformat(), 7)):
            kept = [r[2] for r in rows if r[0] == day]
            self.assertEqual((len(kept), sum(kept), max(kept) - min(kept) <= 1), (24, total, True))

    def test_the_interval_is_the_programs_own(self):
        got = parse_long(table([(DAYS[0], 100)]), "Email", 30, TODAY)
        self.assertEqual(len(got.rows["Email"]), 48)
        self.assertEqual(sum(r[2] for r in got.rows["Email"]), 100)

    def test_the_handle_time_goes_with_the_day(self):
        got = parse_long(table([(DAYS[0], 24, 480)]), "Email", 60, TODAY)
        self.assertEqual({r[3] for r in got.rows["Email"]}, {480.0})
        self.assertEqual(parse_long(table([(DAYS[0], 24, "")]), "Email", 60, TODAY).rows["Email"][0][3], None)

    def test_a_channel_column_can_say_email(self):
        got = parse_long([["Date", "Channel", "Emails"], [DAYS[0], "Email", 48]], None, 60, TODAY)
        self.assertEqual(sum(r[2] for r in got.rows["Email"]), 48)

    def test_only_email_may_be_given_as_a_day_total(self):
        for channel in ("Phone", "Chat"):
            with self.subTest(channel=channel):
                with self.assertRaises(ValueError) as caught:
                    parse_long(table([(DAYS[0], 100)]), channel, 60, TODAY)
                self.assertIn("email", str(caught.exception).lower())

    def test_bad_rows_are_named_and_nothing_is_kept(self):
        got = parse_long(table([(DAYS[0], 10), ("not a date", 5), (DAYS[1], -3), (DAYS[2], 2.5), (DAYS[0], 4)]), "Email", 60, TODAY)
        self.assertEqual(got.rows, {})
        text = " ".join(got.problems)
        for row in (3, 4, 5, 6):
            self.assertIn(f"Row {row}", text)

    def test_the_interval_layout_still_works_for_email(self):
        rows = [[DAYS[0], f"{h:02d}:00", 5] for h in range(24)]
        got = parse_long([["Date", "Interval", "Emails"], *rows], "Email", 60, TODAY)
        self.assertEqual((got.problems, sum(r[2] for r in got.rows["Email"])), ([], 120))


class TheEmailWork(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {}, channel="Email", per_week=7000, aht=480.0)
        self.vb.set_settings(KEY, {"Email": {"aht": 480, "occupancy": 100}}, 1)

    def forecast(self, total=7000):
        return self.vb.forecast(KEY, "Email", SUN, total=total)

    def agent_minutes(self, f, d):
        return sum(f["needs"][d]) * self.vb.step(KEY)

    def test_with_no_hours_it_is_the_per_interval_workload_as_before(self):
        f = self.forecast()
        want = [round(erlang.workload_agents(c, 480.0, 3600, 1.0), 2) if c else 0 for c in f["calls"][1]]
        self.assertEqual(f["needs"][1], want)

    def test_the_80_minute_example(self):
        self.vb.set_open_hours(KEY, {"Email": {"min_cover": 0, "days": {"1": [9 * 60, 11 * 60]}}}, 1)
        f = self.forecast()
        sent = sum(f["calls"][1])
        self.assertGreater(sent, 0)
        # 480 seconds each at full occupancy: 8 minutes of agent time per email, spread over the two open hours
        self.assertAlmostEqual(self.agent_minutes(f, 1), sent * 8.0, delta=2.0)
        self.assertEqual([i for i, n in enumerate(f["needs"][1]) if n], [9, 10])
        self.assertAlmostEqual(f["needs"][1][9], f["needs"][1][10], places=2)

    def test_hours_do_not_lose_the_nights_email(self):
        before = self.forecast()
        self.vb.set_open_hours(KEY, {"Email": {"min_cover": 0, "days": {"1": [9 * 60, 17 * 60]}}}, 1)
        after = self.forecast()
        self.assertAlmostEqual(self.agent_minutes(after, 1), self.agent_minutes(before, 1), delta=3.0)
        self.assertEqual(sum(after["needs"][1][:9]) + sum(after["needs"][1][17:]), 0)
        self.assertEqual(after["needs"][2], before["needs"][2])   # an unset day is as before

    def test_a_holidays_reduced_hours_work_the_same_way(self):
        tuesday = SUN + timedelta(days=2)
        event = {"kind": "Holiday", "name": "Founders day", "channels": ["Email"], "start": tuesday.isoformat(), "end": tuesday.isoformat(),
                 "change": "", "hours": "reduced", "open_from": "10:00", "open_to": "14:00"}
        before = self.forecast()
        self.vb.add_driver(KEY, "events", event, 1)
        after = self.forecast()
        self.assertEqual([i for i, n in enumerate(after["needs"][2]) if n], [10, 11, 12, 13])
        self.assertAlmostEqual(self.agent_minutes(after, 2), self.agent_minutes(before, 2), delta=3.0)

    def test_email_on_a_closed_day_is_said_not_lost_quietly(self):
        self.vb.set_open_hours(KEY, {"Email": {"min_cover": 0, "days": {"0": None}}}, 1)
        f = self.forecast()
        self.assertEqual(sum(f["needs"][0]), 0)
        self.assertTrue([n for n in f["notes"] if "Sun" in n and "closed" in n.lower()], f["notes"])


class TheDayTotalsOnThePage(_Volumes):
    def paste(self, client, text, channel="Email"):
        return client.post("/volumes/actuals/check", data={"program": self.alpha, "csrf_token": token(client), "channel": channel, "paste": text})

    def test_a_pasted_table_of_day_totals_is_checked_and_saved_for_email(self):
        import html
        client = sign_in(self.app, "plan_a", PASSWORD)
        first = ROUTE_TODAY - timedelta(days=5)
        text = "Date\tEmails\tAHT\n" + "\n".join(f"{(first + timedelta(days=k)).isoformat()}\t{100 + k}\t480" for k in range(3))
        got = html.unescape(self.paste(client, text).get_data(as_text=True))
        self.assertIn("spread evenly", got)
        self.assertRegex(got, r'name="token" value="[^"]+"')
        tok = __import__("re").search(r'name="token" value="([^"]+)"', got).group(1)
        client.post("/volumes/actuals/save", data={"program": self.alpha, "csrf_token": token(client), "token": tok})
        rows = self.store.volume_rows(self.alpha, "Email", first.isoformat(), (first + timedelta(days=2)).isoformat())
        self.assertEqual(sum(r["offered"] for r in rows if r["day"] == first.isoformat()), 100)
        self.store.delete_volume_days(self.alpha, "Email", first.isoformat(), (first + timedelta(days=2)).isoformat())

    def test_the_same_table_for_phone_is_refused_in_words(self):
        import html
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = html.unescape(self.paste(client, "Date\tEmails\n2026-11-01\t10", "Phone").get_data(as_text=True))
        self.assertIn("only for email", got)


if __name__ == "__main__":
    unittest.main()
