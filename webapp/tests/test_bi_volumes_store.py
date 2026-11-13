# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI task 3 (owner, 2026-11-03: "adding actuals as input for volumes received per channel"): the tables behind the volumes pages. A day in an
upload replaces that day for that channel as a whole; settings and forecasts are kept per program key; a rename carries them along; nothing here
clears the RTA's kept days (they are not built from volumes)."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from webapp.store import QUIET_TABLES, Store


def fresh():
    return Store(Path(tempfile.mkdtemp()) / "scheduler.db")


ROWS = [("2026-10-26", 540, 12.0, 300.0), ("2026-10-26", 570, 15.0, 310.0), ("2026-10-27", 540, 9.0, None)]


class TheActuals(unittest.TestCase):
    def setUp(self):
        self.store = fresh()

    def test_rows_are_kept_and_read_back_in_order(self):
        made = self.store.replace_volume_rows("SAKS", "Phone", ROWS, 1)
        self.assertEqual(made, {"rows": 3, "days": 2, "replaced_days": 0})
        got = self.store.volume_rows("SAKS", "Phone", "2026-10-26", "2026-10-27")
        self.assertEqual([(r["day"], r["minute"], r["offered"], r["aht"]) for r in got], ROWS)

    def test_a_day_in_the_file_replaces_that_day_as_a_whole(self):
        self.store.replace_volume_rows("SAKS", "Phone", ROWS, 1)
        made = self.store.replace_volume_rows("SAKS", "Phone", [("2026-10-26", 600, 20.0, 280.0)], 1)
        self.assertEqual(made, {"rows": 1, "days": 1, "replaced_days": 1})
        got = self.store.volume_rows("SAKS", "Phone", "2026-10-26", "2026-10-26")
        self.assertEqual([(r["minute"], r["offered"]) for r in got], [(600, 20.0)])
        self.assertEqual(len(self.store.volume_rows("SAKS", "Phone", "2026-10-27", "2026-10-27")), 1)

    def test_channels_and_programs_are_kept_apart(self):
        self.store.replace_volume_rows("SAKS", "Phone", ROWS, 1)
        self.store.replace_volume_rows("SAKS", "Chat", [("2026-10-26", 540, 3.0, None)], 1)
        self.store.replace_volume_rows("GDI", "Phone", [("2026-10-26", 540, 99.0, None)], 1)
        self.assertEqual(len(self.store.volume_rows("SAKS", "Phone", "2026-10-26", "2026-10-27")), 3)
        self.assertEqual(self.store.volume_rows("SAKS", "Chat", "2026-10-26", "2026-10-26")[0]["offered"], 3.0)
        self.assertEqual(self.store.volume_rows("GDI", "Phone", "2026-10-26", "2026-10-26")[0]["offered"], 99.0)

    def test_the_days_held_say_what_is_there(self):
        self.store.replace_volume_rows("SAKS", "Phone", ROWS, 1)
        self.assertEqual(self.store.volume_days("SAKS", "Phone"), ["2026-10-26", "2026-10-27"])
        self.assertEqual(self.store.volume_days("SAKS", "Chat"), [])

    def test_a_failed_write_changes_nothing(self):
        self.store.replace_volume_rows("SAKS", "Phone", ROWS, 1)
        with self.assertRaises(Exception):
            self.store.replace_volume_rows("SAKS", "Phone", [("2026-10-26", 600, 20.0, 280.0), ("2026-10-26", 600, "x", None)], 1)
        got = self.store.volume_rows("SAKS", "Phone", "2026-10-26", "2026-10-26")
        self.assertEqual(len(got), 2)  # the first upload's day is still whole

    def test_days_can_be_deleted(self):
        self.store.replace_volume_rows("SAKS", "Phone", ROWS, 1)
        self.assertEqual(self.store.delete_volume_days("SAKS", "Phone", "2026-10-26", "2026-10-26"), 2)
        self.assertEqual(self.store.volume_days("SAKS", "Phone"), ["2026-10-27"])

    def test_old_rows_are_purged_and_only_those(self):
        today = date(2026, 11, 3)
        old, keep = (today - timedelta(days=800)).isoformat(), (today - timedelta(days=100)).isoformat()
        self.store.replace_volume_rows("SAKS", "Phone", [(old, 540, 1.0, None), (keep, 540, 2.0, None)], 1)
        self.assertEqual(self.store.purge_volumes_before((today - timedelta(days=730)).isoformat()), 1)
        self.assertEqual(self.store.volume_days("SAKS", "Phone"), [keep])


