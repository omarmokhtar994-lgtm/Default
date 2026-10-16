# © 2026 Omar Mokhtar. All rights reserved.
"""Owner A–D contracts, checked without claiming HTTP or solver integration.

Selected production definitions execute with real stdlib/pure helpers. No solver,
authentication or web framework is replaced or claimed to have run here.
"""
import ast
import copy
import json
import sqlite3
import tempfile
import time
import unittest
from datetime import date
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from webapp.break_plan import check_row, hm
from webapp.channels import CHANNELS, QUARTER, blended_at, in_email_hours, inside
from webapp.day import ABSENT, CALLED_IN, STEP
from webapp.versions import channel_blocks

ROOT = Path(__file__).resolve().parents[1]


def definitions(filename, names, namespace):
    """Execute selected real definitions, without executing unrelated imports."""
    source = ROOT / filename
    tree = ast.parse(source.read_text())
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
            selected.append(node)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    code = ast.Module(body=[future] + selected, type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), str(source), "exec"), namespace)
    return namespace


def pure_channels():
    env = {"QUARTER": QUARTER, "blended_at": blended_at, "in_email_hours": in_email_hours,
           "inside": inside, "check_row": check_row, "hm": hm, "copy": copy,
           "CHANNELS": CHANNELS, "FULL": {"Sun": "Sunday"}, "DAYS": ["Sun"]}
    definitions("channel_plan.py", {"need_at", "in_play", "allowed", "coverage_slots", "email_goals",
                                    "fixed_cover", "score_day", "_weights", "BALANCED"}, env)
    definitions("channel_page.py", {"_runs", "apply_edit", "_at", "coverage"}, env)
    return env


def real_store(path):
    env = {"sqlite3": sqlite3, "json": json, "time": time, "Path": Path,
           "contextmanager": contextmanager, "ContextVar": ContextVar}
    definitions("store.py", {"SCHEMA", "Store"}, env)
    return env["Store"](path)


