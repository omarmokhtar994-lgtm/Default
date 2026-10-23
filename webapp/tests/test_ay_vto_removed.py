# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "remove VTO option", then "anything that was marked as VTO to be changed to Early leave, back dated automatically"):
VTO can no longer be booked. ``convert_vto_to_early_leave`` (run once at start-up) turns every VTO already recorded into a Left early at the VTO's
start on its own date, drops the VTO record, notes it, and leaves alone anyone whose shift already carries another status. Made-up names."""
import unittest

from webapp.tests import test_attendance as ta
from webapp.tests.test_attendance import WED

AR = "AE/AR B2B"
WHO = "Associate 001"


class TheVtoIsGone(unittest.TestCase):
    setUpClass = classmethod(ta.TheAttendance.setUpClass.__func__)
    tearDownClass = classmethod(ta.TheAttendance.tearDownClass.__func__)
    setUp = ta.TheAttendance.setUp

    def old_vto(self, name=WHO, lo=14 * 60, hi=15 * 60, on=WED):
        return self.store.add_activity(program=AR, shift_date=on.isoformat(), associate=name, kind="VTO", start=lo, end_min=hi,
                                       billable=0, note="", user_id=self.sara)

    def status(self, name=WHO, on=WED):
        return next((r for r in self.store.list_attendance(AR, [on.isoformat()]) if r["associate"] == name), None)

    def vtos(self, on=WED):
        return [r for r in self.store.list_activities(AR, [on.isoformat()]) if r["kind"] == "VTO"]

    def test_vto_cannot_be_booked_any_more(self):
        with self.assertRaises(ValueError) as said:
            self.days.add_activity(AR, WED, WHO, "VTO", "14:00", "15:00", self.sara)
        self.assertIn("no longer offered", str(said.exception))
        with self.assertRaises(ValueError):
            self.days.add_item(AR, WED, WHO, "VTO", "14:00", 60, self.sara)

    def test_the_add_dialog_no_longer_lists_it(self):
        from webapp.attendance import ADD_KINDS, ACTIVITY_KINDS
        self.assertNotIn("VTO", sum(ADD_KINDS.values(), []))
        self.assertNotIn("VTO", ACTIVITY_KINDS)

    def test_a_recorded_vto_becomes_an_early_leave_at_its_start_on_its_own_date(self):
        self.old_vto()
        done = self.days.convert_vto_to_early_leave()
        self.assertEqual(done["converted"], 1)
        row = self.status()
        self.assertEqual((row["status"], row["from_min"], row["to_min"]), ("Left early", 14 * 60, None))
        self.assertIn("VTO", row["why"])
        self.assertEqual(self.vtos(), [])
        said = " ".join(e["what"] for e in self.days.page(AR, WED)["log"] if e["associate"] == WHO)
        self.assertIn("Left early at 14:00", said)

    def test_two_vtos_on_one_shift_use_the_earliest_start(self):
        self.old_vto(lo=18 * 60, hi=19 * 60)
        self.old_vto(lo=14 * 60, hi=15 * 60)
        self.days.convert_vto_to_early_leave()
        self.assertEqual(self.status()["from_min"], 14 * 60)
        self.assertEqual(self.vtos(), [])

    def test_a_person_who_already_has_another_status_is_skipped_and_reported(self):
        self.days.set_status(AR, WED, WHO, "Sick", self.sara)
        self.old_vto()
        done = self.days.convert_vto_to_early_leave()
        self.assertEqual(done["converted"], 0)
        self.assertEqual([(s["associate"], s["status"]) for s in done["skipped"]], [(WHO, "Sick")])
        self.assertEqual(self.status()["status"], "Sick")
        self.assertEqual(len(self.vtos()), 1)  # kept as history

    def test_an_earlier_early_leave_is_kept(self):
        self.days.set_status(AR, WED, WHO, "Left early", self.sara, start="13:00")
        self.old_vto()
        self.days.convert_vto_to_early_leave()
        self.assertEqual(self.status()["from_min"], 13 * 60)
        self.assertEqual(self.vtos(), [])

    def test_running_it_again_changes_nothing(self):
        self.old_vto()
        self.days.convert_vto_to_early_leave()
        again = self.days.convert_vto_to_early_leave()
        self.assertEqual((again["converted"], again["skipped"]), (0, []))
        self.assertEqual(self.status()["from_min"], 14 * 60)

    def test_it_makes_no_group_post(self):
        self.old_vto()
        before = len(self.store.list_notify_items(AR)) if hasattr(self.store, "list_notify_items") else 0
        self.days.convert_vto_to_early_leave()
        after = len(self.store.list_notify_items(AR)) if hasattr(self.store, "list_notify_items") else 0
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
