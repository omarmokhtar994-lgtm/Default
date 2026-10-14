# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, D6: today at a glance on the RTA. The one line of figures (on shift, short and above demand, language
gaps, channel warnings) becomes tiles that also say when: the intervals short and above demand, and which language
is short when."""
import unittest

from webapp.day import day_view, glance
from webapp.tests.test_day import INPUTS, WED, WEEK


def hm(t):
    return f"{t // 60:02d}:{t % 60:02d}"


class TodayAtAGlance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = day_view(WEEK, INPUTS, WED, {}, {})
        cls.tiles = {t["label"]: t for t in glance(cls.view, 12 * 60)}

    def test_the_tiles_in_order(self):
        self.assertEqual([t["label"] for t in glance(self.view, 12 * 60)],
                         ["On shift now", "Short of demand", "Above demand", "Language gaps"])

    def test_on_shift_now(self):
        planned = sum(1 for lane in self.view["lanes"] for s in lane["segments"] if s["start"] <= 720 < s["end"])
        self.assertTrue(self.tiles["On shift now"]["value"].endswith(f" of {planned}"))

    def test_short_and_above_say_which_intervals(self):
        short = [c["t"] for c in self.view["cells"] if c["pm"] is not None and c["pm"] < 0]
        tile = self.tiles["Short of demand"]
        self.assertEqual(tile["value"], f"{len(short)} interval{'s' if len(short) != 1 else ''}")
        if short:
            self.assertIn(hm(short[0]), tile["note"])
            self.assertEqual(tile["level"], "warn")
        over = [c["t"] for c in self.view["cells"] if c["pm"] is not None and c["pm"] > 0]
        self.assertEqual(self.tiles["Above demand"]["value"], f"{len(over)} interval{'s' if len(over) != 1 else ''}")

    def test_language_gaps_name_the_language_and_when(self):
        tile = self.tiles["Language gaps"]
        gaps = [(l["name"], c["t"]) for l in self.view["languages"] for c in l["cells"] if c["cls"] in ("bad", "warn")]
        if gaps:
            self.assertIn(gaps[0][0], tile["note"])
            self.assertIn(hm(gaps[0][1]), tile["note"])
        else:
            self.assertEqual(tile["value"], "None")


class WholeDay(unittest.TestCase):
    def test_every_interval_reads_all_day(self):
        # seen in the browser check: a day above demand everywhere read "00:00 to 00:00"
        from webapp.day import _stretches
        self.assertEqual(_stretches(list(range(0, 1440, 60)), 60), "all day")
        self.assertEqual(_stretches([0, 60], 60), "00:00 to 02:00")


if __name__ == "__main__":
    unittest.main()