class TheSettingsAndForecasts(unittest.TestCase):
    def setUp(self):
        self.store = fresh()

    def test_settings_round_trip(self):
        self.assertIsNone(self.store.volume_settings("SAKS"))
        self.store.set_volume_settings("SAKS", {"Phone": {"aht": 300}}, 1)
        self.assertEqual(self.store.volume_settings("SAKS"), {"Phone": {"aht": 300}})
        self.store.set_volume_settings("SAKS", {"Phone": {"aht": 280}}, 1)
        self.assertEqual(self.store.volume_settings("SAKS"), {"Phone": {"aht": 280}})

    def test_a_forecast_is_one_row_per_program_channel_and_week(self):
        self.store.set_volume_forecast("SAKS", "Phone", "2026-11-08", 12600, {"1": 2200}, 1)
        self.store.set_volume_forecast("SAKS", "Phone", "2026-11-08", 12700, {}, 1)
        got = self.store.volume_forecast("SAKS", "Phone", "2026-11-08")
        self.assertEqual((got["total"], got["days"]), (12700, {}))
        self.assertIsNone(self.store.volume_forecast("SAKS", "Chat", "2026-11-08"))
        self.assertEqual([f["channel"] for f in self.store.volume_forecasts("SAKS", "2026-11-08")], ["Phone"])

    def test_a_forecast_can_be_removed(self):
        self.store.set_volume_forecast("SAKS", "Phone", "2026-11-08", 12600, {}, 1)
        self.store.delete_volume_forecast("SAKS", "Phone", "2026-11-08")
        self.assertIsNone(self.store.volume_forecast("SAKS", "Phone", "2026-11-08"))


class TheNameAndTheCache(unittest.TestCase):
    def test_a_rename_carries_everything_along(self):
        store = fresh()
        store.replace_volume_rows("OLD", "Phone", ROWS, 1)
        store.set_volume_settings("OLD", {"Phone": {"aht": 300}}, 1)
        store.set_volume_forecast("OLD", "Phone", "2026-11-08", 100, {}, 1)
        store.rename_program("OLD", "NEW", [])
        self.assertEqual(store.volume_days("NEW", "Phone"), ["2026-10-26", "2026-10-27"])
        self.assertEqual(store.volume_days("OLD", "Phone"), [])
        self.assertEqual(store.volume_settings("NEW"), {"Phone": {"aht": 300}})
        self.assertEqual(store.volume_forecast("NEW", "Phone", "2026-11-08")["total"], 100)

    def test_a_name_that_already_has_volumes_keeps_its_own(self):
        store = fresh()
        store.replace_volume_rows("OLD", "Phone", [("2026-10-26", 540, 1.0, None)], 1)
        store.replace_volume_rows("NEW", "Phone", [("2026-10-26", 540, 7.0, None)], 1)
        store.rename_program("OLD", "NEW", [])
        self.assertEqual(store.volume_rows("NEW", "Phone", "2026-10-26", "2026-10-26")[0]["offered"], 7.0)
        self.assertEqual(store.volume_days("OLD", "Phone"), [])

    def test_volumes_never_clear_the_kept_days(self):
        for table in ("volume_actuals", "volume_forecasts", "volume_settings"):
            self.assertIn(table, QUIET_TABLES)


class TheSavedGrid(unittest.TestCase):
    """What the forecast was when it was saved is kept, so how-did-we-do never moves when history is corrected later."""

    def test_the_grid_and_its_basis_are_kept_with_the_forecast(self):
        store = fresh()
        grid = [[0, 5, 7], [1, 2, 3]] + [[0, 0, 0]] * 5
        store.set_volume_forecast("SAKS", "Phone", "2026-11-08", 18, {}, 1, grid=grid, basis={"weeks": 6, "skip": ["2026-10-04"]})
        got = store.volume_forecast("SAKS", "Phone", "2026-11-08")
        self.assertEqual(got["grid"], grid)
        self.assertEqual(got["basis"], {"weeks": 6, "skip": ["2026-10-04"]})

    def test_an_older_row_without_a_grid_reads_as_none(self):
        store = fresh()
        store.set_volume_forecast("SAKS", "Phone", "2026-11-08", 18, {}, 1)
        got = store.volume_forecast("SAKS", "Phone", "2026-11-08")
        self.assertIsNone(got["grid"])
        self.assertEqual(got["basis"], {})

    def test_a_database_made_before_the_grid_column_is_upgraded(self):
        import sqlite3
        path = Path(tempfile.mkdtemp()) / "old.db"
        db = sqlite3.connect(path)
        db.execute("create table volume_forecasts (program text not null, channel text not null, week_start text not null, total integer not null,"
                   " days text not null default '{}', user_id integer, at real not null, primary key (program, channel, week_start))")
        db.execute("insert into volume_forecasts values ('SAKS', 'Phone', '2026-11-01', 5, '{}', 1, 1.0)")
        db.commit()
        db.close()
        store = Store(path)
        self.assertEqual(store.volume_forecast("SAKS", "Phone", "2026-11-01")["total"], 5)
        store.set_volume_forecast("SAKS", "Phone", "2026-11-08", 9, {}, 1, grid=[[1]] * 7)
        self.assertEqual(store.volume_forecast("SAKS", "Phone", "2026-11-08")["grid"], [[1]] * 7)


class TheDrivers(unittest.TestCase):
    def test_drivers_round_trip_and_follow_a_rename(self):
        store = fresh()
        self.assertIsNone(store.volume_drivers("OLD"))
        store.set_volume_drivers("OLD", {"events": [{"id": "e1"}]}, 1)
        self.assertEqual(store.volume_drivers("OLD"), {"events": [{"id": "e1"}]})
        store.rename_program("OLD", "NEW", [])
        self.assertEqual(store.volume_drivers("NEW"), {"events": [{"id": "e1"}]})
        self.assertIsNone(store.volume_drivers("OLD"))

    def test_the_table_is_quiet(self):
        self.assertIn("volume_drivers", QUIET_TABLES)


if __name__ == "__main__":
    unittest.main()