def day_method(name, env):
    """Isolate the real method; collaborators are explicit unit-test fixtures."""
    source = ROOT / "attendance.py"
    tree = ast.parse(source.read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    node.body = [n for n in node.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    code = ast.Module(body=[future, node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), str(source), "exec"), env)
    return env[name]


class OwnerDecisions(unittest.TestCase):
    def test_plan_forms_have_no_revision_requirement(self):
        # Owner D: restore AM forms; ordinary CSRF protection must remain.
        for filename in ("breaks.html", "channels.html"):
            body = (ROOT / "templates" / filename).read_text()
            self.assertNotIn('name="draft_revision"', body)
            self.assertIn('name="csrf_token"', body)

    def test_routes_have_no_draft_guard(self):
        # Owner D: no new 409 draft lock path on the existing planner routes.
        self.assertNotIn("_draft_guard", (ROOT / "app.py").read_text())

    def test_store_has_no_draft_lock_or_epoch(self):
        # Owner D: preserve drafts themselves, remove only the new feature.
        source = (ROOT / "store.py").read_text()
        self.assertNotIn("draft_epochs", source)
        self.assertNotIn("def edit_draft", source)
        self.assertNotIn("fcntl", source)
        self.assertIn("def transaction", source)  # A still requires atomic apply.

    def test_empty_day_explanation_is_kept(self):
        body = (ROOT / "templates/channels.html").read_text()
        self.assertIn("Nobody works on", body)
        self.assertIn("score.short.items()", body)

    def test_manual_short_block_is_allowed_with_warning(self):
        # Owner C replaces AN's new refusal with the original warning contract.
        env = pure_channels()
        setup = {"step": 15, "need": {"P": {}, "C": {}}, "email_mode": "none", "languages": [],
                 "blended": [], "rules": {"min_block": 60, "max_run": {}, "order": ["P", "C", "E"],
                                           "strict": True, "fair": False}}
        person = {"name": "Associate 001", "start": 600, "end": 780, "breaks": [],
                  "skills": "PC", "counts_for": {"english"}, "label": "10:00 - 13:00"}
        plan = {"blocks": {person["name"]: [(600, 780, "P")]}, "breaks": {person["name"]: []}}
        changed = env["apply_edit"](plan, person, 660, 675, "C", setup, 0)
        self.assertIn([660, 675, "C"], changed["blocks"][person["name"]])
        score = env["score_day"]([person], changed, setup, 0, {})
        self.assertTrue(any("15 minutes" in p for p in score["problems"]))
        self.assertEqual(plan["blocks"][person["name"]], [(600, 780, "P")])

    def test_stretch_cut_by_break_keeps_am_exception(self):
        # Owner C: restore the AM warning rule, including its break exception.
        env = pure_channels()
        setup = {"step": 15, "need": {"P": {}, "C": {}}, "email_mode": "none", "languages": [],
                 "blended": [], "rules": {"min_block": 60, "max_run": {}, "order": ["P", "C", "E"],
                                           "strict": True, "fair": False}}
        person = {"name": "Associate 001", "start": 600, "end": 780, "skills": "PC",
                  "counts_for": {"english"}, "breaks": [("Break", 675, 15)]}
        plan = {"blocks": {person["name"]: [(600, 660, "P"), (660, 675, "C"), (690, 780, "P")]},
                "breaks": {person["name"]: [675]}}
        score = env["score_day"]([person], plan, setup, 0, {"segments": [[15, "Break"]]})
        self.assertFalse(any("minute minimum" in p for p in score["problems"]))

    def test_engine_imports_keep_repo_convention(self):
        for filename, module in (("channel_plan.py", "ortools.sat.python"), ("store.py", "werkzeug.security")):
            tree = ast.parse((ROOT / filename).read_text())
            self.assertTrue(any(isinstance(n, ast.ImportFrom) and n.module == module for n in tree.body))

    def test_batch_rollback_keeps_no_partial_database_rows(self):
        with tempfile.TemporaryDirectory() as work:
            store = real_store(Path(work) / "data.db")
            with self.assertRaisesRegex(ValueError, "later change"):
                with store.transaction():
                    store.add_channel_move(program="Test", shift_date="2026-10-14", associate="Associate 001",
                                           start=600, end_min=660, channel="P", user_id=1)
                    store.set_channel_draft(1, "Sun", {"blocks": {}}, 1)
                    raise ValueError("later change failed")
            self.assertEqual(store.list_channel_moves("Test", ["2026-10-14"]), [])
            self.assertEqual(store.get_channel_draft(1), {})

    def test_draft_writes_keep_am_last_save_behavior(self):
        with tempfile.TemporaryDirectory() as work:
            store = real_store(Path(work) / "data.db")
            store.set_channel_draft(1, "Sun", {"blocks": {"Associate 001": [[600, 660, "P"]]}}, 1)
            store.set_channel_draft(1, "Sun", {"blocks": {"Associate 001": [[600, 660, "C"]]}}, 1)
            self.assertEqual(store.get_channel_draft(1)["Sun"]["blocks"]["Associate 001"][0][2], "C")


class RepairContracts(unittest.TestCase):
    def test_only_today_owned_shifts_move_and_prior_night_languages_count(self):
        # Owner B: check solver INPUTS, not a solver outcome.
        env = pure_channels()
        definitions("channel_plan.py", {"counts_for", "NoPlan"}, env)
        definitions("channel_people.py", {"can_work", "ALL"}, env)
        definitions("attendance.py", {"day_index"}, env)
        solver = Mock(return_value={"blocks": {}, "breaks": {}, "seconds": 0.0})
        env.update(plan_day=solver, channel_blocks=channel_blocks, channel_inside=inside,
                   ABSENT=ABSENT, CALLED_IN=CALLED_IN, STEP=STEP)
        setup = {"step": 15, "need": {"P": {3: {t: 1 for t in range(1440)}}},
                 "email_mode": "none", "languages": [], "blended": [],
                 "rules": {"min_block": 60, "max_run": {}, "order": ["P", "C", "E"],
                           "strict": True, "fair": False}}
        hold = SimpleNamespace(setup=setup, ch={"skills": {}, "language_rows": [], "after": 0})
        lanes, runs = [], {}
        for name, offset, start, end in (("Associate 001", -1, -120, 90),
                                         ("Associate 002", 0, 1200, 1500),
                                         ("Associate 003", 1, 1800, 1920)):
            lanes.append({"name": name, "language": "Arabic", "segments": [
                {"offset": offset, "start": start, "end": end, "status": "Present",
                 "breaks": [], "activities": [], "away": (0, 0)}]})
            runs[name] = [(start, end, "P")]
        page = {"view": {"channels": {"hold": hold, "runs": runs}, "lanes": lanes},
                "week": {"associates": []}}
        book = SimpleNamespace(page=Mock(return_value=page))
        day_method("channel_fix_plan", env)(book, "Test", date(2026, 10, 14), now=0)
        people = solver.call_args.args[0]
        self.assertEqual([p["name"] for p in people], ["Associate 002"])
        self.assertEqual(people[0]["end"], 1500)
        self.assertEqual(solver.call_args.kwargs["before"]["P"][15], 1)
        self.assertEqual(solver.call_args.kwargs["before"]["P:arabic"][15], 1)
        self.assertEqual(solver.call_args.kwargs["horizon"], (15, 1500))

    def apply_fixture(self, failure):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        store = real_store(Path(work.name) / "data.db")
        events = []

        class Book:
            @contextmanager
            def _lock(self, *args):
                events.append("locked")
                try:
                    yield
                finally:
                    events.append("unlocked")

            def _channel_change(self, program, on, name, lo, hi, channel):
                if name == "Associate 002" and failure == "validation":
                    raise ValueError("later validation failed")

            @contextmanager
            def action(self, *args, **kwargs):
                yield SimpleNamespace(label="")

            def channel_move(self, program, on, name, lo, hi, channel, user_id):
                if name == "Associate 002" and failure == "write":
                    raise ValueError("later write failed")
                store.add_channel_move(program=program, shift_date=on.isoformat(), associate=name,
                                       start=lo, end_min=hi, channel=channel, user_id=user_id)

        book = Book()
        book.store = store
        transaction = store.transaction

        @contextmanager
        def ordered_transaction():
            self.assertEqual(events, ["locked"])
            with transaction():
                yield

        store.transaction = ordered_transaction
        return book, store, day_method("apply_channel_fix", {"hm": hm}), events

    def test_invalid_later_change_keeps_no_earlier_write(self):
        book, store, apply, events = self.apply_fixture("validation")
        with self.assertRaisesRegex(ValueError, "later validation"):
            apply(book, "Test", date(2026, 10, 14),
                  [("Associate 001", 615, 660, "P"), ("Associate 002", 615, 660, "P")], 1, now=600)
        self.assertEqual(store.list_channel_moves("Test", ["2026-10-14"]), [])
        self.assertEqual(events, ["locked", "unlocked"])

    def test_later_write_failure_rolls_back_the_batch(self):
        book, store, apply, _ = self.apply_fixture("write")
        with self.assertRaisesRegex(ValueError, "later write"):
            apply(book, "Test", date(2026, 10, 14),
                  [("Associate 001", 615, 660, "P"), ("Associate 002", 615, 660, "P")], 1, now=600)
        self.assertEqual(store.list_channel_moves("Test", ["2026-10-14"]), [])

    def test_today_overnight_tail_keeps_original_shift_date(self):
        book, store, apply, _ = self.apply_fixture(None)
        done = apply(book, "Test", date(2026, 10, 14), [("Associate 001", 1455, 1500, "P")], 1, now=1440)
        self.assertEqual(done, 1)
        rows = store.list_channel_moves("Test", ["2026-10-14"])
        self.assertEqual((rows[0]["start"], rows[0]["end_min"]), (1455, 1500))
        self.assertEqual(store.list_channel_moves("Test", ["2026-10-15"]), [])


if __name__ == "__main__":
    unittest.main()
