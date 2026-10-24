# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AO (owner, 2026-10-20: "OT for shift 3 pm to 00:00 ... adds before normally but it glitch for after hours OT
for that shift only: it reflects that associate is there but the hours not being added"). Root cause: the day after
carried yesterday's shift only when it ended after 24:00, so overtime saved as 24:00 to 01:00 on a shift ending at 24:00
was on no day's floor."""
import json
import unittest
from datetime import date

from webapp.tests.test_overtime_side import LATE, WED, _Overtime

THU = date(2026, 10, 15)


class AfterMidnight(_Overtime):
    def setUp(self):
        row, _ = self.days.version(self.key, WED)
        week = json.loads(row["week"])
        who = next(a for a in week["associates"] if a["name"] == LATE)
        self.was = who["days"][3]
        who["days"][3] = "15:00 - 00:00"
        self.store.update_schedule(row["id"], week=json.dumps(week))
        self.row_id = row["id"]

    def tearDown(self):
        for r in self.store.list_activities(self.key, [WED.isoformat()]):
            self.store.delete_activity(r["id"])
        row = self.store.get_schedule(self.row_id)
        week = json.loads(row["week"])
        next(a for a in week["associates"] if a["name"] == LATE)["days"][3] = self.was
        self.store.update_schedule(self.row_id, week=json.dumps(week))

    def lane(self, on):
        page = self.days.page(self.key, on)
        lane = next((l for l in page["view"]["lanes"] if l["name"] == LATE and any(s["offset"] == -1 for s in l["segments"])), None)
        return page["view"], lane

    def test_overtime_after_a_midnight_shift_is_on_the_next_days_floor(self):
        _, none = self.lane(THU)
        self.assertIsNone(none)  # no overtime yet: the shift ended at 24:00
        self.days.add_item(self.key, WED, LATE, "Overtime", "00:00", 60, 1, side="after")
        view, lane = self.lane(THU)
        self.assertIsNotNone(lane, "yesterday's shift with overtime past midnight must reach the next day")
        seg = next(s for s in lane["segments"] if s["offset"] == -1)
        self.assertEqual(seg["end"], 0)  # the shift ended at 24:00; the hour is its overtime
        self.assertEqual([(a["kind"], a["start"], a["end"]) for a in seg["activities"]], [("Overtime", 0, 60)])
        self.assertEqual([c["overtime"] for c in view["cells"][:3]][0], 1)  # 00:00 to 01:00 counts them
        self.assertEqual(view["tiles"]["overtime"], 60)  # the hour counts on the day it is worked, as for a night shift

    def test_a_shift_ending_at_23_has_nothing_carried(self):
        row = self.store.get_schedule(self.row_id)
        week = json.loads(row["week"])
        next(a for a in week["associates"] if a["name"] == LATE)["days"][3] = "15:00 - 23:00"
        self.store.update_schedule(self.row_id, week=json.dumps(week))
        self.days.add_item(self.key, WED, LATE, "Overtime", "00:00", 60, 1, side="after")
        _, lane = self.lane(THU)
        self.assertIsNone(lane)


if __name__ == "__main__":
    unittest.main()
