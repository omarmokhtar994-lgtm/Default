# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF defects X1 and X2: the RTA's "<language> on the floor" rows.

X1 (owner's photo, a Monday): language rows showed a red or orange 0 from about 04:00 to 07:00 although nothing
was needed. An overnight Language Setup window belongs to the day it starts, as the engine reads it (audit F-05):
Mon - Fri 16:00 to 07:00 runs from Monday 16:00 to Saturday 07:00, so Monday 00:00 to 07:00 (Sunday night) is not
covered and Saturday's early morning is. The website also read "Mon - Fri" as Monday and Friday only, and
"Weekends" as no day at all; it now reads days as the engine does.

X2: a language with two Language Setup rows (for example one for weekdays, one for weekends) was listed twice.
It is one row, each interval holding the minimum of the window in force then.
"""
import unittest

from openpyxl import Workbook

from webapp.day import _languages, day_view
from webapp.tests.test_day import INPUTS, WEEK

SUN, MON, FRI, SAT = 0, 1, 5, 6


def rule(name, start, end, days, minimum=1, covers=None):
    return {"name": name, "covers": {name.lower()} | set(covers or ()), "start": start * 60, "end": end * 60,
            "minimum": minimum, "days": days}


def rows(day, rules):
    view = day_view(WEEK, {**INPUTS, "languages": rules}, day, {}, {})
    return view["languages"]


def cell(row, hhmm):
    t = int(hhmm[:2]) * 60 + int(hhmm[3:])
    return next(c for c in row["cells"] if c["t"] == t)


class AnOvernightWindowBelongsToTheDayItStarts(unittest.TestCase):
    WEEKDAY_NIGHTS = [rule("Bilingual", 16, 7, [1, 2, 3, 4, 5])]

    def test_monday_early_morning_is_sunday_night(self):
        (row,) = rows(MON, self.WEEKDAY_NIGHTS)
        for hhmm in ("00:00", "04:00", "06:30"):
            self.assertIsNone(cell(row, hhmm)["count"], hhmm)
            self.assertEqual(cell(row, hhmm)["cls"], "none", hhmm)
        self.assertIsNotNone(cell(row, "16:00")["count"])

    def test_saturday_early_morning_is_friday_night(self):
        (row,) = rows(SAT, self.WEEKDAY_NIGHTS)
        self.assertIsNotNone(cell(row, "04:00")["count"])
        self.assertIsNone(cell(row, "16:00")["count"])


class OneRowPerLanguage(unittest.TestCase):
    TWO_ROWS = [rule("Bilingual", 16, 7, [1, 2, 3, 4, 5], minimum=1), rule("Bilingual", 16, 4, [0, 6], minimum=2)]

    def test_a_language_with_two_rows_is_listed_once(self):
        self.assertEqual([r["name"] for r in rows(FRI, self.TWO_ROWS)], ["Bilingual"])

    def test_each_interval_holds_the_minimum_in_force(self):
        (fri,) = rows(FRI, self.TWO_ROWS)
        self.assertEqual(cell(fri, "20:00")["minimum"], 1)
        (sat,) = rows(SAT, self.TWO_ROWS)
        self.assertEqual(cell(sat, "03:00")["minimum"], 1)  # Friday night's window, the weekday row
        self.assertEqual(cell(sat, "20:00")["minimum"], 2)  # Saturday's own window, the weekend row
        (sun,) = rows(SUN, self.TWO_ROWS)
        self.assertEqual(cell(sun, "03:00")["minimum"], 2)  # Saturday night
        self.assertIsNone(cell(sun, "05:00")["count"])  # the weekend window closes at 04:00


class DaysReadLikeTheEngine(unittest.TestCase):
    def parsed(self, days_text):
        wb = Workbook()
        ws = wb.active
        ws.title = "Language Setup"
        ws.append(["Language / Skill Setup"])
        ws.append(["Language", "Coverage Start", "Coverage End", "Can Cover Languages", "Active?", "Coverage Group",
                   "Minimum Per Interval", "Priority / Notes", "Cross-skilled?", "Coverage Days"])
        ws.append(["English", "16:00", "07:00", "", "Yes", "", 1, "", "", days_text])
        (row,) = _languages(wb)
        return sorted(row["days"])

    def test_day_words(self):
        self.assertEqual(self.parsed("Mon - Fri"), [1, 2, 3, 4, 5])
        self.assertEqual(self.parsed("Sun-Thu"), [0, 1, 2, 3, 4])
        self.assertEqual(self.parsed("Weekends"), [0, 6])
        self.assertEqual(self.parsed("Weekdays"), [1, 2, 3, 4, 5])
        self.assertEqual(self.parsed("Sat, Sun"), [0, 6])
        self.assertEqual(self.parsed(""), [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(self.parsed("All"), [0, 1, 2, 3, 4, 5, 6])

    def test_text_that_is_not_a_day_covers_no_day(self):
        # as the engine: a malformed value never means every day (the engine refuses the run)
        self.assertEqual(self.parsed("Sometimes"), [])


if __name__ == "__main__":
    unittest.main()
