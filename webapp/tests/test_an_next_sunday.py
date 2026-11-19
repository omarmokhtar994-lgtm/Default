# © 2026 Omar Mokhtar. All rights reserved.
"""Home read the "Next Sunday" finding of a schedule's checks and crashed (a 500) when its first example was a step
between neighbouring quarter hours, which has no "interval". The validator lists cap examples first and steps after
them, so a week with steps but no cap breaks had only steps."""
import json
import unittest

from webapp.results import _finding, _folded
from webapp.tests.test_am_figures import INPUT
from webapp.tests.test_runs import REPO, client_for, make_app, run_id_of, upload, wait

CAP = {"interval": "00:30", "actual": 12, "cap": 10}
STEP = {"from": "01:00", "to": "01:15", "change": 9, "maximum": 6, "previous_raw": 3, "current_raw": 12}


def item(caps, steps):
    return {"type": "NEXT_SUNDAY_BALANCE", "overage_cap_violations": len(caps), "imbalance_violations": len(steps),
            "examples": caps + steps}


class NextSundayFinding(unittest.TestCase):
    def test_steps_only_do_not_raise_and_are_said(self):
        text = _finding(item([], [STEP]), "review")["text"]
        self.assertIn("0 half-hours over the cap", text)
        self.assertIn("1 step between neighbouring quarter hours is larger than allowed", text)
        self.assertIn("01:00 to 01:15", text)

    def test_cap_example_is_still_named(self):
        text = _finding(item([CAP], []), "review")["text"]
        self.assertEqual(text, "Next Sunday (the hours carried into the following week): 1 half-hours over the cap, "
                               "for example 00:30 (12 on the floor, cap 10).")

    def test_cap_example_is_found_after_a_step(self):
        text = _finding({"type": "NEXT_SUNDAY_BALANCE", "overage_cap_violations": 1, "imbalance_violations": 1,
                         "examples": [STEP, CAP]}, "review")["text"]
        self.assertIn("for example 00:30 (12 on the floor, cap 10)", text)

    def test_the_week_page_folds_it(self):
        self.assertEqual(len(_folded([item([], [STEP])], "review")), 1)


class HomeWithSteps(unittest.TestCase):
    """The owner's server: Home answered 500 for a run whose schedule's checks held steps and no cap breaks."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.run_id = run_id_of(upload(cls.client, name="BEFOREONLY_steps.xlsx", data=INPUT.read_bytes(),
                                      program="AE/FR", week_start="2026-10-11"))
        wait(cls.store, cls.run_id)

    def test_home_and_the_run_page_answer(self):
        for version in self.app.extensions["schedules"].versions(self.run_id):
            checks = json.loads(version["checks"] or "{}")
            checks["warnings"] = (checks.get("warnings") or []) + [item([], [STEP])]
            self.store.update_schedule(version["id"], checks=json.dumps(checks))
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get(f"/runs/{self.run_id}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
