#!/usr/bin/env python3
"""Guards for Phase C reporting and delivery packaging.

Same theme throughout: an absent result was being published as a passing one,
and an incomplete case was being packaged as a complete delivery.

Run:  python tests/test_rc9_2_1_phase_c_integrity.py
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_PATH = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
PHASE_C_REPORT = ROOT / "engine" / "production" / "phase_c_quality_report.py"
PACKAGE_A = ROOT / "engine" / "production" / "package_phase_a_outputs.py"
PACKAGE_C = ROOT / "engine" / "production" / "package_phase_c_outputs.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLEAN_METRICS = {"active_intervals": 100, "after_target": 100,
                 "after_floor": 100, "after_100": 100}


class SafetyStatusRequiresAnActualValidation(unittest.TestCase):
    """`hard_failures` defaulted to 0 when no count existed anywhere.

    A run whose output validation never executed therefore reported safety
    PASS and could reach phase_c_quality_status = PASS_CLEAN, while the
    report's own interpretation text claims the quality gate is authoritative.
    """

    def setUp(self):
        self.report = load("phase_c_quality_report", PHASE_C_REPORT)

    def _build(self, **candidate):
        selected = {"metrics": dict(CLEAN_METRICS)}
        selected.update(candidate)
        return self.report.build_report({"selected_candidate": selected})

    def test_no_validation_anywhere_is_not_a_safety_pass(self):
        result = self._build()
        self.assertEqual(result["safety"]["status"], "NOT_VALIDATED")
        self.assertFalse(result["safety"]["hard_fail_count_reported"])

    def test_no_validation_cannot_reach_pass_clean(self):
        self.assertEqual(self._build()["phase_c_quality_status"], "REVIEW_NOT_VALIDATED")

    def test_a_reported_zero_is_a_genuine_pass(self):
        result = self._build(output_validation={"validation": {"hard_fail_count": 0}})
        self.assertEqual(result["safety"]["status"], "PASS")
        self.assertTrue(result["safety"]["hard_fail_count_reported"])
        self.assertEqual(result["phase_c_quality_status"], "PASS_CLEAN")

    def test_reported_failures_still_fail(self):
        result = self._build(output_validation={"validation": {"hard_fail_count": 3}})
        self.assertEqual(result["safety"]["status"], "FAIL")
        self.assertEqual(result["phase_c_quality_status"], "FAIL_SAFETY")

    def test_an_audit_level_count_counts_as_reported(self):
        result = self.report.build_report(
            {"selected_candidate": {"metrics": dict(CLEAN_METRICS)}, "hard_fail_count": 0})
        self.assertEqual(result["safety"]["status"], "PASS")

    def test_no_schedule_at_all_is_still_not_run(self):
        result = self.report.build_report({})
        self.assertEqual(result["safety"]["status"], "NOT_RUN")
        self.assertEqual(result["phase_c_quality_status"], "DIAGNOSTICS_ONLY")

    def test_a_failed_production_gate_still_wins(self):
        result = self.report.build_report({
            "selected_candidate": {"metrics": dict(CLEAN_METRICS)},
            "production_quality_gate": {"status": "FAIL"}})
        self.assertEqual(result["phase_c_quality_status"], "FAIL_PRODUCTION_QUALITY_GATE")

    def test_contract_warning_without_failures_is_not_a_blocking_release_error(self):
        """A disclosed parser warning must not suppress exact-output validation."""
        result = self.report.build_report({
            "selected_candidate": {"metrics": dict(CLEAN_METRICS)},
            "hard_fail_count": 0,
            "pre_solver_contract_validation": {
                "status": "WARN", "failures": [], "warnings": [{"code": "INFO"}]},
            "production_quality_gate": {"status": "WARN", "mode": "warn"},
            "artifact_state": "FINAL_VERIFIED",
        })
        self.assertEqual(result["safety"]["status"], "PASS")
        self.assertEqual(result["phase_c_quality_status"], "WARN_PRODUCTION_QUALITY_LIMITED")

    def test_independent_validation_overrides_engine_side_safety_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = Path(tmp)
            (case_root / "INDEPENDENT_VALIDATION.json").write_text(json.dumps({
                "status": "FAIL", "hard_fail_count": 2, "warning_count": 0}),
                encoding="utf-8")
            result = self.report.build_report({
                "selected_candidate": {
                    "metrics": dict(CLEAN_METRICS),
                    "output_validation": {"validation": {"hard_fail_count": 0}},
                },
                "artifact_state": "FINAL_VERIFIED",
            }, case_root)
            self.assertEqual(result["safety"]["status"], "FAIL")
            self.assertEqual(result["safety"]["validation_source"], "independent_validator")
            self.assertEqual(result["phase_c_quality_status"], "FAIL_SAFETY")


class ReportReleaseIsDerivedFromTheEngine(unittest.TestCase):
    """The module carried RELEASE = 'L6.3.2.3-RC9.0-...', two releases stale."""

    def setUp(self):
        self.report = load("phase_c_quality_report", PHASE_C_REPORT)

    def test_fallback_release_matches_the_engine_version(self):
        text = ENGINE_PATH.read_text(encoding="utf-8")
        version = re.search(r'^VERSION\s*=\s*["\'](.+?)["\']', text, re.MULTILINE).group(1)
        self.assertEqual(self.report.RELEASE, version)

    def test_the_stale_literal_is_no_longer_assigned_to_release(self):
        """The name may still appear in the comment explaining the fix.

        What must not come back is the assignment. Asserts on a bool so a
        failure prints one line, not the whole module.
        """
        compact = PHASE_C_REPORT.read_text(encoding="utf-8").replace(" ", "")
        self.assertFalse(
            'RELEASE="L6.3.2.3-RC9.0-UNIVERSAL-PRODUCTION-PLATFORM"' in compact,
            "RELEASE must be derived from the engine, not assigned a literal")
        self.assertTrue("RELEASE=_engine_release()" in compact)

    def test_the_audit_version_still_wins_over_the_fallback(self):
        result = self.report.build_report({"version": "SOME-OTHER-RELEASE"})
        self.assertEqual(result["release"], "SOME-OTHER-RELEASE")


class PackagersRefuseIncompleteCases(unittest.TestCase):
    """Neither packager may ship a delivery that has no schedule in it.

    Phase C checked required roles only AFTER writing all three ZIPs, so an
    incomplete case still produced a *_01_PRODUCTION_ONLY.zip - with no
    manifest to warn anything downstream that globs for it. Phase A had no
    check at all and wrote an empty archive reporting zip_test PASS.
    """

    def _run(self, module, root):
        return subprocess.run([sys.executable, str(module), "--case-root", str(root)],
                              capture_output=True, text=True, timeout=180)

    def _empty_case(self, tmp):
        root = Path(tmp) / "CASE"
        (root / "production").mkdir(parents=True)
        return root

    def test_phase_a_refuses_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._empty_case(tmp)
            result = self._run(PACKAGE_A, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(root.rglob("*.zip")), [],
                             "a refused case must leave no archive behind")

    def test_phase_c_refuses_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._empty_case(tmp)
            result = self._run(PACKAGE_C, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(root.rglob("*.zip")), [],
                             "the role check must run before any ZIP is written")
            self.assertIn("Missing required production artifact roles", result.stderr)

    def test_phase_c_writes_no_partial_package_when_one_role_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._empty_case(tmp)
            (root / "production" / "X_BEST_BEFORE_BREAKS_SCHEDULE.xlsx").write_bytes(b"x")
            result = self._run(PACKAGE_C, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(root.rglob("*.zip")), [])

    def test_a_complete_phase_c_case_still_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._empty_case(tmp)
            (root / "production" / "X_BEST_BEFORE_BREAKS_SCHEDULE.xlsx").write_bytes(b"x")
            final = root / "production" / "X_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"
            final.write_bytes(b"y")
            digest = hashlib.sha256(final.read_bytes()).hexdigest()
            snapshot = root / "input_snapshot" / "INPUT.xlsx"
            snapshot.parent.mkdir()
            snapshot.write_bytes(b"input")
            input_digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            engine_digest = "e" * 64
            (root / "INDEPENDENT_VALIDATION.json").write_text(json.dumps({
                "status":"PASS","hard_fail_count":0,"output_sha256":digest,
                "input_sha256":input_digest,"engine_sha256":engine_digest,
            }))
            (root / "INDEPENDENT_VALIDATION.csv").write_text("Metric,Value\nstatus,PASS\n")
            (root / "production" / "PRODUCTION_ARTIFACT_MANIFEST.json").write_text(json.dumps({
                "production_ready":True,
                "approval_status":"APPROVED_AUTOMATED_RELEASE_GATES",
                "solver":{"engine_sha256":engine_digest},
                "two_artifact_contract":{"BEST_FINAL_AFTER_BREAKS_SCHEDULE":{"path":str(final),"sha256":digest}},
            }))
            result = self._run(PACKAGE_C, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            produced = sorted(p.name for p in root.rglob("*.zip"))
            self.assertEqual(len(produced), 3)
            for component in ("01_PRODUCTION_ONLY", "02_REVIEW_EVIDENCE", "03_FULL_DEBUG"):
                with zipfile.ZipFile(root / "packages" / f"CASE_{component}.zip") as archive:
                    self.assertIn("COMPONENT_MANIFEST.json", archive.namelist())
                    component_manifest = json.loads(archive.read("COMPONENT_MANIFEST.json"))
                    self.assertEqual(component_manifest["component"], component)
                    self.assertEqual(component_manifest["package_set_id"],
                                     json.loads((root / "packages" / "PACKAGE_SPLIT_MANIFEST.json").read_text())["package_set_id"])

    def test_phase_a_is_disabled_even_for_a_complete_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._empty_case(tmp)
            (root / "production" / "X_BEST_BEFORE_BREAKS_SCHEDULE.xlsx").write_bytes(b"x")
            result = self._run(PACKAGE_A, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(list(root.rglob("*.zip"))), 0)
            self.assertIn("Phase A is disabled", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
