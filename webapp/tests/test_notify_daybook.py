# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AB: every change the RTA records reaches the LOB's group rule with its kind and a text safe for a group
(the why of an aux stays on the website), the day log itself is unchanged, and an LOB that posts nowhere keeps
nothing. Made-up "Associate NN" data on the week of Sun 11 Oct with breaks planned automatically."""
import io
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp.notify import KINDS, Notifier, leave_out
from webapp.programs import ProgramBook
from webapp.store import Store
from webapp.tests.test_channel_day import ARABIC_SPARE, _Day
from webapp.tests.test_notify_sender import Group
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait

WED = date(2026, 10, 14)
SLACK = "https://hooks.slack.com/services/T0000/B0000/abcdEFGHijkl"
LATE = "Associate 021"  # 08:00 to 17:00, room for overtime after
OFF = "Associate 002"   # off on Wednesday


def hm(m):
    return f"{m // 60 % 24:02d}:{m % 60:02d}"


class _Tagged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.group = Group()
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO), NOTIFY_THREAD=False, NOTIFY_TRANSPORT=cls.group)
        cls.omar = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        saks = programs.add_program("SAKS")
        cls.key = programs.add_lob(saks, "NMG Tier 2")
        cls.quiet = programs.add_lob(saks, "NMG Tier 1")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        for program in (cls.key, cls.quiet):
            cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                           "program": program, "week_start": "2026-10-11",
                                           "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                            content_type="multipart/form-data")
            run = cls.store.list_runs()[0]["id"]
            wait(cls.store, run, statuses=("DONE", "REJECTED", "FAILED"))
            planned = cls.app.extensions["schedules"].versions(run)[0]["id"]
            cls.client.post(f"/schedules/{planned}/auto-breaks", data={"csrf_token": token(cls.client), "use": "1"})
        cls.days = cls.app.extensions["days"]
        cls.store.set_notify(cls.key, link=SLACK, service="slack", mode="on", kinds=",".join(KINDS), hold=120)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def items(self, n=1):
        return self.store.notify_items(unit=self.key)[-n:]

    def logged(self, n=1):
        return self.store.list_day_log(self.key, WED.isoformat())[-n:]

    def with_breaks(self, skip=()):
        """(name, idx, kind, start, planned start) of the first break of someone present with breaks today."""
        for lane in self.days.page(self.key, WED)["view"]["lanes"]:
            if lane["name"] in skip:
                continue
            for seg in lane["segments"]:
                if seg["offset"] == 0 and seg["status"] == "Present" and seg["breaks"]:
                    b = seg["breaks"][0]
                    return lane["name"], b["idx"], b["kind"], b["start"], b["planned_start"]
        self.fail("nobody with breaks today")

    def move(self, name, idx, start):
        for step in (5, 10, 15, -5, -10, 20, 25, 30):
            try:
                self.days.move_break(self.key, WED, name, idx, hm(start + step), self.omar)
                return start + step
            except ValueError:
                continue
        self.fail(f"no time found to move {name}'s break")


class TheKinds(_Tagged):
    def test_a_break_move_and_back_to_plan(self):
        name, idx, kind, start, planned = self.with_breaks()
        to = self.move(name, idx, start)
        item = self.items()[0]
        self.assertEqual(item["log_id"], self.logged()[0]["id"])
        self.assertEqual((item["kind"], item["text"], item["by_name"]), ("break", f"{kind} moved {hm(start)} to {hm(to)}",
                                                                         "Omar"))
        self.assertEqual((item["ref"], item["before"], item["after"]), (f"break:{name}:{idx}", hm(start), hm(to)))
        self.assertEqual(item["status"], "waiting")
        self.days.move_break(self.key, WED, name, idx, None, self.omar)
        back, moved = self.items(2)[::-1]
        self.assertEqual((back["text"], back["after"]), (f"{kind} back to plan ({hm(planned)})", hm(planned)))
        self.assertEqual({(moved["status"], moved["reason"]), (back["status"], back["reason"])},
                         {("skipped", "undone before it was posted")})

    def test_overtime_and_its_cancellation(self):
        self.days.add_item(self.key, WED, LATE, "Overtime", "", 60, self.omar, side="after")
        made = self.items()[0]
        self.assertEqual((made["kind"], made["text"], made["before"], made["after"]),
                         ("overtime", "Overtime 17:00 to 18:00", "", "on"))
        activity = next(a for a in self.store.list_activities(self.key, [WED.isoformat()])
                        if a["associate"] == LATE and a["kind"] == "Overtime")
        self.assertEqual(made["ref"], f"activity:{activity['id']}")
        self.days.cancel_activity(self.key, WED, activity["id"], self.omar)
        gone = self.items()[0]
        self.assertEqual((gone["kind"], gone["text"], gone["ref"], gone["after"]),
                         ("overtime", "Cancelled: Overtime 17:00 to 18:00", made["ref"], ""))
        both = [i for i in self.store.notify_items(unit=self.key) if i["ref"] == made["ref"]]
        self.assertEqual({(i["status"], i["reason"]) for i in both}, {("skipped", "undone before it was posted")})

    def test_vto_and_a_break_added_on_the_day(self):
        self.days.add_item(self.key, WED, "Associate 037", "VTO", "10:00", 60, self.omar)
        self.assertEqual((self.items()[0]["kind"], self.items()[0]["text"]), ("overtime", "VTO 10:00 to 11:00"))
        for at in ("16:00", "15:30", "11:30", "09:30"):
            try:
                self.days.add_item(self.key, WED, "Associate 012", "Break", at, 15, self.omar)
                break
            except ValueError:
                continue
        added = self.items()[0]
        self.assertEqual(added["kind"], "added_break")
        self.assertEqual(added["text"], self.logged()[0]["what"])

    def test_the_why_never_reaches_a_post(self):
        self.days.add_activity(self.key, WED, "Associate 028", "Coaching", "14:00", "14:30", self.omar, billable=True,
                               with_whom="Lina", why="Call review after a complaint")
        item = self.items()[0]
        self.assertEqual((item["kind"], item["text"]), ("aux", "Coaching 14:00 to 14:30 (billable), with Lina"))
        self.assertEqual(self.logged()[0]["what"],
                         "Coaching 14:00 to 14:30 (billable), with Lina: Call review after a complaint")
        self.days.set_status(self.key, WED, "Associate 036", "Training", self.omar, why="New product")
        item = self.items()[0]
        self.assertEqual((item["kind"], item["text"]), ("aux", "Training (non-billable), whole shift"))
        self.assertIn("New product", self.logged()[0]["what"])

    def test_attendance(self):
        self.days.set_status(self.key, WED, "Associate 010", "Late", self.omar, end="07:20")
        late = self.items()[0]
        self.assertEqual((late["kind"], late["text"], late["ref"], late["before"], late["after"]),
                         ("late", "Late, arrived 07:20", "status:Associate 010", "Present", "Late"))
        self.days.set_status(self.key, WED, "Associate 024", "Left early", self.omar, start="14:00")
        self.assertEqual(self.items()[0]["kind"], "late")
        for status in ("Sick", "Unplanned leave", "Present"):
            self.days.set_status(self.key, WED, "Associate 029", status, self.omar)
            item = self.items()[0]
            self.assertEqual((item["kind"], item["status"], item["reason"]), ("private", "skipped", "kept private"))

    def test_a_day_off_cancelled_and_back(self):
        self.days.add_activity(self.key, WED, OFF, "Called in", "08:00", "17:00", self.omar)
        made = self.items()[0]
        self.assertEqual((made["kind"], made["text"], made["after"]),
                         ("called_in", "Day off cancelled: called in 08:00 - 17:00", "on"))
        activity = next(a for a in self.store.list_activities(self.key, [WED.isoformat()])
                        if a["associate"] == OFF and a["kind"] == "Called in")
        self.assertEqual(made["ref"], f"callin:{activity['id']}")
        self.days.cancel_activity(self.key, WED, activity["id"], self.omar)
        gone = self.items()[0]
        self.assertEqual((gone["kind"], gone["ref"], gone["after"], gone["status"]),
                         ("called_in", made["ref"], "", "skipped"))
        self.assertTrue(gone["text"].startswith("Call-in cancelled: back to the day off"))

    def test_leave_out_skips_one(self):
        name, idx, kind, start, _ = self.with_breaks(skip=("Associate 008",))
        with leave_out(True):
            self.move(name, idx, start)
        item = self.items()[0]
        self.assertEqual((item["status"], item["reason"]), ("skipped", "left out on the RTA"))
        with leave_out(False):
            self.days.add_item(self.key, WED, "Associate 028", "VTO", "16:00", 60, self.omar)
        self.assertEqual(self.items()[0]["status"], "waiting")

    def test_no_settings_no_items(self):
        before = len(self.store.notify_items())
        self.days.add_item(self.quiet, WED, LATE, "Overtime", "", 30, self.omar, side="after")
        self.assertEqual(len(self.store.notify_items()), before)
        self.assertEqual(self.store.list_day_log(self.quiet, WED.isoformat())[-1]["what"], "Overtime 17:00 to 17:30")


class TheChannelKind(_Day):
    def test_a_channel_change_and_taking_it_back(self):
        self.store.set_notify(self.key, link=SLACK, service="slack", mode="on", kinds="channel", hold=120)
        self.days.notifier = Notifier(self.store, transport=Group())
        made_id = self.days.channel_move(self.key, WED, ARABIC_SPARE, "15:00", "16:00", "C", self.omar)
        made = self.store.notify_items(unit=self.key)[-1]
        self.assertEqual((made["kind"], made["ref"], made["after"]), ("channel", f"channel:{made_id}", "on"))
        self.assertTrue(made["text"].startswith("Chat from 15:00 to 16:00"))
        self.days.cancel_channel_move(self.key, WED, made_id, self.omar)
        gone = self.store.notify_items(unit=self.key)[-1]
        self.assertEqual((gone["kind"], gone["ref"], gone["status"]), ("channel", made["ref"], "skipped"))


class TheRename(unittest.TestCase):
    def test_a_rename_takes_the_group_settings_with_it(self):
        store = Store(Path(tempfile.mkdtemp()) / "scheduler.db")
        store.set_notify("SAKS NMG Tier 2", link=SLACK, service="slack", mode="on", kinds="break")
        store.add_notify_item(log_id=1, unit="SAKS NMG Tier 2", shift_date="2026-10-14", associate="Associate 001",
                              kind="break", text="x", at=1.0, status="waiting")
        store.add_notify_post(unit="SAKS NMG Tier 2", shift_date="2026-10-14", what="changes", status="sent")
        store.rename_program("SAKS NMG Tier 2", "SAKS NMG Tier Two", [])
        self.assertIsNone(store.get_notify("SAKS NMG Tier 2"))
        self.assertEqual(store.get_notify("SAKS NMG Tier Two")["link"], SLACK)
        self.assertEqual([i["unit"] for i in store.notify_items()], ["SAKS NMG Tier Two"])
        self.assertEqual([p["unit"] for p in store.notify_posts()], ["SAKS NMG Tier Two"])


if __name__ == "__main__":
    unittest.main()
