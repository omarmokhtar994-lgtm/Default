# © 2026 Omar Mokhtar. All rights reserved.
"""Phase N task 4: attendance and actual breaks kept per program and shift date.

The day is read from the version in use for its week (the tool's own version,
with a note, when none is). Statuses and break moves are checked before they
are kept, and every one is logged with who and when."""
import shutil
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

from webapp.attendance import DayBook
from webapp.day import BreakRefused
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.versions import shift_span
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED = date(2026, 10, 14)  # the run's week starts Sunday 11 October
SAT = date(2026, 10, 17)
SUN, MON, TUE, THU = date(2026, 10, 11), date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 15)


class TheAttendance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """One run with its tool version (the validator runs once); each test gets a copy."""
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        store.add_run("aaaaaaaaaaaa", cls.sara, "AR_week.xlsx", "QUICK", "DONE", program="AE/AR B2B",
                      week_start="2026-10-11")
        ScheduleBook(store, cls.base, REPO).ensure(store.get_run("aaaaaaaaaaaa"), INPUT, AFTER, None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.tool = self.book.versions("aaaaaaaaaaaa")[0]
        self.days = DayBook(self.store, self.book)

    def lane(self, page, name):
        return next(l for l in page["view"]["lanes"] if l["name"] == name)

    def test_tool_version_with_a_note_until_one_is_in_use(self):
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual(page["version"]["id"], self.tool["id"])
        self.assertIn("No version is marked in use", page["note"])
        draft = self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "10:00 - 19:00", "swap")
        self.book.set_in_use(draft, self.sara)
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual((page["version"]["id"], page["note"]), (draft, ""))
        self.assertEqual(self.lane(page, "Associate 001")["segments"][0]["label"], "10:00 - 19:00")
        self.assertEqual(self.days.programs(), ["AE/AR B2B"])
        self.assertIsNone(self.days.page("AE/AR B2B", date(2026, 11, 4)))  # no schedule that week

    def test_status_kept_and_logged(self):
        before = self.days.page("AE/AR B2B", WED)["view"]["tiles"]
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Unplanned leave", self.sara)
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual(page["view"]["tiles"]["absent"], before["absent"] + 1)
        self.assertEqual(self.lane(page, "Associate 001")["segments"][0]["status"], "Unplanned leave")
        self.assertEqual([(e["by_name"], e["associate"], e["what"]) for e in page["log"]],
                         [("Sara", "Associate 001", "Unplanned leave")])
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Present", self.sara)
        self.assertEqual(self.days.page("AE/AR B2B", WED)["view"]["tiles"]["absent"], before["absent"])

    def test_timed_statuses_need_times_inside_the_shift(self):
        with self.assertRaises(ValueError):  # a late arrival needs the time they arrived
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Late", self.sara)
        with self.assertRaises(ValueError):  # Wednesday is 12:00 - 21:00
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Late", self.sara, end="22:00")
        with self.assertRaises(ValueError):
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Meeting", self.sara, start="15:00", end="14:00")
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Late", self.sara, end="13:00")
        seg = self.lane(self.days.page("AE/AR B2B", WED), "Associate 001")["segments"][0]
        self.assertEqual((seg["status"], seg["away"]), ("Late", (12 * 60, 13 * 60)))
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Meeting", self.sara, start="15:00", end="16:00")
        self.assertEqual(self.lane(self.days.page("AE/AR B2B", WED), "Associate 001")["segments"][0]["away"],
                         (15 * 60, 16 * 60))

    def test_aux_is_billable_or_not_and_the_measure_decides(self):
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Coaching", self.sara, start="15:00", end="16:00",
                             billable=True)
        page = self.days.page("AE/AR B2B", WED)
        seg = self.lane(page, "Associate 001")["segments"][0]
        self.assertEqual((seg["status"], seg["billable"]), ("Coaching", True))
        self.assertEqual(page["log"][-1]["what"], "Coaching (billable) 15:00 to 16:00")
        cell = lambda measure: next(c for c in self.days.page("AE/AR B2B", WED, measure)["view"]["cells"]
                                    if c["t"] == 15 * 60)
        self.assertEqual(cell("interval")["now"], cell("interval")["plan"])  # billable: still on the floor
        self.assertEqual(cell("sl")["now"], cell("sl")["plan"] - 1)  # any aux takes them off the queue
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Coaching", self.sara, start="15:00", end="16:00")
        self.assertEqual(self.days.page("AE/AR B2B", WED)["log"][-1]["what"], "Coaching (non-billable) 15:00 to 16:00")
        self.assertEqual(cell("interval")["now"], cell("interval")["plan"] - 1)
        with self.assertRaises(ValueError):
            self.days.page("AE/AR B2B", WED, "weekly")

    def test_break_advice_warns_on_gaps_and_ranks_the_best_times(self):
        # Wednesday 12:00 - 21:00: Break 1 13:45-14:00, Lunch 16:30, Break 2 19:30; gaps 60 to 210 minutes
        advice = self.days.break_advice("AE/AR B2B", WED, "Associate 001", 1, "14:30")
        self.assertEqual(advice["warnings"], ["Break 1 ends and Lunch starts 30 minutes apart; this program's "
                                              "minimum gap between breaks is 60 minutes.",
                                              "Lunch ends and Break 2 starts 270 minutes apart; this program's "
                                              "normal maximum gap between breaks is 210 minutes."])
        fits = advice["fits"]
        self.assertTrue(0 < len(fits) <= 3)
        for fit in fits:  # Lunch between Break 1 and Break 2, within the 60 to 210 minute gaps
            self.assertTrue("15:30" <= fit["start"] <= "17:30", fit)
        self.assertEqual([f["buffer"] for f in fits], sorted((f["buffer"] for f in fits), reverse=True))
        self.assertEqual(self.days.break_advice("AE/AR B2B", WED, "Associate 001", 1, "16:30")["warnings"], [])

    def test_a_missing_input_workbook_is_said_plainly(self):
        self.book.input_path("aaaaaaaaaaaa").unlink()
        with self.assertRaises(ValueError) as said:
            self.days.page("AE/AR B2B", WED)
        self.assertIn("input workbook kept with Tool, after breaks is missing", str(said.exception))

    def acts(self, name):
        seg = self.lane(self.days.page("AE/AR B2B", WED), name)["segments"][0]
        return [(a["kind"], a["start"], a["end"], a["billable"]) for a in seg["activities"]]

    def test_activity_added_logged_and_cancelled(self):
        made = self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Meeting", "15:00", "15:30", self.sara)
        self.assertEqual(self.acts("Associate 001"), [("Meeting", 900, 930, False)])
        self.assertEqual(self.days.page("AE/AR B2B", WED)["log"][-1]["what"], "Meeting 15:00 to 15:30 (non-billable)")
        self.days.cancel_activity("AE/AR B2B", WED, made, self.sara)
        self.assertEqual(self.acts("Associate 001"), [])
        self.assertEqual(self.days.page("AE/AR B2B", WED)["log"][-1]["what"],
                         "Cancelled: Meeting 15:00 to 15:30 (non-billable)")

    def test_activity_rules(self):
        with self.assertRaises(ValueError):  # Wednesday is 12:00 - 21:00
            self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Training", "11:00", "12:00", self.sara)
        self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Training", "15:00", "16:00", self.sara, billable=True)
        with self.assertRaises(ValueError):  # on top of the training
            self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Coaching", "15:30", "16:30", self.sara)
        with self.assertRaises(ValueError):  # overtime must touch the shift
            self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Overtime", "22:00", "23:00", self.sara)
        with self.assertRaises(ValueError):  # at most 2 hours
            self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Overtime", "21:00", "23:30", self.sara)
        with self.assertRaises(ValueError):  # Tuesday 14:00 - 23:00: in at 09:00 leaves 10 hours' rest
            self.days.add_activity("AE/AR B2B", WED, "Associate 013", "Overtime", "09:00", "11:00", self.sara)
        with self.assertRaises(ValueError):  # Thursday 05:00 - 14:00: staying to 19:00 leaves 10 hours' rest
            self.days.add_activity("AE/AR B2B", WED, "Associate 008", "Overtime", "17:00", "19:00", self.sara)
        with self.assertRaises(ValueError):
            self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Lunch party", "15:00", "16:00", self.sara)
        self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Overtime", "21:00", "22:00", self.sara)
        self.days.add_activity("AE/AR B2B", WED, "Associate 001", "VTO", "20:00", "21:00", self.sara)
        self.assertEqual([a[0] for a in self.acts("Associate 001")], ["Training", "VTO", "Overtime"])

    def test_booking_a_meeting_is_all_or_nothing(self):
        slot = self.days.meeting_slots("AE/AR B2B", WED, ["Associate 001", "Associate 013"], 30, "13:00", "19:00")[0]
        self.days.book_session("AE/AR B2B", WED, ["Associate 001", "Associate 013"], slot["start"], 30, "Training", self.sara,
                       billable=True)
        self.assertEqual(len(self.acts("Associate 001")), 1)
        self.assertEqual(len(self.acts("Associate 013")), 1)
        with self.assertRaises(ValueError):  # Associate 013 is now busy then: nobody is booked
            self.days.book_session("AE/AR B2B", WED, ["Associate 012", "Associate 013"], slot["start"], 30, "Meeting", self.sara)
        self.assertEqual(self.acts("Associate 012"), [])

    def test_a_day_off_called_in_works_like_any_shift(self):
        # Associate 002: Tuesday 09:00 - 18:00, off on Wednesday
        self.days.add_activity("AE/AR B2B", WED, "Associate 002", "Called in", "12:00", "21:00", self.sara)
        page = self.days.page("AE/AR B2B", WED)
        seg = self.lane(page, "Associate 002")["segments"][0]
        self.assertEqual((seg["label"], seg["called_in"], [b["kind"] for b in seg["breaks"]]),
                         ("12:00 - 21:00 (called in)", True, ["Break 1", "Lunch", "Break 2"]))
        self.assertEqual(page["log"][-1]["what"], "Day off cancelled: called in 12:00 - 21:00")
        self.days.move_break("AE/AR B2B", WED, "Associate 002", 1, "17:00", self.sara)  # its lunch, planned 16:30
        self.days.set_status("AE/AR B2B", WED, "Associate 002", "Late", self.sara, end="12:30")
        seg = self.lane(self.days.page("AE/AR B2B", WED), "Associate 002")["segments"][0]
        self.assertEqual((seg["breaks"][1]["start"], seg["breaks"][1]["moved"], seg["status"]), (17 * 60, True, "Late"))
        self.assertEqual(self.days.page("AE/AR B2B", WED)["stale"], 0)
        self.assertIn("gap", " ".join(self.days.break_advice("AE/AR B2B", WED, "Associate 002", 1, "14:15")["warnings"]))

    def test_calling_in_keeps_the_rules(self):
        with self.assertRaises(ValueError):  # works that day: overtime instead
            self.days.add_activity("AE/AR B2B", WED, "Associate 001", "Called in", "12:00", "21:00", self.sara)
        with self.assertRaises(ValueError):  # not a Shift Library shift
            self.days.add_activity("AE/AR B2B", WED, "Associate 002", "Called in", "12:05", "21:05", self.sara)
        with self.assertRaises(ValueError):  # Tuesday 23:00 - 08:00 leaves 1 hour's rest before 09:00
            self.days.add_activity("AE/AR B2B", WED, "Associate 004", "Called in", "09:00", "18:00", self.sara)
        self.days.add_activity("AE/AR B2B", WED, "Associate 002", "Called in", "12:00", "21:00", self.sara)
        with self.assertRaises(ValueError):  # once a day
            self.days.add_activity("AE/AR B2B", WED, "Associate 002", "Called in", "09:00", "18:00", self.sara)

    def test_the_rest_gap_reaches_across_the_week_and_what_was_added(self):
        # Sunday: no schedule is kept for the week before, so the previous Saturday comes from the input
        with self.assertRaises(ValueError) as refused:  # Associate 001: Saturday 16:00 - 01:00
            self.days.add_activity("AE/AR B2B", SUN, "Associate 001", "Called in", "09:00", "18:00", self.sara)
        self.assertIn("would rest 8 hours after the previous shift", str(refused.exception))
        self.days.add_activity("AE/AR B2B", SUN, "Associate 001", "Called in", "13:00", "22:00", self.sara)
        with self.assertRaises(ValueError) as refused:  # Associate 010: Saturday 18:00 - 03:00, Sunday from 16:00
            self.days.add_activity("AE/AR B2B", SUN, "Associate 010", "Overtime", "14:00", "16:00", self.sara)
        self.assertIn("would rest 11 hours after the previous shift", str(refused.exception))
        # a call-in is a shift for the days either side: Associate 002 is off Wednesday and Thursday
        self.days.add_activity("AE/AR B2B", WED, "Associate 002", "Called in", "15:00", "00:00", self.sara)
        with self.assertRaises(ValueError) as refused:
            self.days.add_activity("AE/AR B2B", THU, "Associate 002", "Called in", "09:00", "18:00", self.sara)
        self.assertIn("would rest 9 hours after the previous shift", str(refused.exception))
        # and overtime lengthens the shift: Associate 003 works Monday 09:00 - 18:00, off on Tuesday
        self.days.add_activity("AE/AR B2B", MON, "Associate 003", "Overtime", "18:00", "20:00", self.sara)
        with self.assertRaises(ValueError) as refused:
            self.days.add_activity("AE/AR B2B", TUE, "Associate 003", "Called in", "07:00", "16:00", self.sara)
        self.assertIn("would rest 11 hours after the previous shift", str(refused.exception))
        self.days.add_activity("AE/AR B2B", TUE, "Associate 003", "Called in", "08:00", "17:00", self.sara)
        # the other way: Associate 018 (Monday 09:00 - 18:00, off Tuesday) called in at 06:00 has exactly 12 hours
        self.days.add_activity("AE/AR B2B", TUE, "Associate 018", "Called in", "06:00", "15:00", self.sara)
        with self.assertRaises(ValueError) as refused:
            self.days.add_activity("AE/AR B2B", MON, "Associate 018", "Overtime", "18:00", "19:00", self.sara)
        self.assertIn("would rest 11 hours before the next shift", str(refused.exception))

    def test_board_offers_keep_the_rest_gap_across_the_week(self):
        page = self.days.page("AE/AR B2B", SUN)
        cover = self.days.cover_offers(page, 9 * 60)
        offered = [o["name"] for o in cover["dayoff"]]
        self.assertTrue(offered)
        # Associate 001 (Saturday to 01:00) and 012 (to 02:00) cannot start by 09:00 with 12 hours' rest
        self.assertFalse({"Associate 001", "Associate 012"} & set(offered))
        cover = self.days.cover_offers(page, 14 * 60)
        self.assertNotIn("Associate 010", [o["name"] for o in cover["overtime"]])  # 14:00 leaves 11 hours

    def test_cancelling_a_call_in_leaves_nothing_behind(self):
        called = self.days.add_activity("AE/AR B2B", WED, "Associate 002", "Called in", "12:00", "21:00", self.sara)
        training = self.days.add_activity("AE/AR B2B", WED, "Associate 002", "Training", "15:00", "16:00", self.sara)
        self.days.set_status("AE/AR B2B", WED, "Associate 002", "Late", self.sara, end="12:30")
        self.days.move_break("AE/AR B2B", WED, "Associate 002", 1, "17:00", self.sara)
        with self.assertRaises(ValueError) as refused:  # its records would be left on a day off
            self.days.cancel_activity("AE/AR B2B", WED, called, self.sara)
        self.assertEqual(str(refused.exception), "Associate 002 still has a training 15:00 to 16:00, the status Late "
                         "and a moved Lunch on this shift: cancel or set those back first.")
        self.days.cancel_activity("AE/AR B2B", WED, training, self.sara)
        self.days.set_status("AE/AR B2B", WED, "Associate 002", "Present", self.sara)
        self.days.move_break("AE/AR B2B", WED, "Associate 002", 1, None, self.sara)
        self.days.cancel_activity("AE/AR B2B", WED, called, self.sara)
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual(page["log"][-1]["what"], "Call-in cancelled: back to the day off (was 12:00 - 21:00)")
        self.assertNotIn("Associate 002", [l["name"] for l in page["view"]["lanes"]])  # off again: no lane
        self.assertEqual(page["view"]["tiles"]["called_in"], 0)

    def test_unknown_status_or_person_refused(self):
        with self.assertRaises(ValueError):
            self.days.set_status("AE/AR B2B", WED, "Associate 001", "Holiday", self.sara)
        with self.assertRaises(ValueError):
            self.days.set_status("AE/AR B2B", WED, "Nobody", "Sick", self.sara)
        with self.assertRaises(ValueError):  # Associate 001 is off on Saturday
            self.days.set_status("AE/AR B2B", SAT, "Associate 001", "Sick", self.sara)
        self.assertEqual(self.days.page("AE/AR B2B", WED)["log"], [])

    def test_break_moved_then_back_to_plan(self):
        # Wednesday 12:00 - 21:00: Break 1 13:45, Lunch 16:30, Break 2 19:30
        self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, "17:05", self.sara)
        page = self.days.page("AE/AR B2B", WED)
        lunch = self.lane(page, "Associate 001")["segments"][0]["breaks"][1]
        self.assertEqual((lunch["kind"], lunch["start"], lunch["planned_start"], lunch["moved"]),
                         ("Lunch", 17 * 60 + 5, 16 * 60 + 30, True))
        self.assertEqual(page["log"][-1]["what"], "Lunch moved 16:30 to 17:05")
        self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, None, self.sara)
        page = self.days.page("AE/AR B2B", WED)
        lunch = self.lane(page, "Associate 001")["segments"][0]["breaks"][1]
        self.assertEqual((lunch["start"], lunch["moved"]), (16 * 60 + 30, False))
        self.assertEqual(page["log"][-1]["what"], "Lunch back to plan (16:30)")

    def test_refused_break_is_not_kept(self):
        for at in ("17:07", "20:50", "19:30", "bad"):  # not a 5-minute step, past 21:00, on Break 2, not a time
            with self.assertRaises((BreakRefused, ValueError)):
                self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, at, self.sara)
        self.assertFalse(any(b["moved"] for b in self.lane(self.days.page("AE/AR B2B", WED),
                                                           "Associate 001")["segments"][0]["breaks"]))
        self.assertEqual(self.days.page("AE/AR B2B", WED)["log"], [])

    def test_a_move_that_no_longer_matches_the_plan_is_reported_not_applied(self):
        self.store.set_actual_break(program="AE/AR B2B", shift_date=WED.isoformat(), associate="Associate 001",
                                    idx=1, kind="Break 9", start=16 * 60, user_id=self.sara)
        page = self.days.page("AE/AR B2B", WED)
        self.assertEqual(page["stale"], 1)
        self.assertFalse(self.lane(page, "Associate 001")["segments"][0]["breaks"][1]["moved"])

    def test_overnight_status_belongs_to_the_shift_date(self):
        tue = date(2026, 10, 13)
        person = next(a for a in self.book.view(self.tool["id"])["week"]["associates"]
                      if (shift_span(a["days"][2]) or (0, 0))[1] > 1440)  # Tuesday night into Wednesday
        self.days.set_status("AE/AR B2B", tue, person["name"], "Sick", self.sara)
        carry = [s for s in self.lane(self.days.page("AE/AR B2B", WED), person["name"])["segments"] if s["offset"] == -1]
        self.assertEqual(carry[0]["status"], "Sick")

    def test_day_records_deleted_after_13_months(self):
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.sara)
        self.days.move_break("AE/AR B2B", WED, "Associate 001", 1, "17:05", self.sara)
        self.assertEqual(self.days.cleanup(now=time.time() + 300 * 86400), 0)
        # the status, the break move and their two log lines
        self.assertEqual(self.days.cleanup(now=time.mktime((2027, 11, 20, 0, 0, 0, 0, 0, -1))), 4)
        self.assertEqual(self.store.list_attendance("AE/AR B2B", [WED.isoformat()]), [])


