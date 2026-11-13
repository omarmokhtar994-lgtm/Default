#!/usr/bin/env python3
"""Guards for the regression-lab harnesses under engine/regression_assets.

These harnesses are the project's own regression gates, and all of them shared
the failure mode this audit keeps finding: they could report success having
verified nothing.  Two also could not run at all, because they resolved the
engine against the regression-ASSETS root instead of the engine root.

Run:  python tests/test_rc9_2_1_regression_lab_integrity.py
"""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "engine" / "regression_assets" / "regression_lab"
FAST70 = LAB / "run_fast70_migrated.py"
VERIFY = LAB / "verify_phase_a_closure.py"
MICRO = LAB / "run_phase_b_micro.py"
CATALOG = LAB / "FAST70_MIGRATION_CATALOG.json"
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class HarnessesResolveTheEngineThatActuallyExists(unittest.TestCase):
    """ROOT was parents[1] - engine/regression_assets - for both harnesses.

    ENGINE_PATH therefore pointed at engine/regression_assets/_tools/, which has
    never existed, and both died on FileNotFoundError before running anything.
    """

    def test_the_engine_is_where_the_tests_say_it_is(self):
        self.assertTrue(ENGINE.exists(), "the engine must exist for this to mean anything")

    def test_fast70_resolves_the_real_engine(self):
        module = load("fast70_paths", FAST70)
        self.assertEqual(module.ENGINE_PATH.resolve(), ENGINE.resolve())
        self.assertTrue(module.ENGINE_PATH.exists())

    def test_phase_b_micro_resolves_the_real_engine(self):
        module = load("micro_paths", MICRO)
        self.assertEqual(module.ENGINE_PATH.resolve(), ENGINE.resolve())
        self.assertTrue(module.ENGINE_PATH.exists())

    def test_fast70_keeps_finding_its_own_catalog(self):
        module = load("fast70_catalog", FAST70)
        self.assertTrue(module.CATALOG.exists(),
                        "the assets root must still resolve for asset lookups")

    def test_phase_b_micro_keeps_finding_fast70(self):
        module = load("micro_fast70", MICRO)
        self.assertTrue(module.FAST70.exists())


