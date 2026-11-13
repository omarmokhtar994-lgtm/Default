# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22, from a screenshot of Shrinkage day over day): the day labels under a line chart ran into one
another ("Mon 12 OctWed 14 Oct"). Labels are thinned to what fits, by their length."""
import re
import unittest

from webapp import charts


def x_labels(svg):
    """(x, text) of the labels under the plot."""
    return [(float(x), t) for x, y, t in re.findall(r'<text class="ax" x="([\d.]+)" y="([\d.]+)" text-anchor="middle">([^<]*)</text>', str(svg))]


class TheLineChartLabels(unittest.TestCase):
    DAYS = [f"{w} {d} Oct" for d, w in zip(range(4, 23), ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat") * 3)]

    def test_long_day_labels_do_not_touch(self):
        svg = charts.lines(self.DAYS, [("Out", charts.ORANGE, [float(i % 7) for i in range(19)])], y_max=10)
        found = sorted(x_labels(svg))
        self.assertGreater(len(found), 3)
        widest = max(len(t) for _, t in found)
        for (a, _), (b, _) in zip(found, found[1:]):
            self.assertGreaterEqual(b - a, widest * 6.8, (a, b))

    def test_short_labels_keep_the_density_they_had(self):
        hours = [f"{h:02d}:00" for h in range(24)]
        svg = charts.lines(hours, [("Out", charts.ORANGE, [1.0] * 24)], y_max=10)
        self.assertEqual(len(x_labels(svg)), 9)  # every third hour, and the last, as before

    def test_the_last_day_is_named_when_there_is_room_for_it(self):
        svg = charts.lines(self.DAYS[:5], [("Out", charts.ORANGE, [1.0] * 5)], y_max=10)
        self.assertEqual(x_labels(svg)[-1][1], self.DAYS[4])


if __name__ == "__main__":
    unittest.main()
