"""Phase H, task 3: both Colab notebooks run in three steps, no typed paths.

Owner, 2026-10-07: "refine now colab runner make it easier for me as a user to
use it without efforts"; both notebooks; the results keep everything, as today.
Before: 7-10 cells, the workbook given as a typed path, the gate report and
the download as separate cells. Now: 1. Setup, 2. Your workbook (an upload
button; each workbook checked at once), 3. Run (runs every accepted workbook,
scores the gates, then downloads the results ZIP (A) or writes it to Drive (B)).
Every safeguard the earlier notebooks carried stays.
"""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNNERS = next(p for p in (REPO / "runners", REPO / "packages" / "rc9_2_2_production" / "runners") if p.is_dir())
NOTEBOOKS = {"A": RUNNERS / "RC922_Colab_A_NO_DRIVE.ipynb", "B": RUNNERS / "RC922_Colab_B_WITH_DRIVE.ipynb"}
TITLES = ["#@title 1. Setup", "#@title 2. Your workbook", "#@title 3. Run"]
SAFEGUARDS = ("rc922_runner.py", "start_new_session", "KeyboardInterrupt", "--resume", "--overwrite", "SEEDS",
              "RESUME = True", "ortools==9.15.6755", "scipy>=1.11", "ruff==",
              'COVERAGE_MEASURE = "workbook" #@param ["workbook", "INTERVAL_COUNT", "VOLUME_WEIGHTED"]',
              'cmd += ["--coverage-objective-weighting", COVERAGE_MEASURE]')


def all_text(nb: Path) -> str:
    return "\n".join("".join(c["source"]) for c in json.loads(nb.read_text(encoding="utf-8"))["cells"])


def code_cells(nb: Path):
    cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


class ThreeSteps(unittest.TestCase):
    def test_three_code_steps(self):
        for name, nb in NOTEBOOKS.items():
            with self.subTest(notebook=name):
                cells = code_cells(nb)
                self.assertEqual([c.splitlines()[0].split(" {")[0] for c in cells], TITLES)

    def test_workbook_is_uploaded_with_a_button(self):
        for name, nb in NOTEBOOKS.items():
            with self.subTest(notebook=name):
                step2 = code_cells(nb)[1]
                self.assertIn("files.upload()", step2)
                self.assertIn("check_input_workbook.py", step2)

    def test_run_checks_runs_scores_and_delivers(self):
        for name, nb in NOTEBOOKS.items():
            with self.subTest(notebook=name):
                run = code_cells(nb)[2]
                order = [run.index("rc922_runner.py"), run.index("release_gate_report.py"),
                         run.index("make_archive(")]
                self.assertEqual(order, sorted(order))
                if name == "A":
                    self.assertGreater(run.index("files.download("), run.index("make_archive("))

    def test_every_code_cell_compiles(self):
        for name, nb in NOTEBOOKS.items():
            for i, cell in enumerate(code_cells(nb)):
                with self.subTest(notebook=name, cell=i):
                    python = "\n".join("" if re.match(r"\s*[!%]", line) else line for line in cell.splitlines())
                    compile(python, f"{nb.name}[{i}]", "exec")

    def test_every_safeguard_stays(self):
        for name, nb in NOTEBOOKS.items():
            text = all_text(nb)
            for needle in SAFEGUARDS:
                with self.subTest(notebook=name, needle=needle):
                    self.assertIn(needle, text)
        self.assertIn("/content/drive/MyDrive/RC922_RC5", all_text(NOTEBOOKS["B"]))
        self.assertIn("RC9_2_2_FIX_VALIDATION_RC5.zip", all_text(NOTEBOOKS["A"]))


if __name__ == "__main__":
    unittest.main()
