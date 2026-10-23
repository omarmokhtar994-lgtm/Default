# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "removing last night's overtime, call-in and cover ... a max of 2 days back from today"): overtime,
a call-in and cover from outside the roster can be removed for today and the 2 days before, never further back. Today is Egypt's
(the app's ``TODAY`` setting stands in for it in tests). Other activities are not limited by this."""
import unittest
from datetime import timedelta

from webapp.tests.test_overtime_side import WED, _Overtime
from webapp.tests.test_runs import token

NAME = "Made-up Support 02"


class TheEditWindow(_Overtime):
    def setUp(self):
        self.was = self.app.config.get("TODAY")
        self.addCleanup(lambda: self.app.config.__setitem__("TODAY", self.was))
        self.ot = self.days.add_activity(self.key, WED, "Associate 021", "Overtime", "17:00", "18:00", 1)
        self.call = self.days.add_activity(self.key, WED, "Associate 004", "Called in", "10:00", "18:00", 1)
        self.cover = self.days.add_cover(self.key, WED, NAME, "Support", "10:00", "12:00", 1)

        def clean():
            for i in (self.ot, self.call):
                if self.store.get_activity(i):
                    self.store.delete_activity(i)
            if self.store.get_cover(self.cover):
                self.store.delete_cover(self.cover)
        self.addCleanup(clean)

    def post(self, where, ident):
        return self.client.post(where, data={"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(),
                                             "id": str(ident), "view": "cover"}, follow_redirects=True).get_data(as_text=True)

    def today(self, days_after):
        self.app.config["TODAY"] = WED + timedelta(days=days_after)

    def test_two_days_back_is_still_removable(self):
        self.today(2)
        self.post("/day/activity/cancel", self.ot)
        self.post("/day/activity/cancel", self.call)
        self.post("/day/cover/cancel", self.cover)
        self.assertIsNone(self.store.get_activity(self.ot))
        self.assertIsNone(self.store.get_activity(self.call))
        self.assertIsNone(self.store.get_cover(self.cover))

    def test_three_days_back_is_closed_and_the_page_says_so(self):
        self.today(3)
        for where, ident in (("/day/activity/cancel", self.ot), ("/day/activity/cancel", self.call), ("/day/cover/cancel", self.cover)):
            page = self.post(where, ident)
            self.assertIn("2 days before", page)
        self.assertIsNotNone(self.store.get_activity(self.ot))
        self.assertIsNotNone(self.store.get_activity(self.call))
        self.assertIsNotNone(self.store.get_cover(self.cover))

    def test_an_ordinary_activity_is_not_held_by_the_window(self):
        aux = self.days.add_activity(self.key, WED, "Associate 008", "Training", "10:00", "10:30", 1)
        self.addCleanup(lambda: self.store.get_activity(aux) and self.store.delete_activity(aux))
        self.today(9)
        self.post("/day/activity/cancel", aux)
        self.assertIsNone(self.store.get_activity(aux))


if __name__ == "__main__":
    unittest.main()
