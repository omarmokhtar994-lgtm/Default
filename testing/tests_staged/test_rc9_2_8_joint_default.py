"""Joint refinement default: OFF at every depth.

History: this suite first pinned OFF at SMOKE/QUICK and ON at DEEP/OVERNIGHT,
because the evidence then covered QUICK budgets only and the long modes were
untested. They have been measured since (evidence/JOINT_REFINEMENT_REMOVED.md):
36 attempts in 4 DEEP runs with improved 0, two DEEP runs killed at 13.0 and
13.9 GB inside the phase, and improved 0 in all 474 solver audits on record.
The long modes now default it off too; --enable-joint-refinement remains.
"""
import ast
import os
import re
import unittest

RUNNER = os.environ.get(
    "RC9_RUNNER",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "RUN_UNIVERSAL_PRODUCTION.py"),
)
SRC = open(os.path.abspath(RUNNER)).read()


def _mode_defaults():
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "all_mode_defaults" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("all_mode_defaults not found")


class JointDefaultTest(unittest.TestCase):

    def test_off_at_short_modes(self):
        d = _mode_defaults()
        for mode in ("SMOKE", "QUICK"):
            self.assertIs(
                d[mode].get("joint_enabled"), False,
                f"{mode} must default joint refinement off: 69 attempts, 0 improvements",
            )

    def test_off_at_long_modes_now_that_they_are_measured(self):
        """DEEP/OVERNIGHT: measured, improved 0, and the phase caused the kills."""
        d = _mode_defaults()
        for mode in ("DEEP", "OVERNIGHT"):
            self.assertIs(
                d[mode].get("joint_enabled"), False,
                f"{mode}: 36 DEEP attempts improved nothing and two runs died in the phase",
            )

    def test_the_disable_flag_is_actually_emitted(self):
        """Non-vacuity: the default must reach the engine command line.

        --joint-refinement-reserve-sec 0 does NOT disable the phase (measured:
        it only shrinks the allocation), so the command must carry
        --disable-joint-refinement.
        """
        self.assertIn("command.append('--disable-joint-refinement')", SRC)
        self.assertRegex(
            SRC,
            r"if not mode_defaults\.get\('joint_enabled', True\)\s+and not args\.enable_joint_refinement",
            "the emit must be guarded by both the mode default and the override",
        )

    def test_escape_hatch_exists(self):
        self.assertIn("'--enable-joint-refinement'", SRC)

    def test_reserve_zero_is_not_used_as_the_switch(self):
        """Guard the measured fact that reserve=0 leaves the phase running."""
        d = _mode_defaults()
        for mode in ("SMOKE", "QUICK"):
            self.assertGreater(
                d[mode]["joint"], 0,
                "reserve must not be repurposed as an off switch; it does not disable the phase",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
