# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: a "Replan the day's breaks" button in the RTA tab, so it only replans): every break not
yet started is lifted and placed again from scratch inside the rules the day page enforces (inside the shift, in order,
the program's gaps, clear of away time and activities, no language below its minimum). It changes nothing else, and
it is a proposal: the day is not touched until it is approved."""
import unittest

from webapp.day import replan
from webapp.tests import test_day as _td

INPUTS = _td.INPUTS


class TheFreshReplan(unittest.TestCase):
    def setUp(self):
        day = _td.TheDay("view")  # the day's own helpers, without running its tests again
        self.view, self.short_day, self.applied, self.own = day.view, day.short_day, day.applied, day.own

    def fresh(self, att=None, now=0):
        return replan(self.view(att), INPUTS, now, fresh=True)

    def test_it_is_a_proposal_of_moves_with_the_day_before_and_after(self):
        plan = self.fresh(self.short_day())
        self.assertEqual(set(plan), {"moves", "before", "after"})
        for m in plan["moves"]:
            self.assertEqual(set(m), {"name", "idx", "kind", "minutes", "from", "to"})
            self.assertNotEqual(m["from"], m["to"])

    def test_it_never_makes_the_day_worse_and_says_so_truly(self):
        att = self.short_day()
        plan = self.fresh(att)
        self.assertGreaterEqual(plan["after"]["tightest"], plan["before"]["tightest"])
        self.assertLessEqual(plan["after"]["short_hours"], plan["before"]["short_hours"])
        after, _ = self.applied(att, plan)
        self.assertAlmostEqual(plan["after"]["tightest"], min(c["pm"] for c in after["cells"] if c["pm"] is not None), places=2)
        self.assertAlmostEqual(plan["after"]["short_hours"], after["tiles"]["short_hours"], places=1)

    def test_it_keeps_every_rule_for_every_break_it_moves(self):
        att = self.short_day()
        plan = self.fresh(att)
        self.assertTrue(plan["moves"])
        after, _ = self.applied(att, plan)
        moved = {(m["name"], m["idx"]) for m in plan["moves"]}
        for name in {n for n, _ in moved}:
            seg = self.own(after, name)
            brks = sorted(seg["breaks"], key=lambda b: b["idx"])
            self.assertEqual([b["idx"] for b in sorted(brks, key=lambda b: b["start"])], [b["idx"] for b in brks])
            self.assertTrue(seg["start"] <= brks[0]["start"] and brks[-1]["start"] + brks[-1]["minutes"] <= seg["end"])
            for b in brks:
                self.assertEqual(b["start"] % 5, 0)
            for a, b in zip(brks, brks[1:]):
                gap = b["start"] - (a["start"] + a["minutes"])
                self.assertTrue(INPUTS["gap_min"] <= gap <= INPUTS["gap_max"], (name, a["kind"], b["kind"], gap))

    def test_a_break_that_has_started_is_left_where_it_is(self):
        plan = self.fresh(self.short_day(), now=18 * 60)
        self.assertTrue(all(m["from"] >= 18 * 60 and m["to"] >= 18 * 60 for m in plan["moves"]))

    def test_people_who_are_away_are_left_alone(self):
        att = self.short_day()
        gone = {n for (_, n) in att}
        self.assertFalse(gone & {m["name"] for m in self.fresh(att)["moves"]})

    def test_the_same_day_gives_the_same_proposal(self):
        att = self.short_day()
        self.assertEqual(self.fresh(att), self.fresh(att))

    def test_a_proposal_changes_only_breaks(self):
        att = self.short_day()
        plan = self.fresh(att)
        after, actual = self.applied(att, plan)
        before = self.view(att)
        for lane_b, lane_a in zip(before["lanes"], after["lanes"]):
            for sb, sa in zip(lane_b["segments"], lane_a["segments"]):
                self.assertEqual((sb["start"], sb["end"], sb["status"]), (sa["start"], sa["end"], sa["status"]))

    def test_the_other_mode_is_unchanged(self):
        att = self.short_day()
        self.assertEqual(replan(self.view(att), INPUTS), replan(self.view(att), INPUTS, fresh=False))


if __name__ == "__main__":
    unittest.main()


import html as _html

from webapp.tests import test_cancel_break as _cb
from webapp.tests.test_notify_daybook import WED as _WED
from webapp.tests.test_runs import token as _token


class TheReplanButton(_cb._Cancel):
    def url(self, **more):
        q = "&".join(f"{k}={v}" for k, v in {"program": self.key.replace(" ", "+"), "date": _WED.isoformat(), **more}.items())
        return "/day?" + q

    def text(self, **more):
        return _html.unescape(self.client.get(self.url(**more)).get_data(as_text=True))

    def test_the_day_offers_the_button_next_to_the_other_break_tools(self):
        page = self.text()
        self.assertIn("Replan the day's breaks", page)
        self.assertIn("how=fresh", page)
        self.assertIn("Fix the rest of the day's breaks", page)  # the other tool stays

    def test_the_proposal_says_what_it_does_and_asks_before_keeping_anything(self):
        page = self.text(view="replan", how="fresh")
        self.assertIn("<h2 id=\"rp-h\">Replan the day's breaks</h2>", page)
        self.assertIn("every break that has not started", page)
        self.assertIn("Breaks to move", page)
        self.assertNotIn("Fix the rest of the day's breaks</h2>", page)

    def test_the_old_tool_keeps_its_own_words(self):
        page = self.text(view="replan")
        self.assertIn("<h2 id=\"rp-h\">Fix the rest of the day's breaks</h2>", page)

    def test_applying_a_fresh_proposal_keeps_the_moves_asked_for_and_names_the_change(self):
        name, idx, kind, start, _ = self.with_breaks()
        self.addCleanup(self.days.undo_last, self.key, _WED, self.omar)
        got = self.client.post("/day/replan/apply", data={
            "csrf_token": _token(self.client), "program": self.key, "date": _WED.isoformat(), "how": "fresh",
            "move": f"{name}|{idx}|{start + 5}|{_WED.isoformat()}", "start": "0", "tz": "Africa/Cairo",
            "anchor": _WED.isoformat()}, follow_redirects=True)
        self.assertIn("Moved 1 break.", _html.unescape(got.get_data(as_text=True)))
        self.assertIn("Replan breaks moved 1 break", _html.unescape(self.text()))
