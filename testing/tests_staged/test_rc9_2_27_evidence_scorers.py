"""The published A/B verdicts recompute from shipped evidence, and fail closed.

F-11: the evidence behind each verdict lived only in a scratch directory, so
nobody else could recompute a score. evidence/raw_runs now holds each run's
summary, validation, run status/identity and a solver-audit extract.
F-19: the scorers treated a missing run as 0; on an empty directory
score_deep.py printed "adopt E" and exited 0. They now abort with exit 2.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "evidence"
SCORERS = {
    "break_load_feedback_ab": ("score.py", "H1_FBL_9001"),
    "profile_diversity_ab": ("score.py", "AR_ROT_9001"),
    "seed_portfolio_ab": ("score_deep.py", "CHAT_DEEP_9000"),
}


def score(ab: str, raw_root: Path = None):
    env = dict(os.environ)
    if raw_root is not None:
        env["RAW_RUNS_ROOT"] = str(raw_root)
    script = EVIDENCE / ab / SCORERS[ab][0]
    return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env, timeout=300)


class PublishedVerdictsRecompute(unittest.TestCase):
    def test_every_scorer_prints_the_published_verdict(self):
        for ab in SCORERS:
            with self.subTest(ab=ab):
                proc = score(ab)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                published = [l for l in (EVIDENCE / ab / "RESULT.txt").read_text().splitlines()
                             if re.match(r"^(DEEP )?VERDICT:", l)]
                printed = [l for l in proc.stdout.splitlines() if re.match(r"^(DEEP )?VERDICT:", l)]
                self.assertTrue(published)
                self.assertEqual(printed, published)


class ScorersFailClosed(unittest.TestCase):
    def test_a_missing_run_aborts_without_a_verdict(self):
        for ab, (_, victim) in SCORERS.items():
            with self.subTest(ab=ab), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "raw_runs"
                shutil.copytree(EVIDENCE / "raw_runs", root, ignore=shutil.ignore_patterns("*.py", "__pycache__"))
                shutil.rmtree(root / ab / victim)
                proc = score(ab, root)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertNotIn("VERDICT", proc.stdout)
                self.assertIn(victim, proc.stderr)

    def test_an_empty_tree_aborts(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = score("seed_portfolio_ab", Path(tmp))
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("adopt", proc.stdout)

    def test_the_independent_rescorer_needs_the_full_set(self):
        script = EVIDENCE / "independent_audit_2026_09_28" / "indep_score.py"
        root = EVIDENCE / "raw_runs" / "dnbs_e2e_3600b"
        ok = subprocess.run([sys.executable, str(script), str(root), "CUR,NEW", "9000,9001"],
                            capture_output=True, text=True, timeout=300)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("SUM {'CUR': 1057.5, 'NEW': 1058.0}", ok.stdout)
        short = subprocess.run([sys.executable, str(script), str(root), "CUR,NEW", "9000,9001,9002"],
                               capture_output=True, text=True, timeout=300)
        self.assertEqual(short.returncode, 2)
        self.assertNotIn("SUM", short.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
