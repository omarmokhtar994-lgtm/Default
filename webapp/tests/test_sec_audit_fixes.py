# © 2026 Omar Mokhtar. All rights reserved.
"""Fixes for the leads of the 2026-11-11 source audit (evidence/phase_sec_audit/NEEDS-VALIDATION.md). Owner, 2026-11-11: "Fix all".

Each class pins one lead with made-up people and programs. The audit could not run code, so every lead is first reproduced here (red), then fixed.
Where a lead was a policy question (a supervisor managing someone who also holds other programs; an uploader keeping a run after losing its program) the
owner's "Fix all" settles it: the stricter rule is the contract."""
import shutil
import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from webapp import store as store_module
from webapp.access import Access
from webapp.store import LOCK_AFTER_FAILURES, Store
from webapp.tests import test_ar_walls as fx
from webapp.tests.test_channel_people import add_version
from webapp.tests.test_programs import TheAccess
from webapp.tests.test_runs import sign_in, token


class ManagersStayInsideTheirPrograms(TheAccess):
    """Lead people.can_manage.partial-overlap-takeover: sharing one program was enough to reset the password of (and so sign in as) a person who also holds
    programs the supervisor does not. A manager now acts only on people whose programs are all the manager's own."""
    test_planner_sees_only_their_programs = test_people_from_before_keep_all_programs = None
    test_supervisor_manages_their_programs_planners_only = None

    def test_a_person_with_programs_beyond_the_supervisors_is_not_manageable(self):
        sup = self.person("sami2", supervisor=True, programs=["NMG"])
        inside = self.person("lina2", programs=["NMG"])
        straddler = self.person("dina2", programs=["NMG", "AE/AR B2B"])
        boss = Access(self.store, sup)
        self.assertTrue(boss.can_manage(inside))
        self.assertFalse(boss.can_manage(straddler))

    def test_a_supervisor_with_both_programs_manages_the_straddler(self):
        both = self.person("sami3", supervisor=True, programs=["NMG", "AE/AR B2B"])
        straddler = self.person("dina3", programs=["NMG", "AE/AR B2B"])
        self.assertTrue(Access(self.store, both).can_manage(straddler))

    def test_a_person_with_no_programs_is_still_not_manageable(self):
        sup = self.person("sami4", supervisor=True, programs=["NMG"])
        nobody = self.person("nora4", programs=[])
        self.assertFalse(Access(self.store, sup).can_manage(nobody))


