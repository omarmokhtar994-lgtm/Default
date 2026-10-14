# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, E2 and E3: two new statuses on the RTA.

Task records who it is with and why, like the other aux. Public holiday works like Sick or Unplanned leave (the whole
shift, kept off the group posts); it is shrinkage for the client, not for Sutherland (E1 counts it).
"""
import unittest

from webapp.attendance import ADD_KINDS
from webapp.day import ABSENT, AUX, STATUSES
from webapp.tests import test_channel_day
from webapp.tests.test_channel_day import WED, _Day


class TheLists(unittest.TestCase):
    def test_public_holiday_is_a_whole_shift_absence(self):
        self.assertIn("Public holiday", STATUSES)
        self.assertIn("Public holiday", ABSENT)
        self.assertIn("Public holiday", ADD_KINDS["Attendance"])

    def test_task_is_an_aux(self):
        self.assertIn("Task", STATUSES)
        self.assertIn("Task", AUX)
        self.assertIn("Task", ADD_KINDS["Off the floor"])


class _Kinds:
    """Stands in for the group notifier: keeps the kind of each change handed to it."""

    def __init__(self):
        self.kinds = []

    def queue(self, log_id, program, shift_date, name, kind, *args, **kwargs):
        self.kinds.append((name, kind))


class OnTheDay(_Day):
    def test_a_public_holiday_takes_the_whole_shift_and_stays_off_the_group(self):
        self.days.notifier = _Kinds()
        self.days.set_status(self.key, WED, "Associate 031", "Public holiday", self.omar)
        seg = next(s for lane in self.view()["lanes"] if lane["name"] == "Associate 031" for s in lane["segments"]
                   if s["offset"] == 0)
        self.assertEqual(seg["status"], "Public holiday")
        self.assertEqual(self.days.notifier.kinds, [("Associate 031", "private")])

    def test_a_task_asks_who_with_and_why(self):
        from webapp.attendance import aux_details
        with self.assertRaisesRegex(ValueError, "who the task is with"):
            aux_details("Task", "", "Ticket backlog")
        with self.assertRaisesRegex(ValueError, "Say why"):
            aux_details("Task", "Team lead", "")
        self.days.add_activity(self.key, WED, "Associate 031", "Task", "16:00", "16:30", self.omar,
                               with_whom="Team lead", why="Ticket backlog")
        self.assertIn("16:00 Task", self.view()["channels"]["timelines"]["Associate 031"])


class OnThePage(unittest.TestCase):
    """The RTA page draws a public holiday like sick leave: the whole bar hatched, the lane's select marked gone."""

    setUpClass = classmethod(test_channel_day.TheChannelsTab.setUpClass.__func__)
    tearDownClass = classmethod(test_channel_day.TheChannelsTab.tearDownClass.__func__)

    def test_a_public_holiday_is_drawn_as_absent(self):
        self.days.set_status(self.key, WED, "Associate 031", "Public holiday", self.omar)
        url = f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}"
        page = self.admin.get(url).get_data(as_text=True)
        self.assertRegex(page, r'<rect class="tl-away gone"[^>]*><title>Public holiday</title>')

    def test_the_add_dialog_knows_the_new_kinds(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
        self.assertIn('whole = ["Unplanned leave", "Sick", "Public holiday"]', script)
        self.assertIn('"System issue", "Task"]', script)


if __name__ == "__main__":
    unittest.main()
