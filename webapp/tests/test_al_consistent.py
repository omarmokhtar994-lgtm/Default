# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AL item 3 (owner, 2026-10-15: "why consistent schedule is not being captured now from the engine run zip as
we discussed previously"). The engine writes the steadier week beside its schedule as <id>_MORE_CONSISTENT_CANDIDATE
.xlsx and records the validator's verdict in BUSINESS_OUTCOME.json; the website kept only the schedule after and
before breaks. Now a passed one with no worse coverage is kept as "Tool, more consistent": offered, never set in use
by itself, and added once to finished runs when the website starts (rulings on the recommended side)."""
import html
import json
import shutil
import unittest

from webapp.attendance import pick_version
from webapp.tests import fakes
from webapp.tests.test_runs import B3_INPUT, REPO, client_for, make_app, run_id_of, upload, versioned_run, wait


def finished(app, store, client, name, **fields):
    run_id = run_id_of(upload(client, name=name, data=B3_INPUT.read_bytes(), program="AE/AR B2B",
                              week_start="2026-10-11", **fields))
    wait(store, run_id)
    return run_id


class TheVersion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.book, cls.runs = cls.app.extensions["schedules"], cls.app.extensions["runs"]

    def kinds(self, run_id):
        return [(v["kind"], v["label"], v["in_use"]) for v in self.book.versions(run_id)]

    def test_a_passed_one_is_kept_and_offered(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_CONSISTENT_week.xlsx")
        self.assertEqual(self.kinds(run_id), [("tool_after", "Tool, after breaks", 0),
                                              ("tool_consistent", "Tool, more consistent", 0)])
        kept = next(v for v in self.book.versions(run_id) if v["kind"] == "tool_consistent")
        self.assertEqual(json.loads(kept["checks"])["consistency"]["after"]["start_movement_hours"], 53.0)
        body = html.unescape(self.client.get(f"/runs/{run_id}/schedules").get_data(as_text=True))
        self.assertIn("Tool, more consistent", body)
        self.assertIn("steadier start times: 66 h to 53 h of start-time changes, 60 to 59 different starts", body)

    def test_a_failed_one_is_not_kept(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_CONSISTENTFAIL_week.xlsx")
        self.assertEqual([k for k, _, _ in self.kinds(run_id)], ["tool_after"])

    def test_the_week_still_opens_on_the_schedule_the_engine_picked(self):
        run_id = finished(self.app, self.store, self.client, "VERSIONED_CONSISTENT_week.xlsx")
        versions = self.book.versions(run_id)
        self.assertEqual(pick_version(versions)[0]["kind"], "tool_after")
        shown = next(e for e in self.book.week_list("AE/AR B2B", "2026-10-11") if e["run"]["id"] == run_id)["shown"]
        self.assertEqual(shown["kind"], "tool_after")

    def test_finished_runs_get_it_once_at_start(self):
        run_id = versioned_run(self.app, self.store, self.client, program="AE/AR B2B", week_start="2026-10-11")
        self.assertEqual([k for k, _, _ in self.kinds(run_id)], ["tool_after"])
        case = next(p for p in self.runs.results_dir(run_id).iterdir() if p.is_dir())
        fakes.consistent_candidate(case, case.name)
        self.runs.backfill_schedules()
        self.runs.backfill_schedules()
        self.assertEqual([k for k, _, _ in self.kinds(run_id)], ["tool_after", "tool_consistent"])


if __name__ == "__main__":
    unittest.main()
