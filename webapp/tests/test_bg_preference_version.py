# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BG (owner, 2026-11-03: "why didn't you fix what you found"; Phase BE left the swapped week out of the website). The engine writes the
week swapped toward Preference shifts beside its schedule as <id>_PREFERENCE_CANDIDATE.xlsx and the runner records the validator's verdict in
BUSINESS_OUTCOME.json. A passed one with no worse coverage is kept as "Tool, closer to preferences", added once to finished runs when the website
starts.

Re-pinned in Phase BP (owner, 2026-11-12, asked "should it go in use by itself": "yes"): when a run finishes and nobody has set a version of that
week in use, its preference version is set in use by itself (TheInUse below), and only when its coverage is the same ("go with 1"). It never replaces a version a person set in use, and versions
added to old runs at start are still only offered."""
import html
import json
import unittest

from webapp.attendance import pick_version
from webapp.tests import fakes
from webapp.tests.test_al_consistent import finished
from webapp.tests.test_runs import REPO, client_for, make_app, versioned_run


class TheVersion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.book, cls.runs = cls.app.extensions["schedules"], cls.app.extensions["runs"]

    def kinds(self, run_id):  # in use or not is TheInUse's subject: this class shares one site, so earlier runs of the week decide it here
        return [(v["kind"], v["label"]) for v in self.book.versions(run_id)]

    def test_a_passed_one_is_kept_and_offered(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCE_week.xlsx")
        self.assertEqual(self.kinds(run_id), [("tool_after", "Tool, after breaks"), ("tool_preference", "Tool, closer to preferences")])
        kept = next(v for v in self.book.versions(run_id) if v["kind"] == "tool_preference")
        self.assertEqual(json.loads(kept["checks"])["preference"], {"swaps": 13, "matched_before": 21, "matched_after": 34})
        body = html.unescape(self.client.get(f"/runs/{run_id}/schedules").get_data(as_text=True))
        self.assertIn("Tool, closer to preferences", body)
        self.assertIn("closer to the Preference shifts: 21 matched before, 34 after (13 same-day swaps)", body)

    def test_one_that_costs_coverage_inside_the_allowance_says_so(self):
        # Phase BP (owner, 2026-11-12: a preference may cost coverage "maybe 1-2% maximum"): the engine may move a person to the asked shift
        run_id = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCECOST_week.xlsx")
        kept = next(v for v in self.book.versions(run_id) if v["kind"] == "tool_preference")
        self.assertEqual(json.loads(kept["checks"])["preference"],
                         {"swaps": 13, "moves": 5, "matched_before": 21, "matched_after": 39, "allowance": 0.02,
                          "coverage_cost": {"after_target": 2.0, "after100": 1.0}})
        body = html.unescape(self.client.get(f"/runs/{run_id}/schedules").get_data(as_text=True))
        self.assertIn("closer to the Preference shifts: 21 matched before, 39 after (13 same-day swaps, 5 moves to the asked shift); "
                      "costs coverage inside the 2% allowance: 2 fewer intervals at the target", body)

    def test_one_that_costs_nothing_says_same_coverage(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCE_week.xlsx")
        body = html.unescape(self.client.get(f"/runs/{run_id}/schedules").get_data(as_text=True))
        self.assertIn("34 after (13 same-day swaps); same coverage", body)

    def test_a_failed_one_is_not_kept(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCEFAIL_week.xlsx")
        self.assertEqual([k for k, _ in self.kinds(run_id)], ["tool_after"])

    def test_finished_runs_get_it_once_at_start(self):
        run_id = versioned_run(self.app, self.store, self.client, program="AE/AR B2B", week_start="2026-10-11")
        self.assertEqual([k for k, _ in self.kinds(run_id)], ["tool_after"])
        case = next(p for p in self.runs.results_dir(run_id).iterdir() if p.is_dir())
        fakes.preference_candidate(case, case.name)
        self.runs.backfill_schedules()
        self.runs.backfill_schedules()
        self.assertEqual([k for k, _ in self.kinds(run_id)], ["tool_after", "tool_preference"])
        self.assertEqual([v["in_use"] for v in self.book.versions(run_id) if v["kind"] == "tool_preference"], [0])  # old runs: offered only


class TheInUse(unittest.TestCase):
    """Phase BP: each test has its own site, so the week starts with nothing in use."""

    def setUp(self):
        self.app, self.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        self.client = client_for(self.app)
        self.book = self.app.extensions["schedules"]

    def in_use(self, run_id):
        return [v["kind"] for v in self.book.versions(run_id) if v["in_use"]]

    def test_a_new_run_puts_its_preference_version_in_use_when_nothing_is(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCE_week.xlsx")
        self.assertEqual(self.in_use(run_id), ["tool_preference"])
        self.assertEqual(pick_version(self.book.versions(run_id))[0]["kind"], "tool_preference")
        said = self.store.list_events(0, 4e9, kinds=["set_in_use"])
        self.assertEqual([(e["subject"], e["detail"]) for e in said],
                         [("Tool, closer to preferences", "by itself: the run's preference version, nothing else was in use")])

    def test_one_that_costs_coverage_stays_offered(self):
        # owner, 2026-11-12 ("go with 1"): by itself only when coverage is the same; a version that costs anything is one click away
        run_id = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCECOST_week.xlsx")
        self.assertEqual(self.in_use(run_id), [])
        self.assertIn("tool_preference", [v["kind"] for v in self.book.versions(run_id)])
        self.assertEqual(self.store.list_events(0, 4e9, kinds=["set_in_use"]), [])

    def test_it_never_replaces_a_version_a_person_set_in_use(self):
        first = finished(self.app, self.store, self.client, "VERSIONED_plain_week.xlsx")
        chosen = next(v for v in self.book.versions(first) if v["kind"] == "tool_after")
        self.book.set_in_use(chosen["id"], self.store.get_run(first)["user_id"])
        second = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCE_week.xlsx")
        self.assertEqual(self.in_use(second), [])
        self.assertEqual(self.in_use(first), ["tool_after"])

    def test_a_run_without_one_leaves_nothing_in_use(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_PREFERENCEFAIL_week.xlsx")
        self.assertEqual(self.in_use(run_id), [])


if __name__ == "__main__":
    unittest.main()
