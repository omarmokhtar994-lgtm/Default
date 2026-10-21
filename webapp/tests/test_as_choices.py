# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AS (owner, 2026-10-21: an associate choosing another break time "should see the intervals which will be most
probably approved with high buffer then moderate buffer; as for low buffer it should show a warning that this will most
probably be rejected as no availability in that interval"; answer: one person above the need is High, at the need is
Moderate, below it is Low). The times offered for a break, and for coaching, with their buffer, on a window that runs
past 00:00."""
import unittest

from webapp.change_requests import HIGH, LOW, MODERATE, break_choices, coaching_choices, level_of

STEP = 30
START = 20 * 60          # the window opens at 20:00 and runs 24 hours: 1200 to 2640 minutes
SHIFT = (22 * 60, 31 * 60)  # 22:00 to 07:00 the next day


def required_at(t):
    return 6 if t < 1500 else 4 if t < 1620 else 5


def view(break_start=1470, lunch_start=1620, others_on_floor=5):
    """The associate on a 22:00 to 07:00 shift (Break 1 at 00:30, Lunch at 03:00) among ``others_on_floor`` colleagues."""
    breaks = [{"idx": 0, "kind": "Break 1", "start": break_start, "planned_start": 1470, "minutes": 15, "moved": False},
              {"idx": 1, "kind": "Lunch", "start": lunch_start, "planned_start": 1620, "minutes": 30, "moved": False}]
    seg = {"offset": 0, "called_in": False, "label": "22:00 - 07:00", "start": SHIFT[0], "end": SHIFT[1],
           "status": "Present", "billable": False, "away": (0, 0), "breaks": breaks, "cancelled": [], "activities": []}
    def on_floor(t):  # the colleagues, and the associate unless on a break
        mine = SHIFT[0] <= t < SHIFT[1] and not any(b["start"] <= t < b["start"] + b["minutes"] for b in breaks)
        return others_on_floor + (1 if mine else 0)
    cells = [{"t": t, "required": required_at(t), "slots": [on_floor(u) for u in range(t, t + STEP, 5)]}
             for t in range(START, START + 1440, STEP)]
    return {"interval": STEP, "measure": "interval", "start": START, "cells": cells,
            "lanes": [{"name": "Associate 014", "segments": [seg]}]}


INPUTS = {"gap_min": 60, "gap_max": 240}


class TheLevels(unittest.TestCase):
    def test_one_above_the_need_is_high_at_the_need_moderate_below_low(self):
        self.assertEqual((level_of(1), level_of(2.4), level_of(0), level_of(0.9), level_of(-0.1)),
                         (HIGH, HIGH, MODERATE, MODERATE, LOW))
        self.assertEqual(level_of(None), HIGH)  # no demand in the intervals it touches


class TheBreakChoices(unittest.TestCase):
    def test_every_legal_time_is_offered_past_midnight_and_inside_the_gaps(self):
        got = break_choices(view(), INPUTS, "Associate 014", 0, now=SHIFT[0])
        starts = [c["start"] for c in got["choices"]]
        self.assertEqual(starts[0], 1365)   # Break 1 must end 240 minutes or less before Lunch at 03:00
        self.assertEqual(starts[-1], 1545)  # and 60 minutes or more before it
        self.assertEqual(starts, sorted(starts))
        self.assertTrue(all(s % 15 == 0 for s in starts))
        self.assertIn(1470, starts)         # the time it has now is a choice, marked as the current one
        self.assertEqual([c["start"] for c in got["choices"] if c["current"]], [1470])

    def test_the_buffer_is_what_the_interval_has_without_them(self):
        by = {c["start"]: c for c in break_choices(view(), INPUTS, "Associate 014", 0, now=SHIFT[0])["choices"]}
        self.assertEqual(by[1380]["level"], LOW)       # 23:00: 6 needed, 5 would be left
        self.assertEqual(by[1530]["level"], HIGH)      # 01:30: 4 needed, 5 would be left
        # a 15-minute break is half of a 30-minute interval: the interval loses half a person on average
        self.assertEqual(by[1530]["people_above"], 1.5)
        self.assertEqual(by[1380]["people_above"], -0.5)

    def test_a_break_across_two_intervals_takes_the_tighter(self):
        by = {c["start"]: c for c in break_choices(view(), INPUTS, "Associate 014", 0, now=SHIFT[0])["choices"]}
        self.assertEqual(by[1485]["level"], LOW)       # 00:45 to 01:00 is still in the 6-needed interval

    def test_a_time_that_has_passed_is_not_offered(self):
        got = break_choices(view(), INPUTS, "Associate 014", 0, now=1500)
        self.assertTrue(all(c["start"] >= 1500 for c in got["choices"]))

    def test_the_other_break_is_the_limit_after_it_has_moved(self):
        got = break_choices(view(lunch_start=1700), INPUTS, "Associate 014", 0, now=SHIFT[0])
        self.assertEqual(got["choices"][-1]["start"], 1620)  # the latest quarter hour at least 60 minutes before 03:00+

    def test_someone_with_no_such_break_is_refused(self):
        with self.assertRaises(ValueError):
            break_choices(view(), INPUTS, "Associate 014", 7, now=SHIFT[0])
        with self.assertRaises(ValueError):
            break_choices(view(), INPUTS, "Nobody", 0, now=SHIFT[0])


class TheCoachingChoices(unittest.TestCase):
    def test_times_are_those_everyone_is_free_with_their_buffer_for_all_of_them_together(self):
        got = coaching_choices(view(), ["Associate 014"], 30, SHIFT[0], SHIFT[1], now=SHIFT[0])
        by = {c["start"]: c for c in got}
        self.assertEqual(by[1530]["level"], HIGH)  # 01:30: 4 needed, 5 left of 6
        self.assertNotIn(1470, by)      # on a break at 00:30 (with its ten minutes either side)
        self.assertEqual(by[1380]["level"], LOW)  # 23:00 to 23:30: 6 needed, 5 left

    def test_two_people_off_the_floor_cost_two(self):
        v = view()
        v["lanes"].append({"name": "Associate 021", "segments": [dict(v["lanes"][0]["segments"][0], breaks=[])]})
        by = {c["start"]: c for c in coaching_choices(v, ["Associate 014", "Associate 021"], 30, SHIFT[0], SHIFT[1],
                                                       now=SHIFT[0])}
        self.assertEqual(by[1530]["people_above"], 0)  # 4 needed; 6 on the floor, 2 away: 4 left


if __name__ == "__main__":
    unittest.main()
