# © 2026 Omar Mokhtar. All rights reserved.
"""Phase O task 3: adherence, conformance and actual shrinkage from the day's records.

Adherence: minutes doing what the schedule says (working when planned to work,
on a break when the break was planned) out of the shift's minutes. Conformance:
minutes worked out of the minutes scheduled to work, whenever they happened.
On the real Voice Wednesday; names are read from the workbook."""
import unittest

from webapp.adherence import interval_shrinkage, person_day, team
from webapp.day import day_view
from webapp.tests.test_day import INPUTS, WEEK, WED, minute, someone
from webapp.versions import shift_span


def view(attendance=None, actual=None, measure="interval"):
    return day_view(WEEK, INPUTS, WED, attendance or {}, actual or {}, measure)


class TheAdherence(unittest.TestCase):
    def test_a_day_as_planned_is_full_marks(self):
        person, span = someone(WED, 20 * 60)
        row = person_day(view(), person["name"])
        self.assertEqual((row["adherence"], row["conformance"], row["out_of_schedule"]), (100, 100, 0))
        self.assertEqual(row["scheduled"], span[1] - span[0])
        self.assertEqual(row["scheduled_work"], row["scheduled"] - row["breaks_planned"])

    def test_moved_break_costs_adherence_not_conformance(self):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed" and b["kind"] == "Lunch" and b["start"].endswith(":00"))
        lanes = {l["name"]: l for l in view()["lanes"]}
        idx = next(x["idx"] for s in lanes[b["associate"]]["segments"] if s["offset"] == 0 for x in s["breaks"]
                   if x["kind"] == "Lunch")
        row = person_day(view(actual={(0, b["associate"], idx): minute(b["start"]) + 60}), b["associate"])
        self.assertEqual(row["out_of_schedule"], 2 * b["minutes"])  # on a break when due to work, and the reverse
        self.assertEqual(row["conformance"], 100)
        self.assertEqual(row["adherence"], round(100 * (row["scheduled"] - 2 * b["minutes"]) / row["scheduled"]))

    def test_late_costs_both(self):
        person, span = someone(WED, 20 * 60, starts_by=18 * 60 + 30)
        row = person_day(view({(0, person["name"]): {"status": "Late", "to": span[0] + 40}}), person["name"])
        self.assertEqual(row["late"], 40)
        self.assertEqual(row["adherence"], round(100 * (row["scheduled"] - 40) / row["scheduled"]))
        self.assertEqual(row["conformance"], round(100 * (row["scheduled_work"] - 40) / row["scheduled_work"]))

    def test_left_early_takes_no_breaks_after_leaving(self):
        person, span = someone(WED, 20 * 60)
        leave = span[1] - 180
        row = person_day(view({(0, person["name"]): {"status": "Left early", "from": leave}}), person["name"])
        self.assertEqual(row["early"], 180)
        self.assertEqual(row["worked"] + row["breaks_taken"] + row["early"], row["scheduled"])

    def test_billable_aux_counts_as_worked_for_intervals_only(self):
        person, span = someone(WED, 20 * 60)
        aux = lambda billable: {(0, person["name"]): {"status": "Coaching", "from": 20 * 60, "to": 20 * 60 + 30,
                                                      "billable": billable}}  # noqa: E731
        interval = person_day(view(aux(True)), person["name"])
        self.assertEqual((interval["aux_billable"], interval["adherence"], interval["conformance"]), (30, 100, 100))
        sl = person_day(view(aux(True), measure="sl"), person["name"])
        self.assertEqual(sl["out_of_schedule"], 30)
        unbillable = person_day(view(aux(False)), person["name"])
        self.assertEqual((unbillable["aux_unbillable"], unbillable["worked"]),
                         (30, interval["worked"] - 30))

    def test_absence_has_no_percentages_and_the_team_leaves_it_out(self):
        person, span = someone(WED, 20 * 60)
        v = view({(0, person["name"]): {"status": "Unplanned leave"}})
        row = person_day(v, person["name"])
        self.assertEqual((row["adherence"], row["conformance"], row["absent"]), (None, None, row["scheduled"]))
        rows = [person_day(v, l["name"]) for l in v["lanes"] if any(s["offset"] == 0 for s in l["segments"])]
        whole = team(rows)
        self.assertEqual(whole["people"], len(rows) - 1)
        self.assertEqual(whole["adherence"], 100)

    def test_actual_vs_input_shrinkage_per_interval(self):
        person, span = someone(WED, 20 * 60)
        v = view({(0, person["name"]): {"status": "Unplanned leave"}})
        row = next(r for r in interval_shrinkage(v, INPUTS, WED) if r["t"] == 20 * 60)
        cell = next(c for c in v["cells"] if c["t"] == 20 * 60)
        self.assertEqual(row["on_floor"], cell["now"])
        self.assertAlmostEqual(row["actual"], round(1 - cell["now"] / row["paid"], 3))
        self.assertAlmostEqual(row["input"], INPUTS["planned_shrinkage"][WED][20 * 60])
        self.assertTrue(0 < row["input"] < 1)


if __name__ == "__main__":
    unittest.main()