class TheStartDay(unittest.TestCase):
    """Phase P: a schedule's first date is chosen when it is uploaded (Sunday or Monday). A date reads the
    column of its weekday from the run whose seven days hold it; last night's overnight shifts come from the
    day before, in the same run or the run before (the input's carry-in tab when there is none)."""

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        book = ScheduleBook(store, cls.base, REPO)
        for run_id, program, start in (("cccccccccccc", "MON", "2026-10-12"), ("dddddddddddd", "MON", "2026-10-19"),
                                       ("eeeeeeeeeeee", "MIX", "2026-10-11"), ("ffffffffffff", "MIX", "2026-10-12")):
            store.add_run(run_id, cls.sara, "AR_week.xlsx", "QUICK", "DONE", program=program, week_start=start)
            book.ensure(store.get_run(run_id), INPUT, AFTER, None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.days = DayBook(self.store, self.book)

    def run_of(self, program, on):
        row, _ = self.days.version(program, on)
        return row["run_id"] if row else None

    def carried(self, program, on, name):
        lane = next((l for l in self.days.page(program, on)["view"]["lanes"] if l["name"] == name), None)
        return [(s["start"], s["end"]) for s in (lane or {}).get("segments", []) if s["offset"] == -1]

    def test_a_monday_start_covers_monday_to_sunday(self):
        for d in range(12, 19):
            self.assertEqual(self.run_of("MON", date(2026, 10, d)), "cccccccccccc", d)
        self.assertIsNone(self.run_of("MON", date(2026, 10, 11)))
        self.assertEqual(self.run_of("MON", date(2026, 10, 19)), "dddddddddddd")
        self.assertIsNone(self.run_of("MON", date(2026, 10, 26)))
        page = self.days.page("MON", date(2026, 10, 18))
        self.assertEqual((page["day"], page["week_start"]), (0, "2026-10-12"))  # Sunday's column, the run's start

    def test_the_last_day_takes_saturday_night_from_the_same_run(self):
        # Associate 004: Saturday 20:00 - 05:00 runs into Sunday 18 October, the run's last day
        self.assertEqual(self.carried("MON", date(2026, 10, 18), "Associate 004"), [(20 * 60 - 1440, 5 * 60)])

    def test_the_first_day_takes_last_night_from_the_run_before(self):
        # Monday 19: Sunday 18 (the run before, Associate 004 23:00 - 08:00); not the input's carry-in tab
        self.assertEqual(self.carried("MON", date(2026, 10, 19), "Associate 004"), [(23 * 60 - 1440, 8 * 60)])
        self.assertEqual(self.carried("MON", date(2026, 10, 19), "Associate 001"), [])

    def test_the_first_day_without_a_run_before_uses_the_input_tab(self):
        # Monday 12 has no run for Sunday 11: the tab's Associate 001 16:00 - 01:00; never this run's own Sunday
        self.assertEqual(self.carried("MON", date(2026, 10, 12), "Associate 001"), [(16 * 60 - 1440, 60)])
        self.assertEqual(self.carried("MON", date(2026, 10, 12), "Associate 004"), [])

    def test_overlapping_runs_latest_start_unless_in_use(self):
        self.assertEqual(self.run_of("MIX", date(2026, 10, 11)), "eeeeeeeeeeee")
        self.assertEqual(self.run_of("MIX", date(2026, 10, 14)), "ffffffffffff")  # the later start counts
        self.book.set_in_use(self.book.versions("eeeeeeeeeeee")[0]["id"], self.sara)
        self.assertEqual(self.run_of("MIX", date(2026, 10, 14)), "eeeeeeeeeeee")  # unless the other is in use

    def test_tomorrow_unchecked_on_the_last_day(self):
        self.assertTrue(self.days.next_week_unknown("MON", date(2026, 10, 25)))
        self.assertFalse(self.days.next_week_unknown("MON", date(2026, 10, 24)))
        self.assertFalse(self.days.next_week_unknown("MON", date(2026, 10, 18)))  # Monday 19 is covered

    def test_breaks_export_follows_a_monday_start(self):
        import io
        from openpyxl import load_workbook
        from webapp.exports import build
        data, *_ = build(self.store, self.days, date(2026, 10, 11), date(2026, 10, 12), ["breaks"], program="MON",
                         by="Omar")
        rows = list(load_workbook(io.BytesIO(data))["Breaks planned vs taken"].iter_rows(values_only=True))
        self.assertEqual({r[0] for r in rows[1:]}, {"2026-10-12"})


if __name__ == "__main__":
    unittest.main()
