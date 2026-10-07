"""Phase G, task 1: the production package carries its own gate result.

External audit P0-02: the gate evidence bundled in the package was stale
(1,432 tests against a later minimum of 1,436). tools/build_production_package.py
already ran the gate inside the staged package, but only printed its last line,
so what shipped said nothing about the gate that actually ran. The builder now
writes the full gate output to PACKAGE_GATE_RESULT.txt and a parsed record to
MANIFEST.json, and still refuses to package on a failing gate.
"""
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
import zipfile
from unittest import mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PASS_OUT = ("── test totals\n   1483 tests run, 2 skipped\n\n"
            "GATE PASS — 69 suite(s), 1483 tests (2 skipped) + 2 selfchecks + cross-module call signatures"
            " + undefined-name sweep\n")


def load():
    spec = importlib.util.spec_from_file_location("build_production_package_g1", REPO / "tools" / "build_production_package.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TheGateRecord(unittest.TestCase):
    def test_pass_line_is_parsed(self):
        rec = load().gate_record(PASS_OUT, 0)
        self.assertEqual(rec["status"], "PASS")
        self.assertEqual((rec["tests"], rec["skipped"]), (1483, 2))
        self.assertTrue(rec["result_line"].startswith("GATE PASS"))

    def test_a_failing_gate_is_recorded_as_fail(self):
        self.assertEqual(load().gate_record(PASS_OUT, 1)["status"], "FAIL")
        rec = load().gate_record("GATE FAIL — see failures above\n", 1)
        self.assertEqual(rec["status"], "FAIL")
        self.assertIsNone(rec["tests"])


def tiny_repo() -> Path:
    """A minimal repo tree with every path the builder copies. The real repo
    is not usable here: this suite also runs inside the built package, which
    has no packages/ tree (Phase G: building from the real ROOT failed there)."""
    root = Path(tempfile.mkdtemp()) / "repo"
    for tree in ("engine/_tools", "tools", "tests", "tests_staged", "fixtures", "evidence",
                 "packages/rc9_2_2_production/inputs", "packages/rc9_2_2_production/runners"):
        (root / tree).mkdir(parents=True)
        (root / tree / "README.txt").write_text("x", encoding="utf-8")
    engine = root / "engine" / "_tools" / "l632_universal_scheduler.py"
    engine.write_text("# engine\n", encoding="utf-8")
    book = root / "packages" / "rc9_2_2_production" / "inputs" / "CASE.xlsx"
    book.write_bytes(b"workbook")
    for name in ("run_tests.sh", "CODE_AUDIT.md"):
        (root / name).write_text("x", encoding="utf-8")
    pkg = root / "packages" / "rc9_2_2_production"
    for name in ("README.md", "PRODUCTION_RUN_GUIDE.md", "LIVE_SCENARIOS.md"):
        (pkg / name).write_text("x", encoding="utf-8")
    (pkg / "SCENARIOS.json").write_text(json.dumps({
        "engine_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
        "scenarios": [{"scenario_id": "CASE", "input": "CASE.xlsx",
                       "input_sha256": hashlib.sha256(book.read_bytes()).hexdigest()}]}), encoding="utf-8")
    return root


class TheBuilderShipsTheRecord(unittest.TestCase):
    def build_with_gate(self, returncode, stdout):
        """Build a tiny repo into a temp dir with the staged gate replaced by a
        canned result (the real gate is the full suite); subprocess.run and
        ROOT are restored afterwards."""
        mod = load()
        calls = []

        def fake_run(cmd, cwd=None, **kw):
            calls.append((cmd, cwd))
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
        out = Path(tempfile.mkdtemp())
        with mock.patch.object(mod.subprocess, "run", fake_run), mock.patch.object(mod, "ROOT", tiny_repo()):
            try:
                return mod, out, calls, mod.build(out)
            except SystemExit as exc:
                return mod, out, calls, exc

    def test_builder_writes_the_record_into_the_package(self):
        mod, out, calls, zip_path = self.build_with_gate(0, PASS_OUT)
        self.assertIsInstance(zip_path, Path)
        self.assertEqual(calls[0][0], ["bash", "run_tests.sh"])
        staging = out / mod.NAME
        self.assertEqual((staging / "PACKAGE_GATE_RESULT.txt").read_text(encoding="utf-8"), PASS_OUT)
        manifest = json.loads((staging / "MANIFEST.json").read_text())
        self.assertEqual(manifest["gate"]["status"], "PASS")
        self.assertEqual(manifest["gate"]["tests"], 1483)
        self.assertTrue(manifest.get("built_utc"))
        with zipfile.ZipFile(zip_path) as zf:
            self.assertIn(f"{mod.NAME}/PACKAGE_GATE_RESULT.txt", zf.namelist())

    def test_a_failing_gate_leaves_no_package(self):
        mod, out, _, result = self.build_with_gate(1, "GATE FAIL — see failures above\n")
        self.assertIsInstance(result, SystemExit)
        self.assertFalse((out / f"{mod.NAME}.zip").exists())


if __name__ == "__main__":
    unittest.main()
