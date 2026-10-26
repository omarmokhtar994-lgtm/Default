# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC (owner, 2026-10-26: "keep each person on the same channel ... didn't change the channel ... my request was to balance, keep it
for 2-3 hours and avoid a lot of changes in and out from channels"). With the tick on, a person who can work several channels spends a couple
of hours on one, then another, instead of one channel for most of the day. Rule and acceptance: evidence/phase_bc/REQUESTS.md."""
import unittest

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
    @classmethod
    def setUpClass(cls):
        cls.people = day_people()
        cls.config = setup()
        cls.config["rules"] = dict(cls.config["rules"], fair=False, consistent=True)
        cls.plan = plan_day(cls.people, cls.config, RULES, WED, move_breaks=False)
        cls.score = score_day(cls.people, cls.plan, cls.config, WED, RULES)

    def longest_per_person(self):
        longest = []
        for name, blocks in self.plan["blocks"].items():
            runs, last = [], None
            for a, b, c in sorted(blocks):
                if c not in "PCE":
                    continue
                if last == c:
                    runs[-1] += b - a
                else:
                    runs.append(b - a)
                last = c
            if runs:
                longest.append(max(runs))
        return longest

    def test_a_stretch_is_a_couple_of_hours_on_average_not_most_of_the_day(self):
        stretches = self.score["stretch_minutes"]
        self.assertLessEqual(sum(stretches) / len(stretches) / 60, 3.0)

    def test_the_longest_stretch_of_a_person_stays_near_three_hours(self):
        longest = self.longest_per_person()
        self.assertLessEqual(sum(longest) / len(longest) / 60, 4.0)

    def test_still_not_an_hour_here_and_an_hour_there(self):
        # the tick's first promise (Phase AY) keeps holding beside the new one
        off = setup()
        off["rules"] = dict(off["rules"], fair=False, consistent=False)
        base = score_day(self.people, plan_day(self.people, off, RULES, WED, move_breaks=False), off, WED, RULES)
        self.assertLessEqual(self.score["short_stretches"], base["short_stretches"] * 0.6)
        self.assertLessEqual(self.score["moves"], base["moves"] * 0.75)

    def test_coverage_comes_first(self):
        self.assertEqual(self.score["problems"], [])


if __name__ == "__main__":
    unittest.main()
