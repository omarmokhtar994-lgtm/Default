# © 2026 Omar Mokhtar. All rights reserved.
"""Unit checks of the actual search route and Store transaction.

The isolated route harness is not an HTTP test. Full integration is separate.
"""
import ast
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from webapp.permissions import CATALOGUE, ENDPOINTS, allowed
from webapp.store import Store


def route(name, env):
    source = Path(__file__).parents[1] / "app.py"
    tree = ast.parse(source.read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    code = ast.Module(body=[future, node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), str(source), "exec"), env)
    return env[name]


class SearchPermissions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "data.db")
        with self.store._db() as db:
            db.executemany("insert into role_permissions values (?,?,?)", [("Planner", k, 0) for k in CATALOGUE])

    def get(self, permit):
        with self.store._db() as db:
            db.execute("update role_permissions set allowed=? where role='Planner' and key='rta_view'", (permit,))
        from webapp.clock import EGYPT
        from webapp.versions import shift_span
        from webapp.break_plan import hm
        days = SimpleNamespace(roster=Mock(return_value=[("Associate 001", "08:00 - 17:00")]))
        env = {"request": SimpleNamespace(args={"q": "Associate", "program": "Test", "date": "2026-10-14"}),
               "g": SimpleNamespace(user={"id": 1, "is_admin": False}),
               "app": SimpleNamespace(extensions={"store": self.store}), "allowed": allowed,
               "PERMISSION_ENDPOINTS": ENDPOINTS, "GOTO_PAGES": [("Associate schedules", "week_page", "unit")],
               "GOTO_MAX": 8, "clean_program": lambda x: x, "_date": date.fromisoformat,
               "datetime": datetime, "EGYPT": EGYPT,
               "_access": lambda: SimpleNamespace(can_open=lambda _: True), "unit_keys": lambda _: ["Test"],
               "_unit_name": lambda x: x, "url_for": lambda *args, **kwargs: "/test",
               "jsonify": lambda **kwargs: kwargs, "_days": lambda: days, "shift_span": shift_span, "hm": hm}
        return route("goto", env)(), days

    def test_no_roster_read_when_rta_permission_is_denied(self):
        result, days = self.get(False)
        self.assertEqual(result["items"], [])
        days.roster.assert_not_called()

    def test_allowed_roster_search_still_works(self):
        result, _ = self.get(True)
        self.assertEqual([x["label"] for x in result["items"]], ["Associate 001"])


class AtomicStore(unittest.TestCase):
    def test_failed_batch_rolls_back_prior_rows(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root) / "data.db")
            with self.assertRaises(ValueError):
                with store.transaction():
                    store.set_channel_draft(1, "Sun", {"blocks": {}}, 1)
                    store.add_channel_move(program="Test", shift_date="2026-10-14", associate="Associate 001",
                                           start=600, end_min=660, channel="P", user_id=1)
                    raise ValueError("second change refused")
            self.assertEqual(store.get_channel_draft(1), {})
            self.assertEqual(store.list_channel_moves("Test", ["2026-10-14"]), [])


if __name__ == "__main__":
    unittest.main()
