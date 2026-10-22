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

    def test_the_times_the_default_rules_give_win_over_the_best_score(self):
        v = self.view()
        everyone = {(lane["name"], b["idx"]): b["start"] for lane in v["lanes"] for seg in lane["segments"]
                    if seg["offset"] == 0 for b in seg["breaks"]}
        plan = replan(v, INPUTS, 0, fresh=True, desired=everyone)
        # where every break already is, is what was asked for: only a break whose own time breaks the program's gap moves
        for m in plan["moves"]:
            seg = self.own(v, m["name"])
            before = [b for b in seg["breaks"] if b["idx"] < m["idx"]]
            gap = m["from"] - (before[-1]["start"] + before[-1]["minutes"]) if before else 0
            self.assertGreater(gap, INPUTS["gap_max"], m)
        self.assertLess(len(plan["moves"]), len(everyone) // 4)

    def test_a_desired_time_that_cannot_be_kept_gives_the_nearest_allowed_one(self):
        v = self.view()
        name, idx = next((lane["name"], b["idx"]) for lane in v["lanes"] for seg in lane["segments"]
                         if seg["offset"] == 0 and seg["breaks"] for b in seg["breaks"][:1])
        plan = replan(v, INPUTS, 0, fresh=True, desired={(name, idx): 0})  # before the shift: not allowed
        seg = self.own(self.applied({}, plan)[0], name)
        self.assertTrue(seg["start"] <= min(b["start"] for b in seg["breaks"]))

    def test_the_other_mode_is_unchanged(self):
        att = self.short_day()
        self.assertEqual(replan(self.view(att), INPUTS), replan(self.view(att), INPUTS, fresh=False))


if __name__ == "__main__":
    unittest.main()


import html as _html
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

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


def clock(year, month, day, hour, minute=0):
    """A stopped clock, in Cairo time, for ``webapp.app.datetime``."""
    class Stopped(datetime):
        @classmethod
        def now(cls, tz=None):
            at = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("Africa/Cairo"))
            return at.astimezone(tz) if tz else at.replace(tzinfo=None)
    return Stopped


class TheReplanIsForWhatIsStillToCome(TheReplanButton):
    """Owner, 2026-10-22: it applies to the day picked, from the "Day starts at" picked, and only for the future: a day that
    has passed has nothing to replan, today is replanned from now, a day to come is replanned whole."""
    def page_at(self, now, **more):
        with mock.patch("webapp.app.datetime", now):
            return self.text(view="replan", how="fresh", **more)

    def test_a_day_that_has_passed_has_nothing_to_replan(self):
        page = self.page_at(clock(2026, 10, 16, 8))
        self.assertIn("has passed", page)
        self.assertNotIn('name="move"', page)

    def test_today_is_replanned_from_now(self):
        page = self.page_at(clock(2026, 10, 14, 12))
        self.assertIn("after 12:00", page)
        self.assertNotIn("has passed", page)

    def test_a_day_to_come_is_replanned_whole(self):
        page = self.page_at(clock(2026, 10, 12, 12))
        self.assertNotIn("has passed", page)
        self.assertNotIn("(after ", page)

    def test_it_follows_the_day_starts_at_that_was_picked(self):
        self.text(start="13:00")  # picking it on the day page keeps it for the program
        page = self.page_at(clock(2026, 10, 12, 12))
        self.assertIn("The 24 hours from 13:00", page)
        self.text(start="00:00")


from webapp import break_plan as _bp  # noqa: E402
from webapp.attendance import day_index as _day_index  # noqa: E402
from webapp.day import read_inputs as _read_inputs  # noqa: E402


