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



class RunIdentityIsReproducible(unittest.TestCase):
    """`run_parameters` is hashed into parameters_sha256, hence into run_id.

    It carried `"stage1_profile_deadline_epoch": float(stage1_profile_deadline)`
    - an absolute wall-clock timestamp. The run identity therefore depended on
    the moment the run started, which meant two runs of the same input with the
    same parameters produced different run_ids (defeating the exact-identity
    release gate), and `--resume` could NEVER match its own checkpoint, so
    checkpoint/resume was inoperative and always raised "Resume refused".

    Proven at the time: two identical 60s runs gave parameters_sha256
    dc5d8541… vs d833ecb1…. After the fix they agree.

    These guards are structural so they run in the fast gate. A wall-clock value
    anywhere in the hashed parameters breaks reproducibility, whether absolute
    or expressed relative to the start - a relative value still carries
    scheduling jitter, which is how the first attempt at this fix still failed.
    """

    ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"

    def _run_parameters_node(self):
        import ast
        tree = ast.parse(self.ENGINE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and node.targets
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "run_parameters"
                    and isinstance(node.value, ast.Dict)):
                return node.value
        self.fail("run_parameters dict literal not found")

    def test_no_hashed_parameter_is_a_wall_clock_value(self):
        import ast
        node = self._run_parameters_node()
        offenders = []
        for key, value in zip(node.keys, node.values):
            name = key.value if isinstance(key, ast.Constant) else "<dynamic>"
            source = ast.dump(value)
            if "deadline" in source or "time" == source or "'time'" in source:
                if "deadline" in source:
                    offenders.append(f"{name} references a deadline")
            for sub in ast.walk(value):
                if (isinstance(sub, ast.Attribute) and sub.attr == "time"
                        and isinstance(sub.value, ast.Name) and sub.value.id == "time"):
                    offenders.append(f"{name} calls time.time()")
                if isinstance(sub, ast.Name) and sub.id.endswith("_epoch"):
                    offenders.append(f"{name} uses {sub.id}")
        self.assertEqual(offenders, [],
                         "a wall-clock value in run_parameters makes run_id "
                         "irreproducible and breaks --resume")

    def test_no_hashed_parameter_key_is_named_like_a_timestamp(self):
        import ast
        node = self._run_parameters_node()
        bad = [k.value for k in node.keys
               if isinstance(k, ast.Constant) and isinstance(k.value, str)
               and (k.value.endswith("_epoch") or k.value.endswith("_deadline"))]
        self.assertEqual(bad, [])

    def test_the_wall_clock_is_still_reported_just_not_hashed(self):
        """Removing it from the identity must not lose the diagnostic."""
        source = self.ENGINE.read_text(encoding="utf-8")
        self.assertIn('"run_wall_clock"', source)
        self.assertIn('"stage1_profile_deadline_epoch": float(stage1_profile_deadline)', source)

    def test_resume_still_refuses_a_genuinely_different_run(self):
        """The fix must not weaken the guard it broke.

        Resume refusing everything is not the same as resume refusing the wrong
        thing; input, contract, engine and parameters must all still be hashed.
        """
        source = self.ENGINE.read_text(encoding="utf-8").replace(" ", "")
        for field in ('"input_sha256":sha256_file(input_path)',
                      '"contract_sha256":canonical_hash(contract_payload)',
                      '"engine_sha256":sha256_file(Path(__file__))',
                      '"parameters_sha256":canonical_hash(run_parameters)'):
            with self.subTest(field=field):
                self.assertIn(field, source)
        self.assertIn("Resumerefused:", source)

if __name__ == "__main__":
    unittest.main(verbosity=2)
