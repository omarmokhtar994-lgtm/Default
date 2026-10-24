# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AO (owner, 2026-10-20: "They cant swap full week"; answer: as recommended). A full-week swap is one request:
the two people exchange each day of the week from today on, each day's shift or day off, with the rules (and any
warnings) shown per day. A day either has Leave on, or already passed, or has both off, or is the same shift, is left
as it is and said. Approval swaps every day as one new version, set in use."""
import json
import unittest
from datetime import date

from webapp.tests import test_ag_swaps
from webapp.tests.test_ag_swaps import TUE

SUN = date(2026, 10, 11)
A, B = "Associate 027", "Associate 038"   # 027: Sun-Tue 10-19, Wed-Thu 11-20; 038: Leave Sun-Mon, then 01-10 Thu, 22-07 Fri-Sat


class TheWeek(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_ag_swaps.Swaps.setUpClass.__func__(cls)
        cls.book = cls.app.extensions["swaps"]
        cls.days = cls.app.extensions["days"]

    @classmethod
    def tearDownClass(cls):
        test_ag_swaps.Swaps.tearDownClass.__func__(cls)

    def cells(self, name):
        return [dict(self.days.roster(self.key, date.fromordinal(SUN.toordinal() + i))).get(name, "") for i in range(7)]

    def test_each_day_has_a_status(self):
        found = self.book.week_check(self.key, SUN, A, B, today=TUE)
        got = {d["day"]: d["status"] for d in found["days"]}
        self.assertEqual(got["Sun"], "past")
        self.assertEqual(got["Mon"], "past")
        self.assertEqual([got[d] for d in ("Tue", "Wed", "Thu", "Fri", "Sat")], ["swap"] * 5)

    def test_leave_days_are_left_as_they_are(self):
        found = self.book.week_check(self.key, SUN, A, B, today=date(2026, 10, 10))
        got = {d["day"]: d["status"] for d in found["days"]}
        self.assertEqual((got["Sun"], got["Mon"]), ("leave", "leave"))

    def test_one_who_has_the_day_off_takes_the_shift_with_its_rest_checked(self):
        tue = next(d for d in self.book.week_check(self.key, SUN, A, B, today=TUE)["days"] if d["day"] == "Tue")
        self.assertEqual((tue["a_cell"], tue["b_cell"]), ("10:00 - 19:00", "OFF"))
        self.assertEqual(tue["status"], "swap")

    def test_the_colleagues_listed_say_the_days_and_warnings(self):
        found = {c["name"]: c for c in self.book.week_candidates(self.key, SUN, A, today=TUE)}
        self.assertIn(B, found)
        self.assertEqual(found[B]["swap_days"], 5)
        self.assertTrue(found[B]["has_account"])
        self.assertIsInstance(found[B]["problems"], list)

    def test_a_week_with_warnings_needs_them_allowed_and_a_week_without_nothing_to_swap_is_refused(self):
        check = self.book.week_check(self.key, SUN, A, B, today=TUE)
        if any(d["problems"] for d in check["days"]):
            with self.assertRaisesRegex(ValueError, r"(Tue|Wed|Thu|Fri|Sat) \d+ Oct"):
                self.book.offer_week(self.key, SUN, A, self.users["a027"]["id"], B, "", today=TUE)
        with self.assertRaisesRegex(ValueError, "Nothing to swap"):
            self.book.offer_week(self.key, SUN, A, self.users["a027"]["id"], B, "", today=date(2026, 10, 18))

    def test_the_request_then_approval_swaps_every_day_as_one_version(self):
        before_a, before_b = self.cells(A), self.cells(B)
        sid = self.book.offer_week(self.key, SUN, A, self.users["a027"]["id"], B, "whole week", today=TUE,
                                   allow_warnings=True)
        row = self.store.get_swap(sid)
        self.assertEqual((row["scope"], row["status"]), ("week", "waiting_other"))
        self.assertEqual([d["date"] for d in json.loads(row["detail"])["days"]],
                         ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17"])
        self.book.answer(sid, self.users["a038"], accept=True)
        said = self.book.decide(sid, self.users["tm1"], approve=True)
        self.assertIn("Approved:", said)
        after_a, after_b = self.cells(A), self.cells(B)
        for i in range(2, 7):  # Tue to Sat exchanged
            self.assertEqual((after_a[i], after_b[i]), (before_b[i], before_a[i]), i)
        self.assertEqual((after_a[0], after_a[1]), (before_a[0], before_a[1]))  # Sunday and Monday as they were
        version = self.days.version(self.key, SUN)[0]
        self.assertTrue(version["in_use"])
        self.assertIn("Week swap of", version["label"])

    def test_two_requests_cannot_overlap(self):
        with self.assertRaisesRegex(ValueError, "already has a swap waiting"):
            self.book.offer_week(self.key, SUN, A, self.users["a027"]["id"], "Associate 033", "", today=TUE,
                                 allow_warnings=True)
            self.book.offer_week(self.key, SUN, A, self.users["a027"]["id"], "Associate 033", "", today=TUE,
                                 allow_warnings=True)


class TheWeekOnMyWeek(unittest.TestCase):
    """The associate's own page: pick a week, see the colleagues and what changes, send the request."""

    @classmethod
    def setUpClass(cls):
        test_ag_swaps.Swaps.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        test_ag_swaps.Swaps.tearDownClass.__func__(cls)

    def test_the_page_offers_the_week_and_sends_the_request(self):
        from unittest import mock
        from webapp.tests.test_ag_leave import _Clock
        from webapp.tests.test_runs import TOKEN, sign_in
        me = sign_in(self.app, "a027", "Associate-pass-1")
        with mock.patch("webapp.app.datetime", _Clock):
            page = me.get("/me?swapweek=2026-10-11").get_data(as_text=True)
            self.assertIn("Swap the whole week", page)
            self.assertIn('<option value="2026-10-11" selected>', page)
            self.assertIn('name="week" value="2026-10-11"', page)
            self.assertIn("5 days change", page)
            tok = TOKEN.search(page).group(1)
            got = me.post("/me/swap", data={"csrf_token": tok, "week": "2026-10-11", "other": "Associate 038",
                                            "anyway": "1"})
            self.assertEqual(got.status_code, 302)
            after = me.get("/me").get_data(as_text=True)
        self.assertIn("Sent to Associate 038: the week from", after)
        self.assertIn("Week from Tue 13 Oct", after)


if __name__ == "__main__":
    unittest.main()
