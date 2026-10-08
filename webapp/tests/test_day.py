# © 2026 Omar Mokhtar. All rights reserved.
"""Phase N task 4: the day, from the schedule in use plus attendance and actual breaks.

The real Voice week in the repository (English and International, 30-minute
demand, Tuesday overnight shifts reaching into Wednesday). Names are read from
the workbook, never written here."""
import unittest
from pathlib import Path

from webapp.day import BreakRefused, check_break, day_view, read_inputs
from webapp.versions import DAYS, read_week, shift_span

REPO = Path(__file__).resolve().parents[2]
VOICE = REPO / "fixtures" / "real_runs" / "language_hours" / "VOICE_FINAL_SHEET_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"
WEEK = read_week(VOICE)
INPUTS = read_inputs(VOICE)
WED = 3


def at(view, hhmm):
    h, m = map(int, hhmm.split(":"))
    return next(c for c in view["cells"] if c["t"] == h * 60 + m)


def minute(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def someone(day, covering, starts_by=None):
    """A person whose shift that day covers the given half-hour and who has no break
    within two hours of it; with ``starts_by``, one whose shift starts by then and who
    has no break in its first half-hour or in the given one."""
    for a in WEEK["associates"]:
        span = shift_span(a["days"][day])
        if not span or not (span[0] <= covering and covering + 30 <= span[1]):
            continue
        mine = [(minute(b["start"]) + (1440 if minute(b["start"]) < span[0] else 0), b["minutes"])
                for b in WEEK["breaks"] if b["associate"] == a["name"] and b["day"] == DAYS[day]]
        if starts_by is None:
            clash = [s for s, m in mine if abs(s - covering) < 120]
        elif span[0] > starts_by:
            continue
        else:
            clash = [s for s, m in mine for lo in (span[0], covering) if s < lo + 30 and lo < s + m]
        if not clash:
            return a, span
    raise AssertionError("nobody found")


class TheDay(unittest.TestCase):
    def view(self, attendance=None, actual=None):
        return day_view(WEEK, INPUTS, WED, attendance or {}, actual or {})

    def test_overnight_carry_in_counts(self):
        tuesday_night = [a for a in WEEK["associates"] if (shift_span(a["days"][2]) or (0, 0))[1] > 1440]
        self.assertTrue(tuesday_night)
        self.assertFalse([a for a in WEEK["associates"] if (shift_span(a["days"][WED]) or (99, 0))[0] < 30])
        # 00:00 to 00:30 is Tuesday's night shift alone: each person counts for the
        # 5-minute steps they are not on a Tuesday break (breaks after midnight read +24h)
        expected = 0.0
        for a in tuesday_night:
            start = shift_span(a["days"][2])[0]
            away = [(minute(b["start"]) + (1440 if minute(b["start"]) < start else 0) - 1440, b["minutes"])
                    for b in WEEK["breaks"] if b["associate"] == a["name"] and b["day"] == "Tue"]
            expected += sum(1 for t in range(0, 30, 5) if not any(s <= t < s + m for s, m in away)) / 6
        self.assertAlmostEqual(at(self.view(), "00:00")["plan"], round(expected, 1))
        lanes = {l["name"]: l for l in self.view()["lanes"]}
        self.assertTrue(any(s["offset"] == -1 for s in lanes[tuesday_night[0]["name"]]["segments"]))

    def test_unplanned_leave_lowers_the_floor(self):
        person, span = someone(WED, 20 * 60)
        v = self.view({(0, person["name"]): {"status": "Unplanned leave"}})
        cell = at(v, "20:00")
        self.assertEqual(cell["now"], cell["plan"] - 1)
        self.assertEqual(v["tiles"]["absent"], 1)

    def test_late_counts_from_arrival(self):
        person, span = someone(WED, 20 * 60, starts_by=18 * 60 + 30)
        late = {(0, person["name"]): {"status": "Late", "to": span[0] + 60}}
        v = self.view(late)
        first = at(v, f"{span[0] // 60:02d}:{span[0] % 60:02d}")
        self.assertEqual(first["now"], first["plan"] - 1)
        self.assertEqual(at(v, "20:00")["now"], at(v, "20:00")["plan"])

    def test_moved_break_changes_two_intervals(self):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed" and b["kind"] == "Lunch" and b["start"].endswith(":00"))
        person = b["associate"]
        lanes = {l["name"]: l for l in self.view()["lanes"]}
        idx = next(x["idx"] for s in lanes[person]["segments"] if s["offset"] == 0 for x in s["breaks"] if x["kind"] == "Lunch")
        start = int(b["start"][:2]) * 60 + int(b["start"][3:])
        v = self.view(actual={(0, person, idx): start + 60})
        self.assertEqual(at(v, b["start"])["now"], at(v, b["start"])["plan"] + 1)
        moved = f"{(start + 60) // 60:02d}:{(start + 60) % 60:02d}"
        self.assertEqual(at(v, moved)["now"], at(v, moved)["plan"] - 1)
        self.assertTrue(next(x for s in {l["name"]: l for l in v["lanes"]}[person]["segments"] if s["offset"] == 0
                             for x in s["breaks"] if x["idx"] == idx)["moved"])

    def test_break_must_stay_inside_the_shift(self):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed")
        person = next(a for a in WEEK["associates"] if a["name"] == b["associate"])
        span = shift_span(person["days"][WED])
        with self.assertRaises(BreakRefused):
            check_break(WEEK, WED, 0, person["name"], 0, span[1] - 5, {})  # would run past the shift's end
        with self.assertRaises(BreakRefused):
            check_break(WEEK, WED, 0, person["name"], 0, span[0] + 7, {})  # not a 5-minute step
        check_break(WEEK, WED, 0, person["name"], 0, span[0] + 120, {})  # fine

    def test_five_minute_steps_only(self):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed")
        span = shift_span(next(a for a in WEEK["associates"] if a["name"] == b["associate"])["days"][WED])
        for step in (1, 2, 3, 4, 7, 13):
            with self.assertRaises(BreakRefused):
                check_break(WEEK, WED, 0, b["associate"], 0, span[0] + 120 + step, {})
        check_break(WEEK, WED, 0, b["associate"], 0, span[0] + 125, {})

    def test_break_may_not_overlap_another(self):
        breaks = [b for b in WEEK["breaks"] if b["day"] == "Wed"]
        name = breaks[0]["associate"]
        mine = [b for b in breaks if b["associate"] == name]
        second = int(mine[1]["start"][:2]) * 60 + int(mine[1]["start"][3:])
        with self.assertRaises(BreakRefused):
            check_break(WEEK, WED, 0, name, 0, second, {})

    def test_language_rows(self):
        rows = {r["name"]: r for r in self.view()["languages"]}
        self.assertEqual(set(rows), {"English", "International"})
        intl = rows["International"]
        self.assertEqual((intl["start"], intl["end"]), (0, 16 * 60))
        inside = [c for c in intl["cells"] if c["count"] is not None]
        self.assertEqual(len(inside), 32)  # 00:00 to 16:00 in half-hours
        self.assertIsNone(next(c for c in rows["English"]["cells"] if c["t"] == 12 * 60)["count"])  # outside English hours

    def test_tiles_sum_the_cells(self):
        v = self.view()
        short = sum(-c["pm"] for c in v["cells"] if c["pm"] is not None and c["pm"] < 0)
        self.assertAlmostEqual(v["tiles"]["short_hours"], round(short, 1), places=1)
        self.assertEqual(v["interval"], 30)


if __name__ == "__main__":
    unittest.main()
