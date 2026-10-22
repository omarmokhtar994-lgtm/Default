# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: Rescue and Fix the rest "consider the default but still prioritize the intervals"): in Rescue
the default (the usual shape, then the engine's rules) comes after the intervals at the target, the intervals with 10
minutes to spare and the fewest given up, and before the fewest breaks moved. The small days of test_rescue."""
import unittest

from webapp import rescue
from webapp.day import day_view
from webapp.tests import test_rescue as _tr


def penalty(at):  # a stand-in default: a break that starts on the hour is 30 minutes off it
    return (30 if at % 60 == 0 else 0, 0)


class TheDefaultInRescue(unittest.TestCase):
    def solve(self, may, defaults=None):
        wk, inp = _tr.week(_tr.LUNCHES), _tr.inputs()
        view = day_view(wk, inp, _tr.D, {}, {})
        return view, rescue.solve(view, inp, 0.9, 0, may, seconds=20.0, defaults=defaults)

    def total(self, view, found):
        moved = {(m["name"], m["idx"]): m["to"] for m in found["moves"]}
        return sum(penalty(moved.get((l["name"], b["idx"]), b["start"]))[0]
                   for l in view["lanes"] for s in l["segments"] if s["offset"] == 0 for b in s["breaks"])

    def test_the_intervals_rescued_do_not_change(self):
        for may in (1, 2):
            _, plain = self.solve(may)
            _, with_default = self.solve(may, penalty_for)
            self.assertEqual((with_default["after_at"], with_default["after_safe"], len(with_default["given_up"])),
                             (plain["after_at"], plain["after_safe"], len(plain["given_up"])), may)

    def test_among_answers_that_rescue_the_same_it_takes_the_better_fit(self):
        view, plain = self.solve(2)
        _, with_default = self.solve(2, penalty_for)
        self.assertLessEqual(self.total(view, with_default), self.total(view, plain))

    def test_without_a_default_the_answer_is_the_one_it_always_gave(self):
        _, a = self.solve(2)
        _, b = self.solve(2, None)
        key = lambda f: (f["status"], f["after_at"], f["after_safe"], len(f["given_up"]), len(f["moves"]))  # noqa: E731
        self.assertEqual(key(a), key(b))  # equally good answers can differ in who moves (four workers): what they win cannot


def penalty_for(name, idx, at):
    return penalty(at)


if __name__ == "__main__":
    unittest.main()


class TheNormalMaximumGapIsANormal(unittest.TestCase):
    """The workbook says "Break Normal Maximum Gap Minutes: two breaks are normally no further apart than this" and "Break
    Absolute Minimum Gap Minutes: never closer": the minimum is absolute, the maximum is a normal, and the engine's own
    breaks deviate from it. With a default given, Rescue may pass the maximum by as little as it takes."""
    PEOPLE = [("Associate 001", "ENG", "11:00 - 15:00", [("Break 1", "11:15", 15), ("Lunch", "12:45", 60)]),
              ("Associate 002", "ENG", "11:00 - 15:00", [("Break 1", "11:30", 15), ("Lunch", "13:00", 60)]),
              ("Associate 003", "ENG", "11:00 - 15:00", [("Break 1", "11:45", 15), ("Lunch", "13:15", 60)]),
              ("Associate 004", "ENG", "11:00 - 15:00", [("Break 1", "12:00", 15), ("Lunch", "13:30", 60)])]

    def run_with(self, gap_max, defaults):
        wk, inp = _tr.week(self.PEOPLE), {**_tr.inputs(), "gap_min": 0, "gap_max": gap_max}
        view = day_view(wk, inp, _tr.D, {}, {})
        return rescue.solve(view, inp, 0.9, 0, 3, seconds=20.0, defaults=defaults)

    def test_with_a_default_it_is_never_worse_than_when_the_maximum_is_absolute(self):
        for gap_max in (30, 60, 120):
            hard = self.run_with(gap_max, None)
            soft = self.run_with(gap_max, lambda name, idx, at: (0, 0))
            self.assertGreaterEqual((soft["after_at"], soft["after_safe"]), (hard["after_at"], hard["after_safe"]), gap_max)



if __name__ == "__main__":
    unittest.main()
