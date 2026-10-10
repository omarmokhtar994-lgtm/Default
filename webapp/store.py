# © 2026 Omar Mokhtar. All rights reserved.
"""Users and runs, kept in one SQLite file (stdlib only).

Passwords are stored only as salted scrypt hashes (Werkzeug). Five wrong
passwords lock the account for 15 minutes; a successful login clears it.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import date, timedelta
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
    created real not null,
    is_supervisor integer not null default 0,
    all_programs integer not null default 0
);
create table if not exists programs (
    id integer primary key autoincrement,
    name text unique not null,
    key text unique not null,
    start_day integer not null default 0,
    run_mode text not null default 'QUICK',
    options text not null default '',
    created real not null
);
create table if not exists lobs (
    id integer primary key autoincrement,
    program_id integer not null,
    name text not null,
    key text unique not null,
    created real not null,
    unique (program_id, name)
);
create table if not exists aux_departments (
    id integer primary key autoincrement,
    program_id integer not null,
    name text not null,
    created real not null
);
create table if not exists aux_people (
    id integer primary key autoincrement,
    department_id integer not null,
    name text not null,
    created real not null
);
create table if not exists associate_channels (
    program_id integer not null,
    name text not null collate nocase,
    channels text not null,
    user_id integer,
    updated real not null,
    primary key (program_id, name)
);
create table if not exists channel_moves (
    id integer primary key autoincrement,
    program text not null,
    shift_date text not null,
    associate text not null,
    start integer not null,
    end_min integer not null,
    channel text not null,
    user_id integer,
    at real not null
);
create table if not exists interval_targets (
    program text not null,
    week_start text not null,
    target integer not null,
    user_id integer,
    at real not null,
    primary key (program, week_start)
);
create table if not exists channel_drafts (
    schedule_id integer not null,
    day text not null,
    plan text not null,
    user_id integer,
    updated real not null,
    primary key (schedule_id, day)
);
create table if not exists break_drafts (
    schedule_id integer not null,
    day text not null,
    rows text not null,
    user_id integer,
    updated real not null,
    primary key (schedule_id, day)
);
create table if not exists user_programs (
    user_id integer not null,
    program_id integer not null,
    primary key (user_id, program_id)
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
    billable integer not null default 0,
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
create table if not exists events (
    id integer primary key autoincrement,
    at real not null,
    user_id integer,
    kind text not null,
    program text not null default '',
    week_start text not null default '',
    run_id text not null default '',
    schedule_id integer,
    subject text not null default '',
    detail text not null default ''
);
create index if not exists events_at on events (at);
create table if not exists activities (
    id integer primary key autoincrement,
    program text not null,
    shift_date text not null,
    associate text not null,
    kind text not null,
    start integer not null,
    end_min integer not null,
    billable integer not null default 0,
    note text not null default '',
    user_id integer not null,
    at real not null
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
create table if not exists notify_settings (
    unit text primary key,
    link text not null default '',
    service text not null default '',
    mode text not null default 'off',
    kinds text not null default '',
    hold integer not null default 120,
    morning text not null default '',
    morning_day text not null default 'same',
    site text not null default '',
    saved_by integer,
    saved_at real
);
create table if not exists notify_items (
    id integer primary key autoincrement,
    log_id integer,
    unit text not null,
    shift_date text not null,
    associate text not null,
    kind text not null,
    text text not null,
    ref text not null default '',
    before text not null default '',
    after text not null default '',
    by_name text not null default '',
    at real not null,
    status text not null,
    reason text not null default '',
    post_id integer
);
create index if not exists notify_items_unit on notify_items (unit, shift_date, status);
create table if not exists notify_posts (
    id integer primary key autoincrement,
    unit text not null,
    shift_date text not null,
    what text not null,
    service text not null default '',
    count integer not null default 0,
    status text not null,
    tries integer not null default 0,
    next_at real,
    sent_at real,
    reason text not null default '',
    body text not null default '',
    made_at real not null
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
            # Phase Q: roles and program access. People from before keep every program (nobody is locked out
            # by the update); people added from now on get the programs chosen for them.
            people = {row["name"] for row in db.execute("pragma table_info(users)")}
            if "is_supervisor" not in people:
                db.execute("alter table users add column is_supervisor integer not null default 0")
            if "all_programs" not in people:
                db.execute("alter table users add column all_programs integer not null default 0")
                db.execute("update users set all_programs = 1")
            # Phase AD: a break the RTA cancelled keeps the reason; rows from before were never cancelled.
            have = {row["name"] for row in db.execute("pragma table_info(actual_breaks)")}
            if "cancelled" not in have:
                db.execute("alter table actual_breaks add column cancelled integer not null default 0")
            if "why" not in have:
                db.execute("alter table actual_breaks add column why text not null default ''")
            # Phase T: an aux says who it is with and why; rows from before keep both empty.
            for table in ("attendance", "activities"):
                have = {row["name"] for row in db.execute(f"pragma table_info({table})")}
                for name in ("with_whom", "why", "with_dept"):  # with_dept: Phase U
                    if name not in have:
                        db.execute(f"alter table {table} add column {name} text not null default ''")

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

    PERSON_FIELDS = ("display_name", "is_admin", "is_supervisor", "all_programs")

    def update_user(self, user_id: int, **fields: Any) -> None:
        unknown = set(fields) - set(self.PERSON_FIELDS)
        if unknown:
            raise ValueError(f"Not a person's detail: {', '.join(sorted(unknown))}.")
        if fields:
            names = ", ".join(f"{k} = ?" for k in fields)
            with self._db() as db:
                db.execute(f"update users set {names} where id = ?", (*fields.values(), user_id))

    def set_user_programs(self, user_id: int, program_ids: List[int]) -> None:
        with self._db() as db:
            db.execute("delete from user_programs where user_id = ?", (user_id,))
            db.executemany("insert into user_programs (user_id, program_id) values (?, ?)",
                           [(user_id, pid) for pid in sorted(set(program_ids))])

    def user_program_ids(self, user_id: int) -> List[int]:
        with self._db() as db:
            return [r[0] for r in db.execute("select program_id from user_programs where user_id = ?"
                                             " order by program_id", (user_id,))]

    # ------------------------------------------------------------- programs and LOBs (the registry)
    def add_program_row(self, name: str, key: str) -> int:
        with self._db() as db:
            return int(db.execute("insert into programs (name, key, created) values (?, ?, ?)",
                                  (name, key, time.time())).lastrowid)

    def list_programs(self) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute("select * from programs order by name collate nocase")]

    def update_program(self, program_id: int, **fields: Any) -> None:
        unknown = set(fields) - {"name", "start_day", "run_mode", "options"}
        if unknown:
            raise ValueError(f"Not a program detail: {', '.join(sorted(unknown))}.")
        if fields:
            names = ", ".join(f"{k} = ?" for k in fields)
            with self._db() as db:
                db.execute(f"update programs set {names} where id = ?", (*fields.values(), program_id))

    def add_lob_row(self, program_id: int, name: str, key: str) -> int:
        with self._db() as db:
            return int(db.execute("insert into lobs (program_id, name, key, created) values (?, ?, ?, ?)",
                                  (program_id, name, key, time.time())).lastrowid)

    def list_lobs(self) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute("select * from lobs order by name collate nocase")]

    def rename_lob(self, lob_id: int, name: str) -> None:
        with self._db() as db:
            db.execute("update lobs set name = ? where id = ?", (name, lob_id))

    def fold_program(self, program_id: int, into: int) -> None:
        """A program row without LOBs folded into another program: its people get that program."""
        with self._db() as db:
            db.execute("insert or ignore into user_programs (user_id, program_id) select user_id, ?"
                       " from user_programs where program_id = ?", (into, program_id))
            db.execute("delete from user_programs where program_id = ?", (program_id,))
            self._fold_aux(db, program_id, into)
            db.execute("delete from programs where id = ?", (program_id,))

    @staticmethod
    def _fold_aux(db: sqlite3.Connection, program_id: int, into: int) -> None:
        """Its departments and people move into the other program; a department both have is merged."""
        theirs = {r["name"].casefold(): r["id"] for r in db.execute(
            "select id, name from aux_departments where program_id = ?", (into,))}
        for dept in db.execute("select id, name from aux_departments where program_id = ?", (program_id,)).fetchall():
            target = theirs.get(dept["name"].casefold())
            if target is None:
                db.execute("update aux_departments set program_id = ? where id = ?", (into, dept["id"]))
                continue
            have = {r["name"].casefold() for r in db.execute("select name from aux_people where department_id = ?",
                                                             (target,))}
            for person in db.execute("select id, name from aux_people where department_id = ?",
                                     (dept["id"],)).fetchall():
                if person["name"].casefold() in have:
                    db.execute("delete from aux_people where id = ?", (person["id"],))
                else:
                    db.execute("update aux_people set department_id = ? where id = ?", (target, person["id"]))
            db.execute("delete from aux_departments where id = ?", (dept["id"],))

    # ------------------------------------------------------------- a week's breaks being planned (Phase R)
    def set_break_draft(self, schedule_id: int, day: str, rows: Dict[str, List[Optional[int]]], user_id: int) -> None:
        with self._db() as db:
            db.execute("insert into break_drafts (schedule_id, day, rows, user_id, updated) values (?, ?, ?, ?, ?)"
                       " on conflict (schedule_id, day) do update set rows = excluded.rows,"
                       " user_id = excluded.user_id, updated = excluded.updated",
                       (schedule_id, day, json.dumps(rows), user_id, time.time()))

    def get_break_draft(self, schedule_id: int) -> Dict[str, Dict[str, List[Optional[int]]]]:
        with self._db() as db:
            return {r["day"]: json.loads(r["rows"]) for r in db.execute(
                "select day, rows from break_drafts where schedule_id = ? order by day", (schedule_id,))}

    def clear_break_draft(self, schedule_id: int) -> None:
        with self._db() as db:
            db.execute("delete from break_drafts where schedule_id = ?", (schedule_id,))

    # ------------------------------------------------------------- channels changed on the day (Phase V)
    def add_channel_move(self, **fields: Any) -> int:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            return int(db.execute(f"insert into channel_moves ({names}) values ({marks})",
                                  tuple(fields.values())).lastrowid)

    def get_channel_move(self, move_id: int) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select * from channel_moves where id = ?", (move_id,)).fetchone()
        return dict(row) if row else None

    def delete_channel_move(self, move_id: int) -> None:
        with self._db() as db:
            db.execute("delete from channel_moves where id = ?", (move_id,))

    def list_channel_moves(self, program: str, dates: List[str]) -> List[Dict[str, Any]]:
        marks = ", ".join("?" for _ in dates)
        with self._db() as db:
            return [dict(r) for r in db.execute(
                f"select * from channel_moves where program = ? and shift_date in ({marks}) order by start, id",
                (program, *dates))]

    def channel_moves_between(self, start: str, end: str, program: Optional[str] = None,
                              user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._between("select channel_moves.*, coalesce(users.display_name, '') as by_name from channel_moves"
                             " left join users on users.id = channel_moves.user_id where shift_date between ? and ?",
                             [start, end], program, user_id, "channel_moves", "shift_date, program, associate, start")

    # ------------------------------------------------------------- a week's channels being planned (Phase V)
    def set_channel_draft(self, schedule_id: int, day: str, plan: Dict[str, Any], user_id: int) -> None:
        with self._db() as db:
            db.execute("insert into channel_drafts (schedule_id, day, plan, user_id, updated) values (?, ?, ?, ?, ?)"
                       " on conflict (schedule_id, day) do update set plan = excluded.plan,"
                       " user_id = excluded.user_id, updated = excluded.updated",
                       (schedule_id, day, json.dumps(plan), user_id, time.time()))

    def get_channel_draft(self, schedule_id: int) -> Dict[str, Dict[str, Any]]:
        with self._db() as db:
            return {r["day"]: json.loads(r["plan"]) for r in db.execute(
                "select day, plan from channel_drafts where schedule_id = ? order by day", (schedule_id,))}

    def clear_channel_draft(self, schedule_id: int) -> None:
        with self._db() as db:
            db.execute("delete from channel_drafts where schedule_id = ?", (schedule_id,))

    # ------------------------------------------------------------- who can work which channel (Phase V)
    def list_associate_channels(self, program_id: int) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute("select * from associate_channels where program_id = ? order by name",
                                                (program_id,))]

    def set_associate_channels(self, program_id: int, rows: Dict[str, Optional[str]], user_id: int) -> None:
        """name -> letters, or None to take the person off the list; in one transaction."""
        now = time.time()
        with self._db() as db:
            for name, letters in rows.items():
                if letters is None:
                    db.execute("delete from associate_channels where program_id = ? and name = ?", (program_id, name))
                else:
                    db.execute("insert into associate_channels (program_id, name, channels, user_id, updated) values"
                               " (?, ?, ?, ?, ?) on conflict (program_id, name) do update set name = excluded.name,"
                               " channels = excluded.channels, user_id = excluded.user_id, updated = excluded.updated",
                               (program_id, name, letters, user_id, now))

    # ------------------------------------------------------------- who an aux is with (Phase U)
    def list_aux_departments(self, program_id: int) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute("select * from aux_departments where program_id = ? order by name "
                                                "collate nocase", (program_id,))]

    def list_aux_people(self, program_id: int) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "select aux_people.*, aux_departments.program_id from aux_people join aux_departments on "
                "aux_departments.id = aux_people.department_id where aux_departments.program_id = ? "
                "order by aux_people.name collate nocase", (program_id,))]

    def add_aux_entries(self, program_id: int, entries: List[Tuple[str, str]]) -> None:
        """(department, name or "") pairs, in one transaction: a department is made when it is new."""
        now = time.time()
        with self._db() as db:
            for dept, name in entries:
                row = db.execute("select id from aux_departments where program_id = ? and name = ?",
                                 (program_id, dept)).fetchone()
                dept_id = row["id"] if row else db.execute(
                    "insert into aux_departments (program_id, name, created) values (?, ?, ?)",
                    (program_id, dept, now)).lastrowid
                if name:
                    db.execute("insert into aux_people (department_id, name, created) values (?, ?, ?)",
                               (dept_id, name, now))

    def get_aux_department(self, department_id: int) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select * from aux_departments where id = ?", (department_id,)).fetchone()
        return dict(row) if row else None

    def get_aux_person(self, person_id: int) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select aux_people.*, aux_departments.program_id, aux_departments.name as department "
                             "from aux_people join aux_departments on aux_departments.id = aux_people.department_id "
                             "where aux_people.id = ?", (person_id,)).fetchone()
        return dict(row) if row else None

    def delete_aux_person(self, person_id: int) -> None:
        with self._db() as db:
            db.execute("delete from aux_people where id = ?", (person_id,))

    def delete_aux_department(self, department_id: int) -> None:
        with self._db() as db:
            db.execute("delete from aux_people where department_id = ?", (department_id,))
            db.execute("delete from aux_departments where id = ?", (department_id,))

    def delete_program_row(self, program_id: int) -> None:
        """A program row, who was assigned to it and its departments and people (its LOBs are deleted first, by
        the caller)."""
        with self._db() as db:
            db.execute("delete from user_programs where program_id = ?", (program_id,))
            db.execute("delete from aux_people where department_id in (select id from aux_departments where "
                       "program_id = ?)", (program_id,))
            db.execute("delete from aux_departments where program_id = ?", (program_id,))
            db.execute("delete from associate_channels where program_id = ?", (program_id,))
            db.execute("delete from programs where id = ?", (program_id,))

    def delete_lob_row(self, lob_id: int) -> None:
        with self._db() as db:
            db.execute("delete from lobs where id = ?", (lob_id,))

    def key_usage(self, key: str) -> Dict[str, int]:
        """What is stored under a program key: runs, schedule versions and day records per table."""
        with self._db() as db:
            found = {name: db.execute(f"select count(*) from {table} where program = ?", (key,)).fetchone()[0]
                     for name, table in (("runs", "runs"), ("versions", "schedules"), *self.DAY_TABLES)}
        return found

    def latest_weeks(self) -> Dict[str, str]:
        """Each program key's latest schedule start date (from its kept versions)."""
        with self._db() as db:
            return {r[0]: r[1] for r in db.execute("select program, max(week_start) from schedules"
                                                   " where program != '' and week_start != '' group by program")}

    def run_programs(self) -> List[str]:
        """Every program key a run was made under."""
        with self._db() as db:
            return [r[0] for r in db.execute("select distinct program from runs where program != ''"
                                             " order by program")]

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

    def set_interval_target(self, program: str, week_start: str, target: int, user_id: Optional[int]) -> None:
        """The interval target (a whole percent) for a program and week (Phase W)."""
        with self._db() as db:
            db.execute("insert or replace into interval_targets (program, week_start, target, user_id, at)"
                       " values (?, ?, ?, ?, ?)", (program, week_start, int(target), user_id, time.time()))

    def get_interval_target(self, program: str, week_start: str) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select interval_targets.*, users.display_name as by_name from interval_targets"
                             " left join users on users.id = interval_targets.user_id"
                             " where program = ? and week_start = ?", (program, week_start)).fetchone()
        return dict(row) if row else None

    def in_use_runs(self) -> Dict[Tuple[str, str], str]:
        """(program, week start) -> the run whose version is in use that week (Phase W)."""
        with self._db() as db:
            return {(r[0], r[1]): r[2] for r in db.execute(
                "select program, week_start, run_id from schedules where in_use = 1 and program != ''"
                " and week_start != ''")}

    def schedule_weeks(self) -> List[Tuple[str, str]]:
        """Every (program, week start) that has a kept schedule (Phase W: the Week page lists uploaded ones too)."""
        with self._db() as db:
            return [(r[0], r[1]) for r in db.execute(
                "select distinct program, week_start from schedules where program != '' and week_start != ''")]

    def list_schedules(self, run_id: Optional[str] = None, program: Optional[str] = None,
                       week_start: Optional[str] = None, covering: Optional[str] = None) -> List[Dict[str, Any]]:
        """Versions by run, program and start date; ``covering`` (a YYYY-MM-DD date) keeps those whose
        seven days hold that date."""
        where, args = [], []
        for column, value in (("run_id", run_id), ("program", program), ("week_start", week_start)):
            if value is not None:
                where.append(f"schedules.{column} = ?")
                args.append(value)
        if covering is not None:
            first = (date.fromisoformat(covering) - timedelta(days=6)).isoformat()
            where.append("schedules.week_start between ? and ?")
            args += [first, covering]
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

    def delete_run(self, run_id: str) -> int:
        """A run and what belongs only to it (Phase AA): its schedule versions, their changes and their drafts.
        Events and every record of the days (attendance, moved breaks, activities, channel moves, day log, interval
        targets) stay. Returns how many versions were deleted."""
        with self._db() as db:
            ids = [(r[0],) for r in db.execute("select id from schedules where run_id = ?", (run_id,))]
            for table in ("schedule_changes", "break_drafts", "channel_drafts"):
                db.executemany(f"delete from {table} where schedule_id = ?", ids)
            db.execute("delete from schedules where run_id = ?", (run_id,))
            db.execute("delete from runs where id = ?", (run_id,))
        return len(ids)

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

    def add_activity(self, **fields: Any) -> int:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            return int(db.execute(f"insert into activities ({names}) values ({marks})", tuple(fields.values())).lastrowid)

    def get_activity(self, activity_id: int) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select * from activities where id = ?", (activity_id,)).fetchone()
        return dict(row) if row else None

    def delete_activity(self, activity_id: int) -> None:
        with self._db() as db:
            db.execute("delete from activities where id = ?", (activity_id,))

    def list_activities(self, program: str, dates: List[str]) -> List[Dict[str, Any]]:
        marks = ", ".join("?" for _ in dates)
        with self._db() as db:
            return [dict(r) for r in db.execute(
                f"select * from activities where program = ? and shift_date in ({marks}) order by start, id",
                (program, *dates))]

    def activities_between(self, start: str, end: str, program: Optional[str] = None,
                           user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._between("select activities.*, coalesce(users.display_name, '') as by_name from activities"
                             " left join users on users.id = activities.user_id where shift_date between ? and ?",
                             [start, end], program, user_id, "activities", "shift_date, program, associate, start")

    def add_day_log(self, **fields: Any) -> int:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            return int(db.execute(f"insert into day_log ({names}) values ({marks})", tuple(fields.values())).lastrowid)

    def list_day_log(self, program: str, shift_date: str) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "select day_log.*, users.display_name as by_name from day_log join users on users.id = day_log.user_id"
                " where program = ? and shift_date = ? order by day_log.id", (program, shift_date))]

    def delete_day_before(self, shift_date: str) -> int:
        """Delete attendance, actual breaks and their log for shift dates before the one given."""
        with self._db() as db:
            return sum(db.execute(f"delete from {table} where shift_date < ?", (shift_date,)).rowcount
                       for table in ("attendance", "actual_breaks", "activities", "day_log", "notify_items",
                                     "notify_posts"))

    # ------------------------------------------------------------- group posts (Phase AB)
    def get_notify(self, unit: str) -> Optional[Dict[str, Any]]:
        with self._db() as db:
            row = db.execute("select * from notify_settings where unit = ?", (unit,)).fetchone()
        return dict(row) if row else None

    def set_notify(self, unit: str, **fields: Any) -> None:
        with self._db() as db:
            db.execute("insert or ignore into notify_settings (unit) values (?)", (unit,))
            if fields:
                sets = ", ".join(f"{name} = ?" for name in fields)
                db.execute(f"update notify_settings set {sets} where unit = ?", (*fields.values(), unit))

    def list_notify(self) -> List[Dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute("select * from notify_settings order by unit")]

    def notify_overview(self) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Every LOB's settings and its newest post, keyed by unit, in two queries (Phase AC)."""
        with self._db() as db:
            settings = {r["unit"]: dict(r) for r in db.execute("select * from notify_settings")}
            newest = {r["unit"]: dict(r) for r in db.execute(
                "select * from notify_posts where id in (select max(id) from notify_posts group by unit)")}
        return settings, newest

    def add_notify_item(self, **fields: Any) -> int:
        names, marks = ", ".join(fields), ", ".join("?" for _ in fields)
        with self._db() as db:
            return int(db.execute(f"insert into notify_items ({names}) values ({marks})",
                                  tuple(fields.values())).lastrowid)

    def notify_items(self, unit: Optional[str] = None, shift_date: Optional[str] = None,
                     status: Optional[str] = None, post_id: Optional[int] = None) -> List[Dict[str, Any]]:
        where = {"unit": unit, "shift_date": shift_date, "status": status, "post_id": post_id}
        where = {k: v for k, v in where.items() if v is not None}
        sql = "select * from notify_items" + (" where " + " and ".join(f"{k} = ?" for k in where) if where else "")
        with self._db() as db:
            return [dict(r) for r in db.execute(sql + " order by id", tuple(where.values()))]

    def set_notify_items(self, ids: List[int], **fields: Any) -> None:
        if not ids or not fields:
            return
        sets = ", ".join(f"{name} = ?" for name in fields)
        with self._db() as db:
            db.execute(f"update notify_items set {sets} where id in ({', '.join('?' for _ in ids)})",
                       (*fields.values(), *ids))

    def add_notify_post(self, **fields: Any) -> int:
        fields.setdefault("made_at", time.time())
        names, marks = ", ".join(fields), ", ".join("?" for _ in fields)
        with self._db() as db:
            return int(db.execute(f"insert into notify_posts ({names}) values ({marks})",
                                  tuple(fields.values())).lastrowid)

    def set_notify_post(self, post_id: int, **fields: Any) -> None:
        sets = ", ".join(f"{name} = ?" for name in fields)
        with self._db() as db:
            db.execute(f"update notify_posts set {sets} where id = ?", (*fields.values(), post_id))

    def notify_posts(self, unit: Optional[str] = None, status: Optional[str] = None, what: Optional[str] = None,
                     shift_date: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Newest first."""
        where = {"unit": unit, "status": status, "what": what, "shift_date": shift_date}
        where = {k: v for k, v in where.items() if v is not None}
        sql = "select * from notify_posts" + (" where " + " and ".join(f"{k} = ?" for k in where) if where else "")
        sql += " order by id desc" + (f" limit {int(limit)}" if limit else "")
        with self._db() as db:
            return [dict(r) for r in db.execute(sql, tuple(where.values()))]

    # ------------------------------------------------------------- ranges for exports
    @staticmethod
    def _program_filter(column: str, program: Any) -> Tuple[str, List[Any]]:
        """" and <column> = ?" for one program, "in (...)" for several (none matches nothing), "" for all."""
        if program is None:
            return "", []
        if isinstance(program, str):
            return f" and {column} = ?", [program]
        names = sorted(set(program))
        if not names:
            return " and 0", []
        return f" and {column} in ({', '.join('?' for _ in names)})", names

    def _between(self, sql: str, args: List[Any], program: Any, user_id: Optional[int], table: str,
                 order: str) -> List[Dict[str, Any]]:
        """``program``: one name, several (a list or set), or None for every program."""
        extra, more = self._program_filter(f"{table}.program", program)
        sql += extra
        args.extend(more)
        if user_id is not None:
            sql += f" and {table}.user_id = ?"
            args.append(user_id)
        with self._db() as db:
            return [dict(r) for r in db.execute(sql + " order by " + order, args)]

    def attendance_between(self, start: str, end: str, program: Optional[str] = None,
                           user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._between("select attendance.*, coalesce(users.display_name, '') as by_name from attendance"
                             " left join users on users.id = attendance.user_id where shift_date between ? and ?",
                             [start, end], program, user_id, "attendance", "shift_date, program, associate")

    def latest_record_date(self, program: Any = None) -> Optional[str]:
        """The latest shift date anything was recorded for on the day (attendance, break moves, activities)."""
        found = []
        with self._db() as db:
            for table in ("attendance", "actual_breaks", "activities"):
                extra, args = self._program_filter(f"{table}.program", program)
                row = db.execute(f"select max(shift_date) from {table} where 1 = 1{extra}", args).fetchone()
                if row and row[0]:
                    found.append(row[0])
        return max(found) if found else None

    def actual_breaks_between(self, start: str, end: str, program: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._between("select actual_breaks.*, coalesce(users.display_name, '') as by_name from actual_breaks"
                             " left join users on users.id = actual_breaks.user_id where shift_date between ? and ?",
                             [start, end], program, None, "actual_breaks", "shift_date, program, associate, idx")

    def day_log_between(self, start: str, end: str, program: Optional[str] = None,
                        user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._between("select day_log.*, coalesce(users.display_name, '') as by_name from day_log"
                             " left join users on users.id = day_log.user_id where shift_date between ? and ?",
                             [start, end], program, user_id, "day_log", "day_log.shift_date, day_log.id")

    def changes_between(self, start: float, end: float, program: Optional[str] = None,
                        user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = ("select schedule_changes.*, schedules.program, schedules.week_start, schedules.label,"
               " coalesce(users.display_name, '') as by_name from schedule_changes join schedules"
               " on schedules.id = schedule_changes.schedule_id left join users on users.id = schedule_changes.user_id"
               " where schedule_changes.at >= ? and schedule_changes.at < ?")
        args: List[Any] = [start, end]
        extra, more = self._program_filter("schedules.program", program)
        sql += extra
        args.extend(more)
        if user_id is not None:
            sql += " and schedule_changes.user_id = ?"
            args.append(user_id)
        with self._db() as db:
            return [dict(r) for r in db.execute(sql + " order by schedule_changes.at, schedule_changes.id", args)]

    def runs_between(self, start: float, end: float, program: Optional[str] = None,
                     user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._between("select runs.*, coalesce(users.display_name, '') as by_name from runs left join users"
                             " on users.id = runs.user_id where runs.created >= ? and runs.created < ?",
                             [start, end], program, user_id, "runs", "runs.created")

    # ------------------------------------------------------------- the record (actions not in another log)
    def add_event(self, **fields: Any) -> None:
        fields.setdefault("at", time.time())
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            db.execute(f"insert into events ({names}) values ({marks})", tuple(fields.values()))

    def list_events(self, start: float, end: float, program: Optional[str] = None, user_id: Optional[int] = None,
                    kinds: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Events with ``start <= at < end``, oldest first, with the name of who did them."""
        where, args = ["events.at >= ?", "events.at < ?"], [start, end]
        extra, more = self._program_filter("events.program", program)
        if extra:
            where.append(extra[len(" and "):])
            args.extend(more)
        if user_id is not None:
            where.append("events.user_id = ?")
            args.append(user_id)
        if kinds:
            where.append(f"events.kind in ({', '.join('?' for _ in kinds)})")
            args.extend(kinds)
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "select events.*, coalesce(users.display_name, '') as by_name from events left join users"
                " on users.id = events.user_id where " + " and ".join(where) + " order by events.at, events.id", args)]

    def delete_events_before(self, at: float) -> int:
        with self._db() as db:
            return db.execute("delete from events where at < ?", (at,)).rowcount

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        names = ", ".join(f"{k} = ?" for k in fields)
        with self._db() as db:
            db.execute(f"update runs set {names} where id = ?", (*fields.values(), run_id))

    RUN_DETAILS = ("program", "week_start", "user_id", "workbook")

    def move_run(self, run_id: str, fields: Dict[str, Any], stop_in_use: List[int]) -> None:
        """Change a run's details in one transaction: its versions take its program and week, and the
        versions in ``stop_in_use`` stop being in use."""
        unknown = set(fields) - set(self.RUN_DETAILS)
        if unknown:
            raise ValueError(f"Not a run detail: {', '.join(sorted(unknown))}.")
        with self._db() as db:
            if fields:
                names = ", ".join(f"{k} = ?" for k in fields)
                db.execute(f"update runs set {names} where id = ?", (*fields.values(), run_id))
            moved = {k: v for k, v in fields.items() if k in ("program", "week_start")}
            if moved:
                names = ", ".join(f"{k} = ?" for k in moved)
                db.execute(f"update schedules set {names} where run_id = ?", (*moved.values(), run_id))
            for schedule_id in stop_in_use:
                db.execute("update schedules set in_use = 0 where id = ?", (schedule_id,))

    def day_record_counts(self, program: str, start: str, end: str) -> Dict[str, int]:
        """How many day records a program holds for shift dates ``start`` to ``end``."""
        counts = {}
        with self._db() as db:
            for key, table in self.DAY_TABLES:
                counts[key] = db.execute(f"select count(*) from {table} where program = ?"
                                         " and shift_date between ? and ?", (program, start, end)).fetchone()[0]
        return counts

    DAY_TABLES = (("attendance", "attendance"), ("breaks", "actual_breaks"), ("activities", "activities"),
                  ("log", "day_log"), ("channels", "channel_moves"))  # channels: Phase V

    def rename_program(self, old: str, new: str, stop_in_use: List[int]) -> Dict[str, int]:
        """Move everything kept under program ``old`` to ``new`` in one transaction (runs, versions and day
        records; past events keep the name they had). Rows moved per table."""
        moved = {}
        with self._db() as db:
            for schedule_id in stop_in_use:
                db.execute("update schedules set in_use = 0 where id = ?", (schedule_id,))
            for key, table in (("runs", "runs"), ("versions", "schedules"), *self.DAY_TABLES):
                moved[key] = db.execute(f"update {table} set program = ? where program = ?", (new, old)).rowcount
            # interval targets (Phase W) go with the name; a week the new name has a target for keeps its own
            db.execute("update or ignore interval_targets set program = ? where program = ?", (new, old))
            db.execute("delete from interval_targets where program = ?", (old,))
            # group posts (Phase AB) go with the name too; a name that has its own settings keeps them
            db.execute("update or ignore notify_settings set unit = ? where unit = ?", (new, old))
            db.execute("delete from notify_settings where unit = ?", (old,))
            for table in ("notify_items", "notify_posts"):
                db.execute(f"update {table} set unit = ? where unit = ?", (new, old))
        return moved

    def program_clashes(self, old: str, new: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Attendance and moved breaks kept under both names for the same person, day (and break)."""
        with self._db() as db:
            found = [dict(r, what="attendance") for r in db.execute(
                "select a.shift_date, a.associate from attendance a join attendance b on b.program = ?"
                " and b.shift_date = a.shift_date and b.associate = a.associate where a.program = ?"
                " order by a.shift_date, a.associate limit ?", (new, old, limit))]
            found += [dict(r, what="break") for r in db.execute(
                "select a.shift_date, a.associate, a.kind from actual_breaks a join actual_breaks b on b.program = ?"
                " and b.shift_date = a.shift_date and b.associate = a.associate and b.idx = a.idx"
                " where a.program = ? order by a.shift_date, a.associate limit ?", (new, old, limit))]
        return found[:limit]

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
