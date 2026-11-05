# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: "remove that part for break time changes, let's stick to what was scheduled in RTA, and in
case missed is ticked, count it as out of adherence"): a break moved in the RTA is the schedule now, so moving it costs
nothing; a break the associate missed (the tick) is out of adherence for its minutes."""
import unittest

from webapp.adherence import person_day
from webapp.tests import test_adherence as _ta
from webapp.tests.test_day import WEEK, minute, someone


class TheScheduleIsWhatTheRtaHolds(unittest.TestCase):
    def moved(self, by=60):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed" and b["kind"] == "Lunch" and b["start"].endswith(":00"))
        lanes = {l["name"]: l for l in _ta.view()["lanes"]}
        idx = next(x["idx"] for s in lanes[b["associate"]]["segments"] if s["offset"] == 0 for x in s["breaks"]
                   if x["kind"] == "Lunch")
        return b, person_day(_ta.view(actual={(0, b["associate"], idx): minute(b["start"]) + by}), b["associate"])

    def test_a_break_moved_in_the_rta_costs_no_adherence(self):
        _, row = self.moved()
        self.assertEqual((row["out_of_schedule"], row["adherence"], row["conformance"]), (0, 100, 100))

    def test_a_break_moved_earlier_costs_none_either(self):
        _, row = self.moved(-60)
        self.assertEqual((row["out_of_schedule"], row["adherence"]), (0, 100))

    def test_a_missed_break_is_out_of_adherence_for_its_minutes(self):
        person, _ = someone(_ta.WED, 20 * 60)
        v = _ta.view()
        seg = next(s for l in v["lanes"] if l["name"] == person["name"] for s in l["segments"] if s["offset"] == 0)
        seg["missed_min"] = 30
        row = person_day(v, person["name"])
        self.assertEqual(row["out_of_schedule"], 30)
        self.assertEqual(row["adherence"], round(100 * (row["scheduled"] - 30) / row["scheduled"]))
        self.assertEqual(row["conformance"], 100)

    def test_it_adds_to_what_else_was_out_and_never_past_the_shift(self):
        person, span = someone(_ta.WED, 20 * 60)
        v = _ta.view()
        seg = next(s for l in v["lanes"] if l["name"] == person["name"] for s in l["segments"] if s["offset"] == 0)
        seg["missed_min"] = 10 * 24 * 60
        row = person_day(v, person["name"])
        self.assertEqual(row["out_of_schedule"], row["scheduled"])
        self.assertEqual(row["adherence"], 0)

    def test_an_absent_person_has_no_adherence_to_lose(self):
        person, _ = someone(_ta.WED, 20 * 60)
        v = _ta.view({(0, person["name"]): {"status": "Sick"}})
        seg = next(s for l in v["lanes"] if l["name"] == person["name"] for s in l["segments"] if s["offset"] == 0)
        seg["missed_min"] = 30
        self.assertIsNone(person_day(v, person["name"])["adherence"])


if __name__ == "__main__":
    unittest.main()