class TheDefaultRules(_cb._Cancel):
    """Owner, 2026-10-22: "it is not rescheduling based on the default": the replan places the breaks as the program's
    default break rules do (the planner behind Plan breaks > Suggest), then keeps whatever the day's own rules refuse
    out of it."""
    def rules_and_week(self):
        row, _ = self.days.version(self.key, _WED)
        return row, self.days._week(row), self.days.book.break_rules(row["id"])

    def test_every_move_is_the_time_the_default_rules_give(self):
        row, week, rules = self.rules_and_week()
        inputs = _read_inputs(self.days.book.input_path(row["run_id"]))
        d = _day_index(_WED)
        # a few people's breaks are moved away from the plan by hand: the replan puts them back where the rules put them
        shifted = []
        for lane in self.days.page(self.key, _WED)["view"]["lanes"][:6]:
            for seg in lane["segments"]:
                if seg["offset"] == 0 and seg["status"] == "Present" and seg["breaks"]:
                    b = seg["breaks"][-1]
                    for step in (30, -30, 20, -20, 10, -10):
                        try:
                            self.days.move_break(self.key, _WED, lane["name"], b["idx"],
                                                 f"{(b['start'] + step) // 60 % 24:02d}:{(b['start'] + step) % 60:02d}", self.omar)
                            shifted.append((lane["name"], b["idx"]))
                            self.addCleanup(self.days.move_break, self.key, _WED, lane["name"], b["idx"], None, self.omar)
                            break
                        except ValueError:
                            continue
        self.assertTrue(shifted)
        found = self.days.fresh_replan_window(self.key, _WED, 0, 0)
        # the rules' own plan with every break empty: what Plan breaks > Suggest gives
        empty = {a["name"]: [None] * len(_bp.slots_for(rules, _bp.shift_span(a["days"][d])[1] - _bp.shift_span(a["days"][d])[0]))
                 for a in week["associates"] if _bp.shift_span(a["days"][d])}
        want = _bp.suggest(week, inputs, rules, d, empty)
        self.assertTrue(found["moves"], "breaks moved away from the plan are put back")
        for m in found["moves"]:
            self.assertEqual(m["to"], want[m["name"]][m["idx"]], m)
        self.assertTrue({(m["name"], m["idx"]) for m in found["moves"]} >= set(shifted[:1]))

    def test_a_break_that_has_started_is_not_in_it(self):
        found = self.days.fresh_replan_window(self.key, _WED, 0, 18 * 60)
        self.assertTrue(all(m["from"] >= 18 * 60 and m["to"] >= 18 * 60 for m in found["moves"]))

    def test_when_the_rules_cannot_be_read_it_says_so_and_still_replans(self):
        with mock.patch.object(self.days.book, "break_rules", side_effect=ValueError("no rules")):
            found = self.days.fresh_replan_window(self.key, _WED, 0, 0)
        self.assertIn("could not be read", found["note"])
        self.assertIn("moves", found)

    def test_the_page_names_the_rules_it_followed(self):
        with mock.patch("webapp.app.datetime", clock(2026, 10, 10, 12)):
            page = _html.unescape(self.client.get(
                f"/day?program={self.key.replace(' ', '+')}&date={_WED.isoformat()}&view=replan&how=fresh").get_data(as_text=True))
        self.assertIn("default break rules", page)


from webapp.tests import test_channel_day as _cd  # noqa: E402


class TheFreshReplanWithChannels(_cd._Day):
    """The default times come from a planner that does not know about channels, so the day's channel guard has the last
    word: no move leaves a channel, or a language inside it, below its need."""
    def test_no_move_it_proposes_leaves_a_channel_short(self):
        before = {w["text"] for w in self.view()["channels"]["warnings"]}
        found = self.days.fresh_replan_window(self.key, _cd.WED, 0, 0)
        for m in found["moves"]:
            at = f"{m['to'] // 60 % 24:02d}:{m['to'] % 60:02d}"
            self.days.move_break(self.key, _cd.WED, m["name"], m["idx"], at, self.omar)
        self.assertEqual({w["text"] for w in self.warnings()} - before, set())

    def test_a_default_time_that_would_leave_a_channel_empty_is_not_used(self):
        # Associate 031 is the only one on Phone from 15:00 to 16:00 (test_channel_day: "nobody on Phone"), so a default
        # of 15:00 for their break must give way to the nearest time the channel allows
        page = self.days.page(self.key, _cd.WED)
        found = replan(page["view"], page["inputs"], 0, target=page["target"]["target"], fresh=True,
                       desired={("Associate 031", 0): 15 * 60})
        moved = [m for m in found["moves"] if m["name"] == "Associate 031"]
        self.assertTrue(moved)
        self.assertNotEqual(moved[0]["to"], 15 * 60)
        self.assertNotIn(moved[0]["to"] // 60, (15,))
