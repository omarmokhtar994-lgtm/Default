# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA (owner, 2026-10-25: "go for what you suggested"): a little 3D, CSS only, within a speed budget. Where it goes: the sign-in
stack and turning mark, Home's program cards tilting toward the pointer, the week's blocks on Weeks, a once-only flip when a run is
approved, a tiny stack on three empty states, and a tilted swatch on each look button. Never on the RTA, the tables, the forms or
the wallboard. The budget: no filter or blur, at most three keyframe animations, everything off for reduced motion, no script library."""
import re
import unittest
from pathlib import Path

from webapp.tests.test_notify_daybook import WED, _Tagged

STATIC = Path(__file__).resolve().parents[1] / "static"
CSS = (STATIC / "app.css").read_text()
START = "/* Phase BA: a little 3D"


def depth_block():
    # re-pinned (Phase BB/BC): the Phase BA block ends where the later blocks begin (they are paint-only depth on charts and tiles, and the scroll
    # panel rules of the list switch; each has its own tests), so this block is still the one that must stay off the RTA, tables and forms
    start = CSS.index(START)
    later = CSS.find("/* Phase BB:", start)
    return CSS[start:later if later != -1 else len(CSS)]


class TheBudget(unittest.TestCase):
    def test_the_depth_block_has_no_blur_and_no_filter(self):
        block = depth_block()
        self.assertNotRegex(block, r"(?<![-\w])filter\s*:")
        self.assertNotIn("backdrop-filter", block)
        self.assertNotIn("will-change", block)  # a promoted layer for nothing

    def test_at_most_three_animations_and_each_is_switched_off_for_reduced_motion(self):
        block = depth_block()
        names = re.findall(r"@keyframes ([\w-]+)", block)
        self.assertEqual(sorted(names), ["ts-drift", "ts-flip", "ts-spin"])
        calm = re.search(r"@media \(prefers-reduced-motion: reduce\) \{([^}]*\{[^}]*\}[^}]*)\}", block, re.S).group(1)
        for selector in (".deck3d", ".mark3d", ".flip"):
            self.assertIn(selector, calm)

    def test_the_motion_stops_when_hidden_or_off_screen(self):
        block = depth_block()
        self.assertIn(".paused .deck3d", block)
        self.assertIn(".still .deck3d", block)

    def test_tilt_is_for_a_mouse_only(self):
        js = (STATIC / "app.js").read_text()
        self.assertIn("(hover: hover) and (pointer: fine)", js)
        self.assertIn("prefers-reduced-motion: reduce", js)

    def test_no_library_came_with_it(self):
        self.assertFalse(list(STATIC.glob("*three*")))
        self.assertNotIn("WebGL", (STATIC / "app.js").read_text())


class ThePages(_Tagged):
    def test_the_sign_in_page_has_a_stack_and_a_mark(self):
        page = self.app.test_client().get("/login").get_data(as_text=True)
        self.assertRegex(page, r'<div class="deck3d" role="img" aria-label="[^"]+">')
        self.assertEqual(page.count('class="day3"'), 4)
        self.assertIn('class="mark3d"', page)

    def test_the_sign_in_page_still_has_its_form(self):
        page = self.app.test_client().get("/login").get_data(as_text=True)
        self.assertIn('name="username"', page)
        self.assertIn('name="password"', page)

    def test_home_cards_tilt(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertRegex(page, r'<article class="pcard" data-tilt>')

    def test_weeks_has_the_week_as_blocks(self):
        q = self.key.replace(" ", "+")
        page = self.client.get(f"/week?program={q}&week=2026-10-11").get_data(as_text=True)
        box = re.search(r'<div class="blocks3d" role="img" aria-label="([^"]+)">(.*?)</div>\s*<div class="tgt-days">', page, re.S)
        self.assertIsNotNone(box, "no blocks")
        self.assertIn("Sun", box.group(1))
        cols = re.findall(r'<span class="blk hb(\d+) (ok|miss|none)" aria-hidden="true">', box.group(2))
        self.assertEqual(len(cols), 7)
        self.assertTrue(all(0 <= int(h) <= 10 for h, _ in cols))

    def test_three_empty_states_wear_a_tiny_stack(self):
        q = self.key.replace(" ", "+")
        page = self.client.get(f"/requests?program={q}").get_data(as_text=True)
        self.assertIn('class="empty deco"', page)

    def test_the_look_buttons_are_previewed(self):
        for look in ("light", "dark", "draft"):
            self.assertIn(f'.look[data-look="{look}"]::before', CSS)

    def test_nothing_3d_on_the_rta_tables_or_forms(self):
        block = depth_block()
        for flat in ("[data-day]", ".tl-", ".panel-scroll", ".actable", ".adh-t", ".wkgrid"):
            self.assertNotIn(flat, block, flat)
        self.assertNotRegex(block, r"(?<![-\w])form\b")  # no form element, only the word transform


if __name__ == "__main__":
    unittest.main()
