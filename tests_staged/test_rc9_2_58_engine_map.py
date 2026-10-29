# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AZ (owner, 2026-10-25: "a map for later fixes"): ``docs/ENGINE_MAP.md`` is written from the engine by
``tools/engine_map.py``. It holds line numbers and the engine's sha256, so an engine edit that leaves the map as it was fails
here, with the command that writes it again. The map only reads the engine."""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import engine_map  # noqa: E402

ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
MAP = ROOT / "docs" / "ENGINE_MAP.md"


class TheEngineMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = engine_map.build()

    def test_the_written_map_is_the_one_the_engine_gives(self):
        self.assertTrue(MAP.exists(), "docs/ENGINE_MAP.md is missing: run python3 tools/engine_map.py --write")
        self.assertEqual(MAP.read_text(encoding="utf-8"), self.text,
                         "the engine changed since docs/ENGINE_MAP.md was written: run python3 tools/engine_map.py --write")

    def test_it_names_the_engine_file_it_was_read_from(self):
        self.assertIn(hashlib.sha256(ENGINE.read_bytes()).hexdigest(), self.text)

    def test_run_case_has_an_outline_and_every_symptom_names_real_functions(self):
        self.assertIn("## 1. The stages of `run_case`", self.text)
        self.assertGreater(self.text.count("| `"), 300)  # the function tables
        for symptom, names in engine_map.SYMPTOMS:  # build() already stops on a missing name; here the table is read too
            for name in names:
                self.assertIn(f"`{name}`", self.text, symptom)

    def test_the_six_switches_are_listed_with_where_they_are_written(self):
        for name in engine_map.SWITCHES:
            self.assertRegex(self.text, rf"\| `{name}` \| \d+ \| `\w+`")

    def test_the_command_line_check_agrees(self):
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "engine_map.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class TheMapReadsTheSameInTheInstalledPackage(unittest.TestCase):
    """Phase BC (owner, 2026-10-29: the server's safety gate failed on ENGINE_MAP.md): the package builder writes MANIFEST.json (and ships
    SCENARIOS.json) into the package root after the gate inside the build has run, and the map used to list any root-level JSON that names the
    hash, so the installed package's map no longer matched. The map reads the code folders only; a file in the package root changes nothing."""

    def map_with(self, root_files):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        (root / "engine" / "_tools").mkdir(parents=True)
        shutil.copy2(ENGINE, root / "engine" / "_tools" / ENGINE.name)
        for name, body in root_files.items():
            (root / name).write_text(body, encoding="utf-8")
        return engine_map.build(root / "engine" / "_tools" / ENGINE.name, root)

    def test_a_manifest_in_the_package_root_does_not_change_the_map(self):
        bare = self.map_with({})
        shipped = self.map_with({"MANIFEST.json": '{"engine_sha256": "abc", "engine_file_sha256": "abc"}\n',
                                 "SCENARIOS.json": '{"engine_sha256": "abc"}\n', "other.json": '{"engine_sha256": "abc"}\n'})
        self.assertEqual(bare, shipped)


if __name__ == "__main__":
    unittest.main()
