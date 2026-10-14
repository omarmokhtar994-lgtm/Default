# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T2: the RTA's first screen says what happens now and next (sample ag01, owner's approval 2026-10-14).

A "Now" panel above the tabs, today only: the next hour (breaks starting, shifts starting and ending, each person a
link to their day) and what needs attention in the next three hours (short intervals, language gaps, channel
warnings), most urgent first. Another day has no Now panel.
"""
import datetime as dt
import unittest
from unittest import mock

from webapp.day import now_panel

H = 60


def seg(start, end, breaks=(), status="Present", offset=0):
    return {"offset": offset, "start": int(start * H), "end": int(end * H), "status": status,
            "breaks": [{"idx": i, "kind": k, "start": int(s * H), "minutes": m} for i, (k, s, m) in enumerate(breaks)]}


def view(short=(), bad=()):
    cells = []
    for t in range(0, 1440, 60):
        cls = "bad" if t in bad else ("warn" if t in short else "ok")
        cells.append({"t": t, "need": 3, "now": 2.0 if cls != "ok" else 3.0, "pm": -1.0 if cls != "ok" else 0.0,
                      "cls": cls})
    lanes = [{"name": "Associate 07", "segments": [seg(12, 21, [("Break 1", 14.5, 15), ("Lunch", 17, 30), ("Break 2", 18.5, 15)])]},
             {"name": "Associate 12", "segments": [seg(10.25, 19.25, [("Break 2", 18.75, 15)])]},
             {"name": "Associate 30", "segments": [seg(19, 28, [("Break 1", 19.75, 15)])]},
             {"name": "Associate 33", "segments": [seg(17, 26, [("Break 1", 18.75, 15)], status="Sick")]}]
    return {"interval": 60, "cells": cells, "lanes": lanes, "languages": [], "channels": None}


NOW = 18 * H + 24


class TheNextHour(unittest.TestCase):
    def test_breaks_starts_and_ends_in_time_order(self):
        found = now_panel(view(), NOW)
        self.assertEqual([(n["t"], n["name"], n["what"]) for n in found["next"]],
                         [(18 * H + 30, "Associate 07", "Break 2"), (18 * H + 45, "Associate 12", "Break 2"),
                          (19 * H, "Associate 30", "Starts"), (19 * H + 15, "Associate 12", "Ends")])
        # past breaks, those beyond the hour (19:45) and the sick person's break are left out

    def test_another_day_has_none(self):
        self.assertIsNone(now_panel(view(), 10 ** 6))
        self.assertIsNone(now_panel(view(), -10 ** 6))


class NeedsAttention(unittest.TestCase):
    def test_short_and_gaps_in_the_next_three_hours(self):
        found = now_panel(view(short={19 * H}, bad={21 * H, 23 * H}), NOW)
        self.assertEqual([(a["level"], a["text"]) for a in found["attention"]],
                         [("gap", "21:00 to 22:00: short by a person or more"),
                          ("short", "19:00 to 20:00: short by less than one person")])

    def test_language_gaps_and_channel_warnings(self):
        v = view()
        v["languages"] = [{"name": "French", "cells": [{"t": t, "cls": "bad" if t == 20 * H else "lok"} for t in range(0, 1440, 60)]}]
        v["channels"] = {"warnings": [{"t0": 19 * H, "t1": 20 * H, "text": "19:00 to 20:00: nobody on Chat"},
                                      {"t0": 9 * H, "t1": 10 * H, "text": "09:00 to 10:00: nobody on Phone"}]}
        texts = [a["text"] for a in now_panel(v, NOW)["attention"]]
        self.assertIn("French: 20:00 to 21:00", texts)
        self.assertIn("19:00 to 20:00: nobody on Chat", texts)
        self.assertNotIn("09:00 to 10:00: nobody on Phone", texts)  # over already

    def test_nothing_to_watch(self):
        self.assertEqual(now_panel(view(), NOW)["attention"], [])


class _Clock(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 10, 14, 15, 30, tzinfo=tz)


class OnThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def url(self, day):
        return f"/day?program={self.key.replace(' ', '+')}&date={day}"

    def test_today_has_the_now_panel(self):
        with mock.patch("webapp.app.datetime", _Clock):
            page = self.admin.get(self.url("2026-10-14")).get_data(as_text=True)
            other = self.admin.get(self.url("2026-10-15")).get_data(as_text=True)
        self.assertIn('aria-labelledby="now-h"', page)
        self.assertIn("Next hour", page)
        self.assertNotIn('aria-labelledby="now-h"', other)


if __name__ == "__main__":
    unittest.main()
