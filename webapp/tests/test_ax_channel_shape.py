# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: "make sure we prefer more the usual shape, followed by the engine layer"): when Plan channels
moves breaks, it prefers the usual shape (the first break 2 to 3.5 hours into the shift, lunch 2 to 3 hours of work after
the first break, the last break ending an hour before the shift does) over leaving a break where it was; the engine's
break rules stay limits, and a channel's need still comes first."""
import unittest

from webapp.break_plan import check_row, hm
from webapp.channel_plan import plan_day
from webapp.tests.test_af_planner_rules import H, person, quiet_phone
from webapp.tests.test_channel_plan import RULES, WED, grid, setup

LO, HI = 10 * H, 19 * H  # a 09:00 shift from 10:00


def planned(rules=RULES, breaks=(10.75, 12, 15), needs=None, move=True):
    one = person("Associate 01", 10, breaks)
    return plan_day([one], needs or quiet_phone(), rules, WED, move_breaks=move)["breaks"]["Associate 01"]


def label():
    return f"{hm(LO)} - {hm(HI)}"


class ThePreferredShape(unittest.TestCase):
    def test_breaks_that_are_out_of_shape_move_into_it_when_nothing_needs_them_where_they_are(self):
        first, lunch, last = planned()
        self.assertTrue(LO + 120 <= first <= LO + 210, hm(first))  # 2 to 3.5 hours in
        self.assertTrue(120 <= lunch - (first + 15) <= 180, (hm(first), hm(lunch)))  # 2 to 3 hours of work later
        self.assertLessEqual(last + 15, HI - 60)  # the last one ends an hour before the shift does

    def test_breaks_already_in_shape_stay_where_they_are(self):
        start = (12.5, 15, 17.25)  # 150 minutes in; 135 minutes of work to lunch; the last ends 90 minutes before the end
        self.assertEqual([s / H for s in planned(breaks=start)], list(start))

    def test_the_engines_rules_still_hold_for_what_it_moves(self):
        starts = planned()
        self.assertEqual(check_row(RULES, label(), starts)[0], "ok", check_row(RULES, label(), starts))

    def test_a_window_in_the_engines_rules_wins_over_the_shape(self):
        rules = {**RULES, "windows": {**RULES["windows"], "break 1": {"earliest": None, "latest": 100}}}
        first = planned(rules)[0]
        self.assertLessEqual(first - LO, 100, hm(first))  # the shape wants 120 or later: the rule says no

    def test_a_window_inside_the_shape_is_followed_too(self):
        rules = {**RULES, "windows": {**RULES["windows"], "break 1": {"earliest": 160, "latest": None}}}
        first = planned(rules)[0]
        self.assertTrue(LO + 160 <= first <= LO + 210, hm(first))

    def test_a_channels_need_comes_before_the_shape(self):
        # Phone needs one person from 12:00 to 14:00 and this is the only one: the shape's first-break time (12:00 to
        # 13:30) would leave Phone short, so the break goes where it does not
        needs = setup(need={"P": grid(lambda t: 1 if 720 <= t < 840 else 0)}, email_mode="none", languages=[],
                      email_hours={d: {"hours": 0.0, "languages": {}, "start": 0, "end": 1440} for d in range(7)})
        needs["rules"] = {**needs["rules"], "max_run": {"P": 0, "C": 0, "E": 0}}
        first = planned(needs=needs)[0]
        self.assertFalse(first < 840 and first + 15 > 720, hm(first))

    def test_nothing_moves_when_breaks_may_not_move(self):
        self.assertEqual([s / H for s in planned(move=False)], [10.75, 12, 15])


if __name__ == "__main__":
    unittest.main()
