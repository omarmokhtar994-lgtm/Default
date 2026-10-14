# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, D2 and D3: what hovering shows on the RTA timeline.

A shift bar: start, end and length, time worked so far, time left until logout and breaks taken. A break: the time
since the last break (or since the shift started) and the time from the shift start.
"""
import unittest

from webapp.day import day_view, hover_tips
from webapp.tests.test_day import INPUTS, WED, WEEK


class WhatHoveringShows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = day_view(WEEK, INPUTS, WED, {}, {})
        cls.lane, cls.seg = next((lane, s) for lane in cls.view["lanes"] for s in lane["segments"]
                                 if s["offset"] == 0 and len(s["breaks"]) >= 2 and s["end"] - s["start"] >= 480)

    def test_a_shift_bar_mid_shift(self):
        seg = self.seg
        now = seg["start"] + 200
        lines = hover_tips(self.view, now)[(self.lane["name"], 0)]["shift"]
        length = seg["end"] - seg["start"]
        self.assertEqual(lines[0], f"{self.lane['name']}, {seg['label']}")
        self.assertIn(f"Length {length // 60} h" + (f" {length % 60} min" if length % 60 else ""), lines)
        self.assertIn("Worked so far 3 h 20 min", lines)
        left = length - 200
        self.assertIn(f"Left until logout {left // 60} h" + (f" {left % 60} min" if left % 60 else ""), lines)
        taken = sum(1 for b in seg["breaks"] if b["start"] + b["minutes"] <= now)
        self.assertIn(f"Breaks {taken} of {len(seg['breaks'])} taken", lines)

    def test_before_and_after_the_shift(self):
        before = hover_tips(self.view, self.seg["start"] - 30)[(self.lane["name"], 0)]["shift"]
        self.assertIn("Worked so far 0 min", before)
        after = hover_tips(self.view, self.seg["end"] + 30)[(self.lane["name"], 0)]["shift"]
        self.assertIn("Left until logout 0 min", after)

    def test_a_break(self):
        first, second = sorted(self.seg["breaks"], key=lambda b: b["start"])[:2]
        tips = hover_tips(self.view, 0)[(self.lane["name"], 0)]["breaks"]
        since_start = first["start"] - self.seg["start"]
        self.assertIn(f"Since the shift started {since_start // 60} h" + (f" {since_start % 60} min" if since_start % 60 else ""),
                      tips[first["idx"]])
        gap = second["start"] - first["start"] - first["minutes"]
        self.assertIn(f"Since the last break {gap // 60} h" + (f" {gap % 60} min" if gap % 60 else "") if gap >= 60
                      else f"Since the last break {gap} min", tips[second["idx"]])
        from_start = second["start"] - self.seg["start"]
        self.assertIn(f"From shift start {from_start // 60} h" + (f" {from_start % 60} min" if from_start % 60 else ""),
                      tips[second["idx"]])


if __name__ == "__main__":
    unittest.main()
