# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "I want the one equals =agents() in Excel"): the Erlang staffing as Excel formulas that use only functions every Excel and
LibreOffice have (POISSON, SUMPRODUCT, ROW, INDIRECT, EXP). The formulas are recalculated by LibreOffice on thousands of random cases and compared with the Python
Erlang the site uses; they must agree on every case."""
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from webapp import erlang as E
from webapp import excel_agents as X

SOFFICE = shutil.which("soffice")


def recalc(path: Path) -> Path:
    out = path.parent / "out"
    out.mkdir(exist_ok=True)
    subprocess.run([SOFFICE, "--headless", "--norestore", "--convert-to", "xlsx", "--outdir", str(out), str(path)],
                   check=True, capture_output=True, timeout=300)
    return out / path.name


class TheFormulaText(unittest.TestCase):
    def test_only_functions_every_excel_has_and_no_new_ones(self):
        f = X.agents_formula("A1", "B1", "C1", "D1", "E1", "F1")
        for word in ("LET(", "LAMBDA(", "SEQUENCE(", "POISSON.DIST", "_xlfn", "FILTER(", "XLOOKUP"):
            self.assertNotIn(word, f)
        for word in ("POISSON(", "SUMPRODUCT(", "ROW(INDIRECT(", "EXP("):
            self.assertIn(word, f)
        self.assertLess(len(f), 4000)

    def test_the_references_are_used_as_given(self):
        f = X.agents_formula("Calls!B5", "$B$2", "$B$7", "$B$3", "$B$4", "$B$5")
        self.assertIn("Calls!B5", f)
        self.assertIn("$B$7", f)

    def test_the_lambda_text_names_the_function_and_its_six_inputs(self):
        text = X.lambda_definitions()
        self.assertIn("AGENTS", text)
        self.assertIn("SERVICELEVEL", text)
        self.assertIn("LAMBDA(", text)
        self.assertIn("SEQUENCE(", text)


@unittest.skipUnless(SOFFICE, "LibreOffice is not installed here")
class TheFormulaAgainstPython(unittest.TestCase):
    """The formula as Excel would calculate it (LibreOffice recalculates it) against the Erlang the site uses."""

    def cases(self, n, seed):
        rng = random.Random(seed)
        out = []
        for _ in range(n):
            interval = rng.choice((900, 1800, 3600))
            calls = rng.choice((0, 1, 2, 5, rng.randint(0, 60), rng.randint(0, 400), rng.randint(0, 1500)))
            aht = rng.choice((30, 60, 120, 180, 300, 420, 600, rng.randint(20, 900)))
            sl = rng.choice((50, 60, 70, 75, 80, 85, 90, 95, 99, rng.randint(50, 99))) / 100.0
            thr = rng.choice((5, 10, 15, 20, 30, 60, 120, rng.randint(5, 180)))
            occ = rng.choice((0.5, 0.7, 0.8, 0.85, 0.88, 0.9, 0.95, 1.0, rng.randint(50, 100) / 100.0))
            out.append((calls, aht, interval, sl, thr, occ))
        return out

    def test_two_thousand_random_cases_agree_with_python_exactly(self):
        cases = self.cases(2000, 20261104)
        wb = Workbook()
        ws = wb.active
        for i, (calls, aht, interval, sl, thr, occ) in enumerate(cases, start=1):
            for col, v in enumerate((calls, aht, interval, sl, thr, occ), start=1):
                ws.cell(i, col, v)
            ws.cell(i, 7, "=" + X.agents_formula(f"A{i}", f"B{i}", f"C{i}", f"D{i}", f"E{i}", f"F{i}"))
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "agents.xlsx"
        wb.save(src)
        got = load_workbook(recalc(src), data_only=True).active
        wrong = []
        for i, (calls, aht, interval, sl, thr, occ) in enumerate(cases, start=1):
            want = E.agents_needed(calls, aht, interval, sl, thr, occ) if calls > 0 else 0
            value = got.cell(i, 7).value
            if value != want:
                wrong.append((i, (calls, aht, interval, sl, thr, occ), value, want))
        self.assertEqual(wrong, [], f"{len(wrong)} of {len(cases)} differ; first: {wrong[:3]}")

    def test_the_service_level_formula_agrees_with_python(self):
        cases = self.cases(600, 77)
        wb = Workbook()
        ws = wb.active
        used = []
        for calls, aht, interval, sl, thr, occ in cases:
            n = E.agents_needed(calls, aht, interval, sl, thr, occ) if calls > 0 else 0
            for agents in {n, max(0, n - 1), n + 2, max(0, int(calls * aht / interval))}:
                used.append((agents, calls, aht, interval, thr))
        for i, (agents, calls, aht, interval, thr) in enumerate(used, start=1):
            for col, v in enumerate((agents, calls, aht, interval, thr), start=1):
                ws.cell(i, col, v)
            ws.cell(i, 6, "=" + X.service_level_formula(f"A{i}", f"B{i}", f"C{i}", f"D{i}", f"E{i}"))
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "sl.xlsx"
        wb.save(src)
        got = load_workbook(recalc(src), data_only=True).active
        worst = 0.0
        for i, (agents, calls, aht, interval, thr) in enumerate(used, start=1):
            want = E.service_level(agents, calls, aht, interval, thr)
            worst = max(worst, abs(got.cell(i, 6).value - want))
        self.assertLess(worst, 1e-9, f"largest difference {worst}")

    def test_the_worked_example_in_the_read_me(self):
        wb = Workbook()
        wb.active["A1"] = "=" + X.agents_formula("100", "180", "1800", "0.8", "20", "0.88")
        wb.active["A2"] = "=" + X.service_level_formula("14", "100", "180", "1800", "20")
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "one.xlsx"
        wb.save(src)
        got = load_workbook(recalc(src), data_only=True).active
        self.assertEqual(got["A1"].value, 14)
        self.assertAlmostEqual(got["A2"].value, E.service_level(14, 100, 180, 1800, 20), places=9)


if __name__ == "__main__":
    unittest.main()
