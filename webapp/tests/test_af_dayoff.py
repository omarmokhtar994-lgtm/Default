# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, F1 and F2: the tool proposes days off to cancel, then overtime for what is left (owner, 2026-10-14).

- A proposal says how many people, the shift and up to 5 people to choose from: "Cancel 2 days off, 16:00 to 01:00;
  possible: X, Y or Z".
- It must cover at least 6 short intervals of the program's own interval, otherwise it is a waste (owner: "at least
  6-8+ intervals"; built with 6).
- Rules are kept first (rest between shifts, days off in the week, days in a row); a proposal that bends one says so,
  the smallest bend first.
- F2: the proposed shift follows the person's shifts the day before and after where it can ("same as Tue").
- What day-off cancellations cannot cover is proposed as overtime per interval.
"""
import unittest

from webapp.day import dayoff_proposals

H = 60
WED = 3
LIBRARY = ["08:00 - 17:00", "16:00 - 01:00", "20:00 - 05:00", "18:00 - 21:00"]


def view_of(step, short, lanes=()):
    """A day where every interval needs 3 and ``short`` ({minute: people}) are missing."""
    cells = [{"t": t, "required": 3.0, "now": 3.0 - short.get(t, 0),
              "pm": -short[t] * step / 60 if short.get(t) else 0.0} for t in range(0, 1440, step)]
    return {"interval": step, "cells": cells, "lanes": list(lanes)}


def short_from(lo, hi, people, step):
    return {t: people for t in range(int(lo * H), int(hi * H), step)}


def person(name, days, language="English"):
    """``days``: Sun to Sat cells."""
    return {"name": name, "slot": "", "language": language, "days": days}


def week(*people):
    return {"associates": list(people), "shifts": LIBRARY, "settings": {"rest_gap_hours": 12}}


OFF = "OFF"
EVE = "16:00 - 01:00"
DAY = "08:00 - 17:00"


class TheProposal(unittest.TestCase):
    def setUp(self):
        self.week = week(person("Associate 03", [OFF, DAY, EVE, OFF, EVE, DAY, OFF]),
                         person("Associate 14", [DAY, DAY, EVE, OFF, OFF, DAY, DAY]),
                         person("Associate 27", [OFF, DAY, DAY, OFF, DAY, DAY, DAY], "French"),
                         person("Associate 40", [DAY, DAY, DAY, DAY, DAY, OFF, OFF]))  # working today

    def test_two_people_on_the_evening_shift(self):
        found = dayoff_proposals(view_of(60, short_from(16, 24, 2, 60)), self.week, WED, 12)
        first = found["proposals"][0]
        self.assertEqual(first["text"], "Cancel 2 days off, 16:00 to 01:00")
        self.assertEqual(first["people"], 2)
        self.assertEqual(first["intervals"], 8)
        self.assertEqual(first["covers"], "16:00 to 00:00")
        names = [c["name"] for c in first["candidates"]]
        self.assertEqual(names[:2], ["Associate 03", "Associate 14"])  # their own evening shift either side
        self.assertNotIn("Associate 40", names)
        self.assertEqual(first["candidates"][0]["note"], "same as Tue and Thu")
        self.assertEqual(found["overtime"], [])

    def test_up_to_five_people(self):
        many = week(*[person(f"Associate {i:02d}", [OFF, DAY, DAY, OFF, DAY, DAY, OFF]) for i in range(1, 9)])
        found = dayoff_proposals(view_of(60, short_from(8, 17, 1, 60)), many, WED, 12)
        self.assertEqual(len(found["proposals"][0]["candidates"]), 5)


class AtLeastSixIntervals(unittest.TestCase):
    def setUp(self):
        self.week = week(person("Associate 03", [OFF, OFF, DAY, OFF, DAY, DAY, DAY]))

    def test_fewer_than_six_short_intervals_is_overtime_instead(self):
        found = dayoff_proposals(view_of(60, short_from(16, 20, 1, 60)), self.week, WED, 12)
        self.assertEqual(found["proposals"], [])
        self.assertEqual([(o["start"], o["end"], o["people"]) for o in found["overtime"]], [(16 * H, 20 * H, 1)])

    def test_the_programs_own_interval_counts(self):
        # 30-minute program: 18:00 to 21:00 is 6 intervals, 18:00 to 20:30 only 5
        self.assertTrue(dayoff_proposals(view_of(30, short_from(18, 21, 1, 30)), self.week, WED, 12)["proposals"])
        self.assertFalse(dayoff_proposals(view_of(30, short_from(18, 20.5, 1, 30)), self.week, WED, 12)["proposals"])

    def test_the_second_person_needs_six_intervals_too(self):
        short = {**short_from(16, 24, 1, 60), **short_from(16, 19, 2, 60)}  # 2 short for only 3 hours
        two = week(person("Associate 03", [OFF, OFF, DAY, OFF, DAY, DAY, DAY]),
                   person("Associate 04", [OFF, OFF, DAY, OFF, DAY, DAY, DAY]))
        found = dayoff_proposals(view_of(60, short), two, WED, 12)
        self.assertEqual(found["proposals"][0]["people"], 1)
        self.assertEqual([(o["start"], o["end"], o["people"]) for o in found["overtime"]], [(16 * H, 19 * H, 1)])


class TheRules(unittest.TestCase):
    def test_kept_first_then_the_smallest_bend_said(self):
        w = week(person("Associate 18", [DAY, DAY, OFF, OFF, "20:00 - 05:00", DAY, DAY]),  # 1 day off left this week
                 person("Associate 33", [OFF, OFF, DAY, OFF, OFF, DAY, DAY]),  # 3 days off left: kept
                 person("Associate 50", [OFF, DAY, DAY, OFF, "06:00 - 15:00", DAY, OFF]))  # short rest before Thu
        found = dayoff_proposals(view_of(60, short_from(20, 24, 1, 60) | short_from(0, 5, 0, 60)), w, WED, 12,
                                 minimum=4)
        first = found["proposals"][0]
        self.assertEqual([c["name"] for c in first["candidates"]], ["Associate 33", "Associate 18", "Associate 50"])
        self.assertEqual(first["candidates"][0]["bends"], [])
        self.assertEqual(first["rules"], "All kept")
        self.assertIn("1 day off left this week (the week has 2)", first["candidates"][1]["bends"])
        self.assertIn("rest before Thu 1 h (rule 12 h)", first["candidates"][2]["bends"])

    def test_days_in_a_row(self):
        w = week(person("Associate 18", [OFF, DAY, DAY, OFF, DAY, DAY, DAY]))
        found = dayoff_proposals(view_of(60, short_from(8, 17, 1, 60)), w, WED, 12)
        self.assertIn("6 days in a row", found["proposals"][0]["candidates"][0]["bends"])
        self.assertEqual(found["proposals"][0]["rules"], "6 days in a row; 1 day off left this week (the week has 2)")


class Today(unittest.TestCase):
    def test_a_shift_that_has_started_is_not_proposed(self):
        w = week(person("Associate 03", [OFF, OFF, DAY, OFF, DAY, DAY, DAY]))
        found = dayoff_proposals(view_of(60, short_from(8, 24, 1, 60)), w, WED, 12, after=9 * H)
        self.assertEqual([p["text"] for p in found["proposals"]], ["Cancel 1 day off, 16:00 to 01:00"])


class OvertimeForTheRest(unittest.TestCase):
    def test_overtime_offers_next_to_the_shifts(self):
        lane = {"name": "Associate 12", "segments": [{"offset": 0, "status": "Present", "start": 8 * H,
                                                      "end": 17 * H, "away": (0, 0), "activities": []}]}
        w = week(person("Associate 12", [OFF, DAY, DAY, DAY, DAY, DAY, OFF]))
        found = dayoff_proposals(view_of(60, short_from(17, 18, 1, 60), [lane]), w, WED, 12)
        self.assertEqual(found["overtime"][0]["text"], "17:00 to 18:00: 1 person")
        self.assertEqual(found["overtime"][0]["offers"][0]["name"], "Associate 12")


class OnThePage(unittest.TestCase):
    """Rescue the day lists the proposals under the break moves, with a button per person to call them in."""

    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def test_the_rescue_tab_has_the_section(self):
        import datetime
        later = datetime.date(2026, 10, 15)  # a day of the week that is not today, so nothing is over yet
        url = f"/day?program={self.key.replace(' ', '+')}&date={later.isoformat()}&view=rescue"
        page = self.admin.get(url).get_data(as_text=True)
        self.assertIn('aria-labelledby="do-h"', page)
        self.assertIn("Days off to cancel, then overtime", page)
        self.assertTrue("Cancel " in page or "Overtime still needed" in page or "Nothing short" in page)


if __name__ == "__main__":
    unittest.main()
