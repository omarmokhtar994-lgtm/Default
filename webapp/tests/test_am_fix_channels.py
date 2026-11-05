# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AM item 1 (owner, 2026-10-16: "schedule rescheduling in RTA view should be a button such as fix breaks etc 1
click fix things" ... "First point was related to channel for the button"; answers: the channel planner re-plans
everyone's channels from now on, channels only, coverage first then fairness, changes shown first, one Apply, one
Undo)."""
import re
import unittest

from webapp.channel_plan import plan_day
from webapp.tests.test_channel_plan import NO_BREAKS, setup


def flat(values):
    """need per 15 minutes on every day from {start minute: people} (0 elsewhere)."""
    return {d: {t: values.get(t, 0) for t in range(0, 1440, 15)} for d in range(7)}


class TheCarryIn(unittest.TestCase):
    """The planner told what each person is on just before its first slot: carrying on is a continuation."""

    def people(self):
        return [{"name": "Associate 001", "language": "English", "start": 600, "end": 690, "breaks": [],
                 "skills": "PC", "counts_for": {"english"}}]

    def config(self):
        return setup(step=15, need={"P": flat({600: 1}), "C": flat({t: 1 for t in range(615, 690, 15)})},
                     email_mode="none", languages=[],
                     rules={"min_block": 60, "max_run": {"P": 0, "C": 0, "E": 0}, "order": ["P", "C", "E"],
                            "strict": True, "fair": False})

    def test_a_short_stint_that_carries_on_stands(self):
        got = plan_day(self.people(), self.config(), NO_BREAKS, 3, move_breaks=False, carry_in={"Associate 001": "P"})
        self.assertEqual(got["blocks"]["Associate 001"], [(600, 615, "P"), (615, 690, "C")])

    def test_with_nothing_short_nobody_moves(self):
        people = self.people()
        keep = {("Associate 001", t): "C" for t in range(600, 690, 15)}
        config = setup(step=15, need={"P": flat({}), "C": flat({t: 1 for t in range(600, 690, 15)})},
                       email_mode="none", languages=[],
                       rules={"min_block": 60, "max_run": {"P": 0, "C": 0, "E": 0}, "order": ["P", "C", "E"],
                              "strict": True, "fair": True})
        got = plan_day(people, config, NO_BREAKS, 3, carry={"Associate 001": {"C": 2400}}, move_breaks=False,
                       carry_in={"Associate 001": "C"}, keep=keep)
        self.assertEqual(got["blocks"]["Associate 001"], [(600, 690, "C")])  # fairness alone never moves anyone

    def test_without_it_the_minimum_stretch_holds(self):
        got = plan_day(self.people(), self.config(), NO_BREAKS, 3, move_breaks=False)
        self.assertNotIn((600, 615, "P"), got["blocks"]["Associate 001"])


if __name__ == "__main__":
    unittest.main()


from datetime import date  # noqa: E402

from webapp.tests import test_ai_fixes as ai  # noqa: E402

WED = date(2026, 10, 14)


class TheFix(ai.TheChannelsOnTheTimeline):
    """The channel fixture's Wednesday: Associate 001 on Chat, 031 on Phone, 013 (all channels) on Email, the rest
    Email only. With 031 off sick, Phone is short; the fix moves someone who can take it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.days = cls.app.extensions["days"]
        cls.user = cls.store.list_users()[0]["id"]

    def setUp(self):
        with self.store._db() as db:  # each test from the schedule as planned
            for table in ("attendance", "channel_moves", "day_actions", "day_log"):
                db.execute(f"delete from {table}")
        self.days.set_status(self.key, WED, "Associate 031", "Sick", self.user)

    def test_the_plan_cuts_the_phone_shortfall_from_now_on(self):
        plan = self.days.channel_fix_plan(self.key, WED, now=600)
        self.assertGreater(plan["short_before"]["P"], 0)
        self.assertLess(plan["short_after"]["P"], plan["short_before"]["P"])
        self.assertTrue(plan["changes"])
        for name, lo, hi, letter, was in plan["changes"]:
            self.assertGreaterEqual(lo, 600)
            self.assertNotEqual(name, "Associate 031")  # off sick: never given a channel
            self.assertIn(letter, "PCE")

    def test_apply_is_one_step_and_undo_takes_it_all_back(self):
        plan = self.days.channel_fix_plan(self.key, WED, now=600)
        done = self.days.apply_channel_fix(self.key, WED, [c[:4] for c in plan["changes"]], self.user, now=600)
        self.assertEqual(done, len(plan["changes"]))
        self.assertEqual(len(self.store.list_channel_moves(self.key, [WED.isoformat()])), done)
        fixed = self.days.page(self.key, WED)["view"]["channels"]["runs"]
        name, lo, _, letter, _ = plan["changes"][0]
        self.assertTrue(any(a <= lo < b and c == letter for a, b, c in fixed[name]))
        self.assertIn("Fix channels", self.days.undoable(self.key, WED, self.user)["label"])
        self.days.undo_last(self.key, WED, self.user)
        self.assertEqual(self.store.list_channel_moves(self.key, [WED.isoformat()]), [])

    def test_a_change_that_has_passed_is_refused(self):
        plan = self.days.channel_fix_plan(self.key, WED, now=600)
        with self.assertRaisesRegex(ValueError, "has passed: open Fix channels again"):
            self.days.apply_channel_fix(self.key, WED, [c[:4] for c in plan["changes"]], self.user,
                                        now=plan["changes"][0][1])

    def test_nothing_gets_worse(self):
        # with 031 back the plan is still a quarter hour short on Phone (031's break at 14:00), and it has 013,
        # who works every channel, on Email outside the day's Email hours, which the planner never plans; the fix
        # covers Phone and leaves nothing worse
        self.days.set_status(self.key, WED, "Associate 031", "Present", self.user)
        plan = self.days.channel_fix_plan(self.key, WED, now=600)
        self.assertEqual(plan["short_before"]["P"], 0.25)
        for key, hours in plan["short_after"].items():
            self.assertLessEqual(hours, plan["short_before"][key], key)
        self.assertEqual(plan["short_after"]["P"], 0)