class ARunOutlivesNothing(fx._Walls):
    """Lead runs.uploader-access-outlives-program-removal: the uploader of a run kept reading, editing, deleting and setting it in use after an admin took the
    run's program away from them (and setting it in use flips the schedule the program's day pages read). Access to a run with a program now always needs
    that program; a run with no program stays with its uploader."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ex = cls.store.add_user("ex_member", "Ex Member", fx.PASSWORD, must_change=False)
        cls.store.set_user_programs(cls.ex, [cls.alpha_id])
        cls.rid = "00000000a900"
        cls.sid = add_version(cls.store, cls.alpha, fx.WEEK, [("Alpha Person One", "English")], run_id=cls.rid)
        cls.store.update_run(cls.rid, user_id=cls.ex)

    def setUp(self):
        self.store.set_user_programs(self.ex, [self.alpha_id])

    def lose_alpha(self):
        self.store.set_user_programs(self.ex, [self.bravo_id])

    def post(self, client, url, **data):
        return client.post(url, data={"csrf_token": token(client), **data}, follow_redirects=False)

    def test_the_uploader_works_with_the_run_while_they_hold_the_program(self):
        client = sign_in(self.app, "ex_member", fx.PASSWORD)
        self.assertEqual(client.get(f"/runs/{self.rid}/schedules").status_code, 200)
        self.assertNotEqual(self.post(client, f"/schedules/{self.sid}/in-use").status_code, 403)

    def test_after_losing_the_program_the_uploader_is_refused_everywhere(self):
        client = sign_in(self.app, "ex_member", fx.PASSWORD)
        self.lose_alpha()
        for method, url in (("get", f"/runs/{self.rid}"), ("get", f"/runs/{self.rid}/schedules"),
                            ("get", f"/runs/{self.rid}/schedule"), ("get", f"/schedules/{self.sid}/download"),
                            ("post", f"/schedules/{self.sid}/in-use"), ("post", f"/runs/{self.rid}/delete"),
                            ("post", f"/runs/{self.rid}/tag"), ("post", f"/runs/{self.rid}/start")):
            with self.subTest(url):
                got = client.get(url) if method == "get" else self.post(client, url, confirm="1", week_start="2026-10-18")
                self.assertEqual(got.status_code, 403)
        self.assertIsNotNone(self.store.get_run(self.rid))  # nothing was deleted
        self.assertEqual(self.store.get_run(self.rid)["week_start"], fx.WEEK)

    def test_after_losing_the_program_the_run_is_not_listed(self):
        client = sign_in(self.app, "ex_member", fx.PASSWORD)
        self.lose_alpha()
        for url in ("/", "/programs"):
            with self.subTest(url):
                self.assertNotIn("00000000a900", client.get(url).get_data(as_text=True))

    def test_a_run_with_no_program_stays_with_its_uploader(self):
        self.store.add_run("00000000a901", self.ex, "mine.xlsx", "READY", "DONE", program="", week_start=fx.WEEK)
        client = sign_in(self.app, "ex_member", fx.PASSWORD)
        self.lose_alpha()
        self.assertEqual(client.get("/runs/00000000a901").status_code, 200)


class TheDayPageChecksEveryProgramAndEveryDate(fx._Walls):
    """Leads day.post.program.gate-source-mismatch and day.replan-rescue.dated-move-bypasses-back-limit. The program wall read the query string first while the
    day handlers read the form field, so ``?program=ALPHA`` (or an empty ``?program=``) with a form naming BRAVO passed the wall and wrote BRAVO's day. The
    wall now checks every program a request names. The role back-limit (planner 1 day, supervisor 7, admin none) looked only at the form's date and first;
    a move dated in the form, or a window starting days back, slipped past it. It now checks every date the request names."""
    TODAY = date(2026, 10, 14)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app.config["TODAY"] = cls.TODAY

    @classmethod
    def tearDownClass(cls):
        cls.app.config.pop("TODAY", None)

    def post(self, client, url, **data):
        return client.post(url, data={"csrf_token": token(client), **data}, follow_redirects=False)

    def test_a_form_program_the_person_cannot_open_is_refused_whatever_the_query_says(self):
        client = sign_in(self.app, "plan_a", fx.PASSWORD)
        for endpoint in ("break", "send", "cover", "attendance", "bulk/apply", "replan/apply", "rescue/apply"):
            for query in ("", f"?program={self.alpha}", "?program=", f"?program={self.alpha}&program={self.bravo}"):
                with self.subTest(endpoint=endpoint, query=query):
                    got = self.post(client, f"/day/{endpoint}{query}", program=self.bravo, date="2026-10-14")
                    self.assertEqual(got.status_code, 403)

    def test_a_form_program_the_person_can_open_is_not_refused(self):
        client = sign_in(self.app, "plan_a", fx.PASSWORD)
        got = self.post(client, f"/day/break?program={self.alpha}", program=self.alpha, date="2026-10-14")
        self.assertNotEqual(got.status_code, 403)

    def closed_message(self, got, client):
        self.assertEqual(got.status_code, 303)
        return "closed to changes for your role" in client.get(got.headers["Location"]).get_data(as_text=True)

    def test_a_planner_cannot_move_a_break_on_a_day_dated_inside_the_form(self):
        client = sign_in(self.app, "plan_a", fx.PASSWORD)
        old = "2026-10-04"  # ten days before the pinned today
        for endpoint in ("replan/apply", "rescue/apply"):
            with self.subTest(endpoint):
                got = self.post(client, f"/day/{endpoint}", program=self.alpha, date="2026-10-14",
                                move=f"Alpha Person One|0|600|{old}")
                self.assertTrue(self.closed_message(got, client))

    def test_a_planner_cannot_start_a_window_days_back(self):
        client = sign_in(self.app, "plan_a", fx.PASSWORD)
        for endpoint in ("bulk/apply", "rescue/apply"):
            with self.subTest(endpoint):
                got = self.post(client, f"/day/{endpoint}", program=self.alpha, date="2026-10-14", start="-9999")
                self.assertTrue(self.closed_message(got, client))

    def test_dates_inside_the_planners_limit_are_not_closed(self):
        client = sign_in(self.app, "plan_a", fx.PASSWORD)
        got = self.post(client, "/day/replan/apply", program=self.alpha, date="2026-10-14", move="Alpha Person One|0|600|2026-10-13")
        self.assertFalse(self.closed_message(got, client))

    def test_a_supervisor_has_seven_days_and_an_admin_has_no_limit(self):
        for who, closed in (("sup_a", True), ("omar", False)):
            with self.subTest(who):
                client = sign_in(self.app, who, "Owner-pass-123" if who == "omar" else fx.PASSWORD)
                got = self.post(client, "/day/replan/apply", program=self.alpha, date="2026-10-14", move="Alpha Person One|0|600|2026-10-01")
                self.assertEqual(self.closed_message(got, client), closed)


class SignInHoldsUnderParallelGuesses(unittest.TestCase):
    """Leads h1-lockout-counter-lost-update and h1-login-timing-padded-password-enumeration. The count of wrong passwords was read before the (slow) hash
    and written after it as an absolute number, so guesses made at the same moment shared one stale count and the 5-try lock came late or was overwritten;
    a guess already past the lock check could still sign in. A padded wrong password cost two hashes for a real account and one for an unknown or locked
    one, so the time told which usernames exist. The count is now one atomic update, a right password re-checks the lock when it is done, and every
    answer costs the same two hashes. The hash is held at a barrier here so the overlap is certain, not a matter of timing."""
    GOOD = "Right-pass-12345"

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = Store(self.dir / "scheduler.db")
        self.uid = self.store.add_user("dana", "Dana", self.GOOD, must_change=False)

    def row(self):
        return self.store.get_user(self.uid)

    def test_guesses_made_at_the_same_moment_all_count(self):
        tries = LOCK_AFTER_FAILURES + 1
        gate = threading.Barrier(tries, timeout=20)
        real = store_module.check_password_hash

        def held(hashed, password):
            gate.wait()  # every guess has read the row before any of them writes
            return real(hashed, password)

        answers = []
        with mock.patch.object(store_module, "check_password_hash", held):
            threads = [threading.Thread(target=lambda: answers.append(self.store.authenticate("dana", "Wrong-pass-9999")[1]))
                       for _ in range(tries)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)
        self.assertEqual(len(answers), tries)
        self.assertGreater(self.row()["locked_until"], time.time(), "six wrong guesses at once must lock the account")
        self.assertEqual(self.store.authenticate("dana", self.GOOD)[1], "locked")

    def test_a_right_password_that_was_already_past_the_lock_check_does_not_sign_in(self):
        started, release = threading.Event(), threading.Event()
        real = store_module.check_password_hash

        def held(hashed, password):
            if password == self.GOOD:
                started.set()
                release.wait(20)  # the right guess waits inside the hash while the account gets locked
            return real(hashed, password)

        out = []
        with mock.patch.object(store_module, "check_password_hash", held):
            worker = threading.Thread(target=lambda: out.append(self.store.authenticate("dana", self.GOOD)))
            worker.start()
            self.assertTrue(started.wait(20))
            with self.store._db() as db:
                db.execute("update users set locked_until = ? where id = ?", (time.time() + 600, self.uid))
            release.set()
            worker.join(30)
        self.assertEqual(out[0][1], "locked")
        self.assertIsNone(out[0][0])

    def test_the_lock_still_comes_on_the_fifth_wrong_guess_one_after_another(self):
        for n in range(1, LOCK_AFTER_FAILURES):
            self.assertEqual(self.store.authenticate("dana", "Wrong-pass-9999")[1], "bad", n)
        self.assertEqual(self.store.authenticate("dana", "Wrong-pass-9999")[1], "locked")
        self.assertEqual(self.store.authenticate("dana", self.GOOD)[1], "locked")

    def test_a_right_password_clears_the_count(self):
        self.store.authenticate("dana", "Wrong-pass-9999")
        self.assertEqual(self.store.authenticate("dana", self.GOOD)[1], "ok")
        self.assertEqual(self.row()["failed"], 0)

    def test_every_answer_costs_the_same_number_of_hashes(self):
        locked = self.store.add_user("lena", "Lena", self.GOOD, must_change=False)
        with self.store._db() as db:
            db.execute("update users set locked_until = ? where id = ?", (time.time() + 600, locked))
        real, counts = store_module.check_password_hash, []

        def counted(hashed, password):
            counts[-1] += 1
            return real(hashed, password)

        cases = {"unknown": ("nobody", "Wrong-pass-9999"), "unknown padded": ("nobody", " Wrong-pass-9999 "),
                 "locked": ("lena", "Wrong-pass-9999"), "locked padded": ("lena", " Wrong-pass-9999 "),
                 "real wrong": ("dana", "Wrong-pass-9999"), "real wrong padded": ("dana", "\u00a0Wrong-pass-9999\n"),
                 "real right": ("dana", self.GOOD), "real right padded": ("dana", f" {self.GOOD} ")}
        got = {}
        with mock.patch.object(store_module, "check_password_hash", counted):
            for name, (who, password) in cases.items():
                counts.append(0)
                self.store.authenticate(who, password)
                got[name] = counts[-1]
        self.assertEqual(set(got.values()), {2}, got)


if __name__ == "__main__":
    unittest.main()
