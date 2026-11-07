# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 2 (owner, 2026-11-07): an 8.5 hour shift, fixed per associate.

An associate whose Schedule row says ``Shift Length`` 8.5 may only be given library shifts of 8.5 hours, in every place the
engine picks or changes a shift (Stage 1, the joint refinement, the consistency polish and the preference swaps), and the
finished schedule is checked for it. A blank Shift Length changes nothing: the A/B rule is in
``evidence/phase_bl/ab_columns_blank.md`` (pre-registered before the run: with the new columns blank, Stage 1 on the
example workbook gives the same shifts as the engine before this phase).
An associate whose length has no shift in the library is refused by name before any solving.
Made-up "Associate NN" data (the example workbook's Synth Agent names)."""
import io
import sys
import unittest
from pathlib import Path

from openpyxl import load_workbook

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "engine" / "_tools"))
EXAMPLE = REPO / "webapp" / "workbooks" / "Scheduler_Input_Example.xlsx"
LONG = [("06:00 - 14:30", "06:00", "14:30"), ("08:00 - 16:30", "08:00", "16:30"), ("10:00 - 18:30", "10:00", "18:30"),
        ("12:00 - 20:30", "12:00", "20:30"), ("14:00 - 22:30", "14:00", "22:30")]


def workbook(tmp, lengths=None, durations="9, 8.5", library=True):
    """The example workbook with Allowed Shift Durations changed, 8.5 hour shifts added to the library and a Shift Length
    column on the Schedule sheet (``lengths``: associate row number from 1 -> hours)."""
    wb = load_workbook(EXAMPLE)
    for row in wb["Instructions"].iter_rows():
        if row[1].value == "Allowed Shift Durations Hours":
            row[2].value = durations
    lib = wb["Shift Library"]
    if library:
        last = max(r for r in range(1, lib.max_row + 1) if lib.cell(r, 1).value)
        for i, (label, start, end) in enumerate(LONG, 1):
            lib.cell(last + i, 1, label), lib.cell(last + i, 2, start), lib.cell(last + i, 3, end)
            lib.cell(last + i, 4, 8.5), lib.cell(last + i, 5, "8.5H")
    if lengths:
        ws = wb["Schedule"]
        col = ws.max_column + 1
        ws.cell(2, col, "Shift Length")
        for slot, hours in lengths.items():
            ws.cell(2 + slot, col, hours)
    path = Path(tmp) / "ex85.xlsx"
    wb.save(path)
    return str(path)


def parse(tmp, **kw):
    import l632_universal_scheduler as E
    return E, E.parse_input(workbook(tmp, **kw))


class TheEightAndAHalfHourShift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.dir = tempfile.mkdtemp()

    def test_the_library_holds_510_minute_shifts_when_the_duration_is_allowed(self):
        E, parsed = parse(self.dir)
        self.assertEqual(sorted({s.duration_min for s in parsed.shifts}), [510, 540])

    def test_an_associate_with_a_length_is_offered_only_shifts_of_that_length(self):
        E, parsed = parse(self.dir, lengths={1: 8.5, 2: 9})
        for day in range(7):
            self.assertEqual({s.duration_min for s in E.associate_day_eligible_shifts(parsed, parsed.associates[0], day)}, {510})
            self.assertEqual({s.duration_min for s in E.associate_day_eligible_shifts(parsed, parsed.associates[1], day)}, {540})
            self.assertEqual({s.duration_min for s in E.associate_day_eligible_shifts(parsed, parsed.associates[2], day)}, {510, 540})

    def test_the_polish_and_swap_steps_cannot_move_someone_to_another_length(self):
        E, parsed = parse(self.dir, lengths={1: 8.5})
        # shifts the demand-fit guard lets the unrestricted associate (row 2) take, so only the length can differ
        long_, nine = (next(s for s in parsed.shifts if s.duration_min == m and E._consistency_cell_allowed(parsed, 1, 1, s))
                       for m in (510, 540))
        self.assertTrue(E._consistency_cell_allowed(parsed, 0, 1, long_))
        self.assertFalse(E._consistency_cell_allowed(parsed, 0, 1, nine))
        self.assertTrue(E._consistency_cell_allowed(parsed, 1, 1, nine))

    def test_stage_1_gives_each_associate_only_their_length(self):
        E, parsed = parse(self.dir, lengths={1: 8.5, 2: 8.5, 3: 8.5, 4: 9})
        sk = E.build_skeleton(parsed, None, E.HardConfig(), 20.0, 2, io.StringIO(), random_seed=9000)
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        got = {a: {parsed.shifts[si].duration_min for si in sk.selected_shift_index[a] if si is not None} for a in range(4)}
        self.assertTrue(got[0] and got[1] and got[2] and got[3], got)
        self.assertEqual([got[0], got[1], got[2], got[3]], [{510}, {510}, {510}, {540}])

    def test_a_length_with_no_library_shift_is_refused_by_name(self):
        E, parsed = parse(self.dir, lengths={1: 7.5})
        failures = E.validate_input_contract(parsed)["failures"]
        found = [f for f in failures if f["code"] == "ASSOCIATE_SHIFT_LENGTH_NOT_IN_LIBRARY"]
        self.assertEqual([f["associate"] for f in found], [parsed.associates[0].name], failures)
        self.assertIn("7.5", found[0]["detail"])

    def test_a_length_the_duration_setting_does_not_allow_is_refused_with_the_fix(self):
        E, parsed = parse(self.dir, lengths={1: 8.5}, durations="9")
        found = [f for f in E.validate_input_contract(parsed)["failures"] if f["code"] == "ASSOCIATE_SHIFT_LENGTH_NOT_IN_LIBRARY"]
        self.assertEqual(len(found), 1)
        self.assertIn("Allowed Shift Durations Hours", found[0]["detail"])

    def test_a_finished_schedule_with_the_wrong_length_fails_the_check(self):
        E, parsed = parse(self.dir, lengths={1: 8.5})
        sk = E.build_skeleton(parsed, None, E.HardConfig(), 20.0, 2, io.StringIO(), random_seed=9000)
        nine = next(i for i, s in enumerate(parsed.shifts) if s.duration_min == 540)
        day = next(d for d, si in enumerate(sk.selected_shift_index[0]) if si is not None)
        sk.selected_shift_index[0][day] = nine
        failures = E.shift_length_failures(parsed, sk)
        self.assertTrue([f for f in failures if f["type"] == "shift_length" and f["associate"] == parsed.associates[0].name],
                        failures)


if __name__ == "__main__":
    unittest.main()
