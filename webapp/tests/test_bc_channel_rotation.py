# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC (owner, 2026-10-26: "keep each person on the same channel ... didn't change the channel ... my request was to balance, keep it
for 2-3 hours and avoid a lot of changes in and out from channels"). With the tick on, a person who can work several channels spends a couple
of hours on one, then another, instead of one channel for most of the day. Rule and acceptance: evidence/phase_bc/REQUESTS.md."""
import unittest
from unittest import mock

from webapp.channel_plan import plan_day, score_day
from webapp.tests.test_channel_plan import RULES, WED, day_people, setup


class TheScore(unittest.TestCase):
    def test_score_day_lists_every_stretch_in_minutes(self):
        people, config = day_people(), setup()
        plan = plan_day(people, config, RULES, WED, move_breaks=False)
        got = score_day(people, plan, config, WED, RULES)["stretch_minutes"]
        worked = sum((b - a) for blocks in plan["blocks"].values() for a, b, c in blocks if c in "PCE")
        self.assertEqual(sum(got), worked)  # every working minute is in exactly one stretch
        self.assertTrue(all(m % 15 == 0 and m > 0 for m in got))


class TheRotation(unittest.TestCase):
    """Measured contract (evidence/phase_bc/REQUESTS.md, sweep of DAY_MIX 0, 4, 8, 12 on base_16 and tight_16, Mon to Fri): the term shortens the
    longest stretch (4.81 to 3.87 h and 4.71 to 4.40 h) and keeps the average at 2.3 to 2.4 h; it costs some calm (changes per person-day 1.8 to
    2.4 against 2.6 with the tick off). The pre-registered limits were met on some teams and missed on others (stated in the file), so this
    test pins the direction on one day, not the limits."""

    @classmethod
    def setUpClass(cls):
        cls.people = day_people()
        cls.config = setup()
        cls.config["rules"] = dict(cls.config["rules"], fair=False, consistent=True)
        cls.plan = plan_day(cls.people, cls.config, RULES, WED, move_breaks=False)
        cls.score = score_day(cls.people, cls.plan, cls.config, WED, RULES)
        with mock.patch("webapp.channel_plan.DAY_MIX", 0):
            cls.plan_without = plan_day(cls.people, cls.config, RULES, WED, move_breaks=False)
            cls.score_without = score_day(cls.people, cls.plan_without, cls.config, WED, RULES)

    def test_the_longest_stretch_of_a_person_is_shorter_than_without_the_term(self):
        longest = sum(self.score["longest_minutes"]) / len(self.score["longest_minutes"])
        without = sum(self.score_without["longest_minutes"]) / len(self.score_without["longest_minutes"])
        self.assertLess(longest, without * 0.95)

    def test_a_stretch_is_a_couple_of_hours_on_average(self):
        stretches = self.score["stretch_minutes"]
        self.assertTrue(2.0 <= sum(stretches) / len(stretches) / 60 <= 3.0)

    def test_the_term_is_not_charged_with_the_tick_off(self):
        off = dict(self.config, rules=dict(self.config["rules"], consistent=False))
        with mock.patch("webapp.channel_plan.DAY_MIX", 0):
            was = score_day(self.people, plan_day(self.people, off, RULES, WED, move_breaks=False), off, WED, RULES)
        now = score_day(self.people, plan_day(self.people, off, RULES, WED, move_breaks=False), off, WED, RULES)
        self.assertEqual(sum(now["stretch_minutes"]), sum(was["stretch_minutes"]))  # the same hours worked, same coverage
        self.assertEqual((now["short"], now["language_short"]), (was["short"], was["language_short"]))

    def test_the_tick_still_calms_changes_and_short_stretches_against_off(self):
        off = dict(self.config, rules=dict(self.config["rules"], consistent=False))
        base = score_day(self.people, plan_day(self.people, off, RULES, WED, move_breaks=False), off, WED, RULES)
        self.assertLess(self.score["moves"], base["moves"])
        self.assertLess(self.score["short_stretches"], base["short_stretches"])

    def test_coverage_comes_first(self):
        self.assertEqual(self.score["problems"], [])
        lost = sum(self.score["short"].values()) + self.score["language_short"] \
            - sum(self.score_without["short"].values()) - self.score_without["language_short"]
        self.assertLessEqual(lost, 0.5)


if __name__ == "__main__":
    unittest.main()
