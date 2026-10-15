# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T6: shift swaps (sample ag07; owner's answer 6, 2026-10-14).

Two associates working the same day swap their shifts for that day: each takes the other's shift, its breaks and its
channel stretches. A swap is offered only when it keeps the rules: the rest gap for both; the same language, unless
swapping changes no language coverage; and channels: when they work different channels (Chat and Phone against all
three), only if each can work what the other's shift needs. The colleague accepts, then a supervisor or an admin
approves; the rules are checked again then, and the swap is saved as a new version set in use.
"""
import json
import unittest
from datetime import date

from webapp.programs import ProgramBook
from webapp.tests.test_runs import TOKEN, sign_in

TUE, WED = date(2026, 10, 13), date(2026, 10, 14)


class _Day:
    """A day where the two people speak different languages; ``gap`` says whether swapping opens a French gap."""
    book = None

    def __init__(self, gap):
        self.gap = gap

    def roster(self, program, on):
        return [("Associate 40", "08:00 - 17:00"), ("Associate 41", "12:00 - 21:00")]

    def version(self, program, on):
        week = {"settings": {"rest_gap_hours": 0}, "channels": [],
                "associates": [{"name": "Associate 40", "language": "French"},
                               {"name": "Associate 41", "language": "English"}]}
        return {"id": 1, "week": json.dumps(week)}, ""

    def _rest(self, *args):
        return None

    def page(self, program, on, extra=None):
        bad = self.gap and extra is not None
        return {"view": {"interval": 60, "languages": [{"name": "French", "cells": [
            {"t": t, "cls": "bad" if bad and t == 480 else "lok"} for t in range(0, 1440, 60)]}]}}


class LanguageRule(unittest.TestCase):
    def check(self, gap):
        from webapp.swaps import SwapBook
        return SwapBook(None, _Day(gap), skills=lambda program: {}).check("P", WED, "Associate 40", "Associate 41")

    def test_languages_differ_without_a_gap(self):
        found = self.check(gap=False)
        self.assertTrue(found["ok"], found["problems"])
        self.assertIn("Languages differ; no language coverage changes", found["facts"])

    def test_languages_differ_and_a_gap_opens(self):
        found = self.check(gap=True)
        self.assertFalse(found["ok"])
        self.assertEqual(found["problems"], ["Swapping leaves no French speaker from 08:00 to 09:00."])


class Swaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)
        cls.book = cls.app.extensions["swaps"]
        cls.pid = next(p["id"] for p in ProgramBook(cls.store).tree() if p["name"] == "SAKS")
        cls.users = {}
        for username, kind in (("tm1", "supervisor"), ("rta1", "planner")):
            uid = cls.store.add_user(username, username.upper(), "Staff-pass-123", must_change=False)
            cls.store.update_user(uid, is_supervisor=int(kind == "supervisor"))
            cls.store.set_user_programs(uid, [cls.pid])
            cls.users[username] = cls.store.get_user(uid)
        for n in ("006", "007", "008", "012", "014", "020", "023", "024", "026", "027", "029", "033", "038"):
            uid = cls.store.add_user(f"a{n}", f"Associate {n}", "Associate-pass-1", must_change=False)
            cls.store.update_user(uid, is_associate=1, roster_name=f"Associate {n}")
            cls.store.set_user_programs(uid, [cls.pid])
            cls.users[f"a{n}"] = cls.store.get_user(uid)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def cell(self, name, on=WED):
        return dict(self.app.extensions["days"].roster(self.key, on))[name]

    def offer(self, a, b, on=WED):
        return self.book.offer(self.key, on, f"Associate {a}", self.users[f"a{a}"]["id"], f"Associate {b}", "", today=TUE)

    # ------------------------------------------------------------------ the rules
    def test_a_swap_that_keeps_every_rule(self):
        found = self.book.check(self.key, WED, "Associate 012", "Associate 027")
        self.assertTrue(found["ok"], found["problems"])
        self.assertEqual((found["a_cell"], found["b_cell"]), ("09:00 - 18:00", "11:00 - 20:00"))
        self.assertEqual(found["facts"], ["Rest between shifts kept for both", "Same language", "Channels kept"])

    def test_the_rest_gap(self):
        found = self.book.check(self.key, WED, "Associate 012", "Associate 016")
        self.assertIn("Associate 012 would rest 7 hours before the next shift; the rule is 12.", found["problems"])

    def test_channels_one_cannot_work(self):
        found = self.book.check(self.key, WED, "Associate 012", "Associate 031")
        self.assertEqual(found["problems"], ["Associate 012 does not work Phone, which Associate 031's shift needs."])

    def test_not_a_swap(self):
        self.assertEqual(self.book.check(self.key, WED, "Associate 012", "Associate 028")["problems"],
                         ["They work the same shift that day."])
        self.assertEqual(self.book.check(self.key, WED, "Associate 012", "Associate 009")["problems"],
                         ["Associate 009 does not work on Wed 14 Oct."])

    def test_the_colleagues_offered(self):
        names = {c["name"]: c for c in self.book.candidates(self.key, WED, "Associate 012")}
        self.assertTrue(names["Associate 027"]["ok"])
        self.assertFalse(names["Associate 016"]["ok"])
        self.assertNotIn("Associate 028", names)  # the same shift
        self.assertNotIn("Associate 009", names)  # off that day

    # ------------------------------------------------------------------ the flow
    def test_accepted_then_approved_swaps_shifts_and_breaks(self):
        # each flow test has its own pair: an approved swap changes the schedule the other tests read
        breaks = lambda name: sorted((b["kind"], b["start"]) for b in json.loads(self.app.extensions["days"].version(
            self.key, WED)[0]["week"])["breaks"] if b["associate"] == name and b["day"] == "Wed")
        was_014 = breaks("Associate 014")
        stretches = lambda name: sorted((c["start"], c["end"], c["channel"]) for c in json.loads(
            self.app.extensions["days"].version(self.key, WED)[0]["week"])["channels"]
            if c["associate"] == name and c["day"] == "Wed")
        stretches_014 = stretches("Associate 014")
        self.assertTrue(stretches_014)
        sid = self.offer("007", "014")
        self.assertEqual(self.store.get_swap(sid)["status"], "waiting_other")
        with self.assertRaisesRegex(ValueError, "Only Associate 014 can answer this."):
            self.book.answer(sid, self.users["a008"], accept=True)
        self.assertEqual(self.book.answer(sid, self.users["a014"], accept=True),
                         "Accepted. Your TM decides next.")
        # re-pinned in Phase AK: the owner added team managers; a planner is still refused, told who decides
        with self.assertRaisesRegex(ValueError, r"Waiting for a team manager \(Associate \d+\) and a team manager"):
            self.book.decide(sid, self.users["rta1"], approve=True)
        said = self.book.decide(sid, self.users["tm1"], approve=True)
        self.assertEqual(said, "Approved: Associate 007 works 21:00 - 06:00 and Associate 014 works 18:00 - 03:00 "
                               "on Wed 14 Oct, each with the other's breaks and channels.")
        self.assertEqual((self.cell("Associate 007"), self.cell("Associate 014")), ("21:00 - 06:00", "18:00 - 03:00"))
        self.assertEqual(breaks("Associate 007"), was_014)
        self.assertEqual(stretches("Associate 007"), stretches_014)
        version = self.app.extensions["days"].version(self.key, WED)[0]
        self.assertTrue(version["in_use"])
        self.assertIn("Swap of Associate 007 and Associate 014", version["label"])
        with self.assertRaisesRegex(ValueError, "This swap was already decided: approved."):
            self.book.decide(sid, self.users["tm1"], approve=True)

    def test_offers_that_break_a_rule_are_refused(self):
        with self.assertRaisesRegex(ValueError, "would rest 7 hours"):
            self.offer("012", "016")
        with self.assertRaisesRegex(ValueError, "Pick today or a later day."):
            self.offer("012", "027", on=date(2026, 10, 12))

    def test_the_rules_are_checked_again_at_approval(self):
        sid = self.offer("006", "020")
        self.book.answer(sid, self.users["a020"], accept=True)
        days = self.app.extensions["days"]
        schedules = self.app.extensions["schedules"]
        changed = schedules.change(days.version(self.key, WED)[0]["id"], self.omar, "Associate 020", "Wed", "OFF", "test")
        schedules.set_in_use(changed, self.omar)
        with self.assertRaisesRegex(ValueError, "The schedule changed since it was asked: Associate 020 now has OFF "
                                                "on Wed 14 Oct."):
            self.book.decide(sid, self.users["tm1"], approve=True)
        self.assertEqual(self.store.get_swap(sid)["status"], "waiting_tm")

    def test_declined(self):
        sid = self.offer("008", "024")
        self.assertEqual(self.book.answer(sid, self.users["a024"], accept=False), "Declined.")
        self.assertEqual(self.store.get_swap(sid)["status"], "declined")

    # ------------------------------------------------------------------ the pages
    def test_an_associate_offers_from_my_week(self):
        me = sign_in(self.app, "a029", "Associate-pass-1")
        page = me.get("/me?swap=2026-10-15").get_data(as_text=True)
        self.assertIn('name="other" value="Associate 038"', page)
        self.assertNotIn('name="other" value="Associate 033"', page)  # has an account, but the rest gap breaks
        tok = TOKEN.search(page).group(1)
        from unittest import mock
        from webapp.tests.test_ag_leave import _Clock
        with mock.patch("webapp.app.datetime", _Clock):
            got = me.post("/me/swap", data={"csrf_token": tok, "day": "2026-10-15", "other": "Associate 038"})
        self.assertEqual(got.status_code, 302)
        self.assertIn("Sent to Associate 038. Once they accept, your TM decides.", me.get("/me").get_data(as_text=True))

    def test_the_requests_page_lists_swaps(self):
        sid = self.offer("023", "026", on=date(2026, 10, 15))
        self.book.answer(sid, self.users["a026"], accept=True)
        tm = sign_in(self.app, "tm1", "Staff-pass-123")
        page = tm.get(f"/requests?program={self.key.replace(' ', '+')}").get_data(as_text=True)
        self.assertIn("Associate 023 and Associate 026", page)
        self.assertIn(f'action="/requests/swap/{sid}"', page)


if __name__ == "__main__":
    unittest.main()
