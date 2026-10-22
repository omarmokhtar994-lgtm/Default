# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: "that should be the case for any two layers: prioritize the default, followed by the engine"):
how well a person's breaks fit the two layers, so every tool that schedules breaks can rank by it. The default is the usual
shape (first break 2 to 3.5 hours in, lunch 2 to 3 hours of work after it, the last break ending an hour before the shift
does); the engine's layer is the workbook's rules (margin, windows, gaps, order)."""
import unittest

from webapp.break_plan import fit
from webapp.tests.test_channel_plan import RULES

H = 60
LABEL = "10:00 - 19:00"  # 600 to 1140


class TheFitOfABreakSet(unittest.TestCase):
    def test_breaks_in_the_usual_shape_and_inside_the_rules_miss_nothing(self):
        self.assertEqual(fit(RULES, LABEL, [12.5 * H, 15 * H, 17.25 * H]), (0, []))

    def test_each_part_of_the_shape_missed_is_counted(self):
        shape, rules = fit(RULES, LABEL, [10.75 * H, 12 * H, 15 * H])  # first 45 minutes in; lunch 60 minutes of work after
        self.assertEqual(shape, 2)
        self.assertEqual(rules, [])  # all of it inside the engine's rules

    def test_the_last_break_too_close_to_the_end_is_a_miss(self):
        shape, _ = fit(RULES, LABEL, [12.5 * H, 15 * H, 18.25 * H])
        self.assertEqual(shape, 1)

    def test_the_engines_rules_are_listed_in_words(self):
        shape, rules = fit({**RULES, "min_gap": 60}, LABEL, [12.5 * H, 13 * H, 17 * H])  # lunch 15 minutes after the first
        self.assertTrue(any("minimum gap" in r for r in rules), rules)

    def test_the_five_minute_steps_of_the_rta_are_not_a_rule_here(self):
        _, rules = fit(RULES, LABEL, [12.5 * H + 5, 15 * H, 17.25 * H])
        self.assertFalse(any("15-minute" in r for r in rules), rules)

    def test_a_break_that_is_not_there_is_not_a_miss(self):
        shape, rules = fit(RULES, LABEL, [12.5 * H, None, 17.25 * H])  # cancelled
        self.assertEqual(rules, [])

    def test_a_window_in_the_rules_is_an_engine_miss_not_a_shape_miss(self):
        windowed = {**RULES, "windows": {**RULES["windows"], "break 1": {"earliest": None, "latest": 100}}}
        shape, rules = fit(windowed, LABEL, [12.5 * H, 15 * H, 17.25 * H])
        self.assertEqual(shape, 0)
        self.assertTrue(rules)


if __name__ == "__main__":
    unittest.main()


from webapp.break_plan import break_default  # noqa: E402


class TheFitOfOneBreak(unittest.TestCase):
    """The parts of the two layers that one break decides alone (Rescue weighs these): the first break's and the last
    break's place in the shape, and the engine's margin and window for it."""
    def test_a_first_break_inside_the_band_misses_nothing(self):
        self.assertEqual(break_default(RULES, LABEL, 0, 3, 12.5 * H), (0, 0))

    def test_a_first_break_too_early_or_too_late_misses_the_shape(self):
        self.assertEqual(break_default(RULES, LABEL, 0, 3, 10.75 * H), (1, 0))
        self.assertEqual(break_default(RULES, LABEL, 0, 3, 14 * H), (1, 0))

    def test_the_last_break_ending_too_near_the_end_misses_the_shape(self):
        self.assertEqual(break_default(RULES, LABEL, 2, 3, 18 * H), (1, 0))  # ends 18:15; the engine's margin is 45 minutes, so 18:15 is the latest
        self.assertEqual(break_default(RULES, LABEL, 2, 3, 17.25 * H), (0, 0))

    def test_a_middle_break_has_no_shape_of_its_own(self):
        self.assertEqual(break_default(RULES, LABEL, 1, 3, 10.25 * H)[0], 0)

    def test_the_engines_edge_margin_and_window_count_as_the_engines(self):
        windowed = {**RULES, "windows": {**RULES["windows"], "lunch": {"earliest": 240, "latest": None}}}
        self.assertEqual(break_default(windowed, LABEL, 1, 3, 12 * H), (0, 1))  # 2 hours in; the window says 4
        self.assertEqual(break_default({**RULES, "edge_margin": 30}, LABEL, 0, 3, 10.25 * H), (1, 1))
