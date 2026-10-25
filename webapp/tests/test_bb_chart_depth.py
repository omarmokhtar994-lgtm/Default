# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BB (owner, 2026-10-25: "build it ... with 0 risk"): columns and horizontal bars get a lit top and a darker side.
The front face is the bar: its size is exactly what it was, so depth can never change what a value looks like. The faces are
decoration (no tip, no pointer), stay inside the picture, and crowded charts stay flat."""
import re
import unittest
from pathlib import Path

from webapp.charts import BLUE, ORANGE, W, columns, hbars

CSS = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")


def rect(svg, cls="bar"):
    return [dict(re.findall(r'(\w[\w-]*)="([^"]*)"', m)) for m in re.findall(rf'<rect class="{cls}"[^>]*>', svg)]


def faces(svg, kind):
    return [[tuple(float(n) for n in p.split(",")) for p in pts.split()]
            for pts in re.findall(rf'<polygon class="face {kind}"[^>]*points="([^"]*)"', svg)]


class TheColumns(unittest.TestCase):
    labels = ["Mon", "Tue", "Wed", "Thu"]
    values = [3, 6, 9, 12]

    def svg(self, **kw):
        return str(columns(self.labels, self.values, **kw))

    def test_every_column_has_a_top_and_a_side(self):
        svg = self.svg()
        self.assertEqual(len(faces(svg, "face-top")), 4)
        self.assertEqual(len(faces(svg, "face-side")), 4)

    def test_the_front_face_is_still_the_value(self):
        heights = [float(r["height"]) for r in rect(self.svg())]
        for h, v in zip(heights, self.values):
            self.assertAlmostEqual(h / heights[0], v / self.values[0], delta=0.01)

    def test_a_top_face_sits_on_its_column_and_goes_up_and_right(self):
        svg = self.svg()
        for front, top, side in zip(rect(svg), faces(svg, "face-top"), faces(svg, "face-side")):
            x, y, w, h = (float(front[k]) for k in ("x", "y", "width", "height"))
            self.assertEqual(top[0], (x, y)); self.assertEqual(top[3], (x + w, y))
            self.assertTrue(all(py < y and px > x for px, py in top[1:3]))
            self.assertEqual(side[0], (x + w, y)); self.assertEqual(side[3], (x + w, y + h))

    def test_faces_are_painted_before_the_column_tip_and_stay_inside_the_picture(self):
        svg = self.svg()
        for poly in faces(svg, "face-top") + faces(svg, "face-side"):
            for px, py in poly:
                self.assertTrue(0 <= px <= W and py >= 0, (px, py))
        self.assertNotRegex(svg, r'<polygon[^>]*data-tip')

    def test_the_faces_carry_the_series(self):
        self.assertIn('class="face face-top" data-series="orange"', self.svg(colour=ORANGE))

    def test_the_number_sits_above_the_top_face(self):
        svg = self.svg()
        tops = [min(py for _, py in poly) for poly in faces(svg, "face-top")]
        labels = [float(y) for y in re.findall(r'<text class="val" x="[\d.]+" y="([\d.]+)"', svg)]
        for t, label in zip(tops, labels):
            self.assertLess(label, t)

    def test_a_crowded_chart_stays_flat(self):
        many = [str(i) for i in range(40)]
        svg = str(columns(many, list(range(1, 41))))
        self.assertNotIn("<polygon", svg)
        self.assertEqual(len(rect(svg)), 40)

    def test_a_missing_value_draws_no_faces(self):
        svg = str(columns(self.labels, [3, None, 9, 0]))
        self.assertEqual(len(faces(svg, "face-top")), 2)  # none for the gap, none for the zero


class TheHorizontalBars(unittest.TestCase):
    rows = [("Breaks", 18, ORANGE), ("Rules", 6, BLUE), ("Coaching", 2, BLUE)]

    def test_each_bar_has_a_top_and_an_end(self):
        svg = str(hbars(self.rows))
        self.assertEqual(len(faces(svg, "face-top")), 3)
        self.assertEqual(len(faces(svg, "face-side")), 3)

    def test_the_bar_length_is_still_the_value(self):
        widths = [float(r["width"]) for r in rect(str(hbars(self.rows)))]
        self.assertAlmostEqual(widths[0] / widths[1], 3, delta=0.05)

    def test_the_end_face_is_at_the_end_of_the_bar_and_the_number_is_beyond_it(self):
        svg = str(hbars(self.rows))
        for front, end in zip(rect(svg), faces(svg, "face-side")):
            right = float(front["x"]) + float(front["width"])
            self.assertEqual(end[0][0], right)
            self.assertTrue(all(px >= right for px, _ in end))
        numbers = [float(x) for x in re.findall(r'<text class="val" x="([\d.]+)"', svg)]
        for n, end in zip(numbers, faces(svg, "face-side")):
            self.assertGreater(n, max(px for px, _ in end))

    def test_everything_stays_inside_the_picture(self):
        svg = str(hbars([("A long one", 1000, BLUE), ("b", 1, BLUE)]))
        for poly in faces(svg, "face-top") + faces(svg, "face-side"):
            for px, py in poly:
                self.assertTrue(0 <= px <= W and py >= 0, (px, py))


class TheStylesheet(unittest.TestCase):
    def test_faces_do_not_take_the_pointer_and_every_series_has_a_lit_and_a_dark_face(self):
        self.assertRegex(CSS, r"\.chart \.face \{[^}]*pointer-events: none")
        for series in ("blue", "aqua", "orange", "yellow"):
            self.assertRegex(CSS, rf"\.chart polygon\.face-top\[data-series={series}\][^}}]*color-mix")
            self.assertRegex(CSS, rf"\.chart polygon\.face-side\[data-series={series}\][^}}]*color-mix")

    def test_each_face_has_a_plain_colour_first_for_a_browser_without_color_mix(self):
        self.assertRegex(CSS, r"polygon\.face-top\[data-series=blue\][^{]*\{ fill: var\(--c-blue\); fill: color-mix")


class TheFigureStrips(unittest.TestCase):
    def test_the_tile_strips_and_boxes_have_a_raised_edge_without_any_motion(self):
        self.assertRegex(CSS, r"\.tiles, \.ins-tiles[^{]*\{[^}]*box-shadow: [^;]*var\(--edge\)")
        self.assertRegex(CSS, r"\.shr-tile[^{]*\{[^}]*box-shadow")
        edge = CSS[CSS.index("Phase BB"):]
        self.assertNotIn("transition", edge)
        self.assertNotIn("transform", edge)


if __name__ == "__main__":
    unittest.main()
