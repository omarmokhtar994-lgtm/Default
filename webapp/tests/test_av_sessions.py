# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: "what if I need 5-6 coaching at the same time ... easily from the RTA tab, and if I need
to change the coaching time later for one or more from that bulk, an option to do it easily"). People booked together
share a session; chosen members can be moved or removed together, all or none, and each is logged and undone. Made-up
"Associate NN" data, Wednesday 14 Oct."""
import re
import unittest

from webapp.tests.test_notify_daybook import WED, _Tagged, hm
from webapp.tests.test_runs import token

WHO = ("Coaching", "Coaching with the team lead")


class _Sessions(_Tagged):
    def present(self, n):
        """n people present on the same shift today (so they can share an hour)."""
        groups = {}
        for lane in self.days.page(self.key, WED)["view"]["lanes"]:
            for s in lane["segments"]:
                if s["offset"] == 0 and s["status"] == "Present":
                    groups.setdefault((s["start"], s["end"]), []).append(lane["name"])
        names = max(groups.values(), key=len)
        self.assertGreaterEqual(len(names), n)
        self.shift = max(groups, key=lambda k: len(groups[k]))
        return names[:n]

    def free(self, names, minutes=30, skip=()):
        lo, hi = self.shift
        slots = self.days.meeting_slots(self.key, WED, names, minutes, hm(lo % 1440), hm(hi % 1440 or 1440 - 1))
        return [s["start"] for s in slots if s["start"] not in skip]

    def booked(self, n=3, minutes=30):
        names = self.present(n)
        start = self.free(names, minutes)[0]
        self.days.book_session(self.key, WED, names, start, minutes, "Coaching", self.omar, why="Weekly coaching")
        self.addCleanup(self.clear)
        return names, start

    def clear(self):
        for r in self.store.list_activities(self.key, [WED.isoformat()]):
            self.store.delete_activity(r["id"])

    def rows(self):
        return [r for r in self.store.list_activities(self.key, [WED.isoformat()]) if r["kind"] == "Coaching"]


class TheSession(_Sessions):
    def test_a_booking_shares_one_session(self):
        names, start = self.booked(3)
        rows = self.rows()
        self.assertEqual(sorted(r["associate"] for r in rows), sorted(names))
        self.assertEqual(len({r["session"] for r in rows}), 1)
        self.assertTrue(rows[0]["session"])

    def test_two_bookings_have_two_sessions(self):
        names = self.present(3)
        a, b = names[:1], names[1:]
        self.days.book_session(self.key, WED, a, self.free(a)[0], 30, "Coaching", self.omar, why="x")
        self.addCleanup(self.clear)
        self.days.book_session(self.key, WED, b, self.free(b)[-1], 30, "Coaching", self.omar, why="y")
        self.assertEqual(len({r["session"] for r in self.rows()}), 2)

    def test_the_sessions_of_a_day_list_their_members(self):
        names, start = self.booked(3)
        got = self.days.sessions(self.key, WED)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["kind"], got[0]["start"], got[0]["end"]), ("Coaching", start, start + 30))
        self.assertEqual(sorted(m["name"] for m in got[0]["members"]), sorted(names))

    def test_an_activity_added_on_its_own_has_no_session(self):
        name = self.present(1)[0]
        lo = self.free([name])[0]
        self.days.add_activity(self.key, WED, name, "Coaching", hm(lo), hm(lo + 30), self.omar)
        self.addCleanup(self.clear)
        self.assertEqual(self.days.sessions(self.key, WED), [])


class TheMove(_Sessions):
    def test_the_chosen_members_move_together_and_the_others_stay(self):
        names, start = self.booked(3)
        sid = self.days.sessions(self.key, WED)[0]["session"]
        later = self.free(names[:2], skip=(start,))[-1]
        self.days.move_session(self.key, WED, sid, names[:2], later, self.omar)
        by = {r["associate"]: r["start"] for r in self.rows()}
        self.assertEqual((by[names[0]], by[names[1]], by[names[2]]), (later, later, start))
        self.assertEqual(next(r for r in self.rows() if r["associate"] == names[0])["end_min"], later + 30)

    def test_all_or_none_when_one_is_not_free(self):
        names, start = self.booked(2)
        sid = self.days.sessions(self.key, WED)[0]["session"]
        taken = self.free(names, skip=(start,))[-1]
        self.days.add_activity(self.key, WED, names[1], "Meeting", hm(taken), hm(taken + 30), self.omar)
        with self.assertRaises(ValueError) as said:
            self.days.move_session(self.key, WED, sid, names, taken, self.omar)
        self.assertIn("Not free then", str(said.exception))
        self.assertEqual({r["associate"]: r["start"] for r in self.rows()}, {n: start for n in names})

    def test_a_move_is_logged_per_person_and_undone_in_one_step(self):
        names, start = self.booked(2)
        sid = self.days.sessions(self.key, WED)[0]["session"]
        later = self.free(names, skip=(start,))[-1]
        self.days.move_session(self.key, WED, sid, names, later, self.omar)
        lines = [e["what"] for e in self.logged(2)]
        self.assertTrue(all(f"{hm(start)} to {hm(start + 30)} moved to {hm(later)}" in w for w in lines), lines)
        self.days.undo_last(self.key, WED, self.omar)
        self.assertEqual({r["associate"]: r["start"] for r in self.rows()}, {n: start for n in names})

    def test_a_session_that_is_not_there_is_refused(self):
        with self.assertRaises(ValueError):
            self.days.move_session(self.key, WED, "nope", ["Associate 001"], 600, self.omar)


class TheRemove(_Sessions):
    def test_the_chosen_members_leave_the_session(self):
        names, start = self.booked(3)
        sid = self.days.sessions(self.key, WED)[0]["session"]
        self.days.cancel_session(self.key, WED, sid, names[:2], self.omar)
        self.assertEqual([r["associate"] for r in self.rows()], names[2:])


class TheRoutes(_Sessions):
    def form(self, **more):
        return {"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(), **more}

    def test_a_set_time_books_the_people_at_once(self):
        names = self.present(3)
        start = self.free(names)[0]
        got = self.client.post("/day/book", data=self.form(who=names, at=hm(start), minutes="30", kind="Coaching", with_whom="Team lead",
                                                           why="Weekly coaching"))
        self.addCleanup(self.clear)
        self.assertEqual(got.status_code, 303)
        self.assertEqual(sorted(r["associate"] for r in self.rows()), sorted(names))
        self.assertEqual({r["start"] for r in self.rows()}, {start})

    def test_the_sessions_tab_lists_them_and_the_move_route_works(self):
        names, start = self.booked(2)
        sid = self.days.sessions(self.key, WED)[0]["session"]
        page = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}&view=sessions"
                               ).get_data(as_text=True)
        for n in names:
            self.assertIn(n, page)
        later = self.free(names, skip=(start,))[-1]
        got = self.client.post("/day/session/move", data=self.form(session=sid, who=names, at=hm(later)))
        self.assertEqual(got.status_code, 303)
        self.assertEqual({r["start"] for r in self.rows()}, {later})
        got = self.client.post("/day/session/cancel", data=self.form(session=sid, who=names[:1]))
        self.assertEqual(got.status_code, 303)
        self.assertEqual(len(self.rows()), 1)

    def test_the_board_row_links_to_book_several(self):
        page = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}&view=board"
                               ).get_data(as_text=True)
        self.assertRegex(page, r'class="rb-book" href="[^"]*view=meeting[^"]*at=')


if __name__ == "__main__":
    unittest.main()
