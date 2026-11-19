# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BT (owner, 2026-11-19: "go ahead with both, no off-server copy"): a nightly copy of the website's database kept on the server (14 nights),
and the disk alert run every 15 minutes, both by systemd timers that the installer, the updater and setup_timers.sh put in place."""
import gzip
import importlib.util
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
SPEC = importlib.util.spec_from_file_location("db_backup", DEPLOY / "db_backup.py")
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
NOW = datetime(2026, 11, 19, 1, 30, 0)


def make_db(folder: Path, rows=3) -> Path:
    db = folder / "scheduler.db"
    con = sqlite3.connect(db)
    con.execute("create table users (name text)")
    con.executemany("insert into users values (?)", [(f"Associate {i:02d}",) for i in range(rows)])
    con.commit()
    con.close()
    return db


def rows_in(gz: Path):
    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "copy.db"
        plain.write_bytes(gzip.decompress(gz.read_bytes()))
        con = sqlite3.connect(plain)
        try:
            return [r[0] for r in con.execute("select name from users order by name")]
        finally:
            con.close()


class TheBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data, self.dest = self.tmp / "data", self.tmp / "backups"
        self.data.mkdir()
        self.db = make_db(self.data)

    def test_a_backup_is_a_whole_readable_copy_kept_private(self):
        out = B.backup(self.db, self.dest, NOW)
        self.assertEqual(out.name, "scheduler-2026-11-19-013000.db.gz")
        self.assertEqual(rows_in(out), ["Associate 00", "Associate 01", "Associate 02"])
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.dest.stat().st_mode & 0o777, 0o700)
        self.assertEqual([p.name for p in self.dest.iterdir()], [out.name])        # no half-written file left beside it

    def test_a_write_the_website_has_committed_is_in_the_copy_even_while_it_holds_the_database_open(self):
        con = sqlite3.connect(self.db)
        con.execute("insert into users values ('Associate 09')")
        con.commit()
        try:
            out = B.backup(self.db, self.dest, NOW)
        finally:
            con.close()
        self.assertIn("Associate 09", rows_in(out))

    def test_a_damaged_database_is_refused_and_nothing_is_kept(self):
        bad = self.data / "scheduler.db"
        raw = bytearray(bad.read_bytes())
        raw[100:4096] = b"\xff" * (4096 - 100)
        bad.write_bytes(bytes(raw))
        with self.assertRaises(B.BackupError):
            B.backup(bad, self.dest, NOW)
        self.assertEqual(list(self.dest.glob("*")) if self.dest.exists() else [], [])

    def test_no_database_is_refused_by_name(self):
        with self.assertRaisesRegex(B.BackupError, "not found"):
            B.backup(self.data / "missing.db", self.dest, NOW)

    def test_it_will_not_fill_the_disk(self):
        tight = mock.Mock(free=self.db.stat().st_size, total=10 ** 12, used=0)
        with mock.patch.object(B.shutil, "disk_usage", return_value=tight), self.assertRaisesRegex(B.BackupError, "free"):
            B.backup(self.db, self.dest, NOW)
        self.assertEqual(list(self.dest.glob("*")) if self.dest.exists() else [], [])


class ThePruning(unittest.TestCase):
    def test_it_keeps_the_newest_and_leaves_other_files_alone(self):
        dest = Path(tempfile.mkdtemp())
        names = [f"scheduler-2026-11-{d:02d}-013000.db.gz" for d in range(1, 21)]
        for n in names + ["scheduler-2026-11-19.db", "notes.txt"]:
            (dest / n).write_bytes(b"x")
        gone = B.prune(dest, keep=14)
        self.assertEqual(sorted(p.name for p in gone), names[:6])
        left = sorted(p.name for p in dest.iterdir())
        self.assertEqual(left, sorted(names[6:] + ["scheduler-2026-11-19.db", "notes.txt"]))

    def test_a_keep_below_one_is_refused(self):
        with self.assertRaises(ValueError):
            B.prune(Path(tempfile.mkdtemp()), keep=0)


class TheRun(unittest.TestCase):
    def run_main(self, **env):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "data").mkdir()
        make_db(tmp / "data")
        base = {"SCHEDULER_DATA_DIR": str(tmp / "data"), "BACKUP_DIR": str(tmp / "backups"), "KEEP": "14"}
        base.update(env)
        with mock.patch.dict("os.environ", base):
            return B.main([]), tmp / "backups"

    def test_a_good_night_makes_one_copy_and_exits_0(self):
        code, dest = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(len(list(dest.glob("scheduler-*.db.gz"))), 1)

    def test_a_failed_night_exits_1_and_removes_no_older_copy(self):
        tmp = Path(tempfile.mkdtemp())
        dest = tmp / "backups"
        dest.mkdir(mode=0o700)
        old = [dest / f"scheduler-2026-10-{d:02d}-013000.db.gz" for d in range(1, 21)]
        for p in old:
            p.write_bytes(b"x")
        env = {"SCHEDULER_DATA_DIR": str(tmp / "nothing-here"), "BACKUP_DIR": str(dest), "KEEP": "14"}
        with mock.patch.dict("os.environ", env):
            self.assertEqual(B.main([]), 1)
        self.assertTrue(all(p.exists() for p in old))

    def test_a_bad_keep_setting_stops_with_a_message(self):
        code, _ = self.run_main(KEEP="none")
        self.assertEqual(code, 2)


def setup_dry_run(env_file_exists=False):
    out = Path(tempfile.mkdtemp())
    if env_file_exists:
        (out / "etc" / "scheduler").mkdir(parents=True)
        (out / "etc" / "scheduler" / "disk-alert.env").write_text("ALERT_UNIT=Group A\n")
    env = dict(os.environ, DRY_RUN="1", DRY_ROOT=str(out))
    proc = subprocess.run(["bash", str(DEPLOY / "setup_timers.sh")], capture_output=True, text=True, env=env, timeout=60)
    return proc, out


class TheTimers(unittest.TestCase):
    def test_setup_renders_both_timers_and_enables_them(self):
        proc, out = setup_dry_run()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        units = out / "etc" / "systemd" / "system"
        for name in ("scheduler-backup.service", "scheduler-backup.timer", "disk-alert.service", "disk-alert.timer"):
            text = (units / name).read_text(encoding="utf-8")
            self.assertNotIn("{{", text, name)
        self.assertIn("enable --now scheduler-backup.timer disk-alert.timer", proc.stdout)
        self.assertIn("install -d -o root -g root -m 700 /var/backups/scheduler", proc.stdout)

    def test_the_backup_runs_nightly_as_root_and_writes_only_its_folder(self):
        _, out = setup_dry_run()
        units = out / "etc" / "systemd" / "system"
        timer = (units / "scheduler-backup.timer").read_text(encoding="utf-8")
        self.assertIn("OnCalendar=*-*-* 23:30:00 UTC", timer)                  # 01:30 Egypt time in winter, 02:30 in summer
        self.assertIn("Persistent=true", timer)
        service = (units / "scheduler-backup.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/opt/scheduler/venv/bin/python /opt/scheduler/package/deploy/db_backup.py", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("ReadWritePaths=/var/backups/scheduler", service)
        self.assertNotIn("User=", service)

    def test_the_disk_alert_runs_every_15_minutes_as_the_websites_account(self):
        _, out = setup_dry_run()
        units = out / "etc" / "systemd" / "system"
        self.assertIn("OnCalendar=*:0/15", (units / "disk-alert.timer").read_text(encoding="utf-8"))
        service = (units / "disk-alert.service").read_text(encoding="utf-8")
        for line in ("User=scheduler", "PYTHONPATH=/opt/scheduler/package", "EnvironmentFile=-/etc/scheduler/disk-alert.env",
                     "ExecStart=/opt/scheduler/venv/bin/python /opt/scheduler/package/deploy/disk_alert.py",
                     "ReadWritePaths=/var/lib/scheduler", "ProtectSystem=strict"):
            self.assertIn(line, service)

    def test_the_alert_settings_file_names_a_group_never_a_link_and_is_never_overwritten(self):
        _, out = setup_dry_run()
        made = (out / "etc" / "scheduler" / "disk-alert.env").read_text(encoding="utf-8")
        self.assertIn("# ALERT_UNIT=", made)
        self.assertNotIn("http", made)
        _, kept = setup_dry_run(env_file_exists=True)
        self.assertEqual((kept / "etc" / "scheduler" / "disk-alert.env").read_text(encoding="utf-8"), "ALERT_UNIT=Group A\n")

    def test_the_installer_and_the_updater_set_the_timers_up(self):
        for script in ("install.sh", "update.sh"):
            self.assertIn("deploy/setup_timers.sh", (DEPLOY / script).read_text(encoding="utf-8"), script)

    def test_the_setup_note_the_alert_points_to_exists(self):
        self.assertIn("disk_alert_setup.md", (DEPLOY / "disk_alert.py").read_text(encoding="utf-8"))
        self.assertTrue((DEPLOY / "disk_alert_setup.md").is_file())


if __name__ == "__main__":
    unittest.main()
