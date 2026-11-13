# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL audit: the channel planner's first solve, when it has breaks to place, uses large-neighbourhood search only.

``test_channel_plan`` failed intermittently, on the commit before Phase BL too: the planner stops FEASIBLE at its wall-clock limit, and with the default
portfolio the objective it reached swung from 54 to 300 between identical runs, the high ones leaving a "normal maximum gap" rule missed. Measured on the
test's own scenario, 12 runs each (evidence/phase_bl/channel_solver_ab.md): ``use_lns_only`` had no rule problem in 12 of 12 with a median objective of
about 36; today's setting had a problem in 4 of 12 with a median of about 158, at the same wall time.
Only the solve that places empty breaks takes it: the measurement was of that case, and plans of typed breaks (test_bc_channel_rotation, test_bc_two_ticks
compare them against each other) keep exactly their old settings, as does the second solve, which may move breaks and starts from the first's plan. If it ever finds no plan at all,
the old settings are tried before the planner gives up, so a day that planned before still plans."""
import unittest
from unittest import mock

from ortools.sat.python import cp_model

from webapp import channel_plan as CP
from webapp.channel_solver import Solution
from webapp.tests.test_channel_plan import RULES, WED, day_people, setup


class TheFirstSolveSetting(unittest.TestCase):
    def test_only_the_solve_that_places_breaks_uses_large_neighbourhood_search_only(self):
        self.assertEqual(CP.KEPT, {"num_workers": 4, "max_time_in_seconds": 12.0, "random_seed": 9000})
        self.assertEqual(CP.MOVING, {"num_workers": 4, "max_time_in_seconds": 10.0, "random_seed": 9000})
        # re-pinned 2026-11-08 (owner's decision): placing blank breaks gets 25 s; at 12 s it passed the normal maximum gap in 3 of 20 runs, at 25 s in
        # none of 20 (evidence/phase_bl/channel_solver_ab.md)
        self.assertEqual(CP.PLACING, {**CP.KEPT, "use_lns_only": True, "max_time_in_seconds": 25.0})

    def test_typed_breaks_keep_their_old_settings_and_empty_ones_get_the_new(self):
        seen = []
        real = CP._solve

        def spy(*args, **kwargs):
            seen.append(kwargs.get("solver_settings"))
            raise CP.NoPlan("stop here")

        with mock.patch.object(CP, "_solve", spy):
            for with_breaks, want in ((True, CP.KEPT), (False, CP.PLACING)):
                with self.assertRaises(CP.NoPlan):
                    CP.plan_day(day_people(with_breaks=with_breaks), setup(), RULES, WED, move_breaks=False)
                self.assertEqual(seen[-1], want, with_breaks)

    def test_when_it_finds_no_plan_the_old_settings_are_tried(self):
        real = CP.solve_channels
        calls = []

        def stub(model, settings):
            calls.append(dict(settings))
            if settings.get("use_lns_only"):
                return Solution(int(cp_model.UNKNOWN), "UNKNOWN", [], str(settings))
            return real(model, settings)

        people = day_people(with_breaks=False)
        with mock.patch.object(CP, "solve_channels", stub):
            plan = CP.plan_day(people, setup(), RULES, WED)
        self.assertEqual([bool(c.get("use_lns_only")) for c in calls], [True, False])
        self.assertIn(plan["status"], ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(all(len(plan["breaks"][p["name"]]) == 3 for p in people))

    def test_when_neither_finds_a_plan_it_says_so_as_before(self):
        people = day_people(with_breaks=False)
        calls = []

        def stub(model, settings):
            calls.append(dict(settings))
            return Solution(int(cp_model.UNKNOWN), "UNKNOWN", [], str(settings))

        with mock.patch.object(CP, "solve_channels", stub):
            with self.assertRaises(CP.NoPlan) as caught:
                CP.plan_day(people, setup(), RULES, WED)
        self.assertIn("No plan was found in the time allowed", str(caught.exception))
        self.assertEqual(len(calls), 2)

    def test_an_infeasible_day_is_still_said_to_be_infeasible_without_a_second_try(self):
        people = day_people(with_breaks=False)
        calls = []

        def stub(model, settings):
            calls.append(dict(settings))
            return Solution(int(cp_model.INFEASIBLE), "INFEASIBLE", [], str(settings))

        with mock.patch.object(CP, "solve_channels", stub):
            with self.assertRaises(CP.NoPlan) as caught:
                CP.plan_day(people, setup(), RULES, WED)
        self.assertIn("cannot all fit", str(caught.exception))
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
