# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI tasks 4 to 6 (owner, 2026-11-03): settings per channel, the forecast of a week from a typed total, the people needed with Erlang for
service-level programs, the grids in the input sheet's layout (intervals down, Sun to Sat across), how the week went (OTF and trends), and the
requirement workbook. Made-up numbers; weeks start on Sunday here.

Phase BJ (2026-11-04): the forecast no longer takes a ``today`` argument (the weeks are counted back from the week planned, not from the day it is looked
at) and reads the same N whole weeks for every weekday; the calls that passed ``today=`` were changed to match, and nothing else in these tests was loosened."""
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from openpyxl import load_workbook

from webapp import erlang
from webapp.store import Store
from webapp.volumes import VolumeBook

STEP = 60
KEY = "Program 01 Voice"
SUN = date(2026, 11, 8)       # the week being planned
TODAY = date(2026, 11, 3)


def weights(weekday):
    """Hours 8 to 19 open; a morning and an afternoon peak; weekends shorter."""
    base = {8: 4, 9: 8, 10: 10, 11: 9, 12: 6, 13: 6, 14: 8, 15: 9, 16: 7, 17: 5, 18: 3, 19: 2}
    if weekday in (4, 5):  # Friday and Saturday (python weekday 4 = Fri, 5 = Sat)
        base = {h: v for h, v in base.items() if 10 <= h <= 15}
    return base


def history(store, weeks=8, per_week=7000, channel="Phone", aht=300.0, key=KEY):
    rows = []
    for w in range(1, weeks + 1):
        sunday = SUN - timedelta(weeks=w)
        for k in range(7):
            day = sunday + timedelta(days=k)
            wts = weights(day.weekday())
            total = per_week / 7 * (1.3 if day.weekday() in (6, 0) else 1.0)
            s = sum(wts.values())
            for h, v in wts.items():
                rows.append((day.isoformat(), h * 60, round(total * v / s), aht))
    store.replace_volume_rows(key, channel, rows, 1)


def book(measure="sl", staffing=None):
    store = Store(Path(tempfile.mkdtemp()) / "s.db")
    return store, VolumeBook(store, measure_of=lambda key: measure, staffing=staffing or (lambda key, on: None), step_of=lambda key: STEP)


class TheSettings(unittest.TestCase):
    def test_defaults_are_there_for_every_channel(self):
        _, vb = book()
        s = vb.settings(KEY)
        self.assertEqual(sorted(s), ["Chat", "Email", "Phone"])
        self.assertEqual((s["Phone"]["sl_target"], s["Phone"]["sl_seconds"]), (80, 20))
        self.assertEqual(s["Chat"]["concurrency"], 2.0)

    def test_saved_values_win_and_the_rest_stay_default(self):
        _, vb = book()
        vb.set_settings(KEY, {"Phone": {"sl_target": 90, "sl_seconds": 30}}, 1)
        s = vb.settings(KEY)
        self.assertEqual((s["Phone"]["sl_target"], s["Phone"]["sl_seconds"], s["Phone"]["occupancy"]), (90, 30, 88))

    def test_values_out_of_range_are_refused_whole(self):
        _, vb = book()
        for bad in ({"sl_target": 40}, {"sl_target": 101}, {"sl_seconds": 0}, {"occupancy": 10}, {"shrinkage": 80}, {"concurrency": 9},
                    {"aht": 5}, {"forecast_weeks": 2}, {"band_low": 95, "band_high": 90}, {"sl_target": "abc"}):
            with self.assertRaises(ValueError, msg=bad):
                vb.set_settings(KEY, {"Phone": {"sl_target": 85, **bad}}, 1)
        self.assertEqual(vb.settings(KEY)["Phone"]["sl_target"], 80)

    def test_an_unknown_channel_or_key_is_refused(self):
        _, vb = book()
        with self.assertRaises(ValueError):
            vb.set_settings(KEY, {"Fax": {"aht": 300}}, 1)
        with self.assertRaises(ValueError):
            vb.set_settings(KEY, {"Phone": {"colour": 1}}, 1)

    def test_erlang_is_for_service_level_and_volume_weighted_programs_only(self):
        for measure, want in (("sl", True), ("volume", True), ("interval", False)):
            self.assertEqual(book(measure)[1].uses_erlang(KEY), want, measure)


class TheForecast(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        history(self.store)

    def test_a_typed_total_is_spread_and_kept_exactly(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertEqual(sum(sum(day) for day in f["calls"]), 8000)
        self.assertEqual(len(f["calls"]), 7)
        self.assertTrue(all(len(day) == 24 for day in f["calls"]))
        self.assertEqual(f["total"], 8000)
        self.assertEqual(f["source"], "typed")

    def test_days_come_out_in_the_input_sheets_order_sunday_first(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        sun, mon, fri = (sum(f["calls"][i]) for i in (0, 1, 5))
        self.assertGreater(sun, fri)        # Sundays carry 1.3 times a Friday's volume in the made-up history
        self.assertGreater(mon, fri)
        self.assertEqual(f["days"], ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])

    def test_the_shape_follows_the_history_and_closed_hours_stay_empty(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        mon = f["calls"][1]
        self.assertEqual(sum(mon[:8]), 0)
        self.assertEqual(max(range(24), key=lambda h: mon[h]), 10)

    def test_a_typed_day_is_kept_and_the_rest_share_what_is_left(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000, day_totals={1: 1500})
        self.assertEqual(sum(f["calls"][1]), 1500)
        self.assertEqual(sum(sum(d) for d in f["calls"]), 8000)

    def test_with_no_total_the_suggestion_is_used_and_said(self):
        f = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(f["source"], "suggestion")
        self.assertAlmostEqual(f["total"], 7600, delta=60)  # 1000 a day, with Sunday and Monday at 1.3 times
        lo, hi = f["suggestion"]["low"], f["suggestion"]["high"]
        self.assertLessEqual(lo, f["total"])
        self.assertGreaterEqual(hi, f["total"])

    def test_a_saved_forecast_is_used_before_the_suggestion(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 9100, {}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual((f["total"], f["source"]), (9100, "saved"))

    def test_no_history_is_said_in_words(self):
        f = self.vb.forecast(KEY, "Chat", SUN, total=500)
        self.assertIn("history", f["error"].lower())
        self.assertEqual(f["calls"], [])

    def test_bad_totals_are_refused(self):
        for bad in (-1, 1.5, "abc", 10 ** 9):
            with self.assertRaises(ValueError, msg=bad):
                self.vb.forecast(KEY, "Phone", SUN, total=bad)

    def test_the_grid_is_ready_to_paste(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        grid = self.vb.grid(f["calls"], STEP)
        self.assertEqual(grid[0], ["Interval", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual(len(grid), 1 + 24)
        self.assertEqual(grid[1][0], "00:00")
        self.assertEqual(grid[11][0], "10:00")
        self.assertEqual(grid[11][2], f["calls"][1][10])


class TheNeeds(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book("sl")
        history(self.store)

    def test_voice_needs_follow_erlang(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        calls, need = f["calls"][1][10], f["needs"][1][10]
        self.assertEqual(need, erlang.agents_needed(calls, f["aht"], STEP * 60, 0.8, 20, 0.88))
        self.assertGreater(need, 0)
        self.assertEqual(f["needs"][1][3], 0)

    def test_the_service_level_the_need_gives_is_at_least_the_target(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        for d in range(7):
            for i in range(24):
                if f["calls"][d][i]:
                    self.assertGreaterEqual(f["service"][d][i], 80.0 - 1e-6)

    def test_the_aht_comes_from_the_history_unless_the_program_sets_one(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertEqual(f["aht"], 300.0)
        self.vb.set_settings(KEY, {"Phone": {"aht": 420}}, 1)
        self.assertEqual(self.vb.forecast(KEY, "Phone", SUN, total=8000)["aht"], 420.0)

    def test_a_program_counted_by_interval_compliance_gets_no_erlang(self):
        store, vb = book("interval")
        history(store)
        f = vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertIsNone(f["needs"])
        self.assertIsNone(f["service"])
        self.assertTrue(f["calls"])

    def test_chat_uses_concurrency_and_email_the_workload(self):
        history(self.store, channel="Chat", aht=600.0)
        history(self.store, channel="Email", aht=600.0)
        chat = self.vb.forecast(KEY, "Chat", SUN, total=8000)
        phone = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertLess(sum(map(sum, chat["needs"])) / max(1, chat["aht"]), sum(map(sum, phone["needs"])) / max(1, phone["aht"]))
        email = self.vb.forecast(KEY, "Email", SUN, total=8000)
        calls, need = email["calls"][1][10], email["needs"][1][10]
        self.assertAlmostEqual(need, erlang.workload_agents(calls, email["aht"], STEP * 60, 0.85), places=2)

    def test_more_calls_never_need_fewer_people(self):
        low = self.vb.forecast(KEY, "Phone", SUN, total=6000)
        high = self.vb.forecast(KEY, "Phone", SUN, total=12000)
        self.assertGreaterEqual(sum(map(sum, high["needs"])), sum(map(sum, low["needs"])))

    def test_the_requirement_workbook_is_laid_out_like_the_input_sheet(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        data = self.vb.requirement_workbook(KEY, SUN, {"Phone": f})
        wb = load_workbook(io.BytesIO(data))
        self.assertEqual(wb.sheetnames, ["FT Wise 60 Min", "Phone 60 Min"])
        ws = wb["FT Wise 60 Min"]
        header = next(r for r in range(1, 10) if ws.cell(r, 1).value == "Interval")
        self.assertEqual([ws.cell(header, c).value for c in range(1, 9)], ["Interval", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual(ws.cell(header + 1, 1).value, "00:00")
        self.assertEqual(ws.cell(header + 11, 1).value, "10:00")
        self.assertEqual(ws.cell(header + 11, 3).value, f["needs"][1][10])
        self.assertEqual(ws.max_row - header, 24)

    def test_ft_wise_is_the_sum_of_the_channels(self):
        history(self.store, channel="Chat", aht=600.0)
        a = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        b = self.vb.forecast(KEY, "Chat", SUN, total=3000)
        wb = load_workbook(io.BytesIO(self.vb.requirement_workbook(KEY, SUN, {"Phone": a, "Chat": b})))
        self.assertEqual(wb.sheetnames, ["FT Wise 60 Min", "Chat 60 Min", "Phone 60 Min"])
        ws = wb["FT Wise 60 Min"]
        header = next(r for r in range(1, 10) if ws.cell(r, 1).value == "Interval")
        self.assertAlmostEqual(ws.cell(header + 11, 3).value, a["needs"][1][10] + b["needs"][1][10], places=2)

    def test_no_cell_of_the_workbook_is_text_a_person_typed(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        wb = load_workbook(io.BytesIO(self.vb.requirement_workbook(KEY, SUN, {"Phone": f})))
        for ws in wb.worksheets:
            for row in ws.iter_rows(min_row=5):
                for cell in row[1:]:
                    self.assertIsInstance(cell.value, (int, float), (ws.title, cell.coordinate))

    def test_a_program_counted_by_interval_has_no_requirement_workbook(self):
        store, vb = book("interval")
        history(store)
        f = vb.forecast(KEY, "Phone", SUN, total=8000)
        with self.assertRaises(ValueError):
            vb.requirement_workbook(KEY, SUN, {"Phone": f})


class TheReport(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book("sl")
        history(self.store)
        # the week of 08 Nov is planned at 8000 and then comes in 6 percent over, evenly
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN)
        rows = []
        for d in range(7):
            day = next(SUN + timedelta(days=k) for k in range(7) if (SUN + timedelta(days=k)).weekday() == (d - 1) % 7)
            for h in range(24):
                if f["calls"][d][h]:
                    rows.append((day.isoformat(), h * 60, round(f["calls"][d][h] * 1.06), 300.0))
        self.store.replace_volume_rows(KEY, "Phone", rows, 1)
        self.f = f

    def test_otf_per_interval_day_and_week(self):
        r = self.vb.report(KEY, "Phone", SUN)
        self.assertAlmostEqual(r["week_otf"], 106.0, delta=0.6)
        self.assertEqual(len(r["otf"]), 7)
        peak = max(range(24), key=lambda h: self.f["calls"][1][h])
        self.assertAlmostEqual(r["otf"][1][peak], 106.0, delta=1.5)
        self.assertIsNone(r["otf"][1][3])  # a closed hour has no forecast: no OTF, not 0 percent
        self.assertEqual(r["band"][1][peak], "on")

    def test_a_week_with_no_forecast_says_so_and_gives_no_otf(self):
        self.store.delete_volume_forecast(KEY, "Phone", SUN)
        r = self.vb.report(KEY, "Phone", SUN)
        self.assertIsNone(r["week_otf"])
        self.assertIn("no forecast", r["note"].lower())

    def test_a_week_with_no_actuals_says_so(self):
        r = self.vb.report(KEY, "Phone", SUN + timedelta(weeks=3))
        self.assertIn("no actual", r["note"].lower())

    def test_the_trend_lists_the_weeks_that_have_both(self):
        r = self.vb.report(KEY, "Phone", SUN)
        self.assertEqual([w["week"] for w in r["trend"]], [SUN.isoformat()])
        self.assertAlmostEqual(r["trend"][0]["otf"], 106.0, delta=0.6)

    def test_the_week_the_actuals_are_in_is_counted_in_the_programs_own_week(self):
        r = self.vb.report(KEY, "Phone", SUN)
        self.assertEqual(r["actual_total"], sum(sum(d) for d in r["actual"]))
        self.assertGreater(r["actual_total"], 8000)

    def test_staffing_lines_for_a_day(self):
        monday = SUN + timedelta(days=1)

        def staffing(key, on):
            return {h * 60: (10.0, 11.0, 9.0) for h in range(24)} if on == monday else None
        _, vb = book("sl", staffing=staffing)
        history(vb.store)
        vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        rows = [(monday.isoformat(), h * 60, 60, 300.0) for h in range(8, 20)]
        vb.store.replace_volume_rows(KEY, "Phone", rows, 1)
        r = vb.report(KEY, "Phone", SUN, on=monday)
        s = r["staffing"]
        self.assertEqual(len(s["required"]), 24)
        self.assertEqual(s["required"][10], 10.0)
        self.assertEqual(s["floor"][10], 9.0)
        self.assertEqual(s["at_actual"][10], erlang.agents_needed(60, 300.0, 3600, 0.8, 20, 0.88))
        self.assertEqual(s["modelled_sl"][10], round(erlang.service_level(9, 60, 300.0, 3600, 20) * 100, 1))
        self.assertIn("modelled", s["note"].lower())

    def test_no_schedule_for_the_day_is_said(self):
        r = self.vb.report(KEY, "Phone", SUN, on=SUN)
        self.assertIsNone(r["staffing"]["required"])
        self.assertIn("schedule", r["staffing"]["note"].lower())

    def test_an_interval_program_gets_no_erlang_or_service_level_lines(self):
        monday = SUN + timedelta(days=1)
        _, vb = book("interval", staffing=lambda key, on: {h * 60: (10.0, 11.0, 9.0) for h in range(24)})
        history(vb.store)
        vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        vb.store.replace_volume_rows(KEY, "Phone", [(monday.isoformat(), 600, 60, 300.0)], 1)
        s = vb.report(KEY, "Phone", SUN, on=monday)["staffing"]
        self.assertEqual(s["required"][10], 10.0)
        self.assertIsNone(s["at_actual"])
        self.assertIsNone(s["modelled_sl"])


class TheActualsCoverage(unittest.TestCase):
    def test_coverage_names_the_weeks_held(self):
        store, vb = book()
        history(store, weeks=3)
        c = vb.coverage(KEY, "Phone")
        self.assertEqual(c["days"], 21)
        self.assertEqual(c["first"], (SUN - timedelta(weeks=3)).isoformat())
        self.assertEqual(vb.coverage(KEY, "Chat"), {"days": 0, "first": None, "last": None, "weeks": []})


if __name__ == "__main__":
    unittest.main()
