# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T3: Go to (Ctrl K) jumps to any page, program or person (sample ag04, owner's approval 2026-10-14).

GET /goto?q=...&program=...&date=... answers JSON: pages whose name matches, programs the person may open, and the
people on that program's schedule that day (with their shift), each with the address to open. Every page has the
Go to button and its dialog.
"""
import unittest
from urllib.parse import quote_plus

from webapp.tests.test_channel_day import WED


class GoTo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def find(self, q, client=None):
        got = (client or self.admin).get(f"/goto?q={quote_plus(q)}&program={quote_plus(self.key)}&date={WED.isoformat()}")
        return got

    def test_pages(self):
        items = self.find("week").get_json()["items"]
        page = next(i for i in items if i["group"] == "Pages")
        self.assertEqual(page["label"], "Weeks")
        self.assertEqual(page["url"], f"/week?program={quote_plus(self.key)}")

    def test_people_with_their_shift_that_day(self):
        items = [i for i in self.find("associate 00").get_json()["items"] if i["group"] == "People"]
        self.assertTrue(items)
        self.assertLessEqual(len(items), 8)
        first = items[0]
        self.assertTrue(first["label"].startswith("Associate 00"))
        self.assertRegex(first["note"], r"^(Wed \d\d:\d\d to \d\d:\d\d|Off on Wed|On leave on Wed)")
        self.assertIn("who=" + quote_plus(first["label"]), first["url"])

    def test_programs(self):
        items = [i for i in self.find("tier").get_json()["items"] if i["group"] == "Programs"]
        self.assertEqual([i["label"] for i in items], ["SAKS, NMG Tier 2"])

    def test_signed_out_goes_to_sign_in(self):
        got = self.app.test_client().get("/goto?q=week")
        self.assertEqual(got.status_code, 302)

    def test_every_page_has_the_button_and_the_dialog(self):
        page = self.admin.get("/").get_data(as_text=True)
        self.assertIn("data-goto-open", page)
        self.assertIn('<dialog id="goto"', page)


if __name__ == "__main__":
    unittest.main()
