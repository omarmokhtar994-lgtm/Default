# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AH (owner, 2026-10-15): "if target is 90% and I'm now 91% but have only 2-3 mins that's very tight at least
10 mins is sufficient to cover that probably that's my ask when rescue works and fix the breaks as well". The count of
intervals at the target is unchanged ("at target, marked tight"); Rescue the day and Fix breaks aim for intervals with
10 person-minutes or more over the target.

A made-up day where the answer is known by counting: four people on 11:00 to 13:00, four needed each hour, target 90%
(216 person-minutes an hour). Two 10-minute breaks both at 11:00 leave 11:00 to 12:00 at the target by only 4 minutes
(220); one of them moved past 12:00 leaves both hours 14 minutes over. Every result is recounted with ``day_view``."""
import unittest

from webapp import rescue
from webapp.day import at_target, day_view, replan
from webapp.tests.test_rescue import D, week

NEED = {660: 4.0, 720: 4.0}
TEN = [("Associate 001", "ENG", "11:00 - 13:00", [("Break 1", "11:00", 10)]),
       ("Associate 002", "ENG", "11:00 - 13:00", [("Break 1", "11:10", 10)]),
       ("Associate 003", "ENG", "11:00 - 13:00", []),
       ("Associate 004", "ENG", "11:00 - 13:00", [])]


def inputs():
    return {"interval": 60, "required": {D: dict(NEED)}, "languages": [], "previous_saturday": [],
            "gap_min": None, "gap_max": None}


class RescueKeepsTenMinutes(unittest.TestCase):
    def test_a_tight_hour_gets_its_ten_minutes(self):
        wk, inp = week(TEN), inputs()
        view = day_view(wk, inp, D, {}, {})
        before = at_target(view["cells"], 0.9)
        self.assertEqual((before["now"], before["tight"], before["safe"]), (2, 1, 1))
        found = rescue.solve(view, inp, 0.9, None, 0, seconds=20.0)
        self.assertEqual(found["status"], "rescued")
        after = at_target(day_view(wk, inp, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in found["moves"]})["cells"],
                          0.9)
        self.assertEqual((after["now"], after["tight"], after["safe"]), (2, 0, 2))
        self.assertEqual(found["given_up"], [])
        self.assertEqual(len(found["moves"]), 1)  # the fewest moves that do it

    def test_never_trades_an_interval_at_the_target_for_ten_minutes(self):
        # 45 minutes of breaks over the two hours: both at the target is possible, both with 10 minutes is not; one
        # with 10 minutes would push the other below the target, so the answer keeps both at the target
        people = [("Associate 001", "ENG", "11:00 - 13:00", [("Break 1", "11:00", 15)]),
                  ("Associate 002", "ENG", "11:00 - 13:00", [("Break 1", "11:15", 15)]),
                  ("Associate 003", "ENG", "11:00 - 13:00", [("Break 1", "12:00", 15)]),
                  ("Associate 004", "ENG", "11:00 - 13:00", [])]
        wk, inp = week(people), inputs()
        found = rescue.solve(day_view(wk, inp, D, {}, {}), inp, 0.9, None, 1, seconds=20.0)
        after = at_target(day_view(wk, inp, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in found["moves"]})["cells"],
                          0.9)
        self.assertEqual(after["now"], 2)


# Fix breaks lifts the weakest interval first. Here the weakest is 10:00 to 11:00 (two people of four, nobody's break
# can help it); moving a break from 11:00 to 12:00 changes neither the weakest nor the hours short, so Fix breaks
# made no move before Phase AH, leaving 11:00 at the target by 4 minutes.
EARLY = TEN + [("Associate 005", "ENG", "10:00 - 11:00", []), ("Associate 006", "ENG", "10:00 - 11:00", [])]


def early_inputs():
    inp = inputs()
    inp["required"][D][600] = 4.0
    return inp


class FixBreaksKeepsTenMinutes(unittest.TestCase):
    def test_same_tightest_more_with_ten_minutes(self):
        wk, inp = week(EARLY), early_inputs()
        view = day_view(wk, inp, D, {}, {})
        found = replan(view, inp, 0, target=0.9)
        after = at_target(day_view(wk, inp, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in found["moves"]})["cells"],
                          0.9)
        self.assertEqual((after["now"], after["safe"]), (2, 2))
        self.assertEqual((found["before"]["safe"], found["after"]["safe"]), (1, 2))
        self.assertEqual(found["after"]["tightest"], found["before"]["tightest"])  # its aim is kept
        self.assertEqual(found["after"]["short_hours"], found["before"]["short_hours"])

    def test_without_a_target_fix_breaks_is_as_before(self):
        wk, inp = week(EARLY), early_inputs()
        found = replan(day_view(wk, inp, D, {}, {}), inp, 0)
        self.assertEqual(found["moves"], [])
        self.assertNotIn("safe", found["after"])


if __name__ == "__main__":
    unittest.main()