import html  # noqa: E402
from unittest import mock  # noqa: E402

from webapp.permissions import ENDPOINTS  # noqa: E402
from webapp.tests.test_af_outlook import _Clock  # noqa: E402  (Wednesday 14 October 2026, 10:00 Egypt time)
from webapp.tests.test_runs import token  # noqa: E402


class ThePage(TheFix):
    def url(self, **more):
        return "/day?" + "&".join(f"{k}={v}" for k, v in {"program": self.key.replace(" ", "+"), "date": "2026-10-14",
                                                         "view": "channels", **more}.items())

    def test_the_button_then_the_changes_then_apply(self):
        with mock.patch("webapp.app.datetime", _Clock):
            body = html.unescape(self.client.get(self.url()).get_data(as_text=True))
            self.assertIn(">Fix channels</button>", body)
            preview = html.unescape(self.client.get(self.url(fix=1)).get_data(as_text=True))
            plan = self.days.channel_fix_plan(self.key, WED, now=600)
            name, lo, hi, letter, was = plan["changes"][0]
            self.assertRegex(preview, rf"{name}: \w+ {lo // 60:02d}:{lo % 60:02d} to")
            self.assertIn(f"Apply all {len(plan['changes'])}", preview)
            self.assertIn("Phone short", preview)
            items = re.findall(r'name="change" value="([^"]+)"', preview)
            self.assertEqual(len(items), len(plan["changes"]))
            got = self.client.post("/day/channels/fix", data={"csrf_token": token(self.client), "program": self.key,
                                                               "date": "2026-10-14", "change": items})
            self.assertEqual(got.status_code, 303)
        self.assertEqual(len(self.store.list_channel_moves(self.key, [WED.isoformat()])), len(items))

    def test_it_is_an_rta_change(self):
        self.assertEqual(ENDPOINTS.get("day_channel_fix"), "rta_change")
