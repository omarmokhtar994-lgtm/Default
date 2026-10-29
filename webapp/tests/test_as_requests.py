# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AS (owner, 2026-10-21): an associate asks to move a break on the running day (up to the end of an overnight
shift), a team manager asks for coaching, and the RTA decides each with the intervals' impact in front of them.
Answers: all breaks and lunch may be moved; departments are named on the team manager's request; coaching may be
asked for the running day and later days."""
import json
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from webapp.change_requests import HIGH, LOW, ChangeBook
from webapp.tests import test_ag_swaps

CAIRO = ZoneInfo("Africa/Cairo")
WED, THU = date(2026, 10, 14), date(2026, 10, 15)
ME, NIGHT, MATE = "Associate 027", "Associate 029", "Associate 012"


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=CAIRO)


class _Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_ag_swaps.Swaps.setUpClass.__func__(cls)
        wed = cls.app.extensions["days"].version(cls.key, WED)[0]
        week = json.loads(wed["week"])
        for a in week["associates"]:
            if a["name"] == NIGHT:
                a["days"][3] = "22:00 - 07:00"
        week["breaks"] += [
            {"associate": ME, "day": "Wed", "kind": "Break 1", "start": "13:00", "minutes": 15},
            {"associate": ME, "day": "Wed", "kind": "Lunch", "start": "15:00", "minutes": 30},
            {"associate": NIGHT, "day": "Wed", "kind": "Break 1", "start": "00:30", "minutes": 15},
            {"associate": NIGHT, "day": "Wed", "kind": "Lunch", "start": "03:00", "minutes": 30}]
        cls.store.update_schedule(wed["id"], week=json.dumps(week))
        cls.book = ChangeBook(cls.store, cls.app.extensions["days"])
        cls.rta = cls.users["rta1"]
        cls.me = cls.users["a027"]
        cls.night = cls.users["a029"]

    @classmethod
    def tearDownClass(cls):
        test_ag_swaps.Swaps.tearDownClass.__func__(cls)

    def clear(self):
        """A clean day: no requests and none of the day's records, so the tests do not depend on their order."""
        with self.store._db() as db:
            for table in ("change_requests", "attendance", "actual_breaks", "activities", "day_log", "day_actions"):
                db.execute(f"delete from {table}")

    def other(self, options, n=0):
        """The n-th time offered that is not the one the break has now, as HH:MM."""
        m = [c["start"] for c in options["choices"] if not c["current"]][n]
        return f"{(m // 60) % 24:02d}:{m % 60:02d}", m


