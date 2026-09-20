"""Joint refinement default: OFF at SMOKE/QUICK, ON at DEEP/OVERNIGHT.

The scope split is the point. Evidence covers QUICK budgets only, so the
untested long modes must keep the phase enabled.
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

    def test_on_at_untested_long_modes(self):
        """DEEP/OVERNIGHT allot 5400s/8400s and were never measured."""
        d = _mode_defaults()
        for mode in ("DEEP", "OVERNIGHT"):
            self.assertIsNot(
                d[mode].get("joint_enabled"), False,
                f"{mode} is untested; do not disable the phase there",
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
