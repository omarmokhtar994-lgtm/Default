# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU, the gaps found on a second walk (owner: "fix the rest"): waiting requests that land on the same time say so;
approval refuses a break that is no longer where the request says; a request whose time has passed expires and says so;
a new request is posted to the LOB's group and the list is in order of urgency; a program may switch associate break
requests off, set a lead time and a daily limit."""
import json
import unittest

from webapp.change_requests import ChangeBook
from webapp.programs import ProgramBook
from webapp.tests.test_as_requests import ME, MATE, NIGHT, THU, WED, _Fixture, at


class _Rows(_Fixture):
    def row(self, name, idx, frm, to, on=WED, minutes=15, user=None, status="waiting"):
        detail = {"idx": idx, "kind": "Break 1", "minutes": minutes, "from": frm, "to": to, "level": "high",
                  "people_above": 3}
        return self.store.add_change_request(kind="break", program=self.key, shift_date=on.isoformat(),
                                             names=json.dumps([name]), requester_id=user or self.me["id"], requester_name=name,
                                             detail=json.dumps(detail), why="", status=status)

    def setUp(self):
        self.clear()


class TheOverlaps(_Rows):
    def test_requests_that_land_on_the_same_time_name_each_other_and_count_the_peak(self):
        a = self.row(ME, 0, 13 * 60, 12 * 60)
        b = self.row(MATE, 0, 14 * 60, 12 * 60 + 5)
        c = self.row(NIGHT, 0, 15 * 60, 16 * 60)               # elsewhere: not an overlap
        found = self.book.overlaps(self.book._label(self.store.get_change_request(a)),
                                   [self.book._label(self.store.get_change_request(i)) for i in (a, b, c)])
        self.assertEqual([o["names"] for o in found["others"]], [[MATE]])
        self.assertEqual(found["peak"], 2)                      # this one and one other off at once

    def test_a_request_alone_has_no_overlap(self):
        a = self.row(ME, 0, 13 * 60, 12 * 60)
        label = self.book._label(self.store.get_change_request(a))
        self.assertEqual(self.book.overlaps(label, [label])["others"], [])

    def test_the_rta_page_says_so(self):
        from webapp.tests.test_as_pages import _Pages  # noqa: F401  (the fixture clock is not needed: the rows are direct)
        a = self.row(ME, 0, 13 * 60, 12 * 60)
        self.row(MATE, 0, 14 * 60, 12 * 60 + 5)
        rows = self.book.waiting(self.key)
        first = next(r for r in rows if r["id"] == a)
        self.assertEqual(self.book.overlaps(first, rows)["peak"], 2)


class TheStaleness(_Rows):
    def test_a_break_that_moved_since_the_request_cannot_be_approved_from_the_old_time(self):
        rid = self.row(ME, 0, 13 * 60, 12 * 60)
        self.assertEqual(self.book.stale_note(self.store.get_change_request(rid), at(WED, 11)), "")
        rta = self.store.get_user(self.rta["id"])
        self.app.extensions["days"].move_break(self.key, WED, ME, 0, "13:15", rta["id"])
        self.assertIn("13:15", self.book.stale_note(self.store.get_change_request(rid), at(WED, 11)))
        with self.assertRaises(ValueError) as caught:
            self.book.decide(rid, rta, True, "", at(WED, 11))
        self.assertIn("no longer", str(caught.exception))
        self.assertEqual(self.store.get_change_request(rid)["status"], "waiting")
        self.book.decide(rid, rta, False, "Asked at the old time", at(WED, 11))    # rejecting is still possible
        self.assertEqual(self.store.get_change_request(rid)["status"], "rejected")


class TheExpiry(_Rows):
    def test_a_request_whose_time_has_passed_expires_and_the_asker_is_told(self):
        rid = self.row(ME, 0, 13 * 60, 12 * 60 + 30)
        later = self.row(ME, 1, 15 * 60, 15 * 60 + 15)
        tomorrow = self.row(ME, 0, 13 * 60, 12 * 60, on=THU)
        self.book.expire_overdue(self.key, at(WED, 12, 45))                         # 12:45: the move to 12:30 is past
        self.assertEqual(self.store.get_change_request(rid)["status"], "expired")
        self.assertEqual(self.store.get_change_request(later)["status"], "waiting")
        self.assertEqual(self.store.get_change_request(tomorrow)["status"], "waiting")
        news = self.book.news(self.me["id"])
        self.assertEqual([n["id"] for n in news], [rid])
        self.assertIn("expired", news[0]["status_words"])

    def test_coaching_expires_when_its_start_has_passed(self):
        rid = self.store.add_change_request(kind="coaching", program=self.key, shift_date=WED.isoformat(),
                                            names=json.dumps([ME]), requester_id=self.rta["id"], requester_name="Made-up",
                                            detail=json.dumps({"start": 14 * 60, "end": 14 * 60 + 30, "minutes": 30,
                                                               "dept": "", "billable": False}), why="")
        self.book.expire_overdue(self.key, at(WED, 14, 10))
        self.assertEqual(self.store.get_change_request(rid)["status"], "expired")

    def test_an_expired_request_cannot_be_decided(self):
        rid = self.row(ME, 0, 13 * 60, 12 * 60 + 30)
        self.book.expire_overdue(self.key, at(WED, 12, 45))
        with self.assertRaises(ValueError):
            self.book.decide(rid, self.store.get_user(self.rta["id"]), True, "", at(WED, 12, 45))


class TheOrderAndTheGroup(_Rows):
    def test_the_list_is_in_order_of_urgency(self):
        late = self.row(ME, 1, 15 * 60, 15 * 60 + 15)
        soon = self.row(MATE, 0, 12 * 60 + 15, 12 * 60 + 30)
        next_day = self.row(NIGHT, 0, 9 * 60, 9 * 60 + 15, on=THU)
        self.assertEqual([r["id"] for r in self.book.waiting(self.key)], [soon, late, next_day])

    def test_a_new_request_is_posted_to_the_group_without_the_reason(self):
        from webapp.notify import DEFAULT_KINDS
        with self.store._db() as db:
            db.execute("delete from notify_items")
        self.store.set_notify(self.key, link="https://hooks.slack.com/services/T000/B000/xxxxxxxxxxxxxxxxxxxxxxxx",
                              service="slack", mode="on", kinds=",".join(DEFAULT_KINDS), hold=0)
        user = self.store.get_user(self.me["id"])
        rid = self.book.ask_break(self.key, ME, user, 0, "13:30", "Made-up private reason", at(WED, 12))
        items = [i for i in self.store.notify_items(unit=self.key) if i["kind"] == "request"]
        self.assertEqual(len(items), 1)
        self.assertIn("asked", items[0]["text"])
        self.assertIn("waiting for the RTA", items[0]["text"])
        self.assertNotIn("private", items[0]["text"])
        self.assertEqual(items[0]["ref"], f"asked:{rid}")


class TheProgramsSettings(_Rows):
    def setUp(self):
        super().setUp()
        self.book = self.app.extensions["changes"]          # the site's own, wired to the program's settings
        self.programs = ProgramBook(self.store)
        self.pid = self.programs.unit(self.key)["program"]["id"]
        self.addCleanup(self.programs.set_request_settings, self.pid, True, 0, 0)

    def ask(self, idx=0, to="13:30", name=ME, now=None):
        return self.book.ask_break(self.key, name, self.store.get_user(self.me["id"]), idx, to, "", now or at(WED, 12))

    def test_the_defaults_allow_requests(self):
        self.assertEqual(self.programs.request_settings(self.pid), {"enabled": True, "lead": 0, "limit": 0})

    def test_switched_off_refuses_and_says_so(self):
        self.programs.set_request_settings(self.pid, False, 0, 0)
        with self.assertRaises(ValueError) as caught:
            self.ask()
        self.assertIn("switched off", str(caught.exception))

    def test_a_lead_time_keeps_the_next_minutes_out_of_the_choices(self):
        self.programs.set_request_settings(self.pid, True, 90, 0)                     # at 12:00 the earliest is 13:30
        options = self.book.break_options(self.key, ME, 0, at(WED, 12))
        self.assertTrue(all(c["start"] >= 13 * 60 + 30 for c in options["choices"]))

    def test_a_daily_limit_counts_waiting_and_approved_not_cancelled(self):
        self.programs.set_request_settings(self.pid, True, 0, 1)
        first = self.ask(0, "13:30")
        with self.assertRaises(ValueError) as caught:
            self.ask(1, "15:15")
        self.assertIn("1 request", str(caught.exception))
        self.book.cancel(first, self.store.get_user(self.me["id"]))
        self.ask(1, "15:15")                                                          # a cancelled one does not count

    def test_the_settings_are_checked(self):
        for bad in ((True, -1, 0), (True, 241, 0), (True, 0, -1), (True, 0, 11)):
            with self.assertRaises(ValueError):
                self.programs.set_request_settings(self.pid, *bad)


if __name__ == "__main__":
    unittest.main()


class ThePages(TheProgramsSettings):  # noqa: E301
    def test_the_setup_page_saves_the_rules(self):
        from webapp.tests.test_runs import sign_in, token
        admin = sign_in(self.app, "omar", "Owner-pass-123") if any(u["username"] == "omar" for u in self.store.list_users()) else None
        if admin is None:
            uid = self.store.add_user("omar_setup", "Omar", "Owner-pass-123", must_change=False)
            self.store.update_user(uid, is_admin=1)
            admin = sign_in(self.app, "omar_setup", "Owner-pass-123")
        page = admin.get("/setup/programs").get_data(as_text=True)
        self.assertIn("Break change requests", page)
        admin.post("/setup/programs", data={"csrf_token": token(admin), "action": "requests", "program_id": str(self.pid),
                                            "enabled": "", "lead": "20", "limit": "2"})
        self.assertEqual(self.programs.request_settings(self.pid), {"enabled": False, "lead": 20, "limit": 2})

    def test_the_associates_page_says_when_it_is_off_and_hides_the_change_links(self):
        from unittest import mock
        from webapp.tests.test_as_pages import _Noon
        from webapp.tests.test_runs import sign_in
        self.programs.set_request_settings(self.pid, False, 0, 0)
        with mock.patch("webapp.app.datetime", _Noon):
            page = sign_in(self.app, "a027", "Associate-pass-1").get("/me/breaks").get_data(as_text=True)
        self.assertIn("switched off for this program", page)
        self.assertNotIn("?change=", page)
