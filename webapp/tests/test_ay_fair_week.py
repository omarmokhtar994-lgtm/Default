# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "I don't see fairness applies that much"): over a week the planner keeps the minutes of
people with the same channels and language close together. Rule pre-registered in evidence/phase_ay/REQUESTS.md.

The week is the 16-person test day planned Mon to Fri with the earlier days carried. The figure is the sum over groups
and channels of (most hours minus fewest hours). Measured before the change, with the same script: 35.5 h with the
tick off and 78.75 h with it on; hours short 2.5 in both. The new planner is accepted at no more than 2/3 of that."""
import unittest

from webapp.channel_plan import plan_day, score_day
from webapp.tests.test_channel_plan import RULES, day_people, setup

OLD_RANGE = {False: 35.5, True: 78.75}
OLD_SHORT = 2.5


def plan_week(consistent):
    people, config, carry, short = day_people(), setup(), {}, 0.0
    config["rules"] = dict(config["rules"], fair=True, consistent=consistent)
    for d in (1, 2, 3, 4, 5):
        plan = plan_day(people, config, RULES, d, carry=carry, move_breaks=False)
        got = score_day(people, plan, config, d, RULES)
        short += sum(got["short"].values()) + got["language_short"]
        for name, blocks in plan["blocks"].items():
            for a, b, c in blocks:
                if c in "PCE":
                    carry.setdefault(name, {})[c] = carry.get(name, {}).get(c, 0) + b - a
    groups = {}
    for p in people:
        groups.setdefault((p["skills"], p["language"]), []).append(p["name"])
    spread = 0.0
    for (skills, _), names in groups.items():
        if len(names) > 1:
            for c in skills:
                hours = [carry.get(n, {}).get(c, 0) / 60 for n in names]
                spread += max(hours) - min(hours)
    return spread, short


class TheFairWeek(unittest.TestCase):
    def check(self, consistent):
        spread, short = plan_week(consistent)
        self.assertLessEqual(spread, OLD_RANGE[consistent] * 2 / 3)
        self.assertLessEqual(short, OLD_SHORT + 0.5)

    def test_people_alike_end_the_week_closer_with_the_tick_off(self):
        self.check(False)

    def test_and_with_the_consistency_tick_on(self):
        self.check(True)


if __name__ == "__main__":
    unittest.main()
