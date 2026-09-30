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
        self.assertEqual(E.SOLVER_MAX_MEMORY_MB, 6000)
        self.assertEqual(E.SOLVER_RELATIVE_GAP_LIMIT, 0.0)

        solver = cp_model.CpSolver()
        before_gap = solver.parameters.relative_gap_limit
        applied = E.configure_solver_limits(solver)

        # The gap limit is what must stay inert: it can trade away coverage on
        # this objective. The memory ceiling is protective and IS applied.
        self.assertEqual(solver.parameters.relative_gap_limit, before_gap)
        self.assertIsNone(applied["relative_gap_limit"])
        self.assertEqual(applied["max_memory_in_mb"], 6000)
        self.assertLess(
            E.SOLVER_MAX_MEMORY_MB, 7760,
            "ceiling must bind before the cgroup OOM killer did",
        )

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
        """Non-vacuity: a loose gap must stop the search before optimality is proved.

        Re-pinned 2026-09-30 (audit gate run): the previous model was solved by
        presolve at the root, so both runs did identical work (205 branches, the
        same deterministic time) and the test compared two ~12 ms wall clocks --
        it failed on timer noise and could never detect a gap limit that did
        nothing. This multi-knapsack needs real search, and the comparison uses
        CP-SAT's deterministic time and branch count (single worker, fixed
        seed), which are reproducible, instead of wall time.
        """
        import random

        def build():
            rnd = random.Random(7)
            model = cp_model.CpModel()
            xs = [model.NewBoolVar(f"x{i}") for i in range(60)]
            for _ in range(5):
                w = [rnd.randint(10, 100) for _ in range(60)]
                model.Add(sum(w[i] * xs[i] for i in range(60)) <= sum(w) // 3)
            v = [rnd.randint(10, 100) for _ in range(60)]
            model.Maximize(sum(v[i] * xs[i] for i in range(60)))
            return model

        def run(gap):
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30.0
            solver.parameters.num_search_workers = 1
            solver.parameters.random_seed = 9000
            if gap:
                solver.parameters.relative_gap_limit = gap
            solver.Solve(build())
            return (solver.ResponseProto().deterministic_time, solver.NumBranches(),
                    solver.ObjectiveValue(), solver.BestObjectiveBound())

        exact_work, exact_branches, exact_obj, exact_bound = run(0.0)
        loose_work, loose_branches, loose_obj, loose_bound = run(0.05)

        self.assertEqual(exact_obj, exact_bound, "the reference run must prove optimality")
        self.assertGreater(loose_bound, loose_obj, "the loose run must stop with an open gap")
        self.assertLessEqual((loose_bound - loose_obj) / loose_bound, 0.05 + 1e-9)
        self.assertLess(loose_work, exact_work / 2,
                        "a loose gap limit must stop the search well before proving optimality")
        self.assertLess(loose_branches, exact_branches)
        self.assertLessEqual(loose_obj, exact_obj + 1e-6,
                             "a loose gap maximisation cannot beat the proven optimum")

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
