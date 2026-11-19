# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BO (owner, 2026-11-12: "count of intervals at target and worst intervals, try to balance both"): the exact break solver can also lift the
worst interval. The count of intervals at the target still comes first; among plans with the same count the worst interval's share of demand (up to
the target) is lifted as far as it goes. Nothing is given up, so no interval under the target falls below where it is.

The made-up day: four people 11:00 to 15:00, each with an hour's lunch; four needed at 11:00 and 12:00, 3.8 at 13:00 and 14:00. Two lunch at 11:00 and
two at 12:00, so those hours stand at 50% and the afternoon is covered: two of four hours are at 90%. No plan gets a third hour to 90% with nothing given
up: the lunches are 240 person-minutes, one morning hour may keep its 120, the other spares about 20 at 90% and each afternoon hour about 30, which is
200. But half an hour of lunch can go into each afternoon hour, which lifts both morning hours from 50% to above 60%. Every result is recounted with the
page's own ``day_view``."""
import unittest

from webapp import rescue
from webapp.day import at_target, day_view
from webapp.tests.test_rescue import D, week

NEED = {660: 4.0, 720: 4.0, 780: 3.8, 840: 3.8}
PEOPLE = [("Associate 001", "ENG", "11:00 - 15:00", [("Lunch", "11:00", 60)]),
          ("Associate 002", "ENG", "11:00 - 15:00", [("Lunch", "11:00", 60)]),
          ("Associate 003", "ENG", "11:00 - 15:00", [("Lunch", "12:00", 60)]),
          ("Associate 004", "ENG", "11:00 - 15:00", [("Lunch", "12:00", 60)])]
INPUTS = {"interval": 60, "required": {D: dict(NEED)}, "languages": [], "previous_saturday": [], "gap_min": None, "gap_max": None}


def counted(moves):
    view = day_view(week(PEOPLE), INPUTS, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in moves})
    shares = [c["now"] / c["required"] for c in view["cells"] if c["required"] > 0]
    return at_target(view["cells"], 0.9)["now"], round(min(shares), 2)


class TheWorstIntervalIsLifted(unittest.TestCase):
    def setUp(self):
        self.view = day_view(week(PEOPLE), INPUTS, D, {}, {})

    def test_the_day_as_it_stands(self):
        self.assertEqual(counted([]), (2, 0.5))

    def test_without_the_option_nothing_is_proposed(self):
        out = rescue.solve(self.view, INPUTS, 0.9, None, 0)
        self.assertEqual((out["status"], out["moves"]), ("no gain", []))

    def test_with_it_the_worst_hours_are_lifted_and_the_count_stays(self):
        out = rescue.solve(self.view, INPUTS, 0.9, None, 0, lift_worst=True)
        self.assertEqual(out["solver"], "OPTIMAL")
        count, worst = counted(out["moves"])
        self.assertEqual(count, 2)
        self.assertGreaterEqual(worst, 0.6)
        self.assertEqual(out["before_worst"], 500)
        self.assertGreaterEqual(out["after_worst"], 600)

    def test_the_count_still_comes_first(self):
        # three needed all day: moving the lunches so that each hour has one puts every hour at its three, and that beats any lift of the worst
        inputs = dict(INPUTS, required={D: {t: 3.0 for t in NEED}})
        view = day_view(week(PEOPLE), inputs, D, {}, {})
        out = rescue.solve(view, inputs, 0.9, None, 0, lift_worst=True)
        after = day_view(week(PEOPLE), inputs, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in out["moves"]})
        self.assertEqual(at_target(after["cells"], 0.9)["now"], 4)


if __name__ == "__main__":
    unittest.main()


from webapp.day import replan as greedy_replan  # noqa: E402
from webapp.tests.test_notify_daybook import WED, _Tagged  # noqa: E402


class FixRestOfTheDayUsesIt(_Tagged):
    """Fix rest of the day asks the exact solver first (nothing given up, the worst interval lifted) and keeps the greedy answer when the exact one
    proposes nothing or the page's own count does not confirm it. Measured in evidence/phase_bo/FIX_EXACT_AB.md."""

    def count_after(self, page, moves):
        after = self.days._recount(self.key, WED, 0, [(m["name"], m["idx"], m["to"], WED) for m in moves])
        return after["target"]["now"]

    def test_the_proposal_says_which_search_made_it_and_is_never_behind_the_greedy_one(self):
        page = self.days.page(self.key, WED)
        found = self.days.replan(page)
        self.assertIn(found["by"], ("exact", "greedy"))
        greedy = greedy_replan(page["view"], page["inputs"], 0, target=page["target"]["target"])
        self.assertGreaterEqual(self.count_after(page, found["moves"]), self.count_after(page, greedy["moves"]))
        self.assertEqual(set(found["before"]), set(greedy["before"]))  # the same figures the page already shows
        self.assertEqual(set(found["after"]), set(greedy["after"]))

    def test_the_window_tool_says_it_too(self):
        found = self.days.replan_window(self.key, WED, 0)
        self.assertIn(found["by"], ("exact", "greedy"))
