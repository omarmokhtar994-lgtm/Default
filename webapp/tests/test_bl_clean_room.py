# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL: the clean-room check (tools/clean_room_check.py, which shares no code with the engine) knows the new Schedule columns.

A full engine run of a workbook with an 8.5 hour associate, part-timers with their own off days and one break each passed the independent
validator but was blocked by the clean-room check (off_count and break_set), because it still owed everyone two off days and the usual break
set. With the columns blank nothing changes. Made-up data (the example workbook's Synth Agent names)."""
import sys
import unittest
from pathlib import Path

from webapp.tests.test_bl_engine_parttime import workbook

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import clean_room_check as C  # noqa: E402


def contract(tmp, **columns):
    return C.read_contract(Path(workbook(tmp, columns=columns, durations="9, 8.5, 5")))


class TheCleanRoomKnowsTheColumns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.dir = tempfile.mkdtemp()

    def test_without_the_columns_everyone_owes_what_they_always_did(self):
        k = contract(self.dir)
        self.assertEqual(k.person, {n_: {"len": None, "off": None, "breaks": None, "part_time": False} for n_ in k.person})
        self.assertEqual(C.owed_off_days(k, C.n(k.names[0]), False, 7), 2)
        self.assertEqual(C.owed_off_days(k, C.n(k.names[0]), True, 7), 3)
        self.assertEqual(C.break_lengths_for(k, 540), [15, 15, 30])
        self.assertEqual(C.break_lengths_for(k, 300), [15, 15, 30])

    def test_off_days_replace_the_usual_two_for_that_person_and_leave_still_comes_out(self):
        k = contract(self.dir, **{"Off Days": {1: 4, 2: 1}})
        first, second, third = (C.n(x) for x in k.names[:3])
        self.assertEqual([C.owed_off_days(k, x, False, 7) for x in (first, second, third)], [4, 1, 2])
        self.assertEqual(C.owed_off_days(k, first, True, 7), 4)
        self.assertEqual(C.owed_off_days(k, first, False, 2), 2)       # 5 days of leave leave 2 to give

    def test_breaks_give_that_shift_length_the_first_n_breaks_in_shift_order(self):
        for n_breaks, want in ((1, [15]), (2, [15, 30]), (3, [15, 15, 30])):
            with self.subTest(breaks=n_breaks):
                k = contract(self.dir, **{"Shift Length": {1: 5}, "Breaks": {1: n_breaks}})
                self.assertEqual(C.break_lengths_for(k, 300), want)
                self.assertEqual(C.break_lengths_for(k, 540), [15, 15, 30])   # other lengths keep their own set

    def test_a_typed_break_set_for_long_shifts_is_cut_in_the_order_it_was_typed(self):
        k = contract(self.dir, **{"Shift Length": {1: 5}, "Breaks": {1: 2}})
        k.break_sets, k.break_sets_ordered = [(300, [15, 15, 15, 30])], [(300, [15, 30, 15, 15])]
        self.assertEqual(C.break_lengths_for(k, 300), [15, 30])

    def test_a_length_a_part_timer_claims_is_not_for_others(self):
        k = contract(self.dir, **{"Shift Length": {1: 5}, "Employment Type": {1: "Part time"}})
        sched = {C.n(name): ["OFF"] * 7 for name in k.names}
        sched[C.n(k.names[0])][1] = "09:00 - 14:00"        # the part-timer: fine
        sched[C.n(k.names[5])][2] = "09:00 - 14:00"        # a full-timer with no length of their own on the part-time shift
        sched[C.n(k.names[6])][2] = "09:00 - 18:00"        # and on an ordinary one
        found = [x for x in C.check(k, sched, [], set())["violations"] if x["rule"] == "part_time_shift"]
        self.assertEqual([(x["who"], x["day"]) for x in found], [(k.names[5], "tue")])

    def test_a_shift_of_another_length_is_flagged(self):
        k = contract(self.dir, **{"Shift Length": {1: 8.5}})
        sched = {C.n(name): ["OFF"] * 7 for name in k.names}
        sched[C.n(k.names[0])][1] = "09:00 - 18:00"       # nine hours for someone set to 8.5
        found = [x for x in C.check(k, sched, [], set())["violations"] if x["rule"] == "shift_length"]
        self.assertEqual([(x["who"], x["day"]) for x in found], [(k.names[0], "mon")])
        sched[C.n(k.names[0])][1] = "09:00 - 17:30"       # eight and a half is right
        self.assertEqual([x for x in C.check(k, sched, [], set())["violations"] if x["rule"] == "shift_length"], [])


if __name__ == "__main__":
    unittest.main()
