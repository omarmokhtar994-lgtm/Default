# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 3 (owner, 2026-11-07): part-time associates.

On the Schedule sheet a part-timer's row may say ``Type`` Part time, a ``Shift Length`` (hours), ``Off Days`` (how many days off in
the week) and ``Breaks`` (how many breaks on a shift). Rules, each pinned below:

- Off Days replaces the usual 2 (3 on the 11H/3OFF pattern) for that person only, in Stage 1, the joint refinement, the finished
  schedule's check (it asks ``required_off_days``) and the input contract. Days of leave still come out of the same seven days.
- Breaks N gives the shift length on that row the first N breaks of the break set it would have had, through the engine's existing
  "break set by shift length" rule, so every stage and report follows it. Two rows with the same Shift Length and different Breaks,
  Breaks without a Shift Length, and more Breaks than the shift's break set has are refused by name.
- With these columns blank nothing changes (A/B in evidence/phase_bl/ab_columns_blank.md).
Made-up "Associate NN" data (the example workbook's Synth Agent names)."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "engine" / "_tools"))
EXAMPLE = REPO / "webapp" / "workbooks" / "Scheduler_Input_Example.xlsx"
FIVE_HOUR = [("09:00 - 14:00", "09:00", "14:00"), ("12:00 - 17:00", "12:00", "17:00"), ("15:00 - 20:00", "15:00", "20:00"),
             ("17:00 - 22:00", "17:00", "22:00")]


def workbook(tmp, columns=None, durations="9, 5"):
    """The example workbook with 5 hour shifts in the library and optional Schedule columns: ``columns`` maps a header to
    {associate number from 1: value}."""
    wb = load_workbook(EXAMPLE)
    for row in wb["Instructions"].iter_rows():
        if row[1].value == "Allowed Shift Durations Hours":
            row[2].value = durations
    lib = wb["Shift Library"]
    last = max(r for r in range(1, lib.max_row + 1) if lib.cell(r, 1).value)
    for i, (label, start, end) in enumerate(FIVE_HOUR, 1):
        lib.cell(last + i, 1, label), lib.cell(last + i, 2, start), lib.cell(last + i, 3, end)
        lib.cell(last + i, 4, 5), lib.cell(last + i, 5, "5H")
    ws = wb["Schedule"]
    for header, values in (columns or {}).items():
        col = ws.max_column + 1
        ws.cell(2, col, header)
        for number, value in values.items():
            ws.cell(2 + number, col, value)
    path = Path(tmp) / "parttime.xlsx"
    wb.save(path)
    return str(path)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()

    def parse(self, **kw):
        import l632_universal_scheduler as E
        return E, E.parse_input(workbook(self.dir, **kw))


class TheOffDays(_Base):
    def test_the_sheet_replaces_the_usual_two_off_days_for_that_person_only(self):
        E, parsed = self.parse(columns={"Off Days": {1: 4, 2: 1}})
        got = [E.required_off_days(parsed, a, False) for a in parsed.associates[:4]]
        self.assertEqual(got, [4, 1, 2, 2])
        self.assertEqual(E.required_off_days(parsed, parsed.associates[0], True), 4)  # not 3 + more: the sheet decides

    def test_leave_days_still_come_out_of_the_same_seven_days(self):
        E, parsed = self.parse(columns={"Off Days": {1: 4}})
        a = parsed.associates[0]
        a.preferences = ["Leave"] * 5 + [""] * 2
        parsed.leave_enabled = True
        self.assertEqual(E.required_off_days(parsed, a, False), 2)  # 7 - 5 leave days = 2 left to give

    def test_stage_1_gives_each_part_timer_exactly_their_off_days(self):
        E, parsed = self.parse(columns={"Off Days": {1: 4, 2: 4, 3: 1}})
        self.assertTrue(parsed.strict_off)
        sk = E.build_skeleton(parsed, None, E.HardConfig(), 30.0, 2, io.StringIO(), random_seed=9000)
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        offs = [sum(sk.assignment[a][d] == "OFF" for d in range(7)) for a in range(5)]
        self.assertEqual(offs, [4, 4, 1, 2, 2])

    def test_capacity_estimates_count_the_days_a_part_timer_really_works(self):
        E, parsed = self.parse(columns={"Off Days": {1: 4, 2: 1}})
        a, b, c = parsed.associates[:3]
        self.assertEqual([E.associate_workdays(parsed, x) for x in (a, b, c)], [3, 6, E.default_workdays_per_week(parsed)])


class TheShiftsAPartTimerClaims(_Base):
    """A shift length a part-time row names is for part-timers: someone with no length of their own is not given it (a full-timer working a 5 hour
    shift was seen in a real run). A part-timer with no length may work anything, and an explicit Shift Length is always honoured."""

    def eligible(self, E, parsed, row):
        a = parsed.associates[row - 1]
        return {s.duration_min for d in range(7) for s in E.associate_day_eligible_shifts(parsed, a, d)}

    def test_others_are_not_given_the_part_time_length(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5, 2: 5}, "Employment Type": {1: "Part time", 2: "Part time"}})
        self.assertEqual(self.eligible(E, parsed, 1), {300})                  # the part-timer: their length only
        self.assertEqual(self.eligible(E, parsed, 3), {540})                  # everyone else: not the 5 hour shifts
        self.assertTrue(all(s.part_time_only for s in parsed.shifts if s.duration_min == 300))
        self.assertFalse(any(s.part_time_only for s in parsed.shifts if s.duration_min == 540))

    def test_a_part_timer_with_no_length_may_work_anything_and_an_explicit_length_is_honoured(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5, 3: 5}, "Employment Type": {1: "Part time", 2: "Part time"}})
        self.assertEqual(self.eligible(E, parsed, 2), {300, 540})             # part time, no length of their own
        self.assertEqual(self.eligible(E, parsed, 3), {300})                  # a length on the row is theirs, whatever their type

    def test_a_full_time_row_with_a_length_does_not_reserve_it(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5}, "Employment Type": {1: "Full time"}})
        self.assertFalse(any(s.part_time_only for s in parsed.shifts))
        self.assertEqual(self.eligible(E, parsed, 2), {300, 540})

    def test_nothing_changes_without_part_time_rows(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5}})
        self.assertFalse(any(s.part_time_only for s in parsed.shifts))

    def test_stage_1_keeps_the_others_off_the_part_time_shifts(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5, 2: 5, 3: 5}, "Employment Type": {1: "Part time", 2: "Part time", 3: "Part time"},
                                        "Off Days": {1: 3, 2: 3, 3: 3}})
        sk = E.build_skeleton(parsed, None, E.HardConfig(), 30.0, 2, io.StringIO(), random_seed=9000)
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        others = {parsed.shifts[si].duration_min for a in range(3, len(parsed.associates)) for si in sk.selected_shift_index[a] if si is not None}
        self.assertEqual(others, {540})


