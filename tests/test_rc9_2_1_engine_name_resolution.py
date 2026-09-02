#!/usr/bin/env python3
"""Every name the engine calls must actually exist.

`derive_adaptive_feedback_cuts` and `adaptive_operator_focus_cells` both called
`parse_time_to_minute`, which is defined nowhere in this engine.  Both call
sites sit inside a loop over a candidate's `language_gaps`, so the NameError
fired for any candidate carrying an unmet language minimum - the bilingual and
directional-skill scenarios specifically.  Six live call sites reach those two
functions from the joint-refinement and descent paths.

Neither the test suite nor line-by-line reading found this; a static
undefined-name check did.  That check is now part of the gate.

Run:  python tests/test_rc9_2_1_engine_name_resolution.py
"""
from __future__ import annotations

import ast
import builtins
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

import l632_universal_scheduler as E  # noqa: E402

SOURCES = sorted(
    p for p in [
        ROOT / "engine" / "_tools" / "l632_universal_scheduler.py",
        ROOT / "engine" / "_tools" / "phase_b_maturity.py",
        ROOT / "engine" / "_tools" / "phase_b_adaptive.py",
        ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py",
        ROOT / "engine" / "tools" / "independent_validator.py",
        ROOT / "engine" / "production" / "phase_c_quality_report.py",
        ROOT / "engine" / "production" / "production_output_polisher.py",
        ROOT / "engine" / "production" / "package_phase_a_outputs.py",
        ROOT / "engine" / "production" / "package_phase_c_outputs.py",
        ROOT / "tools" / "release_gate_report.py",
        ROOT / "tools" / "replay_candidate_ranking.py",
    ] if p.exists())


class TheEngineCallsOnlyNamesItDefines(unittest.TestCase):

    def test_the_missing_function_is_gone(self):
        source = SOURCES[0] if SOURCES[0].name.startswith("l632") else (
            ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
        text = source.read_text(encoding="utf-8")
        calls = [line for line in text.splitlines()
                 if "parse_time_to_minute(" in line and not line.strip().startswith("#")]
        self.assertEqual(calls, [], "this name is defined nowhere in the engine")

    def test_the_replacement_exists_and_is_the_exact_inverse(self):
        self.assertTrue(hasattr(E, "minute_of_day"))
        for minute in (0, 1, 555, 720, 1439):
            with self.subTest(minute=minute):
                self.assertEqual(E.minute_of_day(E.hhmm(minute)), minute)

    def test_a_language_gap_row_round_trips(self):
        """The exact row shape calculate_metrics emits for an unmet minimum."""
        row = {"day": "Sun", "time": E.hhmm(555), "group": "spanish",
               "minimum": 2, "actual": 1}
        self.assertEqual(E.minute_of_day(row["time"]), 555)
        self.assertEqual(int(555 // 15), 37)

    def test_no_undefined_names_in_any_first_party_module(self):
        """Static undefined-name check (ruff F821) over the whole codebase.

        This is the check that found the defect. Skipped, loudly, rather than
        silently passing if ruff is unavailable.
        """
        import shutil
        ruff = shutil.which("ruff")
        if ruff is None:
            probe = subprocess.run([sys.executable, "-m", "ruff", "--version"],
                                   capture_output=True, text=True)
            if probe.returncode != 0:
                self.skipTest("ruff not installed; static undefined-name check not run")
            ruff_cmd = [sys.executable, "-m", "ruff"]
        else:
            ruff_cmd = [ruff]
        result = subprocess.run(
            [*ruff_cmd, "check", "--isolated", "--select", "E9,F821",
             *[str(p) for p in SOURCES]],
            capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0,
                         f"undefined names found:\n{result.stdout[-2000:]}")


class EveryModuleLevelNameResolves(unittest.TestCase):
    """A cheaper in-process cross-check that does not depend on ruff."""

    def _defined(self, tree, text):
        names = set(dir(builtins))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, ast.alias):
                names.add((node.asname or node.name).split(".")[0])
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                names.update(node.names)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names.add(node.name)
        return names

    def test_every_called_name_is_defined_somewhere_in_its_module(self):
        for path in SOURCES:
            with self.subTest(module=path.name):
                text = path.read_text(encoding="utf-8")
                tree = ast.parse(text)
                defined = self._defined(tree, text)
                missing = sorted({
                    node.func.id for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id not in defined})
                self.assertEqual(missing, [], f"{path.name} calls undefined name(s)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
