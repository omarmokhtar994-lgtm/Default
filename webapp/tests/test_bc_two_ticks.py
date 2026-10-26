# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC (owner, 2026-10-26: "make the 2 modules for channel: fixed as much as possible, or the balanced one, with 2 different ticks"): the
Channel Setup tab and the Plan channels page have two ticks. Fixed ("Keep each person on the same channel through the day") is the Phase AY tick
as it was; Balanced ("Balance each person's channels through the day") is that tick plus a couple of hours on one channel, then another.
If both are ticked, Balanced wins (it contains Fixed's calm)."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import webapp.app as app_module
from webapp.channel_template import SETTINGS
from webapp.channels import read_channels
from webapp.tests.test_channel_page import _Page
from webapp.tests.test_channels import add_channel_tabs

FIXED_ROW = "Keep each person on the same channel through the day"
BALANCED_ROW = "Balance each person's channels through the day"


class TheRows(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_template_offers_both_rows_off_by_default(self):
        rows = {name: value for name, value, _ in SETTINGS}
        self.assertEqual(rows[FIXED_ROW], "No")
        self.assertEqual(rows[BALANCED_ROW], "No")

    def test_each_row_is_read_on_its_own(self):
        fixed = read_channels(add_channel_tabs(self.dir / "a.xlsx", settings=[(FIXED_ROW, "Yes")]), 60)["rules"]
        balanced = read_channels(add_channel_tabs(self.dir / "b.xlsx", settings=[(BALANCED_ROW, "Yes")]), 60)["rules"]
        plain = read_channels(add_channel_tabs(self.dir / "c.xlsx"), 60)["rules"]
        self.assertEqual((bool(fixed["consistent"]), bool(fixed.get("balanced"))), (True, False))
        self.assertEqual((bool(balanced["consistent"]), bool(balanced.get("balanced"))), (False, True))
        self.assertEqual((bool(plain["consistent"]), bool(plain.get("balanced"))), (False, False))

    def test_a_row_that_is_not_yes_or_no_is_refused_with_its_name(self):
        book = add_channel_tabs(self.dir / "d.xlsx", settings=[(BALANCED_ROW, "Sometimes")])
        with self.assertRaisesRegex(ValueError, "Balance each person's channels through the day must be Yes or No; it reads Sometimes"):
            read_channels(book, 60)


class TheTicksOnThePage(_Page):
    @classmethod
    def setUpClass(cls):
        cls.start()

    def seen(self, **form):
        seen = []
        real = app_module.plan_day

        def spy(people, setup, *a, **k):
            seen.append((bool(setup["rules"].get("consistent")), bool(setup["rules"].get("balanced"))))
            return real(people, setup, *a, **k)
        with mock.patch.object(app_module, "plan_day", spy):
            self.post(action="suggest", move="1", **form)
        return seen[0]

    def test_the_page_has_two_ticks_with_their_own_words(self):
        page = self.page()[1]
        self.assertIn('name="consistent"', page)
        self.assertIn('name="balanced"', page)
        self.assertIn("Keep each person on one channel as much as possible", page)
        self.assertIn("Balance channels: a couple of hours on one, then another", page)

    def test_each_tick_reaches_the_planner_on_its_own(self):
        self.assertEqual(self.seen(), (False, False))
        self.assertEqual(self.seen(consistent="1"), (True, False))
        self.assertEqual(self.seen(balanced="1"), (False, True))

    def test_both_ticks_mean_balanced(self):
        self.assertEqual(self.seen(consistent="1", balanced="1"), (False, True))


if __name__ == "__main__":
    unittest.main()
