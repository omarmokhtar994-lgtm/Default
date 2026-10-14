# © 2026 Omar Mokhtar. All rights reserved.
"""Egypt time follows Cairo's clock (owner, 2026-10-14: "yes fix it and update the line").

Egypt changes its clocks: UTC+3 in summer, UTC+2 from midnight on Thursday 29 October 2026 until the last Friday
of April 2027. The website fixed Egypt at UTC+3 in seven modules, so in winter the RTA's "now" line and "today",
Rescue the day's lost-so-far, the day's break posts and every recorded time would run one hour ahead. Every
module now takes Egypt time from one source, the Africa/Cairo zone.
"""

import re
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from webapp import analytics, app, attendance, coach, exports, notify, schedules

WEBAPP = Path(__file__).resolve().parents[1]
MODULES = (app, analytics, attendance, coach, exports, notify, schedules)


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc).timestamp()


WINTER_NOON = utc(2026, 11, 15, 10, 0)    # 12:00 on Sunday 15 November in Cairo (UTC+2)
SUMMER = utc(2026, 7, 15, 10, 0)          # 13:00 on Wednesday 15 July in Cairo (UTC+3)
SAT_LATE = utc(2026, 11, 14, 21, 30)      # 23:30 on Saturday 14 November in Cairo; a fixed UTC+3 says Sunday 00:30


class EgyptClockTest(unittest.TestCase):
    def test_every_module_uses_the_cairo_zone(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                self.assertEqual(getattr(module.EGYPT, "key", None), "Africa/Cairo")

    def test_winter_is_two_hours_ahead_of_utc(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                self.assertEqual(datetime.fromtimestamp(WINTER_NOON, module.EGYPT).strftime("%H:%M"), "12:00")

    def test_summer_is_three_hours_ahead_of_utc(self):
        for module in MODULES:
            with self.subTest(module=module.__name__):
                self.assertEqual(datetime.fromtimestamp(SUMMER, module.EGYPT).strftime("%H:%M"), "13:00")

    def test_the_night_the_clocks_go_back(self):
        # 23:30 happens twice in Cairo on 29 October 2026: once at UTC+3, then again an hour later at UTC+2.
        for epoch in (utc(2026, 10, 29, 20, 30), utc(2026, 10, 29, 21, 30)):
            self.assertEqual(notify._hm(epoch), "23:30")
        self.assertEqual(notify._hm(utc(2026, 10, 29, 22, 0)), "00:00")

    def test_times_shown_and_recorded_in_winter(self):
        self.assertEqual(app._when(WINTER_NOON), "Sun 15 Nov, 12:00")
        self.assertEqual(app._clock(WINTER_NOON), "12:00")
        self.assertEqual(exports._when(WINTER_NOON), "2026-11-15 12:00")
        self.assertEqual(notify._hm(WINTER_NOON), "12:00")

    def test_a_winter_day_starts_at_cairo_midnight(self):
        self.assertEqual(exports._ts(date(2026, 11, 15)), utc(2026, 11, 14, 22, 0))
        self.assertEqual(exports._ts(date(2026, 7, 15)), utc(2026, 7, 14, 21, 0))

    def test_late_saturday_stays_in_its_own_week(self):
        self.assertEqual(analytics._sunday(SAT_LATE), "2026-11-08")

    def test_no_module_fixes_egypt_at_utc_plus_3(self):
        found = []
        for path in sorted(WEBAPP.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for pattern in (r"timedelta\(\s*hours\s*=\s*3\s*\)", r"Egypt time \(UTC\+3\)"):
                found += [f"{path.name}: {m.group(0)}" for m in re.finditer(pattern, text)]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