class Fast70CannotReportSuccessHavingRunNothing(unittest.TestCase):
    """`assert len(data)==70` is stripped by `python -O`.

    With the catalog cut from 70 scenarios to 3, `-O` printed passed 0 /
    failed 0 and exited 0.  Every check here runs under -O for that reason.
    """

    def _run(self, args, catalog=None):
        with tempfile.TemporaryDirectory() as tmp:
            lab = Path(tmp) / "regression_lab"
            shutil.copytree(LAB, lab)
            if catalog is not None:
                (lab / "FAST70_MIGRATION_CATALOG.json").write_text(
                    json.dumps(catalog), encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-O", str(lab / "run_fast70_migrated.py"),
                 "--output-dir", str(Path(tmp) / "out"), *args],
                capture_output=True, text=True, timeout=600)

    def _catalog(self):
        return json.loads(CATALOG.read_text(encoding="utf-8"))

    def test_the_shipped_catalog_still_holds_seventy_scenarios(self):
        catalog = self._catalog()
        self.assertEqual(len(catalog), 70)
        self.assertEqual(len({row["id"] for row in catalog}), 70)

    def test_a_truncated_catalog_fails_under_optimised_mode(self):
        result = self._run(["--only-ids", "T42"], catalog=self._catalog()[:3])
        self.assertEqual(result.returncode, 2)
        self.assertIn("CATALOG INTEGRITY FAILURE", result.stderr)

    def test_a_duplicated_id_is_caught(self):
        catalog = self._catalog()
        catalog[1] = copy.deepcopy(catalog[0])
        result = self._run(["--only-ids", "T42"], catalog=catalog)
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate", result.stderr)

    def test_a_missing_category_is_caught(self):
        catalog = [row for row in self._catalog() if row.get("category") != "language"]
        while len(catalog) < 70:
            extra = copy.deepcopy(catalog[0])
            extra["id"] = f"PAD{len(catalog)}"
            catalog.append(extra)
        result = self._run(["--only-ids", "T42"], catalog=catalog[:70])
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing required categories", result.stderr)

    def test_selecting_no_scenarios_is_not_success(self):
        result = self._run(["--only-ids", "NO_SUCH_SCENARIO"])
        self.assertEqual(result.returncode, 2)

    def test_an_intact_catalog_still_runs(self):
        """Run the harness where it lives.

        The mutation cases above use a temp copy, which is fine because the
        catalog checks run before the engine is loaded. A full run needs the
        engine, and the harness resolves it relative to its own location, so
        this one stays in place and only redirects the output.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-O", str(FAST70), "--only-ids", "T42",
                 "--output-dir", str(Path(tmp) / "out")],
                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertIn('"selected": 1', result.stdout)


class PhaseAClosureVerifierCannotPassVacuously(unittest.TestCase):
    """Its entire verification was bare asserts."""

    def setUp(self):
        self.module = load("verify_phase_a", VERIFY)
        self.evidence = {
            "status": self.module.EXPECTED_STATUS, "release": "R", "engine_sha256": "abc",
            "gates": [
                {"gate": "MIGRATED_FAST70_FRESH_SOLVER", "passed": 70},
                {"gate": "THIN_OVERNIGHT_BREAK_RESILIENCE", "no_break_exceptions": 0},
                {"gate": "FIXED_FLEXIBLE_AND_HARD_FLOOR", "probe_status": "OPTIMAL"},
                {"gate": "FEASIBLE_11H_3OFF_MICRO_T42", "break_status": "FEASIBLE"},
                {"gate": "FEASIBLE_DIRECTIONAL_SKILL_MICRO_T44", "language_gap_count": 0},
                {"gate": "GDI_HISTORICAL_DIRECTIONAL_SKILL_GUARD",
                 "classification": "EXPECTED_GUARDED_REJECTION_DIAGNOSTIC"},
                {"gate": "11H_SKILL_REDUNDANCY_GUARD", "exception_lower_bound": 12},
            ]}

    def test_intact_evidence_verifies(self):
        self.assertEqual(self.module.verify(self.evidence), [])

    def test_a_degraded_pass_count_is_caught(self):
        bad = copy.deepcopy(self.evidence)
        bad["gates"][0]["passed"] = 69
        self.assertTrue(self.module.verify(bad))

    def test_an_absent_field_is_not_a_satisfied_one(self):
        bad = copy.deepcopy(self.evidence)
        del bad["gates"][1]["no_break_exceptions"]
        failures = self.module.verify(bad)
        self.assertTrue(failures)
        self.assertIn("cannot confirm", failures[0])

    def test_a_missing_gate_is_caught(self):
        bad = copy.deepcopy(self.evidence)
        bad["gates"] = bad["gates"][:2]
        self.assertEqual(len(self.module.verify(bad)), 5)

    def test_a_wrong_checkpoint_status_is_caught(self):
        bad = copy.deepcopy(self.evidence)
        bad["status"] = "SOMETHING_ELSE"
        self.assertTrue(self.module.verify(bad))

    def test_no_bare_assert_carries_a_check(self):
        """Parse it, do not grep it.

        A line-prefix scan also matches prose in the docstring that explains
        the fix, which is how this test first failed against correct code.
        """
        import ast
        tree = ast.parse(VERIFY.read_text(encoding="utf-8"))
        asserts = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)]
        self.assertEqual(asserts, [], "`python -O` strips assert; these verify nothing under -O")

    def test_missing_evidence_is_distinct_from_a_verification_failure(self):
        result = subprocess.run([sys.executable, "-O", str(VERIFY)],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 3,
                         "absent frozen evidence must not read as a failed check "
                         "or as a pass")
        self.assertIn("Do not regenerate", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
