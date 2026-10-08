# © 2026 Omar Mokhtar. All rights reserved.
"""Users and runs, kept in one SQLite file (stdlib only).

Passwords are stored only as salted scrypt hashes (Werkzeug). Five wrong
passwords lock the account for 15 minutes; a successful login clears it.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash

LOCK_AFTER_FAILURES = 5
LOCK_SECONDS = 15 * 60

SCHEMA = """
create table if not exists users (
    id integer primary key,
    username text unique not null,
    display_name text not null,
    password_hash text not null,
    is_admin integer not null default 0,
    active integer not null default 1,
    must_change integer not null default 1,
    failed integer not null default 0,
    locked_until real not null default 0,
    created real not null
);
create table if not exists runs (
    id text primary key,
    user_id integer not null references users(id),
    workbook text not null,
    mode text not null,
    status text not null,
    message text not null default '',
    exit_code integer,
    verdict text not null default '',
    created real not null,
    started real,
    finished real,
    resume integer not null default 0,
    options text not null default '',
    program text not null default '',
    week_start text not null default '',
    metrics text not null default '',
    engine_outcome text not null default ''
);
create table if not exists schedules (
    id integer primary key autoincrement,
    run_id text not null,
    program text not null default '',
    week_start text not null default '',
    kind text not null,
    number integer not null,
    label text not null,
    base_id integer,
    user_id integer,
    created real not null,
    updated real not null,
    in_use integer not null default 0,
    file text not null,
    week text not null default '',
    checks text not null default ''
);
create table if not exists schedule_changes (
    id integer primary key autoincrement,
    schedule_id integer not null,
    user_id integer not null,
    at real not null,
    associate text not null,
    day text not null,
    old text not null,
    new text not null,
    reason text not null default '',
    severity text not null default '',
    problems text not null default ''
);
create table if not exists attendance (
    program text not null,
    shift_date text not null,
    associate text not null,
    status text not null,
    from_min integer,
    to_min integer,
    user_id integer not null,
    at real not null,
    primary key (program, shift_date, associate)
);
create table if not exists actual_breaks (
    program text not null,
    shift_date text not null,
    associate text not null,
    idx integer not null,
    kind text not null,
    start integer not null,
    user_id integer not null,
    at real not null,
    primary key (program, shift_date, associate, idx)
);
create table if not exists day_log (
    id integer primary key autoincrement,
    program text not null,
    shift_date text not null,
    associate text not null,
    what text not null,
    user_id integer not null,
    at real not null
);
"""


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="scrypt")


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(SCHEMA)
            # Databases created before Phase J have no options column: add it.
            columns = {row["name"] for row in db.execute("pragma table_info(runs)")}
            # Databases from earlier versions lack the later columns: add them.
            for name in ("options", "program", "week_start", "metrics", "engine_outcome"):
                if name not in columns:
                    db.execute(f"alter table runs add column {name} text not null default ''")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    # ------------------------------------------------------------------ users
    def add_user(self, username: str, display_name: str, password: str, is_admin: bool = False,
                 must_change: bool = True) -> int:
        username = username.strip().lower()
        if not username or not password:
            raise ValueError("username and password are required")
        with self._db() as db:
            cur = db.execute(
                "insert into users (username, display_name, password_hash, is_admin, must_change, created)"
                " values (?, ?, ?, ?, ?, ?)",
                (username, display_name.strip() or username, hash_password(password), int(is_admin),
                 int(must_change), time.time()))
            return int(cur.lastrowid)

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select * from users where id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute("select * from users order by username")]

    def authenticate(self, username: str, password: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """(user, "ok") or (None, "bad" | "locked" | "disabled")."""
        username = (username or "").strip().lower()
        now = time.time()
        with self._db() as db:
            row = db.execute("select * from users where username = ?", (username,)).fetchone()
            if row is None:
                check_password_hash(hash_password("x"), password or "")  # same cost either way
                return None, "bad"
            if not row["active"]:
                return None, "disabled"
            if row["locked_until"] > now:
                return None, "locked"
            if not check_password_hash(row["password_hash"], password or ""):
                failed = row["failed"] + 1
                locked = now + LOCK_SECONDS if failed >= LOCK_AFTER_FAILURES else 0
                db.execute("update users set failed = ?, locked_until = ? where id = ?",
                           (0 if locked else failed, locked, row["id"]))
                return None, "locked" if locked else "bad"
            db.execute("update users set failed = 0, locked_until = 0 where id = ?", (row["id"],))
            return dict(row), "ok"

    def check_password(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        return self.authenticate(username, password)[0]

    def set_password(self, user_id: int, password: str, must_change: bool = False) -> None:
        with self._db() as db:
            db.execute("update users set password_hash = ?, must_change = ?, failed = 0, locked_until = 0"
                       " where id = ?", (hash_password(password), int(must_change), user_id))

    def set_active(self, user_id: int, active: bool) -> None:
        with self._db() as db:
            db.execute("update users set active = ? where id = ?", (int(active), user_id))

    # ------------------------------------------------------------------- runs
    def add_run(self, run_id: str, user_id: int, workbook: str, mode: str, status: str, message: str = "",
                options: str = "", program: str = "", week_start: str = "") -> None:
        with self._db() as db:
            db.execute("insert into runs (id, user_id, workbook, mode, status, message, created, options,"
                       " program, week_start) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (run_id, user_id, workbook, mode, status, message, time.time(), options, program, week_start))

    # ------------------------------------------------------------- schedule versions
    def add_schedule(self, **fields: Any) -> int:
        fields.setdefault("created", time.time())
        fields.setdefault("updated", fields["created"])
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            return int(db.execute(f"insert into schedules ({names}) values ({marks})", tuple(fields.values())).lastrowid)

    def get_schedule(self, schedule_id: int) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select schedules.*, users.display_name as by_name from schedules left join users"
                             " on users.id = schedules.user_id where schedules.id = ?", (schedule_id,)).fetchone()
        return dict(row) if row else None

    def list_schedules(self, run_id: Optional[str] = None, program: Optional[str] = None,
                       week_start: Optional[str] = None) -> List[Dict[str, Any]]:
        where, args = [], []
        for column, value in (("run_id", run_id), ("program", program), ("week_start", week_start)):
            if value is not None:
                where.append(f"schedules.{column} = ?")
                args.append(value)
        sql = ("select schedules.*, users.display_name as by_name from schedules left join users"
               " on users.id = schedules.user_id" + (" where " + " and ".join(where) if where else "")
               + " order by schedules.number")
        with self._db() as db:
            return [dict(r) for r in db.execute(sql, args)]

    def update_schedule(self, schedule_id: int, **fields: Any) -> None:
        if not fields:
            return
        names = ", ".join(f"{k} = ?" for k in fields)
        with self._db() as db:
            db.execute(f"update schedules set {names} where id = ?", (*fields.values(), schedule_id))

    def delete_schedule(self, schedule_id: int) -> None:
        with self._db() as db:
            db.execute("delete from schedule_changes where schedule_id = ?", (schedule_id,))
            db.execute("delete from schedules where id = ?", (schedule_id,))

    def add_change(self, **fields: Any) -> int:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            return int(db.execute(f"insert into schedule_changes ({names}) values ({marks})",
                                  tuple(fields.values())).lastrowid)

    def list_changes(self, schedule_id: int) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "select schedule_changes.*, users.display_name as by_name from schedule_changes join users"
                " on users.id = schedule_changes.user_id where schedule_id = ? order by schedule_changes.id",
                (schedule_id,))]

    # ------------------------------------------------------------- the day (attendance, actual breaks)
    def set_attendance(self, **fields: Any) -> None:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            db.execute(f"insert or replace into attendance ({names}) values ({marks})", tuple(fields.values()))

    def list_attendance(self, program: str, dates: List[str]) -> List[Dict[str, Any]]:
        marks = ", ".join("?" for _ in dates)
        with self._db() as db:
            return [dict(r) for r in db.execute(
                f"select * from attendance where program = ? and shift_date in ({marks})", (program, *dates))]

    def set_actual_break(self, **fields: Any) -> None:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            db.execute(f"insert or replace into actual_breaks ({names}) values ({marks})", tuple(fields.values()))

    def clear_actual_break(self, program: str, shift_date: str, associate: str, idx: int) -> None:
        with self._db() as db:
            db.execute("delete from actual_breaks where program = ? and shift_date = ? and associate = ? and idx = ?",
                       (program, shift_date, associate, idx))

    def list_actual_breaks(self, program: str, dates: List[str]) -> List[Dict[str, Any]]:
        marks = ", ".join("?" for _ in dates)
        with self._db() as db:
            return [dict(r) for r in db.execute(
                f"select * from actual_breaks where program = ? and shift_date in ({marks})", (program, *dates))]

    def add_day_log(self, **fields: Any) -> None:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            db.execute(f"insert into day_log ({names}) values ({marks})", tuple(fields.values()))

    def list_day_log(self, program: str, shift_date: str) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "select day_log.*, users.display_name as by_name from day_log join users on users.id = day_log.user_id"
                " where program = ? and shift_date = ? order by day_log.id", (program, shift_date))]

    def delete_day_before(self, shift_date: str) -> int:
        """Delete attendance, actual breaks and their log for shift dates before the one given."""
        with self._db() as db:
            return sum(db.execute(f"delete from {table} where shift_date < ?", (shift_date,)).rowcount
                       for table in ("attendance", "actual_breaks", "day_log"))

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        names = ", ".join(f"{k} = ?" for k in fields)
        with self._db() as db:
            db.execute(f"update runs set {names} where id = ?", (*fields.values(), run_id))

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select runs.*, users.display_name as by_name from runs join users"
                             " on users.id = runs.user_id where runs.id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "select runs.*, users.display_name as by_name from runs join users on users.id = runs.user_id"
                " order by runs.created desc limit ?", (limit,))]

    def runs_with_status(self, *statuses: str) -> List[Dict[str, Any]]:
        marks = ", ".join("?" for _ in statuses)
        with self._db() as db:
            return [dict(r) for r in db.execute(
                f"select * from runs where status in ({marks}) order by created", statuses)]
