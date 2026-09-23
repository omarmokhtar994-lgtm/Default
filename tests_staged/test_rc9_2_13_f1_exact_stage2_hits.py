#!/usr/bin/env python3
"""F-1: Stage-2 decides coverage hits in the metric's own arithmetic.

See evidence/formula_audit/FINDINGS.md, F-1. Two things are pinned:

1. the helpers Stage-2 now uses agree with the reported metric on every
   (demand, shrinkage, ratio, quarter-count) case drawn from the real
   workbooks, including the non-terminating 12/130 shrinkage that broke the
   old x100 arithmetic;
2. solve_breaks reifies every hit on the exact expression while leaving the
   weighted deficit terms in their original units, so no objective magnitude
   moved.
"""
from __future__ import annotations

import ast
import inspect
import itertools
import math
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

CRICUT_SHRINK = 12 / 130   # the value that exposed the defect


def metric_hit(quarter_counts, shrink, req, ratio, qpi):
    """The validator's definition, verbatim in arithmetic."""
    effective = sum(quarter_counts) * (1 - shrink) / qpi
    return effective / req + 1e-9 >= ratio


def exact_hit(quarter_counts, shrink, req, ratio, qpi):
    return (sum(quarter_counts) * E.scaled_effective_factor(shrink)
            >= E.scaled_coverage_threshold(req, ratio, qpi))


def old_x100_hit(quarter_counts, shrink, req, ratio, qpi):
    return (sum(quarter_counts) * int(round((1 - shrink) * 100))
            >= E.ceil_units(req * ratio) * qpi)


class ExactArithmeticAgreesWithTheMetric(unittest.TestCase):
    def cases(self):
        for shrink in (0.0, 0.17, CRICUT_SHRINK, 0.3, 1 / 3):
            for req in (1.0, 2.5, 7.0, 10.0, 13.3, 21.0):
                for ratio in (0.8, 0.9, 1.0):
                    for qpi in (1, 2):
                        lo = max(0, int(req * ratio / (1 - shrink)) - 2)
                        hi = int(math.ceil(req * 1.3 / (1 - shrink))) + 2
                        for counts in itertools.product(range(lo, hi), repeat=qpi):
                            yield counts, shrink, req, ratio, qpi

    def test_exact_form_never_disagrees(self):
        n = 0
        for c in self.cases():
            n += 1
            self.assertEqual(exact_hit(*c), metric_hit(*c), c)
        self.assertGreater(n, 5000)

    def test_the_old_form_did_disagree_on_cricut_shrinkage(self):
        """Non-vacuity: this suite would have caught the original defect."""
        bad = [c for c in self.cases() if old_x100_hit(*c) != metric_hit(*c)]
        self.assertTrue(bad, "the x100 form must be shown wrong somewhere")
        self.assertTrue(any(abs(c[1] - CRICUT_SHRINK) < 1e-12 for c in bad))

    def test_the_recorded_worked_case(self):
        """Chat d1 i35: 10 FTE, 9.23% shrinkage, 11 people -> 99.85%, a miss."""
        case = ((11,), CRICUT_SHRINK, 10.0, 1.0, 1)
        self.assertFalse(metric_hit(*case))
        self.assertTrue(old_x100_hit(*case), "the old arithmetic called this a hit")
        self.assertFalse(exact_hit(*case))


class Stage2UsesTheExactExpressionOnlyForDecisions(unittest.TestCase):
    def setUp(self):
        src = textwrap.dedent(inspect.getsource(E.solve_breaks))
        self.tree = ast.parse(src)
        self.src = src

    def reified(self):
        """(lhs, rhs) of every `model.Add(a >= b).OnlyEnforceIf(hit)`."""
        out = []
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "OnlyEnforceIf"
                    and isinstance(node.func.value, ast.Call)
                    and node.func.value.args
                    and isinstance(node.func.value.args[0], ast.Compare)):
                cmp = node.func.value.args[0]
                out.append((ast.unparse(cmp.left), ast.unparse(cmp.comparators[0]),
                            ast.unparse(node.args[0])))
        return out

    def test_every_coverage_hit_is_reified_on_the_exact_expression(self):
        hits = [r for r in self.reified()
                if any(h in r[2] for h in ("floor_hit", "severe_hit", "target_hit", "full_hit"))]
        main = [r for r in hits if r[0] == "after_exact"]
        self.assertEqual(len(main), 8, "main week: four hits, each reified both ways")
        for lhs, rhs, lit in main:
            with self.subTest(hit=lit):
                self.assertTrue(rhs.split(" ")[0].endswith("_exact"), rhs)
        # The only other hits are the next-Sunday boundary block's target and
        # full, which were exact before F-1: its after_eff is built from
        # scaled_effective_factor and its thresholds from
        # scaled_coverage_threshold (both x1e6). Anything else reified on the
        # x100 expression would be a hit F-1 missed.
        rest = [r for r in hits if r[0] != "after_exact"]
        self.assertEqual(sorted(r[2] for r in rest),
                         ["full_hit", "full_hit.Not()", "target_hit", "target_hit.Not()"])
        block = self.src[self.src.index("next_sunday_after_raw_sequence: List"):]
        block = block[:block.index("if parsed.next_sunday_balance_enabled:\n        ordered_boundary")]
        self.assertIn("eff_person = scaled_effective_factor(parsed.shrinkage[0][i])", block)
        self.assertIn("target_units = scaled_coverage_threshold(", block)
        self.assertIn("full_units = scaled_coverage_threshold(", block)
        self.assertNotIn("round((1", block)
        for lhs, rhs, lit in rest:
            with self.subTest(hit=lit):
                self.assertEqual(lhs, "after_eff")
                self.assertIn(rhs.split(" ")[0], ("target_units", "full_units"))

    def test_deficit_terms_keep_their_original_units(self):
        """Moving these to x1e6 would multiply their weight by 10,000."""
        self.assertIn("model.Add(floor_slack >= floor_units - after_eff)", self.src)
        self.assertIn("model.Add(target_def >= target_units - after_eff)", self.src)

    def test_the_hard_floor_is_exact(self):
        self.assertIn('add_break_family(model.Add(after_exact >= hard_floor_exact), "floor")', self.src)
        self.assertNotIn("model.Add(after_eff >= hard_floor_units)", self.src)

    def test_overage_minimum_headcount_uses_the_true_factor(self):
        self.assertNotIn("100.0 / max(1, eff_person)", self.src,
                         "dividing by the rounded coefficient gave 11 where 12 is correct")


if __name__ == "__main__":
    unittest.main(verbosity=1)
