# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "an option to split the view in the RTA tab between 2-3 different LOBs or programs"; "make it a max of 2 or 3"):
/day/split shows 2 or 3 RTA pages side by side or stacked, each its own program, day, zone and tab. A pane is the ordinary RTA page embedded
(``embed=1``: no page header), so every check of the ordinary page holds in it. Only the embedded page may be framed, and only by this site."""
import html
import re
import unittest

from webapp.tests.test_overtime_side import WED, _Overtime
from webapp.tests.test_runs import token


class TheSplitPage(_Overtime):
    def split(self, **query):
        got = self.client.get("/day/split", query_string=query)
        return got, html.unescape(got.get_data(as_text=True))

    def frames(self, body):
        return re.findall(r'<iframe[^>]*class="split-pane[^"]*"[^>]*>', body)

    def test_two_programs_give_two_panes_each_pointing_at_the_embedded_day(self):
        got, body = self.split(p1=self.key, d1=WED.isoformat(), p2=self.key, d2="2026-10-15")
        self.assertEqual(got.status_code, 200)
        frames = self.frames(body)
        self.assertEqual(len(frames), 2)
        for frame in frames:
            self.assertIn("/day?", frame)
            self.assertIn("embed=1", frame)
        self.assertIn("date=2026-10-15", frames[1])

    def test_three_is_the_most(self):
        got, body = self.split(p1=self.key, p2=self.key, p3=self.key, p4=self.key)
        self.assertEqual(len(self.frames(body)), 3)

    def test_a_program_that_is_not_there_gets_a_message_not_a_pane(self):
        got, body = self.split(p1=self.key, p2="No such program")
        self.assertEqual(len(self.frames(body)), 1)
        self.assertIn("not one of your programs", body.lower())

    def test_one_pane_asks_for_a_second_and_the_page_offers_to_add_one(self):
        got, body = self.split(p1=self.key)
        self.assertEqual(len(self.frames(body)), 1)
        self.assertIn("Add a pane", body)

    def test_the_layout_is_stacked_or_side_by_side(self):
        _, rows = self.split(p1=self.key, p2=self.key, layout="rows")
        _, cols = self.split(p1=self.key, p2=self.key, layout="cols")
        self.assertIn("split-rows", rows)
        self.assertIn("split-cols", cols)


class TheEmbeddedDay(_Overtime):
    def day(self, **query):
        return self.client.get("/day", query_string={"program": self.key, "date": WED.isoformat(), **query})

    def test_only_the_embedded_day_may_be_framed_and_only_by_this_site(self):
        plain, embedded = self.day(), self.day(embed="1")
        self.assertEqual(plain.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", plain.headers["Content-Security-Policy"])
        self.assertEqual(embedded.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", embedded.headers["Content-Security-Policy"])
        split = self.client.get("/day/split", query_string={"p1": self.key})
        self.assertEqual(split.headers["X-Frame-Options"], "DENY")

    def test_the_embedded_page_has_no_page_header_and_keeps_embed_on_its_links(self):
        body = html.unescape(self.day(embed="1").get_data(as_text=True))
        self.assertRegex(body, r'<body[^>]*class="[^"]*\bembed\b')
        links = re.findall(r'href="(/day\?[^"]*view=[^"]*)"', body)
        self.assertTrue(links)
        self.assertTrue(all("embed=1" in link for link in links), links[:3])
        self.assertNotRegex(html.unescape(self.day().get_data(as_text=True)), r'<body[^>]*class="[^"]*\bembed\b')

    def test_a_change_made_in_a_pane_comes_back_to_the_embedded_page(self):
        got = self.client.post("/day/undo-last", data={"csrf_token": token(self.client), "program": self.key,
                                                       "date": WED.isoformat(), "embed": "1"})
        self.assertEqual(got.status_code, 303)
        self.assertIn("embed=1", got.headers["Location"])


if __name__ == "__main__":
    unittest.main()