class TheBreakRequests(_Fixture):
    def setUp(self):
        self.clear()

    def test_the_running_shift_is_found_and_its_choices_start_now_and_include_the_current_time(self):
        options = self.book.break_options(self.key, ME, 0, at(WED, 12))
        self.assertEqual((options["kind"], options["current"]), ("Break 1", 13 * 60))
        starts = [c["start"] for c in options["choices"]]
        self.assertTrue(all(s >= 12 * 60 for s in starts))
        self.assertIn(13 * 60, starts)
        self.assertEqual([c["start"] for c in options["choices"] if c["current"]], [13 * 60])  # the plan, on a clean day
        self.assertTrue(all(c["level"] in (HIGH, "moderate", LOW) for c in options["choices"]))

    def test_a_shift_that_is_over_or_a_day_off_has_nothing_to_change(self):
        with self.assertRaises(ValueError):
            self.book.break_options(self.key, ME, 0, at(WED, 21))
        with self.assertRaises(ValueError):
            self.book.break_options(self.key, ME, 0, at(date(2026, 10, 10), 12))  # nothing running that day

    def test_an_overnight_shift_can_move_a_break_past_midnight_and_is_still_running_at_one_am(self):
        for now in (at(WED, 21), at(THU, 1)):
            options = self.book.break_options(self.key, NIGHT, 0, now)
            self.assertEqual(options["shift"]["on"], WED)
            self.assertTrue(any(c["start"] >= 1440 for c in options["choices"]), now)
        found = self.book.running_shift(self.key, NIGHT, at(THU, 8))  # Wednesday's night shift ended at 07:00
        self.assertTrue(found is None or found["on"] == THU)

    def test_a_request_is_kept_waiting_with_its_buffer_and_the_associate_sees_it(self):
        to, _ = self.other(self.book.break_options(self.key, ME, 0, at(WED, 12)), -1)
        rid = self.book.ask_break(self.key, ME, self.me, 0, to, "Made-up: appointment", at(WED, 12))
        row = self.store.get_change_request(rid)
        self.assertEqual((row["kind"], row["status"], json.loads(row["names"])), ("break", "waiting", [ME]))
        self.assertIn(json.loads(row["detail"])["level"], (HIGH, "moderate", LOW))
        self.assertEqual([r["id"] for r in self.book.mine(self.key, self.me["id"])], [rid])
        self.assertEqual(self.book.count(self.key), 1)

    def test_a_time_that_is_not_offered_the_current_time_and_a_second_request_are_refused(self):
        with self.assertRaises(ValueError):
            self.book.ask_break(self.key, ME, self.me, 0, "02:00", "", at(WED, 12))
        with self.assertRaises(ValueError):
            self.book.ask_break(self.key, ME, self.me, 0, "13:00", "", at(WED, 12))
        options = self.book.break_options(self.key, ME, 0, at(WED, 12))
        self.book.ask_break(self.key, ME, self.me, 0, self.other(options, 0)[0], "", at(WED, 12))
        with self.assertRaises(ValueError):
            self.book.ask_break(self.key, ME, self.me, 0, self.other(options, 1)[0], "", at(WED, 12))

    def test_approving_moves_the_break_on_the_day_and_says_who_asked(self):
        clock, to = self.other(self.book.break_options(self.key, ME, 0, at(WED, 12)), 1)
        rid = self.book.ask_break(self.key, ME, self.me, 0, clock, "", at(WED, 12))
        said = self.book.decide(rid, self.rta, True, "", at(WED, 12, 5))
        self.assertIn("Approved", said)
        lane = next(l for l in self.app.extensions["days"].page(self.key, WED)["view"]["lanes"] if l["name"] == ME)
        moved = next(b for s in lane["segments"] if s["offset"] == 0 for b in s["breaks"] if b["idx"] == 0)
        self.assertEqual((moved["start"], moved["moved"]), (to, True))
        self.assertEqual(self.store.get_change_request(rid)["status"], "approved")
        log = " ".join(e["what"] for e in self.store.list_day_log(self.key, WED.isoformat()) if "what" in e)
        self.assertIn("asked by Associate 027", log)

    def test_rejecting_needs_a_reason_the_associate_can_read(self):
        clock, to = self.other(self.book.break_options(self.key, ME, 0, at(WED, 12)), 1)
        rid = self.book.ask_break(self.key, ME, self.me, 0, clock, "", at(WED, 12))
        with self.assertRaises(ValueError):
            self.book.decide(rid, self.rta, False, "", at(WED, 12, 5))
        self.book.decide(rid, self.rta, False, "Phones are busy then", at(WED, 12, 5))
        row = self.store.get_change_request(rid)
        self.assertEqual((row["status"], row["decision"]), ("rejected", "Phones are busy then"))

    def test_a_time_that_has_passed_by_approval_is_not_applied(self):
        clock, _ = self.other(self.book.break_options(self.key, ME, 0, at(WED, 12)), 0)
        rid = self.book.ask_break(self.key, ME, self.me, 0, clock, "", at(WED, 12))
        with self.assertRaises(ValueError):
            self.book.decide(rid, self.rta, True, "", at(WED, 14))
        self.assertEqual(self.store.get_change_request(rid)["status"], "refused")

    def test_only_the_asker_cancels_and_only_while_waiting(self):
        clock, to = self.other(self.book.break_options(self.key, ME, 0, at(WED, 12)), 1)
        rid = self.book.ask_break(self.key, ME, self.me, 0, clock, "", at(WED, 12))
        with self.assertRaises(ValueError):
            self.book.cancel(rid, self.night)
        self.book.cancel(rid, self.me)
        self.assertEqual(self.store.get_change_request(rid)["status"], "cancelled")
        with self.assertRaises(ValueError):
            self.book.decide(rid, self.rta, True, "", at(WED, 12, 5))

    def test_the_rta_sees_the_intervals_the_move_leaves_and_lands_on(self):
        clock, to = self.other(self.book.break_options(self.key, ME, 0, at(WED, 12)), 1)
        rid = self.book.ask_break(self.key, ME, self.me, 0, clock, "", at(WED, 12))
        rows = self.book.impact(self.store.get_change_request(rid))
        self.assertTrue(rows)
        self.assertTrue(all({"t", "need", "before", "after", "level"} <= set(r) for r in rows))
        self.assertTrue(any(r["after"] < r["before"] for r in rows))   # where it lands
        self.assertTrue(any(r["after"] > r["before"] for r in rows))   # where it leaves


