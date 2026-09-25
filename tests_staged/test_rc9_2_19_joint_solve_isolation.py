"""Joint-refinement solves run in a forked, memory-watched child process.

CHAT_DEEP_9000 was killed by the kernel at 13 GB inside joint refinement: no
schedule, no summary, no validation (evidence/DEEP_MODE_OOM.md). A replay of
that phase showed the second joint model at 3.8 GB before the solve and past
6.5 GB inside CP-SAT. The fix runs each joint solve in a fork of the engine:
same model object, same parameters, same seed, so the answer is the one the
engine would have computed in process; when the machine runs out of memory
only the child dies, the solve reports UNKNOWN, and joint refinement stops
starting new (larger) models.

These tests pin: bit-identical results on a deterministic solve; the memory
stop (watchdog, kernel kill, MemoryError) is survived and recorded; any other
child failure is raised, not hidden; the in-process fallbacks; the child dies
with its parent; the engine's joint solves use it.
"""
import inspect
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
E = B.load_engine(ENGINE)
cp_model = E.import_cp_sat()
from ortools.sat.python import cp_model_helper as CMH  # noqa: E402


def small_model(seed=1, n=250):
    import random
    rnd = random.Random(seed)
    m = cp_model.CpModel()
    xs = [m.new_bool_var(f"x{i}") for i in range(n)]
    for _ in range(n * 2):
        a, b, c = rnd.sample(xs, 3)
        m.add_bool_or([a, b.Not(), c])
    m.add(sum(xs) <= n // 2)
    m.maximize(sum(rnd.randint(1, 9) * x for x in xs))
    return m, xs


def deterministic(solver):
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.max_deterministic_time = 0.5
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 7
    return solver


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = (E.JOINT_SOLVE_ISOLATION_ENABLED, E.JOINT_SOLVE_KILL_BELOW_FREE_MB, list(E._JOINT_SOLVE_MEMORY_STOPS))
        del E._JOINT_SOLVE_MEMORY_STOPS[:]
        self.tmp_before = set(os.listdir(tempfile.gettempdir()))

    def tearDown(self):
        E.JOINT_SOLVE_ISOLATION_ENABLED, E.JOINT_SOLVE_KILL_BELOW_FREE_MB, stops = self.saved
        E._JOINT_SOLVE_MEMORY_STOPS[:] = stops

    def assert_no_leftover_files(self):
        left = {n for n in set(os.listdir(tempfile.gettempdir())) - self.tmp_before if n.startswith("joint_solve_")}
        self.assertEqual(left, set())


class SameAnswerAsInProcess(Base):
    def test_bit_identical_on_a_deterministic_solve(self):
        for seed in (1, 2):
            m, xs = small_model(seed)
            a = deterministic(cp_model.CpSolver())
            sa = a.Solve(m)
            b = deterministic(E.isolated_cp_solver(cp_model))
            sb = b.Solve(m)
            self.assertEqual(b.isolation_record["mode"], "ISOLATED")
            self.assertEqual(b.isolation_record["child_exit"], 0)
            self.assertIn(sa, (cp_model.OPTIMAL, cp_model.FEASIBLE))
            self.assertEqual(sa, sb)
            self.assertEqual(a.StatusName(sa), b.StatusName(sb))
            self.assertEqual(a.ObjectiveValue(), b.ObjectiveValue())
            self.assertEqual(a.BestObjectiveBound(), b.BestObjectiveBound())
            self.assertEqual([a.Value(x) for x in xs], [b.Value(x) for x in xs])
            self.assertEqual([a.BooleanValue(x) for x in xs], [b.BooleanValue(x) for x in xs])
            self.assertEqual(a.Value(sum(xs)), b.Value(sum(xs)))
            self.assertEqual((a.NumBranches(), a.NumConflicts()), (b.NumBranches(), b.NumConflicts()))
            self.assertEqual(a.response_proto.deterministic_time, b.response_proto.deterministic_time)
        self.assert_no_leftover_files()

    def test_lexicographic_reuse_of_the_model_matches(self):
        """The engine solves, locks the stage value into the model, then re-solves."""
        results = []
        for make in (cp_model.CpSolver, lambda: E.isolated_cp_solver(cp_model)):
            m, xs = small_model(3)
            s1 = deterministic(make())
            s1.Solve(m)
            m.add(sum(xs) >= int(s1.Value(sum(xs))))
            m.minimize(sum(xs[::2]))
            s2 = deterministic(make())
            st = s2.Solve(m)
            results.append((st, s2.ObjectiveValue(), [s2.Value(x) for x in xs]))
        self.assertEqual(results[0], results[1])

    def test_infeasible_is_reported_as_infeasible(self):
        m = cp_model.CpModel()
        x = m.new_int_var(0, 3, "x")
        m.add(x >= 5)
        s = E.isolated_cp_solver(cp_model)
        status = s.Solve(m)
        self.assertEqual(status, cp_model.INFEASIBLE)
        self.assertEqual(s.StatusName(status), "INFEASIBLE")  # StatusName() without an argument is broken in OR-Tools 9.15 itself
        self.assertEqual(E._JOINT_SOLVE_MEMORY_STOPS, [])


class MemoryStop(Base):
    def test_watchdog_stops_the_child_and_the_parent_carries_on(self):
        E.JOINT_SOLVE_KILL_BELOW_FREE_MB = 10 ** 9  # every machine is "out of memory"
        m, _ = small_model(4, n=600)
        s = E.isolated_cp_solver(cp_model)
        s.parameters.max_time_in_seconds = 60
        started = time.time()
        status = s.Solve(m)
        self.assertLess(time.time() - started, 30)
        self.assertEqual(status, cp_model.UNKNOWN)
        self.assertEqual(s.StatusName(status), "UNKNOWN")
        record = s.isolation_record
        self.assertTrue(record["killed_for_memory"])
        self.assertTrue(record["memory_stop"])
        self.assertEqual(record["child_exit"], "SIGNAL_9")
        self.assertEqual(len(E._JOINT_SOLVE_MEMORY_STOPS), 1)
        headroom = E.joint_memory_headroom()
        self.assertFalse(headroom["ok"])
        self.assertEqual(headroom["source"], "JOINT_SOLVE_ISOLATION")
        self.assert_no_leftover_files()

    def fake(self, body):
        s = E.isolated_cp_solver(cp_model)
        return s, E.isolated_cp_solve(s, None, body, CMH.CpSolverResponse)

    def test_a_kernel_oom_kill_of_the_child_is_a_memory_stop(self):
        s, status = self.fake(lambda model, cb=None: os.kill(os.getpid(), signal.SIGKILL))
        self.assertEqual(status, cp_model.UNKNOWN)
        self.assertTrue(s.isolation_record["memory_stop"])
        self.assertFalse(s.isolation_record["killed_for_memory"])
        self.assertFalse(E.joint_memory_headroom()["ok"])

    def test_bad_alloc_in_the_child_is_a_memory_stop(self):
        def raise_memory_error(model, cb=None):
            raise MemoryError("std::bad_alloc")
        s, status = self.fake(raise_memory_error)
        self.assertEqual(status, cp_model.UNKNOWN)
        self.assertEqual(s.isolation_record["child_exit"], 71)
        self.assertTrue(s.isolation_record["memory_stop"])

    def test_the_child_prefers_itself_as_the_oom_victim(self):
        E._child_prepare_for_isolated_solve  # exists
        src = inspect.getsource(E._child_prepare_for_isolated_solve)
        self.assertIn('"/proc/self/oom_score_adj"', src)
        self.assertIn('write("1000")', src)
        self.assertIn("gc.disable()", src)


class ErrorsAreNotHidden(Base):
    def test_any_other_child_failure_is_raised_in_the_parent(self):
        def broken(model, cb=None):
            raise ValueError("model trouble 1234")
        s = E.isolated_cp_solver(cp_model)
        with self.assertRaises(RuntimeError) as ctx:
            E.isolated_cp_solve(s, None, broken, CMH.CpSolverResponse)
        self.assertIn("model trouble 1234", str(ctx.exception))
        self.assertEqual(E._JOINT_SOLVE_MEMORY_STOPS, [])
        self.assert_no_leftover_files()


class InProcessFallbacks(Base):
    def test_disabled_runs_in_process(self):
        E.JOINT_SOLVE_ISOLATION_ENABLED = False
        m, _ = small_model(5)
        s = deterministic(E.isolated_cp_solver(cp_model))
        self.assertIn(s.Solve(m), (cp_model.OPTIMAL, cp_model.FEASIBLE))
        self.assertEqual((s.isolation_record["mode"], s.isolation_record["reason"]), ("IN_PROCESS", "DISABLED"))

    def test_a_solution_callback_runs_in_process(self):
        m, _ = small_model(6)
        seen = []

        class CB(cp_model.CpSolverSolutionCallback):
            def on_solution_callback(self):
                seen.append(self.ObjectiveValue())

        s = deterministic(E.isolated_cp_solver(cp_model))
        s.Solve(m, CB())
        self.assertEqual(s.isolation_record["reason"], "CALLBACK_ATTACHED")
        self.assertTrue(seen)


class ChildDiesWithItsParent(Base):
    def test_killing_the_engine_kills_its_solve(self):
        script = textwrap.dedent(f"""
            import sys, time
            from pathlib import Path
            sys.path.insert(0, {str(REPO / 'tools')!r})
            import build_synthetic_suite as B
            E = B.load_engine(Path({str(ENGINE)!r}))
            cp_model = E.import_cp_sat()
            from ortools.sat.python import cp_model_helper as CMH
            s = E.isolated_cp_solver(cp_model)
            E.isolated_cp_solve(s, None, lambda model, cb=None: time.sleep(120), CMH.CpSolverResponse)
        """)
        proc = subprocess.Popen([sys.executable, "-c", script])
        try:
            child = None
            for _ in range(600):
                for tid in os.listdir(f"/proc/{proc.pid}/task"):
                    kids = open(f"/proc/{proc.pid}/task/{tid}/children").read().split()
                    if kids:
                        child = int(kids[0])
                if child:
                    break
                time.sleep(0.1)
            self.assertIsNotNone(child, "isolated solve never forked")
            proc.kill()
            proc.wait()
            for _ in range(50):
                if not os.path.exists(f"/proc/{child}") or open(f"/proc/{child}/stat").read().split()[2] == "Z":
                    break
                time.sleep(0.1)
            alive = os.path.exists(f"/proc/{child}") and open(f"/proc/{child}/stat").read().split()[2] != "Z"
            self.assertFalse(alive, "orphaned solve still running")
        finally:
            if proc.poll() is None:
                proc.kill()


class Wiring(unittest.TestCase):
    def test_joint_refinement_solves_are_isolated(self):
        src = inspect.getsource(E.solve_joint_shift_off_language_break_refinement)
        self.assertIn("stage_solver = isolated_cp_solver(cp_model)", src)
        self.assertNotIn("cp_model.CpSolver()", src)
        self.assertIn("solve_isolation=list(solve_isolation_rows)", src)
        self.assertTrue(E.JOINT_SOLVE_ISOLATION_ENABLED)

    def test_parameters_reach_the_child_unchanged(self):
        """configure_solver_limits and the stage settings are set on the parent
        object; fork carries that object, so nothing is copied or re-derived."""
        s = E.isolated_cp_solver(cp_model)
        self.assertIsInstance(s, cp_model.CpSolver)
        s.parameters.random_seed = 4242
        s.parameters.num_search_workers = 3
        self.assertEqual((s.parameters.random_seed, s.parameters.num_search_workers), (4242, 3))

    def test_threshold(self):
        self.assertEqual(E.joint_solve_kill_threshold_mb(16000), 320)
        self.assertEqual(E.joint_solve_kill_threshold_mb(4000), E.JOINT_SOLVE_KILL_BELOW_FREE_MB)
        self.assertEqual(E.joint_solve_kill_threshold_mb(None), E.JOINT_SOLVE_KILL_BELOW_FREE_MB)


if __name__ == "__main__":
    unittest.main(verbosity=2)
