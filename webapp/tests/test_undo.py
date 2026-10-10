# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AD (owner, 2026-10-11: "a button to undo last move or 2 ... like if we did fix breaks and i didn't like the
view i can just undo same goes for the emergency button as well and any moves maybe max 2 moves back"; answer 2:
your own only): every RTA change is one entry in the day's journal; Undo takes back your own last 2 entries exactly,
and never overwrites what someone changed since. Made-up "Associate NN" data, Wednesday 14 Oct."""
import html
import json
import re

from webapp.tests.test_notify_daybook import LATE, WED, _Tagged, hm
from webapp.tests.test_runs import sign_in, token

TWO = "Nothing of yours to undo on this day: Undo goes back 2 changes at most."


class _Journal(_Tagged):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sara = next(u["id"] for u in cls.store.list_users() if u["username"] == "sara")  # made by make_app

    def actual(self, name, idx):
        found = [r for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])
                 if r["associate"] == name and r["idx"] == idx]
        return found[0] if found else None

    def fresh(self, skip=()):
        """A break nobody touched yet, put back to the plan after the test."""
        used = {r["associate"] for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])}
        name, idx, kind, start, planned = self.with_breaks(skip=set(skip) | used)
        self.addCleanup(self.store.clear_actual_break, self.key, WED.isoformat(), name, idx)
        return name, idx, kind, start


class TheUndo(_Journal):
    def test_undo_takes_back_my_last_change(self):
        name, idx, kind, start = self.fresh()
        self.move(name, idx, start)
        said = self.days.undo_last(self.key, WED, self.omar)
        self.assertIsNone(self.actual(name, idx))  # back to the plan, as before the move
        self.assertTrue(said.startswith("Undone: "), said)
        self.assertEqual(self.logged()[0]["what"], f"{kind} back to plan (undone)")

    def test_undo_goes_back_two_at_most(self):
        moved = []
        for _ in range(3):
            name, idx, kind, start = self.fresh(skip=[m[0] for m in moved])
            self.move(name, idx, start)
            moved.append((name, idx))
        self.days.undo_last(self.key, WED, self.omar)
        self.days.undo_last(self.key, WED, self.omar)
        self.assertIsNone(self.actual(*moved[2]))
        self.assertIsNone(self.actual(*moved[1]))
        with self.assertRaises(ValueError) as said:
            self.days.undo_last(self.key, WED, self.omar)
        self.assertEqual(str(said.exception), TWO)
        self.assertIsNotNone(self.actual(*moved[0]))  # the third one back stays

    def test_undo_is_mine_only(self):
        name, idx, kind, start = self.fresh()
        self.days.move_break(self.key, WED, name, idx, hm(start + 5), self.sara)
        mine = self.days.undoable(self.key, WED, self.omar)
        hers = self.days.undoable(self.key, WED, self.sara)
        self.assertEqual(hers["user_id"], self.sara)
        self.assertTrue(mine is None or mine["id"] != hers["id"])

    def test_undo_refuses_when_someone_changed_it_since(self):
        name, idx, kind, start = self.fresh()
        self.days.move_break(self.key, WED, name, idx, hm(start + 5), self.omar)
        self.days.move_break(self.key, WED, name, idx, hm(start + 10), self.sara)
        with self.assertRaises(ValueError) as said:
            self.days.undo_last(self.key, WED, self.omar)
        self.assertEqual(str(said.exception), f"Not undone: {name}'s {kind} was changed again after it, by Sara.")
        self.assertEqual(self.actual(name, idx)["start"], start + 10)  # Sara's move stands

    def test_undo_restores_an_added_item_and_a_status(self):
        self.days.add_activity(self.key, WED, LATE, "Overtime", "17:00", "18:00", self.omar)
        self.days.undo_last(self.key, WED, self.omar)
        self.assertFalse([a for a in self.store.list_activities(self.key, [WED.isoformat()])
                          if a["associate"] == LATE and a["kind"] == "Overtime"])
        self.days.set_status(self.key, WED, LATE, "Sick", self.omar)
        self.days.undo_last(self.key, WED, self.omar)
        self.assertFalse([r for r in self.store.list_attendance(self.key, [WED.isoformat()]) if r["associate"] == LATE])

    def test_nested_calls_are_one_change(self):
        a = self.fresh()
        b = self.fresh(skip=[a[0]])
        count = len(self.store.day_actions(self.key, WED.isoformat()))
        moves = [(a[0], a[1], a[3] + 5), (b[0], b[1], b[3] + 5)]
        try:
            self.days.apply_replan(self.key, WED, moves, self.omar)
        except ValueError:  # a move the rules refuse: try the other way
            moves = [(a[0], a[1], a[3] - 5), (b[0], b[1], b[3] - 5)]
            self.days.apply_replan(self.key, WED, moves, self.omar)
        entries = self.store.day_actions(self.key, WED.isoformat())
        self.assertEqual(len(entries), count + 1)
        self.assertEqual(len(json.loads(entries[-1]["changes"])), 2)
        self.days.undo_last(self.key, WED, self.omar)
        self.assertIsNone(self.actual(a[0], a[1]))
        self.assertIsNone(self.actual(b[0], b[1]))


class TheButton(_Journal):
    def test_undo_button_and_route(self):
        name, idx, kind, start = self.fresh()
        self.move(name, idx, start)
        page = html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}")
                             .get_data(as_text=True))
        self.assertIn('action="/day/undo-last"', page)
        self.assertIn(f"Your last change: {name}, {kind} moved", re.sub(r"<[^>]+>", "", page))  # as read
        got = self.client.post("/day/undo-last", data={"csrf_token": token(self.client), "program": self.key,
                                                        "date": WED.isoformat()}, follow_redirects=True)
        self.assertIn("Undone: ", html.unescape(got.get_data(as_text=True)))
        self.assertIsNone(self.actual(name, idx))
        sara = sign_in(self.app, "sara", "Sara-pass-1")
        got = sara.post("/day/undo-last", data={"csrf_token": token(sara), "program": self.key,
                                                 "date": WED.isoformat()}, follow_redirects=True)
        self.assertIn(TWO, html.unescape(got.get_data(as_text=True)))


if __name__ == "__main__":
    import unittest
    unittest.main()
