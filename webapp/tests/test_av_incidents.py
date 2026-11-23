# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: "while rescheduling any break I need a check mark if it was a missed break, so we can
capture those incidents and see if it's a behaviour"). A break moved with "Missed break" ticked keeps an incident for
the analysis; it goes with Undo and with the old-day purge. Made-up "Associate NN" data, Wednesday 14 Oct."""
import re
import unittest

from webapp.tests import test_cancel_break as _cb
from webapp.tests.test_notify_daybook import WED, _Tagged, hm
from webapp.tests.test_runs import token


class TheMissedBreak(_Tagged):
    def incidents(self):
        return self.store.list_incidents(self.key, [WED.isoformat()])

    def moved(self, missed):
        name, idx, kind, start, _ = self.with_breaks()
        self.addCleanup(self.days.move_break, self.key, WED, name, idx, None, self.omar)
        self.days.move_break(self.key, WED, name, idx, hm(start + 5), self.omar, missed=missed)
        return name, idx, kind

    def test_a_ticked_move_keeps_an_incident(self):
        name, idx, kind = self.moved(True)
        got = self.incidents()
        self.assertEqual([(r["associate"], r["kind"], r["idx"], r["note"]) for r in got],
                         [(name, "missed_break", idx, kind)])
        self.addCleanup(self.store.delete_day_before, "2999-01-01")

    def test_an_unticked_move_keeps_none(self):
        self.moved(False)
        self.assertEqual(self.incidents(), [])

    def test_undo_takes_the_incident_back_with_the_move(self):
        self.moved(True)
        self.days.undo_last(self.key, WED, self.omar)
        self.assertEqual(self.incidents(), [])

    def test_the_old_day_purge_clears_them(self):
        self.moved(True)
        self.store.delete_day_before("2999-01-01")
        self.assertEqual(self.incidents(), [])


class TheTick(_cb.ThePage):
    def test_the_dialog_offers_the_tick(self):
        dialog = re.search(r'(?s)<dialog id="break-dialog".*?</dialog>', self.page()).group(0)
        self.assertRegex(dialog, r'<input type="checkbox" name="missed" value="1"> Missed break')

    def test_the_route_keeps_the_incident(self):
        name, idx, kind, start, _ = self.with_breaks()
        self.addCleanup(self.days.move_break, self.key, WED, name, idx, None, self.omar)
        form = {"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(), "associate": name,
                "idx": str(idx), "at": hm(start + 5), "missed": "1"}
        self.assertEqual(self.client.post("/day/break", data=form).get_json(), {"ok": True})
        self.assertEqual([r["kind"] for r in self.store.list_incidents(self.key, [WED.isoformat()])], ["missed_break"])


if __name__ == "__main__":
    unittest.main()
