# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: the site must carry 500 users): a day is built once and kept until anything is written.
Every kind of change must clear it, a kept day is handed out as a copy, and a page that asks for something else than the
plain day (counted as if, as planned, another version) is never answered from it. Made-up "Associate NN" data."""
import time
import unittest
from datetime import date
from unittest import mock

from webapp import attendance as att
from webapp.tests.test_notify_daybook import WED, _Tagged, hm

THU = date(2026, 10, 15)


class TheCache(_Tagged):
    def builds(self):
        """Count the full builds of a day while the block runs."""
        return mock.patch.object(att, "day_view", wraps=att.day_view)

    @unittest.skipIf(att.VERIFY_PAGES, "the checking mode builds the day again on purpose")
    def test_the_second_look_at_a_day_is_not_built_again(self):
        self.days.page(self.key, WED)
        with self.builds() as built:
            for _ in range(3):
                self.days.page(self.key, WED)
        self.assertEqual(built.call_count, 0)

    def test_a_kept_day_is_the_same_day(self):
        first = self.days.page(self.key, WED)
        again = self.days.page(self.key, WED)
        for k in ("view", "target", "log", "date", "day", "week_start", "unlisted", "stale"):
            self.assertEqual(first[k], again[k], k)

    def test_what_a_caller_changes_in_its_copy_is_not_seen_by_the_next(self):
        first = self.days.page(self.key, WED)
        first["view"]["lanes"].clear()
        first["view"]["cells"][0]["now"] = -999
        first["target"]["target"] = -1
        again = self.days.page(self.key, WED)
        self.assertTrue(again["view"]["lanes"])
        self.assertNotEqual(again["view"]["cells"][0]["now"], -999)
        self.assertNotEqual(again["target"]["target"], -1)

    def test_a_reader_that_only_reads_may_ask_for_the_kept_day_itself(self):
        one = self.days.page(self.key, WED, shared=True)
        two = self.days.page(self.key, WED, shared=True)
        self.assertIs(one, two)
        self.assertIsNot(self.days.page(self.key, WED), one)  # everyone else still gets a copy

    def test_the_channel_counters_a_replan_changes_are_not_shared_between_copies(self):
        one = self.days.page(self.key, WED)
        hold = (one["view"].get("channels") or {}).get("hold")
        if hold is None:
            self.skipTest("this fixture's day has no channel counters")
        name = next(iter(hold.who[0]), (0, ""))[1] if hold.who else ""
        before = [list(v) for v in self.days.page(self.key, WED)["view"]["channels"]["hold"].language]
        for row in hold.language:
            for i in range(len(row)):
                row[i] += 99
        again = self.days.page(self.key, WED)["view"]["channels"]["hold"].language
        self.assertEqual([list(v) for v in again], before)

    def test_days_programs_and_measures_are_kept_apart(self):
        self.days.page(self.key, WED)
        with self.builds() as built:
            self.days.page(self.key, THU)
            self.days.page(self.quiet, WED)
            self.days.page(self.key, WED, "sl")
        self.assertEqual(built.call_count, 3)

    def test_asking_for_something_other_than_the_plain_day_is_never_answered_from_it(self):
        self.days.page(self.key, WED)
        name, idx, kind, start, _ = self.with_breaks()
        with self.builds() as built:
            self.days.page(self.key, WED, recorded=False)
            self.days.page(self.key, WED, cover=False)
            self.days.page(self.key, WED, extra={"break": (name, idx, start + 5)})
        self.assertEqual(built.call_count, 3)

    def test_the_checking_mode_names_a_kept_day_that_is_out_of_date(self):
        self.days.page(self.key, WED)
        key = (self.key, WED, self.days.measure_of(self.key))
        generation, built_at, page = self.days._pages[key]
        self.addCleanup(self.days._pages.clear)  # the tampered day must not outlive this test
        page["view"]["cells"][0]["now"] = -123  # a kept day that no longer matches the data
        with mock.patch.object(att, "VERIFY_PAGES", True), self.assertRaises(AssertionError) as said:
            self.days.page(self.key, WED)
        self.assertIn("differs from a fresh build", str(said.exception))
        self.assertIn("cells", str(said.exception))

    def test_time_alone_clears_it_after_the_safety_expiry(self):
        self.days.page(self.key, WED)
        with self.builds() as built, mock.patch.object(att.time, "monotonic", return_value=time.monotonic() + att.PAGE_KEEP + 1):
            self.days.page(self.key, WED)
        self.assertEqual(built.call_count, 1)


class AFileChangeClearsItToo(_Tagged):
    """The checking mode found this one: channel needs added to a schedule are a file, so no row changed and the kept day
    went on showing the schedule as it was before they were added."""
    def test_adding_channel_needs_clears_the_kept_day(self):
        from webapp.tests.test_channel_needs import filled
        import tempfile
        from pathlib import Path
        version = self.days.version(self.key, WED)[0]
        self.days.page(self.key, WED)
        before = self.store.generation
        path = filled(Path(tempfile.mkdtemp()) / "needs.xlsx", 60)
        self.addCleanup(path.unlink, True)
        run = version["run_id"]
        try:
            self.app.extensions["schedules"].attach_channels(run, path)
        except ValueError:
            self.skipTest("these channel needs do not fit this fixture's week")
        self.addCleanup((self.app.extensions["schedules"].root / run / "channels.xlsx").unlink, True)
        self.assertGreater(self.store.generation, before)

    def test_an_expired_run_clears_it(self):
        before = self.store.generation
        self.store.invalidate_days()
        self.assertGreater(self.store.generation, before)


class EveryWriteClearsIt(_Tagged):
    def seg(self, name):
        lane = next(l for l in self.days.page(self.key, WED)["view"]["lanes"] if l["name"] == name)
        return next(s for s in lane["segments"] if s["offset"] == 0)

    def test_a_read_does_not_clear_it_and_a_write_does(self):
        before = self.store.generation
        self.days.page(self.key, WED)
        self.assertEqual(self.store.generation, before)
        self.store.set_attendance(program=self.key, shift_date=WED.isoformat(), associate="Associate 008", status="Present",
                                  from_min=None, to_min=None, user_id=self.omar)
        self.assertGreater(self.store.generation, before)

    def test_sign_ins_events_requests_and_incidents_do_not_clear_it(self):
        before = self.store.generation
        self.store.add_user("quiet1", "Quiet One", "Quiet-pass-123", must_change=False)
        self.store.authenticate("quiet1", "Quiet-pass-123")
        self.store.add_event(kind="signed_in", detail="x", user_id=self.omar)
        self.store.add_incident(program=self.key, shift_date=WED.isoformat(), associate="Associate 008", kind="x", user_id=self.omar, at=1.0)
        self.assertEqual(self.store.generation, before)

    def test_attendance(self):
        name = self.with_breaks()[0]
        self.days.set_status(self.key, WED, name, "Sick", self.omar)
        self.addCleanup(self.days.set_status, self.key, WED, name, "Present", self.omar)
        self.assertEqual(self.seg(name)["status"], "Sick")

    def test_a_break_move_and_its_undo(self):
        name, idx, kind, start, _ = self.with_breaks()
        self.days.page(self.key, WED)
        self.days.move_break(self.key, WED, name, idx, hm(start + 5), self.omar)
        self.addCleanup(self.days.move_break, self.key, WED, name, idx, None, self.omar)
        moved = next(b for b in self.seg(name)["breaks"] if b["idx"] == idx)
        self.assertEqual(moved["start"], start + 5)
        self.days.undo_last(self.key, WED, self.omar)
        back = next(b for b in self.seg(name)["breaks"] if b["idx"] == idx)
        self.assertEqual(back["start"], start)

    def test_an_activity_a_session_and_their_removal(self):
        name, idx, kind, start, _ = self.with_breaks()
        self.days.page(self.key, WED)
        seg = self.seg(name)
        lo = next(s["start"] for s in self.days.meeting_slots(self.key, WED, [name], 30, hm(seg["start"] % 1440), hm(seg["end"] % 1440 or 1439)))
        self.days.book_session(self.key, WED, [name], lo, 30, "Coaching", self.omar, with_whom="Lead", why="x")
        self.assertTrue(any(a["kind"] == "Coaching" for a in self.seg(name)["activities"]))
        sid = self.days.sessions(self.key, WED)[0]["session"]
        self.days.cancel_session(self.key, WED, sid, [name], self.omar)
        self.assertFalse(any(a["kind"] == "Coaching" for a in self.seg(name)["activities"]))

    def test_a_schedule_edit(self):
        import json
        row = self.days.version(self.key, WED)[0]
        self.days.page(self.key, WED)
        week = json.loads(row["week"])
        week["associates"][0]["days"][3] = "OFF"
        gone = week["associates"][0]["name"]
        original = row["week"]
        self.store.update_schedule(row["id"], week=json.dumps(week))
        self.addCleanup(self.store.update_schedule, row["id"], week=original)
        names = {l["name"] for l in self.days.page(self.key, WED)["view"]["lanes"]
                 if any(s["offset"] == 0 for s in l["segments"])}
        self.assertNotIn(gone, names)

    def test_a_setting_that_changes_the_day(self):
        before = self.days.page(self.key, WED)["target"]["target"]
        self.store.set_interval_target(self.key, "2026-10-11", 63 if round(before * 100) != 63 else 64, self.omar)
        self.addCleanup(self.clear_targets)
        self.assertNotEqual(self.days.page(self.key, WED)["target"]["target"], before)

    def clear_targets(self):
        with self.store._db() as db:
            db.execute("delete from interval_targets")


if __name__ == "__main__":
    unittest.main()


class TheServer(unittest.TestCase):
    def test_the_server_accepts_more_than_100_open_connections(self):
        from webapp import serve
        with mock.patch.dict("os.environ", {"SCHEDULER_DATA_DIR": "/tmp/x"}), mock.patch("webapp.app.create_app"), mock.patch("waitress.serve") as run:
            serve.main()
        self.assertEqual(run.call_args.kwargs["connection_limit"], 1000)
        self.assertEqual(run.call_args.kwargs["threads"], 8)


class TheBusyHour(unittest.TestCase):
    """What the people of a busy hour do (sign in, look at their day and their weeks, look at the RTA's pages) writes
    nothing a kept day is built from, so it does not clear it."""
    @classmethod
    def setUpClass(cls):
        from webapp.tests.test_as_requests import _Fixture
        _Fixture.setUpClass.__func__(cls)
        cls._fixture = _Fixture

    @classmethod
    def tearDownClass(cls):
        cls._fixture.tearDownClass.__func__(cls)

    def test_signing_in_and_looking_at_pages_keeps_the_days(self):
        from webapp.tests.test_runs import sign_in
        before = self.store.generation
        associate = sign_in(self.app, "a027", "Associate-pass-1")
        rta = sign_in(self.app, "rta1", "Staff-pass-123")
        q = self.key.replace(" ", "+")
        for client, url in ((associate, "/me/breaks"), (associate, "/me"), (rta, f"/day?program={q}&date=2026-10-14"),
                            (rta, f"/incidents?program={q}&from=2026-10-11&to=2026-10-14"),
                            (rta, f"/shrinkage?program={q}&from=2026-10-11&to=2026-10-14")):
            self.assertEqual(client.get(url).status_code, 200, url)
        self.assertEqual(self.store.generation, before)
