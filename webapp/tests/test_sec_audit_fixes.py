# © 2026 Omar Mokhtar. All rights reserved.
"""Fixes for the leads of the 2026-11-11 source audit (evidence/phase_sec_audit/NEEDS-VALIDATION.md). Owner, 2026-11-11: "Fix all".

Each class pins one lead with made-up people and programs. The audit could not run code, so every lead is first reproduced here (red), then fixed.
Where a lead was a policy question (a supervisor managing someone who also holds other programs; an uploader keeping a run after losing its program) the
owner's "Fix all" settles it: the stricter rule is the contract."""
import io
import math
import re
import shutil
import zipfile
import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from webapp import bulk_users, erlang, volumes_io, zipcheck
from webapp import store as store_module
from webapp.access import Access
from webapp.programs import ProgramBook
from webapp.swaps import SwapBook
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


class ASwapIsAnsweredByTheAccountItWasOfferedTo(unittest.TestCase):
    """Lead swaps.answer.roster-name-without-program: ``answer`` trusted the roster name alone, and the same name may sit on associate accounts of two
    programs that share nobody, so an associate of another program could accept or decline a swap offered to someone else. The answer now needs the
    account the offer resolved: the associate account of that name that holds the swap's program."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = Store(self.dir / "scheduler.db")
        programs = ProgramBook(self.store)
        self.a, self.b = programs.add_program("ONE"), programs.add_program("TWO")
        self.unit_a, self.unit_b = programs.add_lob(self.a, "One Unit"), programs.add_lob(self.b, "Two Unit")

    def associate(self, username, program, roster="Associate 07"):
        uid = self.store.add_user(username, username.title(), "Associate-pass-1", must_change=False)
        self.store.update_user(uid, is_associate=1, roster_name=roster)
        self.store.set_user_programs(uid, [program])
        return self.store.get_user(uid)

    def swap(self, book, other="Associate 07"):
        return self.store.add_swap(program=self.unit_a, day="2026-10-14", asker="Associate 01", asker_user=1, other=other,
                                   asker_cell="09:00 - 18:00", other_cell="11:00 - 20:00")

    def test_the_named_colleague_of_that_program_can_answer(self):
        book = SwapBook(self.store, None, skills=lambda program: {})
        real = self.associate("real_one", self.a)
        sid = self.swap(book)
        self.assertEqual(book.answer(sid, real, accept=True), "Accepted. Your TM decides next.")
        self.assertEqual(self.store.get_swap(sid)["status"], "waiting_tm")

    def test_a_namesake_of_another_program_cannot_answer(self):
        book = SwapBook(self.store, None, skills=lambda program: {})
        self.associate("real_one", self.a)
        namesake = self.associate("namesake", self.b)  # same roster name, a program that shares nobody with ONE
        sid = self.swap(book)
        for accept in (True, False):
            with self.assertRaises(ValueError):
                book.answer(sid, namesake, accept=accept)
        self.assertEqual(self.store.get_swap(sid)["status"], "waiting_other")

    def test_a_namesake_cannot_answer_before_the_real_colleague_does_either(self):
        book = SwapBook(self.store, None, skills=lambda program: {})
        namesake = self.associate("namesake", self.b)
        sid = self.swap(book)  # no account of that name holds ONE at all
        with self.assertRaises(ValueError):
            book.answer(sid, namesake, accept=True)


class ACoachingCancelNeverNamesAnotherProgram(fx._Walls):
    """Lead coaching.cancel.redirect-program-name-leak: cancelling a request by number redirected to the request's own program page, so the Location header
    named the program of any request number, and told a missing number from a real one. A person who cannot open the request's program now gets the same
    answer as for a number that does not exist."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base = dict(kind="coaching", shift_date="2027-06-30", requester_name="x", names="[]", detail='{"start": 600, "minutes": 30, "billable": false}', why="", status="waiting")
        cls.theirs = cls.store.add_change_request(program=cls.bravo, requester_id=cls.users["tm_b"], **base)
        cls.ours = cls.store.add_change_request(program=cls.alpha, requester_id=cls.users["tm_a"], **base)

    def cancel(self, who, request_id):
        client = sign_in(self.app, who, fx.PASSWORD)
        return client.post(f"/requests/coaching/{request_id}/cancel", data={"csrf_token": token(client)}, follow_redirects=False)

    def test_another_programs_request_looks_like_a_missing_one(self):
        got, missing = self.cancel("plan_a", self.theirs), self.cancel("plan_a", 999999)
        self.assertEqual(got.status_code, missing.status_code)
        self.assertNotIn(self.bravo, got.headers.get("Location", ""))
        self.assertEqual(got.headers.get("Location"), missing.headers.get("Location"))
        self.assertEqual(self.store.get_change_request(self.theirs)["status"], "waiting")

    def test_a_request_of_the_persons_own_program_still_answers_with_that_program(self):
        got = self.cancel("plan_a", self.ours)  # not theirs to cancel: refused in words, back to their own program
        self.assertEqual(got.status_code, 303)
        self.assertIn("program=", got.headers["Location"])
        self.assertEqual(self.store.get_change_request(self.ours)["status"], "waiting")

    def test_the_requester_still_cancels_their_own(self):
        got = self.cancel("tm_a", self.ours)
        self.assertEqual(got.status_code, 303)
        self.assertEqual(self.store.get_change_request(self.ours)["status"], "cancelled")


