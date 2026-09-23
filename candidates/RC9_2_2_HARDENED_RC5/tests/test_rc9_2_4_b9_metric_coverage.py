#!/usr/bin/env python3
"""B-9: six decision-driving metrics get an independent check.

Each field pinned here is read by a release gate or by candidate selection.
Until B-9 only the engine computed them, so the parity gate had nothing to
compare against: an engine-side error in any of them was undetectable by
construction, because no second derivation of the number existed.

The fix makes the independent validator derive all six from the workbook cells
it already parses, and puts them on the canonical surface so a disagreement
becomes a gate failure.  These tests are written from both sides -- the gate
must report a disagreement AND must not report a false one -- and the last two
check the derivations against real recorded artifacts rather than only against
synthetic surfaces.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
VALIDATOR = ROOT / "engine" / "tools" / "independent_validator.py"
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

import canonical_metrics as CM  # noqa: E402

B9_FIELDS = (
    "target_losses_from_breaks",
    "floor_losses_from_breaks",
    "before_severe_floor_gap_count",
    "hard_floor_gap_count",
    "week_boundary_hard_failure_count",
    "week_boundary_max_adjacent_raw_change",
    "week_boundary_max_coverage_ratio",
)

# The validator publishes next_sunday_* where the engine publishes
# week_boundary_*.  Both spellings must land on the same canonical field, or
# the two surfaces would fail to line up and every run would report a
# mismatch that is really just a vocabulary difference.
VALIDATOR_SPELLING = {
    "week_boundary_hard_failure_count": "next_sunday_hard_failure_count",
    "week_boundary_max_adjacent_raw_change": "next_sunday_max_adjacent_raw_change",
    "week_boundary_max_coverage_ratio": "next_sunday_max_coverage_ratio",
}

# Where the two sides use the same word, the validator's own metrics key.
SAME_SPELLING = tuple(f for f in B9_FIELDS if f not in VALIDATOR_SPELLING)


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def surface(source, **values):
    """The canonical surface is flat: canonical field names at the top level."""
    return CM.canonicalize_metrics(dict(values), source, stage=CM.STAGE_FULL_SCHEDULE)


def compare(engine_raw, validator_raw):
    """compare_metric_surfaces canonicalizes its own arguments, so these are
    raw source-spelled dicts, not already-canonical surfaces."""
    return CM.compare_metric_surfaces(
        engine_raw, validator_raw,
        engine_stage=CM.STAGE_FULL_SCHEDULE,
        validator_stage=CM.STAGE_FULL_SCHEDULE)


class CanonicalSurface(unittest.TestCase):
    def test_every_b9_field_is_compared(self):
        for field in B9_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, CM.PARITY_FIELDS)

    def test_b9_added_exactly_seven_fields(self):
        """Pinned so a later edit cannot quietly drop one back off the gate."""
        self.assertEqual(len(CM.PARITY_FIELDS), 48)
        self.assertEqual(len(set(B9_FIELDS) & set(CM.PARITY_FIELDS)), 7)

    def test_engine_spelling_resolves(self):
        for field in B9_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(surface("engine", **{field: 3})[field], 3)

    def test_validator_spelling_resolves_to_the_same_field(self):
        for engine_name, validator_name in sorted(VALIDATOR_SPELLING.items()):
            with self.subTest(field=engine_name):
                self.assertIn(validator_name, CM.ALIASES[engine_name])
                got = surface("independent_validator", **{validator_name: 7})
                self.assertEqual(got[engine_name], 7)

    def test_max_coverage_ratio_is_not_compared_as_an_integer(self):
        """It is a ratio.  Rounding it to an int would hide every real drift."""
        self.assertNotIn("week_boundary_max_coverage_ratio", CM.INTEGER_FIELDS)
        got = surface("engine", week_boundary_max_coverage_ratio=1.375)
        self.assertAlmostEqual(
            got["week_boundary_max_coverage_ratio"], 1.375, places=6)


class ParityGate(unittest.TestCase):
    def test_disagreement_is_reported(self):
        for field in B9_FIELDS:
            with self.subTest(field=field):
                report = compare({field: 4}, {VALIDATOR_SPELLING.get(field, field): 9})
                self.assertNotEqual(report["status"], "PASS")
                self.assertTrue(
                    any(m["field"] == field for m in report["mismatches"]),
                    report["mismatches"])

    def test_agreement_is_not_reported(self):
        for field in B9_FIELDS:
            with self.subTest(field=field):
                report = compare({field: 4}, {VALIDATOR_SPELLING.get(field, field): 4})
                self.assertFalse(
                    any(m["field"] == field for m in report["mismatches"]),
                    report["mismatches"])

    def test_a_ratio_drift_below_one_is_still_reported(self):
        """The integer-field exclusion must not become a tolerance."""
        report = compare({"week_boundary_max_coverage_ratio": 1.2},
                         {"next_sunday_max_coverage_ratio": 1.9})
        self.assertTrue(
            any(m["field"] == "week_boundary_max_coverage_ratio"
                for m in report["mismatches"]), report["mismatches"])


class AgainstRecordedArtifacts(unittest.TestCase):
    """The derivations must reproduce the engine's numbers on real schedules.

    A disagreement here is the point of B-9 and must be root-caused, not
    tolerated: it is either a wrong derivation on the validator side or a real
    engine defect, and nothing else in the suite can tell them apart.
    """

    @classmethod
    def setUpClass(cls):
        cls.validator = load("independent_validator_b9", VALIDATOR)
        cls.cases = []
        for base in (ROOT.parent.parent,):
            for audit in sorted(base.glob("**/*.l6_3_2_3_solver_audit.json")):
                root = audit.parent
                books = list(root.glob("*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"))
                inputs = list(root.glob("input_snapshot/*.xlsx"))
                if books and inputs:
                    cls.cases.append((root.name, audit, books[0], inputs[0]))

    def _engine_metrics(self, audit_path: Path):
        audit = json.loads(audit_path.read_text())
        block = audit.get("stage_metric_surface") or {}
        if block.get("stage") != "FULL_SCHEDULE":
            return None
        return block.get("metrics") or None

    def test_recorded_artifacts_agree_on_every_b9_field(self):
        checked = 0
        for name, audit_path, book, workbook_input in self.cases:
            engine_metrics = self._engine_metrics(audit_path)
            if not engine_metrics:
                continue
            result = self.validator.validate(workbook_input, book, ENGINE)
            got = result["metrics"]
            for field in B9_FIELDS:
                if field not in engine_metrics:
                    continue
                validator_key = VALIDATOR_SPELLING.get(field, field)
                with self.subTest(case=name, field=field):
                    self.assertAlmostEqual(
                        float(got[validator_key]), float(engine_metrics[field]),
                        places=6,
                        msg="%s: engine=%r validator[%s]=%r"
                            % (field, engine_metrics[field], validator_key,
                               got.get(validator_key)))
                checked += 1
        if not checked:
            self.skipTest("no full-schedule artifacts present in this environment")

    def test_hard_floor_gap_count_is_zero_when_no_hard_floor_is_configured(self):
        """The metric must mirror the engine, which reports 0, NOT fall back
        to the soft floor the way the HARD_FLOOR *failure* deliberately does."""
        checked = 0
        for name, audit_path, book, workbook_input in self.cases:
            engine_metrics = self._engine_metrics(audit_path)
            if not engine_metrics:
                continue
            parsed = load("engine_b9", ENGINE).parse_input(workbook_input)
            if parsed.hard_floor_ratio is not None:
                continue
            result = self.validator.validate(workbook_input, book, ENGINE)
            with self.subTest(case=name):
                self.assertEqual(int(result["metrics"]["hard_floor_gap_count"]), 0)
            checked += 1
        if not checked:
            self.skipTest("every available artifact configures a hard floor")


if __name__ == "__main__":
    unittest.main(verbosity=1)
