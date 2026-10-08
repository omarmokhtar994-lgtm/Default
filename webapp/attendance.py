# © 2026 Omar Mokhtar. All rights reserved.
"""The day as it happens: attendance and actual breaks for a program and date.

Read against the version in use for that week (the tool's own version, with a
note, when none is marked). Kept per program, shift date and associate, so an
overnight shift's status and breaks belong to the day it started. Every change
is checked first (a timed status needs its times inside the shift; a break
stays inside the shift, off the person's other breaks, on a 5-minute step) and
logged with who and when. Kept 13 months, like the schedules.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .day import AUX, MEASURES, STATUSES, TIMED, BreakRefused, advice, check_break, day_view, planned, read_inputs
from .schedules import EGYPT, KEEP_DAYS, ScheduleBook
from .versions import DAYS, shift_span

HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
FALLBACK = "No version is marked in use for this week, so this is the tool's own schedule."


def week_start(on: date) -> date:
    """The Sunday that starts the week holding ``on``."""
    return on - timedelta(days=(on.weekday() + 1) % 7)


def day_index(on: date) -> int:
    return (on.weekday() + 1) % 7  # Sunday = 0


def hm(minute: int) -> str:
    minute %= 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _clock(text: str) -> Optional[int]:
    found = HHMM.match((text or "").strip())
    return int(found.group(1)) * 60 + int(found.group(2)) if found else None


class DayBook:
    def __init__(self, store, book: ScheduleBook):
        self.store = store
        self.book = book

    # ------------------------------------------------------------- what the day reads
    def programs(self) -> List[str]:
        return sorted({v["program"] for v in self.store.list_schedules() if v["program"]}, key=str.lower)

    def version(self, program: str, on: date) -> Tuple[Optional[Dict[str, Any]], str]:
        """The version in use for the week holding ``on``, else the tool's own (after breaks first)."""
        start = week_start(on).isoformat()
        chosen = self.book.in_use(program, start)
        if chosen:
            return chosen, ""
        tools = [v for v in self.store.list_schedules(program=program, week_start=start) if v["kind"] != "edited"]
        tools.sort(key=lambda v: (v["kind"] != "tool_after", -v["created"]))
        return (tools[0], FALLBACK) if tools else (None, "")

    def _week(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(row["week"] or "{}")

    def _shift(self, program: str, on: date, name: str) -> Tuple[Dict[str, Any], Dict[str, Any], Tuple[int, int]]:
        row, _ = self.version(program, on)
        if row is None:
            raise ValueError(f"There is no schedule for {program} in the week of {week_start(on):%d %b}.")
        week = self._week(row)
        person = next((a for a in week.get("associates", []) if a["name"] == name), None)
        if person is None:
            raise ValueError(f"{name} is not on this schedule.")
        span = shift_span(person["days"][day_index(on)])
        if not span:
            raise ValueError(f"{name} has no shift on {on:%A %d %b} ({person['days'][day_index(on)]}).")
        return row, week, span

    def _records(self, program: str, on: date, row: Dict[str, Any]) -> Tuple[dict, dict, int]:
        """Attendance and actual breaks keyed for day_view: (offset, name[, idx]). A kept break move
        whose break no longer matches the plan (the version changed) is counted, not applied."""
        dates = {0: on, -1: on - timedelta(days=1)}
        attendance, actual, stale = {}, {}, 0
        for offset, d in dates.items():
            for r in self.store.list_attendance(program, [d.isoformat()]):
                attendance[(offset, r["associate"])] = {"status": r["status"], "from": r["from_min"], "to": r["to_min"],
                                                        "billable": bool(r["billable"])}
            source, _ = (row, "") if week_start(d) == week_start(on) else self.version(program, d)
            week = self._week(source) if source else {}
            for r in self.store.list_actual_breaks(program, [d.isoformat()]):
                plan = {b["idx"]: b for b in planned(week, day_index(d), r["associate"])} if week else {}
                if plan.get(r["idx"], {}).get("kind") != r["kind"]:
                    stale += 1
                    continue
                actual[(offset, r["associate"], r["idx"])] = r["start"]
        return attendance, actual, stale

    def page(self, program: str, on: date, measure: str = "interval") -> Optional[Dict[str, Any]]:
        if measure not in MEASURES:
            raise ValueError(f"Unknown measure: {measure}.")
        row, note = self.version(program, on)
        if row is None:
            return None
        week = self._week(row)
        inputs = read_inputs(self.book.input_path(row["run_id"]))
        attendance, actual, stale = self._records(program, on, row)
        view = day_view(week, inputs, day_index(on), attendance, actual, measure)
        return {"version": row, "note": note, "view": view, "stale": stale, "date": on,
                "week_start": week_start(on).isoformat(), "day": day_index(on), "inputs": inputs,
                "log": self.store.list_day_log(program, on.isoformat())}

    # ------------------------------------------------------------- what people record
    def set_status(self, program: str, on: date, name: str, status: str, user_id: int,
                   start: str = "", end: str = "", billable: bool = False) -> None:
        """Record a status for the shift that starts on ``on``. Late needs the arrival (``end``),
        Left early the leaving time (``start``); an aux (Training, Coaching, Meeting, System issue)
        takes an optional from/to and is billable or not."""
        if status not in STATUSES:
            raise ValueError(f"Unknown status: {status}.")
        _, _, span = self._shift(program, on, name)

        def inside(text: str, what: str) -> Optional[int]:
            if not (text or "").strip():
                return None
            m = _clock(text)
            if m is None:
                raise ValueError(f"{what} must be a time like 13:05.")
            m += 1440 if m < span[0] else 0
            if not span[0] <= m <= span[1]:
                raise ValueError(f"{what} {hm(m)} is outside {name}'s shift ({hm(span[0])} to {hm(span[1])}).")
            return m

        lo, hi = inside(start, "From"), inside(end, "To")
        if status == "Late":
            if hi is None:
                raise ValueError("Give the time they arrived.")
            lo, what = None, f"Late, arrived {hm(hi)}"
        elif status == "Left early":
            if lo is None:
                raise ValueError("Give the time they left.")
            hi, what = None, f"Left early at {hm(lo)}"
        elif status in TIMED:
            if (lo is None) != (hi is None):
                raise ValueError("Give both times, or neither for the whole shift.")
            if lo is not None and lo >= hi:
                raise ValueError("The end time must be after the start time.")
            kind = f"{status} ({'billable' if billable else 'non-billable'})"
            what = f"{kind} {hm(lo)} to {hm(hi)}" if lo is not None else f"{kind}, whole shift"
        else:
            lo = hi = None
            what = status
        self.store.set_attendance(program=program, shift_date=on.isoformat(), associate=name, status=status,
                                  from_min=lo, to_min=hi, billable=int(bool(billable) and status in AUX),
                                  user_id=user_id)
        self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name, what=what, user_id=user_id)

    def move_break(self, program: str, on: date, name: str, idx: int, at: Optional[str], user_id: int) -> None:
        """Move a break of the shift that starts on ``on`` to ``at`` (HH:MM), or back to the plan (None)."""
        row, week, span = self._shift(program, on, name)
        plan = {b["idx"]: b for b in planned(week, day_index(on), name)}
        if idx not in plan:
            raise BreakRefused("That break is not on the plan.")
        kept = {(0, r["associate"], r["idx"]): r["start"] for r in self.store.list_actual_breaks(program, [on.isoformat()])
                if r["associate"] == name and plan.get(r["idx"], {}).get("kind") == r["kind"]}
        was = kept.get((0, name, idx), plan[idx]["start"])
        if at is None:
            self.store.clear_actual_break(program, on.isoformat(), name, idx)
            what = f"{plan[idx]['kind']} back to plan ({hm(plan[idx]['start'])})"
        else:
            m = _clock(at)
            if m is None:
                raise ValueError("The break time must be like 13:05.")
            m += 1440 if m < span[0] else 0
            check_break(week, day_index(on), 0, name, idx, m, kept)
            self.store.set_actual_break(program=program, shift_date=on.isoformat(), associate=name, idx=idx,
                                        kind=plan[idx]["kind"], start=m, user_id=user_id)
            what = f"{plan[idx]['kind']} moved {hm(was)} to {hm(m)}"
        self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name, what=what, user_id=user_id)

    def break_advice(self, program: str, on: date, name: str, idx: int, at: str,
                     measure: str = "interval") -> Dict[str, Any]:
        """Gap warnings for a proposed break time and the best times for that break today."""
        _, week, span = self._shift(program, on, name)
        if idx not in {b["idx"] for b in planned(week, day_index(on), name)}:
            raise BreakRefused("That break is not on the plan.")
        m = _clock(at)
        if m is None:
            raise ValueError("The break time must be like 13:05.")
        page = self.page(program, on, measure)
        return advice(page["view"], page["inputs"], name, idx, m + (1440 if m < span[0] else 0))

    # ------------------------------------------------------------- retention
    def cleanup(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        cutoff = datetime.fromtimestamp(now, EGYPT).date() - timedelta(days=KEEP_DAYS)
        return self.store.delete_day_before(cutoff.isoformat())
