# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU (owner, 2026-10-21): Suggest builds breaks in the usual shape: the first 2 to 3.5 h after the shift starts,
lunch 2 to 3 h of work after the first break, the last after lunch and before the shift's last hour. A preferred shape:
it gives way when an interval would go short, and never beyond the engine's hard rules. The rule and the measured
arms: evidence/phase_au/BREAKS_RULE.md (arm A, the old placement: 15 of 184 people fit; tightest buffers by day
1.75, 3.25, 3.0, 2.75, 2.75, 2.0, 1.75)."""
import unittest

from webapp.break_plan import check_row, floor, shape_fit, slots_for, suggest
from webapp.tests import test_break_plan
from webapp.versions import shift_span

ARM_A_TIGHTEST = [1.75, 3.25, 3.0, 2.75, 2.75, 2.0, 1.75]
SLOTS = [("Break 1", 15), ("Lunch", 30), ("Break 2", 15)]


class TheShape(unittest.TestCase):
    def test_a_break_set_that_fits(self):
        # 09:00 to 18:00 (540 to 1080): break 1 at 11:30, lunch 3 h of work later is too far, 2.5 h is right
        lo, hi = 540, 1080
        starts = [lo + 150, lo + 150 + 15 + 150, lo + 150 + 15 + 150 + 30 + 120]
        self.assertEqual(shape_fit(lo, hi, starts, SLOTS), (True, True, True))

    def test_each_part_is_judged_on_its_own(self):
        lo, hi = 540, 1080
        self.assertEqual(shape_fit(lo, hi, [lo + 60, None, None], SLOTS)[0], False)           # first too early
        self.assertEqual(shape_fit(lo, hi, [lo + 240, None, None], SLOTS)[0], False)          # first too late
        self.assertEqual(shape_fit(lo, hi, [lo + 150, lo + 150 + 15 + 60, None], SLOTS)[1], False)   # lunch too soon
        self.assertEqual(shape_fit(lo, hi, [lo + 150, lo + 150 + 15 + 200, None], SLOTS)[1], False)  # lunch too late
        self.assertFalse(shape_fit(lo, hi, [lo + 150, lo + 330, hi - 60], SLOTS)[2])          # last ends in the last hour
        self.assertIsNone(shape_fit(lo, hi, [None, None, None], SLOTS)[1])                     # nothing placed: no verdict

    def test_a_shift_without_lunch_has_the_first_and_last_parts_only(self):
        found = shape_fit(0, 480, [150, 300], [("Break 1", 15), ("Break 2", 15)])
        self.assertEqual(found, (True, None, True))


class TheSuggestion(test_break_plan.TheBreakPlan):
    def people(self, d, plan):
        for a in self.week["associates"]:
            span = shift_span(a["days"][d])
            if span and a["name"] in plan:
                yield a["name"], span, slots_for(self.rules, span[1] - span[0]), plan[a["name"]]

    def test_most_people_get_the_usual_shape_and_none_break_a_hard_rule(self):
        fit = total = 0
        for d in range(7):
            plan = suggest(self.week, self.inputs, self.rules, d, {})
            for name, (lo, hi), slots, starts in self.people(d, plan):
                got = [x for x in shape_fit(lo, hi, starts, slots) if x is not None]
                if got:
                    total += 1
                    fit += all(got)
                self.assertEqual(check_row(self.rules, f"{lo // 60:02d}:{lo % 60:02d} - {hi // 60 % 24:02d}:{hi % 60:02d}",
                                           starts)[0] in ("ok", "none"), True, (d, name, starts))
        self.assertGreaterEqual(fit / total, 0.95, f"{fit} of {total} fit the shape")

    def test_the_floor_is_not_given_up_for_the_shape(self):
        for d in range(7):
            plan = suggest(self.week, self.inputs, self.rules, d, {})
            cells = floor(self.week, self.inputs, d, plan, self.rules)
            worst = min(c["pm"] for c in cells if c["pm"] is not None)
            self.assertGreaterEqual(worst, ARM_A_TIGHTEST[d] - 0.75, f"day {d}")  # owner, 2026-10-21: up to 0.75 h less
            self.assertGreater(worst, 1.0, f"day {d}: still well above the need")

    def test_a_break_typed_by_hand_is_kept(self):
        d = 3
        first = next(a for a in self.working(d))
        typed = {first["name"]: [600, None, None]}
        plan = suggest(self.week, self.inputs, self.rules, d, typed)
        self.assertEqual(plan[first["name"]][0], 600)


if __name__ == "__main__":
    unittest.main()
