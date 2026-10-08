# © 2026 Omar Mokhtar. All rights reserved.
"""Phase N task 4: the day, from the schedule in use plus attendance and actual breaks.

The real Voice week in the repository (English and International, 30-minute
demand, Tuesday overnight shifts reaching into Wednesday). Names are read from
the workbook, never written here."""
import math
import unittest
from pathlib import Path

from webapp.day import (BreakRefused, check_break, day_view, meeting_slots, overtime_offers, read_inputs, replan,
                        vto_offers)
from webapp.versions import DAYS, read_week, shift_span

REPO = Path(__file__).resolve().parents[2]
VOICE = REPO / "fixtures" / "real_runs" / "language_hours" / "VOICE_FINAL_SHEET_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"
WEEK = read_week(VOICE)
INPUTS = read_inputs(VOICE)
WED = 3


def at(view, hhmm):
    h, m = map(int, hhmm.split(":"))
    return next(c for c in view["cells"] if c["t"] == h * 60 + m)


def minute(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def someone(day, covering, starts_by=None):
    """A person whose shift that day covers the given half-hour and who has no break
    within two hours of it; with ``starts_by``, one whose shift starts by then and who
    has no break in its first half-hour or in the given one."""
    for a in WEEK["associates"]:
        span = shift_span(a["days"][day])
        if not span or not (span[0] <= covering and covering + 30 <= span[1]):
            continue
        mine = [(minute(b["start"]) + (1440 if minute(b["start"]) < span[0] else 0), b["minutes"])
                for b in WEEK["breaks"] if b["associate"] == a["name"] and b["day"] == DAYS[day]]
        if starts_by is None:
            clash = [s for s, m in mine if abs(s - covering) < 120]
        elif span[0] > starts_by:
            continue
        else:
            clash = [s for s, m in mine for lo in (span[0], covering) if s < lo + 30 and lo < s + m]
        if not clash:
            return a, span
    raise AssertionError("nobody found")


class TheDay(unittest.TestCase):
    def view(self, attendance=None, actual=None):
        return day_view(WEEK, INPUTS, WED, attendance or {}, actual or {})

    def test_overnight_carry_in_counts(self):
        tuesday_night = [a for a in WEEK["associates"] if (shift_span(a["days"][2]) or (0, 0))[1] > 1440]
        self.assertTrue(tuesday_night)
        self.assertFalse([a for a in WEEK["associates"] if (shift_span(a["days"][WED]) or (99, 0))[0] < 30])
        # 00:00 to 00:30 is Tuesday's night shift alone: each person counts for the
        # 5-minute steps they are not on a Tuesday break (breaks after midnight read +24h)
        expected = 0.0
        for a in tuesday_night:
            start = shift_span(a["days"][2])[0]
            away = [(minute(b["start"]) + (1440 if minute(b["start"]) < start else 0) - 1440, b["minutes"])
                    for b in WEEK["breaks"] if b["associate"] == a["name"] and b["day"] == "Tue"]
            expected += sum(1 for t in range(0, 30, 5) if not any(s <= t < s + m for s, m in away)) / 6
        self.assertAlmostEqual(at(self.view(), "00:00")["plan"], round(expected, 1))
        lanes = {l["name"]: l for l in self.view()["lanes"]}
        self.assertTrue(any(s["offset"] == -1 for s in lanes[tuesday_night[0]["name"]]["segments"]))

    def test_unplanned_leave_lowers_the_floor(self):
        person, span = someone(WED, 20 * 60)
        v = self.view({(0, person["name"]): {"status": "Unplanned leave"}})
        cell = at(v, "20:00")
        self.assertEqual(cell["now"], cell["plan"] - 1)
        self.assertEqual(v["tiles"]["absent"], 1)

    def test_late_counts_from_arrival(self):
        person, span = someone(WED, 20 * 60, starts_by=18 * 60 + 30)
        late = {(0, person["name"]): {"status": "Late", "to": span[0] + 60}}
        v = self.view(late)
        first = at(v, f"{span[0] // 60:02d}:{span[0] % 60:02d}")
        self.assertEqual(first["now"], first["plan"] - 1)
        self.assertEqual(at(v, "20:00")["now"], at(v, "20:00")["plan"])

    def test_moved_break_changes_two_intervals(self):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed" and b["kind"] == "Lunch" and b["start"].endswith(":00"))
        person = b["associate"]
        lanes = {l["name"]: l for l in self.view()["lanes"]}
        idx = next(x["idx"] for s in lanes[person]["segments"] if s["offset"] == 0 for x in s["breaks"] if x["kind"] == "Lunch")
        start = int(b["start"][:2]) * 60 + int(b["start"][3:])
        v = self.view(actual={(0, person, idx): start + 60})
        self.assertEqual(at(v, b["start"])["now"], at(v, b["start"])["plan"] + 1)
        moved = f"{(start + 60) // 60:02d}:{(start + 60) % 60:02d}"
        self.assertEqual(at(v, moved)["now"], at(v, moved)["plan"] - 1)
        self.assertTrue(next(x for s in {l["name"]: l for l in v["lanes"]}[person]["segments"] if s["offset"] == 0
                             for x in s["breaks"] if x["idx"] == idx)["moved"])

    def test_break_must_stay_inside_the_shift(self):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed")
        person = next(a for a in WEEK["associates"] if a["name"] == b["associate"])
        span = shift_span(person["days"][WED])
        with self.assertRaises(BreakRefused):
            check_break(WEEK, WED, 0, person["name"], 0, span[1] - 5, {})  # would run past the shift's end
        with self.assertRaises(BreakRefused):
            check_break(WEEK, WED, 0, person["name"], 0, span[0] + 7, {})  # not a 5-minute step
        check_break(WEEK, WED, 0, person["name"], 0, span[0] + 120, {})  # fine

    def test_five_minute_steps_only(self):
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed")
        span = shift_span(next(a for a in WEEK["associates"] if a["name"] == b["associate"])["days"][WED])
        for step in (1, 2, 3, 4, 7, 13):
            with self.assertRaises(BreakRefused):
                check_break(WEEK, WED, 0, b["associate"], 0, span[0] + 120 + step, {})
        check_break(WEEK, WED, 0, b["associate"], 0, span[0] + 125, {})

    def test_break_may_not_overlap_another(self):
        breaks = [b for b in WEEK["breaks"] if b["day"] == "Wed"]
        name = breaks[0]["associate"]
        mine = [b for b in breaks if b["associate"] == name]
        second = int(mine[1]["start"][:2]) * 60 + int(mine[1]["start"][3:])
        with self.assertRaises(BreakRefused):
            check_break(WEEK, WED, 0, name, 0, second, {})

    def test_language_rows(self):
        rows = {r["name"]: r for r in self.view()["languages"]}
        self.assertEqual(set(rows), {"English", "International"})
        intl = rows["International"]
        self.assertEqual((intl["start"], intl["end"]), (0, 16 * 60))
        inside = [c for c in intl["cells"] if c["count"] is not None]
        self.assertEqual(len(inside), 32)  # 00:00 to 16:00 in half-hours
        self.assertIsNone(next(c for c in rows["English"]["cells"] if c["t"] == 12 * 60)["count"])  # outside English hours

    def test_need_is_the_raw_requirement_without_shrinkage(self):
        # actuals replace the input's shrinkage: absences, breaks and aux are counted as they happen
        cell = at(self.view(), "20:00")
        required = INPUTS["required"][WED][20 * 60]
        self.assertEqual(cell["need"], math.ceil(required))
        self.assertAlmostEqual(cell["pm"], round((cell["now"] - required) * 0.5, 2))
        self.assertNotIn("shrinkage", INPUTS)

    def test_billable_aux_counts_for_intervals_but_not_for_service_level(self):
        person, span = someone(WED, 20 * 60)
        coaching = lambda billable: {(0, person["name"]): {"status": "Coaching", "from": 20 * 60, "to": 21 * 60,
                                                           "billable": billable}}
        plan = at(self.view(), "20:00")["plan"]
        billable = coaching(True)
        self.assertEqual(at(day_view(WEEK, INPUTS, WED, billable, {}, measure="interval"), "20:00")["now"], plan)
        self.assertEqual(at(day_view(WEEK, INPUTS, WED, billable, {}, measure="sl"), "20:00")["now"], plan - 1)
        unbillable = coaching(False)
        self.assertEqual(at(day_view(WEEK, INPUTS, WED, unbillable, {}, measure="interval"), "20:00")["now"], plan - 1)
        self.assertEqual(at(self.view(billable), "20:00")["aux"], 1)  # counted either way
        self.assertEqual(at(self.view(billable), "21:00")["aux"], 0)

    def test_counts_per_interval(self):
        person, span = someone(WED, 20 * 60)
        v = self.view({(0, person["name"]): {"status": "Unplanned leave"}})
        self.assertEqual((at(v, "20:00")["absent"], at(v, "20:00")["aux"]), (1, 0))
        b = next(b for b in WEEK["breaks"] if b["day"] == "Wed" and b["kind"] == "Lunch" and b["start"].endswith(":00"))
        lanes = {l["name"]: l for l in self.view()["lanes"]}
        idx = next(x["idx"] for s in lanes[b["associate"]]["segments"] if s["offset"] == 0 for x in s["breaks"]
                   if x["kind"] == "Lunch")
        start = minute(b["start"])
        hhmm = lambda m: f"{m // 60:02d}:{m % 60:02d}"
        moved = self.view(actual={(0, b["associate"], idx): start + 60})
        self.assertEqual(at(moved, b["start"])["breaks"], at(self.view(), b["start"])["breaks"] - 1)
        self.assertEqual(at(moved, hhmm(start + 60))["breaks"], at(self.view(), hhmm(start + 60))["breaks"] + 1)

    def test_five_minute_ticks_per_interval(self):
        cell = at(self.view(), "20:00")
        self.assertEqual(len(cell["slots"]), 6)
        self.assertEqual(cell["low"], min(cell["slots"]))
        self.assertAlmostEqual(cell["now"], round(sum(cell["slots"]) / 6, 1))

    def test_activities_take_people_off_the_floor(self):
        person, span = someone(WED, 20 * 60)
        plan = at(self.view(), "20:00")["plan"]
        meeting = {(0, person["name"]): [{"kind": "Meeting", "start": 20 * 60, "end": 20 * 60 + 30, "billable": False}]}
        self.assertEqual(at(day_view(WEEK, INPUTS, WED, {}, {}, activities=meeting), "20:00")["now"], plan - 1)
        training = {(0, person["name"]): [{"kind": "Training", "start": 20 * 60, "end": 20 * 60 + 30, "billable": True}]}
        self.assertEqual(at(day_view(WEEK, INPUTS, WED, {}, {}, activities=training), "20:00")["now"], plan)
        self.assertEqual(at(day_view(WEEK, INPUTS, WED, {}, {}, measure="sl", activities=training), "20:00")["now"],
                         plan - 1)
        v = day_view(WEEK, INPUTS, WED, {}, {}, activities=meeting)
        seg = next(s for l in v["lanes"] if l["name"] == person["name"] for s in l["segments"] if s["offset"] == 0)
        self.assertEqual([(a["kind"], a["start"], a["end"]) for a in seg["activities"]], [("Meeting", 1200, 1230)])
        self.assertEqual(at(v, "20:00")["aux"], 1)

    def test_overtime_adds_floor_time_outside_the_shift(self):
        person = next(a for a in WEEK["associates"] if (shift_span(a["days"][WED]) or (0, 0))[1] == 14 * 60)
        before = at(self.view(), "14:00")
        ot = {(0, person["name"]): [{"kind": "Overtime", "start": 14 * 60, "end": 15 * 60, "billable": True}]}
        after = at(day_view(WEEK, INPUTS, WED, {}, {}, activities=ot), "14:00")
        self.assertEqual((after["now"], after["plan"]), (before["now"] + 1, before["plan"]))

    def test_vto_leaves_early(self):
        person, span = someone(WED, 20 * 60)
        vto = {(0, person["name"]): [{"kind": "VTO", "start": 20 * 60, "end": span[1], "billable": False}]}
        v = day_view(WEEK, INPUTS, WED, {}, {}, activities=vto)
        self.assertEqual(at(v, "20:00")["now"], at(self.view(), "20:00")["plan"] - 1)

    def own(self, v, name):
        return next(s for l in v["lanes"] if l["name"] == name for s in l["segments"] if s["offset"] == 0)

    def test_meeting_slots_avoid_breaks_and_rank_by_the_tightest_buffer(self):
        v = self.view()
        team = [a["name"] for a in WEEK["associates"] if (shift_span(a["days"][WED]) or (0, 0))[0] == 17 * 60][:3]
        slots = meeting_slots(v, team, 30, 17 * 60, 23 * 60)
        self.assertTrue(slots)
        self.assertEqual([x["tightest"] for x in slots], sorted((x["tightest"] for x in slots), reverse=True))
        for x in slots:
            self.assertEqual(x["start"] % 5, 0)
            for name in team:
                for b in self.own(v, name)["breaks"]:  # 10 minutes clear of every break
                    self.assertTrue(x["end"] + 10 <= b["start"] or b["start"] + b["minutes"] + 10 <= x["start"], (name, x, b))
        with self.assertRaises(ValueError):
            meeting_slots(v, ["Nobody"], 30, 17 * 60, 23 * 60)

    def test_a_booked_slot_is_no_longer_free(self):
        team = [a["name"] for a in WEEK["associates"] if (shift_span(a["days"][WED]) or (0, 0))[0] == 17 * 60][:2]
        first = meeting_slots(self.view(), team, 30, 17 * 60, 23 * 60)[0]
        acts = {(0, n): [{"kind": "Meeting", "start": first["start"], "end": first["end"], "billable": False}] for n in team}
        again = meeting_slots(day_view(WEEK, INPUTS, WED, {}, {}, activities=acts), team, 30, 17 * 60, 23 * 60)
        self.assertFalse(any(x["start"] < first["end"] and first["start"] < x["end"] for x in again))

    def test_overtime_only_next_to_short_intervals_and_inside_the_rules(self):
        v = self.view({(0, someone(WED, 20 * 60)[0]["name"]): {"status": "Unplanned leave"}})
        offers = overtime_offers(v, WEEK, WED, rest_hours=12)
        short = {c["t"] for c in v["cells"] if c["pm"] is not None and c["pm"] < 0}
        self.assertTrue(offers)
        for row in offers:
            self.assertIn(row["t"], short)
            for o in row["offers"]:
                seg = self.own(v, o["name"])
                self.assertTrue(o["end"] == seg["start"] or o["start"] == seg["end"])  # next to the shift
                self.assertLessEqual(o["end"] - o["start"], 120)
                a = next(x for x in WEEK["associates"] if x["name"] == o["name"])
                nxt, prv = shift_span(a["days"][WED + 1]), shift_span(a["days"][WED - 1])
                if nxt:
                    self.assertGreaterEqual(nxt[0] + 1440 - o["end"], 12 * 60)
                if prv:
                    self.assertGreaterEqual(o["start"] + 1440 - prv[1], 12 * 60)

    def test_vto_keeps_need_and_languages(self):
        v = self.view()
        for row in vto_offers(v):
            removed = {o["name"]: o for o in row["offers"]}
            acts = {(0, n): [{"kind": "VTO", "start": o["start"], "end": o["end"], "billable": False}] for n, o in removed.items()}
            after = day_view(WEEK, INPUTS, WED, {}, {}, activities=acts)
            for c in after["cells"]:
                if c["required"] > 0 and row["t"] <= c["t"] < max(o["end"] for o in row["offers"]):
                    self.assertGreaterEqual(c["low"], c["need"], (row["t"], c["t"]))

    def short_day(self):
        gone = [a["name"] for a in WEEK["associates"] if (shift_span(a["days"][WED]) or (0, 0))[0] == 17 * 60][:2]
        return {(0, n): {"status": "Unplanned leave"} for n in gone}

    def applied(self, attendance, plan):
        actual = {(0, m["name"], m["idx"]): m["to"] for m in plan["moves"]}
        return day_view(WEEK, INPUTS, WED, attendance, actual), actual

    def test_replan_never_makes_the_day_worse_and_says_so_truly(self):
        att = self.short_day()
        plan = replan(self.view(att), INPUTS)
        self.assertTrue(plan["moves"])
        self.assertGreaterEqual(plan["after"]["tightest"], plan["before"]["tightest"])
        self.assertLessEqual(plan["after"]["short_hours"], plan["before"]["short_hours"])
        after, _ = self.applied(att, plan)
        self.assertAlmostEqual(plan["after"]["tightest"], min(c["pm"] for c in after["cells"] if c["pm"] is not None), places=2)
        self.assertAlmostEqual(plan["after"]["short_hours"], after["tiles"]["short_hours"], places=1)

    def test_replan_moves_only_breaks_not_started(self):
        plan = replan(self.view(self.short_day()), INPUTS, now=18 * 60)
        self.assertTrue(all(m["from"] >= 18 * 60 and m["to"] >= 18 * 60 for m in plan["moves"]))

    def test_replan_keeps_every_rule(self):
        att = self.short_day()
        plan = replan(self.view(att), INPUTS)
        after, actual = self.applied(att, plan)
        for m in plan["moves"]:
            seg = self.own(after, m["name"])
            self.assertEqual(m["to"] % 5, 0)
            brks = sorted(seg["breaks"], key=lambda b: b["idx"])
            self.assertEqual([b["idx"] for b in sorted(brks, key=lambda b: b["start"])], [b["idx"] for b in brks])
            self.assertTrue(seg["start"] <= brks[0]["start"] and brks[-1]["start"] + brks[-1]["minutes"] <= seg["end"])
            for a, b in zip(brks, brks[1:]):  # the gaps next to a moved break keep the rules (the plan's own may not)
                if m["idx"] in (a["idx"], b["idx"]):
                    gap = b["start"] - (a["start"] + a["minutes"])
                    self.assertTrue(INPUTS["gap_min"] <= gap <= INPUTS["gap_max"], (m["name"], a["kind"], b["kind"], gap))

    def test_tiles_sum_the_cells(self):
        v = self.view()
        short = sum(-c["pm"] for c in v["cells"] if c["pm"] is not None and c["pm"] < 0)
        self.assertAlmostEqual(v["tiles"]["short_hours"], round(short, 1), places=1)
        self.assertEqual(v["interval"], 30)


if __name__ == "__main__":
    unittest.main()
