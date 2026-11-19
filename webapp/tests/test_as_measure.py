# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AS (owner, 2026-10-21): billable coaching follows the program's setup. Under interval compliance a billable
session keeps people on the floor, so it does not touch the intervals; under service level or volume weighted it does,
billable or not. The program says which in its setup; the RTA opens on it and so do the requests' choices and impact."""
import html
import unittest

from webapp.change_requests import ChangeBook
from webapp.programs import ProgramBook
from webapp.tests.test_as_requests import ME, MATE, WED, _Fixture, at
from webapp.tests.test_runs import make_app


class TheProgramSetting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.book = ProgramBook(cls.store)
        cls.pid = cls.book.add_program("SAKS")
        cls.lob = cls.book.add_lob(cls.pid, "Tier 1")

    def test_a_program_is_interval_compliance_until_it_says_otherwise(self):
        self.assertEqual(self.book.day_measure(self.lob), "interval")
        self.assertEqual(self.book.measure_setting(self.pid), "interval")

    def test_service_level_and_volume_weighted_both_count_billable_time_against_the_intervals(self):
        for value in ("sl", "volume"):
            self.book.set_measure(self.pid, value)
            self.assertEqual(self.book.measure_setting(self.pid), value)
            self.assertEqual(self.book.day_measure(self.lob), "sl", value)  # the RTA's name for "billable still counts"
        self.book.set_measure(self.pid, "interval")
        self.assertEqual(self.book.day_measure(self.lob), "interval")

    def test_something_else_is_refused(self):
        with self.assertRaises(ValueError):
            self.book.set_measure(self.pid, "weekly")

    def test_a_key_that_is_not_a_program_is_interval_compliance(self):
        self.assertEqual(self.book.day_measure("No such program"), "interval")


class TheRequestsFollowTheSetting(_Fixture):
    def setUp(self):
        self.clear()

    def options(self, measure, billable):
        book = ChangeBook(self.store, self.app.extensions["days"], measure_of=lambda program: measure)
        return {c["start"]: c["people_above"] for c in book.coaching_options(self.key, WED, [ME, MATE], 60, at(WED, 9),
                                                                              billable=billable)}

    def test_under_interval_compliance_billable_coaching_leaves_the_intervals_alone(self):
        non, bill = self.options("interval", False), self.options("interval", True)
        whole = [t for t in non if t in bill and non[t] is not None and t % 60 == 0]
        self.assertTrue(whole)
        self.assertTrue(all(abs(bill[t] - non[t] - 2) < 1e-6 for t in whole))

    def test_under_service_level_billable_coaching_counts_like_any_other(self):
        non, bill = self.options("sl", False), self.options("sl", True)
        self.assertEqual(non, bill)

    def test_the_impact_follows_too(self):
        book = ChangeBook(self.store, self.app.extensions["days"], measure_of=lambda program: "sl")
        first = next(t for t in self.options("sl", True) if t % 60 == 0)
        rid = book.ask_coaching(self.key, [ME, MATE], self.users["tm1"], WED, f"{first // 60:02d}:{first % 60:02d}", 60,
                                "", "", at(WED, 9), billable=True)
        rows = book.impact(self.store.get_change_request(rid))
        self.assertTrue(all(abs((r["before"] - r["after"]) - 2) < 1e-6 for r in rows), rows)  # billable, still two off


class TheRtaOpensOnTheProgramsMeasure(_Fixture):
    def test_the_measure_pick_starts_on_the_programs_setting_and_an_address_still_wins(self):
        book = ProgramBook(self.store)
        pid = next(p["id"] for p in book.tree() if p["name"] == "SAKS")
        url = {"program": self.key, "date": WED.isoformat()}
        try:
            book.set_measure(pid, "sl")
            page = html.unescape(self.admin.get("/day", query_string=url).get_data(as_text=True))
            self.assertIn('<option value="sl" selected>', page)
            page = html.unescape(self.admin.get("/day", query_string={**url, "measure": "interval"}).get_data(as_text=True))
            self.assertIn('<option value="interval" selected>', page)
        finally:
            book.set_measure(pid, "interval")
        page = html.unescape(self.admin.get("/day", query_string=url).get_data(as_text=True))
        self.assertIn('<option value="interval" selected>', page)

    def test_an_admin_sets_it_on_the_program_page(self):
        book = ProgramBook(self.store)
        pid = next(p["id"] for p in book.tree() if p["name"] == "SAKS")
        try:
            got = self.admin.post("/setup/programs", data={"csrf_token": self.token(self.admin), "action": "measure",
                                                           "program_id": str(pid), "coverage_measure": "volume"})
            self.assertIn(got.status_code, (200, 302, 303))
            self.assertEqual(book.measure_setting(pid), "volume")
        finally:
            book.set_measure(pid, "interval")


if __name__ == "__main__":
    unittest.main()
