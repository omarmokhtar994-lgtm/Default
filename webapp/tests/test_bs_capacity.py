# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BS (owner, 2026-11-18: "then add capacity plan"): people needed against people held, week by week, with the hiring it implies.
Hand-worked numbers; made-up programs."""
import math
import unittest
from datetime import date, timedelta

from webapp import capacity as C
from webapp.programs import ProgramBook
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_runs import sign_in, token

FIRST = date(2026, 11, 22)    # a Sunday


def weeks(hours):
    return [{"week": (FIRST + timedelta(weeks=i)).isoformat(), "hours": h, "low": h * 0.9, "high": h * 1.1} for i, h in enumerate(hours)]


def inputs(**over):
    base = {"head_count": "20", "hours_per_week": "40", "attrition": "", "training_weeks": "", "nesting_weeks": "", "nesting_output": "", "classes": []}
    return C.check_inputs({**base, **over}, FIRST)


class TheInputs(unittest.TestCase):
    def test_blanks_take_the_stated_defaults(self):
        got = inputs()
        self.assertEqual(got, {"head_count": 20.0, "hours_per_week": 40.0, "attrition": 0.0, "training_weeks": 4, "nesting_weeks": 2,
                               "nesting_output": 50.0, "classes": []})

    def test_head_count_is_required_never_invented(self):
        with self.assertRaisesRegex(ValueError, "head count"):
            inputs(head_count="")

    def test_a_bad_value_is_refused_by_name(self):
        for field, bad, words in (("attrition", "120", "Attrition"), ("head_count", "-3", "head count"), ("hours_per_week", "80", "Hours a week"),
                                  ("training_weeks", "2.5", "Training"), ("nesting_output", "5", "output"), ("attrition", "lots", "Attrition")):
            with self.assertRaisesRegex(ValueError, words, msg=f"{field}={bad}"):
                inputs(**{field: bad})

    def test_a_class_is_a_week_start_and_whole_people(self):
        got = inputs(classes=[{"week": "2026-12-06", "people": "8"}])
        self.assertEqual(got["classes"], [{"week": "2026-12-06", "people": 8}])
        for bad in ({"week": "2026-12-07", "people": "8"},           # a Monday
                    {"week": "2026-01-04", "people": "8"},           # more than 26 weeks before the plan starts
                    {"week": "2026-12-06", "people": "0"},
                    {"week": "2026-12-06", "people": "eight"}):
            with self.assertRaisesRegex(ValueError, "class", msg=str(bad)):
                inputs(classes=[bad])
        with self.assertRaisesRegex(ValueError, "20 classes"):
            inputs(classes=[{"week": "2026-12-06", "people": "1"}] * 21)


class ThePlan(unittest.TestCase):
    def test_needed_is_floor_hours_over_the_productive_hours_of_one_person(self):
        out = C.plan(weeks([560.0]), inputs(), shrinkage=0.30)
        row = out["weeks"][0]
        self.assertEqual(row["needed"], 20.0)                 # 560 / (40 x 0.7)
        self.assertEqual((row["needed_low"], row["needed_high"]), (18.0, 22.0))
        self.assertEqual((row["available"], row["gap"]), (20.0, 0.0))
        self.assertIsNone(out["first_short"])
        self.assertIsNone(out["suggestion"])

    def test_attrition_is_typed_per_month_and_taken_weekly(self):
        out = C.plan(weeks([0.0] * 3), inputs(attrition="10"), shrinkage=0.0)
        keep = 0.9 ** (1 / 4.345)
        self.assertEqual([r["available"] for r in out["weeks"]], [20.0, round(20 * keep, 1), round(20 * keep ** 2, 1)])

    def test_a_class_counts_nothing_in_training_part_in_nesting_then_whole(self):
        got = inputs(training_weeks="2", nesting_weeks="1", nesting_output="50", classes=[{"week": FIRST.isoformat(), "people": "10"}])
        out = C.plan(weeks([0.0] * 4), got, shrinkage=0.0)
        self.assertEqual([r["available"] for r in out["weeks"]], [20.0, 20.0, 25.0, 30.0])
        self.assertEqual([r["classes_live"] for r in out["weeks"]], [0.0, 0.0, 5.0, 10.0])

    def test_a_class_started_before_the_plan_is_already_on_its_way(self):
        before = (FIRST - timedelta(weeks=2)).isoformat()
        got = inputs(training_weeks="2", nesting_weeks="0", classes=[{"week": before, "people": "4"}])
        self.assertEqual(C.plan(weeks([0.0]), got, shrinkage=0.0)["weeks"][0]["available"], 24.0)

    def test_the_first_short_week_gets_a_class_that_is_ready_in_time(self):
        hours = [560.0] * 8 + [700.0] * 2           # weeks 8 and 9 need 25 people
        out = C.plan(weeks(hours), inputs(training_weeks="4", nesting_weeks="2"), shrinkage=0.30)
        short = (FIRST + timedelta(weeks=8)).isoformat()
        self.assertEqual(out["first_short"], short)
        self.assertEqual(out["suggestion"], {"start": (FIRST + timedelta(weeks=2)).isoformat(), "people": 5, "ready": short, "late": False})

    def test_a_class_for_a_short_week_too_close_to_reach_starts_now_and_says_it_is_late(self):
        out = C.plan(weeks([700.0]), inputs(training_weeks="4", nesting_weeks="2", attrition="5"), shrinkage=0.30)
        keep = 0.95 ** (1 / 4.345)
        self.assertEqual(out["suggestion"], {"start": FIRST.isoformat(), "people": math.ceil(5 / keep ** 6),
                                             "ready": (FIRST + timedelta(weeks=6)).isoformat(), "late": True})

    def test_no_weeks_gives_an_empty_plan(self):
        self.assertEqual(C.plan([], inputs(), shrinkage=0.3), {"weeks": [], "first_short": None, "suggestion": None})

    def test_shrinkage_of_100_percent_is_refused(self):
        with self.assertRaisesRegex(ValueError, "hrinkage"):
            C.plan(weeks([10.0]), inputs(), shrinkage=1.0)


FORM = {"channel": "Phone", "head_count": "12", "hours_per_week": "40", "attrition": "3", "training_weeks": "4", "nesting_weeks": "2",
        "nesting_output": "50", "class.1.week": "", "class.1.people": ""}


class TheTab(_Volumes):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ProgramBook(cls.store).set_measure(cls.alpha_id, "sl")

    def setUp(self):
        self.history(self.alpha, weeks=10)
        self.addCleanup(lambda: self.store.set_volume_settings(self.alpha, {**(self.store.volume_settings(self.alpha) or {}), "capacity": {}}, None))

    def post(self, who="plan_a", **form):
        client = sign_in(self.app, who, PASSWORD)
        return client.post("/volumes/capacity", data={"program": self.alpha, "csrf_token": token(client), **FORM, **form})

    def test_before_any_figures_the_tab_asks_for_the_head_count(self):
        page = self.page("plan_a", tab="capacity").get_data(as_text=True)
        self.assertIn("<h1>Volumes: capacity plan</h1>", page)
        self.assertIn('name="head_count"', page)
        self.assertIn("Type the people you have now", page)
        self.assertIn("on the newest schedule", page)            # the roster count is a hint beside the box, never taken

    def test_saved_figures_give_a_week_by_week_plan(self):
        self.assertEqual(self.post().status_code, 303)
        got = self.vb.capacity(self.alpha, "Phone", 3)
        self.assertEqual(got["inputs"]["head_count"], 12.0)
        # one row for each week the months ahead reach (10 weeks of history: the trend alone, up to 8 weeks ahead)
        self.assertEqual([w["week"] for w in got["plan"]["weeks"]], [w["week"] for w in self.vb.outlook(self.alpha, "Phone", months=3)["weeks"]])
        self.assertGreater(len(got["plan"]["weeks"]), 4)
        first = got["plan"]["weeks"][0]
        self.assertGreater(first["needed"], 0)
        self.assertEqual(first["available"], 12.0)
        page = self.page("plan_a", tab="capacity", months="3").get_data(as_text=True)
        self.assertIn(first["week"], page)
        self.assertIn("{:.1f}".format(first["needed"]), page)

    def test_needed_hours_are_the_staffing_tabs_people_for_the_same_week(self):
        self.post()
        got = self.vb.capacity(self.alpha, "Phone", 3)
        row = got["plan"]["weeks"][0]
        week = date.fromisoformat(row["week"])
        expected = self.vb.outlook(self.alpha, "Phone", months=3)["weeks"][0]["expected"]
        f = self.vb.forecast(self.alpha, "Phone", week, total=expected)
        hours = sum(sum(day) for day in f["needs"]) * self.step / 60
        shrink = self.vb.settings(self.alpha)["Phone"]["shrinkage"] / 100
        self.assertAlmostEqual(row["needed"], round(hours / (40 * (1 - shrink)), 1), delta=0.15)

    def test_a_bad_figure_is_refused_and_nothing_is_kept(self):
        reply = self.post(attrition="120")
        self.assertEqual(reply.status_code, 200)
        self.assertIn("Attrition is a percent a month from 0 to 30.", reply.get_data(as_text=True))
        self.assertIsNone(self.vb.capacity_inputs(self.alpha, "Phone"))

    def test_a_team_manager_looks_but_cannot_change(self):
        self.assertEqual(self.page("tm_a", tab="capacity").status_code, 200)
        self.assertEqual(self.post(who="tm_a").status_code, 403)
        self.assertIsNone(self.vb.capacity_inputs(self.alpha, "Phone"))

    def test_another_programs_planner_cannot_read_or_write_it(self):
        client = sign_in(self.app, "plan_b", PASSWORD)
        self.assertEqual(client.get("/volumes", query_string={"program": self.alpha, "tab": "capacity"}).status_code, 403)
        self.assertEqual(client.get("/volumes/capacity.xlsx", query_string={"program": self.alpha, "channel": "Phone"}).status_code, 403)

    def test_a_class_is_kept_and_counted(self):
        first = self.vb.capacity(self.alpha, "Phone", 3)["start"]
        self.post(**{"class.1.week": first, "class.1.people": "6", "training_weeks": "0", "nesting_weeks": "0"})
        got = self.vb.capacity(self.alpha, "Phone", 3)
        self.assertEqual(got["inputs"]["classes"], [{"week": first, "people": 6}])
        self.assertEqual(got["plan"]["weeks"][0]["available"], 18.0)

    def test_the_download_holds_the_pages_numbers(self):
        import io
        from openpyxl import load_workbook
        self.post()
        client = sign_in(self.app, "plan_a", PASSWORD)
        reply = client.get("/volumes/capacity.xlsx", query_string={"program": self.alpha, "channel": "Phone", "months": "3"})
        self.assertEqual(reply.status_code, 200)
        ws = load_workbook(io.BytesIO(reply.data)).active
        rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(rows[0][:6], ("Week starting", "Needed", "Needed, low", "Needed, high", "Available", "Gap"))
        plan = self.vb.capacity(self.alpha, "Phone", 3)["plan"]["weeks"]
        self.assertEqual([r[:6] for r in rows[1:1 + len(plan)]],
                         [(w["week"], w["needed"], w["needed_low"], w["needed_high"], w["available"], w["gap"]) for w in plan])

    def test_email_is_counted_as_work_not_erlang(self):
        self.history(self.alpha, weeks=10, per_week=700, channel="Email")
        self.post(channel="Email")
        got = self.vb.capacity(self.alpha, "Email", 3)
        self.assertGreater(got["plan"]["weeks"][0]["needed"], 0)

    def test_without_history_the_tab_says_what_is_missing(self):
        self.post(channel="Chat")
        got = self.vb.capacity(self.alpha, "Chat", 3)
        self.assertIn("There is no Chat history", got["error"])
        self.assertIsNone(got["plan"])


if __name__ == "__main__":
    unittest.main()
