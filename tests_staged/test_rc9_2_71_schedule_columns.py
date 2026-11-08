"""Phase BL (owner, 2026-11-07): optional Schedule-sheet columns, in the release gate.

``Shift Length`` (hours), ``Employment Type`` (Full time or Part time), ``Off Days`` and ``Breaks Per Day`` per associate. Blank or absent they change nothing; a
value that cannot be read is refused by name; the shift length is a hard rule everywhere a shift is chosen; Off Days replaces the usual two; Breaks Per Day gives a
shift length the first N breaks of its set; a shift length a Part time row names is for part-timers. The engine and the clean-room check (which shares no code with
it) must agree on every one of these, or a real run passes one and is blocked by the other (it was, before this suite).

Built on copies of a protected baseline workbook: the original is read, never changed."""
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
sys.path.insert(0, str(next(p for p in (ROOT / "tools", REPO / "tools") if (p / "clean_room_check.py").exists())))
import l632_universal_scheduler as E  # noqa: E402
import clean_room_check as C  # noqa: E402

INPUTS = next(p for p in (ROOT / "inputs", REPO / "packages" / "rc9_2_2_production" / "inputs") if p.exists())
BOOK = INPUTS / "NMG_SP_RC9_1_READY_FIXED.xlsx"
LONG = [("06:00 - 14:30", "06:00", "14:30"), ("08:00 - 16:30", "08:00", "16:30"), ("10:00 - 18:30", "10:00", "18:30"), ("12:00 - 20:30", "12:00", "20:30")]
SHORT = [("09:00 - 14:00", "09:00", "14:00"), ("12:00 - 17:00", "12:00", "17:00"), ("15:00 - 20:00", "15:00", "20:00")]
NEW = ("shift_minutes", "part_time", "off_days", "breaks_per_day")


def variant(tmp, columns=None, durations="9, 8.5, 5", extra=True):
    """A copy of the baseline with durations changed, 8.5 and 5 hour shifts in the library and ``columns`` (header -> {associate number from 1: value}) added."""
    wb = load_workbook(BOOK)
    if durations:
        for row in wb["Instructions"].iter_rows():
            if row[1].value == "Allowed Shift Durations Hours":
                row[2].value = durations
    lib = wb["Shift Library"]
    if extra:
        last = max(r for r in range(1, lib.max_row + 1) if lib.cell(r, 1).value)
        for i, (label, start, end) in enumerate(LONG + SHORT, 1):
            hours = 8.5 if (label, start, end) in LONG else 5
            for c, v in enumerate((label, start, end, hours, "x"), 1):
                lib.cell(last + i, c, v)
    ws = wb["Schedule"]
    head = 2
    col = ws.max_column + 1
    for header, values in (columns or {}).items():
        ws.cell(head, col, header)
        for number, value in values.items():
            ws.cell(head + number, col, value)
        col += 1
    path = Path(tmp) / f"variant_{random.random():.9f}.xlsx"
    wb.save(path)
    return path


def new(a):
    return tuple(getattr(a, n) for n in NEW)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)


