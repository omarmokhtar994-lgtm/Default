# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "when I change something, how long until it shows on the associate view if it is already open?",
then "1 and 2, 30 seconds"): an open page asks a small address every 30 seconds whether what it shows has changed. Read-only pages
(My day, My week, Overview) reload by themselves; pages where people are in the middle of something (the RTA day, Requests) show
a bar instead. The answer is a stamp of what the page shows, not the database write counter: opening a page writes the "day seen"
mark, and that must not make every other open page reload."""
import json
import re
import unittest

from webapp.live import KEEP, Stamps, digest
from webapp.tests.test_as_pages import _Pages
from webapp.tests.test_as_requests import ME, NIGHT, WED


class TheStamps(unittest.TestCase):
    def test_a_stamp_is_kept_for_a_few_seconds_so_many_askers_build_it_once(self):
        now = [100.0]
        stamps, made = Stamps(lambda: now[0]), []
        for _ in range(50):
            stamps.get("k", lambda: made.append(1) or "a")
        self.assertEqual(len(made), 1)
        now[0] += KEEP + 1
        self.assertEqual(stamps.get("k", lambda: "b"), "b")
        self.assertIn("51 asked, 2 built", stamps.line())

    def test_the_digest_follows_the_values_and_not_the_order_of_keys(self):
        self.assertEqual(digest({"a": 1, "b": [1, 2]}), digest({"b": [1, 2], "a": 1}))
        self.assertNotEqual(digest({"a": 1}), digest({"a": 2}))


class TheLiveStamp(_Pages):
    def stamp(self, client, **query):
        r = client.get("/live/stamp", query_string=query)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])
        return r.get_json()["stamp"]

    def move_break(self, name, start):
        row = self.app.extensions["days"].version(self.key, WED)[0]
        week = json.loads(row["week"])
        old = row["week"]
        for b in week["breaks"]:
            if b["associate"] == name and b["kind"] == "Break 1":
                b["start"] = start
        self.store.update_schedule(row["id"], week=json.dumps(week))
        self.addCleanup(self.store.update_schedule, row["id"], week=old)
        self.addCleanup(self.app.extensions["live"]._kept.clear)
        self.app.extensions["days"]._pages.clear()
        self.app.extensions["live"]._kept.clear()

    def test_the_associates_stamp_changes_when_their_own_break_moves(self):
        before = self.stamp(self.assoc, kind="me")
        self.assertEqual(self.stamp(self.assoc, kind="me"), before)
        self.move_break(ME, "13:30")
        self.assertNotEqual(self.stamp(self.assoc, kind="me"), before)

    def test_the_associates_stamp_ignores_a_colleagues_break_and_opening_a_page(self):
        before = self.stamp(self.assoc, kind="me")
        self.get(self.sup, "/day")  # somebody else opens pages: the day seen mark is written
        self.get(self.assoc, "/me/breaks")
        self.app.extensions["live"]._kept.clear()
        self.assertEqual(self.stamp(self.assoc, kind="me"), before)
        self.move_break(NIGHT, "00:45")
        self.assertEqual(self.stamp(self.assoc, kind="me"), before)

    def test_the_rtas_day_stamp_changes_when_anyones_break_moves(self):
        args = {"kind": "day", "program": "SAKS NMG Tier 2", "date": "2026-10-14"}
        before = self.stamp(self.staff, **args)
        self.move_break(NIGHT, "00:45")
        self.assertNotEqual(self.stamp(self.staff, **args), before)

    def test_the_requests_stamp_changes_when_a_request_arrives(self):
        before = self.stamp(self.staff, kind="requests", program="SAKS NMG Tier 2")
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first, why="Made-up: appointment")
        self.app.extensions["live"]._kept.clear()
        self.assertNotEqual(self.stamp(self.staff, kind="requests", program="SAKS NMG Tier 2"), before)

    def test_an_unknown_kind_and_a_program_the_person_may_not_see_are_refused(self):
        self.assertEqual(self.assoc.get("/live/stamp", query_string={"kind": "nope"}).status_code, 404)
        self.assertEqual(self.staff.get("/live/stamp", query_string={"kind": "day", "program": "No such program"}).status_code, 403)  # the site's wall for a program that is not theirs

    def test_a_person_who_is_not_signed_in_is_sent_to_sign_in(self):
        anyone = self.app.test_client()
        self.assertEqual(anyone.get("/live/stamp", query_string={"kind": "me"}).status_code, 302)

    def test_the_answer_is_never_kept_by_the_browser(self):
        r = self.assoc.get("/live/stamp", query_string={"kind": "me"})
        self.assertIn("no-store", r.headers.get("Cache-Control", ""))


class ThePagesThatWatch(_Pages):
    def mode(self, client, url, **query):
        page = self.get(client, url, **query)
        found = re.search(r'<div id="live"[^>]*data-mode="(\w+)"', page)
        return found.group(1) if found else None

    def test_my_day_and_my_week_and_the_overview_reload_by_themselves(self):
        self.assertEqual(self.mode(self.assoc, "/me/breaks"), "reload")
        self.assertEqual(self.mode(self.assoc, "/me"), "reload")
        self.assertEqual(self.mode(self.staff, "/overview"), "reload")

    def test_the_rta_day_and_requests_show_a_bar_and_never_reload(self):
        self.assertEqual(self.mode(self.staff, "/day"), "bar")
        self.assertEqual(self.mode(self.staff, "/requests"), "bar")

    def test_reports_and_setup_do_not_watch(self):
        for url in ("/incidents", "/shrinkage"):
            self.assertIsNone(self.mode(self.staff, url), url)

    def test_the_page_carries_the_stamp_it_was_built_from(self):
        page = self.get(self.assoc, "/me/breaks")
        found = re.search(r'<div id="live"[^>]*data-stamp="(\w+)"', page)
        self.assertTrue(found)
        r = self.assoc.get("/live/stamp", query_string={"kind": "me"})
        self.assertEqual(r.get_json()["stamp"], found.group(1))


class TheWatcherScript(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.js = Path(__file__).parents[1].joinpath("static", "app.js").read_text()

    def test_it_asks_every_30_seconds_with_a_spread_and_backs_off_after_a_failure(self):
        for needle in ("30000", "Math.random", "visibilitychange", "document.hidden", "liveWatch"):
            self.assertIn(needle, self.js)
        self.assertRegex(self.js, r"delay\s*=\s*Math\.min\(")

    def test_a_page_where_somebody_is_typing_gets_a_bar_not_a_reload(self):
        self.assertIn("The page changed", self.js)
        self.assertRegex(self.js, r"activeElement")


if __name__ == "__main__":
    unittest.main()
