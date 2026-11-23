# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "while adding it, state the count of breaks, how many shorts and how many lunches; if not, keep 0;
if there, plan it automatically"): the form that adds overtime or a call-in takes a number of short breaks and of lunches. 0 and 0
(the default) adds nothing; any other count is placed at once by the planner behind Plan breaks automatically, with everyone else's
breaks where they are, inside the stretch the overtime or the call-in covers. The lengths are the workbook's (a short break and
a lunch). One Undo takes the record and its breaks back. Made-up names, Wednesday 14 Oct."""
import unittest

from webapp.break_plan import break_minutes
from webapp.tests import test_attendance as ta
from webapp.tests.test_attendance import WED

AR = "AE/AR B2B"
OFF = "Associate 004"
WORKER = "Associate 001"


class TheExtraBreaks(unittest.TestCase):
    setUpClass = classmethod(ta.TheAttendance.setUpClass.__func__)
    tearDownClass = classmethod(ta.TheAttendance.tearDownClass.__func__)
    setUp = ta.TheAttendance.setUp

    def made(self, name):
        return sorted((r["start"], r["end_min"], r["kind"]) for r in self.store.list_activities(AR, [WED.isoformat()])
                      if r["associate"] == name and r["kind"] in ("Break", "Lunch"))

    def lengths(self):
        return break_minutes(self.book.break_rules(self.tool["id"]))

    def test_the_workbooks_short_break_and_lunch_lengths_are_read(self):
        short, lunch = self.lengths()
        self.assertTrue(short and lunch, (short, lunch))

    def test_a_call_in_gets_the_counts_asked_for(self):
        short, lunch = self.lengths()
        self.days.add_activity(AR, WED, OFF, "Called in", "10:00", "18:00", self.sara)
        made = self.days.plan_extra_breaks(AR, WED, OFF, 2, 1, self.sara)
        self.assertEqual(len(made), 3)
        got = self.made(OFF)
        self.assertEqual(sorted(k for _, _, k in got), ["Break", "Break", "Lunch"])
        for start, end, kind in got:
            self.assertEqual(end - start, lunch if kind == "Lunch" else short)
            self.assertTrue(10 * 60 <= start and end <= 18 * 60, (start, end))
        for (a0, a1, _), (b0, b1, _) in zip(got, got[1:]):
            self.assertLessEqual(a1, b0)

    def test_overtime_gets_its_breaks_inside_the_overtime_stretch(self):
        self.days.add_activity(AR, WED, WORKER, "Overtime", "21:00", "00:00", self.sara)
        before = self.made(WORKER)
        made = self.days.plan_extra_breaks(AR, WED, WORKER, 1, 0, self.sara)
        self.assertEqual(len(made), 1)
        new = [x for x in self.made(WORKER) if x not in before]
        self.assertEqual(len(new), 1)
        self.assertTrue(21 * 60 <= new[0][0] and new[0][1] <= 24 * 60, new)

    def test_zero_and_zero_asks_for_nothing_and_a_negative_or_huge_count_is_refused(self):
        self.days.add_activity(AR, WED, OFF, "Called in", "10:00", "18:00", self.sara)
        self.assertEqual(self.days.plan_extra_breaks(AR, WED, OFF, 0, 0, self.sara), [])
        self.assertEqual(self.made(OFF), [])
        for bad in ((-1, 0), (0, -1), (9, 0), (0, 5)):
            with self.assertRaises(ValueError):
                self.days.plan_extra_breaks(AR, WED, OFF, *bad, self.sara)

    def test_a_person_with_neither_overtime_nor_call_in_is_refused(self):
        with self.assertRaises(ValueError) as said:
            self.days.plan_extra_breaks(AR, WED, WORKER, 1, 0, self.sara)
        self.assertIn("overtime", str(said.exception))

    def test_one_undo_takes_back_the_breaks(self):
        self.days.add_activity(AR, WED, OFF, "Called in", "10:00", "18:00", self.sara)
        self.days.plan_extra_breaks(AR, WED, OFF, 1, 1, self.sara)
        self.days.undo_last(AR, WED, self.sara)
        self.assertEqual(self.made(OFF), [])
        self.assertIsNotNone(self.days.called_in_on(AR, WED, OFF))


class TheForms(unittest.TestCase):
    """The two forms that add overtime or a call-in carry the counts (through the website, Wednesday 14 Oct)."""

    @classmethod
    def setUpClass(cls):
        from webapp.tests.test_overtime_side import _Overtime
        cls.o = _Overtime
        cls.o.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.o.tearDownClass()

    def setUp(self):
        self.o.app.config["TODAY"] = WED
        self.addCleanup(self.clear)

    def clear(self):
        for r in self.o.store.list_activities(self.o.key, [WED.isoformat()]):
            self.o.store.delete_activity(r["id"])

    def acts(self, name):
        return sorted(r["kind"] for r in self.o.store.list_activities(self.o.key, [WED.isoformat()]) if r["associate"] == name)

    def post(self, **more):
        from webapp.tests.test_runs import token
        return self.o.client.post("/day/activity", data={"csrf_token": token(self.o.client), "program": self.o.key,
                                                         "date": WED.isoformat(), "view": "cover", **more}, follow_redirects=True)

    def test_a_call_in_form_with_counts_places_them_at_once(self):
        self.post(associate=OFF, kind="Called in", **{"from": "10:00", "to": "18:00"}, shorts="2", lunches="1")
        self.assertEqual(self.acts(OFF), ["Break", "Break", "Called in", "Lunch"])

    def test_the_default_zero_adds_no_breaks(self):
        self.post(associate=OFF, kind="Called in", **{"from": "10:00", "to": "18:00"}, shorts="0", lunches="0")
        self.assertEqual(self.acts(OFF), ["Called in"])
        self.clear()
        self.post(associate=OFF, kind="Called in", **{"from": "10:00", "to": "18:00"})  # the field missing altogether
        self.assertEqual(self.acts(OFF), ["Called in"])

    def test_the_add_dialog_has_the_two_fields(self):
        got = self.o.client.get("/day", query_string={"program": self.o.key, "date": WED.isoformat(), "view": "board", "add": "480",
                                                      "person": "Associate 008"})
        body = got.get_data(as_text=True)
        self.assertRegex(body, r'name="shorts"[^>]*value="0"')
        self.assertRegex(body, r'name="lunches"[^>]*value="0"')

    def test_overtime_through_the_form_with_one_short_break(self):
        self.post(associate="Associate 021", kind="Overtime", **{"from": "17:00", "to": "20:00"}, shorts="1", lunches="0")
        self.assertEqual(self.acts("Associate 021"), ["Break", "Overtime"])

    def test_a_refused_count_keeps_the_record_and_says_why(self):
        got = self.post(associate=OFF, kind="Called in", **{"from": "10:00", "to": "18:00"}, shorts="9", lunches="0")
        self.assertEqual(self.acts(OFF), ["Called in"])
        self.assertIn("Recorded, but the breaks were not planned", got.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