class TheColumns(_Base):
    def parse(self, **kw):
        return E.parse_input(variant(self.tmp, **kw))

    def test_the_baseline_reads_as_it_always_did(self):
        parsed = E.parse_input(BOOK)
        self.assertTrue(all(new(a) == (None, False, None, None) for a in parsed.associates))
        self.assertFalse([w for w in parsed.parser_warnings if any(x in str(w) for x in ("SHIFT_LENGTH", "ASSOCIATE_TYPE", "OFF_DAYS", "BREAKS"))])
        self.assertTrue(all(not s.part_time_only for s in parsed.shifts))

    def test_the_columns_are_read(self):
        parsed = self.parse(columns={"Shift Length": {1: 8.5, 2: "5 h"}, "Employment Type": {2: "Part time", 3: "Full time"},
                                     "Off Days": {2: 4, 3: "3"}, "Breaks Per Day": {2: 1}})
        self.assertEqual([new(a) for a in parsed.associates[:3]], [(510, False, None, None), (300, True, 4, 1), (None, False, 3, None)])

    def test_a_value_that_cannot_be_read_is_refused_by_name(self):
        for header, value, code in (("Shift Length", "x", "HARD_INVALID_SHIFT_LENGTH"), ("Shift Length", 20, "HARD_INVALID_SHIFT_LENGTH"),
                                    ("Employment Type", "casual", "HARD_INVALID_ASSOCIATE_TYPE"), ("Off Days", 7, "HARD_INVALID_OFF_DAYS"),
                                    ("Off Days", 1.5, "HARD_INVALID_OFF_DAYS"), ("Breaks Per Day", -1, "HARD_INVALID_BREAKS")):
            with self.subTest(header=header, value=value):
                parsed = self.parse(columns={header: {1: value}})
                self.assertTrue([w for w in parsed.parser_warnings if str(w).startswith(code)], parsed.parser_warnings)

    def test_a_column_only_called_type_or_breaks_is_not_ours(self):
        parsed = self.parse(columns={"Type": {1: "contractor"}, "Breaks": {1: "12:00"}})
        self.assertTrue(all(new(a) == (None, False, None, None) for a in parsed.associates))
        self.assertFalse([w for w in parsed.parser_warnings if str(w).startswith("HARD_INVALID")])

    def test_a_shift_length_is_a_hard_rule_for_that_person_only(self):
        parsed = self.parse(columns={"Shift Length": {1: 8.5}})
        for day in range(7):
            self.assertEqual({s.duration_min for s in E.associate_day_eligible_shifts(parsed, parsed.associates[0], day)}, {510})
        self.assertTrue(E.shift_length_allows(parsed.associates[1], parsed.shifts[0]))
        long_ = next(s for s in parsed.shifts if s.duration_min == 510)
        nine = next(s for s in parsed.shifts if s.duration_min == 540)
        self.assertTrue(E.shift_length_allows(parsed.associates[0], long_))
        self.assertFalse(E.shift_length_allows(parsed.associates[0], nine))

    def test_a_length_the_library_lacks_is_refused_with_the_fix(self):
        parsed = self.parse(columns={"Shift Length": {1: 7.5}})
        found = [f for f in E.validate_input_contract(parsed)["failures"] if f["code"] == "ASSOCIATE_SHIFT_LENGTH_NOT_IN_LIBRARY"]
        self.assertEqual(len(found), 1)
        self.assertIn("Allowed Shift Durations Hours", found[0]["detail"])

    def test_a_length_a_part_timer_names_is_for_part_timers(self):
        parsed = self.parse(columns={"Shift Length": {1: 5, 3: 5}, "Employment Type": {1: "Part time", 2: "Part time"}})
        durations = lambda row: {s.duration_min for d in range(7) for s in E.associate_day_eligible_shifts(parsed, parsed.associates[row - 1], d)}  # noqa: E731
        self.assertEqual(durations(1), {300})
        self.assertEqual(durations(3), {300})                       # a length on the row is theirs, whatever their type
        self.assertIn(300, durations(2))                            # a part-timer with no length may work anything
        self.assertNotIn(300, durations(4))                         # everyone else is kept off it
        self.assertTrue(all(s.part_time_only for s in parsed.shifts if s.duration_min == 300))

    def test_off_days_replace_the_usual_two_for_that_person(self):
        parsed = self.parse(columns={"Off Days": {1: 4, 2: 1}})
        owed = [E.required_off_days(parsed, a, False) for a in parsed.associates[:3]]
        self.assertEqual(owed[:2], [min(4, 7 - E.pinned_leave_days(parsed, parsed.associates[0])), min(1, 7 - E.pinned_leave_days(parsed, parsed.associates[1]))])
        self.assertEqual(owed[2], E.required_off_days(E.parse_input(BOOK), E.parse_input(BOOK).associates[2], False))

    def test_breaks_per_day_give_a_shift_length_the_first_breaks_of_its_set(self):
        base = E.parse_input(variant(self.tmp))
        parsed = self.parse(columns={"Shift Length": {1: 5}, "Breaks Per Day": {1: 1}})
        self.assertEqual(E.break_segments_for(parsed, 300), E.break_segments_for(base, 300)[:1])
        self.assertEqual(E.break_segments_for(parsed, 540), E.break_segments_for(base, 540))
        zero = self.parse(columns={"Shift Length": {1: 5}, "Breaks Per Day": {1: 0}})
        self.assertEqual(E.break_segments_for(zero, 300), ())

    def test_breaks_that_cannot_be_given_are_refused_by_name(self):
        cases = (({"Breaks Per Day": {1: 1}}, "HARD_BREAKS_NEED_SHIFT_LENGTH"),
                 ({"Shift Length": {1: 5, 2: 5}, "Breaks Per Day": {1: 1, 2: 2}}, "HARD_BREAKS_CONFLICT"),
                 ({"Shift Length": {1: 5}, "Breaks Per Day": {1: 6}}, "HARD_BREAKS_EXCEED_SET"))
        for columns, code in cases:
            with self.subTest(code=code):
                parsed = self.parse(columns=columns)
                self.assertTrue([w for w in parsed.parser_warnings if str(w).startswith(code)], parsed.parser_warnings)


