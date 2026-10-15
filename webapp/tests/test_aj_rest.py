# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AJ item 5 (owner, 2026-10-15: "i tried to add 4 hours OT for an associate but it was breaking a rule of 12
hours so that stopped it it should show a warning but still adds it"). Overtime that leaves less rest than the
program's rest gap is kept, with a warning: on the page, in the "+ Add" preview and in the day's log."""
import html
import unittest

from webapp.tests import test_attendance as ta
from webapp.tests.test_attendance import WED
from webapp.tests.test_overtime_side import _Overtime
from webapp.tests.test_runs import token

AR = "AE/AR B2B"
WARNED = "Associate 013 would rest 10 hours after the previous shift; the rule is 12."


class TheRestGap(unittest.TestCase):
    setUpClass = classmethod(ta.TheAttendance.setUpClass.__func__)
    tearDownClass = classmethod(ta.TheAttendance.tearDownClass.__func__)
    setUp = ta.TheAttendance.setUp

    def test_overtime_breaking_the_rest_gap_is_kept_with_a_warning(self):
        # Tuesday 14:00 - 23:00: in at 09:00 on Wednesday leaves 10 hours' rest
        made = self.days.add_activity(AR, WED, "Associate 013", "Overtime", "09:00", "11:00", self.sara)
        self.assertTrue(made)
        acts = [a for a in self.store.list_activities(AR, [WED.isoformat()]) if a["associate"] == "Associate 013"]
        self.assertEqual([(a["kind"], a["start"], a["end_min"]) for a in acts], [("Overtime", 540, 660)])
        self.assertEqual(self.days.page(AR, WED)["log"][-1]["what"], f"Overtime 09:00 to 11:00. Warning: {WARNED}")

    def test_the_dry_run_and_the_add_say_the_warning(self):
        found = self.days.add_item(AR, WED, "Associate 013", "Overtime", "", 120, self.sara, dry_run=True,
                                   side="before")
        self.assertEqual(found["warning"], WARNED)
        self.assertEqual(self.days.add_item(AR, WED, "Associate 001", "Overtime", "21:00", 60, self.sara,
                                            dry_run=True)["warning"], "")

    def test_the_preview_says_it(self):
        found = self.days.preview_item(AR, WED, "Associate 013", "Overtime", "", 120, side="before")
        self.assertIn(WARNED, found["text"])
        self.assertIn(found["level"], ("warn", "bad"))

    def test_the_other_overtime_rules_still_refuse(self):
        for start, end in (("22:00", "23:00"), ("21:00", "01:05")):  # not touching the shift; over 4 hours
            with self.assertRaises(ValueError):
                self.days.add_activity(AR, WED, "Associate 001", "Overtime", start, end, self.sara)


class ThePage(_Overtime):
    def test_the_page_says_the_warning(self):
        # Associate 008 starts early on Thursday: 4 hours after Wednesday's 17:00 end leaves too little rest
        got = self.client.post("/day/add", data=self.form(associate="Associate 008", side="after", minutes="240",
                                                          start="17:00", csrf_token=token(self.client)),
                               follow_redirects=True)
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("Recorded: Associate 008, Overtime 17:00 to 21:00", body)
        self.assertRegex(body, r"Warning: Associate 008 would rest [\d.]+ hours before the next shift; the rule is")
