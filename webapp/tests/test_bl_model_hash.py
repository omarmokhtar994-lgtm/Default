# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL audit (2026-11-08): with the new Schedule columns blank or absent, the Stage 1 model the engine builds is the model it built before Phase BL.

The SHA-256 of the CP-SAT model (seed 9000, default hard rules, solve stopped before it starts, so no timing) of the three protected baseline workbooks
was measured on the engine at 40aec97 (before Phase BL) and on this one: identical for all of them, and for all 85 workbooks in the repository that
are scheduler inputs (evidence/phase_bl/stage1_hash_all.md). Pinned here so a later change that alters the model of an existing workbook fails by name.
The hash is of OR-Tools' text form of the model, so it is pinned to the OR-Tools version it was measured with; on another version the test is skipped
with that reason, and the pins are re-measured (old engine and new engine side by side) before they are changed."""
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "tools" / "stage1_model_hash.py"        # ships with the package; evidence/phase_bl/ab_model_hash.py is the same file
INPUTS = next(p for p in (REPO / "inputs", REPO / "packages" / "rc9_2_2_production" / "inputs") if p.exists())   # the package, or the repository
ORTOOLS = "9.15.6755"
PINS = {  # workbook: (associates, shifts, hash), measured at 40aec97 and at Phase BL
    "AE_AR_B2B.xlsx": ("35", "24", "06b3708c287df3c5f4c64cebe3b633778f487a168435c7c573b51c2902078b8d"),
    "Cricut_Voice_RC9_1_READY_SKELETON.xlsx": ("33", "24", "8633584433b4890c03a71cebf1b2dc6a1238c983d8741515f54fb188d1963f45"),
    "NMG_SP_RC9_1_READY_FIXED.xlsx": ("7", "1", "72ce8e92200ea81b17613c49ed4e4fcc0a9067c6487ad606657c1680d64125ce"),
}


class TheStageOneModelIsTheOldOne(unittest.TestCase):
    def test_the_protected_baselines_build_the_model_they_always_did(self):
        import ortools
        if ortools.__version__ != ORTOOLS:
            self.skipTest(f"pins measured with OR-Tools {ORTOOLS}, this is {ortools.__version__}: re-measure old and new engine before re-pinning")
        for name, expected in PINS.items():
            with self.subTest(workbook=name):
                out = subprocess.run([sys.executable, str(HELPER), str(REPO / "engine" / "_tools"), str(INPUTS / name)],
                                     capture_output=True, text=True, timeout=280, cwd=REPO)
                self.assertEqual(out.returncode, 0, out.stderr[-500:])
                self.assertEqual(tuple(out.stdout.strip().splitlines()[-1].split("\t")[1:]), expected)


if __name__ == "__main__":
    unittest.main()