class TheCoachingRequests(_Fixture):
    def setUp(self):
        self.clear()
        self.tm = self.users["tm1"]

    def test_the_options_are_the_times_everyone_is_free(self):
        got = self.book.coaching_options(self.key, WED, [ME, MATE], 30, at(WED, 9))
        self.assertTrue(got)
        self.assertTrue(all(c["start"] % 15 == 0 and c["level"] in (HIGH, "moderate", LOW) for c in got))

    def test_a_day_that_has_passed_or_someone_without_a_shift_is_refused(self):
        with self.assertRaises(ValueError):
            self.book.coaching_options(self.key, WED, [ME], 30, at(THU, 9))
        with self.assertRaises(ValueError):
            self.book.coaching_options(self.key, date(2026, 10, 10), ["Nobody"], 30, at(WED, 9))

    def test_a_request_names_the_people_the_time_and_the_department(self):
        first = self.book.coaching_options(self.key, WED, [ME, MATE], 30, at(WED, 9))[0]["start"]
        rid = self.book.ask_coaching(self.key, [ME, MATE], self.tm, WED, f"{first // 60:02d}:{first % 60:02d}", 30,
                                     "Quality", "Made-up: call review", at(WED, 9))
        row = self.book._label(self.store.get_change_request(rid))
        self.assertEqual((row["kind"], row["names_list"], row["d"]["dept"]), ("coaching", sorted([ME, MATE]), "Quality"))
        self.assertIn("Coaching", row["what"])

    def test_approving_records_the_coaching_for_every_person(self):
        first = self.book.coaching_options(self.key, WED, [ME, MATE], 30, at(WED, 9))[0]["start"]
        rid = self.book.ask_coaching(self.key, [ME, MATE], self.tm, WED, f"{first // 60:02d}:{first % 60:02d}", 30,
                                     "Quality", "Made-up: call review", at(WED, 9))
        self.book.decide(rid, self.rta, True, "", at(WED, 9, 5))
        days = self.app.extensions["days"]
        for name in (ME, MATE):
            lane = next(l for l in days.page(self.key, WED)["view"]["lanes"] if l["name"] == name)
            acts = [a for s in lane["segments"] for a in s["activities"] if a["kind"] == "Coaching"]
            self.assertEqual([(a["start"], a["end"]) for a in acts], [(first, first + 30)], name)

    def test_the_impact_counts_every_person_taken_off(self):
        first = next(c["start"] for c in self.book.coaching_options(self.key, WED, [ME, MATE], 60, at(WED, 9))
                     if c["start"] % 60 == 0)  # a whole hour of an hourly day, so the two people are two off its average
        rid = self.book.ask_coaching(self.key, [ME, MATE], self.tm, WED, f"{first // 60:02d}:{first % 60:02d}", 60,
                                     "", "", at(WED, 9))
        rows = self.book.impact(self.store.get_change_request(rid))
        self.assertTrue(rows)
        self.assertTrue(all(abs((r["before"] - r["after"]) - 2) < 1e-6 for r in rows), rows)

    def test_one_person_who_cannot_be_coached_stops_the_whole_request(self):
        first = self.book.coaching_options(self.key, WED, [ME], 30, at(WED, 9))[0]["start"]
        rid = self.book.ask_coaching(self.key, [ME], self.tm, WED, f"{first // 60:02d}:{first % 60:02d}", 30, "", "", at(WED, 9))
        self.app.extensions["days"].set_status(self.key, WED, ME, "Sick", self.rta["id"])
        with self.assertRaises(ValueError):
            self.book.decide(rid, self.rta, True, "", at(WED, 9, 5))
        self.assertEqual(self.store.get_change_request(rid)["status"], "refused")


