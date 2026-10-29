# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: a bilingual is counted where they are needed, split only when both languages need them): the rule is pre-registered
in evidence/phase_ay/REQUESTS.md. ``spread_languages`` spreads the people on the floor in one 5-minute slot over the open language rows."""
import random
import unittest

from webapp.day import spread_languages

EN_FR = {"bilingual": ["english", "french"], "english": ["english"], "french": ["french"]}


class TheSpread(unittest.TestCase):
    def test_a_bilingual_needed_by_english_only_counts_there_and_not_in_french(self):
        got = spread_languages({"english": 2, "french": 3, "bilingual": 1}, EN_FR, {"english": 3, "french": 3})
        self.assertEqual(got, {"english": 3.0, "french": 3.0})

    def test_the_other_way_round(self):
        got = spread_languages({"english": 3, "french": 2, "bilingual": 1}, EN_FR, {"english": 3, "french": 3})
        self.assertEqual(got, {"english": 3.0, "french": 3.0})

    def test_both_short_by_the_same_amount_the_bilinguals_are_split(self):
        got = spread_languages({"english": 0, "french": 0, "bilingual": 2}, EN_FR, {"english": 2, "french": 2})
        self.assertEqual(got, {"english": 1.0, "french": 1.0})

    def test_one_bilingual_for_two_short_rows_is_a_half_each(self):
        got = spread_languages({"bilingual": 1}, EN_FR, {"english": 1, "french": 1})
        self.assertEqual(got, {"english": 0.5, "french": 0.5})

    def test_nobody_short_the_bilinguals_are_split_equally(self):
        got = spread_languages({"english": 5, "french": 5, "bilingual": 2}, EN_FR, {"english": 1, "french": 1})
        self.assertEqual(got, {"english": 6.0, "french": 6.0})

    def test_a_label_that_serves_one_row_counts_there_in_full(self):
        got = spread_languages({"english": 4, "french": 1}, EN_FR, {"english": 3, "french": 3})
        self.assertEqual(got, {"english": 4.0, "french": 1.0})

    def test_a_row_that_is_not_open_gets_nothing_and_the_person_goes_to_the_open_one(self):
        got = spread_languages({"bilingual": 2}, {"bilingual": ["english"]}, {"english": 3})
        self.assertEqual(got, {"english": 2.0})

    def test_a_label_that_serves_no_open_row_counts_nowhere(self):
        got = spread_languages({"spanish": 2}, {"spanish": []}, {"english": 1})
        self.assertEqual(got, {"english": 0.0})

    def test_the_counts_add_up_to_the_people_who_serve_an_open_row(self):
        people = {"english": 3, "french": 1, "bilingual": 4}
        got = spread_languages(people, EN_FR, {"english": 5, "french": 2})
        self.assertAlmostEqual(sum(got.values()), 8.0)

    def test_the_order_the_labels_are_listed_in_does_not_change_the_result(self):
        serves = {"a": ["x", "y"], "b": ["y", "z"], "c": ["x", "y", "z"], "x": ["x"], "y": ["y"], "z": ["z"]}
        people = {"a": 2, "b": 1, "c": 3, "x": 1, "y": 0, "z": 2}
        need = {"x": 4, "y": 3, "z": 5}
        want = spread_languages(people, serves, need)
        for seed in range(20):
            labels = list(people)
            random.Random(seed).shuffle(labels)
            self.assertEqual(spread_languages({k: people[k] for k in labels}, {k: serves[k] for k in labels}, need), want)


if __name__ == "__main__":
    unittest.main()
