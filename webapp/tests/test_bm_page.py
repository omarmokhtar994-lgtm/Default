# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BM, task 5 (owner, 2026-11-10: "still simple and easy to use"): the volumes page reads as three numbered steps (data, forecast, staffing)
followed by the months ahead, how we did and the settings. Staffing is a page of its own: the people needed for the week and the files the
schedule reads. The forecast opens with one line that says where it stands. Old addresses keep working. Made-up data."""
import re
import unittest
from datetime import date, timedelta

from webapp.programs import ProgramBook
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_runs import sign_in


def sunday(weeks_ahead):
    today = date.today()
    return today - timedelta(days=(today.weekday() + 1) % 7) + timedelta(weeks=weeks_ahead)


class TheThreeSteps(_Volumes):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ProgramBook(cls.store).set_measure(cls.alpha_id, "sl")      # alpha is planned to a service level; bravo reads its requirement as it is

    def get(self, **query):
        return sign_in(self.app, "plan_a", PASSWORD).get("/volumes", query_string={"program": self.alpha, **query})

    def test_the_tabs_in_their_order(self):
        page = self.get(tab="forecast").get_data(as_text=True)
        nav = re.search(r'<nav class="bp-days" aria-label="Volumes">(.*?)</nav>', page, re.S).group(1)
        self.assertEqual(re.findall(r">([^<]+)</a>", nav), ["1. Data", "2. Forecast", "3. Staffing", "Months ahead", "How we did", "Settings"])

    def test_every_tab_answers_with_the_copyright_and_no_inline_code(self):
        for tab in ("actuals", "forecast", "staffing", "outlook", "how", "settings"):
            reply = self.get(tab=tab)
            self.assertEqual(reply.status_code, 200, tab)
            page = reply.get_data(as_text=True)
            self.assertNotRegex(page, r"<script(?![^>]*\bsrc=)[^>]*>\s*\S", tab)
            self.assertNotRegex(page, r"\sstyle=\"|\son[a-z]+=\"", tab)

    def test_staffing_without_a_forecast_says_the_next_step(self):
        self.history(self.alpha)
        page = self.get(tab="staffing", week=sunday(2).isoformat()).get_data(as_text=True)   # a week nothing is saved for
        self.assertIn("There is no forecast for this week yet", page)
        self.assertIn("tab=forecast", page)
        self.assertNotIn('id="tbl-needs"', page)

    def test_staffing_shows_the_people_needed_and_the_files_for_the_schedule(self):
        self.history(self.alpha)
        self.vb.save_forecast(self.alpha, "Phone", sunday(1), 7000, {}, self.admin_id)
        page = self.get(tab="staffing", week=sunday(1).isoformat()).get_data(as_text=True)
        self.assertIn('id="tbl-needs"', page)
        self.assertIn("Download the requirement tabs", page)
        self.assertIn("Needed on the floor at the peak", page)
        self.assertNotIn('id="tbl-calls"', page)                     # the contacts are the forecast's step
        self.assertIn('aria-label="Interval"', page)
        self.assertIn('name="show_tz"', page)

    def test_a_program_without_a_service_level_is_told_why_there_is_nothing_here(self):
        page = sign_in(self.app, "plan_b", PASSWORD).get("/volumes", query_string={"program": self.bravo, "tab": "staffing"}).get_data(as_text=True)
        self.assertIn("does not use a service level", page)

    def test_the_forecast_opens_with_where_it_stands(self):
        self.history(self.alpha)
        page = self.get(tab="forecast", week=sunday(2).isoformat()).get_data(as_text=True)
        summary = re.search(r'<p[^>]*id="fc-summary"[^>]*>(.*?)</p>', page, re.S).group(1)
        self.assertIn("Type the contacts you expect", summary)
        typed = self.get(tab="forecast", week=sunday(2).isoformat(), total="7000").get_data(as_text=True)
        summary = re.search(r'<p[^>]*id="fc-summary"[^>]*>(.*?)</p>', typed, re.S).group(1)
        self.assertIn("7,000", summary)
        self.assertIn("not saved", summary)

    def test_the_data_tab_with_nothing_held_says_what_to_do_first(self):
        page = sign_in(self.app, "plan_b", PASSWORD).get("/volumes", query_string={"program": self.bravo, "tab": "actuals"}).get_data(as_text=True)
        self.assertIn("Start here", page)


if __name__ == "__main__":
    unittest.main()
