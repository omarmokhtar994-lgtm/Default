# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "I want the one equals =agents() in Excel"): the downloadable workbook whose people-needed grid is made of live formulas.
The grid is recalculated by LibreOffice and must equal the people the site worked out, cell for cell; changing an input must give what the site's Erlang
gives for that input. Made-up numbers."""
import io
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from openpyxl import load_workbook

from webapp import erlang
from webapp import volumes_formulas as V
from webapp.tests.test_bi_volumes import KEY, STEP, SUN, book, history

SOFFICE = shutil.which("soffice")
FIRST = 14       # the first row of the grids on a channel sheet (volumes_formulas.GRID_ROW)


def forecasts(measure="sl"):
    store, vb = book(measure)
    history(store, per_week=7000, channel="Phone")
    history(store, per_week=3000, channel="Chat", aht=420.0)
    history(store, per_week=2000, channel="Email", aht=600.0)
    out = {ch: vb.forecast(KEY, ch, SUN, total=total) for ch, total in (("Phone", 7600), ("Chat", 3100), ("Email", 2100))}
    return vb, out


def recalc(data: bytes, name="w.xlsx"):
    tmp = Path(tempfile.mkdtemp())
    src = tmp / name
    src.write_bytes(data)
    out = tmp / "out"
    out.mkdir()
    subprocess.run([SOFFICE, "--headless", "--norestore", "--convert-to", "xlsx", "--outdir", str(out), str(src)], check=True, capture_output=True, timeout=300)
    return load_workbook(out / name, data_only=True)


class TheWorkbook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vb, cls.f = forecasts()
        cls.settings = cls.vb.settings(KEY)
        cls.data = V.formulas_workbook(SUN, STEP, cls.f, cls.settings)
        cls.wb = load_workbook(io.BytesIO(cls.data))

    def test_a_read_me_and_a_sheet_for_each_channel_given(self):
        self.assertEqual(self.wb.sheetnames, ["Read me", "Phone", "Chat", "Email"])
        only = load_workbook(io.BytesIO(V.formulas_workbook(SUN, STEP, {"Chat": self.f["Chat"]}, self.settings)))
        self.assertEqual(only.sheetnames, ["Read me", "Chat"])

    def test_the_inputs_are_the_sites_own_settings(self):
        ws = self.wb["Phone"]
        s = self.settings["Phone"]
        self.assertEqual([ws["B4"].value, ws["B5"].value, ws["B6"].value, ws["B7"].value, ws["B8"].value, ws["B10"].value],
                         [self.f["Phone"]["aht"], STEP * 60, s["sl_target"], s["sl_seconds"], s["occupancy"], s["shrinkage"]])
        self.assertEqual(self.wb["Chat"]["B9"].value, self.settings["Chat"]["concurrency"])

    def test_the_contacts_grid_holds_the_forecast_and_is_laid_out_like_the_input_sheet(self):
        ws = self.wb["Phone"]
        head = [ws.cell(FIRST - 1, c).value for c in range(1, 9)]
        self.assertEqual(head, ["Interval", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        for slot in (0, 9, 10, 23):
            self.assertEqual(ws.cell(FIRST + slot, 1).value, f"{slot * STEP // 60:02d}:{slot * STEP % 60:02d}")
            for day in range(7):
                self.assertEqual(ws.cell(FIRST + slot, 2 + day).value, self.f["Phone"]["calls"][day][slot])

    def test_the_people_grid_is_made_of_formulas_and_the_site_grid_of_numbers(self):
        ws = self.wb["Phone"]
        cell = ws.cell(FIRST + 9, 10)
        self.assertTrue(str(cell.value).startswith("=IF("))
        self.assertIn("POISSON(", cell.value)
        self.assertLess(len(cell.value), 8000)
        self.assertEqual(ws.cell(FIRST + 9, 18).value, self.f["Phone"]["needs"][0][9])

    def test_the_read_me_carries_the_agents_function_as_text_not_as_a_formula(self):
        info = self.wb["Read me"]
        found = [c for row in info.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=LAMBDA(")]
        self.assertEqual(len(found), 2)
        self.assertTrue(all(c.data_type == "s" for c in found))
        self.assertTrue(any("AGENTS" in str(c.value) for row in info.iter_rows() for c in row))

    def test_the_read_me_says_what_to_do_if_a_future_excel_drops_the_old_poisson_name(self):
        text = " ".join(str(c.value) for row in self.wb["Read me"].iter_rows() for c in row if isinstance(c.value, str) and not c.value.startswith("=LAMBDA"))
        self.assertIn("POISSON.DIST", text)

    def test_nothing_reaches_outside_the_file(self):
        with __import__("zipfile").ZipFile(io.BytesIO(self.data)) as z:
            names = " ".join(z.namelist()).lower()
        for part in ("externallink", "vbaproject", "embeddings", "activex"):
            self.assertNotIn(part, names)

    def test_it_recalculates_on_opening(self):
        self.assertTrue(self.wb.calculation.fullCalcOnLoad)

    def test_a_channel_with_no_grid_is_refused(self):
        with self.assertRaises(ValueError):
            V.formulas_workbook(SUN, STEP, {}, self.settings)
        with self.assertRaises(ValueError):
            V.formulas_workbook(SUN, STEP, {"Phone": {**self.f["Phone"], "needs": None}}, self.settings)


@unittest.skipUnless(SOFFICE, "LibreOffice is not installed here")
class TheFormulasAgainstTheSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vb, cls.f = forecasts()
        cls.settings = cls.vb.settings(KEY)

    def grids(self, ws, f):
        slots = len(f["calls"][0])
        live = [[ws.cell(FIRST + i, 10 + d).value for i in range(slots)] for d in range(7)]
        return live, f["needs"]

    def test_every_cell_of_every_channel_equals_what_the_site_worked_out(self):
        wb = recalc(V.formulas_workbook(SUN, STEP, self.f, self.settings))
        for ch in ("Phone", "Chat", "Email"):
            live, site = self.grids(wb[ch], self.f[ch])
            for d in range(7):
                for i, (a, b) in enumerate(zip(live[d], site[d])):
                    self.assertAlmostEqual(float(a), float(b), places=9, msg=(ch, d, i, a, b))

    def test_the_sheet_says_how_many_intervals_differ_and_it_is_none(self):
        wb = recalc(V.formulas_workbook(SUN, STEP, self.f, self.settings))
        for ch in ("Phone", "Chat", "Email"):
            ws = wb[ch]
            self.assertEqual(ws["F7"].value, 0, ch)
            self.assertIn("matches", str(ws["F8"].value).lower(), ch)

    def test_the_summary_matches_the_sites_numbers(self):
        wb = recalc(V.formulas_workbook(SUN, STEP, self.f, self.settings))
        needs = self.f["Phone"]["needs"]
        self.assertAlmostEqual(wb["Phone"]["F4"].value, sum(sum(r) for r in needs) * STEP / 60, places=6)
        self.assertEqual(wb["Phone"]["F5"].value, max(max(r) for r in needs))

    def test_changing_an_input_gives_what_the_sites_erlang_gives_for_it(self):
        data = V.formulas_workbook(SUN, STEP, self.f, self.settings)
        wb = load_workbook(io.BytesIO(data))
        ws = wb["Phone"]
        ws["B6"], ws["B7"], ws["B8"], ws["B4"] = 95, 10, 75, 420
        out = io.BytesIO()
        wb.save(out)
        got = recalc(out.getvalue())["Phone"]
        calls = self.f["Phone"]["calls"]
        for d in range(7):
            for i in range(len(calls[d])):
                want = erlang.agents_needed(calls[d][i], 420, STEP * 60, 0.95, 10, 0.75) if calls[d][i] else 0
                self.assertEqual(got.cell(FIRST + i, 10 + d).value, want, (d, i))
        self.assertGreater(got["F7"].value, 0)                       # the settings changed, so the sheet says the intervals differ from the site's
        self.assertIn("differ", str(got["F8"].value).lower())

    def test_chat_follows_the_chats_at_once_input(self):
        wb = load_workbook(io.BytesIO(V.formulas_workbook(SUN, STEP, self.f, self.settings)))
        wb["Chat"]["B9"] = 3
        out = io.BytesIO()
        wb.save(out)
        got = recalc(out.getvalue())["Chat"]
        s = self.settings["Chat"]
        calls = self.f["Chat"]["calls"]
        for d in range(7):
            for i in range(len(calls[d])):
                want = erlang.chat_agents_needed(calls[d][i], self.f["Chat"]["aht"], STEP * 60, s["sl_target"] / 100.0, s["sl_seconds"], 3, s["occupancy"] / 100.0) if calls[d][i] else 0
                self.assertEqual(got.cell(FIRST + i, 10 + d).value, want, (d, i))

    def test_email_follows_the_workload_input(self):
        wb = load_workbook(io.BytesIO(V.formulas_workbook(SUN, STEP, self.f, self.settings)))
        wb["Email"]["B8"] = 70
        out = io.BytesIO()
        wb.save(out)
        got = recalc(out.getvalue())["Email"]
        calls = self.f["Email"]["calls"]
        for d in range(7):
            for i in range(len(calls[d])):
                want = round(erlang.workload_agents(calls[d][i], self.f["Email"]["aht"], STEP * 60, 0.7), 2) if calls[d][i] else 0
                self.assertAlmostEqual(got.cell(FIRST + i, 10 + d).value, want, places=9, msg=(d, i))

    def test_a_changed_forecast_cell_is_followed(self):
        wb = load_workbook(io.BytesIO(V.formulas_workbook(SUN, STEP, self.f, self.settings)))
        wb["Phone"].cell(FIRST + 10, 3).value = 480                  # Monday 10:00
        out = io.BytesIO()
        wb.save(out)
        got = recalc(out.getvalue())["Phone"]
        s = self.settings["Phone"]
        self.assertEqual(got.cell(FIRST + 10, 11).value, erlang.agents_needed(480, self.f["Phone"]["aht"], STEP * 60, s["sl_target"] / 100.0, s["sl_seconds"], s["occupancy"] / 100.0))


if __name__ == "__main__":
    unittest.main()
