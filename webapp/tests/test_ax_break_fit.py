# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: "the default 2 to 3.5 hours is the timing that makes the most sense, the engine should be near
that as well, not far; in a rescue or a fix I can sacrifice the rules towards an interval win, but to the nearest"): how far a
person's breaks are from the two layers, in minutes, so every tool can sacrifice as little as it must. The default is the
usual shape (first break 2 to 3.5 hours in, lunch 2 to 3 hours of work after it, the last break ending an hour before the
shift does); the engine's layer is the workbook's rules (margin, windows, gaps)."""
import unittest

from webapp.break_plan import break_default, fit, fit_words
from webapp.tests.test_channel_plan import RULES

H = 60
LABEL = "10:00 - 19:00"  # 600 to 1140; the engine's own edge margin for it is 45 minutes


class TheDistanceOfABreakSet(unittest.TestCase):
    def test_breaks_in_the_usual_shape_and_inside_the_rules_are_at_no_distance(self):
        self.assertEqual(fit(RULES, LABEL, [12.5 * H, 15 * H, 17.25 * H]), (0, 0))

    def test_the_shape_is_measured_in_the_minutes_each_part_is_off(self):
        # first break 45 minutes in (75 short of 2 hours); lunch 60 minutes of work after it (60 short of 2 hours)
        self.assertEqual(fit(RULES, LABEL, [10.75 * H, 12 * H, 15 * H]), (135, 0))

    def test_a_first_break_too_late_is_measured_past_three_and_a_half_hours(self):
        shape, _ = fit(RULES, LABEL, [14 * H, 16.5 * H, 17.25 * H])  # 240 minutes in: 30 past 210
        self.assertEqual(shape, 30)

    def test_the_last_break_ending_too_near_the_end_is_measured_in_minutes(self):
        shape, rules = fit(RULES, LABEL, [12.5 * H, 15 * H, 18.25 * H])  # ends 18:30: 30 past 18:00; 15 past the margin
        self.assertEqual((shape, rules), (30, 15))

    def test_the_engines_rules_are_measured_in_minutes_too(self):
        windowed = {**RULES, "windows": {**RULES["windows"], "break 1": {"earliest": None, "latest": 100}}}
        shape, rules = fit(windowed, LABEL, [12.5 * H, 15 * H, 17.25 * H])  # 150 minutes in; the window says 100
        self.assertEqual((shape, rules), (0, 50))

    def test_a_gap_short_of_the_minimum_is_measured(self):
        _, rules = fit({**RULES, "min_gap": 60}, LABEL, [12.5 * H, 13 * H, 17 * H])  # lunch 15 minutes after the first ends
        self.assertGreaterEqual(rules, 45)

    def test_the_five_minute_steps_of_the_rta_are_not_a_rule_here(self):
        self.assertEqual(fit(RULES, LABEL, [12.5 * H + 5, 15 * H, 17.25 * H]), (0, 0))

    def test_a_break_that_is_not_there_costs_nothing_and_holds_no_gap(self):
        self.assertEqual(fit(RULES, LABEL, [12.5 * H, None, 17.25 * H]), (0, 0))  # cancelled: no gap across it


class TheDistanceOfOneBreak(unittest.TestCase):
    """The parts one break decides alone (Rescue weighs these): the first and last break's place in the shape, and the
    engine's margin and window for it."""
    def test_a_first_break_inside_the_band_is_at_no_distance(self):
        self.assertEqual(break_default(RULES, LABEL, 0, 3, 12.5 * H), (0, 0))

    def test_a_first_break_off_the_band_is_measured_to_its_nearest_edge(self):
        self.assertEqual(break_default(RULES, LABEL, 0, 3, 10.75 * H), (75, 0))
        self.assertEqual(break_default(RULES, LABEL, 0, 3, 14 * H), (30, 0))

    def test_the_last_break_is_measured_by_how_far_past_an_hour_before_the_end_it_ends(self):
        self.assertEqual(break_default(RULES, LABEL, 2, 3, 18 * H), (15, 0))  # ends 18:15; the engine's margin allows it
        self.assertEqual(break_default(RULES, LABEL, 2, 3, 17.25 * H), (0, 0))

    def test_a_middle_break_has_no_shape_of_its_own(self):
        self.assertEqual(break_default(RULES, LABEL, 1, 3, 10.25 * H)[0], 0)

    def test_the_engines_margin_and_window_are_measured_as_the_engines(self):
        windowed = {**RULES, "windows": {**RULES["windows"], "lunch": {"earliest": 240, "latest": None}}}
        self.assertEqual(break_default(windowed, LABEL, 1, 3, 12 * H), (0, 120))  # 2 hours in; the window says 4
        self.assertEqual(break_default({**RULES, "edge_margin": 30}, LABEL, 0, 3, 10.25 * H), (105, 15))  # 15 in: 15 short of the margin, 105 short of the shape


