# © 2026 Omar Mokhtar. All rights reserved.
"""Phase M task 1: the week view, from the validator's interval rows.

The real run (Phase I, NMG Spanish, 30-minute intervals) gives the expected
figures; the 60-minute and nobody-on-the-floor cases are built from it."""
import copy
import json
import unittest
from pathlib import Path

from webapp.week import compact, view

ROWS = json.loads((Path(__file__).with_name("fixtures") / "real_run" / "NMG_SP_RC9_1_READY_FIXED"
                   / "INDEPENDENT_VALIDATION.json").read_text(encoding="utf-8"))["interval_rows"]
REAL = compact(ROWS)


class TheWeekView(unittest.TestCase):
    def test_real_week_totals(self):
        t = view(REAL)["totals"]
        self.assertEqual((t["full"], t["active"]), (107, 126))
        self.assertEqual((t["overtime_people"], t["overtime_hours"]), (19, 9.5))
        self.assertEqual((t["extra_people"], t["extra_hours"]), (49, 24.5))

    def test_sunday_2130_needs_one_more(self):
        row = next(r for r in view(REAL)["short"] if (r["day"], r["time"]) == ("Sun", "21:30"))
        self.assertEqual((row["need"], row["have"], row["pct"], row["people"], row["hours"]), (4, 3, 96, 1, 0.5))

    def test_no_demand_hours_fold(self):
        v = view(REAL)
        self.assertEqual(v["step"], 30)
        folds = [r["fold"] for r in v["grid"] if "fold" in r]
        self.assertEqual(folds, ["02:00 to 17:00"])
        first = v["grid"][0]
        self.assertEqual((first["time"], first["cells"][0]["pct"], first["cells"][0]["have"]), ("00:00", 134, 4))
        self.assertEqual(len(v["days_at_full"]), 7)

    def test_before_breaks_view(self):
        after, before = view(REAL), view(REAL, side="before")
        self.assertGreater(before["totals"]["full"], after["totals"]["full"])  # breaks cost coverage
        self.assertEqual(before["totals"]["full"], 125)

    def test_sixty_minute_week(self):
        hourly = [r for r in copy.deepcopy(REAL) if r[1].endswith(":00")]
        v = view(hourly)
        self.assertEqual(v["step"], 60)
        for row in v["short"] + v["extra"]:
            self.assertEqual(row["hours"], row["people"])  # one associate for one hour

    def test_nobody_on_the_floor(self):
        rows = copy.deepcopy(REAL)
        target = next(r for r in rows if r[2] > 0)
        target[3], target[4] = 0.0, 0  # demand, nobody after breaks
        row = next(r for r in view(rows)["short"] if r["time"] == target[1] and r["day"] == "SunMonTueWedThuFriSat"[target[0] * 3:target[0] * 3 + 3])
        self.assertGreaterEqual(row["need"], 1)
        self.assertEqual((row["have"], row["pct"]), (0, 0))

    def test_compact_holds_counts_and_times_only(self):
        for r in REAL:
            self.assertEqual(len(r), 8)
            self.assertIsInstance(r[1], str)
            self.assertTrue(all(isinstance(x, (int, float)) for x in (r[0], *r[2:])))


if __name__ == "__main__":
    unittest.main()
