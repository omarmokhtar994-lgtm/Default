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
        self.assertEqual(a["moves"], b["moves"])


def penalty_for(name, idx, at):
    return penalty(at)


if __name__ == "__main__":
    unittest.main()
