# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T5: leave requests and their approval (samples ag02 and ag06; owner's answers, 2026-10-14).

An associate asks for Planned leave or a Public holiday for a run of days. Each day shows the person's shift and what
the floor loses if it is approved (the coverage decides; there is no fixed number of places). Two approvals: the TM
(a supervisor or an admin) first, then the RTA (another staff member of the program). The RTA's approval writes Leave
on the days they work into a new version of the schedule and sets it in use; days off and days with no schedule yet
are said, not changed. A Planned leave balance per person and year is shown to the approvers.
"""
import datetime as dt
import json
import re
import unittest
from datetime import date
from unittest import mock

from webapp.leave import KINDS
from webapp.programs import ProgramBook
from webapp.tests.test_runs import TOKEN, sign_in

TUE, WED, THU, FRI, SAT, SUN2 = (date(2026, 10, d) for d in (13, 14, 15, 16, 17, 18))


class _Clock(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 10, 13, 9, 0, tzinfo=tz)  # Tuesday morning: the fixture week is still to come


class _TightDay:
    """A day where every hour has exactly the people it needs: whoever is away leaves it short."""
    book = None

    def roster(self, program, on):
        return [("Associate 21", "16:00 - 22:00")]

    def version(self, program, on):
        return {"id": 1}, ""

    def page(self, program, on, extra=None):
        away = extra is not None
        cells = [{"t": t, "need": 3, "now": 2.0 if away and 960 <= t < 1320 else 3.0} for t in range(0, 1440, 60)]
        french = [{"t": t, "cls": "bad" if away and t == 1200 else "lok"} for t in range(0, 1440, 60)]
        warnings = [{"text": "20:00 to 21:00: nobody on Chat"}] if away else []
        return {"view": {"interval": 60, "cells": cells, "languages": [{"name": "French", "cells": french}],
                         "channels": {"warnings": warnings}}}


class WhatADayLoses(unittest.TestCase):
    def test_short_hours_language_and_channel(self):
        from webapp.leave import LeaveBook
        found = LeaveBook(None, _TightDay()).impact("P", "Associate 21", THU)
        self.assertEqual(found["text"], "Short by 1 from 16:00 to 22:00.")
        self.assertEqual(found["languages"], ["No French speaker from 20:00 to 21:00"])
        self.assertEqual(found["channels"], ["20:00 to 21:00: nobody on Chat"])


class Leave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)
        cls.book = cls.app.extensions["leave"]
        pid = next(p["id"] for p in ProgramBook(cls.store).tree() if p["name"] == "SAKS")
        cls.users = {}
        for username, kind in (("tm1", "supervisor"), ("rta1", "planner"), ("rta2", "planner")):
            uid = cls.store.add_user(username, username.upper(), "Staff-pass-123", must_change=False)
            cls.store.update_user(uid, is_supervisor=int(kind == "supervisor"))
            cls.store.set_user_programs(uid, [pid])
            cls.users[username] = cls.store.get_user(uid)
        uid = cls.store.add_user("a12", "Associate 012", "Associate-pass-1", must_change=False)
        cls.store.update_user(uid, is_associate=1, roster_name="Associate 012")
        cls.store.set_user_programs(uid, [pid])
        cls.users["a12"] = cls.store.get_user(uid)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def ask(self, name, first, last, kind="Planned leave", note=""):
        return self.book.ask(self.key, name, self.omar, kind, first, last, note, today=TUE)

    def cell(self, name, on):
        return dict(self.app.extensions["days"].roster(self.key, on))[name]

    # ------------------------------------------------------------------ asking
    def test_the_kinds(self):
        # re-pinned in Phase AI: the owner added exam leave (2026-10-15)
        self.assertEqual(KINDS, ("Planned leave", "Public holiday", "Exam leave"))

    def test_each_day_with_their_shift(self):
        days = self.book.days_of(self.key, "Associate 007", WED, SUN2)
        self.assertEqual([(d["date"], d["cell"]) for d in days],
                         [(WED, "18:00 - 03:00"), (THU, "OFF"), (FRI, "OFF"), (SAT, "16:00 - 01:00"), (SUN2, "")])

    def test_what_is_refused(self):
        cases = [((TUE - dt.timedelta(days=1), TUE), "Pick today or a later day."),
                 ((THU, WED), "The last day must be on or after the first."),
                 ((WED, WED + dt.timedelta(days=31)), "Ask for 31 days at most."),
                 ((THU, FRI), "Associate 007 does not work on any of these days.")]
        for (first, last), said in cases:
            with self.subTest(said):
                with self.assertRaisesRegex(ValueError, re.escape(said)):
                    self.ask("Associate 007", first, last)
        # re-pinned in Phase AI: the owner added exam leave (2026-10-15)
        with self.assertRaisesRegex(ValueError, "Pick Planned leave, Public holiday or Exam leave."):
            self.ask("Associate 007", WED, WED, kind="Sick")
        with self.assertRaisesRegex(ValueError, "Associate 999 is not on this program's schedule."):
            self.ask("Associate 999", WED, WED)

    def test_one_open_request_per_day(self):
        self.ask("Associate 008", WED, WED)
        with self.assertRaisesRegex(ValueError, re.escape("Associate 008 already asked for leave on Wed 14 Oct.")):
            self.ask("Associate 008", TUE, SAT)

    # ------------------------------------------------------------------ deciding
    def test_two_approvals_then_the_schedule_changes(self):
        before = self.app.extensions["days"].version(self.key, WED)[0]["id"]
        rid = self.ask("Associate 007", WED, SUN2, note="Family visit")
        self.assertEqual(self.store.get_leave(rid)["status"], "waiting_tm")
        with self.assertRaisesRegex(ValueError, "The first approval is the TM's: a supervisor or an admin."):
            self.book.decide(rid, self.users["rta1"], approve=True)
        self.book.decide(rid, self.users["tm1"], approve=True)
        self.assertEqual(self.store.get_leave(rid)["status"], "waiting_rta")
        self.assertEqual(self.cell("Associate 007", WED), "18:00 - 03:00")  # nothing changes before the RTA
        with self.assertRaisesRegex(ValueError, "Someone other than the TM gives the RTA's approval."):
            self.book.decide(rid, self.users["tm1"], approve=True)
        said = self.book.decide(rid, self.users["rta1"], approve=True)
        self.assertEqual(said, "Approved: Leave on Wed 14 Oct and Sat 17 Oct. Thu 15 Oct and Fri 16 Oct are days off. "
                               "Sun 18 Oct has no schedule yet: mark it when that week is planned.")
        self.assertEqual([self.cell("Associate 007", d) for d in (WED, THU, FRI, SAT)], ["Leave", "OFF", "OFF", "Leave"])
        now = self.app.extensions["days"].version(self.key, WED)[0]
        self.assertNotEqual(now["id"], before)
        self.assertTrue(now["in_use"])
        self.assertIn("Associate 007", now["label"])
        self.assertIsNotNone(self.store.get_schedule(before))  # the earlier version is kept
        row = self.store.get_leave(rid)
        self.assertEqual((row["status"], row["tm_id"], row["rta_id"]),
                         ("approved", self.users["tm1"]["id"], self.users["rta1"]["id"]))
        with self.assertRaisesRegex(ValueError, "This request was already decided: approved."):
            self.book.decide(rid, self.users["rta2"], approve=True)

    def test_refused_with_a_reason(self):
        rid = self.ask("Associate 009", FRI, FRI)
        self.book.decide(rid, self.users["tm1"], approve=False, reason="Training that day")
        row = self.store.get_leave(rid)
        self.assertEqual((row["status"], row["reason"]), ("refused", "Training that day"))
        self.assertEqual(self.cell("Associate 009", FRI), "16:00 - 01:00")

    def test_the_asker_cancels_while_it_waits(self):
        rid = self.ask("Associate 010", THU, THU)
        with self.assertRaisesRegex(ValueError, "Only the person who asked can cancel it."):
            self.book.cancel(rid, self.users["rta1"]["id"])
        self.book.cancel(rid, self.omar)
        self.assertEqual(self.store.get_leave(rid)["status"], "cancelled")
        with self.assertRaisesRegex(ValueError, "This request was already decided: cancelled."):
            self.book.cancel(rid, self.omar)

    # ------------------------------------------------------------------ what it costs
    def test_impact_of_a_day(self):
        found = self.book.impact(self.key, "Associate 008", THU)
        self.assertEqual(found["cell"], "05:00 - 14:00")
        self.assertRegex(found["text"], r"^(Coverage holds\.|Short by \d+(\.\d)? from \d\d:\d\d to \d\d:\d\d.*)$")
        self.assertEqual(self.store.list_attendance(self.key, [THU.isoformat()]), [])  # worked out, not recorded
        self.assertEqual(self.book.impact(self.key, "Associate 008", date(2026, 10, 11))["text"],
                         "Day off: nothing changes.")

    def test_the_balance_warns(self):
        self.book.set_balances(self.key, 2026, {"Associate 003": 2}, self.omar)
        rid = self.ask("Associate 003", WED, SAT)  # works Thu, Fri, Sat
        found = next(r for r in self.book.waiting(self.key) if r["id"] == rid)
        self.assertEqual(found["balance"], {"days": 2, "used": 0, "asked": 3, "left": -1})
        self.assertEqual(found["balance_text"], "Asks 3 days; 2 left this year.")
        holiday = self.ask("Associate 004", TUE, TUE, kind="Public holiday")
        self.assertIsNone(next(r for r in self.book.waiting(self.key) if r["id"] == holiday)["balance"])

    # ------------------------------------------------------------------ the pages
    def test_an_associate_asks_from_my_week(self):
        me = sign_in(self.app, "a12", "Associate-pass-1")
        tok = TOKEN.search(me.get("/me").get_data(as_text=True)).group(1)
        with mock.patch("webapp.app.datetime", _Clock):
            got = me.post("/me/leave", data={"csrf_token": tok, "kind": "Planned leave", "first": "2026-10-15",
                                             "last": "2026-10-15", "note": "Family visit",
                                             "name": "Associate 001"})  # a name sent by hand is ignored
        self.assertEqual(got.status_code, 302)
        self.assertTrue(got.headers["Location"].endswith("/me"))
        row = next(r for r in self.store.list_leave(program=self.key) if r["user_id"] == self.users["a12"]["id"])
        self.assertEqual((row["associate"], row["first_day"], row["note"]), ("Associate 012", "2026-10-15", "Family visit"))
        self.assertIn("Sent. Your TM decides first, then the RTA.", me.get("/me").get_data(as_text=True))

    def test_the_requests_page_and_its_menu_count(self):
        rid = self.ask("Associate 011", SAT, SAT)
        tm = sign_in(self.app, "tm1", "Staff-pass-123")
        page = tm.get(f"/requests?program={self.key.replace(' ', '+')}").get_data(as_text=True)
        self.assertIn("Associate 011", page)
        self.assertIn("Planned leave, Sat 17 Oct", page)
        self.assertRegex(page, r'<p class="navhead">Requests</p>\s*<a href="/requests[^"]*"[^>]*>Leave and swaps'
                               r' <span class="count"[^>]*>\d+</span></a>')
        tok = TOKEN.search(page).group(1)
        got = tm.post(f"/requests/leave/{rid}", data={"csrf_token": tok, "decision": "approve"})
        self.assertEqual(got.status_code, 302)
        self.assertEqual(self.store.get_leave(rid)["status"], "waiting_rta")
        self.assertIn("Approved by the TM: the RTA decides next.", tm.get(got.headers["Location"]).get_data(as_text=True))

    def test_the_rtas_now_panel_counts_them(self):
        self.ask("Associate 006", SAT, SAT)

        class Afternoon(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return dt.datetime(2026, 10, 14, 15, 30, tzinfo=tz)
        tm = sign_in(self.app, "tm1", "Staff-pass-123")
        with mock.patch("webapp.app.datetime", Afternoon):
            page = tm.get(f"/day?program={self.key.replace(' ', '+')}&date=2026-10-14").get_data(as_text=True)
        now = page[page.index('aria-labelledby="now-h"'):]
        self.assertRegex(now, r'<a href="/requests\?program=[^"]+">\d+ requests? waiting for you</a>')

    def test_balances_are_pasted_by_managers(self):
        tm = sign_in(self.app, "tm1", "Staff-pass-123")
        page = tm.get(f"/requests?program={self.key.replace(' ', '+')}").get_data(as_text=True)
        tok = TOKEN.search(page).group(1)
        got = tm.post("/requests/balances", data={"csrf_token": tok, "program": self.key, "year": "2026",
                                                  "rows": "Associate 004\t12\nAssociate 005, 7.5\n"},
                      follow_redirects=True).get_data(as_text=True)
        self.assertIn("Saved 2 balances for 2026.", got)
        self.assertEqual(self.book.balance(self.key, "Associate 004", 2026)["days"], 12)
        bad = tm.post("/requests/balances", data={"csrf_token": tok, "program": self.key, "year": "2026",
                                                  "rows": "Associate 999\t3\n"}, follow_redirects=True)
        self.assertIn("Associate 999 is not on this program&#39;s schedule.", bad.get_data(as_text=True))
        planner = sign_in(self.app, "rta1", "Staff-pass-123")
        refused = planner.post("/requests/balances", data={"csrf_token": TOKEN.search(planner.get("/").get_data(
            as_text=True)).group(1), "program": self.key, "year": "2026", "rows": "Associate 004\t99"})
        self.assertEqual(refused.status_code, 403)


if __name__ == "__main__":
    unittest.main()
