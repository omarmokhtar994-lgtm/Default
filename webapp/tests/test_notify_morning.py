# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AB (approved sample 04): at a time the admin picks, one post with everyone's breaks for the day, by shift,
as they stand then (moved breaks at their new time); people marked sick or on unplanned leave are left out. Once a
day, never hours late, the evening before when asked, and nothing when the day has no schedule."""
import json
from datetime import datetime, timedelta, timezone

from webapp.notify import KINDS
from webapp.tests.test_notify_daybook import SLACK, WED, _Tagged, hm

EGYPT = timezone(timedelta(hours=3))


def at(day, hhmm):
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=EGYPT).timestamp()


class TheDaysBreaks(_Tagged):
    def setUp(self):
        with self.store._db() as db:
            db.execute("delete from notify_posts where what = 'morning'")
        self.settle()
        self.notifier = self.app.extensions["notifier"]

    def settle(self, morning="07:30", day="same", mode="on", kinds=",".join(KINDS)):
        self.store.set_notify(self.key, link=SLACK, service="slack", mode=mode, kinds=kinds, hold=120,
                              morning=morning, morning_day=day, site="https://rta.example/")

    def mornings(self):
        return self.store.notify_posts(unit=self.key, what="morning")

    def text(self):
        return json.dumps(self.group.calls[-1][1])

    def expected(self, on):
        """(shift label, name, "Break 1 11:00, Lunch 12:45, ...") for everyone working ``on`` and not absent."""
        out = []
        for lane in self.days.page(self.key, on)["view"]["lanes"]:
            for seg in lane["segments"]:
                if seg["offset"] == 0 and seg["status"] not in ("Sick", "Unplanned leave"):
                    breaks = sorted(seg["breaks"], key=lambda b: b["start"])
                    out.append((seg["start"], seg["label"], lane["name"],
                                ", ".join(f"{b['kind']} {hm(b['start'])}" for b in breaks) or "No breaks planned"))
        return sorted(out)

    def test_morning_post_lists_breaks_by_shift(self):
        calls = len(self.group.calls)
        self.notifier.run_once(at("2026-10-14", "07:31"))
        self.assertEqual(len(self.group.calls), calls + 1)
        body = self.group.calls[-1][1]
        text = json.dumps(body)
        self.assertIn("SAKS, NMG Tier 2: breaks for Wed 14 Oct", text)
        rows = self.expected(WED)
        first_start, first_label, name, breaks = rows[0]
        people = sum(1 for r in rows if r[1] == first_label)
        self.assertIn(f"*{first_label.replace(' - ', ' to ')} ({people} {'person' if people == 1 else 'people'})*",
                      text)
        self.assertIn(f"*{name}*: {breaks}", text)
        headings = [b["text"]["text"].split("\n")[0] for b in body["blocks"][1:-1]]
        self.assertTrue(headings[0].startswith(f"*{first_label.replace(' - ', ' to ')}"))
        self.assertIn("As planned at 07:31. Changes during the day are posted as they happen.", text)
        self.assertEqual([(p["shift_date"], p["status"]) for p in self.mornings()], [("2026-10-14", "sent")])

    def test_morning_post_once_a_day(self):
        self.notifier.run_once(at("2026-10-14", "07:35"))
        calls = len(self.group.calls)
        self.notifier.run_once(at("2026-10-14", "08:10"))
        self.assertEqual(len(self.group.calls), calls)
        self.assertEqual(len(self.mornings()), 1)

    def test_evening_before_posts_tomorrow(self):
        self.settle(morning="21:00", day="before")
        self.notifier.run_once(at("2026-10-13", "21:05"))
        self.assertIn("SAKS, NMG Tier 2: breaks for Wed 14 Oct", self.text())
        self.assertEqual([p["shift_date"] for p in self.mornings()], ["2026-10-14"])

    def test_morning_post_not_sent_hours_late(self):
        calls = len(self.group.calls)
        self.notifier.run_once(at("2026-10-14", "07:29"))
        self.notifier.run_once(at("2026-10-14", "09:31"))
        self.assertEqual(len(self.group.calls), calls)
        self.assertEqual(self.mornings(), [])

    def test_sick_people_left_out(self):
        name = self.expected(WED)[-1][2]
        self.days.set_status(self.key, WED, name, "Sick", self.omar)
        try:
            self.notifier.run_once(at("2026-10-14", "07:40"))
            self.assertNotIn(f"*{name}*", self.text())
        finally:
            self.days.set_status(self.key, WED, name, "Present", self.omar)

    def test_without_change_posts_the_footer_says_less(self):
        self.settle(kinds="")
        self.notifier.run_once(at("2026-10-14", "07:40"))
        self.assertIn("As planned at 07:40.", self.text())
        self.assertNotIn("Changes during the day", self.text())

    def test_no_schedule_no_post(self):
        calls = len(self.group.calls)
        self.notifier.run_once(at("2026-10-25", "07:31"))
        self.assertEqual(len(self.group.calls), calls)
        self.assertEqual([(p["shift_date"], p["status"], p["reason"]) for p in self.mornings()],
                         [("2026-10-25", "skipped", "there is no schedule in use for that day")])

    def test_a_day_that_cannot_be_read_is_said_once(self):
        def broken(unit, on):
            raise ValueError("The input workbook kept with week.xlsx is missing, so the day cannot be worked out.")
        self.notifier.days = type("Broken", (), {"page": staticmethod(broken)})()
        try:
            self.notifier.run_once(at("2026-10-14", "07:31"))
            self.notifier.run_once(at("2026-10-14", "07:46"))
        finally:
            self.notifier.days = self.days
        self.assertEqual([(p["status"], p["reason"]) for p in self.mornings()],
                         [("skipped", "The input workbook kept with week.xlsx is missing, so the day cannot be worked "
                                      "out.")])

    def test_preview_sends_nothing(self):
        self.settle(mode="preview")
        calls = len(self.group.calls)
        self.notifier.run_once(at("2026-10-14", "07:31"))
        self.assertEqual(len(self.group.calls), calls)
        self.assertEqual([p["status"] for p in self.mornings()], ["preview"])


if __name__ == "__main__":
    import unittest
    unittest.main()
