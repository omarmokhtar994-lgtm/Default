# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC (owner, 2026-10-26: "I think it considers a break as a separator, that's why it kept associates the whole day on the same channel"):
score_day tells a change of channel at a break from one in the middle of a stretch, and with the Balanced tick a change at a break is priced
below one in the middle of a stretch. Rule and acceptance: evidence/phase_bc/REQUESTS.md."""
import unittest
from unittest import mock

from webapp.channel_plan import plan_day, score_day
from webapp.tests.test_channel_plan import RULES, WED, day_people, setup


def person():
    return {"name": "Associate 001", "language": "English", "start": 480, "end": 1020, "skills": "PCE", "counts_for": {"english"},
            "breaks": [("Break 1", 600, 15), ("Lunch", 750, 30)]}


class TheSplit(unittest.TestCase):
    def test_a_change_at_a_break_and_one_in_the_middle_are_told_apart(self):
        people = [person()]
        plan = {"breaks": {"Associate 001": [600, 750]},
                "blocks": {"Associate 001": [(480, 600, "P"), (615, 750, "C"),   # P to C across Break 1
                                             (780, 900, "C"), (900, 1020, "E")]}}  # C to E in the middle of a stretch
        got = score_day(people, plan, setup(), WED, RULES)
        self.assertEqual((got["moves_at_breaks"], got["moves_mid"]), (1, 1))
        self.assertEqual(got["moves"], 2)  # the old total still counts both

    def test_no_change_no_count(self):
        people = [person()]
        plan = {"breaks": {"Associate 001": [600, 750]}, "blocks": {"Associate 001": [(480, 600, "P"), (615, 750, "P"), (780, 1020, "P")]}}
        got = score_day(people, plan, setup(), WED, RULES)
        self.assertEqual((got["moves_at_breaks"], got["moves_mid"]), (0, 0))


class ThePricing(unittest.TestCase):
    """The price of a change at a break is its own constant, BREAK_CHANGE (evidence/phase_bc/REQUESTS.md: 0.66 against 1.44 changes per person-day in
    the middle of a stretch on base_16, the moves going to breaks). Pinned on one person whose day needs Phone before lunch and Chat after it: with
    a change in the middle of a stretch made dear, the change is made at the lunch when the lunch is free to change at, and not at all when it is
    not (the coverage is then given up)."""

    def one_day(self, price, balanced=True, consistent=False):
        need = lambda f: {d: {t: f(t) for t in range(0, 1440, 30)} for d in range(7)}  # noqa: E731
        config = setup(need={"P": need(lambda t: 1 if 480 <= t < 720 else 0), "C": need(lambda t: 1 if 750 <= t < 1020 else 0)},
                       languages=[], email_hours={d: {"hours": 0.0, "languages": {}, "start": 480, "end": 1320} for d in range(7)})
        config["rules"] = dict(config["rules"], fair=False, balanced=balanced, consistent=consistent, max_run={"P": 0, "C": 0, "E": 0})
        people = [dict(person(), breaks=[("Lunch", 720, 30)])]
        with mock.patch("webapp.channel_plan.BREAK_CHANGE", price), mock.patch("webapp.channel_plan.CONSISTENT", 1000):
            plan = plan_day(people, config, {**RULES, "segments": [[30, "Lunch"]]}, WED, move_breaks=False)
        return score_day(people, plan, config, WED, {**RULES, "segments": [[30, "Lunch"]]})

    def test_a_change_at_a_break_costs_its_own_price(self):
        free = self.one_day(0)
        self.assertEqual((free["moves_at_breaks"], free["moves_mid"]), (1, 0))  # Phone, lunch, Chat

    def test_priced_like_the_middle_of_a_stretch_the_person_stays_put(self):
        dear = self.one_day(1000)
        self.assertEqual((dear["moves_at_breaks"], dear["moves_mid"]), (0, 0))  # coverage given up rather than a dear change

    def test_the_shipped_price_is_the_measured_one(self):
        from webapp import channel_plan
        self.assertEqual(channel_plan.BREAK_CHANGE, 0)

    def test_fixed_prices_a_break_like_the_middle_of_a_stretch(self):
        got = self.one_day(0, balanced=False, consistent=True)  # BREAK_CHANGE is for the balanced tick only
        self.assertEqual((got["moves_at_breaks"], got["moves_mid"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
