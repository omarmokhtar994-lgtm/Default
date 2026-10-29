"""Joint refinement and its endgame are off by default at every depth.

evidence/JOINT_REFINEMENT_REMOVED.md: 474 solver audits on record, improved 0
in every one (the 28 "accepted" are replays of the anchor the phase started
from); 36 attempts in 4 DEEP runs, improved 0; two DEEP runs killed at 13.0 and
13.9 GB inside the phase. The no-candidate endgame ran 9 times and added 0
candidates each time. Both stay available behind explicit flags.
"""
import inspect
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
RUNNER_SRC = (ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py").read_text(encoding="utf-8")


class Endgame(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(E.FINAL_RECOVERY_ENDGAME_ENABLED)

    def test_the_loop_is_gated_by_it(self):
        src = inspect.getsource(E)
        loop = src.index("FINAL_RECOVERY_ENDGAME_ENABLED\n            and not (compliant or exceptions)")
        self.assertLess(loop, src.index("and endgame_round < 6"))
        self.assertIn('"DISABLED_NO_MEASURED_VALUE" if not FINAL_RECOVERY_ENDGAME_ENABLED', src)

    def test_the_flag_turns_it_back_on(self):
        args = E.build_arg_parser().parse_args(["--enable-final-recovery-endgame", "--selfcheck"])
        self.assertTrue(args.enable_final_recovery_endgame)
        self.assertIn("FINAL_RECOVERY_ENDGAME_ENABLED = True", inspect.getsource(E.main))
        self.assertIn("command.append('--enable-final-recovery-endgame')", RUNNER_SRC)


class JointRefinementEverywhere(unittest.TestCase):
    def test_runner_disables_it_at_every_depth_unless_forced(self):
        for mode in ("SMOKE", "QUICK", "DEEP", "OVERNIGHT"):
            self.assertRegex(RUNNER_SRC, rf"'{mode}': \{{[^}}]*'joint_enabled': False")
        self.assertIn("'--enable-joint-refinement'", RUNNER_SRC)

    def test_its_time_goes_to_the_other_phases(self):
        sys.path.insert(0, str(ROOT / "engine" / "_tools"))
        import phase_b_maturity as P
        kw = dict(allow_exceptions=False, coordinated_repair=True, target_lock_recovery=True)
        on = P.build_global_budget_plan(14400, joint_refinement=True, **kw)
        off = P.build_global_budget_plan(14400, joint_refinement=False, **kw)
        self.assertEqual(off["joint_refinement"], 0)
        self.assertEqual(sum(off.values()), 14400)
        self.assertGreater(off["stage1_search"] + off["break_search"], on["stage1_search"] + on["break_search"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
