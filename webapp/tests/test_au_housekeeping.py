# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU, found by walking the journeys again: a renamed LOB keeps its waiting break and coaching requests; a person
switched off or deleted leaves no request waiting for the RTA; a new password has to differ from the one it replaces."""
import json
import re
import tempfile
import time
import unittest
from pathlib import Path

from webapp.store import Store
from webapp.tests.test_runs import make_app


def fresh():
    return Store(Path(tempfile.mkdtemp()) / "scheduler.db")


class TheRename(unittest.TestCase):
    def test_a_renamed_program_keeps_its_break_and_coaching_requests(self):
        store = fresh()
        uid = store.add_user("a1", "A One", "Password-1234", must_change=False)
        rid = store.add_change_request(kind="break", program="SAKS Tier 1", shift_date="2026-10-14",
                                       names=json.dumps(["Associate 001"]), requester_id=uid, requester_name="A One",
                                       detail="{}", why="")
        store.rename_program("SAKS Tier 1", "SAKS Tier One", [])
        self.assertEqual(store.get_change_request(rid)["program"], "SAKS Tier One")


class ThePersonWhoLeaves(unittest.TestCase):
    def setUp(self):
        self.store = store = fresh()
        self.uid = store.add_user("a1", "A One", "Password-1234", must_change=False)
        self.other = store.add_user("a2", "A Two", "Password-1234", must_change=False)
        self.change = store.add_change_request(kind="break", program="P", shift_date="2026-10-14",
                                               names=json.dumps(["A One"]), requester_id=self.uid, requester_name="A One",
                                               detail="{}", why="")
        self.done = store.add_change_request(kind="break", program="P", shift_date="2026-10-13",
                                             names=json.dumps(["A One"]), requester_id=self.uid, requester_name="A One",
                                             detail="{}", why="", status="approved")
        self.theirs = store.add_change_request(kind="break", program="P", shift_date="2026-10-14",
                                               names=json.dumps(["A Two"]), requester_id=self.other,
                                               requester_name="A Two", detail="{}", why="")
        self.leave = store.add_leave(program="P", associate="A One", user_id=self.uid, kind="Planned leave",
                                     first_day="2026-10-20", last_day="2026-10-21", status="waiting_rta")
        self.swap = store.add_swap(program="P", day="2026-10-15", asker="A One", asker_user=self.uid, other="A Two",
                                   asker_cell="09:00 - 18:00", other_cell="11:00 - 20:00")

    def check(self):
        s = self.store
        self.assertEqual(s.get_change_request(self.change)["status"], "cancelled")
        self.assertEqual(s.get_change_request(self.done)["status"], "approved")     # an answer already given stays
        self.assertEqual(s.get_change_request(self.theirs)["status"], "waiting")    # someone else's is not touched
        self.assertEqual(s.get_leave(self.leave)["status"], "cancelled")
        self.assertEqual(s.get_swap(self.swap)["status"], "cancelled")

    def test_switching_a_person_off_cancels_what_they_had_waiting(self):
        self.store.set_active(self.uid, False)
        self.check()
        self.store.set_active(self.uid, True)                                       # switching on does not revive them
        self.assertEqual(self.store.get_change_request(self.change)["status"], "cancelled")

    def test_deleting_a_person_cancels_what_they_had_waiting(self):
        self.store.delete_user(self.uid)
        self.check()


class TheNewPassword(unittest.TestCase):
    def test_it_has_to_differ_from_the_current_one(self):
        app, store, *_ = make_app(start_worker=False)
        store.add_user("pat", "Pat", "Password1!", must_change=True)
        client = app.test_client()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)
        client.post("/login", data={"username": "pat", "password": "Password1!", "csrf_token": tok})
        page = client.get("/account/password").get_data(as_text=True)
        tok = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        got = client.post("/account/password", data={"csrf_token": tok, "current": "Password1!", "new": "Password1!",
                                                     "confirm": "Password1!"}, follow_redirects=True)
        self.assertIn("different from your current", got.get_data(as_text=True).replace("&nbsp;", " "))
        self.assertEqual(store.get_user_by_name("pat")["must_change"], 1)           # still has to choose one
        ok = client.post("/account/password", data={"csrf_token": tok, "current": "Password1!", "new": "Another-1234x",
                                                    "confirm": "Another-1234x"}, follow_redirects=True)
        self.assertIn("Password changed", ok.get_data(as_text=True))
        self.assertEqual(store.get_user_by_name("pat")["must_change"], 0)


if __name__ == "__main__":
    unittest.main()
