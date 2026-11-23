# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC (owner, 2026-10-26: Chat-and-Email people "weren't very balanced"; "keep it for 2-3 hours"): with the Balanced tick a stretch on one channel
that runs past STRETCH_LIMIT quarter hours costs STRETCH_OVER per quarter hour, for a person who can work exactly two channels, so two people sharing a
Chat need swap over every few hours instead of one keeping Chat all day. Rule and acceptance: evidence/phase_bc/REQUESTS.md."""
import unittest
from unittest import mock

from webapp.channel_plan import plan_day, score_day
from webapp.tests.test_channel_plan import RULES, WED, setup

NO_BREAKS = {**RULES, "segments": []}


def person(name):
    return {"name": name, "language": "English", "start": 480, "end": 1020, "skills": "CE", "counts_for": {"english"}, "breaks": []}


def config(balanced=True):
    grid = lambda f: {d: {t: f(t) for t in range(0, 1440, 30)} for d in range(7)}  # noqa: E731
    found = setup(need={"C": grid(lambda t: 1 if 480 <= t < 1020 else 0)}, languages=[],
                  email_hours={d: {"hours": 0.0, "languages": {}, "start": 480, "end": 1020} for d in range(7)})
    found["rules"] = dict(found["rules"], fair=False, balanced=balanced, consistent=False, max_run={"P": 0, "C": 0, "E": 0})
    return found


def longest_hours(over, balanced=True):
    people = [person("Associate 001"), person("Associate 002")]
    cfg = config(balanced)
    with mock.patch("webapp.channel_plan.STRETCH_OVER", over):
        plan = plan_day(people, cfg, NO_BREAKS, WED, move_breaks=False)
    got = score_day(people, plan, cfg, WED, NO_BREAKS)
    assert got["problems"] == [], got["problems"]
    return max(got["longest_minutes"]) / 60, got


class TheLongStretch(unittest.TestCase):
    def test_two_people_sharing_one_chat_need_swap_over_instead_of_one_keeping_it_all_day(self):
        without, _ = longest_hours(0)
        with_term, got = longest_hours(10)
        self.assertGreater(without, 5)  # the problem: one of them stays on Chat most of the day
        self.assertLessEqual(with_term, 3.5)  # a stretch is about three hours, then they swap
        self.assertEqual(sum(got["short"].values()), 0)  # and Chat stays covered the whole day

    def test_only_the_balanced_tick_has_it(self):
        fixed, _ = longest_hours(10, balanced=False)
        self.assertGreater(fixed, 5)

    def test_a_person_with_three_channels_is_not_charged(self):
        # measured: charged too, three-channel people changed channel more often than with the tick off (2.8 to 3.3 against 2.5 a day), so the
        # term is not in the model for them: counted as boolean variables, which is exact where comparing two timed plans would not be
        from ortools.sat.python import cp_model

        def booleans(skills, over):
            made = []
            real = cp_model.CpModel.new_bool_var

            def spy(self, name=""):
                made.append(1)
                return real(self, name)
            people = [dict(person("Associate 001"), skills=skills), dict(person("Associate 002"), skills=skills)]
            cfg = config()
            cfg["need"]["P"] = cfg["need"]["C"]
            with mock.patch.object(cp_model.CpModel, "new_bool_var", spy), mock.patch("webapp.channel_plan.STRETCH_OVER", over):
                plan_day(people, cfg, NO_BREAKS, WED, move_breaks=False)
            return len(made)
        self.assertEqual(booleans("PCE", 0), booleans("PCE", 10))
        self.assertGreater(booleans("CE", 10), booleans("CE", 0))

    def test_the_shipped_weight_is_the_measured_one(self):
        from webapp import channel_plan
        self.assertEqual((channel_plan.STRETCH_LIMIT, channel_plan.STRETCH_OVER), (12, 20))


if __name__ == "__main__":
    unittest.main()