class TheBreaks(_Base):
    def test_the_shift_length_on_the_row_gets_the_first_n_breaks_of_its_set(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5}, "Employment Type": {1: "Part time"}, "Breaks Per Day": {1: 1}})
        before = E.break_segments_for(E.parse_input(workbook(self.dir)), 300)
        self.assertEqual(E.break_segments_for(parsed, 300), before[:1])
        self.assertEqual(len(E.break_segments_for(parsed, 300)), 1)

    def test_other_shift_lengths_keep_their_own_break_set(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5}, "Breaks Per Day": {1: 1}})
        plain = E.parse_input(workbook(self.dir))
        for minutes in (300, 540):
            if minutes != 300:
                self.assertEqual(E.break_segments_for(parsed, minutes), E.break_segments_for(plain, minutes))
        self.assertEqual(parsed.break_segments_q, plain.break_segments_q)

    def test_two_rows_with_one_shift_length_and_different_breaks_are_refused_by_name(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5, 2: 5}, "Breaks Per Day": {1: 1, 2: 2}})
        self.assertTrue([w for w in parsed.parser_warnings if str(w).startswith("HARD_BREAKS_CONFLICT")
                         and "Synth Agent 001" in str(w) and "Synth Agent 002" in str(w)], parsed.parser_warnings)

    def test_breaks_without_a_shift_length_are_refused_by_name(self):
        E, parsed = self.parse(columns={"Breaks Per Day": {1: 1}})
        self.assertTrue([w for w in parsed.parser_warnings if str(w).startswith("HARD_BREAKS_NEED_SHIFT_LENGTH")
                         and "Synth Agent 001" in str(w)], parsed.parser_warnings)

    def test_more_breaks_than_the_break_set_has_is_refused_by_name(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5}, "Breaks Per Day": {1: 6}})
        self.assertTrue([w for w in parsed.parser_warnings if str(w).startswith("HARD_BREAKS_EXCEED_SET")
                         and "Synth Agent 001" in str(w)], parsed.parser_warnings)

    def test_a_part_timer_with_one_break_is_planned_one_break_end_to_end(self):
        E, parsed = self.parse(columns={"Shift Length": {1: 5}, "Employment Type": {1: "Part time"}, "Breaks Per Day": {1: 1}, "Off Days": {1: 3}})
        sk = E.build_skeleton(parsed, None, E.HardConfig(), 30.0, 2, io.StringIO(), random_seed=9000)
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        worked = [parsed.shifts[si] for si in sk.selected_shift_index[0] if si is not None]
        self.assertEqual({s.duration_min for s in worked}, {300})
        self.assertEqual(sum(d is not None for d in sk.selected_shift_index[0]), 4)
        self.assertEqual(len(E.break_segments_for(parsed, 300)), 1)


if __name__ == "__main__":
    unittest.main()
