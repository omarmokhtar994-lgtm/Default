# © 2026 Omar Mokhtar. All rights reserved.
"""Phase K task 3: a program's history, trends, insights and suggestions.

Weeks are built from run rows (program, week, the compact metrics kept on the
row). The metrics here start from the real Phase I run's figures and vary the
fields a test is about."""
import copy
import json
import unittest
from pathlib import Path

from webapp.analytics import insights, program_weeks, recurring, suggestions, team
from webapp.results import metrics, summarize

REAL = metrics(summarize(Path(__file__).with_name("fixtures") / "real_run"))


def run(run_id, week, created, program="NMG", status="DONE", user="Sara", **changes):
    m = copy.deepcopy(REAL)
    m.update(changes)
    m["outcome"] = status
    return {"id": run_id, "program": program, "week_start": week, "created": created, "started": created,
            "finished": created + 3600, "status": status, "by_name": user, "user_id": 1, "mode": "QUICK",
            "workbook": f"{run_id}.xlsx", "metrics": json.dumps(m)}


class TheWeeks(unittest.TestCase):
    def test_latest_run_counts_for_the_week(self):
        weeks = program_weeks([run("a", "2026-10-04", 100, fully_covered=90),
                               run("b", "2026-10-04", 200, fully_covered=100)])["NMG"]
        self.assertEqual(len(weeks), 1)
        self.assertEqual((weeks[0]["run_id"], weeks[0]["runs_that_week"]), ("b", 2))

    def test_not_approved_runs_do_not_count(self):
        weeks = program_weeks([run("a", "2026-10-04", 100), run("b", "2026-10-04", 200, status="FAILED")])["NMG"]
        self.assertEqual(weeks[0]["run_id"], "a")

    def test_one_week_has_no_deltas(self):
        weeks = program_weeks([run("a", "2026-10-04", 100)])["NMG"]
        self.assertIsNone(weeks[0]["delta"]["associates"])
        texts = [i["text"] for i in insights(weeks)]
        self.assertTrue(any("first week on record" in t.lower() for t in texts), texts)

    def test_untagged_runs_use_the_run_date(self):
        weeks = program_weeks([run("a", "", 1_791_460_800, program="")])  # Thu 2026-10-08 UTC
        self.assertIn("Untagged", weeks)
        self.assertEqual(weeks["Untagged"][0]["week"], "2026-10-04")
        self.assertEqual(weeks["Untagged"][0]["week_basis"], "run date")


class TheInsights(unittest.TestCase):
    def two_weeks(self, **this_week):
        return program_weeks([run("a", "2026-10-04", 100, associates=8, fully_covered=101, before_full=126),
                              run("b", "2026-10-11", 200, **this_week)])["NMG"]

    def test_associates_trend_sentence(self):
        texts = [i["text"] for i in insights(self.two_weeks(associates=7))]
        self.assertTrue(any("Associates: 7" in t and "down 1" in t for t in texts), texts)

    def test_coverage_before_and_after_trend_sentences(self):
        texts = " ".join(i["text"] for i in insights(self.two_weeks()))
        self.assertIn("after breaks: 85%", texts)
        self.assertIn("up 5 points", texts)  # 101/126 = 80% -> 107/126 = 85%
        self.assertIn("before breaks: 99%", texts)
        self.assertIn("breaks cost 14 points", texts)

    def test_main_cause_named(self):
        texts = " ".join(i["text"] for i in insights(self.two_weeks()))
        self.assertIn("Main reason for missing 100%: breaks", texts)

    def test_recurring_short_hours_counted_across_weeks(self):
        weeks = program_weeks([run(str(i), f"2026-09-{6 + 7 * i:02d}", i, short_cells=["Tue 20:30", "Mon 08:00"] if i else ["Tue 20:30"])
                               for i in range(3)])["NMG"]
        rec = recurring(weeks)
        self.assertEqual(rec["weeks"], 3)
        self.assertEqual(rec["top"][0], ("Tue 20:30", 3))
        texts = " ".join(i["text"] for i in insights(weeks))
        self.assertIn("Tue 20:30 was short in 3 of the last 3 weeks", texts)


class TheSuggestions(unittest.TestCase):
    def test_target_suggestion_names_the_90_percent_share(self):
        texts = " ".join(s["text"] for s in suggestions(json.loads(run("a", "2026-10-04", 1)["metrics"])))
        self.assertIn("at 90% it is met in 96%", texts)
        self.assertIn("100% is met in 85%", texts)

    def test_breaks_suggestion_when_breaks_dominate(self):
        texts = " ".join(s["text"] for s in suggestions(REAL))
        self.assertIn("Breaks cause 18 of the 19", texts)

    def test_overstaffing_suggestion_points_from_surplus_to_shortage(self):
        texts = " ".join(s["text"] for s in suggestions(REAL))
        self.assertIn("40.5 staffed hours above need", texts)
        self.assertIn("Sat 00:00", texts)


class TheTeam(unittest.TestCase):
    def test_team_activity_per_user(self):
        rows = team([run("a", "2026-10-04", 1, user="Sara"), run("b", "2026-10-04", 2, user="Sara", status="FAILED"),
                     run("c", "2026-10-04", 3, user="Omar", program="AE")])
        sara = next(r for r in rows if r["name"] == "Sara")
        self.assertEqual((sara["runs"], sara["approved"], sara["not_approved"]), (2, 1, 1))
        self.assertEqual(sara["programs"], ["NMG"])


if __name__ == "__main__":
    unittest.main()
