"""Stage-1 profile rotation for seed portfolios (--stage1-profile-rotation i/n).

At 3,600 s Stage 1 funds 9-10 of 15 profiles, always the first ones, so every
seed of a portfolio explored the same skeletons. Seed i of n keeps the first
STAGE1_ROTATION_ANCHORS profiles and rotates the rest. Opt-in
(RUN_PORTFOLIO.py --diversify-profiles) until its registered A/B decides
(evidence/profile_diversity_ab/PREREGISTERED_RULE.txt).
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
spec = importlib.util.spec_from_file_location("portfolio_rotation", ROOT / "engine" / "RUN_PORTFOLIO.py")
PF = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PF)
NAMES = [f"p{i}" for i in range(15)]


class Rotation(unittest.TestCase):
    def test_seed_zero_and_single_runs_are_unchanged(self):
        self.assertEqual(E.rotate_stage1_profiles(NAMES, 0, 4), NAMES)
        self.assertEqual(E.rotate_stage1_profiles(NAMES, 0, 1), NAMES)
        self.assertEqual(E.STAGE1_PROFILE_ROTATION, (0, 1))

    def test_anchors_stay_first_and_every_profile_is_kept(self):
        k = E.STAGE1_ROTATION_ANCHORS
        for n in (2, 3, 4, 6):
            for i in range(n):
                order = E.rotate_stage1_profiles(NAMES, i, n)
                self.assertEqual(order[:k], NAMES[:k])
                self.assertEqual(sorted(order), sorted(NAMES))

    def test_two_seeds_cover_the_whole_tail_early(self):
        k = E.STAGE1_ROTATION_ANCHORS
        tail = NAMES[k:]
        first = E.rotate_stage1_profiles(NAMES, 0, 2)[k:k + 5]
        second = E.rotate_stage1_profiles(NAMES, 1, 2)[k:k + 5]
        self.assertEqual(set(first) | set(second), set(tail))

    def test_cli_sets_it_and_rejects_nonsense(self):
        parser = E.build_arg_parser()
        self.assertEqual(parser.parse_args(["--stage1-profile-rotation", "1/2", "--selfcheck"]).stage1_profile_rotation, "1/2")
        src = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(encoding="utf-8")
        self.assertIn("--stage1-profile-rotation expects i/n with 0 <= i < n", src)
        self.assertIn("rotate_stage1_profiles(skeleton_profile_names, *STAGE1_PROFILE_ROTATION)", src)


class PortfolioFlag(unittest.TestCase):
    def run_main(self, argv):
        calls = []

        def fake(seed, schedule_id, seeds_root, passthrough, log_dir):
            calls.append(list(passthrough))
            d = Path(seeds_root) / f"{schedule_id}_S{seed}"
            d.mkdir(parents=True)
            return d

        saved = PF.run_seed
        PF.run_seed = fake
        try:
            PF.main(argv + ["--output-root", tempfile.mkdtemp(), "--schedule-id", "C"])
        finally:
            PF.run_seed = saved
        return calls

    def test_off_by_default(self):
        for call in self.run_main(["--seeds", "2"]):
            self.assertNotIn("--stage1-profile-rotation", call)

    def test_each_seed_gets_its_index(self):
        calls = self.run_main(["--seeds", "3", "--diversify-profiles"])
        self.assertEqual([c[-1] for c in calls], ["0/3", "1/3", "2/3"])

    def test_an_explicit_profile_list_is_respected(self):
        for call in self.run_main(["--seeds", "2", "--diversify-profiles", "--skeleton-profiles", "a,b"]):
            self.assertNotIn("--stage1-profile-rotation", call)


class BreakLoadInput(unittest.TestCase):
    def test_stage1_break_load_is_optional_and_objective_only(self):
        import inspect
        sig = inspect.signature(E.build_skeleton)
        self.assertIsNone(sig.parameters["break_load_units"].default)
        src = inspect.getsource(E.build_skeleton)
        load = src.index("observed_break_load = int(")
        self.assertLess(src.index("model.Add(eff >= hard_floor_units)"), load)


if __name__ == "__main__":
    unittest.main(verbosity=2)
