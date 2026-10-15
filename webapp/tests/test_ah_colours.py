# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AH (owner, 2026-10-15, answer 5: "all pages"): the colour rule of ``day.band`` on every page that colours
intervals: the Weeks grid, the run and Home walls, the plan-breaks strip, the RTA's board, timeline, achievement
strip and wallboard. Below the week's target red, from the target to 99% amber (marked tight under 10 minutes over
the target), 100% or more teal. Made-up "Associate NN" data."""
import copy
import re
import unittest
from datetime import date

from webapp import results
from webapp.break_plan import floor
from webapp.day import CUSHION, band, board
from webapp.tests.test_notify_daybook import WED, _Tagged
from webapp.tests.test_week import REAL
from webapp.week import view


def cells_of(v):
    return [c for row in v["grid"] if "cells" in row for c in row["cells"] if c["cls"] != "none"]


class TheWeekGrid(unittest.TestCase):
    def test_cells_follow_the_weeks_target(self):
        found = {}
        for target in (0.9, 0.8):
            for c in cells_of(view(REAL, target=target)):
                ratio = c["pct"] / 100
                if c["cls"] == "over":
                    continue
                found.setdefault(target, []).append(c["cls"])
                with self.subTest(target=target, day=c["day"], time=c["time"]):
                    self.assertEqual(c["cls"], "covered" if c["full"] else "short" if c["share"] >= target - 1e-9
                                     else "gap")
                    self.assertEqual(c["tight"], c["cls"] == "short" and c["over"] < CUSHION)
        self.assertGreater(found[0.8].count("short"), found[0.9].count("short"))  # 80 to 89% turns amber
        self.assertEqual(view(REAL)["totals"], view(REAL, target=0.9)["totals"])  # the counts do not move


class TheWalls(unittest.TestCase):
    def test_run_wall_recoloured_by_the_target(self):
        summary = results.version_summary({"intervals": copy.deepcopy(REAL)})
        results.recolour(summary, 0.8)
        self.assertEqual(summary["target"], 0.8)
        seen = [c for day in summary["cells"] for c in day if c]
        for c in seen:
            if c["cls"] == "over":
                continue
            self.assertEqual(c["cls"], "covered" if c["share"] >= 1 - 1e-9 else
                             "short" if c["share"] >= 0.8 - 1e-9 else "gap")
            self.assertEqual(c["before_cls"], "covered" if c["before_share"] >= 1 - 1e-9 else
                             "short" if c["before_share"] >= 0.8 - 1e-9 else "gap")

    def test_an_older_summary_without_shares_still_recolours(self):
        summary = {"cells": [[{"cls": "gap", "pct": 85, "before_pct": 100, "before_cls": "covered"}, None]]}
        results.recolour(summary, 0.8)
        self.assertEqual((summary["cells"][0][0]["cls"], summary["cells"][0][0]["before_cls"]), ("short", "covered"))


class ThePages(_Tagged):
    def setUp(self):
        self.store.set_interval_target(self.key, "2026-10-11", 80, self.omar)

    def tearDown(self):
        self.store.set_interval_target(self.key, "2026-10-11", 90, self.omar)

    def test_board_states_follow_the_page(self):
        page = self.days.page(self.key, WED)
        rows = board(page["view"], page["target"]["target"])
        for r in rows:
            with self.subTest(t=r["t"]):
                want = {"none": "none", "ok": "good", "warn": "under", "bad": "short"}[r["cls"]]
                self.assertEqual(r["state"], want)
                if r["state"] == "under":
                    self.assertEqual(r["label"], "Tight" if r["tight"] else "Under 100%")
                if r["state"] == "short":
                    self.assertEqual(r["label"], "Below the target")

    def test_plan_breaks_strip_follows_the_target(self):
        page = self.days.page(self.key, WED)
        week, inputs = page["week"], page["inputs"]
        strip = floor(week, inputs, page["day"], {}, {"breaks": []}, 0.8)
        for c in strip:
            if c["pm"] is not None:
                req = inputs["required"].get(page["day"], {}).get(c["t"], 0.0)
                self.assertEqual(c["cls"], band(c["now"], req, 0.8))

    def test_legends_name_the_weeks_target(self):
        week = self.client.get(f"/week?program={self.key}&week=2026-10-11").get_data(as_text=True)
        self.assertIn("80 to 99%", week)
        self.assertIn("Under 80%", week)
        self.assertNotIn("90 to 99%", week)
        day = self.client.get(f"/day?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        self.assertIn("Below the target", day)
        self.assertNotIn("Short by a person or more", day)
        self.assertRegex(day, r'class="achv-strip[^"]*"[^>]*>\s*<i class="(ok|warn|bad|none)')
        board_html = self.client.get(f"/day?program={self.key}&date={WED.isoformat()}&view=board").get_data(as_text=True)
        self.assertNotIn("short by less than one person", board_html)
        self.assertNotRegex(board_html, r'style="')

    def test_handover_short_intervals_follow_the_target(self):
        from webapp.handover import note
        n = note(self.days, self.key, WED)
        page = self.days.page(self.key, WED)
        cls = {c["t"]: c["cls"] for c in page["view"]["cells"]}
        self.assertEqual(n["short_cls"], {t: cls[t] for t, _ in n["short"]})
        later = self.days.page(self.key, date(2026, 10, 15))
        ratio = later["target"]["target"]
        want = {c["t"]: band(c["plan"], c["required"], ratio) for c in later["view"]["cells"]}
        self.assertEqual(n["tomorrow"]["short_cls"], {t: want[t] for t, _ in n["tomorrow"]["short"]})
        html = self.client.get(f"/day/handover?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        for t, kind in n["short_cls"].items():
            self.assertIn(f'<span class="pill {kind}">{t // 60:02d}:{t % 60:02d}', html)

    def test_run_page_wall_names_the_target(self):
        run = next(r for r in self.store.list_runs() if r.get("program") == self.key)
        html = self.client.get(f"/runs/{run['id']}").get_data(as_text=True)
        if 'class="wall"' in html:
            self.assertIn("Under 80%", html)
            self.assertNotIn("Under 90%", html)


if __name__ == "__main__":
    unittest.main()
