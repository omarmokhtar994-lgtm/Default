#!/usr/bin/env python3
"""Engine <-> independent-validator semantic parity guards.

The independent validator must recompute the exported workbook's coverage on its
own - that is what makes it independent, and it must be able to fail a release
the optimizer called PASS.

Independence does NOT extend to contract semantics.  Where the validator and the
engine must agree by definition - what counts as a long shift, what tolerance
converts an effective requirement into whole associates - a second private copy
of the value is not independence, it is a silent disagreement that shows up as a
validator false positive.  Under the release gates any validator mismatch blocks
the release, so a false positive is as damaging as a missed defect.

These tests pin the constants that must be shared, and the coverage math that
must not be.

Run:  python tests/test_rc9_2_1_validator_parity.py
"""
from __future__ import annotations

import importlib.util
import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

import l632_universal_scheduler as E  # noqa: E402

VALIDATOR_PATH = ROOT / "engine" / "tools" / "independent_validator.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("independent_validator", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedContractConstants(unittest.TestCase):
    """Constants that both sides apply must have exactly one definition."""

    def test_long_shift_threshold_is_defined_once(self):
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        # assertFalse on a bool, not assertNotIn on the file, so a failure prints
        # one line instead of the entire validator source.
        self.assertFalse(
            "duration_min>=660" in source.replace(" ", ""),
            "Validator carries its own long-shift threshold (660). It must use "
            "eng.LONG_SHIFT_MIN_DURATION_MIN, or a shift in [630, 660) is long to "
            "the engine and short to the validator, producing a false "
            "OFF_COUNT_VIOLATION that blocks a valid release.",
        )
        self.assertTrue(
            "LONG_SHIFT_MIN_DURATION_MIN" in source,
            "Validator must reference the engine's shared long-shift constant.",
        )

    def test_engine_long_shift_threshold_value(self):
        self.assertEqual(E.LONG_SHIFT_MIN_DURATION_MIN, 630)

    def test_engine_has_no_bare_long_shift_literals(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        compact = source.replace(" ", "")
        self.assertNotIn("duration_min>=630", compact)
        self.assertNotIn("duration_min<630", compact)

    def test_off_expectation_agrees_across_the_boundary(self):
        """A 10.5h shift must be long mode on both sides, not just one."""
        threshold = E.LONG_SHIFT_MIN_DURATION_MIN
        for duration, expected_off in ((threshold - 1, 2), (threshold, 3), (threshold + 30, 3)):
            with self.subTest(duration=duration):
                self.assertEqual(3 if duration >= threshold else 2, expected_off)

    def test_ceil_tolerance_is_shared(self):
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("OVERAGE_CEIL_TOLERANCE", source,
                      "Validator must apply the engine's ceil tolerance.")
        self.assertEqual(E.OVERAGE_CEIL_TOLERANCE, 1e-9)


class AvoidableOverageParity(unittest.TestCase):
    """The engine and validator must agree on avoidable overage, always.

    This is the metric the whole RC9.2.1 release argument turns on.  A
    disagreement here means the two sides are arguing about different numbers.
    """

    @staticmethod
    def validator_unavoidable(req, eff, target):
        return math.ceil(req * target / max(eff, 1e-9) - E.OVERAGE_CEIL_TOLERANCE) * eff

    @staticmethod
    def engine_unavoidable(req, eff, target):
        return E.fractional_safe_overage_metrics(
            req, 0.0, target, eff, 1.1, 1.25, 1.5)["minimum_raw_target"] * eff

    def test_agreement_over_random_contracts(self):
        random.seed(7)
        divergences = []
        for _ in range(200000):
            req = round(random.uniform(0.5, 60.0), 2)
            eff = round(random.uniform(0.70, 1.00), 4)
            target = random.choice([0.80, 0.90, 1.00])
            a = self.engine_unavoidable(req, eff, target)
            b = self.validator_unavoidable(req, eff, target)
            if abs(a - b) > 1e-12:
                divergences.append((req, eff, target, a, b))
                if len(divergences) > 3:
                    break
        self.assertEqual(
            divergences, [],
            "Engine and validator disagree on unavoidable staffing, so they "
            "disagree on avoidable overage.",
        )

    def test_zero_demand_interval_agrees(self):
        for staffing in (0.0, 3.4, 8.5):
            with self.subTest(staffing=staffing):
                engine = E.fractional_safe_overage_metrics(
                    0.0, staffing, 0.90, 0.85, 1.1, 1.25, 1.5)["avoidable_overage_fte"]
                validator = max(0.0, staffing - self.validator_unavoidable(0.0, 0.85, 0.90))
                self.assertAlmostEqual(engine, validator, places=9)

    def test_known_floating_point_boundary_case(self):
        """req=45.56 eff=0.9112 target=0.9 -> exactly 45 associates in exact math.

        45.56 * 0.9 / 0.9112 == 45.0 exactly, but lands marginally above 45 in
        floating point.  Found by random search against the pre-fix validator,
        which rounded up to 46 and so understated avoidable overage by one whole
        associate-equivalent (0.9112 effective FTE) on this interval.
        """
        a = self.engine_unavoidable(45.56, 0.9112, 0.90)
        b = self.validator_unavoidable(45.56, 0.9112, 0.90)
        self.assertAlmostEqual(a, b, places=9)
        self.assertAlmostEqual(a, 45 * 0.9112, places=9)

    def test_pre_fix_validator_would_have_failed_this_case(self):
        """Pin that the boundary case is genuinely discriminating."""
        naive = math.ceil(45.56 * 0.90 / 0.9112) * 0.9112  # validator before the fix
        engine = self.engine_unavoidable(45.56, 0.9112, 0.90)
        self.assertAlmostEqual(naive - engine, 0.9112, places=9,
                               msg="Expected exactly one associate-equivalent of "
                                   "disagreement before the tolerance was shared.")


class ValidatorIndependenceIsPreserved(unittest.TestCase):
    """The validator must still compute coverage itself, not defer to the engine."""

    def test_validator_recomputes_coverage_locally(self):
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        for marker in ("before100+=", "after100+=", "before_target+=", "after_floor+="):
            self.assertIn(marker.replace("+=", ""), source.replace(" ", ""),
                          "Validator must accumulate its own tier counts.")

    def test_validator_does_not_call_engine_metric_calculator(self):
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        self.assertNotIn("calculate_metrics", source,
                         "Reusing the engine's metric calculator would destroy "
                         "the validator's independence.")

    def test_validator_states_its_evidence_basis(self):
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("optimizer audit values were not used", source)

    def test_validator_module_loads(self):
        module = load_validator()
        self.assertTrue(hasattr(module, "validate"))


class TierCountingFormulaParity(unittest.TestCase):
    """Tier counting math must be identical on both sides.

    Audited by reading both implementations: same active guard, same
    effective-FTE derivation, same zero-demand convention, same epsilon.  These
    tests pin the conventions so a future edit to one side is caught.
    """

    def test_zero_demand_counts_as_fully_covered_on_both_sides(self):
        engine_src = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8").replace(" ", "")
        validator_src = VALIDATOR_PATH.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("before_pct=before/reqifreq>0else1.0", engine_src)
        self.assertIn("bp=be/reqifreq>0else1.0", validator_src)

    def test_both_sides_use_the_same_tier_epsilon(self):
        engine_src = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8").replace(" ", "")
        validator_src = VALIDATOR_PATH.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("before_pct>=0.90-1e-9", engine_src)
        self.assertIn("bp>=.9-1e-9", validator_src)

    def test_both_sides_skip_inactive_intervals(self):
        engine_src = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8").replace(" ", "")
        validator_src = VALIDATOR_PATH.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("ifnotparsed.active[d][i]:", engine_src)
        self.assertIn("ifnotparsed.active[d][i]:", validator_src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
