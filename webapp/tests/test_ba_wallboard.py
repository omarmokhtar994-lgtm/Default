# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA, T5 (owner, 2026-10-25: "make sure wallboard contains all needed info"): besides the next four intervals, who is on break and who
is next, and the languages, the floor's screen shows the day's headcount (on shift, out, late or left early, overtime, VTO, called in),
the day's achievement against the target, the shifts starting or ending in the next hour, what needs attention in the next three hours,
who is out and why, each channel's cover now, and when the screen was drawn."""
import html
import re
import unittest

from webapp.day import wall_extra
from webapp.tests.test_notify_daybook import WED, _Tagged


def lane(name, *segments):
    return {"name": name, "segments": list(segments)}


def seg(start, end, status="Present", breaks=(), offset=0):
    return {"start": start, "end": end, "status": status, "breaks": list(breaks), "offset": offset, "activities": []}


def view(**more):
    base = {"interval": 30, "cells": [], "languages": [], "channels": None,
            "tiles": {"planned": 4, "present": 2, "absent": 1, "late_early": 1, "aux": 0, "moved": 0, "overtime": 90, "vto": 30,
                      "called_in": 60, "short_hours": 1.5, "short_intervals": 3},
            "lanes": [lane("Associate 01", seg(480, 960)), lane("Associate 02", seg(540, 1020, "Sick")),
                      lane("Associate 03", seg(480, 960, "Late")), lane("Associate 04", seg(600, 1080))]}
    base.update(more)
    return base


class TheExtraFigures(unittest.TestCase):
    def test_who_is_out_and_why(self):
        got = wall_extra(view(), 700)
        self.assertEqual(got["out"], [{"name": "Associate 02", "status": "Sick"}, {"name": "Associate 03", "status": "Late"}])

    def test_the_day_figures_in_hours(self):
        got = wall_extra(view(), 700)["day"]
        self.assertEqual(got, {"on_shift": "3 of 4", "out": 1, "late_early": 1, "overtime": "1.5", "vto": "0.5", "called_in": "1",
                               "short": "1.5"})

    def test_shifts_starting_or_ending_in_the_next_hour(self):
        got = wall_extra(view(), 570)["changes"]  # 09:30: Associate 04 starts at 10:00; nobody ends before 16:00
        self.assertEqual([(c["t"], c["name"], c["what"]) for c in got], [(600, "Associate 04", "Starts")])

    def test_channels_now_are_the_cells_of_the_current_interval(self):
        rows = [{"name": "Phone", "letter": "P", "cells": [{"t": 690, "need": 4, "have": 3, "cls": "bad"}, {"t": 720, "need": 4, "have": 5, "cls": "lok"}]},
                {"name": "Chat · Arabic (at least 1)", "cells": [{"t": 690, "need": 1, "have": 0, "cls": "bad"}]}]
        got = wall_extra(view(channels={"rows": rows, "warnings": [], "now": {}}), 700)["channels"]
        self.assertEqual(got, [{"name": "Phone", "have": 3, "need": 4, "cls": "bad"}])  # only the channels, not the language rules
        self.assertEqual(wall_extra(view(), 700)["channels"], [])  # no channel needs on the schedule: none shown

    def test_a_missing_figure_is_zero_not_an_error(self):
        thin = view(tiles={"planned": 0, "present": 0, "absent": 0, "late_early": 0})
        got = wall_extra(dict(thin, lanes=[]), 700)["day"]
        self.assertEqual((got["on_shift"], got["overtime"], got["vto"], got["called_in"], got["short"]), ("0 of 0", "0", "0", "0", "0"))


class TheScreen(_Tagged):
    def get(self, at="12:00", date=WED):
        return html.unescape(self.client.get(f"/day/wallboard?program={self.key.replace(' ', '+')}&date={date.isoformat()}&at={at}").get_data(as_text=True))

    def test_the_new_sections_are_there_in_a_sensible_order(self):
        page = self.get()
        heads = re.findall(r"<h2>([^<]+)</h2>", page)
        for want in ("On break now", "Next 30 minutes", "Shifts starting or ending", "Needs attention", "Out today", "Languages now"):
            self.assertTrue(any(h.startswith(want) for h in heads), f"{want}: {heads}")
        self.assertLess(page.index("On break now"), page.index("Next 30 minutes"))  # an older test slices the page between these two
        self.assertIn("wall-today", page)
        self.assertIn("intervals at", page)  # the day's achievement against the target

    def test_who_is_out_shows_names_and_the_reason(self):
        days = self.days
        name = next(l["name"] for l in days.page(self.key, WED)["view"]["lanes"] if any(s["offset"] == 0 and s["status"] == "Present" for s in l["segments"]))
        days.set_status(self.key, WED, name, "Sick", self.omar)
        try:
            page = self.get()
            out = page[page.index("Out today"):]
            self.assertIn(f"<b>{name}</b> Sick", out)
        finally:
            days.set_status(self.key, WED, name, "Present", self.omar)

    def test_the_screen_says_when_it_was_drawn(self):
        self.assertRegex(self.get(), r'class="wall-drawn">Drawn \d\d:\d\d:\d\d')

    def test_nobody_out_says_so(self):
        page = self.get(date=WED)
        self.assertRegex(page, r"Out today</h2>(<ul>|<p class=\"wall-none\">)")


if __name__ == "__main__":
    unittest.main()