class TheWords(unittest.TestCase):
    def test_a_move_that_newly_misses_the_shape_says_so(self):
        said = fit_words(RULES, LABEL, [12.5 * H, 15 * H, 17.25 * H], [10.5 * H, 15 * H, 17.25 * H])
        self.assertIn("The first break is normally 2 to 3.5 hours into the shift.", said)

    def test_a_break_already_off_is_not_blamed_for_a_nudge(self):
        self.assertEqual(fit_words(RULES, LABEL, [10.75 * H, 15 * H, 17.25 * H], [10.75 * H + 5, 15 * H, 17.25 * H]), [])


if __name__ == "__main__":
    unittest.main()


import collections  # noqa: E402

from webapp.break_plan import suggest  # noqa: E402
from webapp.tests.test_day import INPUTS, WED, WEEK  # noqa: E402
from webapp.versions import shift_span  # noqa: E402


class TheBreaksAreSpreadWhereTheBufferIsAmple(unittest.TestCase):
    """Owner, 2026-10-23, from a screenshot of a replanned day: "not that perfect even though there is buffer in the intervals":
    people on the same shift all took their breaks at the same times. Where the spare cover is ample it no longer tells times
    apart, so the breaks are spread over the quarter hours the usual shape allows. The real Voice Wednesday (29 people, 12 shifts)."""
    @classmethod
    def setUpClass(cls):
        cls.got = suggest(WEEK, INPUTS, RULES, WED, {})
        cls.by_shift = collections.defaultdict(list)
        for a in WEEK["associates"]:
            if a["name"] in cls.got and shift_span(a["days"][WED]):
                cls.by_shift[a["days"][WED]].append((a["name"], cls.got[a["name"]]))

    def test_no_more_than_three_of_a_shift_start_the_same_break_at_the_same_time(self):
        big = {k: v for k, v in self.by_shift.items() if len(v) >= 5}
        self.assertTrue(big)
        for shift, people in big.items():
            for k in range(3):
                most = max(collections.Counter(row[k] for _, row in people).values())
                self.assertLessEqual(most, 3, (shift, k))  # measured: before the spread 4, now 3 at worst

    def test_a_shift_of_seven_has_seven_different_first_breaks(self):
        seven = next(v for v in self.by_shift.values() if len(v) == 7)
        self.assertEqual(len({row[0] for _, row in seven}), 7)

    def test_the_spread_keeps_the_engines_rules_and_is_no_further_from_the_shape_than_before(self):
        # measured on this day: before the spread 5 people sat 15 to 60 minutes off the usual shape, after it 3 sit 15, 15 and 45 off
        off = []
        for shift, people in self.by_shift.items():
            for name, row in people:
                shape, rules = fit(RULES, shift, row)
                self.assertEqual(rules, 0, (name, shift, row))
                if shape:
                    off.append(shape)
        self.assertLessEqual(len(off), 3)
        self.assertLessEqual(max(off, default=0), 45)

    def test_the_same_day_gives_the_same_plan(self):
        self.assertEqual(suggest(WEEK, INPUTS, RULES, WED, {}), self.got)
