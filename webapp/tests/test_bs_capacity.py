# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BS (owner, 2026-11-18: "then add capacity plan"): people needed against people held, week by week, with the hiring it implies.
Hand-worked numbers; made-up programs."""
import math
import unittest
from datetime import date, timedelta

from webapp import capacity as C

FIRST = date(2026, 11, 22)    # a Sunday


def weeks(hours):
    return [{"week": (FIRST + timedelta(weeks=i)).isoformat(), "hours": h, "low": h * 0.9, "high": h * 1.1} for i, h in enumerate(hours)]


def inputs(**over):
    base = {"head_count": "20", "hours_per_week": "40", "attrition": "", "training_weeks": "", "nesting_weeks": "", "nesting_output": "", "classes": []}
    return C.check_inputs({**base, **over}, FIRST)


class TheInputs(unittest.TestCase):
    def test_blanks_take_the_stated_defaults(self):
        got = inputs()
        self.assertEqual(got, {"head_count": 20.0, "hours_per_week": 40.0, "attrition": 0.0, "training_weeks": 4, "nesting_weeks": 2,
                               "nesting_output": 50.0, "classes": []})

    def test_head_count_is_required_never_invented(self):
        with self.assertRaisesRegex(ValueError, "head count"):
            inputs(head_count="")

    def test_a_bad_value_is_refused_by_name(self):
        for field, bad, words in (("attrition", "120", "Attrition"), ("head_count", "-3", "head count"), ("hours_per_week", "80", "Hours a week"),
                                  ("training_weeks", "2.5", "Training"), ("nesting_output", "5", "output"), ("attrition", "lots", "Attrition")):
            with self.assertRaisesRegex(ValueError, words, msg=f"{field}={bad}"):
                inputs(**{field: bad})

    def test_a_class_is_a_week_start_and_whole_people(self):
        got = inputs(classes=[{"week": "2026-12-06", "people": "8"}])
        self.assertEqual(got["classes"], [{"week": "2026-12-06", "people": 8}])
        for bad in ({"week": "2026-12-07", "people": "8"},           # a Monday
                    {"week": "2026-01-04", "people": "8"},           # more than 26 weeks before the plan starts
                    {"week": "2026-12-06", "people": "0"},
                    {"week": "2026-12-06", "people": "eight"}):
            with self.assertRaisesRegex(ValueError, "class", msg=str(bad)):
                inputs(classes=[bad])
        with self.assertRaisesRegex(ValueError, "20 classes"):
            inputs(classes=[{"week": "2026-12-06", "people": "1"}] * 21)


class ThePlan(unittest.TestCase):
    def test_needed_is_floor_hours_over_the_productive_hours_of_one_person(self):
        out = C.plan(weeks([560.0]), inputs(), shrinkage=0.30)
        row = out["weeks"][0]
        self.assertEqual(row["needed"], 20.0)                 # 560 / (40 x 0.7)
        self.assertEqual((row["needed_low"], row["needed_high"]), (18.0, 22.0))
        self.assertEqual((row["available"], row["gap"]), (20.0, 0.0))
        self.assertIsNone(out["first_short"])
        self.assertIsNone(out["suggestion"])

    def test_attrition_is_typed_per_month_and_taken_weekly(self):
        out = C.plan(weeks([0.0] * 3), inputs(attrition="10"), shrinkage=0.0)
        keep = 0.9 ** (1 / 4.345)
        self.assertEqual([r["available"] for r in out["weeks"]], [20.0, round(20 * keep, 1), round(20 * keep ** 2, 1)])

    def test_a_class_counts_nothing_in_training_part_in_nesting_then_whole(self):
        got = inputs(training_weeks="2", nesting_weeks="1", nesting_output="50", classes=[{"week": FIRST.isoformat(), "people": "10"}])
        out = C.plan(weeks([0.0] * 4), got, shrinkage=0.0)
        self.assertEqual([r["available"] for r in out["weeks"]], [20.0, 20.0, 25.0, 30.0])
        self.assertEqual([r["classes_live"] for r in out["weeks"]], [0.0, 0.0, 5.0, 10.0])

    def test_a_class_started_before_the_plan_is_already_on_its_way(self):
        before = (FIRST - timedelta(weeks=2)).isoformat()
        got = inputs(training_weeks="2", nesting_weeks="0", classes=[{"week": before, "people": "4"}])
        self.assertEqual(C.plan(weeks([0.0]), got, shrinkage=0.0)["weeks"][0]["available"], 24.0)

    def test_the_first_short_week_gets_a_class_that_is_ready_in_time(self):
        hours = [560.0] * 8 + [700.0] * 2           # weeks 8 and 9 need 25 people
        out = C.plan(weeks(hours), inputs(training_weeks="4", nesting_weeks="2"), shrinkage=0.30)
        short = (FIRST + timedelta(weeks=8)).isoformat()
        self.assertEqual(out["first_short"], short)
        self.assertEqual(out["suggestion"], {"start": (FIRST + timedelta(weeks=2)).isoformat(), "people": 5, "ready": short, "late": False})

    def test_a_class_for_a_short_week_too_close_to_reach_starts_now_and_says_it_is_late(self):
        out = C.plan(weeks([700.0]), inputs(training_weeks="4", nesting_weeks="2", attrition="5"), shrinkage=0.30)
        keep = 0.95 ** (1 / 4.345)
        self.assertEqual(out["suggestion"], {"start": FIRST.isoformat(), "people": math.ceil(5 / keep ** 6),
                                             "ready": (FIRST + timedelta(weeks=6)).isoformat(), "late": True})

    def test_no_weeks_gives_an_empty_plan(self):
        self.assertEqual(C.plan([], inputs(), shrinkage=0.3), {"weeks": [], "first_short": None, "suggestion": None})

    def test_shrinkage_of_100_percent_is_refused(self):
        with self.assertRaisesRegex(ValueError, "hrinkage"):
            C.plan(weeks([10.0]), inputs(), shrinkage=1.0)


if __name__ == "__main__":
    unittest.main()
