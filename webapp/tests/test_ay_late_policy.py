# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "for early leave and late logins it should be maximum of 2 hours on maximum 2 times per month; a warning mentioning
duration and count while booking them, asking for the account manager's approval as an exception, but still booked if the RTA writes a comment
and says it was approved"): a Late login (minutes from the shift's start to the arrival) or an Early leave (minutes from the leaving time to the shift's
end) is booked freely up to 2 hours, and while the person has had fewer than 2 this month (Late and Left early together). Past either limit it is
refused until the booking says the account manager approved it, with a comment; the comment goes to the day's log. Made-up names, October 2026."""
import re
import unittest
from datetime import date, timedelta

from webapp.attendance import LATE_MAX_COUNT, LATE_MAX_MINUTES
from webapp.tests import test_attendance as ta
from webapp.tests.test_attendance import WED

AR = "AE/AR B2B"
WHO = "Associate 001"


class TheLatePolicy(unittest.TestCase):
    setUpClass = classmethod(ta.TheAttendance.setUpClass.__func__)
    tearDownClass = classmethod(ta.TheAttendance.tearDownClass.__func__)
    setUp = ta.TheAttendance.setUp

    def days_worked(self, name, n):
        found = []
        for d in range(-3, 4):
            on = WED + timedelta(days=d)
            try:
                page = self.days.page(AR, on)
            except ValueError:
                continue
            if page and any(s["offset"] == 0 and s["status"] == "Present" for l in page["view"]["lanes"] if l["name"] == name
                            for s in l["segments"]):
                found.append(on)
        self.assertGreaterEqual(len(found), n, found)
        return found[:n]

    def late(self, on, minutes, **more):
        shift = next(s for l in self.days.page(AR, on)["view"]["lanes"] if l["name"] == WHO for s in l["segments"] if s["offset"] == 0)
        at = shift["start"] + minutes
        return self.days.set_status(AR, on, WHO, "Late", self.sara, end=f"{at // 60:02d}:{at % 60:02d}", **more)

    def test_the_limits_are_two_hours_and_two_a_month(self):
        self.assertEqual((LATE_MAX_MINUTES, LATE_MAX_COUNT), (120, 2))

    def test_a_short_first_late_is_booked_and_the_preview_says_the_duration_and_count(self):
        on = self.days_worked(WHO, 1)[0]
        seen = self.late(on, 45, dry_run=True)["policy"]
        self.assertEqual((seen["minutes"], seen["count"], seen["over"]), (45, 1, []))
        self.late(on, 45)

    def test_over_two_hours_is_refused_without_approval_and_booked_with_it(self):
        on = self.days_worked(WHO, 1)[0]
        with self.assertRaises(ValueError) as said:
            self.late(on, 150)
        self.assertIn("account manager", str(said.exception))
        self.assertIn("2 hours", str(said.exception))
        with self.assertRaises(ValueError):  # a tick alone is not enough: the comment is needed
            self.late(on, 150, am_note="  ")
        self.late(on, 150, am_note="Approved by the account manager, bus strike")
        said = " ".join(e["what"] for e in self.days.page(AR, on)["log"] if e["associate"] == WHO)
        self.assertIn("bus strike", said)
        self.assertIn("exception", said.lower())

    def test_the_third_in_a_month_needs_approval_and_early_leaves_count_with_lates(self):
        a, b, c = self.days_worked(WHO, 3)
        self.late(a, 30)
        shift = next(s for l in self.days.page(AR, b)["view"]["lanes"] if l["name"] == WHO for s in l["segments"] if s["offset"] == 0)
        left = shift["end"] - 30
        self.days.set_status(AR, b, WHO, "Left early", self.sara, start=f"{left // 60 % 24:02d}:{left % 60:02d}")
        with self.assertRaises(ValueError) as said:
            self.late(c, 20)
        self.assertIn("3rd", str(said.exception))
        self.late(c, 20, am_note="Approved by the account manager")

    def test_booking_the_same_day_again_does_not_count_twice(self):
        a, b = self.days_worked(WHO, 2)
        self.late(a, 30)
        self.late(a, 40)  # the same day, changed
        self.late(b, 30)  # the second of the month: still free

    def test_a_left_early_is_measured_from_the_leaving_time_to_the_shifts_end(self):
        on = self.days_worked(WHO, 1)[0]
        shift = next(s for l in self.days.page(AR, on)["view"]["lanes"] if l["name"] == WHO for s in l["segments"] if s["offset"] == 0)
        left = shift["end"] - 180
        seen = self.days.set_status(AR, on, WHO, "Left early", self.sara, start=f"{left // 60 % 24:02d}:{left % 60:02d}", dry_run=True)
        self.assertEqual(seen["policy"]["minutes"], 180)
        self.assertEqual(seen["policy"]["over"], ["longer than 2 hours"])


if __name__ == "__main__":
    unittest.main()
