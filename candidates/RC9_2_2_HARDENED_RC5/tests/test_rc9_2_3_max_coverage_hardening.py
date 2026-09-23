#!/usr/bin/env python3
"""Regression guards for the RC5 execution-path fixes.

These tests are intentionally solver-free. They pin the release state machine,
canonical metric surface, and coverage-first policy that can otherwise regress
without exercising an expensive CP-SAT run.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
RUNNER = ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"
REPORTER = ROOT / "engine" / "production" / "phase_c_quality_report.py"
PACKAGER = ROOT / "engine" / "production" / "package_phase_c_outputs.py"
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

from canonical_metrics import canonicalize_metrics, compare_metric_surfaces  # noqa: E402
import l632_universal_scheduler as E  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CanonicalMetricSurface(unittest.TestCase):
    def test_compact_engine_surface_keeps_gap_and_blank_scalars(self):
        compact = E.compact_metric_surface({
            "floor_gap_count": 3,
            "max_consecutive_floor_gaps": 2,
            "blank_staffed_quarters": 4,
            "interval_rows": [{"interval": "00:00"}],
            "zero_qslots": [1, 2],
        })
        self.assertEqual(compact["floor_gap_count"], 3)
        self.assertEqual(compact["max_consecutive_floor_gaps"], 2)
        self.assertEqual(compact["blank_staffed_quarters"], 4)
        self.assertNotIn("interval_rows", compact)
        self.assertNotIn("zero_qslots", compact)

    def test_engine_and_validator_aliases_compare_equal(self):
        engine = {
            "active_intervals": 10, "before_100": 8, "before_90": 9,
            "before_80": 10, "after_100": 7, "after_90": 8,
            "after_80": 9, "before_target": 9, "after_target": 8,
            "before_floor": 10, "after_floor": 9, "floor_gap_count": 1,
            "severe_floor_gap_count": 0, "max_consecutive_floor_gaps": 1,
            "zero_staffed_active_quarters": 0, "language_gap_count": 0,
            "opening_gap_count": 0, "blank_staffed_quarters": 0,
            "break_concurrency_violation_count": 0,
            "whole_week_overage_cap_violation_count": 0,
            "whole_week_imbalance_violation_count": 0,
            "max_concurrent_breaks_observed": 2,
            "max_concurrent_break_ratio_observed": 0.5,
            "after_avoidable_overage_fte_sum": 1.25,
            "after_avoidable_overage_interval_count": 2,
            "after_severe_overage_count": 1,
            "after_extreme_overage_count": 0,
            "after_avoidable_overage_peak_fte": 1.5,
            "after_avoidable_overage_variance_fte": 0.25,
            "after_avoidable_overage_stddev_fte": 0.5,
            "after_overage_top10_concentration": 0.75,
            "after_max_consecutive_avoidable_overage_intervals": 2,
            "week_boundary_after_target": 3,
            "week_boundary_after_floor": 4,
            "week_boundary_floor_gap_count": 1,
            "week_boundary_zero_staffed_active_quarters": 0,
            "week_boundary_language_gap_count": 0,
            "week_boundary_opening_gap_count": 0,
            "week_boundary_blank_staffed_quarters": 0,
            "week_boundary_overage_cap_violation_count": 0,
            "week_boundary_imbalance_violation_count": 0,
            # B-9: the seven newly compared fields, engine spellings
            "target_losses_from_breaks": 2,
            "floor_losses_from_breaks": 1,
            "before_severe_floor_gap_count": 0,
            "hard_floor_gap_count": 0,
            "week_boundary_hard_failure_count": 1,
            "week_boundary_max_adjacent_raw_change": 2,
            "week_boundary_max_coverage_ratio": 1.25,
        }
        validator = {"active_intervals": 10, "before100": 8, "before90": 9,
                     "before80": 10, "after100": 7, "after90": 8,
                     "after80": 9, "before_target": 9, "after_target": 8,
                     "before_floor": 10, "after_floor": 9, "floor_gaps": 1,
                     "severe_floor_gaps": 0, "max_consecutive_floor_gaps": 1,
                     "zero_staffed_active_quarters": 0, "language_gap_count": 0,
                     "opening_gap_count": 0, "blank_staffed_quarters": 0,
                     "break_concurrency_violation_count": 0,
                     "whole_week_overage_cap_violation_count": 0,
                     "whole_week_imbalance_violation_count": 0,
                     "max_concurrent_breaks_observed": 2,
                     "max_concurrent_break_ratio_observed": 0.5,
                     "avoidable_overage_fte_sum": 1.25,
                     "avoidable_overage_positive_interval_count": 2,
                     "severe_overage_interval_count": 1,
                     "extreme_overage_interval_count": 0,
                     "avoidable_overage_peak_fte": 1.5,
                     "avoidable_overage_variance_fte": 0.25,
                     "avoidable_overage_stddev_fte": 0.5,
                     "avoidable_overage_top10_concentration": 0.75,
                     "avoidable_overage_max_consecutive_intervals": 2,
                     "next_sunday_target_hits": 3,
                     "next_sunday_floor_hits": 4,
                     "next_sunday_floor_gap_count": 1,
                     "next_sunday_zero_staffed_quarters": 0,
                     "next_sunday_language_gap_count": 0,
                     "next_sunday_opening_gap_count": 0,
                     "next_sunday_blank_staffed_quarters": 0,
                     "next_sunday_overage_cap_violation_count": 0,
                     "next_sunday_imbalance_violation_count": 0,
                     # B-9: the same seven, validator spellings
                     "target_losses_from_breaks": 2,
                     "floor_losses_from_breaks": 1,
                     "before_severe_floor_gap_count": 0,
                     "hard_floor_gap_count": 0,
                     "next_sunday_hard_failure_count": 1,
                     "next_sunday_max_adjacent_raw_change": 2,
                     "next_sunday_max_coverage_ratio": 1.25}
        result = compare_metric_surfaces(engine, validator)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["mismatch_count"], 0)

    def test_missing_or_changed_metric_is_a_release_failure(self):
        result = compare_metric_surfaces(
            {"active_intervals": 1}, {"active_intervals": 2})
        self.assertEqual(result["status"], "FAIL")
        self.assertGreater(result["mismatch_count"], 0)


class CoverageFirstSolverPolicy(unittest.TestCase):
    def test_quality_mode_does_not_change_primary_target_order(self):
        for ratio, first in ((0.80, "target_priority"), (0.90, "target_priority"), (1.00, "target_100")):
            with self.subTest(ratio=ratio):
                common = SimpleNamespace(target_ratio=ratio, quality_gate_mode="warn")
                fail = SimpleNamespace(target_ratio=ratio, quality_gate_mode="fail")
                self.assertEqual(E.default_break_objective_modes(common)[0], first)
                self.assertEqual(E.default_break_objective_modes(fail)[0], first)

    def test_joint_quality_blend_was_removed(self):
        source = ENGINE.read_text(encoding="utf-8")
        self.assertNotIn("MAXIMIZE_RELEASE_QUALITY_SCORE", source)
        self.assertNotIn(
            'quality_gate_mode", "warn") == "fail" and floor_hits', source)

    def test_search_audit_never_claims_global_maximum(self):
        source = ENGINE.read_text(encoding="utf-8")
        self.assertIn('"global_coverage_maximum_proven": False', source)
        self.assertIn('"SEARCH_TRUNCATED_GLOBAL_MAXIMUM_NOT_PROVEN"', source)

    def test_stage2_does_not_shrink_the_stage1_retention_cap(self):
        source = ENGINE.read_text(encoding="utf-8")
        self.assertIn(
            "retained_top = successful_skeletons[:MAX_RETAINED_STAGE1_SKELETONS]",
            source,
        )


class ReleasePathFixes(unittest.TestCase):
    def test_validator_separates_quality_gate_debt_from_hard_failures(self):
        source = (ROOT / "engine" / "tools" / "independent_validator.py").read_text(encoding="utf-8")
        self.assertIn("quality_gate_failures", source)
        self.assertIn("quality_gate_suppressed", source)
        self.assertIn('"quality_gate_status":quality_gate_status', source)

    def test_quality_failed_engine_result_is_allowed_to_reach_polisher(self):
        source = RUNNER.read_text(encoding="utf-8")
        branch = source[source.index("validation_workbook = None"):source.index("if validation_workbook is not None")]
        self.assertIn("engine_rc == 0 or quality_pending_validation", branch)

    def test_external_metric_parity_failure_is_not_safety_pass(self):
        reporter = load("rc5_phase_report", REPORTER)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "INDEPENDENT_VALIDATION.json").write_text(json.dumps({
                "status": "FAIL_METRIC_PARITY", "hard_fail_count": 0,
            }), encoding="utf-8")
            result = reporter.build_report({
                "selected_candidate": {
                    "metrics": {"active_intervals": 1, "after_target": 1}
                }
            }, root)
            self.assertIn(result["safety"]["status"], {"FAIL", "ERROR"})

    def test_hard_gate_seal_with_quality_debt_can_be_packaged_as_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "CASE"
            production = root / "production"
            production.mkdir(parents=True)
            (production / "X_BEST_BEFORE_BREAKS_SCHEDULE.xlsx").write_bytes(b"before")
            final = production / "X_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"
            final.write_bytes(b"final")
            final_hash = hashlib.sha256(final.read_bytes()).hexdigest()
            snapshot = root / "input_snapshot" / "INPUT.xlsx"
            snapshot.parent.mkdir()
            snapshot.write_bytes(b"input")
            input_hash = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            engine_hash = "e" * 64
            (root / "INDEPENDENT_VALIDATION.json").write_text(json.dumps({
                "status": "PASS", "hard_fail_count": 0,
                "output_sha256": final_hash, "input_sha256": input_hash,
                "engine_sha256": engine_hash,
            }), encoding="utf-8")
            (production / "PRODUCTION_ARTIFACT_MANIFEST.json").write_text(json.dumps({
                "automated_hard_gates_passed": True,
                "production_ready": False,
                "approval_status": "AUTOMATED_HARD_GATES_PASSED_PENDING_HUMAN_APPROVAL",
                "quality_gate_status": "FAIL",
                "solver": {"engine_sha256": engine_hash},
                "two_artifact_contract": {
                    "BEST_FINAL_AFTER_BREAKS_SCHEDULE": {
                        "path": str(final), "sha256": final_hash
                    }
                },
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PACKAGER), "--case-root", str(root)],
                capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((root / "packages" / "PACKAGE_SPLIT_MANIFEST.json").read_text())
            codes = {warning["code"] for warning in manifest["warnings"]}
            self.assertIn("AUTOMATED_HARD_GATES_PASSED_HUMAN_APPROVAL_PENDING", codes)
            self.assertIn("PRODUCTION_QUALITY_GATE_BLOCKED", codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
