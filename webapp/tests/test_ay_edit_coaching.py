# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "I need easy edits for planned coaching by the RTA, right now we can't just extend or edit the time, we
have to delete and do it again"): a booked session (meeting, training, coaching) can change its start and its end for the people ticked,
all or none, and one booked activity can change its start and end. Each change is logged and undone like any other. Made-up names,
Wednesday 14 Oct."""
import html
import re
import unittest

from webapp.tests.test_av_sessions import _Sessions
from webapp.tests.test_notify_daybook import WED, hm
from webapp.tests.test_runs import token


class TheEditOfASession(_Sessions):
    def sid(self):
        return self.days.sessions(self.key, WED)[0]["session"]

    def test_the_ticked_people_can_get_a_later_end(self):
        names, start = self.booked(3)
        self.days.edit_session(self.key, WED, self.sid(), names, start, start + 60, self.omar)
        self.assertEqual({(r["start"], r["end_min"]) for r in self.rows()}, {(start, start + 60)})

    def test_only_the_ticked_change_and_the_others_stay(self):
        names, start = self.booked(3)
        self.days.edit_session(self.key, WED, self.sid(), names[:1], start, start + 60, self.omar)
        got = {r["associate"]: r["end_min"] for r in self.rows()}
        self.assertEqual(got[names[0]], start + 60)
        self.assertEqual({got[n] for n in names[1:]}, {start + 30})

    def test_the_start_and_the_end_can_both_change_and_the_session_can_get_shorter(self):
        names, start = self.booked(2, minutes=60)
        self.days.edit_session(self.key, WED, self.sid(), names, start, start + 30, self.omar)
        self.assertEqual({(r["start"], r["end_min"]) for r in self.rows()}, {(start, start + 30)})

    def test_it_is_all_or_none_when_someone_is_not_free_for_the_longer_time(self):
        names, start = self.booked(2)
        other = self.days.book_session(self.key, WED, names[1:], start + 30, 30, "Meeting", self.omar, why="Made-up")
        before = sorted((r["associate"], r["kind"], r["start"], r["end_min"]) for r in self.rows())
        with self.assertRaises(ValueError) as refused:
            self.days.edit_session(self.key, WED, [s for s in self.days.sessions(self.key, WED) if s["kind"] == "Coaching"][0]["session"],
                                   names, start, start + 60, self.omar)
        self.assertIn(names[1], str(refused.exception))
        self.assertIn("Nobody was changed", str(refused.exception))
        self.assertEqual(sorted((r["associate"], r["kind"], r["start"], r["end_min"]) for r in self.rows()), before)

    def test_an_end_that_is_not_after_the_start_or_not_in_5_minute_steps_is_refused(self):
        names, start = self.booked(2)
        for end in (start, start - 5, start + 32):
            with self.assertRaises(ValueError):
                self.days.edit_session(self.key, WED, self.sid(), names, start, end, self.omar)
        self.assertEqual({(r["start"], r["end_min"]) for r in self.rows()}, {(start, start + 30)})

    def test_each_person_gets_a_log_line_and_undo_puts_the_times_back(self):
        names, start = self.booked(2)
        self.days.edit_session(self.key, WED, self.sid(), names, start, start + 60, self.omar)
        said = [e["what"] for e in self.days.page(self.key, WED)["log"] if e["associate"] in names]
        self.assertTrue(any(f"{hm(start)} to {hm(start + 60)}" in w for w in said), said)
        self.days.undo_last(self.key, WED, self.omar)
        self.assertEqual({(r["start"], r["end_min"]) for r in self.rows()}, {(start, start + 30)})


class TheEditOfOneActivity(_Sessions):
    def one(self):
        names = self.present(1)
        start = self.free(names)[0]
        self.days.book_session(self.key, WED, names, start, 30, "Coaching", self.omar, why="Made-up")
        self.addCleanup(self.clear)
        return names[0], start, self.rows()[0]["id"]

    def test_the_start_and_end_can_change_and_the_who_and_why_stay(self):
        name, start, rid = self.one()
        self.days.edit_activity(self.key, WED, rid, hm(start), hm(start + 60), self.omar)
        row = self.rows()[0]
        self.assertEqual((row["start"], row["end_min"], row["why"]), (start, start + 60, "Made-up"))

    def test_without_an_end_it_moves_and_keeps_its_length(self):
        name, start, rid = self.one()
        later = self.free([name], skip=(start,))[-1]
        self.days.edit_activity(self.key, WED, rid, hm(later), "", self.omar)
        row = self.rows()[0]
        self.assertEqual((row["start"], row["end_min"]), (later, later + 30))

    def test_a_time_outside_the_shift_is_refused_and_the_original_stays(self):
        name, start, rid = self.one()
        with self.assertRaises(ValueError):
            self.days.edit_activity(self.key, WED, rid, hm(start), "23:55", self.omar)
        with self.assertRaises(ValueError):
            self.days.edit_activity(self.key, WED, rid, hm(start), hm(start), self.omar)  # an end that is not after the start
        row = self.rows()[0]
        self.assertEqual((row["start"], row["end_min"]), (start, start + 30))

    def test_overtime_and_a_call_in_are_not_edited_here(self):
        name = self.present(1)[0]
        after = self.shift[1] % 1440
        self.days.add_activity(self.key, WED, name, "Overtime", hm(after), hm(after + 60), self.omar)
        self.addCleanup(self.clear)
        rid = next(r["id"] for r in self.store.list_activities(self.key, [WED.isoformat()]) if r["kind"] == "Overtime")
        with self.assertRaises(ValueError):
            self.days.edit_activity(self.key, WED, rid, hm(after), hm(after + 90), self.omar)

    def test_undo_puts_the_old_time_back(self):
        name, start, rid = self.one()
        self.days.edit_activity(self.key, WED, rid, hm(start), hm(start + 60), self.omar)
        self.days.undo_last(self.key, WED, self.omar)
        row = self.rows()[0]
        self.assertEqual((row["start"], row["end_min"]), (start, start + 30))


class TheRoutes(_Sessions):
    def form(self, **more):
        return {"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(), **more}

    def tab(self, view):
        got = self.client.get("/day", query_string={"program": self.key, "date": WED.isoformat(), "view": view})
        return html.unescape(got.get_data(as_text=True))

    def test_the_sessions_tab_has_a_new_end_and_a_button_to_change_the_time(self):
        self.booked(2)
        body = self.tab("sessions")
        self.assertRegex(body, r'<input type="time" name="to"')
        self.assertIn("Change the time of the ticked", body)
        self.assertIn("/day/session/edit", body)

    def test_the_session_route_extends_the_ticked_and_says_so(self):
        names, start = self.booked(2)
        sid = self.days.sessions(self.key, WED)[0]["session"]
        got = self.client.post("/day/session/edit", data=self.form(session=sid, who=names, at=hm(start), to=hm(start + 60)))
        self.assertEqual(got.status_code, 303)
        self.assertIn("view=sessions", got.headers["Location"])
        self.assertEqual({(r["start"], r["end_min"]) for r in self.rows()}, {(start, start + 60)})

    def test_a_refusal_is_said_and_nothing_changes(self):
        names, start = self.booked(2)
        sid = self.days.sessions(self.key, WED)[0]["session"]
        got = self.client.post("/day/session/edit", data=self.form(session=sid, who=names, at=hm(start), to=hm(start)),
                               follow_redirects=True)
        self.assertIn("after the start", html.unescape(got.get_data(as_text=True)))
        self.assertEqual({(r["start"], r["end_min"]) for r in self.rows()}, {(start, start + 30)})

    def test_the_activities_list_has_an_edit_form_for_a_booked_activity(self):
        names, start = self.booked(1)
        rid = self.rows()[0]["id"]
        body = self.tab("cover")
        form = re.search(r'<form[^>]*action="/day/activity/edit"[^>]*>(?:(?!</form>).)*name="id" value="' + str(rid) +
                         r'"(?:(?!</form>).)*</form>', body, re.S)
        self.assertTrue(form, "no edit form for the booked activity")
        self.assertIn('name="to"', form.group(0))
        data = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', form.group(0)))
        data.update({"at": hm(start), "to": hm(start + 60)})
        got = self.client.post("/day/activity/edit", data=data)
        self.assertEqual(got.status_code, 303)
        self.assertEqual((self.rows()[0]["start"], self.rows()[0]["end_min"]), (start, start + 60))

    def test_overtime_has_no_edit_form(self):
        name = self.present(1)[0]
        after = self.shift[1] % 1440
        self.days.add_activity(self.key, WED, name, "Overtime", hm(after), hm(after + 60), self.omar)
        self.addCleanup(self.clear)
        rid = next(r["id"] for r in self.store.list_activities(self.key, [WED.isoformat()]) if r["kind"] == "Overtime")
        self.assertNotRegex(self.tab("cover"), r'action="/day/activity/edit"[^>]*>(?:(?!</form>).)*name="id" value="' + str(rid) + '"')


if __name__ == "__main__":
    unittest.main()
