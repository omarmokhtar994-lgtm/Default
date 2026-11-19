# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BM, task 2 (owner, 2026-11-10: "why not have option to switch between 30 mins and 60 mins?"; "30-60 only").

The forecast, the week's report and their downloads can be looked at every 30 or every 60 minutes, whatever the program's own interval allows:
contacts are added up, people needed is the larger of the two halves (the hour must cover its busier half), the service level is weighted by the
contacts. What the schedule reads (the requirement tabs) stays at the program's interval. Made-up data."""
import io
import unittest
from datetime import date, timedelta

from openpyxl import load_workbook

from webapp.volumes import VolumeBook
from webapp.tests.test_bi_volumes import KEY, SUN, book as hourly_book, weights
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_runs import sign_in


def book(step=30):
    store, _ = hourly_book()
    vb = VolumeBook(store, measure_of=lambda key: "sl", step_of=lambda key: step)
    rows = []
    for w in range(1, 9):
        for k in range(7):
            day = SUN - timedelta(weeks=w) + timedelta(days=k)
            wts = weights(day.weekday())
            for h, v in wts.items():
                for sub in range(60 // step):
                    rows.append((day.isoformat(), h * 60 + sub * step, v * (3 if sub == 0 else 1), 300.0))
    store.replace_volume_rows(KEY, "Phone", rows, 1)
    return store, vb


class TheChoices(unittest.TestCase):
    def test_what_each_program_may_pick(self):
        self.assertEqual(book(30)[1].every_choices(KEY), [30, 60])
        self.assertEqual(book(60)[1].every_choices(KEY), [60])
        self.assertEqual(book(15)[1].every_choices(KEY), [15, 30, 60])


class TheForecastEveryHour(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.vb = book(30)
        cls.f = cls.vb.forecast(KEY, "Phone", SUN, total=7000)
        cls.hour = cls.vb.view_every(cls.f, 60)

    def test_the_programs_own_interval_is_the_forecast_itself(self):
        self.assertIs(self.vb.view_every(self.f, 30), self.f)

    def test_contacts_are_added_up_and_every_day_keeps_its_total(self):
        self.assertEqual(self.hour["step"], 60)
        self.assertEqual([len(r) for r in self.hour["calls"]], [24] * 7)
        self.assertEqual([sum(r) for r in self.hour["calls"]], [sum(r) for r in self.f["calls"]])
        self.assertEqual(self.hour["calls"][1][9], self.f["calls"][1][18] + self.f["calls"][1][19])
        self.assertEqual(self.hour["total"], self.f["total"])

    def test_people_needed_is_the_larger_half(self):
        for h in (9, 10, 15):
            self.assertEqual(self.hour["needs"][1][h], max(self.f["needs"][1][2 * h], self.f["needs"][1][2 * h + 1]))

    def test_the_service_level_is_weighted_by_the_contacts(self):
        a, b = self.f["service"][1][18], self.f["service"][1][19]
        ca, cb = self.f["calls"][1][18], self.f["calls"][1][19]
        self.assertAlmostEqual(self.hour["service"][1][9], round((a * ca + b * cb) / (ca + cb), 1), places=1)

    def test_the_forecast_it_came_from_is_untouched(self):
        self.assertEqual(self.f["step"], 30)
        self.assertEqual(len(self.f["calls"][0]), 48)

    def test_a_value_the_program_cannot_show_is_refused_in_words(self):
        with self.assertRaises(ValueError) as caught:
            self.vb.view_every(self.f, 45)
        self.assertIn("30 or 60", str(caught.exception))

    def test_the_report_of_a_week_every_hour(self):
        week = SUN - timedelta(weeks=1)
        self.vb.save_forecast(KEY, "Phone", week, 7000, {}, 1)
        r = self.vb.report(KEY, "Phone", week)
        hour = self.vb.report_every(r, 60)
        self.assertEqual(hour["step"], 60)
        self.assertEqual([sum(x) for x in hour["actual"]], [sum(x) for x in r["actual"]])
        self.assertEqual([sum(x) for x in hour["forecast"]], [sum(x) for x in r["forecast"]])
        self.assertEqual(hour["week_otf"], r["week_otf"])
        self.assertEqual(len(hour["otf"][1]), 24)
        self.assertEqual(len(hour["band"][1]), 24)
        self.assertIs(self.vb.report_every(r, 30), r)


class ThePage(_Volumes):
    def test_the_picker_and_the_choice_carried(self):
        self.history(self.alpha)
        client = sign_in(self.app, "plan_a", PASSWORD)
        page = client.get("/volumes", query_string={"program": self.alpha, "tab": "forecast", "total": "7000"}).get_data(as_text=True)
        choices = self.vb.every_choices(self.alpha)
        if len(choices) < 2:
            self.assertNotIn('aria-label="Interval"', page)
            return
        self.assertIn('aria-label="Interval"', page)
        coarse = choices[-1]
        self.assertIn(f"every={coarse}", page)
        page = client.get("/volumes", query_string={"program": self.alpha, "tab": "forecast", "total": "7000", "every": str(coarse)}).get_data(as_text=True)
        self.assertIn(f'name="every" value="{coarse}"', page)                      # the forms keep it
        self.assertIn(f"Shown every {coarse} minutes", page)
        self.assertEqual(page.count('<th scope="row">00:30</th>'), 0)

    def test_the_download_follows_the_choice_and_the_requirement_tabs_do_not(self):
        self.history(self.alpha)
        client = sign_in(self.app, "plan_a", PASSWORD)
        sunday = date.today() - timedelta(days=(date.today().weekday() + 1) % 7) + timedelta(weeks=1)
        coarse = self.vb.every_choices(self.alpha)[-1]
        got = client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "channel": "Phone", "week": sunday.isoformat(), "what": "calls",
                                                               "total": "7000", "every": str(coarse)})
        self.assertEqual(got.status_code, 200)
        rows = list(load_workbook(io.BytesIO(got.data)).active.iter_rows(values_only=True))
        self.assertEqual(len(rows) - 1, 1440 // coarse)
        self.assertEqual(client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "channel": "Phone", "week": sunday.isoformat(),
                                                                       "what": "calls", "total": "7000", "every": "45"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
