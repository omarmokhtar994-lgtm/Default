#!/usr/bin/env python3
"""Exhaustive checks of the engine's time and index arithmetic.

Midnight wrap, overnight shifts, the Saturday -> next-Sunday week boundary and
quarter indexing are where off-by-one errors live, and they are invisible on a
normal day-shift workbook. Each helper is checked against an independent
reference implementation over its FULL input space on the 15-minute grid,
rather than on a handful of hand-picked examples.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = (Path(os.environ["RC9_ENGINE_DIR"]).resolve().parent.parent
        if os.environ.get("RC9_ENGINE_DIR")
        else Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

GRID = range(0, 1440, 15)
EPOCH = datetime(2026, 1, 4)  # a Sunday


def ref_minutes_covered(day: int, start: int, duration: int) -> set[int]:
    """Absolute week-minutes a shift covers, computed with real datetimes."""
    begin = EPOCH + timedelta(days=day, minutes=start)
    return {int((begin + timedelta(minutes=m) - EPOCH).total_seconds() // 60)
            for m in range(duration)}


class MinuteAndClockText(unittest.TestCase):
    def test_hhmm_round_trips_through_minute_of_day_for_every_minute(self):
        for minute in range(1440):
            with self.subTest(minute=minute):
                self.assertEqual(E.minute_of_day(E.hhmm(minute)), minute)

    def test_excel_day_fractions_land_on_the_right_minute(self):
        """Excel stores 09:15 as 0.385416666..., which is not exact in binary."""
        for minute in range(1440):
            with self.subTest(minute=minute):
                self.assertEqual(E.minute_of_day(minute / 1440.0), minute)

    def test_datetime_and_time_objects(self):
        for minute in GRID:
            t = dtime(minute // 60, minute % 60)
            self.assertEqual(E.minute_of_day(t), minute)
            self.assertEqual(E.minute_of_day(datetime(2026, 1, 1, t.hour, t.minute)), minute)

    def test_invalid_clock_text_is_rejected_not_wrapped(self):
        for bad in ("24:00", "12:60", "99:99", "", None, "abc"):
            with self.subTest(bad=bad):
                self.assertIsNone(E.minute_of_day(bad))

    def test_hhmm_wraps_negative_and_overflow(self):
        self.assertEqual(E.hhmm(1440), "00:00")
        self.assertEqual(E.hhmm(1455), "00:15")
        self.assertEqual(E.hhmm(-15), "23:45")


class ShiftParsing(unittest.TestCase):
    def test_every_start_end_pair_on_the_grid(self):
        """Duration must be the forward distance, with 00:00-00:00 as 24h."""
        for st in GRID:
            for en in GRID:
                with self.subTest(st=st, en=en):
                    parts = E.shift_parts(f"{E.hhmm(st)}-{E.hhmm(en)}")
                    self.assertIsNotNone(parts)
                    got_st, got_en, dur = parts
                    expected = (en - st) % 1440 or 1440
                    self.assertEqual((got_st, got_en, dur), (st, en, expected))
                    self.assertTrue(0 < dur <= 1440)

    def test_overnight_shift_is_not_negative(self):
        self.assertEqual(E.shift_parts("22:00-07:00"), (1320, 420, 540))


class WeekQuarterCoverage(unittest.TestCase):
    """shift_covers_week_qslot against real datetimes, including Saturday
    overnight shifts that spill into the next Sunday's pseudo-quarters."""

    def test_matches_datetime_reference_for_every_day_start_and_duration(self):
        for day in range(7):
            for st in GRID:
                for dur in (240, 480, 540, 600, 720):
                    shift = SimpleNamespace(start_min=st, duration_q=dur // 15)
                    expected_q = {m // 15 for m in ref_minutes_covered(day, st, dur)}
                    lo = day * 96 + st // 15
                    got_q = {q for q in range(lo - 2, lo + dur // 15 + 2)
                             if E.shift_covers_week_qslot(day, shift, q)}
                    with self.subTest(day=day, st=st, dur=dur):
                        self.assertEqual(got_q, expected_q)

    def test_saturday_overnight_spills_past_the_week(self):
        shift = SimpleNamespace(start_min=22 * 60, duration_q=36)
        last = 6 * 96 + 88 + 36 - 1
        self.assertTrue(E.shift_covers_week_qslot(6, shift, last))
        self.assertGreaterEqual(last, E.TOTAL_QSLOTS,
                                "a Saturday overnight shift must reach next-Sunday quarters")

    def test_previous_saturday_carry_matches_the_same_arithmetic(self):
        """Last week's Saturday shift, relative to this Sunday (quarter 0)."""
        for st in GRID:
            for dur in (480, 540, 600):
                label = f"{E.hhmm(st)}-{E.hhmm(st + dur)}"
                covered = {q for q in range(-96, 96)
                           if E.previous_saturday_covers_qslot(label, q)}
                expected = set(range(-96 + st // 15, -96 + st // 15 + dur // 15))
                with self.subTest(label=label):
                    self.assertEqual(covered, expected)

    def test_next_sunday_pseudo_quarter_maps_back_to_sunday(self):
        for q in range(96):
            self.assertEqual(E.next_sunday_own_qslot(E.TOTAL_QSLOTS + q), q)

    def test_total_qslots_is_seven_days_of_quarters(self):
        self.assertEqual(E.TOTAL_QSLOTS, 7 * 96)


class RestBetweenShifts(unittest.TestCase):
    """rest_compatible against real datetimes for consecutive days."""

    def ref_rest_minutes(self, prev_st, prev_dur, next_st):
        prev_end = EPOCH + timedelta(minutes=prev_st + prev_dur)
        next_begin = EPOCH + timedelta(days=1, minutes=next_st)
        return (next_begin - prev_end).total_seconds() / 60

    def test_matches_datetime_reference_across_the_grid(self):
        for prev_st in GRID:
            for prev_dur in (480, 540, 600, 720):
                for next_st in GRID:
                    rest = self.ref_rest_minutes(prev_st, prev_dur, next_st)
                    prev = SimpleNamespace(start_min=prev_st, duration_min=prev_dur)
                    nxt = SimpleNamespace(start_min=next_st, duration_min=540)
                    for hours in (8, 11, 12):
                        with self.subTest(prev_st=prev_st, prev_dur=prev_dur,
                                          next_st=next_st, hours=hours):
                            self.assertEqual(E.rest_compatible(prev, nxt, hours),
                                             rest >= hours * 60)

    def test_overnight_previous_shift(self):
        """22:00 + 9h ends 07:00; an 08:00 start is one hour later."""
        prev = SimpleNamespace(start_min=1320, duration_min=540)
        nxt = SimpleNamespace(start_min=480, duration_min=540)
        self.assertTrue(E.rest_compatible(prev, nxt, 1.0))
        self.assertFalse(E.rest_compatible(prev, nxt, 1.25))


class CircularDistance(unittest.TestCase):
    def test_is_the_shorter_way_round_the_clock(self):
        for a in GRID:
            for b in GRID:
                d = abs(a - b)
                self.assertEqual(E.circular_minute_distance(a, b), min(d, 1440 - d))


if __name__ == "__main__":
    unittest.main(verbosity=1)
