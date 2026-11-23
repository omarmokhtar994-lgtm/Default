# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU (owner, 2026-10-21: "operating hours: only the start hour, then calculate till the end of the last shift
automatically; if it cannot be worked out, 24 hours from the start hour"). When the RTA shows the program's operating day
it runs from the operating day's start to the end of the last shift that starts in it; any other start keeps 24 hours."""
import unittest
from unittest import mock

from webapp.attendance import operating_span
from webapp.programs import ProgramBook
from webapp.tests.test_as_requests import WED, _Fixture
from webapp.tests.test_runs import sign_in

TABS = (None, "board", "adherence", "meeting", "cover", "replan", "rescue", "bulk", "requests")


def view(start, ends, interval=30, offsets=None):
    return {"interval": interval, "start": start,
            "lanes": [{"name": f"A{n}", "segments": [{"offset": (offsets or {}).get(n, 0), "end": e}]} for n, e in enumerate(ends)]}


class TheSpan(unittest.TestCase):
    def test_it_runs_to_the_end_of_the_last_shift_rounded_up_to_an_interval(self):
        self.assertEqual(operating_span(view(780, [1080, 1620, 1845])), 1080)   # the last ends 30:45: 17 h 45 rounds up to 18 h
        self.assertEqual(operating_span(view(780, [1040])), 270)                                       # 17:20 rounds up to 17:30

    def test_a_shift_that_began_before_the_window_does_not_count(self):
        self.assertEqual(operating_span(view(780, [1000, 2400], offsets={1: -1})), 240)

    def test_it_is_never_more_than_24_hours(self):
        self.assertEqual(operating_span(view(540, [540 + 1440 + 600])), 1440)

    def test_nothing_to_go_on_is_an_error_so_the_caller_uses_24_hours(self):
        with self.assertRaises(ValueError):
            operating_span(view(780, []))
        with self.assertRaises(ValueError):
            operating_span(view(780, [700]))


class TheOperatingHours(_Fixture):
    START = 9 * 60

    def setUp(self):
        self.days = self.app.extensions["days"]
        self.programs = ProgramBook(self.store)
        self.programs.set_rta_defaults(self.pid, target=None, day_start=self.START, shrinkage=None)
        self.addCleanup(self.programs.set_rta_defaults, self.pid, None, None, None)

    SPAN = 15 * 60

    def fitted_window(self):
        return mock.patch("webapp.attendance.operating_span", return_value=self.SPAN)

    def test_the_window_runs_to_the_end_of_the_last_shift(self):
        full = self.days.window_page(self.key, WED, self.START)["view"]
        self.assertEqual(full["span"], 1440)
        with self.fitted_window():
            fitted = self.days.window_page(self.key, WED, self.START, fit=True)["view"]
        self.assertEqual(fitted["span"], self.SPAN)
        self.assertEqual(len(fitted["cells"]) * fitted["interval"], self.SPAN)
        self.assertEqual(fitted["cells"][0]["t"], self.START)
        self.assertEqual(self.days.window_page(self.key, WED, self.START, fit=True)["view"]["span"], 1440)  # 24 h data: no trim

    def test_nothing_else_changes_inside_the_window(self):
        full = self.days.window_page(self.key, WED, self.START)
        with self.fitted_window():
            fitted = self.days.window_page(self.key, WED, self.START, fit=True)
        n = len(fitted["view"]["cells"])
        self.assertEqual([c["now"] for c in full["view"]["cells"][:n]], [c["now"] for c in fitted["view"]["cells"]])
        self.assertEqual(fitted["target"]["intervals"], sum(1 for c in fitted["view"]["cells"] if c["required"] > 0))

    def test_when_it_cannot_be_worked_out_it_is_24_hours(self):
        with mock.patch("webapp.attendance.operating_span", side_effect=ValueError("no shifts")):
            self.assertEqual(self.days.window_page(self.key, WED, self.START, fit=True)["view"].get("span", 1440), 1440)

    def test_a_day_nobody_starts_a_shift_in_is_24_hours(self):
        self.assertEqual(self.days.window_page(self.key, WED, 3 * 60, fit=False)["view"].get("span", 1440), 1440)

    def test_the_rta_fits_only_when_the_start_picked_is_the_operating_day(self):
        client = sign_in(self.app, "rta1", "Staff-pass-123")
        base = {"program": self.key, "date": WED.isoformat(), "tz": "Africa/Cairo"}
        with self.fitted_window(), mock.patch("webapp.app.operating_span", return_value=self.SPAN):
            page = client.get("/day", query_string={**base, "start": "09:00"}).get_data(as_text=True)
        self.assertIn(f'viewBox="{self.START} 0 {self.SPAN} 30"', page)
        self.assertIn("The operating day: 15 hours from 09:00", page)
        other = client.get("/day", query_string={**base, "start": "10:00"}).get_data(as_text=True)
        self.assertIn('viewBox="600 0 1440 30"', other)
        calendar = client.get("/day", query_string={**base, "start": "00:00"}).get_data(as_text=True)
        self.assertIn('viewBox="0 0 1440 30"', calendar)

    def test_every_tab_renders_on_the_fitted_window(self):
        client = sign_in(self.app, "rta1", "Staff-pass-123")
        for tab in TABS:
            query = {"program": self.key, "date": WED.isoformat(), "tz": "Africa/Cairo", "start": "09:00"}
            if tab:
                query["view"] = tab
            with mock.patch("webapp.app.operating_span", return_value=self.SPAN):
                got = client.get("/day", query_string=query)
            self.assertEqual(got.status_code, 200, tab)
            self.assertNotIn("Traceback", got.get_data(as_text=True), tab)


if __name__ == "__main__":
    unittest.main()