class TheRealityView(_Fixture):
    """Owner, 2026-10-21: the choices and the impact follow what the RTA tab holds now (absences, moved breaks, overtime,
    activities), not what was planned."""

    def setUp(self):
        self.clear()

    def levels(self, name=ME):
        options = self.book.break_options(self.key, name, 0, at(WED, 12))
        return {c["start"]: c["people_above"] for c in options["choices"]}

    def test_a_colleague_marked_sick_takes_cover_out_of_the_buffer(self):
        planned = self.levels()
        self.app.extensions["days"].set_status(self.key, WED, MATE, "Sick", self.rta["id"])
        real = self.levels()
        self.assertEqual(planned.keys(), real.keys())
        self.assertTrue(all(real[t] is None or planned[t] is None or real[t] < planned[t] for t in real))

    def test_a_break_the_rta_moved_is_the_one_the_associate_changes(self):
        days = self.app.extensions["days"]
        days.move_break(self.key, WED, ME, 0, "12:30", self.rta["id"])
        options = self.book.break_options(self.key, ME, 0, at(WED, 12))
        self.assertEqual(options["current"], 12 * 60 + 30)
        self.assertEqual([c["start"] for c in options["choices"] if c["current"]], [12 * 60 + 30])

    def test_coaching_the_rta_already_booked_is_busy_time(self):
        before = {c["start"] for c in self.book.coaching_options(self.key, WED, [ME], 30, at(WED, 9))}
        self.app.extensions["days"].add_activity(self.key, WED, ME, "Meeting", "14:00", "15:00", self.rta["id"],
                                                 with_whom="Made-up", why="Made-up", with_dept="")
        after = {c["start"] for c in self.book.coaching_options(self.key, WED, [ME], 30, at(WED, 9))}
        self.assertTrue(before - after)
        self.assertNotIn(14 * 60 + 15, after)


class TheBillableChoice(_Fixture):
    def setUp(self):
        self.clear()
        self.tm = self.users["tm1"]

    def test_billable_coaching_keeps_people_on_the_floor_so_the_buffer_is_higher(self):
        non = {c["start"]: c["people_above"] for c in self.book.coaching_options(self.key, WED, [ME, MATE], 60, at(WED, 9))}
        bill = {c["start"]: c["people_above"] for c in self.book.coaching_options(self.key, WED, [ME, MATE], 60, at(WED, 9),
                                                                                    billable=True)}
        both = [t for t in non if t in bill and non[t] is not None and t % 60 == 0]  # whole hours of an hourly day
        self.assertTrue(both)
        self.assertTrue(all(abs(bill[t] - non[t] - 2) < 1e-6 for t in both))

    def test_the_request_says_which_and_the_rta_can_correct_it_when_approving(self):
        first = self.book.coaching_options(self.key, WED, [ME], 30, at(WED, 9))[0]["start"]
        rid = self.book.ask_coaching(self.key, [ME], self.tm, WED, f"{first // 60:02d}:{first % 60:02d}", 30, "Quality",
                                     "Made-up", at(WED, 9), billable=False)
        self.assertIn("not billable", self.book._label(self.store.get_change_request(rid))["what"].lower())
        self.book.decide(rid, self.rta, True, "It is billable, set by Quality", at(WED, 9, 5), billable=True)
        lane = next(l for l in self.app.extensions["days"].page(self.key, WED)["view"]["lanes"] if l["name"] == ME)
        acts = [a for s in lane["segments"] for a in s["activities"] if a["kind"] == "Coaching"]
        self.assertEqual([a["billable"] for a in acts], [True])
        self.assertTrue(json.loads(self.store.get_change_request(rid)["detail"])["billable"])


