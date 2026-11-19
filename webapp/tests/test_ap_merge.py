# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP (sample ap01, A and B approved; owner 2026-10-21: only the LOBs of one program merge): two LOBs' day views
as one, with one requirement, one staffed count and one shrinkage, each person kept with their own LOB."""
import math
import unittest
from datetime import date

from webapp.merge import merge_intervals, merge_views, same_interval, shift_view

STEP = 30


def cell(t, required, now, **more):
    base = {"t": t, "required": required, "plan": now, "now": now, "slots": [now] * (STEP // 5), "low": now,
            "absent": 0, "aux": 0, "late_early": 0, "breaks": 0, "overtime": 0, "vto": 0, "outside": 0}
    base.update(more)
    pm = None if required <= 0 else round((now - required) * STEP / 60, 2)
    return {**base, "need": math.ceil(required - 1e-9) if required > 0 else 0, "pm": pm,
            "plan_pm": None if required <= 0 else round((now - required) * STEP / 60, 2),
            "cls": "none" if required <= 0 else ("ok" if now >= required else "warn" if now > required - 1 else "bad")}


def seg(start, end, status="Present", **more):
    return {"offset": 0, "called_in": False, "label": f"{start}-{end}", "start": start, "end": end, "status": status,
            "billable": False, "from": None, "to": None, "away": (0, 0), "breaks": [], "cancelled": [],
            "activities": [], "with_whom": "", "why": "", "with_dept": "", **more}


def view(cells, lanes, languages=None, channels=None, **more):
    return {"interval": STEP, "measure": "interval", "cells": cells, "lanes": lanes, "languages": languages or [],
            "channels": channels, "outside": [],
            "tiles": {"planned": len(lanes),
                      "present": sum(1 for l in lanes if l["segments"][0]["status"] == "Present"),
                      "absent": sum(1 for l in lanes if l["segments"][0]["status"] != "Present")}, **more}


def lane(name, *segments):
    return {"name": name, "slot": "", "language": "English", "segments": list(segments)}


class TheMergeCore(unittest.TestCase):
    def setUp(self):
        self.one = view([cell(0, 2, 2), cell(30, 2, 1), cell(60, 0, 0)],
                        [lane("Associate 01", seg(0, 60)), lane("Associate 02", seg(0, 60, "Sick"))])
        self.two = view([cell(0, 1, 1), cell(30, 1, 2), cell(60, 0, 0)], [lane("Associate 21", seg(0, 60))])

    def test_cells_add_up_and_are_judged_on_the_sum(self):
        got = merge_views({"LOB 1": self.one, "LOB 2": self.two})
        a, b, c = got["cells"]
        self.assertEqual((a["required"], a["now"], a["need"], a["pm"], a["cls"]), (3, 3, 3, 0.0, "ok"))
        self.assertEqual((b["required"], b["now"], b["pm"], b["cls"]), (3, 3, 0.0, "ok"))  # 1 short + 1 over cancel
        self.assertEqual((c["required"], c["pm"], c["cls"]), (0, None, "none"))
        self.assertEqual(a["slots"], [3] * 6)
        self.assertEqual(a["low"], 3)

    def test_a_shortfall_in_one_lob_is_not_hidden_by_the_other_only_when_the_sum_covers_it(self):
        short = view([cell(0, 4, 1)], [lane("Associate 31", seg(0, 30))])
        long = view([cell(0, 1, 5)], [lane("Associate 41", seg(0, 30))])
        got = merge_views({"LOB 1": short, "LOB 2": long})["cells"][0]
        self.assertEqual((got["required"], got["now"], got["pm"]), (5, 6, 0.5))

    def test_every_person_keeps_their_lob(self):
        got = merge_views({"LOB 1": self.one, "LOB 2": self.two})
        self.assertEqual([(l["name"], l["lob"]) for l in got["lanes"]],
                         [("Associate 01", "LOB 1"), ("Associate 02", "LOB 1"), ("Associate 21", "LOB 2")])

    def test_tiles_are_recounted_from_the_merged_day(self):
        t = merge_views({"LOB 1": self.one, "LOB 2": self.two})["tiles"]
        self.assertEqual((t["planned"], t["present"], t["absent"]), (3, 2, 1))

    def test_the_same_name_in_two_lobs_is_refused_with_both_named(self):
        twin = view([cell(0, 1, 1)], [lane("Associate 01", seg(0, 60))])
        with self.assertRaises(ValueError) as ctx:
            merge_views({"LOB 1": self.one, "LOB 2": twin})
        self.assertIn("Associate 01", str(ctx.exception))
        self.assertIn("LOB 2", str(ctx.exception))

    def test_different_intervals_are_refused_naming_the_lobs(self):
        other = {**self.two, "interval": 60}
        with self.assertRaises(ValueError) as ctx:
            same_interval({"LOB 1": self.one, "LOB 2": other})
        self.assertIn("LOB 2", str(ctx.exception))

    def test_a_view_moved_by_its_zone_lands_on_the_same_clock_hour(self):
        later = shift_view(self.two, 60)  # LOB 2 is an hour behind: its 00:00 is 01:00 on the shared clock
        self.assertEqual([c["t"] for c in later["cells"]], [60, 90, 120])
        self.assertEqual((later["lanes"][0]["segments"][0]["start"], later["lanes"][0]["segments"][0]["end"]), (60, 120))
        self.assertEqual(self.two["cells"][0]["t"], 0)  # the original is not changed

    def test_cells_that_do_not_line_up_after_the_move_are_refused(self):
        with self.assertRaises(ValueError):
            merge_views({"LOB 1": self.one, "LOB 2": shift_view(self.two, 30)})

    def test_one_lob_alone_comes_back_as_it_was_with_the_lob_named(self):
        got = merge_views({"LOB 1": self.one})
        self.assertEqual(got["cells"], self.one["cells"])
        self.assertEqual(got["lanes"][0]["segments"], self.one["lanes"][0]["segments"])

    def test_languages_add_their_counts_and_minimums(self):
        row = lambda count, minimum: {"name": "English", "start": "00:00", "end": "24:00", "minimum": minimum,
                                      "eligible": ["english"], "gaps": 0,
                                      "cells": [{"t": 0, "count": count, "cls": "lok", "minimum": minimum}]}
        a = view([cell(0, 1, 1)], [lane("Associate 01", seg(0, 30))], languages=[row(1, 1)])
        b = view([cell(0, 1, 1)], [lane("Associate 21", seg(0, 30))], languages=[row(0, 2)])
        got = merge_views({"LOB 1": a, "LOB 2": b})["languages"]
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["minimum"], got[0]["cells"][0]["count"], got[0]["cells"][0]["cls"]), (3, 1, "bad"))
        self.assertEqual(got[0]["gaps"], 1)

    def test_channel_stretches_are_joined_by_person(self):
        a = view([cell(0, 1, 1)], [lane("Associate 01", seg(0, 30))],
                 channels={"runs": {"Associate 01": [(0, 30, "P")]}, "rows": [], "warnings": [], "planned": True,
                           "timelines": {"Associate 01": ["Phone"]}})
        b = view([cell(0, 1, 1)], [lane("Associate 21", seg(0, 30))], channels=None)
        got = merge_views({"LOB 1": a, "LOB 2": b})["channels"]
        self.assertEqual(got["runs"], {"Associate 01": [(0, 30, "P")]})
        self.assertTrue(got["planned"])
        self.assertEqual(got["rows"], [])
        self.assertIsNone(merge_views({"LOB 2": b})["channels"])

    def test_interval_rows_of_a_week_are_summed_by_day_and_time(self):
        # [day, "HH:MM", required, after_eff, after_raw, before_eff, before_raw, severe]
        a = [[0, "09:00", 2.0, 1.5, 2, 1.0, 1, 0]]
        b = [[0, "09:00", 1.0, 1.0, 1, 1.0, 1, 1], [1, "09:00", 3.0, 2.0, 2, 2.0, 2, 0]]
        got = merge_intervals({"LOB 1": a, "LOB 2": b})
        self.assertEqual(got, [[0, "09:00", 3.0, 2.5, 3, 2.0, 2, 1], [1, "09:00", 3.0, 2.0, 2, 2.0, 2, 0]])


if __name__ == "__main__":
    unittest.main()
