# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23, from a screenshot of the RTA day: "Kevin Tarek would rest 9 hours after the previous shift; the rule
is 12" stopped a day off being cancelled; "it should show warnings but still apply it"): a manual change shows a warning and is
kept, never refused. Overtime has been kept with a warning since Phase AJ (2026-10-15); calling someone in on a day off is now the
same. The rules that are not about rest (one call-in a day, 15-minute steps, a length the library allows, no shift that day) still
refuse: they say the change cannot be made at all, not that it is a bad idea."""
import html
import unittest

from webapp.attendance import DAY_OFF
from webapp.tests import test_attendance as ta
from webapp.tests.test_attendance import THU, WED
from webapp.tests.test_overtime_side import _Overtime
from webapp.tests.test_runs import token

AR = "AE/AR B2B"
# Tuesday 23:00 - 08:00, off on Wednesday: in at 09:00 leaves one hour's rest (the rule is 12)
WARNED = "Associate 004 would rest 1 hours after the previous shift; the rule is 12."


class TheRestGapOnACallIn(unittest.TestCase):
    setUpClass = classmethod(ta.TheAttendance.setUpClass.__func__)
    tearDownClass = classmethod(ta.TheAttendance.tearDownClass.__func__)
    setUp = ta.TheAttendance.setUp

    def acts(self, name, on=WED):
        return [(a["kind"], a["start"], a["end_min"]) for a in self.store.list_activities(AR, [on.isoformat()])
                if a["associate"] == name]

    def test_a_call_in_that_breaks_the_rest_gap_is_kept_with_a_warning(self):
        made = self.days.add_activity(AR, WED, "Associate 004", "Called in", "09:00", "18:00", self.sara)
        self.assertTrue(made)
        self.assertEqual(self.acts("Associate 004"), [("Called in", 540, 1080)])
        what = self.days.page(AR, WED)["log"][-1]["what"]
        self.assertTrue(what.startswith("Day off cancelled: called in 09:00 - 18:00"), what)
        self.assertTrue(what.endswith(f"Warning: {WARNED}"), what)

    def test_a_dry_run_keeps_nothing_and_says_the_warning(self):
        found = self.days.add_activity(AR, WED, "Associate 004", "Called in", "09:00", "18:00", self.sara, dry_run=True)
        self.assertEqual(found["warning"], WARNED)
        self.assertEqual(self.acts("Associate 004"), [])  # a dry run keeps nothing

    def test_the_plus_add_returns_and_previews_the_warning(self):
        found = self.days.add_item(AR, WED, "Associate 004", DAY_OFF, "09:00", 0, self.sara, end="18:00", dry_run=True)
        self.assertEqual(found["warning"], WARNED)
        self.assertEqual(self.acts("Associate 004"), [])
        preview = self.days.preview_item(AR, WED, "Associate 004", DAY_OFF, "09:00", 0, end="18:00")
        self.assertIn(f"Warning: {WARNED}", preview["text"])
        self.assertIn(preview["level"], ("warn", "bad"))
        kept = self.days.add_item(AR, WED, "Associate 004", DAY_OFF, "09:00", 0, self.sara, end="18:00")
        self.assertEqual(kept["warning"], WARNED)
        self.assertEqual(self.acts("Associate 004"), [("Called in", 540, 1080)])

    def test_a_call_in_that_keeps_the_rest_has_no_warning(self):
        found = self.days.add_activity(AR, WED, "Associate 002", "Called in", "12:00", "21:00", self.sara, dry_run=True)
        self.assertEqual(found["warning"], "")

    def test_the_rest_to_the_next_shift_warns_too(self):
        # a call-in on Wednesday for Associate 002 (off Wednesday and Thursday), then another on Thursday: the later one warns
        self.days.add_activity(AR, WED, "Associate 002", "Called in", "15:00", "00:00", self.sara)
        found = self.days.add_activity(AR, THU, "Associate 002", "Called in", "09:00", "18:00", self.sara, dry_run=True)
        self.assertIn("would rest 9 hours after the previous shift", found["warning"])

    def test_the_rules_that_are_not_about_rest_still_refuse(self):
        with self.assertRaises(ValueError):  # not in 15-minute steps
            self.days.add_activity(AR, WED, "Associate 002", "Called in", "12:05", "21:05", self.sara)
        self.days.add_activity(AR, WED, "Associate 002", "Called in", "12:00", "21:00", self.sara)
        with self.assertRaises(ValueError):  # once a day
            self.days.add_activity(AR, WED, "Associate 002", "Called in", "09:00", "18:00", self.sara)
        with self.assertRaises(ValueError):  # not off that day: add overtime instead
            self.days.add_activity(AR, WED, "Associate 001", "Called in", "09:00", "18:00", self.sara)


class ThePage(_Overtime):
    """The ready schedule of Wed 14 Oct: Associate 004 works Tuesday 23:00 - 08:00 and is off on Wednesday."""
    WARNED = "Associate 004 would rest 1 hours after the previous shift; the rule is 12."

    def test_plus_add_says_the_warning_and_keeps_the_call_in(self):
        got = self.client.post("/day/add", data=self.form(associate="Associate 004", what="Day off cancelled", **{"from": "09:00"},
                                                          to="18:00", minutes="0", csrf_token=token(self.client)),
                               follow_redirects=True)
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("Recorded: Associate 004, Day off cancelled: called in 09:00 - 18:00", body)
        self.assertIn(f"Warning: {self.WARNED}", body)
        kept = [a for a in self.store.list_activities(self.key, ["2026-10-14"]) if a["associate"] == "Associate 004"]
        self.assertEqual([(a["kind"], a["start"], a["end_min"]) for a in kept], [("Called in", 540, 1080)])
        self.addCleanup(self.store.delete_activity, kept[0]["id"]) if hasattr(self.store, "delete_activity") else None

    def test_the_older_form_says_the_warning_too(self):
        got = self.client.post("/day/activity", data={"csrf_token": token(self.client), "program": self.key,
                                                      "date": "2026-10-14", "associate": "Associate 011", "kind": "Called in",
                                                      "from": "09:00", "to": "18:00", "view": "board"},
                               follow_redirects=True)
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("Recorded: Associate 011, day off cancelled (called in).", body)
        self.assertIn("Warning: Associate 011 would rest 1 hours after the previous shift; the rule is 12.", body)


if __name__ == "__main__":
    unittest.main()
