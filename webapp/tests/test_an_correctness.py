# © 2026 Omar Mokhtar. All rights reserved.
"""Regressions for the independent AM review; fictional associates only."""
import unittest

from webapp.channel_plan import score_day
from webapp.channel_page import coverage, apply_edit


def config():
    return {"step": 15, "need": {"P": {0: {t: 1 for t in range(540, 660, 15)}}},
            "email_mode": "none", "languages": [], "blended": [],
            "rules": {"min_block": 60, "max_run": {}, "order": ["P", "C", "E"],
                      "strict": True, "fair": False}}


def person():
    return {"name": "Associate 001", "language": "English", "start": 600, "end": 660,
            "breaks": [], "skills": "P", "counts_for": {"english"}}


def plan():
    return {"blocks": {"Associate 001": [(600, 660, "P")]}, "breaks": {"Associate 001": []}}


class CoverageRegressions(unittest.TestCase):
    def test_unstaffed_open_hour_counts_as_short(self):
        self.assertEqual(score_day([person()], plan(), config(), 0, {})["short"]["P"], 1.0)

    def test_empty_roster_does_not_erase_demand(self):
        got = score_day([], {"blocks": {}, "breaks": {}}, config(), 0, {})
        self.assertEqual(got["short"]["P"], 2.0)
        rows = coverage([], {"blocks": {}, "breaks": {}}, config(), 0, 15)
        self.assertEqual(next(c for c in rows[0]["cells"] if c["t"] == 540)["text"], "0/1")

    def test_coverage_table_shows_hour_before_first_shift(self):
        cells = coverage([person()], plan(), config(), 0, 15)[0]["cells"]
        self.assertEqual(next(c for c in cells if c["t"] == 540)["text"], "0/1")

    def test_previous_shift_counts_in_score_and_table(self):
        before = {"P": {t: 1 for t in range(540, 600, 15)}}
        self.assertEqual(score_day([person()], plan(), config(), 0, {}, before=before)["short"]["P"], 0)
        cells = coverage([person()], plan(), config(), 0, 15, before=before)[0]["cells"]
        self.assertEqual(next(c for c in cells if c["t"] == 540)["text"], "1/1")

    def test_fixed_language_cover_is_counted(self):
        setup = config()
        setup["languages"] = [{"channel": "P", "language": "Arabic", "active": True, "minimum": 1,
                              "days": {0}, "start": 540, "end": 600}]
        before = {"P": {t: 1 for t in range(540, 600, 15)},
                  "P:arabic": {t: 1 for t in range(540, 600, 15)}}
        self.assertEqual(score_day([person()], plan(), setup, 0, {}, before=before)["language_short"], 0)

    def test_short_channel_cut_by_break_keeps_am_exception(self):
        # Owner C, 16 October 2026: restore AM's warning rule at breaks.
        p = dict(person(), skills="PC", end=780, breaks=[("Break", 675, 15)])
        setup = config()
        setup["need"]["C"] = {}
        proposed = {"blocks": {p["name"]: [(600, 660, "P"), (660, 675, "C"), (690, 780, "P")]},
                    "breaks": {p["name"]: [675]}}
        got = score_day([p], proposed, setup, 0, {"segments": [[15, "Break"]]})
        self.assertFalse(any("minute minimum" in problem for problem in got["problems"]))

    def test_manual_short_block_is_kept_with_warning(self):
        # Owner C replaces the unrequested refusal with AM's manual override.
        p = dict(person(), skills="PC", end=780, label="10:00 - 13:00")
        setup = config()
        setup["need"]["C"] = {}
        original = {"blocks": {p["name"]: [(600, 780, "P")]}, "breaks": {p["name"]: []}}
        changed = apply_edit(original, p, 660, 675, "C", setup, 0)
        self.assertIn([660, 675, "C"], changed["blocks"][p["name"]])
        got = score_day([p], changed, setup, 0, {})
        self.assertTrue(any("15 minutes" in problem for problem in got["problems"]))

if __name__ == "__main__":
    unittest.main()
