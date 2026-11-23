"""The solver telemetry capture must record what the engine used to discard.

The change under test is observation-only, so these tests check two things:
what is now captured, and that capturing it does not alter a solve.
"""
import os
import sys
import time
import unittest

ENGINE_DIR = os.environ.get(
    "RC9_ENGINE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "_tools"),
)
sys.path.insert(0, os.path.abspath(ENGINE_DIR))

import l632_universal_scheduler as E  # noqa: E402
from ortools.sat.python import cp_model  # noqa: E402


def _hard_model():
    """A model too big to settle inside a tiny slice, so the solve ends UNKNOWN."""
    model = cp_model.CpModel()
    xs = [model.NewIntVar(0, 10 ** 6, f"x{i}") for i in range(400)]
    for i in range(399):
        model.Add(xs[i] + xs[i + 1] >= 10 ** 5)
    model.Minimize(sum(xs))
    return model


def _solve(model, seconds):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 9000
    status = solver.Solve(model)
    return solver, status


class SolverTelemetryTest(unittest.TestCase):

    def test_the_bound_is_captured_on_unknown(self):
        """The whole point: the old diagnostics wrote None here.

        best_objective_bound was recorded only on OPTIMAL/FEASIBLE, so on a
        timed-out solve the engine discarded the one number that says how far
        the search actually got.
        """
        solver, status = _solve(_hard_model(), 0.01)
        self.assertEqual(
            E.status_name(cp_model, solver, status), "UNKNOWN",
            "fixture must produce UNKNOWN or it is not testing the fix",
        )
        telemetry = E.capture_solver_telemetry(cp_model, solver, status, 0.01)

        old_style_value = (
            solver.BestObjectiveBound()
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None
        )
        self.assertIsNone(old_style_value, "old capture should drop the bound here")
        self.assertIsNotNone(
            telemetry["best_objective_bound"],
            "new capture must keep the bound precisely when the old one dropped it",
        )
        self.assertFalse(telemetry["has_solution"])
        self.assertEqual(telemetry["status"], "UNKNOWN")

    def test_deterministic_time_is_captured(self):
        """Load-independent effort measure -- the fix for wall-clock confounding."""
        solver, status = _solve(_hard_model(), 0.05)
        telemetry = E.capture_solver_telemetry(cp_model, solver, status, 0.05)
        self.assertIsNotNone(telemetry["deterministic_time"])
        self.assertGreater(telemetry["deterministic_time"], 0.0)

    def test_capture_does_not_disturb_the_solve(self):
        """Observation only: reading telemetry must not change a result."""
        model = cp_model.CpModel()
        x = model.NewIntVar(0, 100, "x")
        y = model.NewIntVar(0, 100, "y")
        model.Add(x + y >= 40)
        model.Minimize(3 * x + 5 * y)

        solver_a, status_a = _solve(model, 5.0)
        value_a = solver_a.ObjectiveValue()

        solver_b, status_b = _solve(model, 5.0)
        E.capture_solver_telemetry(cp_model, solver_b, status_b, 5.0)
        # capture again -- repeated reads must also be inert
        E.capture_solver_telemetry(cp_model, solver_b, status_b, 5.0)
        value_b = solver_b.ObjectiveValue()

        self.assertEqual(status_a, status_b)
        self.assertEqual(value_a, value_b)

    def test_helper_sets_no_solver_parameter(self):
        """Guard the contract by reading the source, not just the behaviour."""
        import inspect
        source = inspect.getsource(E.capture_solver_telemetry)
        self.assertNotIn(
            "parameters.", source,
            "telemetry capture must never set a solver parameter",
        )
        self.assertNotIn(
            "log_search_progress", source,
            "enabling logging costs wall clock on a budgeted solve",
        )

    def test_learning_health_ratio_is_reported(self):
        solver, status = _solve(_hard_model(), 0.2)
        telemetry = E.capture_solver_telemetry(cp_model, solver, status, 0.2)
        self.assertIn("branches_per_conflict", telemetry)
        self.assertIn("slice_utilisation", telemetry)


if __name__ == "__main__":
    unittest.main(verbosity=2)
