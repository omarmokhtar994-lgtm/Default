# © 2026 Omar Mokhtar. All rights reserved.
"""Exports: what was recorded on the website for a period, and who did it.

Shift-dated items (attendance, day activity, breaks, worked hours) follow the
shift's own date; logged actions (schedule changes, versions, runs, the other
actions) follow when they happened. All times are Egypt time. Excel holds an
"About this export" tab and a tab per item; CSV holds one item. Text typed by
people is always written as text (never a formula, in Excel or CSV).
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

from .adherence import person_day
from .day import ABSENT, AUX, CALLED_IN, MEASURES, pattern_breaks, planned
from .versions import DAYS

EGYPT = timezone(timedelta(hours=3))
MAX_DAYS = 400
KINDS = {"attendance": "Attendance", "activities": "Activities", "activity": "Day activity",
         "breaks": "Breaks planned vs taken",
         "changes": "Schedule changes and swaps", "versions": "Versions and in use", "runs": "Runs",
         "worked": "Worked hours and adherence", "summary": "Daily summary", "record": "Other actions"}
VERSION_EVENTS = {"version_created": "New version", "set_in_use": "Set in use"}
OTHER_EVENTS = {"run_uploaded": "Run uploaded", "run_started": "Run started", "run_stopped": "Run stopped",
                "run_resumed": "Run resumed", "downloaded": "Downloaded", "exported": "Exported",
                "user_added": "Person added", "user_disabled": "Person switched off", "user_enabled": "Person switched on",
                "password_reset": "Password reset", "run_details_changed": "Run details changed",
                "program_renamed": "Program renamed", "user_programs_changed": "Programs or role changed",
                "program_set_up": "Programs and LOBs"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
RISKY = ("=", "+", "-", "@", "\t", "\r")


def _ts(day: date) -> float:
    return datetime(day.year, day.month, day.day, tzinfo=EGYPT).timestamp()


def _when(ts: Optional[float]) -> str:
    return datetime.fromtimestamp(ts, EGYPT).strftime("%Y-%m-%d %H:%M") if ts else ""


def _hm(minute: Optional[int]) -> str:
    if minute is None:
        return ""
    minute %= 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _dates(start: date, end: date) -> Iterable[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _day_index(day: date) -> int:
    return (day.weekday() + 1) % 7


class _Weeks:
    """The schedule in use (or the tool's) per program and week, read once."""

    def __init__(self, days):
        self.days = days
        self.seen: Dict[int, Dict[str, Any]] = {}
        self.dates: Dict[Tuple[str, date], Dict[str, Any]] = {}

    def week(self, program: str, day: date) -> Dict[str, Any]:
        """The week holding ``day`` (its start may be any weekday): looked up once per program and date,
        read once per version."""
        if (program, day) not in self.dates:
            row, _ = self.days.version(program, day)
            if row is not None and row["id"] not in self.seen:
                self.seen[row["id"]] = json.loads(row["week"] or "{}")
            self.dates[(program, day)] = self.seen[row["id"]] if row is not None else {}
        return self.dates[(program, day)]

    def person(self, program: str, day: date, name: str) -> Dict[str, Any]:
        return next((a for a in self.week(program, day).get("associates", []) if a["name"] == name), {})


def _attendance(store, days, weeks, start, end, program, user_id, measure):
    yield ["Shift date", "Program", "Associate", "Slot", "Shift", "Status", "From", "To", "Billable", "Recorded by",
           "Recorded at"]
    for r in store.attendance_between(start.isoformat(), end.isoformat(), program, user_id):
        day = date.fromisoformat(r["shift_date"])
        person = weeks.person(r["program"], day, r["associate"])
        billable = "Yes" if r["billable"] else ("No" if r["status"] in AUX else "")
        yield [r["shift_date"], r["program"], r["associate"], person.get("slot", ""),
               (person.get("days") or [""] * 7)[_day_index(day)], r["status"], _hm(r["from_min"]), _hm(r["to_min"]),
               billable, r["by_name"], _when(r["at"])]


def _activities(store, days, weeks, start, end, program, user_id, measure):
    yield ["Shift date", "Program", "Associate", "Activity", "From", "To", "Minutes", "Billable", "Note", "Recorded by",
           "Recorded at"]
    for r in store.activities_between(start.isoformat(), end.isoformat(), program, user_id):
        yield [r["shift_date"], r["program"], r["associate"], r["kind"], _hm(r["start"]), _hm(r["end_min"]),
               r["end_min"] - r["start"], "Yes" if r["billable"] else "No", r["note"], r["by_name"], _when(r["at"])]


def _activity(store, days, weeks, start, end, program, user_id, measure):
    yield ["Shift date", "Program", "Associate", "What", "By", "At"]
    for r in store.day_log_between(start.isoformat(), end.isoformat(), program, user_id):
        yield [r["shift_date"], r["program"], r["associate"], r["what"], r["by_name"], _when(r["at"])]


def _programs_said(program) -> str:
    """The About tab's line: one program, a person's own, none, or all."""
    if program is None:
        return "All programs"
    if isinstance(program, str):
        return program
    return ", ".join(sorted(program)) or "None (no programs assigned)"


def _programs(days, program):
    """One program, several (a person's own), or every program with schedules."""
    if isinstance(program, (list, tuple, set, frozenset)):
        return sorted(program)
    return [program] if program else days.programs()


def _breaks(store, days, weeks, start, end, program, user_id, measure):
    yield ["Shift date", "Program", "Associate", "Slot", "Shift", "Break", "Minutes", "Planned", "Taken", "Moved by",
           "Moved at", "Status"]
    for p in _programs(days, program):
        moved = {(r["shift_date"], r["associate"], r["idx"]): r for r in store.actual_breaks_between(
            start.isoformat(), end.isoformat(), p)}
        status = {(r["shift_date"], r["associate"]): r["status"] for r in store.attendance_between(
            start.isoformat(), end.isoformat(), p)}
        called = {(r["shift_date"], r["associate"]): r["note"] for r in store.activities_between(
            start.isoformat(), end.isoformat(), p) if r["kind"] == CALLED_IN}
        for day in _dates(start, end):
            week = weeks.week(p, day)
            for a in week.get("associates", []):
                state = status.get((day.isoformat(), a["name"]), "Present")
                shift, plan = a["days"][_day_index(day)], planned(week, _day_index(day), a["name"])
                label = called.get((day.isoformat(), a["name"]))
                if not plan and label:  # a day off cancelled: the plan's breaks for the shift they came in for
                    shift, plan = f"{label} (called in)", pattern_breaks(week, _day_index(day), label)
                for b in plan:
                    m = moved.get((day.isoformat(), a["name"], b["idx"]))
                    m = m if m and m["kind"] == b["kind"] else None  # a move kept against another plan is not this break
                    taken = "" if state in ABSENT else _hm(m["start"] if m else b["start"])
                    yield [day.isoformat(), p, a["name"], a.get("slot", ""), shift, b["kind"],
                           b["minutes"], _hm(b["start"]), taken, m["by_name"] if m else "", _when(m["at"]) if m else "",
                           state]


def _changes(store, days, weeks, start, end, program, user_id, measure):
    yield ["Program", "Week", "Version", "Associate", "Day", "Old", "New", "Reason", "Severity", "Problems", "By", "At"]
    for r in store.changes_between(_ts(start), _ts(end + timedelta(days=1)), program, user_id):
        try:
            found = "; ".join(json.loads(r["problems"] or "[]"))
        except ValueError:
            found = r["problems"]
        severity = {"red": "Rule broken", "yellow": "Warning"}.get(r["severity"], "")
        yield [r["program"], r["week_start"], r["label"], r["associate"],
               "Whole week (slot swap)" if r["day"] == "Week" else r["day"], r["old"], r["new"], r["reason"], severity,
               found, r["by_name"], _when(r["at"])]


def _versions(store, days, weeks, start, end, program, user_id, measure):
    yield ["Program", "Week", "Version", "What", "Detail", "By", "At"]
    for r in store.list_events(_ts(start), _ts(end + timedelta(days=1)), program, user_id, list(VERSION_EVENTS)):
        yield [r["program"], r["week_start"], r["subject"], VERSION_EVENTS[r["kind"]], r["detail"], r["by_name"],
               _when(r["at"])]


def _runs(store, days, weeks, start, end, program, user_id, measure):
    yield ["Workbook", "Program", "Week", "Mode", "Status", "Uploaded by", "Uploaded at", "Finished at", "Run"]
    for r in store.runs_between(_ts(start), _ts(end + timedelta(days=1)), program, user_id):
        yield [r["workbook"], r["program"], r["week_start"], r["mode"], r["status"], r["by_name"], _when(r["created"]),
               _when(r["finished"]), r["id"]]


def _record(store, days, weeks, start, end, program, user_id, measure):
    yield ["What", "About", "Program", "Detail", "By", "At"]
    for r in store.list_events(_ts(start), _ts(end + timedelta(days=1)), program, user_id, list(OTHER_EVENTS)):
        yield [OTHER_EVENTS[r["kind"]], r["subject"], r["program"], r["detail"], r["by_name"], _when(r["at"])]


def _worked(store, days, weeks, start, end, program, user_id, measure):
    yield ["Shift date", "Program", "Associate", "Slot", "Shift", "Status", "Scheduled min", "Scheduled work min",
           "Worked min", "Late min", "Early min", "Absent min", "Aux billable min", "Aux non-billable min",
           "Breaks planned min", "Breaks taken min", "Out of schedule min", "VTO min", "Overtime min", "Adherence %",
           "Conformance %"]
    for p in _programs(days, program):
        for day in _dates(start, end):
            try:
                page = days.page(p, day, measure)
            except ValueError:  # the input workbook is gone: said on the day page, skipped here
                continue
            if page is None:
                continue
            for lane in page["view"]["lanes"]:
                if not any(s["offset"] == 0 for s in lane["segments"]):
                    continue
                r = person_day(page["view"], lane["name"])
                yield [day.isoformat(), p, lane["name"], lane.get("slot", ""), r["shift"], r["status"], r["scheduled"],
                       r["scheduled_work"], r["worked"], r["late"], r["early"], r["absent"], r["aux_billable"],
                       r["aux_unbillable"], r["breaks_planned"], r["breaks_taken"], r["out_of_schedule"], r["vto"],
                       r["overtime"], r["adherence"], r["conformance"]]


def _summary(store, days, weeks, start, end, program, user_id, measure):
    from .handover import note  # the handover note's numbers, one row per program and day
    yield ["Date", "Program", "Planned", "Present", "Absent", "Late or early", "In aux", "Breaks moved", "Overtime min",
           "VTO min", "Called in min", "Hours short", "Hours short in the plan", "Hours above", "Tightest (hours)",
           "Language gaps", "Adherence %", "Conformance %", "Changes recorded"]
    for p in _programs(days, program):
        for day in _dates(start, end):
            try:
                found = note(days, p, day, measure)
            except ValueError:
                continue
            if found is None:
                continue
            n = found["numbers"]
            yield [day.isoformat(), p, n["planned"], n["present"], n["absent"], n["late_early"], n["aux"], n["moved"],
                   n["overtime_minutes"], n["vto_minutes"], n["called_in_minutes"], n["short_hours"],
                   n["plan_short_hours"], n["over_hours"], n["tightest"], n["language_gaps"], n["adherence"],
                   n["conformance"], n["changes"]]


TABLES: Dict[str, Callable] = {"attendance": _attendance, "activities": _activities, "activity": _activity,
                               "breaks": _breaks,
                               "changes": _changes, "versions": _versions, "runs": _runs, "worked": _worked,
                               "summary": _summary,
                               "record": _record}


def _text_cell(ws, value: Any) -> WriteOnlyCell:
    cell = WriteOnlyCell(ws, value=value)
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"  # typed text stays text
    return cell


def _csv_safe(value: Any) -> Any:
    return "'" + value if isinstance(value, str) and value.startswith(RISKY) else value


def build(store, days, start: date, end: date, kinds: List[str], fmt: str = "xlsx", program: Optional[str] = None,
          user_id: Optional[int] = None, by: str = "", measure: str = "interval") -> Tuple[bytes, str, str]:
    """The export as (bytes, file name, media type). Raises ValueError for a request it cannot answer."""
    if end < start:
        raise ValueError("The period ends before it starts.")
    if (end - start).days + 1 > MAX_DAYS:
        raise ValueError(f"Pick at most {MAX_DAYS} days (records are kept 13 months).")
    if not kinds or any(k not in KINDS for k in kinds):
        raise ValueError("Pick what to export.")
    if fmt not in ("xlsx", "csv"):
        raise ValueError("Pick Excel or CSV.")
    if fmt == "csv" and len(kinds) != 1:
        raise ValueError("A CSV file holds one item: pick one, or choose Excel.")
    if measure not in MEASURES:
        raise ValueError("Pick a measure.")
    ordered = [k for k in KINDS if k in kinds]
    weeks = _Weeks(days)
    who = (store.get_user(user_id) or {}).get("display_name", "") if user_id is not None else ""
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        for row in TABLES[ordered[0]](store, days, weeks, start, end, program, user_id, measure):
            writer.writerow([_csv_safe(v) for v in row])
        return (out.getvalue().encode("utf-8-sig"), f"Team_Scheduler_{ordered[0]}_{start}_to_{end}.csv", "text/csv")
    wb = Workbook(write_only=True)
    bold = Font(bold=True)
    about = wb.create_sheet("About this export")
    for key, value in (("Period", f"{start:%d %b %Y} to {end:%d %b %Y}"), ("Programs", _programs_said(program)),
                       ("Changes by", who or "Anyone"), ("Measure", MEASURES[measure]),
                       ("Items", ", ".join(KINDS[k] for k in ordered)), ("Downloaded by", by),
                       ("Downloaded at", datetime.now(EGYPT).strftime("%Y-%m-%d %H:%M")),
                       ("Times", "All times are Egypt time (UTC+3)."),
                       ("Dates", "Attendance, day activity, breaks and worked hours follow the shift's own date (an "
                                 "overnight shift belongs to the day it started); changes, versions, runs and other "
                                 "actions follow when they happened."),
                       ("Changes by filter", "Applies to what people did (attendance, activity, changes, versions, "
                                             "runs, other actions), not to the breaks and worked-hours listings."),
                       ("Kept", "Records are kept 13 months; run files 30 to 60 days.")):
        head = WriteOnlyCell(about, value=key)
        head.font = bold
        about.append([head, _text_cell(about, value)])
    for kind in ordered:
        ws = wb.create_sheet(KINDS[kind][:31])
        rows = TABLES[kind](store, days, weeks, start, end, program, user_id, measure)
        header = next(rows)
        cells = []
        for value in header:
            cell = WriteOnlyCell(ws, value=value)
            cell.font = bold
            cells.append(cell)
        ws.append(cells)
        for row in rows:
            ws.append([_text_cell(ws, v) for v in row])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), f"Team_Scheduler_{start}_to_{end}.xlsx", XLSX
