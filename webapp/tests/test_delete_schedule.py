# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AA (owner, 2026-10-10: "Cant find a way to delete uploaded schedule unneeded"; approved sample 02 and
"Uploader or admin (Recommended)"): admins, and the person who uploaded or ran it, delete any schedule that is not in
use. It takes a tick; the days' records stay; the activity log keeps who deleted it."""
import html
import re

from webapp.tests.test_runs import sign_in, token
from webapp.tests.test_week_list import WEEK, TwoSchedulesForOneWeek

NEXT = "2026-10-18"
WED = "2026-10-14"


class _Delete(TwoSchedulesForOneWeek):
    """Phase Z's week (week_v1.xlsx in use, week_v2.xlsx not), plus: week_v3.xlsx and week_v4.xlsx for the same week,
    the next week's only upload, a run still running, and two planners with access to SAKS: Nour, who uploads
    nour_week.xlsx, and Sami, who uploads nothing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.third = cls.upload("week_v3.xlsx")
        cls.fourth = cls.upload("week_v4.xlsx")
        cls.next = cls.upload("week_next.xlsx", week=NEXT)
        saks = next(p["id"] for p in cls.store.list_programs() if p["name"] == "SAKS")
        for login, name in (("nour", "Nour"), ("sami", "Sami")):
            user = cls.store.add_user(login, name, f"{name}-pass-123", must_change=False)
            cls.store.set_user_programs(user, [saks])
        cls.nour = sign_in(cls.app, "nour", "Nour-pass-123")
        cls.sami = sign_in(cls.app, "sami", "Sami-pass-123")
        client, cls.client = cls.client, cls.nour
        cls.nours = cls.upload("nour_week.xlsx")
        cls.client = client
        cls.running = "0123456789ab"
        cls.store.add_run(cls.running, cls.omar, "running.xlsx", "QUICK", "RUNNING", program=cls.key, week_start=WEEK)

    def delete(self, run_id, client=None, confirm=True):
        client = client or self.client
        data = {"csrf_token": token(client)}
        if confirm:
            data["confirm"] = "1"
        return client.post(f"/runs/{run_id}/delete", data=data, follow_redirects=True)

    def text(self, got):
        return html.unescape(got.get_data(as_text=True))

    def kept(self, run_id):
        return self.store.get_run(run_id) is not None and bool(self.book.versions(run_id))


class TheDelete(_Delete):
    def test_an_upload_not_in_use_is_deleted_and_the_days_records_stay(self):
        name = "Associate 001"
        self.client.post("/day/attendance", data={"csrf_token": token(self.client), "program": self.key, "date": WED,
                                                  "associate": name, "status": "Sick"})
        self.assertTrue(any(r["associate"] == name for r in self.store.list_attendance(self.key, [WED])))
        folder = self.book.root / self.second
        self.assertTrue(folder.is_dir())
        page = self.text(self.delete(self.second))
        self.assertIn("Deleted week_v2.xlsx and its 1 version.", page)
        self.assertIsNone(self.store.get_run(self.second))
        self.assertEqual(self.store.list_schedules(run_id=self.second), [])
        self.assertFalse(folder.exists())
        self.assertTrue(any(r["associate"] == name for r in self.store.list_attendance(self.key, [WED])))
        events = self.store.list_events(0, 4e9, kinds=["run_deleted"])
        self.assertTrue(any(e["subject"] == "week_v2.xlsx" for e in events), events)
        self.assertIn("<h1>Schedules: SAKS, NMG Tier 2</h1>", page)
        self.assertNotIn("week_v2.xlsx</b>", page)

    def test_the_schedule_in_use_cannot_be_deleted(self):
        page = self.text(self.delete(self.first))
        self.assertIn("week_v1.xlsx is the schedule in use for the week, so it cannot be deleted. Set another schedule "
                      "in use first.", page)
        self.assertTrue(self.kept(self.first))

    def test_a_running_run_cannot_be_deleted(self):
        page = self.text(self.delete(self.running))
        self.assertIn("running.xlsx is still running: stop it first, then delete it.", page)
        self.assertIsNotNone(self.store.get_run(self.running))

    def test_only_admins_and_the_uploader_may_delete(self):
        self.assertEqual(self.sami.post(f"/runs/{self.nours}/delete",
                                        data={"csrf_token": token(self.sami), "confirm": "1"}).status_code, 403)
        self.assertTrue(self.kept(self.nours))
        page = self.text(self.delete(self.nours, client=self.nour))
        self.assertIn("Deleted nour_week.xlsx and its 1 version.", page)
        self.assertIsNone(self.store.get_run(self.nours))

    def test_without_the_tick_nothing_is_deleted(self):
        page = self.text(self.delete(self.third, confirm=False))
        self.assertIn("Tick the box to confirm, then press Delete schedule.", page)
        self.assertTrue(self.kept(self.third))

    def test_deleting_a_weeks_only_schedule_leaves_the_picker(self):
        got = self.delete(self.next)
        self.assertEqual(got.status_code, 200)
        page = self.text(got)
        self.assertIn("Deleted week_next.xlsx and its 1 version.", page)
        picker = re.search(r'(?s)<nav class="weekpick".*?</nav>', page).group(0)
        self.assertNotIn("Week of 18 Oct", picker)


class TheSection(_Delete):
    def section(self, run_id, client=None):
        page = self.text((client or self.client).get(f"/runs/{run_id}/schedules"))
        found = re.search(r'(?s)<section[^>]*id="delete".*?</section>', page)
        return found.group(0) if found else None

    def test_the_section_says_what_goes_and_what_stays(self):
        section = self.section(self.fourth)
        self.assertIsNotNone(section)
        self.assertIn("week_v4.xlsx is not in use. Deleting it removes it and its 1 version for everyone", section)
        self.assertIn("Kept: attendance, moved breaks and everything else recorded on the days.", section)
        self.assertRegex(section, r'<input type="checkbox" name="confirm" value="1" required>')
        self.assertRegex(section, r'<button class="danger" type="submit">Delete schedule</button>')
        used = self.section(self.first)
        self.assertIn("week_v1.xlsx is the schedule in use for the week, so it cannot be deleted.", used)
        self.assertNotIn("<form", used)
        self.assertIsNone(self.section(self.fourth, client=self.sami))


if __name__ == "__main__":
    import unittest
    unittest.main()
