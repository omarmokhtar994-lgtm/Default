# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI (owner, 2026-10-15): exam leave.

"we need to add exam leave as something as well and not to be counted in Sutherland shrinkage but in client
shrinkage"; asked how, the owner answered "both": an associate asks for it under Leave and swaps (the TM, then the
RTA, approves; the schedule gets Leave), and the RTA marks it for the whole shift. Either way it counts in the
client's out-of-office shrinkage and not in Sutherland's (a program setting, like the rest). An approved Public
holiday request is also counted as a public holiday, not as planned leave (the owner's formula of 2026-10-14).
Made-up "Associate NN" data.
"""
import re
import unittest

from webapp.attendance import ADD_KINDS
from webapp.day import ABSENT, STATUSES, day_view, hover_tips
from webapp.leave import KINDS
from webapp.shrinkage import day_shrinkage, read_mapping
from webapp.tests.test_af_shrinkage import WED as SWED, lane, seg, week_of
from webapp.tests.test_ag_leave import TUE, WED
from webapp.tests.test_day import INPUTS, WED as DWED, WEEK


class TheRtaMark(unittest.TestCase):
    def test_a_whole_shift_absence_the_rta_can_record(self):
        self.assertIn("Exam leave", STATUSES)
        self.assertIn("Exam leave", ABSENT)
        self.assertIn("Exam leave", ADD_KINDS["Attendance"])

    def test_the_person_is_off_the_floor_all_shift(self):
        base = day_view(WEEK, INPUTS, DWED, {}, {})
        lane0, s = next((l, x) for l in base["lanes"] for x in l["segments"] if x["offset"] == 0)
        view = day_view(WEEK, INPUTS, DWED, {(0, lane0["name"]): {"status": "Exam leave", "from": None, "to": None}}, {})
        self.assertLess(sum(c["now"] for c in view["cells"]), sum(c["now"] for c in base["cells"]))
        lines = hover_tips(view, s["start"] + 60)[(lane0["name"], 0)]["shift"]
        self.assertIn("Exam leave: not on shift today", lines)


class TheClientsShrinkage(unittest.TestCase):
    def setUp(self):
        self.view = {"lanes": [lane("Associate 01", seg(8, 17, "Exam leave")), lane("Associate 02", seg(8, 17, "Sick")),
                               lane("Associate 03", seg(8, 17)), lane("Associate 04", seg(10, 19))]}
        self.week = week_of({**{f"Associate 0{i}": "08:00 - 17:00" for i in range(1, 5)},
                             "Associate 05": "Leave", "Associate 06": "Leave", "Associate 07": "Leave"})

    def test_client_only_by_default(self):
        found = day_shrinkage(self.view, self.week, SWED, read_mapping(None))
        self.assertEqual(found["sutherland"]["text"], "(unplanned 0 + planned 3 + sick 1) / 7 scheduled")
        self.assertEqual(found["client"]["text"],
                         "(unplanned 0 + planned 3 + sick 1 + public holiday 0 + exam leave 1) / 7 scheduled")
        self.assertIn("Exam leave counts for the client only", found["client"]["notes"])

    def test_approved_leave_counts_as_its_kind(self):
        kinds = {"Associate 05": "Exam leave", "Associate 06": "Public holiday", "Associate 07": "Planned leave"}
        found = day_shrinkage(self.view, self.week, SWED, read_mapping(None), leave_kinds=kinds)
        self.assertEqual(found["sutherland"]["text"], "(unplanned 0 + planned 1 + sick 1) / 7 scheduled")
        self.assertEqual(found["client"]["text"],
                         "(unplanned 0 + planned 1 + sick 1 + public holiday 1 + exam leave 2) / 7 scheduled")

    def test_the_program_can_count_it_for_sutherland_too(self):
        found = day_shrinkage(self.view, self.week, SWED, read_mapping('{"exam": ["sutherland", "client"]}'))
        self.assertIn("exam leave 1", found["sutherland"]["text"])


class TheRequest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_ag_leave
        test_ag_leave.Leave.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_ag_leave
        test_ag_leave.Leave.tearDownClass.__func__(cls)

    def test_the_kinds(self):
        self.assertEqual(KINDS, ("Planned leave", "Public holiday", "Exam leave"))
        with self.assertRaisesRegex(ValueError, "Pick Planned leave, Public holiday or Exam leave."):
            self.book.ask(self.key, "Associate 007", self.omar, "Sick", WED, WED, "", today=TUE)

    def tiles(self):
        html = self.admin.get(f"/day?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        return dict(re.findall(r'<div class="shr-tile"><h3>Out of office, (\w+)</h3><b>[^<]*</b><small>([^<]*)</small>',
                               html))

    def test_tm_then_rta_then_the_clients_shrinkage(self):
        before = self.tiles()
        rid = self.book.ask(self.key, "Associate 007", self.omar, "Exam leave", WED, WED, "Finals", today=TUE)
        self.assertIsNone(self.book.waiting(self.key)[0]["balance"])  # not taken from the planned leave balance
        self.book.decide(rid, self.users["tm1"], approve=True)
        self.book.decide(rid, self.users["rta1"], approve=True)
        self.assertEqual(dict(self.app.extensions["days"].roster(self.key, WED))["Associate 007"], "Leave")
        self.assertEqual(self.book.approved_on(self.key, WED), {"Associate 007": "Exam leave"})
        after = self.tiles()
        planned = re.compile(r"planned (\d+)")
        self.assertEqual(planned.search(after["Sutherland"]).group(1), planned.search(before["Sutherland"]).group(1))
        self.assertNotIn("exam", after["Sutherland"])
        self.assertIn("exam leave 1)", after["client"])


if __name__ == "__main__":
    unittest.main()