def _reference_agents_needed(calls, aht_s, interval_s, target, threshold_s, max_occupancy=1.0):
    """The search as it was before the audit fix (service_level recomputed from scratch at every step): the oracle the faster search must equal."""
    traffic = erlang.erlangs(calls, aht_s, interval_s)
    if traffic <= 0:
        return 0
    n = int(math.floor(traffic)) + 1
    while traffic / n - max_occupancy > erlang.TOLERANCE or erlang.service_level(n, calls, aht_s, interval_s, threshold_s) < target - erlang.TOLERANCE:
        n += 1
    return n


class TheStaffingSearchIsLinear(unittest.TestCase):
    """Lead volumes.erlang-agents-needed.quadratic-cpu-with-large-typed-total: the search for the fewest agents recomputed the Erlang sums from scratch at
    every step, so one interval's cost grew with the square of its traffic and one large typed total could hold a server thread for minutes. The Erlang B
    sum is now carried from one step to the next (same arithmetic in the same order, so every answer is the same); an interval beyond any real centre is
    refused in words."""

    def test_the_answers_are_the_same_as_before_over_a_grid(self):
        seen = 0
        for calls in (1, 7, 30, 120, 480, 1500, 4000, 9000):
            for aht in (30.0, 180.0, 300.0, 900.0):
                for interval in (900, 1800, 3600):
                    for target, threshold in ((0.8, 20.0), (0.9, 30.0), (0.95, 10.0), (1.0, 20.0)):
                        for occupancy in (0.5, 0.85, 1.0):
                            got = erlang.agents_needed(calls, aht, interval, target, threshold, occupancy)
                            want = _reference_agents_needed(calls, aht, interval, target, threshold, occupancy)
                            self.assertEqual(got, want, (calls, aht, interval, target, threshold, occupancy))
                            seen += 1
        self.assertGreater(seen, 1000)

    def test_chat_answers_are_the_same_as_before(self):
        for calls in (10, 400, 3000):
            for concurrency in (1.0, 2.0, 3.5):
                got = erlang.chat_agents_needed(calls, 420.0, 900, 0.8, 30.0, concurrency, 0.85)
                want = _reference_agents_needed(calls, 420.0 / concurrency, 900, 0.8, 30.0, 0.85)
                self.assertEqual(got, want, (calls, concurrency))

    def test_a_very_large_interval_is_answered_quickly(self):
        # 50,000 Erlangs in one 15-minute interval with a strict service level and no occupancy cap: the service level is what binds, which is the slow
        # case (with a cap the old search stopped on occupancy before it summed the Erlang terms, and a lax answer time ends in a few steps)
        started = time.monotonic()
        n = erlang.agents_needed(150_000, 300.0, 900, 0.99, 0.0, 1.0)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertGreater(n, 50_000)

    def test_an_interval_beyond_any_real_centre_is_refused_in_words(self):
        with self.assertRaises(ValueError) as caught:
            erlang.agents_needed(5_000_000, 7200.0, 900, 0.8, 20.0, 0.85)
        self.assertIn("too large", str(caught.exception))


