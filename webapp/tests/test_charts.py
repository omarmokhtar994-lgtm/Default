# © 2026 Omar Mokhtar. All rights reserved.
"""Phase K task 4: server-side SVG charts (no chart library; the page's CSP
allows scripts from the site only, and these need none to draw)."""
import re
import unittest

from webapp.charts import AQUA, BLUE, ORANGE, columns, heat, hbars, lines


def bars(svg):
    return re.findall(r'<rect class="bar"[^>]*>', str(svg))


class TheCharts(unittest.TestCase):
    def test_columns_have_one_bar_per_week_and_capped_width(self):
        svg = columns(["01 Mar", "08 Mar", "15 Mar"], [7, 6, 8], unit=" people", deltas=[None, -1, 2])
        found = bars(svg)
        self.assertEqual(len(found), 3)
        for bar in found:
            self.assertLessEqual(float(re.search(r'width="([\d.]+)"', bar).group(1)), 24)
        self.assertIn('data-tip="08 Mar: 6 people (down 1)"', str(svg))
        self.assertIn('data-tip="15 Mar: 8 people (up 2)"', str(svg))
        self.assertIn('role="img"', str(svg))

    def test_one_wide_week_is_still_capped(self):
        width = float(re.search(r'width="([\d.]+)"', bars(columns(["01 Mar"], [7]))[0]).group(1))
        self.assertLessEqual(width, 24)

    def test_lines_have_a_legend_for_two_series(self):
        svg = str(lines(["01 Mar", "08 Mar"], [("Before breaks", BLUE, [99, 98]), ("After breaks", AQUA, [85, 90])]))
        self.assertEqual(svg.count('class="line"'), 2)
        self.assertIn('class="legend"', svg)
        self.assertIn("Before breaks", svg)
        self.assertIn('data-tip="08 Mar: After breaks 90%"', svg)

    def test_one_series_needs_no_legend(self):
        self.assertNotIn('class="legend"', str(lines(["01 Mar", "08 Mar"], [("After", AQUA, [85, 90])])))

    def test_a_missing_week_breaks_the_line_without_inventing_a_value(self):
        svg = str(lines(["a", "b", "c"], [("After", AQUA, [85, None, 90])]))
        self.assertEqual(svg.count("<circle"), 2)
        self.assertNotIn('data-tip="b:', svg)

    def test_labels_are_escaped(self):
        for svg in (columns(["<b>&"], [1]), lines(["<b>&"], [("<i>", BLUE, [1])]),
                    hbars([("<b>&", 3, ORANGE)]), heat(["<b>&"], ["00"], [[1]])):
            self.assertNotIn("<b>", str(svg))
            self.assertIn("&lt;b&gt;&amp;", str(svg))

    def test_empty_series_says_no_data(self):
        for svg in (columns([], []), lines([], []), lines(["a"], [("x", BLUE, [None])]), hbars([]),
                    heat([], [], [])):
            self.assertIn("No data yet", str(svg))

    def test_hbars_scale_to_the_largest_value(self):
        svg = str(hbars([("Breaks", 18, ORANGE), ("Rules", 1, BLUE)], unit=" half-hours"))
        widths = [float(w) for w in re.findall(r'<rect class="bar"[^>]*width="([\d.]+)"', svg)]
        self.assertAlmostEqual(widths[0] / widths[1], 18, delta=0.5)
        self.assertIn('data-tip="Breaks: 18 half-hours"', svg)

    def test_heat_cells_carry_their_count(self):
        svg = str(heat(["Tue", "Thu"], ["20", "21"], [[3, 0], [1, None]], tip_unit=" of 4 weeks"))
        self.assertIn('data-tip="Tue 20: 3 of 4 weeks"', svg)
        self.assertEqual(len(re.findall(r'class="cell', svg)), 4)


if __name__ == "__main__":
    unittest.main()