class TheEngineAndTheCleanRoomAgree(_Base):
    """The two implementations, written apart, on random columns: same off days owed, same breaks for a shift of each length, same view of who may work which shift."""

    def test_random_columns(self):
        compared = 0
        for seed in range(25):
            r = random.Random(20261107 + seed)
            rows = r.sample(range(1, 21), r.randrange(2, 9))
            lengths = {n: r.choice([5, 8.5, 9, None]) for n in rows}
            columns = {"Shift Length": {n: v for n, v in lengths.items() if v},
                       "Employment Type": {n: r.choice(["Part time", "Full time", None]) for n in rows},
                       "Off Days": {n: r.choice([0, 1, 2, 3, 4, None]) for n in rows},
                       "Breaks Per Day": {n: r.choice([0, 1, 2, 3, None]) for n in rows if lengths[n]}}
            path = variant(self.tmp, columns=columns)
            parsed = E.parse_input(path)
            if any(str(w).startswith("HARD_") for w in parsed.parser_warnings):
                continue                                                     # the engine refuses this one (a conflict, say): nothing to agree on
            k = C.read_contract(path)
            compared += 1
            for a in parsed.associates:
                key = C.n(a.name)
                room = 7 - E.pinned_leave_days(parsed, a)
                self.assertEqual(E.required_off_days(parsed, a, False), C.owed_off_days(k, key, False, room), f"seed {seed} {a.name} off days")
                self.assertEqual(k.person[key]["len"], a.shift_minutes, f"seed {seed} {a.name} length")
                self.assertEqual(k.person[key]["part_time"], a.part_time, f"seed {seed} {a.name} type")
                for s in parsed.shifts:
                    theirs_reserved = any(abs(s.duration_min - m) <= 5 for m in k.part_time_lengths)
                    if a.shift_minutes is None:
                        want = not (theirs_reserved and not a.part_time)
                    else:
                        want = abs(s.duration_min - a.shift_minutes) <= 5
                    self.assertEqual(E.shift_length_allows(a, s), want, f"seed {seed} {a.name} {s.label}")
            for minutes in (300, 510, 540):
                engine = sorted(q * 15 for q, _ in E.break_segments_for(parsed, minutes))
                self.assertEqual(engine, C.break_lengths_for(k, minutes), f"seed {seed} breaks for {minutes} minutes")
        self.assertGreater(compared, 10, "enough random cases were valid to compare")


if __name__ == "__main__":
    unittest.main()