class TheNearestTime(_Fixture):
    """When the RTA will not approve a time he sees the nearest ones, may change the request to one of them, and writes why;
    the requester reads it."""

    def setUp(self):
        self.clear()

    def ask(self):
        options = self.book.break_options(self.key, ME, 0, at(WED, 12))
        clock, to = self.other(options, 2)
        return self.book.ask_break(self.key, ME, self.me, 0, clock, "", at(WED, 12)), to

    def test_the_nearest_times_come_nearest_first_and_skip_a_low_one_when_a_better_exists(self):
        rid, to = self.ask()
        near = self.book.alternatives(self.store.get_change_request(rid), at(WED, 12))
        self.assertTrue(near)
        self.assertEqual([abs(n["start"] - to) for n in near], sorted(abs(n["start"] - to) for n in near))
        self.assertTrue(all(n["start"] != to for n in near))
        if any(n["level"] != LOW for n in near):
            self.assertTrue(all(n["level"] != LOW for n in near))

    def test_changing_to_a_nearer_time_applies_that_time_keeps_what_was_asked_and_needs_a_comment(self):
        rid, to = self.ask()
        near = self.book.alternatives(self.store.get_change_request(rid), at(WED, 12))[0]["start"]
        with self.assertRaises(ValueError):
            self.book.decide(rid, self.rta, True, "", at(WED, 12, 5), at=near)
        self.book.decide(rid, self.rta, True, "Phones are busy at your time", at(WED, 12, 5), at=near)
        row = self.store.get_change_request(rid)
        detail = json.loads(row["detail"])
        self.assertEqual((row["status"], detail["to"], detail["asked_to"]), ("approved", near, to))
        lane = next(l for l in self.app.extensions["days"].page(self.key, WED)["view"]["lanes"] if l["name"] == ME)
        moved = next(b for s in lane["segments"] if s["offset"] == 0 for b in s["breaks"] if b["idx"] == 0)
        self.assertEqual(moved["start"], near)
        words = self.book._label(row)
        self.assertIn("instead", words["status_words"])
        self.assertEqual(words["decision"], "Phones are busy at your time")

    def test_a_time_that_is_not_one_of_the_choices_cannot_be_the_change(self):
        rid, _ = self.ask()
        with self.assertRaises(ValueError):
            self.book.decide(rid, self.rta, True, "x", at(WED, 12, 5), at=3 * 60)

    def test_the_associate_reads_the_new_time_and_the_comment(self):
        rid, _ = self.ask()
        near = self.book.alternatives(self.store.get_change_request(rid), at(WED, 12))[0]["start"]
        self.book.decide(rid, self.rta, True, "Phones are busy at your time", at(WED, 12, 5), at=near)
        mine = self.book.mine(self.key, self.me["id"])[0]
        self.assertIn("Phones are busy at your time", mine["decision"])
        self.assertIn(f"{(near // 60) % 24:02d}:{near % 60:02d}", mine["what"] + mine["status_words"])

    def test_coaching_can_be_moved_to_the_nearest_time_too(self):
        tm = self.users["tm1"]
        opts = self.book.coaching_options(self.key, WED, [ME, MATE], 30, at(WED, 9))
        rid = self.book.ask_coaching(self.key, [ME, MATE], tm, WED, f"{opts[4]['start'] // 60:02d}:{opts[4]['start'] % 60:02d}",
                                     30, "", "", at(WED, 9), billable=False)
        near = self.book.alternatives(self.store.get_change_request(rid), at(WED, 9))
        self.assertTrue(near)
        self.book.decide(rid, self.rta, True, "Moved to a quieter time", at(WED, 9, 5), at=near[0]["start"])
        self.assertEqual(json.loads(self.store.get_change_request(rid)["detail"])["start"], near[0]["start"])


if __name__ == "__main__":
    unittest.main()
