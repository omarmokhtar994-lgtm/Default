#!/usr/bin/env python3
"""#38a: the employee_quality release gate must be independently recomputed.

Nine gates in production_quality_gate.gate_results authorise release. Six were
independently recomputed by the validator; employee_quality, language_reserve
and skill_allocation were not, and employee_quality is the one observed
returning a verdict other than PASS.

These tests pin that the recomputation exists, reads the OUTPUT schedule rather
than the engine's own object, and is not stricter than the policy it audits.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

VALIDATOR_PATH = ROOT / "engine" / "tools" / "independent_validator.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("independent_validator", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V = load_validator()


def _shift(label, start_min, end_abs_min):
    return types.SimpleNamespace(label=label, start_min=start_min, end_abs_min=end_abs_min)


def _roster(names):
    return types.SimpleNamespace(associates=[types.SimpleNamespace(name=n) for n in names])


class EmployeeQualityValidationTest(unittest.TestCase):

    def setUp(self):
        self.day = _shift("D", 9 * 60, 17 * 60)          # 09:00-17:00
        self.late = _shift("L", 20 * 60, 23 * 60)        # 20:00-23:00, late
        self.night = _shift("N", 22 * 60, 26 * 60)       # 22:00-02:00, late + overnight
        self.shift_map = {"d": self.day, "l": self.late, "n": self.night}

    def test_the_recomputation_exists(self):
        self.assertTrue(hasattr(V, "independent_employee_quality"))

    def test_even_load_produces_zero_spread(self):
        parsed = _roster(["A", "B"])
        rows = {"a": ["D"] * 7, "b": ["D"] * 7}
        out = V.independent_employee_quality(parsed, rows, self.shift_map)
        self.assertEqual(out["late_shift_load_delta"], 0)
        self.assertEqual(out["overnight_load_delta"], 0)
        self.assertEqual(out["weekend_load_delta"], 0)

    def test_late_shift_spread_is_detected(self):
        """Non-vacuity: one associate carrying every late shift must show up."""
        parsed = _roster(["A", "B"])
        rows = {"a": ["L"] * 7, "b": ["D"] * 7}
        out = V.independent_employee_quality(parsed, rows, self.shift_map)
        self.assertEqual(out["late_shift_load_delta"], 7,
                         "a 7-vs-0 late-shift split must yield a spread of 7")

    def test_overnight_spread_is_detected(self):
        parsed = _roster(["A", "B"])
        rows = {"a": ["N"] * 7, "b": ["D"] * 7}
        out = V.independent_employee_quality(parsed, rows, self.shift_map)
        self.assertEqual(out["overnight_load_delta"], 7)

    def test_weekend_counts_only_sunday_and_saturday(self):
        parsed = _roster(["A", "B"])
        rows = {"a": ["D", "OFF", "OFF", "OFF", "OFF", "OFF", "D"],   # both weekend days
                "b": ["OFF", "D", "D", "D", "D", "D", "OFF"]}          # no weekend days
        out = V.independent_employee_quality(parsed, rows, self.shift_map)
        self.assertEqual(out["weekend_load_delta"], 2)

    def test_isolated_off_is_counted_circularly(self):
        """An OFF with a shift either side, wrapping across the week boundary."""
        parsed = _roster(["A"])
        rows = {"a": ["OFF", "D", "D", "D", "D", "D", "D"]}
        out = V.independent_employee_quality(parsed, rows, self.shift_map)
        self.assertEqual(out["isolated_offday_violation_count"], 1,
                         "Sunday OFF between Saturday and Monday shifts is isolated")

    def test_it_reads_the_output_not_the_engine(self):
        """Independence: the helper must take the parsed assignment grid.

        If it reached into a SkeletonSolution it would be echoing the engine
        rather than checking it.
        """
        import ast
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(V.independent_employee_quality)))
        func = tree.body[0]
        body = func.body
        # Drop the docstring: it legitimately names what the helper must NOT read.
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]
        code = "\n".join(ast.dump(node) for node in body)

        for forbidden in ("skeleton", "selected_shift_index", "diagnostics"):
            self.assertNotIn(forbidden, code,
                             f"validator must not read {forbidden} from the engine")

    def test_missing_associate_row_does_not_crash(self):
        parsed = _roster(["A", "Ghost"])
        rows = {"a": ["D"] * 7}
        out = V.independent_employee_quality(parsed, rows, self.shift_map)
        self.assertEqual(out["roster_size"], 2)

    def test_findings_are_warnings_not_hard_failures(self):
        """The validator must not be stricter than the gate it audits.

        The engine's employee_quality_gate_mode defaults to 'warn', so a spread
        breach is declared, not fatal.
        """
        source = VALIDATOR_PATH.read_text()
        idx = source.find("EMPLOYEE_QUALITY_")
        self.assertGreater(idx, 0, "gate findings must be emitted")
        window = source[max(0, idx - 400):idx]
        self.assertIn("warnings.append", window,
                      "employee_quality breaches must append to warnings, not failures")


if __name__ == "__main__":
    unittest.main(verbosity=2)
