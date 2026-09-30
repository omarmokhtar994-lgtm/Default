"""Package-layer safety restored from RC5 (audit F-17, F-18, F-20, F-05, M-09).

The final Colab package had shipped an older runner lineage than RC5's: no
engine sha256 check, no pinned-runtime check, no process-group stop on
timeout, exit code 0 on failed scenarios or failed gates, a guard that ran
tests/test_rc9_2_1_* only, and workbooks whose dropdowns accepted any typed
value. These tests pin each restored behaviour, in the repository layout and
in the built package layout.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()


def first(*paths):
    return next((p for p in paths if p.exists()), None)


RUNNERS = first(ROOT / "runners", REPO / "packages" / "rc9_2_2_production" / "runners")
INPUTS = first(ROOT / "inputs", REPO / "packages" / "rc9_2_2_production" / "inputs")
MANIFEST = first(ROOT / "SCENARIOS.json", REPO / "packages" / "rc9_2_2_production" / "SCENARIOS.json")
TOOLS = ROOT / "tools"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load("rc921_runner_safety", RUNNERS / "rc921_runner.py")


class EngineAndRuntimeChecks(unittest.TestCase):
    def test_engine_sha_must_match_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = root / "engine" / "_tools" / "l632_universal_scheduler.py"
            engine.parent.mkdir(parents=True)
            engine.write_text("print('x')\n")
            import hashlib
            good = hashlib.sha256(engine.read_bytes()).hexdigest()
            self.assertEqual(RUNNER.verify_engine(root, {"engine_sha256": good}), [])
            self.assertTrue(RUNNER.verify_engine(root, {"engine_sha256": "0" * 64}))
            self.assertTrue(RUNNER.verify_engine(root, {}))

    def test_the_shipped_manifest_names_the_shipped_engine(self):
        manifest = json.loads(MANIFEST.read_text())
        self.assertEqual(RUNNER.verify_engine(ROOT, manifest), [])

    def test_runtime_check_tool_ships_and_pins_ortools_and_scipy(self):
        source = (TOOLS / "runtime_environment_check.py").read_text()
        self.assertIn('"ortools": ("9.15.6755", True)', source)
        self.assertIn('"scipy"', source)

    def test_main_refuses_before_any_run_when_the_engine_does_not_match(self):
        source = (RUNNERS / "rc921_runner.py").read_text()
        main = source[source.index("def main() -> int:"):]
        self.assertLess(main.index("verify_engine(root, manifest)"), main.index("run_runtime_check(root)"))
        self.assertLess(main.index("run_runtime_check(root)"), main.index("run_guard_suite(root)"))
        self.assertLess(main.index("run_guard_suite(root)"), main.index("run_one(root, results_root, row, args)"))

    def test_the_guard_is_the_full_gate_not_one_glob(self):
        source = (RUNNERS / "rc921_runner.py").read_text()
        guard = source[source.index("def run_guard_suite"):source.index("def main() -> int:")]
        self.assertIn("run_tests.sh", guard)
        self.assertNotIn('glob("test_rc9_2_1_*.py")', guard)
        parallel = (RUNNERS / "run_parallel.py").read_text()
        self.assertIn("run_tests.sh", parallel)


class FailuresPropagate(unittest.TestCase):
    def test_a_failed_or_timed_out_scenario_is_a_failure(self):
        self.assertFalse(RUNNER.record_failed({"exit_code": 0}))
        for code in (1, 2, "TIMEOUT", "EXISTS_NOT_OVERWRITTEN"):
            self.assertTrue(RUNNER.record_failed({"exit_code": code}))

    def test_a_portfolio_without_a_validated_winner_is_a_failure(self):
        self.assertTrue(RUNNER.record_failed({"exit_code": 0, "seeds": 4, "after_breaks_winner_seed": None}))
        self.assertFalse(RUNNER.record_failed({"exit_code": 0, "seeds": 4, "after_breaks_winner_seed": 9001}))

    def test_main_returns_the_failure_and_the_gate_verdict(self):
        source = (RUNNERS / "rc921_runner.py").read_text()
        tail = source[source.rindex("run_failed = "):]
        self.assertIn("return 2", tail)
        self.assertIn("return gate_rc", tail)
        self.assertNotRegex(tail.split("if __name__")[0], r"\n    return 0\n")


class ProcessTreeStops(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "process groups are POSIX")
    def test_a_timeout_kills_grandchildren_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "grandchild.pid"
            script = f"sleep 60 & echo $! > {marker}; wait"
            with self.assertRaises(subprocess.TimeoutExpired):
                RUNNER._run_engine(["bash", "-c", script], Path(tmp) / "log.txt", timeout=2)
            pid = int(marker.read_text().strip())

            def dead():  # gone, or a zombie waiting for init to reap it
                try:
                    return Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"
                except FileNotFoundError:
                    return True

            for _ in range(50):
                if dead():
                    break
                time.sleep(0.1)
            else:
                os.kill(pid, 9)
                self.fail(f"grandchild {pid} survived the timeout")

    def test_single_and_portfolio_paths_both_use_the_process_group_runner(self):
        source = (RUNNERS / "rc921_runner.py").read_text()
        self.assertIn('start_new_session=(os.name == "posix")', source)
        self.assertIn("os.killpg(os.getpgid(proc.pid)", source)
        self.assertEqual(source.count("_run_engine("), 3)  # definition + single run + portfolio
        self.assertNotIn("subprocess.run(command, stdout", source)
        self.assertNotIn("subprocess.run(cmd, stdout", source)


class OverwriteIsExplicit(unittest.TestCase):
    def test_the_engine_is_not_told_to_overwrite_unless_asked(self):
        source = (RUNNERS / "rc921_runner.py").read_text()
        run_one = source[source.index("def run_one"):source.index("def run_portfolio")]
        self.assertIn('if getattr(args, "overwrite", False):', run_one)
        self.assertNotIn('"--overwrite",\n    ]', run_one)


class SeedPlanRespectsMemory(unittest.TestCase):
    def test_side_by_side_seeds_are_capped_by_memory(self):
        self.assertEqual(RUNNER.seed_plan(4, 0, 8), (4, 2))
        self.assertEqual(RUNNER.seed_plan(4, 0, 8, memory_mb=7000), (2, 4))
        self.assertEqual(RUNNER.seed_plan(4, 0, 8, memory_mb=1000), (1, 8))
        self.assertEqual(RUNNER.seed_plan(4, 3, 8, memory_mb=1000), (3, 2))  # explicit --parallel wins


class WorkbooksEnforceTheirDropdowns(unittest.TestCase):
    @staticmethod
    def baseline_protected():
        """Workbooks whose exact bytes are the RC9.1 comparison key (gates 2 and 9)."""
        import hashlib
        baseline = json.loads(first(ROOT / "evidence" / "RC9_1_BASELINE.json",
                                    REPO / "evidence" / "RC9_1_BASELINE.json").read_text())
        prefixes = [row.get("input_sha256_prefix") for row in baseline["scenarios"].values()
                    if row.get("input_sha256_prefix")]
        return {book.name for book in INPUTS.glob("*.xlsx")
                if any(hashlib.sha256(book.read_bytes()).hexdigest().startswith(p) for p in prefixes)}

    def test_baseline_protected_workbooks_are_left_byte_identical(self):
        # Editing them (even only their validation flags) voids the RC9.1
        # comparison; C-2 is guarded for them by the engine's contract check.
        self.assertEqual(self.baseline_protected(), {
            "AE_AR_B2B.xlsx", "Cricut_Voice_RC9_1_READY_SKELETON.xlsx", "NMG_SP_RC9_1_READY_FIXED.xlsx"})

    def test_every_other_shipped_workbook_rejects_values_outside_its_lists(self):
        protected = self.baseline_protected()
        books = [b for b in sorted(INPUTS.glob("*.xlsx")) if b.name not in protected]
        self.assertGreaterEqual(len(books), 4)
        for book in books:
            with self.subTest(workbook=book.name), zipfile.ZipFile(book) as archive:
                tags = []
                for name in archive.namelist():
                    if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                        tags += re.findall(rb"<dataValidation\b[^>]*>", archive.read(name))
                self.assertTrue(tags)
                for tag in tags:
                    self.assertIn(b'showErrorMessage="1"', tag)
                    self.assertIn(b'errorStyle="stop"', tag)

    def test_the_template_builder_creates_enforced_dropdowns(self):
        source = (TOOLS / "build_input_template.py").read_text()
        helper = source[source.index("def enforced_list_validation"):source.index("def ensure_language_setup_controls")]
        self.assertIn("dv.showErrorMessage = True", helper)
        self.assertIn('dv.errorStyle = "stop"', helper)
        self.assertEqual(source.count("DataValidation(type="), 1)  # only inside the helper

    def test_rebuilding_a_shipped_workbook_preserves_its_contract_and_enforces_dropdowns(self):
        # The builder read an already two-tab 'Engine Defaults' sheet as the legacy
        # Key|Value layout and dropped its values on rebuild ("Demand Fit Guard
        # Enabled = Auto" came back as No). Every shipped workbook must survive it.
        sys.path.insert(0, str(ROOT / "engine" / "_tools"))
        import l632_universal_scheduler as E
        for book in sorted(INPUTS.glob("*.xlsx")):
            with self.subTest(workbook=book.name), tempfile.TemporaryDirectory() as tmp:
                rebuilt = Path(tmp) / book.name
                subprocess.run([sys.executable, str(TOOLS / "build_input_template.py"), str(book), str(rebuilt)],
                               check=True, capture_output=True)
                before = E.canonical_hash(E.canonical_contract_snapshot(E.parse_input(book)))
                after = E.canonical_hash(E.canonical_contract_snapshot(E.parse_input(rebuilt)))
                self.assertEqual(before, after)
                with zipfile.ZipFile(rebuilt) as archive:
                    for name in archive.namelist():
                        if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                            for tag in re.findall(rb"<dataValidation\b[^>]*>", archive.read(name)):
                                self.assertIn(b'showErrorMessage="1"', tag)

    def test_manifest_hashes_match_the_shipped_workbooks(self):
        import hashlib
        manifest = json.loads(MANIFEST.read_text())
        for row in manifest["scenarios"]:
            with self.subTest(scenario=row["scenario_id"]):
                digest = hashlib.sha256((INPUTS / row["input"]).read_bytes()).hexdigest()
                self.assertEqual(digest, row["input_sha256"])


class NotebooksAreTheSafeOnes(unittest.TestCase):
    def test_only_rc922_notebooks_ship_and_they_carry_the_safeguards(self):
        self.assertFalse(list(RUNNERS.glob("RC921_*.ipynb")))
        for name in ("RC922_Colab_A_NO_DRIVE.ipynb", "RC922_Colab_B_WITH_DRIVE.ipynb"):
            with self.subTest(notebook=name):
                text = (RUNNERS / name).read_text()
                self.assertIn("rc922_runner.py", text)
                self.assertNotIn("rc921_runner.py", text)
                for needle in ("start_new_session", "KeyboardInterrupt", "--resume", "--overwrite", "SEEDS"):
                    self.assertIn(needle, text)

    def test_helper_runners_import_the_canonical_entry_point(self):
        for name in ("run_deep.py", "run_standard_regression.py", "run_targeted_regression.py"):
            with self.subTest(runner=name):
                self.assertIn("from rc922_runner import main", (RUNNERS / name).read_text())


class TheGateNeedsNothingOutsideThePackage(unittest.TestCase):
    """Tests read only files that ship in the package.

    Six tests used to read real run outputs from one machine's scratch
    directory: they ran there, and on the first Colab run they skipped, the
    gate's skip ceiling refused the run, and nothing had been checked either
    way. Those files now ship under fixtures/.
    """

    MACHINE_PATHS = ("/tmp/" + "claude-0", "scratch" + "pad", "/home/" + "user/")

    def test_no_test_refers_to_a_path_on_one_machine(self):
        offenders = []
        for folder in (ROOT / "tests", ROOT / "tests_staged"):
            for path in sorted(folder.glob("test_*.py")):
                text = path.read_text(encoding="utf-8")
                offenders += [f"{path.name}: {m}" for m in self.MACHINE_PATHS if m in text]
        self.assertEqual(offenders, [])

    def test_the_fixtures_the_artifact_tests_read_are_shipped(self):
        fixtures = ROOT / "fixtures"
        self.assertTrue(list((fixtures / "real_runs" / "before_break").rglob("*_BEST_BEFORE_BREAKS_SCHEDULE.xlsx")))
        self.assertEqual(len(list((fixtures / "real_runs" / "week_boundary").glob("*/production/*.xlsx"))), 5)
        self.assertEqual(len(list((fixtures / "ae_inputs").glob("*.xlsx"))), 6)

    def test_the_notebooks_install_what_the_gate_runs(self):
        for name in ("RC922_Colab_A_NO_DRIVE.ipynb", "RC922_Colab_B_WITH_DRIVE.ipynb"):
            text = (RUNNERS / name).read_text()
            for pin in ("ortools==9.15.6755", "scipy>=1.11", "ruff=="):
                self.assertIn(pin, text, name)


class MissingDependenciesStopTheRun(unittest.TestCase):
    def test_the_production_runner_refuses_without_scipy(self):
        source = (ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py").read_text()
        self.assertIn("'scipy'", source[source.index("REQUIRED_RUNTIME_MODULES"):][:200])
        main = source[source.index("def main() -> int:"):]
        self.assertLess(main.index("missing_runtime_dependencies()"), main.index("acquire_case_lock"))

    def test_the_check_reports_a_missing_module(self):
        runner = load("run_universal_production_deps", ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py")
        saved = runner.REQUIRED_RUNTIME_MODULES
        try:
            runner.REQUIRED_RUNTIME_MODULES = ("json", "module_that_does_not_exist_f20")
            self.assertEqual(len(runner.missing_runtime_dependencies()), 1)
        finally:
            runner.REQUIRED_RUNTIME_MODULES = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
