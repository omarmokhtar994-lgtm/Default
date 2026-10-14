# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AH (owner, 2026-10-15): one rule for an interval's standing, on every page. "Highlighting the dropped
intervals ... based on the target set": below the target red, from the target to 99% amber, 100% or more teal. And
"if target is 90% and I'm now 91% but have only 2-3 mins that's very tight at least 10 mins is sufficient": asked
how to count it, the owner picked "at target, marked tight", so the count of intervals at the target is unchanged and
an amber interval under 10 person-minutes over the target is marked tight."""
import unittest
from datetime import date

from webapp.day import CUSHION, at_target, band, minutes_over, now_panel, safe_level
from webapp.tests.test_notify_daybook import WED, _Tagged


def cell(ticks, required=5.0, t=660):
    """An hour of 5-minute ticks: ``ticks`` people on the floor in each."""
    return {"t": t, "required": required, "slots": list(ticks), "now": round(sum(ticks) / len(ticks), 1),
            "plan": required}


FIVE_OVER = [5] * 7 + [4] * 5     # 275 person-minutes against 270 at 90% of 5: 4.6 on the floor, 92%
TWENTY_OVER = [5] * 10 + [4] * 2  # 290 person-minutes: 4.8 on the floor, 96%


class TheRule(unittest.TestCase):
    def test_bands_follow_the_target(self):
        self.assertEqual(band(5.0, 5.0, 0.9), "ok")
        self.assertEqual(band(4.6, 5.0, 0.9), "warn")
        self.assertEqual(band(4.5, 5.0, 0.9), "warn")  # at the target exactly
        self.assertEqual(band(4.4, 5.0, 0.9), "bad")
        self.assertEqual(band(4.2, 5.0, 0.8), "warn")  # the week's own target, not 90%
        self.assertEqual(band(3.0, 0.0, 0.9), "none")

    def test_a_target_of_100_has_no_amber(self):
        self.assertEqual(band(4.9, 5.0, 1.0), "bad")
        self.assertEqual(band(5.0, 5.0, 1.0), "ok")

    def test_minutes_over_count_person_minutes(self):
        self.assertEqual(CUSHION, 10)
        self.assertAlmostEqual(minutes_over(cell(FIVE_OVER), 0.9), 5.0)
        self.assertAlmostEqual(minutes_over(cell(TWENTY_OVER), 0.9), 20.0)
        self.assertAlmostEqual(minutes_over(cell([4] * 12), 0.9), -30.0)

    def test_safe_level_never_asks_more_than_demand(self):
        self.assertAlmostEqual(safe_level(5.0, 0.9, 60), 4.5 + 10 / 60)
        self.assertAlmostEqual(safe_level(1.0, 0.95, 15), 1.0)  # 0.95 + 10/15 would be over demand
        self.assertAlmostEqual(safe_level(5.0, 1.0, 30), 5.0)

    def test_at_target_marks_tight_and_keeps_the_count(self):
        cells = [cell(FIVE_OVER, t=600), cell(TWENTY_OVER, t=660), cell([5] * 12, t=720), cell([4] * 12, t=780),
                 {"t": 840, "required": 0.0, "slots": [0] * 12, "now": 0.0, "plan": 0.0}]
        found = at_target(cells, 0.9)
        self.assertEqual((found["now"], found["intervals"]), (3, 4))  # 92%, 96% and 100% are at the target
        self.assertEqual(found["tight"], 1)
        self.assertEqual(found["safe"], 2)
        marks = [(c["cls"], c["tight"]) for c in found["cells"]]
        self.assertEqual(marks, [("warn", True), ("warn", False), ("ok", False), ("bad", False), ("none", False)])
        self.assertEqual(found["cells"][0]["over"], 5)


class ThePage(_Tagged):
    def test_every_cell_is_coloured_by_the_weeks_target(self):
        for target in (90, 80):
            self.store.set_interval_target(self.key, "2026-10-11", target, self.omar)
            page = self.days.page(self.key, WED)
            ratio = page["target"]["target"]
            self.assertAlmostEqual(ratio, target / 100)
            for c in page["view"]["cells"]:
                with self.subTest(target=target, t=c["t"]):
                    self.assertEqual(c["cls"], band(c["now"], c["required"], ratio))
                    self.assertEqual(c["tight"], c["cls"] == "warn" and minutes_over(c, ratio) < CUSHION)

    def test_now_panel_speaks_of_the_target(self):
        page = self.days.page(self.key, WED)
        view = page["view"]
        for c in view["cells"]:
            if c["required"] > 0:
                c["cls"] = "bad"
                break
        texts = [a["text"] for a in now_panel(view, c["t"])["attention"]]
        self.assertTrue(any("below the target" in t for t in texts), texts)
        self.assertFalse(any("short by a person or more" in t for t in texts), texts)


if __name__ == "__main__":
    unittest.main()
