"""Native CP-SAT limits: memory ceiling and relative-gap stop.

The defaults must be inert -- shipping this must not change any schedule until
a value is deliberately chosen and A/B'd.
"""
import os
import sys
import unittest

ENGINE_DIR = os.environ.get(
    "RC9_ENGINE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "_tools"),
)
sys.path.insert(0, os.path.abspath(ENGINE_DIR))

import l632_universal_scheduler as E  # noqa: E402
from ortools.sat.python import cp_model  # noqa: E402


class SolverLimitsTest(unittest.TestCase):

    def setUp(self):
        self._mem = E.SOLVER_MAX_MEMORY_MB
        self._gap = E.SOLVER_RELATIVE_GAP_LIMIT

    def tearDown(self):
        E.SOLVER_MAX_MEMORY_MB = self._mem
        E.SOLVER_RELATIVE_GAP_LIMIT = self._gap

    def test_defaults_are_inert(self):
        """Shipping this must not change a single solve until opted into."""
        self.assertIsNone(E.SOLVER_MAX_MEMORY_MB)
        self.assertEqual(E.SOLVER_RELATIVE_GAP_LIMIT, 0.0)

        solver = cp_model.CpSolver()
        before_mem = solver.parameters.max_memory_in_mb
        before_gap = solver.parameters.relative_gap_limit
        applied = E.configure_solver_limits(solver)

        self.assertEqual(solver.parameters.max_memory_in_mb, before_mem)
        self.assertEqual(solver.parameters.relative_gap_limit, before_gap)
        self.assertIsNone(applied["max_memory_in_mb"])
        self.assertIsNone(applied["relative_gap_limit"])

    def test_memory_limit_is_applied_when_set(self):
        E.SOLVER_MAX_MEMORY_MB = 2048
        solver = cp_model.CpSolver()
        applied = E.configure_solver_limits(solver)
        self.assertEqual(solver.parameters.max_memory_in_mb, 2048)
        self.assertEqual(applied["max_memory_in_mb"], 2048)

    def test_cpsat_default_memory_exceeds_a_small_container(self):
        """The reason this exists: CP-SAT aims above the ceiling that kills it.

        The OOM that prompted this change died at 7.76 GB resident while the
        solver's own ceiling was still 10 GB.
        """
        self.assertGreaterEqual(
            cp_model.CpSolver().parameters.max_memory_in_mb, 10000,
            "if this default dropped, re-derive the memory guidance",
        )

    def test_gap_limit_is_applied_when_set(self):
        E.SOLVER_RELATIVE_GAP_LIMIT = 0.01
        solver = cp_model.CpSolver()
        applied = E.configure_solver_limits(solver)
        self.assertAlmostEqual(solver.parameters.relative_gap_limit, 0.01)
        self.assertAlmostEqual(applied["relative_gap_limit"], 0.01)

    def test_gap_limit_actually_stops_the_search_early(self):
        """Non-vacuity: a loose gap must return sooner than proving optimality."""
        def build():
            model = cp_model.CpModel()
            xs = [model.NewIntVar(0, 10 ** 4, f"x{i}") for i in range(220)]
            for i in range(219):
                model.Add(xs[i] + xs[i + 1] >= 9000)
            for i in range(0, 200, 7):
                model.Add(xs[i] + xs[i + 10] + xs[i + 20] >= 14000)
            model.Minimize(sum((i % 5 + 1) * xs[i] for i in range(220)))
            return model

        def run(gap):
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30.0
            solver.parameters.num_search_workers = 1
            solver.parameters.random_seed = 9000
            if gap:
                solver.parameters.relative_gap_limit = gap
            status = solver.Solve(build())
            return solver.WallTime(), solver.ObjectiveValue(), solver.StatusName(status)

        exact_time, exact_obj, _ = run(0.0)
        loose_time, loose_obj, _ = run(0.25)

        self.assertLessEqual(
            loose_time, exact_time + 1e-6,
            "a loose gap limit must never take longer than proving optimality",
        )
        self.assertGreaterEqual(
            loose_obj, exact_obj - 1e-6,
            "a loose gap minimisation cannot beat the proven optimum",
        )

    def test_limits_do_not_touch_search_strategy(self):
        """Primer warning: top-level search params perturb the subsolver portfolio.

        Termination limits are safe; selecting subsolvers or workers is not.
        """
        import ast
        import inspect
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(E.configure_solver_limits)))
        func = tree.body[0]
        # Drop the docstring: it legitimately discusses subsolvers and workers.
        body = func.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]
        code = "\n".join(ast.dump(node) for node in body)

        for forbidden in ("num_search_workers", "num_workers", "subsolver",
                          "search_branching", "linearization_level", "cp_model_presolve"):
            self.assertNotIn(
                forbidden, code,
                f"limits helper must not touch {forbidden} in executable code",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
