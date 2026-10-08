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

from .day import (ABSENT, AUX, CALLED_IN, MEASURES, OVERTIME_MAX, STATUSES, STEP, TIMED, BreakRefused, _busy, advice,
                  check_break, day_view, dayoff_offers, meeting_slots, overtime_offers, pattern_breaks, planned,
                  read_inputs, replan, vto_offers)
from .schedules import EGYPT, KEEP_DAYS, ScheduleBook
from .versions import DAYS, shift_span

HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
FALLBACK = "No version is marked in use for this week, so this is the tool's own schedule."
ACTIVITY_KINDS = sorted(AUX) + ["Overtime", "VTO", CALLED_IN]


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


def pick_version(versions: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Which of the versions covering a day it is read from: one in use, else the newest tool schedule
    (after breaks first), with a note saying so; (None, "") when there is none. Where two weeks overlap
    (a program moving from Sunday to Monday starts), the later start counts."""
    order = (lambda v: (v["week_start"], v["kind"] == "tool_after", v["created"]))
    chosen = max((v for v in versions if v["in_use"]), key=order, default=None)
    if chosen:
        return chosen, ""
    tools = sorted((v for v in versions if v["kind"] != "edited"), key=order, reverse=True)
    return (tools[0], FALLBACK) if tools else (None, "")


def tomorrow_unchecked(on: date) -> str:
    """Said when no schedule holds the day after ``on`` (the last day of the latest week here)."""
    day = f"{on + timedelta(days=1):%A}"
    return f"Next week's schedule is not here yet, so the rest gap to {day} is not checked: check {day}'s start by hand."


class DayBook:
    def __init__(self, store, book: ScheduleBook):
        self.store = store
        self.book = book

    # ------------------------------------------------------------- what the day reads
    def programs(self) -> List[str]:
        return sorted({v["program"] for v in self.store.list_schedules() if v["program"]}, key=str.lower)

    def version(self, program: str, on: date) -> Tuple[Optional[Dict[str, Any]], str]:
        """The version in use for the week holding ``on``, else the tool's own (after breaks first)."""
        return pick_version(self.store.list_schedules(program=program, covering=on.isoformat()))

    def _week(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(row["week"] or "{}")

    def called_in_on(self, program: str, on: date, name: str) -> Optional[Dict[str, Any]]:
        return next((r for r in self.store.list_activities(program, [on.isoformat()])
                     if r["associate"] == name and r["kind"] == CALLED_IN), None)

    def _spans(self, program: str, on: date, saturday_before: Optional[List[Dict[str, Any]]] = None
               ) -> Optional[Dict[str, Tuple[int, int]]]:
        """Who works on ``on`` and when (minutes from that day's midnight): the schedule's shift, or the shift
        they were called in for, lengthened by overtime recorded. ``saturday_before`` (the input's previous
        Saturday) stands in when no schedule is kept for that week; None when neither says."""
        row, _ = self.version(program, on)
        spans: Dict[str, Tuple[int, int]] = {}
        if row is not None:
            for a in self._week(row).get("associates", []):
                span = shift_span(a["days"][day_index(on)])
                if span:
                    spans[a["name"]] = span
        elif saturday_before is not None:
            for p in saturday_before:
                span = shift_span(p.get("shift", ""))
                if span:
                    spans[p["name"]] = span
        else:
            return None
        acts = self.store.list_activities(program, [on.isoformat()])
        for r in acts:
            if r["kind"] == CALLED_IN:
                spans.setdefault(r["associate"], (r["start"], r["end_min"]))
        for r in acts:
            if r["kind"] == "Overtime" and r["associate"] in spans:
                lo, hi = spans[r["associate"]]
                spans[r["associate"]] = (min(lo, r["start"]), max(hi, r["end_min"]))
        return spans

    def neighbours(self, program: str, on: date, row: Dict[str, Any]) -> Dict[str, Any]:
        """Everyone's working spans the day before and the day after ``on``, across the week's edges: the
        week before falls back to the input's previous Saturday; a week after with no schedule is unknown."""
        before = on - timedelta(days=1)
        source = self.book.input_path(row["run_id"])  # when no schedule holds the day before: the input's tab
        saturday = read_inputs(source)["previous_saturday"] if source.is_file() else None
        prev, nxt = self._spans(program, before, saturday), self._spans(program, on + timedelta(days=1))
        return {"prev": prev or {}, "next": nxt or {}, "next_known": nxt is not None}

    def _rest(self, program: str, on: date, row: Dict[str, Any], name: str, lo: int, hi: int, rest: int) -> None:
        """Refuse work from ``lo`` to ``hi`` on ``on`` that leaves less than ``rest`` minutes off either side."""
        if not rest:
            return
        near = self.neighbours(program, on, row)
        prv, nxt = near["prev"].get(name), near["next"].get(name)
        if prv and lo + 1440 - prv[1] < rest:
            raise ValueError(f"{name} would rest {(lo + 1440 - prv[1]) / 60:g} hours after the previous shift; "
                             f"the rule is {rest / 60:g}.")
        if nxt and nxt[0] + 1440 - hi < rest:
            raise ValueError(f"{name} would rest {(nxt[0] + 1440 - hi) / 60:g} hours before the next shift; "
                             f"the rule is {rest / 60:g}.")

    def _shift(self, program: str, on: date, name: str) -> Tuple[Dict[str, Any], Dict[str, Any], Tuple[int, int]]:
        """The version, its week and the person's shift that day: the planned one, or the shift they were
        called in for on a day off."""
        row, _ = self.version(program, on)
        if row is None:
            raise ValueError(f"There is no schedule for {program} in the week of {week_start(on):%d %b}.")
        week = self._week(row)
        person = next((a for a in week.get("associates", []) if a["name"] == name), None)
        if person is None:
            raise ValueError(f"{name} is not on this schedule.")
        span = shift_span(person["days"][day_index(on)])
        if not span:
            called = self.called_in_on(program, on, name)
            if called is None:
                raise ValueError(f"{name} has no shift on {on:%A %d %b} ({person['days'][day_index(on)]}).")
            span = (called["start"], called["end_min"])
        return row, week, span

    def plan_for(self, program: str, on: date, name: str, week: Dict[str, Any]) -> List[Dict[str, Any]]:
        """The person's planned breaks that day (a called-in shift takes the plan's breaks for that shift)."""
        found = planned(week, day_index(on), name)
        if not found:
            called = self.called_in_on(program, on, name)
            if called is not None:
                found = pattern_breaks(week, day_index(on), called["note"])
        return found

    def _records(self, program: str, on: date, row: Dict[str, Any]) -> Tuple[dict, dict, int]:
        """Attendance and actual breaks keyed for day_view: (offset, name[, idx]). A kept break move
        whose break no longer matches the plan (the version changed) is counted, not applied."""
        dates = {0: on, -1: on - timedelta(days=1)}
        attendance, actual, stale, acts = {}, {}, 0, {}
        for offset, d in dates.items():
            for r in self.store.list_activities(program, [d.isoformat()]):
                acts.setdefault((offset, r["associate"]), []).append(
                    {"id": r["id"], "kind": r["kind"], "start": r["start"], "end": r["end_min"],
                     "billable": bool(r["billable"]), "note": r["note"], "label": r["note"]})
            for r in self.store.list_attendance(program, [d.isoformat()]):
                attendance[(offset, r["associate"])] = {"status": r["status"], "from": r["from_min"], "to": r["to_min"],
                                                        "billable": bool(r["billable"])}
            source = row if d == on else self.version(program, d)[0]
            week = self._week(source) if source else {}
            for r in self.store.list_actual_breaks(program, [d.isoformat()]):
                plan = {b["idx"]: b for b in self.plan_for(program, d, r["associate"], week)} if week else {}
                if plan.get(r["idx"], {}).get("kind") != r["kind"]:
                    stale += 1
                    continue
                actual[(offset, r["associate"], r["idx"])] = r["start"]
        return attendance, actual, stale, acts

    def page(self, program: str, on: date, measure: str = "interval") -> Optional[Dict[str, Any]]:
        if measure not in MEASURES:
            raise ValueError(f"Unknown measure: {measure}.")
        row, note = self.version(program, on)
        if row is None:
            return None
        week = self._week(row)
        source = self.book.input_path(row["run_id"])
        if not source.is_file():
            raise ValueError(f"The input workbook kept with {row['label']} is missing, so the day cannot be worked "
                             "out. Run the week again, or ask the admin to restore the server's data folder.")
        inputs = read_inputs(source)
        attendance, actual, stale, acts = self._records(program, on, row)
        earlier, _ = self.version(program, on - timedelta(days=1))  # last night: the schedule holding yesterday
        before = (self._week(earlier), day_index(on - timedelta(days=1))) if earlier else None
        view = day_view(week, inputs, day_index(on), attendance, actual, measure, acts, before)
        return {"version": row, "note": note, "view": view, "stale": stale, "date": on,
                "week_start": row["week_start"], "day": day_index(on), "inputs": inputs,
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

    def move_break(self, program: str, on: date, name: str, idx: int, at: Optional[str], user_id: int,
                   suffix: str = "") -> None:
        """Move a break of the shift that starts on ``on`` to ``at`` (HH:MM), or back to the plan (None)."""
        row, week, span = self._shift(program, on, name)
        plan = {b["idx"]: b for b in self.plan_for(program, on, name, week)}
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
            check_break(week, day_index(on), 0, name, idx, m, kept, segment={
                "start": span[0], "end": span[1], "label": f"{hm(span[0])} - {hm(span[1])}",
                "planned": list(plan.values())})
            self.store.set_actual_break(program=program, shift_date=on.isoformat(), associate=name, idx=idx,
                                        kind=plan[idx]["kind"], start=m, user_id=user_id)
            what = f"{plan[idx]['kind']} moved {hm(was)} to {hm(m)}{suffix}"
        self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name, what=what, user_id=user_id)

    def break_advice(self, program: str, on: date, name: str, idx: int, at: str,
                     measure: str = "interval") -> Dict[str, Any]:
        """Gap warnings for a proposed break time and the best times for that break today."""
        _, week, span = self._shift(program, on, name)
        if idx not in {b["idx"] for b in self.plan_for(program, on, name, week)}:
            raise BreakRefused("That break is not on the plan.")
        m = _clock(at)
        if m is None:
            raise ValueError("The break time must be like 13:05.")
        page = self.page(program, on, measure)
        return advice(page["view"], page["inputs"], name, idx, m + (1440 if m < span[0] else 0))

    # ------------------------------------------------------------- activities: aux, meetings, overtime, VTO
    @staticmethod
    def _describe(kind: str, lo: int, hi: int, billable: bool) -> str:
        if kind == CALLED_IN:
            return f"Day off cancelled: called in {hm(lo)} - {hm(hi)}"
        if kind == "Overtime":
            return f"Overtime {hm(lo)} to {hm(hi)}"
        if kind == "VTO":
            return f"VTO, left at {hm(lo)} instead of {hm(hi)}"
        return f"{kind} {hm(lo)} to {hm(hi)} ({'billable' if billable else 'non-billable'})"

    def add_activity(self, program: str, on: date, name: str, kind: str, start: str, end: str, user_id: int,
                     billable: bool = False, note: str = "") -> int:
        """Record an activity for the shift that starts on ``on``: an aux (inside the shift), VTO (to the end
        of the shift) or overtime (touching the shift, at most 2 hours, keeping the rest gap)."""
        if kind not in ACTIVITY_KINDS:
            raise ValueError(f"Unknown activity: {kind}.")
        if kind == CALLED_IN:
            return self._call_in(program, on, name, start, end, user_id, note)
        row, week, span = self._shift(program, on, name)
        lo, hi = _clock(start), _clock(end)
        if lo is None or hi is None:
            raise ValueError("Give the start and end like 13:05.")
        lo += 1440 if lo < span[0] - OVERTIME_MAX else 0
        hi += 1440 if hi <= lo else 0
        if lo % STEP or hi % STEP:
            raise ValueError("Activities go in 5-minute steps.")
        status = next((r["status"] for r in self.store.list_attendance(program, [on.isoformat()])
                       if r["associate"] == name), "Present")
        if status in ABSENT:
            raise ValueError(f"{name} is marked {status.lower()} for this shift.")
        if kind == "Overtime":
            if not (hi == span[0] or lo == span[1]):
                raise ValueError(f"Overtime has to start when {name}'s shift ends ({hm(span[1])}) or end when it "
                                 f"starts ({hm(span[0])}).")
            if hi - lo > OVERTIME_MAX:
                raise ValueError(f"Overtime is offered up to {OVERTIME_MAX // 60} hours.")
            rest = int(float(week.get("settings", {}).get("rest_gap_hours") or 0) * 60)
            self._rest(program, on, row, name, lo, hi, rest)
        else:
            if lo < span[0] or hi > span[1]:
                raise ValueError(f"{kind} has to fall inside {name}'s shift ({hm(span[0])} to {hm(span[1])}).")
            if kind == "VTO" and hi != span[1]:
                raise ValueError(f"VTO runs to the end of the shift ({hm(span[1])}).")
        for r in self.store.list_activities(program, [on.isoformat()]):  # a call-in is the shift itself
            if r["associate"] == name and r["kind"] != CALLED_IN and r["start"] < hi and lo < r["end_min"]:
                raise ValueError(f"{name} already has {r['kind'].lower()} from {hm(r['start'])} to {hm(r['end_min'])}.")
        billable = bool(billable) and kind in AUX or kind == "Overtime"
        made = self.store.add_activity(program=program, shift_date=on.isoformat(), associate=name, kind=kind, start=lo,
                                       end_min=hi, billable=int(billable), note=" ".join(note.split())[:200],
                                       user_id=user_id)
        self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name,
                               what=self._describe(kind, lo, hi if kind != "VTO" else span[1], billable), user_id=user_id)
        return made

    def _call_in(self, program: str, on: date, name: str, start: str, end: str, user_id: int, note: str = "") -> int:
        """A day off cancelled: the person works a Shift Library shift that day, keeping the rest gap."""
        row, _ = self.version(program, on)
        if row is None:
            raise ValueError(f"There is no schedule for {program} in the week of {week_start(on):%d %b}.")
        week = self._week(row)
        person = next((a for a in week.get("associates", []) if a["name"] == name), None)
        if person is None:
            raise ValueError(f"{name} is not on this schedule.")
        d = day_index(on)
        if person["days"][d].strip().casefold() != "off":
            raise ValueError(f"{name} is on {person['days'][d]} that day, not off: add overtime instead.")
        label = f"{(start or '').strip()} - {(end or '').strip()}"
        library = {" ".join(x.split()).casefold(): x for x in week.get("shifts", [])}
        if " ".join(label.split()).casefold() not in library or not shift_span(label):
            raise ValueError(f"{label} is not a shift in this program's Shift Library.")
        label = library[" ".join(label.split()).casefold()]
        lo, hi = shift_span(label)
        rest = int(float(week.get("settings", {}).get("rest_gap_hours") or 0) * 60)
        self._rest(program, on, row, name, lo, hi, rest)
        if self.called_in_on(program, on, name) is not None:
            raise ValueError(f"{name} is already called in that day.")
        made = self.store.add_activity(program=program, shift_date=on.isoformat(), associate=name, kind=CALLED_IN,
                                       start=lo, end_min=hi, billable=1, note=label, user_id=user_id)
        self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name,
                               what=f"Day off cancelled: called in {label}", user_id=user_id)
        return made

    def cancel_activity(self, program: str, on: date, activity_id: int, user_id: int) -> None:
        row = self.store.get_activity(activity_id)
        if row is None or row["program"] != program or row["shift_date"] != on.isoformat():
            raise ValueError("That activity is not on this day.")
        if row["kind"] == CALLED_IN:
            return self._cancel_call_in(program, on, row, user_id)
        self.store.delete_activity(activity_id)
        self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=row["associate"], user_id=user_id,
                               what="Cancelled: " + self._describe(row["kind"], row["start"], row["end_min"],
                                                                   bool(row["billable"])))

    def _cancel_call_in(self, program: str, on: date, row: Dict[str, Any], user_id: int) -> None:
        """Back to the day off, but only once nothing else is recorded on that shift (nothing is left behind)."""
        name, day = row["associate"], [on.isoformat()]
        left = []
        for r in self.store.list_activities(program, day):
            if r["associate"] == name and r["kind"] != CALLED_IN:
                what = r["kind"].lower() if r["kind"] in AUX else r["kind"]
                left.append(f"{'a ' if r['kind'] in AUX else ''}{what} {hm(r['start'])} to {hm(r['end_min'])}")
        left += [f"the status {r['status']}" for r in self.store.list_attendance(program, day)
                 if r["associate"] == name and r["status"] != "Present"]
        left += [f"a moved {r['kind']}" for r in self.store.list_actual_breaks(program, day) if r["associate"] == name]
        if left:
            listed = left[0] if len(left) == 1 else ", ".join(left[:-1]) + " and " + left[-1]
            raise ValueError(f"{name} still has {listed} on this shift: cancel or set those back first.")
        self.store.delete_activity(row["id"])
        self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name, user_id=user_id,
                               what=f"Call-in cancelled: back to the day off (was {hm(row['start'])} - "
                                    f"{hm(row['end_min'])})")

    def meeting_slots(self, program: str, on: date, names: List[str], minutes: int, earliest: str, latest: str,
                      billable: bool = False, measure: str = "interval") -> List[Dict[str, Any]]:
        lo, hi = _clock(earliest), _clock(latest)
        if lo is None or hi is None or hi <= lo:
            raise ValueError("Give the window like 13:00 to 19:00, the end after the start.")
        if not names:
            raise ValueError("Pick who is in it.")
        page = self.page(program, on, measure)
        if page is None:
            raise ValueError("There is no schedule for this day.")
        return meeting_slots(page["view"], names, minutes, lo, hi, billable)

    def offers(self, page: Dict[str, Any], after: int = 0) -> Dict[str, List[Dict[str, Any]]]:
        """Overtime next to short intervals and VTO where the floor stays covered (from ``after``)."""
        week = self._week(page["version"])
        rest = float(week.get("settings", {}).get("rest_gap_hours") or 0)
        near = self.neighbours(page["version"]["program"], page["date"], page["version"])
        return {"overtime": overtime_offers(page["view"], week, page["day"], rest, after, near=near),
                "vto": vto_offers(page["view"], after), "next_known": near["next_known"]}

    def next_week_unknown(self, program: str, on: date) -> bool:
        """The last day of a schedule whose next one is not here: the rest gap to tomorrow cannot be checked."""
        return self.version(program, on + timedelta(days=1))[0] is None

    def cover_offers(self, page: Dict[str, Any], t: int) -> Dict[str, Any]:
        """For one interval: overtime next to people's shifts, and people off that day who could be called in."""
        week = self._week(page["version"])
        rest = float(week.get("settings", {}).get("rest_gap_hours") or 0)
        cell = next((c for c in page["view"]["cells"] if c["t"] == t), None)
        if cell is None:
            raise ValueError("Pick an interval of the day.")
        near = self.neighbours(page["version"]["program"], page["date"], page["version"])
        ot = overtime_offers(page["view"], week, page["day"], rest, only=t, near=near)
        return {"t": t, "end": t + page["view"]["interval"], "cell": cell, "overtime": ot[0]["offers"] if ot else [],
                "dayoff": dayoff_offers(page["view"], week, page["day"], rest, t, near=near),
                "next_known": near["next_known"]}

    def replan(self, page: Dict[str, Any], now: int = 0) -> Dict[str, Any]:
        """The autopilot's proposal for the breaks not yet started (nothing is kept)."""
        return replan(page["view"], page["inputs"], now)

    def apply_replan(self, program: str, on: date, moves: List[Tuple[str, int, int]], user_id: int) -> int:
        """Keep the approved moves (each checked again: the day may have changed since the preview)."""
        done = 0
        for name, idx, start in moves:
            self.move_break(program, on, name, idx, hm(start), user_id, suffix=" (autopilot)")
            done += 1
        return done

    def book_session(self, program: str, on: date, names: List[str], start: int, minutes: int, kind: str, user_id: int,
             billable: bool = False) -> None:
        """Book a session for everyone, or for nobody when anyone is not free then."""
        if kind not in AUX:
            raise ValueError(f"Book a meeting, training or coaching, not {kind}.")
        page = self.page(program, on)
        if page is None or not names:
            raise ValueError("Pick who is in it on a day with a schedule.")
        busy = []
        for name in names:
            seg = next((s for l in page["view"]["lanes"] if l["name"] == name for s in l["segments"]
                        if s["offset"] == 0), None)
            if seg is None or any(_busy(seg, t) for t in range(start, start + minutes, STEP)):
                busy.append(name)
        if busy:
            raise ValueError(f"Not free then: {', '.join(busy)}. Nobody was booked.")
        for name in names:
            self.add_activity(program, on, name, kind, hm(start), hm(start + minutes), user_id, billable=billable)

    # ------------------------------------------------------------- retention
    def cleanup(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        cutoff = datetime.fromtimestamp(now, EGYPT).date() - timedelta(days=KEEP_DAYS)
        return self.store.delete_day_before(cutoff.isoformat())
