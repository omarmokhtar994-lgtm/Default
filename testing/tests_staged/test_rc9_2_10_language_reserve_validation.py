#!/usr/bin/env python3
"""W7/B-9: the language_reserve release gate must be independently recomputed.

Of nine gates in production_quality_gate.gate_results, employee_quality was
closed by #38a. language_reserve was the second of the three with no
independent check: the validator already re-derived the HARD minimum
(rule.minimum) but nothing re-derived the operational RESERVE the gate
actually scores (minimum + language_reserve_extra).

These tests pin that the recomputation exists, that it reads the after-break
coverage rather than the engine's own gate verdict, and that it classifies the
three tiers the way the engine does.
"""
from __future__ import annotations

import ast
import inspect
import os
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = (Path(os.environ["RC9_ENGINE_DIR"]).resolve().parent.parent
        if os.environ.get("RC9_ENGINE_DIR")
        else Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

VALIDATOR = (ROOT / "engine" / "tools" / "independent_validator.py")


class LanguageReserveIsIndependentlyRecomputed(unittest.TestCase):
    def setUp(self):
        self.source = VALIDATOR.read_text(encoding="utf-8")

    def test_the_validator_emits_a_language_reserve_result(self):
        self.assertIn("language_reserve_independent", self.source,
                      "the gate must have an independently recomputed result")

    def test_it_reports_all_three_tiers(self):
        for key in ("reserve_gap_count", "reserve_minimum_only_count",
                    "reserve_protected_count"):
            with self.subTest(key=key):
                self.assertIn(key, self.source)

    def test_it_uses_the_engine_tier_helpers_not_a_private_copy(self):
        """A re-implementation of the thresholds could drift from the engine."""
        self.assertIn("eng.language_operational_reserve_target", self.source)
        self.assertIn("eng.language_reserve_status", self.source)

    def test_it_scores_after_break_coverage(self):
        """Breaks remove people from the floor; a reserve judged before breaks
        would pass a schedule that is short once breaks are placed.

        Checked on the AST, not by text proximity: the first argument to
        language_reserve_status must be the SAME name that the hard-minimum
        check compares against rule.minimum, and that name must be bound from
        after[slot]. Text search cannot tell those apart -- swapping the
        argument to before[slot] leaves 'after[slot]' sitting on a nearby line.
        """
        tree = ast.parse(self.source)
        actual_arg = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "language_reserve_status"
                    and node.args):
                actual_arg = node.args[0]
                break
        self.assertIsNotNone(actual_arg, "language_reserve_status is not called")
        self.assertIsInstance(
            actual_arg, ast.Name,
            "the reserve must be scored from the named eligible count, not an "
            "inline expression that could read the wrong coverage array")
        name = actual_arg.id

        # that name must be assigned from a comprehension over after[slot]
        bound_from_after = False
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == name):
                src = ast.unparse(node.value)
                if "after[slot]" in src:
                    bound_from_after = True
                self.assertNotIn(
                    "before[slot]", src,
                    f"{name} must not be derived from before-break coverage")
        self.assertTrue(
            bound_from_after,
            f"{name} must be counted from after[slot] (after-break coverage)")

    def test_it_does_not_read_the_engines_own_gate_verdict(self):
        """Independence: reading gate_results would make this a mirror, not a
        check. Docstrings are stripped so prose about the gate is not a hit."""
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef, ast.Module)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body = node.body[1:]
        executable = ast.unparse(tree)
        start = executable.find("language_reserve_independent")
        self.assertGreater(start, -1)
        segment = executable[max(0, start - 2000):start + 2000]
        self.assertNotIn("language_reserve_gate_status", segment,
                         "the independent result must not be derived from the "
                         "engine's own gate status")


class TheTierBoundariesMatchTheEngine(unittest.TestCase):
    """Non-vacuity: exercise the engine helpers the validator calls."""

    def test_below_the_hard_minimum_is_a_gap(self):
        self.assertEqual(E.language_reserve_status(1, 2, 3), "GAP")

    def test_at_the_minimum_but_under_the_reserve_is_minimum_only(self):
        self.assertEqual(E.language_reserve_status(2, 2, 3), "MINIMUM_ONLY")

    def test_at_the_reserve_is_protected(self):
        self.assertEqual(E.language_reserve_status(3, 2, 3), "RESERVE_PROTECTED")
        self.assertEqual(E.language_reserve_status(9, 2, 3), "RESERVE_PROTECTED")

    def test_a_disabled_reserve_collapses_to_the_hard_minimum(self):
        class _P:
            language_reserve_enabled = False
            language_reserve_extra = 4

        class _R:
            minimum = 2
        self.assertEqual(
            E.language_operational_reserve_target(_P(), _R()), 2,
            "with the reserve off the target must be the contract minimum")

    def test_an_enabled_reserve_adds_the_extra(self):
        class _P:
            language_reserve_enabled = True
            language_reserve_extra = 1

        class _R:
            minimum = 2
        self.assertEqual(E.language_operational_reserve_target(_P(), _R()), 3)


if __name__ == "__main__":
    unittest.main(verbosity=1)
