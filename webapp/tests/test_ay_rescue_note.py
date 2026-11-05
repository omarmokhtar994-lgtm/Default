# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23): when a run reaches the runner's time cap but a seed had finished a validated schedule, the runner
keeps the best finished seed (rescue on timeout, tests_staged/test_rc9_2_59_portfolio_rescue.py) and writes
``rescued_after_timeout`` in RUN_LEDGER.json. The run page then says so beside its verdict, so nobody reads a schedule that was
chosen among fewer seeds as an ordinary full run."""
import html
import json
import tempfile
import unittest
from pathlib import Path

from webapp.runs import rescue_note
from webapp.tests.test_runs import FINAL, client_for, make_app, run_id_of, upload, wait


class TheNote(unittest.TestCase):
    def ledger(self, *runs):
        folder = Path(tempfile.mkdtemp())
        (folder / "RUN_LEDGER.json").write_text(json.dumps({"runs": list(runs)}))
        return folder

    def test_a_rescued_portfolio_is_named_with_how_many_seeds_finished(self):
        folder = self.ledger({"scenario_id": "X", "rescued_after_timeout": True, "seeds": 4, "seeds_finished": 3})
        note = rescue_note(folder)
        self.assertIn("time limit", note.lower())
        self.assertIn("3 of 4 seeds", note)

    def test_an_ordinary_run_has_no_note(self):
        self.assertEqual(rescue_note(self.ledger({"scenario_id": "X", "rescued_after_timeout": False, "seeds": 2})), "")
        self.assertEqual(rescue_note(self.ledger({"scenario_id": "X", "seeds": 2})), "")

    def test_no_ledger_or_a_broken_one_has_no_note(self):
        self.assertEqual(rescue_note(Path(tempfile.mkdtemp())), "")
        folder = Path(tempfile.mkdtemp())
        (folder / "RUN_LEDGER.json").write_text("{not json")
        self.assertEqual(rescue_note(folder), "")


class TheRunPage(unittest.TestCase):
    def test_a_rescued_run_keeps_its_verdict_and_says_the_time_limit_was_reached(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="RESCUED_week.xlsx"))
        run = wait(store, run_id, FINAL | {"REVIEW"})
        self.assertEqual((run["status"], run["exit_code"]), ("DONE", 0))
        self.assertIn("Approved", run["message"])
        self.assertIn("3 of 4 seeds", run["message"])
        page = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertIn("time limit", page.lower())

    def test_an_ordinary_run_says_nothing_about_a_time_limit(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="week42.xlsx"))
        run = wait(store, run_id, FINAL | {"REVIEW"})
        self.assertNotIn("time limit", run["message"].lower())


if __name__ == "__main__":
    unittest.main()