def _sheet(rows, dimension=None):
    """A one-sheet workbook of ``rows`` as bytes; ``dimension`` rewrites the sheet's size tag, which the uploader controls and which a reader in
    read-only mode takes the width of every row from."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    if dimension is None:
        return buf.getvalue()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                data = re.sub(rb'<dimension ref="[^"]*"\s*/>', f'<dimension ref="{dimension}"/>'.encode(), data)
            dst.writestr(info, data)
    return out.getvalue()


class TheSheetReadersAreBounded(unittest.TestCase):
    """Lead upload.read-only-iter-rows-unbounded-in-volumes-and-people-reader. The shared reader took every row, as wide as the sheet's own size tag says,
    before any row limit applied. Measured while fixing it: a tag of A1:XFD1048576 does not add rows but pads every real row to 16,384 cells, so a file
    of 100,000 short rows would hold about 13 GB of empty cells. Rows are now cut at a width no table of these sheets needs and refused beyond a row
    limit as they are read."""
    FORGED = "A1:XFD1048576"

    def test_a_forged_size_tag_does_not_widen_the_rows(self):
        data = _sheet([["username", "display name"], ["a", "A"], ["b", "B"]], dimension=self.FORGED)
        rows = bulk_users._rows(data, "people.xlsx")
        self.assertEqual(len(rows), 3)
        self.assertLessEqual(max(len(r) for r in rows), 64)
        self.assertEqual(rows[1][:2], ["a", "A"])

    def test_the_volumes_reader_reads_a_forged_file_the_same_way(self):
        data = _sheet([["date", "time", "calls"], ["2026-10-14", "09:00", 12]], dimension=self.FORGED)
        rows = volumes_io.read_table(data, "actuals.xlsx")
        self.assertLessEqual(max(len(r) for r in rows), 64)
        self.assertEqual(rows[1][:3], ["2026-10-14", "09:00", 12])

    def test_more_rows_than_the_limit_are_refused_as_they_are_read(self):
        data = _sheet([[n] for n in range(300)])
        with self.assertRaises(ValueError) as caught:
            bulk_users._rows(data, "people.xlsx", max_rows=100)
        self.assertIn("more than 100 rows", str(caught.exception))
        self.assertEqual(len(bulk_users._rows(data, "people.xlsx", max_rows=300)), 300)

    def test_csv_rows_are_bounded_too(self):
        text = ("a,b\n" * 300).encode()
        with self.assertRaises(ValueError):
            bulk_users._rows(text, "people.csv", max_rows=100)

    def test_an_ordinary_people_sheet_still_reads(self):
        rows = bulk_users.read_people(_sheet([["Username", "Display name", "Role", "Programs", "Roster name", "Team manager", "Password"],
                                              ["lina_x", "Lina X", "Planner", "NMG", "", "", ""]]), "people.xlsx")
        self.assertEqual([r["username"] for r in rows], ["lina_x"])


def _stored_zip(size):
    """A zip of one stored (uncompressed) member of ``size`` bytes: it passes the ratio rule, so only the size limits can refuse it."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"x" * size)
    return out.getvalue()


class ARunWorkbookHasARunSizedLimit(unittest.TestCase):
    """Lead upload.zipcheck-limits-too-loose-for-full-load-workbook-memory. A schedule workbook is opened whole by the web process (every cell becomes an
    object), yet the size limits were sized for a volumes file of 400,000 rows: 150 MB a member, 250 MB in all. Of the 330 workbooks in this repository the
    largest is 4.5 MB opened (1.7 MB a member). A schedule upload now has its own limit (25 MB a member, 40 MB in all, five times the largest real one);
    the volumes and people readers keep theirs."""

    def test_a_workbook_that_opens_far_beyond_any_schedule_is_refused_for_a_run(self):
        data = _stored_zip(30 * 1024 * 1024)
        self.assertEqual(zipcheck.zip_problem(data, **zipcheck.RUN_LIMITS), zipcheck.PROBLEM)

    def test_the_same_file_is_still_read_for_a_volumes_upload(self):
        self.assertEqual(zipcheck.zip_problem(_stored_zip(30 * 1024 * 1024)), "")

    def test_the_largest_real_workbook_passes_the_run_limit(self):
        from pathlib import Path
        real = Path(__file__).resolve().parents[2] / "engine" / "regression_assets" / "ready_inputs" / "SAKS_NEW_RC8_6_1_INPUT_READY.xlsx"
        self.assertEqual(zipcheck.zip_problem(real, **zipcheck.RUN_LIMITS), "")

    def test_the_run_routes_use_the_run_limit(self):
        from pathlib import Path
        for name in ("runs.py", "channel_needs.py"):
            text = (Path(__file__).resolve().parents[1] / "routes" / name).read_text()
            self.assertIn("zip_problem(path, **RUN_LIMITS)", text, name)


if __name__ == "__main__":
    unittest.main()
