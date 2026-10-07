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
    resume integer not null default 0
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
    def add_run(self, run_id: str, user_id: int, workbook: str, mode: str, status: str, message: str = "") -> None:
        with self._db() as db:
            db.execute("insert into runs (id, user_id, workbook, mode, status, message, created)"
                       " values (?, ?, ?, ?, ?, ?, ?)", (run_id, user_id, workbook, mode, status, message, time.time()))

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
