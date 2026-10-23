# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "everything by default should match the pc timezone unless it has been changed manually to be kept as it
is"): a page with no zone in its address shows times in the zone the person's computer reports (the ``pc_tz`` cookie app.js keeps), when it
is one of the zones the pages offer, else Egypt as before. A zone picked on the page stays for that program, whatever the computer says."""
import html
import re
import unittest

from webapp.tests.test_overtime_side import WED, _Overtime


class ThePcZoneDefault(_Overtime):
    def setUp(self):
        self.client.delete_cookie("pc_tz")
        self.addCleanup(self.client.delete_cookie, "pc_tz")
        with self.client.session_transaction() as kept:
            kept.pop("rta", None)

    def chosen(self, **query):
        got = self.client.get("/day", query_string={"program": self.key, "date": WED.isoformat(), "view": "board", **query})
        body = html.unescape(got.get_data(as_text=True))
        select = re.search(r'<label>Times in <select name="tz"[^>]*>(.*?)</select>', body, re.S).group(1)
        return re.search(r'<option value="([^"]+)" selected>', select).group(1)

    def test_without_a_cookie_it_is_egypt_as_before(self):
        self.assertEqual(self.chosen(), "Africa/Cairo")

    def test_the_computers_zone_is_the_default(self):
        self.client.set_cookie("pc_tz", "Asia/Dubai")
        self.assertEqual(self.chosen(), "Asia/Dubai")

    def test_a_zone_the_pages_do_not_offer_falls_back_to_egypt(self):
        self.client.set_cookie("pc_tz", "Pacific/Auckland")
        self.assertEqual(self.chosen(), "Africa/Cairo")
        self.client.set_cookie("pc_tz", "../../etc/passwd")
        self.assertEqual(self.chosen(), "Africa/Cairo")

    def test_a_zone_picked_on_the_page_is_kept_over_the_computers(self):
        self.client.set_cookie("pc_tz", "Asia/Dubai")
        self.assertEqual(self.chosen(tz="UTC"), "UTC")
        self.assertEqual(self.chosen(), "UTC")  # no zone in the address: the pick stays for this program


if __name__ == "__main__":
    unittest.main()
