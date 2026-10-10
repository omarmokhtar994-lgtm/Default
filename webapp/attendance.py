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
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .day import (ABSENT, AUX, CALLED_IN, CANCELLED, EXTRA_BREAKS, LATE_EARLY, MEASURES, OVERTIME_MAX, STATUSES, STEP, TIMED,
                  BreakRefused, _busy, advice, at_target,
                  check_break, day_view, dayoff_offers, meeting_slots, overtime_offers, pattern_breaks, planned,
                  read_inputs, replan, vto_offers)
from .notify import PRIVATE, left_out_now
from .schedules import EGYPT, KEEP_DAYS, ScheduleBook
from .versions import DAYS, channel_blocks, shift_span

HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
FALLBACK = "No version is marked in use for this week, so this is the tool's own schedule."
FALLBACK_READY = "No version is marked in use for this week, so this is the uploaded ready schedule."
ACTIVITY_KINDS = sorted(AUX) + list(EXTRA_BREAKS) + ["Overtime", "VTO", CALLED_IN]
WITH_MAX, WHY_MAX = 80, 200  # characters: who an aux is with, and why (Phase T)
DAY_OFF = "Day off cancelled"  # "+ Add" calls in someone off that day (owner, 2026-10-09)
QUARTER = 15  # typed call-in times go in 15-minute steps
# What RTA's "+ Add" offers in an interval (owner, 2026-10-08), grouped as the dialog shows them.
ADD_KINDS = {"Off the floor": ["Break", "Lunch", "Coaching", "Meeting", "Training", "System issue"],
             "Attendance": ["Unplanned leave", "Sick", "Late", "Left early"],
             "Hours": ["Overtime", "VTO"],
             "Day off": [DAY_OFF]}


def aux_details(kind: str, with_whom: str, why: str) -> Tuple[str, str]:
    """Who an aux (Coaching, Meeting, Training, System issue) is with and why, tidied: both are required, and a
    long answer is refused, never cut (owner, 2026-10-09). Anything else asks for neither: ("", "")."""
    if kind not in AUX:
        return "", ""
    with_whom, why = " ".join((with_whom or "").split()), " ".join((why or "").split())
    if not with_whom:
        raise ValueError(f"Say who the {kind.lower()} is with.")
    if not why:
        raise ValueError(f"Say why: a short reason for the {kind.lower()}.")
    if len(with_whom) > WITH_MAX:
        raise ValueError(f"Keep who it is with to {WITH_MAX} characters.")
    if len(why) > WHY_MAX:
        raise ValueError(f"Keep the reason to {WHY_MAX} characters.")
    return with_whom, why


def with_text(with_whom: str, why: str, with_dept: str = "") -> str:
    """", with Lina (Quality): monthly review" after an aux in the day log, the department when known (Phase U);
    "" when neither is known (records from before Phase T)."""
    who = f"{with_whom} ({with_dept})" if with_whom and with_dept else with_whom
    if who and why:
        return f", with {who}: {why}"
    return f", with {who}" if who else (f": {why}" if why else "")


def _tidy(text: str) -> str:
    return " ".join((text or "").split())


def week_start(on: date) -> date:
    """The Sunday that starts the week holding ``on``."""
    return on - timedelta(days=(on.weekday() + 1) % 7)


def day_index(on: date) -> int:
    return (on.weekday() + 1) % 7  # Sunday = 0


def hm(minute: int) -> str:
    minute %= 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _signed(hours: float) -> str:
    """+1:30 / −0:15 (hours as h:mm)."""
    minutes = round(abs(hours) * 60)
    return f"{'−' if hours < 0 else '+'}{minutes // 60}:{minutes % 60:02d}"


def _clock(text: str) -> Optional[int]:
    found = HHMM.match((text or "").strip())
    return int(found.group(1)) * 60 + int(found.group(2)) if found else None


def pick_version(versions: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Which of the versions covering a day it is read from: one in use, else the newest schedule made by the tool
    or uploaded (Phase W: by when its run's schedules were kept; within one engine run, after breaks before before
    breaks), with a note saying so; (None, "") when there is none. Where two weeks overlap (a program moving from
    Sunday to Monday starts), the later start counts."""
    kept: Dict[Any, float] = {}
    for v in versions:
        kept[v["run_id"]] = min(kept.get(v["run_id"], v["created"]), v["created"])
    order = (lambda v: (v["week_start"], kept[v["run_id"]], v["kind"] == "tool_after", v["created"]))
    chosen = max((v for v in versions if v["in_use"]), key=order, default=None)
    if chosen:
        return chosen, ""
    tools = sorted((v for v in versions if v["kind"] != "edited"), key=order, reverse=True)
    if not tools:
        return None, ""
    return tools[0], (FALLBACK_READY if tools[0]["kind"] == "ready" else FALLBACK)


def tomorrow_unchecked(on: date) -> str:
    """Said when no schedule holds the day after ``on`` (the last day of the latest week here)."""
    day = f"{on + timedelta(days=1):%A}"
    return f"Next week's schedule is not here yet, so the rest gap to {day} is not checked: check {day}'s start by hand."


def _group_kind(kind: str) -> str:
    """The Notifications page's kind (Phase AB) for an activity kind."""
    if kind in EXTRA_BREAKS:
        return "added_break"
    if kind in ("Overtime", "VTO"):
        return "overtime"
    return "called_in" if kind == CALLED_IN else "aux"


class DayBook:
    def __init__(self, store, book: ScheduleBook):
        self.store = store
        self.book = book
        self.notifier = None  # Phase AB: hands each change to its LOB's group rule (webapp/notify.py)

    def _log(self, program: str, on: date, name: str, what: str, user_id: int, kind: str, post: str = "",
             ref: str = "", before: str = "", after: str = "") -> None:
        """Keep a line in the day's log, and hand it to the LOB's group rule (Phase AB): ``post`` is the text a
        group may see (the why of an aux stays on the website); ``ref``, ``before`` and ``after`` let a change
        undone before it is posted drop out. The change is kept even if the hand-over fails; the failure is logged."""
        log_id = self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name, what=what,
                                        user_id=user_id)
        if self.notifier is None:
            return
        try:
            user = self.store.get_user(user_id) or {}
            self.notifier.queue(log_id, program, on.isoformat(), name, kind, post or what,
                                user.get("display_name", ""), ref=ref, before=before, after=after,
                                left_out=left_out_now())
        except Exception:  # noqa: BLE001 (the RTA change stands; the group post is what is lost, and logged)
            logging.getLogger(__name__).exception("group posts: could not queue a change for %s", program)

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
                     "billable": bool(r["billable"]), "note": r["note"], "label": r["note"],
                     "with_whom": r.get("with_whom", ""), "why": r.get("why", ""), "with_dept": r.get("with_dept", "")})
            for r in self.store.list_attendance(program, [d.isoformat()]):
                attendance[(offset, r["associate"])] = {"status": r["status"], "from": r["from_min"], "to": r["to_min"],
                                                        "billable": bool(r["billable"]),
                                                        "with_whom": r.get("with_whom", ""), "why": r.get("why", ""),
                                                        "with_dept": r.get("with_dept", "")}
            source = row if d == on else self.version(program, d)[0]
            week = self._week(source) if source else {}
            for r in self.store.list_actual_breaks(program, [d.isoformat()]):
                plan = {b["idx"]: b for b in self.plan_for(program, d, r["associate"], week)} if week else {}
                if plan.get(r["idx"], {}).get("kind") != r["kind"]:
                    stale += 1
                    continue
                actual[(offset, r["associate"], r["idx"])] = CANCELLED if r.get("cancelled") else r["start"]
        return attendance, actual, stale, acts

    def page(self, program: str, on: date, measure: str = "interval",
             extra: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """The day; ``extra`` (from ``add_item(..., dry_run=True)``) is counted as if it were recorded."""
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
        if extra and extra.get("break"):  # a break at another time (the break advice's channel effect)
            name, idx, minute = extra["break"]
            actual[(0, name, idx)] = minute
        elif extra and extra.get("status"):
            attendance[(0, extra["name"])] = {"status": extra["status"], "from": extra["from"], "to": extra["to"],
                                              "billable": extra["billable"]}
        elif extra and extra.get("kind"):
            acts.setdefault((0, extra["name"]), []).append(
                {"id": 0, "kind": extra["kind"], "start": extra["start"], "end": extra["end"],
                 "billable": extra["billable"], "note": "", "label": "",
                 "with_whom": extra.get("with_whom", ""), "why": extra.get("why", "")})
        earlier, _ = self.version(program, on - timedelta(days=1))  # last night: the schedule holding yesterday
        before = (self._week(earlier), day_index(on - timedelta(days=1))) if earlier else None
        channels, channel_problem = self._channel_inputs(program, on, week, inputs,
                                                         self.book.channel_path(row["run_id"]), earlier)
        view = day_view(week, inputs, day_index(on), attendance, actual, measure, acts, before, channels=channels)
        ratio, source_of_target = self.target_for(program, on, row, inputs)
        return {"version": row, "note": note, "view": view, "stale": stale, "date": on,
                "unlisted": self._unlisted(program, on, view, attendance, acts),
                "target": at_target(view["cells"], ratio), "target_source": source_of_target,
                "channel_problem": channel_problem,
                "week_start": row["week_start"], "day": day_index(on), "inputs": inputs,
                "log": self.store.list_day_log(program, on.isoformat())}

    def target_for(self, program: str, on: date, row: Optional[Dict[str, Any]] = None,
                   inputs: Optional[Dict[str, Any]] = None) -> Tuple[float, Dict[str, Any]]:
        """The interval target of the week holding ``on`` (Phase W): the one set for this program and week (with who
        set it), else the workbook's own "Target"; (0.9, workbook) when there is no schedule."""
        if row is None:
            row, _ = self.version(program, on)
        if row is None:
            return 0.9, {"kind": "workbook"}
        kept = self.store.get_interval_target(program, row["week_start"])
        if kept:
            return kept["target"] / 100, {"kind": "set", "by": kept.get("by_name") or "someone", "at": kept["at"]}
        if inputs is None:
            source = self.book.input_path(row["run_id"])
            inputs = read_inputs(source) if source.is_file() else {}
        return float(inputs.get("target", 0.9)), {"kind": "workbook"}

    def _unlisted(self, program: str, on: date, view: Dict[str, Any], attendance: Dict[Any, Any],
                  acts: Dict[Any, Any]) -> List[Dict[str, str]]:
        """People with this day's records who are not on the floor list (Phase W: kept from another schedule of
        the week), each with what was recorded, in words. Break moves are counted as stale instead."""
        shown = {lane["name"] for lane in view["lanes"]}
        said: Dict[str, List[str]] = {}
        for (offset, name), mark in attendance.items():
            if offset == 0 and name not in shown:
                text = mark["status"]
                if mark["status"] == "Late" and mark.get("to") is not None:
                    text += f", arrived {hm(mark['to'])}"
                elif mark["status"] == "Left early" and mark.get("from") is not None:
                    text += f", left at {hm(mark['from'])}"
                said.setdefault(name, []).append(text)
        for (offset, name), items in acts.items():
            if offset == 0 and name not in shown:
                said.setdefault(name, []).extend(a["kind"] for a in items)
        for r in self.store.list_channel_moves(program, [on.isoformat()]):
            if r["associate"] not in shown:
                said.setdefault(r["associate"], []).append("a channel change")
        return [{"name": name, "what": ", ".join(dict.fromkeys(what))} for name, what in sorted(said.items())]

    # ------------------------------------------------------------- channels on the day (Phase V)
    def _channel_inputs(self, program: str, on: date, week: Dict[str, Any], inputs: Dict[str, Any], source,
                        earlier: Optional[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
        """What the day view needs to count channels (None without channel needs), and why it cannot when the tabs
        no longer read (said on the page; the day itself still shows). ``source`` is the run's channel needs
        (Phase Z: ``ScheduleBook.channel_path``), None when it has none."""
        from .channel_people import ChannelPeople
        from .channels import read_channels
        if source is None:
            return None, ""
        try:
            setup = read_channels(source, inputs["interval"])
        except ValueError as exc:
            return None, f"The channel tabs of this schedule's workbook cannot be read, so channels are not shown: {exc}"
        if not setup:
            return None, ""
        d = day_index(on)
        blocks: Dict[Tuple[int, str], List[Tuple[int, int, str]]] = {}
        for a in week.get("associates", []):
            found = channel_blocks(week, d, a["name"])
            if found:
                blocks[(0, a["name"])] = [(b["start"], b["end"], b["channel"]) for b in found]
        if earlier:  # last night's overnight blocks, read past midnight
            prev, pd = self._week(earlier), day_index(on - timedelta(days=1))
            for a in prev.get("associates", []):
                found = channel_blocks(prev, pd, a["name"])
                if found:
                    blocks[(-1, a["name"])] = [(b["start"] - 1440, b["end"] - 1440, b["channel"]) for b in found]
        moves: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
        for offset, when in ((0, on), (-1, on - timedelta(days=1))):
            for r in self.store.list_channel_moves(program, [when.isoformat()]):
                moves.setdefault((offset, r["associate"]), []).append(
                    {"id": r["id"], "start": r["start"] + 1440 * offset, "end": r["end_min"] + 1440 * offset,
                     "channel": r["channel"]})
        clock = datetime.now(EGYPT)
        after = clock.hour * 60 + clock.minute if on == clock.date() else (0 if on > clock.date() else 1440)
        return {"setup": setup, "skills": ChannelPeople(self.store).skills_for_unit(program),
                "language_rows": inputs["languages"], "blocks": blocks, "moves": moves, "after": after,
                "gaps": (inputs.get("gap_min"), inputs.get("gap_max")), "today": on == clock.date()}, ""

    def channel_move(self, program: str, on: date, name: str, start: Any, end: Any, channel: str,
                     user_id: int) -> int:
        """Put ``name`` on ``channel`` from ``start`` to ``end`` (minutes, or HH:MM) for the shift that starts on
        ``on``; kept and said in the day log. Refused outside the shift, off the 5-minute steps, in all-channels
        time, or for a channel the person cannot work."""
        from .channel_day import letter_at
        from .channel_people import ChannelPeople, can_work
        from .channels import CHANNELS, blended_at, read_channels
        row, week, span = self._shift(program, on, name)
        lo = start if isinstance(start, int) else _clock(str(start))
        hi = end if isinstance(end, int) else _clock(str(end))
        if lo is None or hi is None:
            raise ValueError("Give the start and end like 15:00.")
        lo += 1440 if lo < span[0] else 0
        hi += 1440 if hi <= lo else 0
        if lo % STEP or hi % STEP:
            raise ValueError("Channel changes go in 5-minute steps.")
        if lo < span[0] or hi > span[1]:
            raise ValueError(f"A channel change has to fall inside {name}'s shift ({hm(span[0])} to {hm(span[1])}).")
        if channel not in CHANNELS:
            raise ValueError("Pick Phone, Chat or Email.")
        if channel not in can_work(ChannelPeople(self.store).skills_for_unit(program), name):
            raise ValueError(f"{name} cannot work {CHANNELS[channel]} (see Associate channels).")
        needs, source = self.book.channel_path(row["run_id"]), self.book.input_path(row["run_id"])
        setup = read_channels(needs, read_inputs(source)["interval"]) if needs is not None else None
        if not setup:
            raise ValueError("This schedule's workbook has no channel tabs.")
        d = day_index(on)
        if any(blended_at(setup, d, t) for t in range(lo, hi, STEP)):
            raise ValueError("That is an all-channels time: there everyone covers every channel they work.")
        blocks = [(b["start"], b["end"], b["channel"]) for b in channel_blocks(week, d, name)]
        moved = [{"id": r["id"], "start": r["start"], "end": r["end_min"], "channel": r["channel"]}
                 for r in self.store.list_channel_moves(program, [on.isoformat()]) if r["associate"] == name]
        was = letter_at(blocks, moved, lo, False)
        made = self.store.add_channel_move(program=program, shift_date=on.isoformat(), associate=name, start=lo,
                                           end_min=hi, channel=channel, user_id=user_id)
        what = f"{CHANNELS[channel]} from {hm(lo)} to {hm(hi)}" + (f" (was {CHANNELS[was]})" if was in CHANNELS else "")
        self._log(program, on, name, what, user_id, "channel", ref=f"channel:{made}", after="on")
        return made

    def cancel_channel_move(self, program: str, on: date, move_id: int, user_id: int) -> None:
        from .channels import CHANNELS
        r = self.store.get_channel_move(move_id)
        if r is None or r["program"] != program or r["shift_date"] != on.isoformat():
            raise ValueError("That channel change is not on this day.")
        self.store.delete_channel_move(move_id)
        self._log(program, on, r["associate"], f"{CHANNELS[r['channel']]} from {hm(r['start'])} to {hm(r['end_min'])} "
                  "taken back", user_id, "channel", ref=f"channel:{move_id}", before="on")

    def move_activity(self, program: str, on: date, activity_id: int, start: str, user_id: int) -> int:
        """Move an aux, or a break or lunch added on the day, to ``start`` (HH:MM), the same length, with the same
        who and why; checked like a new booking (the original stays when the new time is refused)."""
        r = self.store.get_activity(activity_id)
        if r is None or r["program"] != program or r["shift_date"] != on.isoformat():
            raise ValueError("That activity is not on this day.")
        if r["kind"] not in AUX and r["kind"] not in EXTRA_BREAKS:
            raise ValueError(f"{r['kind']} cannot be moved here.")
        lo = _clock(start)
        if lo is None:
            raise ValueError("Give the new start like 16:00.")
        fields = {k: v for k, v in r.items() if k != "id"}
        self.store.delete_activity(activity_id)
        try:
            rec = self.add_activity(program, on, r["associate"], r["kind"], start, hm(lo + r["end_min"] - r["start"]),
                                    user_id, billable=bool(r["billable"]), note=r["note"], dry_run=True,
                                    with_whom=r.get("with_whom", ""), why=r.get("why", ""),
                                    with_dept=r.get("with_dept", ""))
        except ValueError:
            self.store.add_activity(**fields)
            raise
        made = self.store.add_activity(**{**fields, "start": rec["start"], "end_min": rec["end"], "user_id": user_id,
                                          "at": time.time()})
        self._log(program, on, r["associate"], f"{r['kind']} moved {hm(r['start'])} to {hm(rec['start'])}", user_id,
                  _group_kind(r["kind"]), ref=f"activity:{made}", before=hm(r["start"]), after=hm(rec["start"]))
        return made

    # ------------------------------------------------------------- what people record
    def set_status(self, program: str, on: date, name: str, status: str, user_id: int,
                   start: str = "", end: str = "", billable: bool = False, dry_run: bool = False,
                   with_whom: str = "", why: str = "", with_dept: str = "") -> Dict[str, Any]:
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
        with_whom, why, with_dept = (_tidy(with_whom), _tidy(why), _tidy(with_dept)) if status in AUX else ("", "", "")
        post = what + with_text(with_whom, "", with_dept)  # Phase AB: what a group may see, never the why
        what += with_text(with_whom, why, with_dept)
        record = {"name": name, "status": status, "from": lo, "to": hi, "billable": bool(billable) and status in AUX,
                  "what": what, "span": span, "with_whom": with_whom, "why": why, "with_dept": with_dept}
        if dry_run:
            return record
        was = next((r["status"] for r in self.store.list_attendance(program, [on.isoformat()])
                    if r["associate"] == name), "Present")
        self.store.set_attendance(program=program, shift_date=on.isoformat(), associate=name, status=status,
                                  from_min=lo, to_min=hi, billable=int(bool(billable) and status in AUX),
                                  user_id=user_id, with_whom=with_whom, why=why, with_dept=with_dept)
        kind = "late" if status in LATE_EARLY else "aux" if status in AUX else PRIVATE  # sick, leave, present
        self._log(program, on, name, what, user_id, kind, post=post, ref=f"status:{name}", before=was, after=status)
        return record

    def move_break(self, program: str, on: date, name: str, idx: int, at: Optional[str], user_id: int,
                   suffix: str = "") -> None:
        """Move a break of the shift that starts on ``on`` to ``at`` (HH:MM), or back to the plan (None)."""
        row, week, span = self._shift(program, on, name)
        plan = {b["idx"]: b for b in self.plan_for(program, on, name, week)}
        if idx not in plan:
            raise BreakRefused("That break is not on the plan.")
        rows = {r["idx"]: r for r in self.store.list_actual_breaks(program, [on.isoformat()])
                if r["associate"] == name and plan.get(r["idx"], {}).get("kind") == r["kind"]}
        kept = {(0, name, i): CANCELLED if r.get("cancelled") else r["start"] for i, r in rows.items()}
        was = rows[idx]["start"] if idx in rows else plan[idx]["start"]
        was_cancelled = bool(rows.get(idx, {}).get("cancelled"))
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
                                        kind=plan[idx]["kind"], start=m, user_id=user_id, cancelled=0, why="")
            what = (f"{plan[idx]['kind']} brought back at {hm(m)}{suffix}" if was_cancelled else
                    f"{plan[idx]['kind']} moved {hm(was)} to {hm(m)}{suffix}")
        self._log(program, on, name, what, user_id, "break", ref=f"break:{name}:{idx}",
                  before="cancelled" if was_cancelled else hm(was), after=hm(plan[idx]["start"] if at is None else m))

    def cancel_break(self, program: str, on: date, name: str, idx: int, why: str, user_id: int,
                     now: Optional[int] = None) -> None:
        """Cancel a break of the shift that starts on ``on`` (Phase AD): the person stays on the floor. ``why`` is
        kept on the site and in exports, never in the group post. ``now`` (minutes, today only) refuses a break that
        has started."""
        why = _tidy(why)[:200]
        if not why:
            raise ValueError("Say why the break is cancelled.")
        row, week, span = self._shift(program, on, name)
        plan = {b["idx"]: b for b in self.plan_for(program, on, name, week)}
        if idx not in plan:
            raise BreakRefused("That break is not on the plan.")
        kept = next((r for r in self.store.list_actual_breaks(program, [on.isoformat()])
                     if r["associate"] == name and r["idx"] == idx and r["kind"] == plan[idx]["kind"]), None)
        if kept and kept.get("cancelled"):
            raise ValueError(f"{name}'s {plan[idx]['kind']} is already cancelled.")
        start = kept["start"] if kept else plan[idx]["start"]
        if now is not None and start <= now:
            raise ValueError("That break has started: it cannot be cancelled.")
        kind = plan[idx]["kind"]
        self.store.set_actual_break(program=program, shift_date=on.isoformat(), associate=name, idx=idx, kind=kind,
                                    start=start, user_id=user_id, cancelled=1, why=why)
        self._log(program, on, name, f"{kind} cancelled ({hm(start)}): {why}", user_id, "break",
                  post=f"{kind} at {hm(start)} cancelled", ref=f"break:{name}:{idx}", before=hm(start),
                  after="cancelled")

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
        m += 1440 if m < span[0] else 0
        found = advice(page["view"], page["inputs"], name, idx, m)
        if page["view"].get("channels") is not None:  # Phase V: what the move does to the channels
            old = {w["text"] for w in page["view"]["channels"]["warnings"]}
            moved = self.page(program, on, measure, extra={"break": (name, idx, m)})["view"]["channels"]
            found["channels"] = [w["text"] for w in moved["warnings"] if w["text"] not in old]
        return found

    # ------------------------------------------------------------- activities: aux, meetings, overtime, VTO
    @staticmethod
    def _describe(kind: str, lo: int, hi: int, billable: bool, with_whom: str = "", why: str = "",
                  with_dept: str = "") -> str:
        if kind == CALLED_IN:
            return f"Day off cancelled: called in {hm(lo)} - {hm(hi)}"
        if kind == "Overtime":
            return f"Overtime {hm(lo)} to {hm(hi)}"
        if kind == "VTO":
            return f"VTO {hm(lo)} to {hm(hi)}"  # any stretch of the shift (owner, 2026-10-08)
        if kind in EXTRA_BREAKS:
            return f"{kind} {hm(lo)} to {hm(hi)}"
        return (f"{kind} {hm(lo)} to {hm(hi)} ({'billable' if billable else 'non-billable'})"
                + with_text(with_whom, why, with_dept))

    def add_activity(self, program: str, on: date, name: str, kind: str, start: str, end: str, user_id: int,
                     billable: bool = False, note: str = "", dry_run: bool = False, with_whom: str = "",
                     why: str = "", with_dept: str = "") -> Any:
        """Record an activity for the shift that starts on ``on``: an aux, a break or lunch added on the day,
        or VTO (each inside the shift), or overtime (touching the shift, at most 2 hours, keeping the rest
        gap). Returns its id; with ``dry_run`` every check runs, nothing is kept, and the record is returned."""
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
            if hi <= lo:
                raise ValueError("The end time must be after the start time.")
        if kind in EXTRA_BREAKS:  # not on top of a break the person already has (as planned or as moved)
            page = self.page(program, on)
            seg = next((x for l in page["view"]["lanes"] if l["name"] == name for x in l["segments"]
                        if x["offset"] == 0), None) if page else None
            for b in (seg or {}).get("breaks", []):
                if b["start"] < hi and lo < b["start"] + b["minutes"]:
                    raise ValueError(f"{name} is already on {b['kind'].lower()} from {hm(b['start'])} to "
                                     f"{hm(b['start'] + b['minutes'])} then.")
        for r in self.store.list_activities(program, [on.isoformat()]):  # a call-in is the shift itself
            if r["associate"] == name and r["kind"] != CALLED_IN and r["start"] < hi and lo < r["end_min"]:
                raise ValueError(f"{name} already has {r['kind'].lower()} from {hm(r['start'])} to {hm(r['end_min'])}.")
        billable = bool(billable) and kind in AUX or kind == "Overtime"
        with_whom, why, with_dept = (_tidy(with_whom), _tidy(why), _tidy(with_dept)) if kind in AUX else ("", "", "")
        what = self._describe(kind, lo, hi, billable, with_whom, why, with_dept)
        if dry_run:
            return {"name": name, "kind": kind, "start": lo, "end": hi, "billable": billable, "what": what,
                    "with_whom": with_whom, "why": why, "with_dept": with_dept}
        made = self.store.add_activity(program=program, shift_date=on.isoformat(), associate=name, kind=kind, start=lo,
                                       end_min=hi, billable=int(billable), note=" ".join(note.split())[:200],
                                       user_id=user_id, with_whom=with_whom, why=why, with_dept=with_dept)
        self._log(program, on, name, what, user_id, _group_kind(kind),
                  post=self._describe(kind, lo, hi, billable, with_whom, "", with_dept), ref=f"activity:{made}",
                  after="on")
        return made

    def add_item(self, program: str, on: date, name: str, what: str, start: str, minutes: int, user_id: int,
                 billable: bool = False, note: str = "", dry_run: bool = False, end: str = "", with_whom: str = "",
                 why: str = "", with_dept: str = "", side: str = "") -> Dict[str, Any]:
        """Anything RTA's "+ Add" offers: Unplanned leave or Sick (the whole shift); Late (``start`` is when
        they arrived); Left early (``start`` is when they left); a break, lunch, aux, overtime or VTO from
        ``start`` for ``minutes``; a day off cancelled from ``start`` to ``end``. Overtime with ``side``
        "before" or "after" (Phase AA) ignores ``start``: it ends when the person's shift starts, or starts when it
        ends. Returns what was recorded ("text") and the minutes it covers (lo, hi)."""
        if what == DAY_OFF:
            rec = self._call_in(program, on, name, start, end, user_id, note, dry_run=True)
            if not dry_run:
                self._call_in(program, on, name, start, end, user_id, note)
            return {"text": rec["what"], "lo": rec["start"], "hi": rec["end"], "record": rec}
        if what in ABSENT or what in LATE_EARLY:
            arrived = start if what == "Late" else ""
            left = start if what == "Left early" else ""
            rec = self.set_status(program, on, name, what, user_id, start=left, end=arrived, dry_run=True)
            span = rec["span"]
            lo = span[0] if rec["from"] is None else rec["from"]
            hi = span[1] if rec["to"] is None else rec["to"]
            if not dry_run:
                self.set_status(program, on, name, what, user_id, start=left, end=arrived)
            return {"text": rec["what"], "lo": lo, "hi": hi, "record": rec}
        if what not in ACTIVITY_KINDS or what == CALLED_IN:
            raise ValueError(f"Unknown: {what}.")
        if what == "Overtime" and side in ("before", "after"):
            if not isinstance(minutes, int) or minutes <= 0 or minutes % STEP:
                raise ValueError("Pick a length in 5-minute steps.")
            span = self._shift(program, on, name)[2]
            if side == "before" and span[0] - minutes < 0:
                length = f"{minutes} min" if minutes < 60 else f"{minutes // 60} h" + (
                    f" {minutes % 60}" if minutes % 60 else "")
                raise ValueError(f"{name}'s shift starts at {hm(span[0])}, so {length} of overtime before it would "
                                 "start the day before. Pick a shorter length, or After the shift.")
            start = hm(span[1] if side == "after" else span[0] - minutes)
        lo = _clock(start)
        if lo is None:
            raise ValueError("Give the start like 13:05.")
        if not isinstance(minutes, int) or minutes <= 0 or minutes % STEP:
            raise ValueError("Pick a length in 5-minute steps.")
        end = hm(lo + minutes)
        rec = self.add_activity(program, on, name, what, start, end, user_id, billable=billable, note=note,
                                dry_run=True, with_whom=with_whom, why=why, with_dept=with_dept)
        if not dry_run:
            self.add_activity(program, on, name, what, start, end, user_id, billable=billable, note=note,
                              with_whom=with_whom, why=why, with_dept=with_dept)
        return {"text": rec["what"], "lo": rec["start"], "hi": rec["end"], "record": rec}

    def preview_item(self, program: str, on: date, name: str, what: str, start: str, minutes: int,
                     billable: bool = False, measure: str = "interval", end: str = "",
                     side: str = "") -> Dict[str, str]:
        """What adding this would do to the floor, before anything is kept: the tightest buffer over the
        intervals it touches, now and after. Refused the same way the real thing is (ValueError)."""
        found = self.add_item(program, on, name, what, start, minutes, 0, billable=billable, dry_run=True, end=end,
                              side=side)
        lo, hi = found["lo"], found["hi"]
        before = self.page(program, on, measure)["view"]
        after = self.page(program, on, measure, extra=found["record"])["view"]
        step = before["interval"]

        def tightest(view: Dict[str, Any]) -> Optional[float]:
            got = [c["pm"] for c in view["cells"] if c["pm"] is not None and c["t"] < hi and lo < c["t"] + step]
            return min(got) if got else None

        was, now = tightest(before), tightest(after)
        said = found["text"] if hm(lo) in found["text"] else f"{found['text']} ({hm(lo)} to {hm(hi)})"
        if was is None or now is None:
            result = {"text": f"{said}: no demand is set for those intervals.", "level": "ok"}
        else:
            level = "ok" if now >= 0 else ("warn" if now > -step / 60 else "bad")
            result = {"text": f"{said}: the floor at its tightest goes from {_signed(was)} to {_signed(now)}.",
                      "level": level}
        if before.get("channels") is not None and after.get("channels") is not None:  # Phase V
            old = {w["text"] for w in before["channels"]["warnings"]}
            result["channels"] = [w["text"] for w in after["channels"]["warnings"] if w["text"] not in old]
            result["better"] = []
            if result["channels"]:
                result["level"] = "bad"
                result["better"] = self._better_times(program, on, name, what, lo, minutes, billable, measure, end,
                                                      before, old)
        return result

    def _better_times(self, program: str, on: date, name: str, what: str, lo: int, minutes: int, billable: bool,
                      measure: str, end: str, before: Dict[str, Any], old: set) -> List[str]:
        """Up to two quarter-hour starts, nearest first (within 4 hours, inside the shift), at which the same
        booking makes no new channel warning."""
        seg = next((x for lane in before["lanes"] if lane["name"] == name for x in lane["segments"]
                    if x["offset"] == 0), None)
        if seg is None or not isinstance(minutes, int):
            return []
        starts = sorted((s for s in range(seg["start"] - seg["start"] % 15, seg["end"] - minutes + 1, 15)
                         if s != lo and abs(s - lo) <= 240 and s >= seg["start"]), key=lambda s: (abs(s - lo), s))
        good: List[str] = []
        for s in starts[:16]:
            try:
                rec = self.add_item(program, on, name, what, hm(s), minutes, 0, billable=billable, dry_run=True,
                                    end=end)
            except ValueError:
                continue
            view = self.page(program, on, measure, extra=rec["record"])["view"]
            if not {w["text"] for w in view["channels"]["warnings"]} - old:
                good.append(hm(s))
                if len(good) == 2:
                    break
        return good

    def off_today(self, program: str, on: date) -> List[Tuple[str, str]]:
        """Who is off on ``on`` in the schedule read for it and not called in yet: (name, language)."""
        row, _ = self.version(program, on)
        if row is None:
            return []
        called = {r["associate"] for r in self.store.list_activities(program, [on.isoformat()]) if r["kind"] == CALLED_IN}
        return sorted((a["name"], a.get("language", "")) for a in self._week(row).get("associates", [])
                      if a["days"][day_index(on)].strip().casefold() == "off" and a["name"] not in called)

    def shift_library(self, program: str, on: date) -> List[Tuple[str, int, int]]:
        """The Shift Library of the schedule read for ``on``: (label, start, end) in start order."""
        row, _ = self.version(program, on)
        found = [(x, *shift_span(x)) for x in (self._week(row).get("shifts", []) if row else []) if shift_span(x)]
        return sorted(found, key=lambda x: (x[1], x[2]))

    def _call_in(self, program: str, on: date, name: str, start: str, end: str, user_id: int, note: str = "",
                 dry_run: bool = False) -> Any:
        """A day off cancelled: the person works a Shift Library shift that day, or typed times (15-minute
        steps, 1 hour up to the library's longest shift; breaks follow the plan's only for a shift someone
        works), keeping the rest gap. With ``dry_run`` every check runs and the record is returned."""
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
        lo, hi = _clock(start), _clock(end)
        if lo is None or hi is None:
            raise ValueError("Give the start and end like 08:00.")
        hi += 1440 if hi <= lo else 0  # ends after midnight
        spans = [(shift_span(x), x) for x in week.get("shifts", []) if shift_span(x)]
        label = next((x for span, x in spans if span == (lo, hi)), "")  # a Shift Library shift
        if not label:
            longest = max((span[1] - span[0] for span, _ in spans), default=12 * 60)
            if lo % QUARTER or hi % QUARTER:
                raise ValueError("Typed times go in 15-minute steps, like 08:00 or 08:15.")
            if not 60 <= hi - lo <= longest:
                raise ValueError(f"A called-in shift is at least 1 hour and at most {longest / 60:g} hours, the "
                                 "longest shift in the Shift Library.")
            label = f"{hm(lo)} - {hm(hi)}"
        rest = int(float(week.get("settings", {}).get("rest_gap_hours") or 0) * 60)
        self._rest(program, on, row, name, lo, hi, rest)
        if self.called_in_on(program, on, name) is not None:
            raise ValueError(f"{name} is already called in that day.")
        if dry_run:
            return {"name": name, "kind": CALLED_IN, "start": lo, "end": hi, "billable": True,
                    "what": f"Day off cancelled: called in {label}"}
        made = self.store.add_activity(program=program, shift_date=on.isoformat(), associate=name, kind=CALLED_IN,
                                       start=lo, end_min=hi, billable=1, note=label, user_id=user_id)
        self._log(program, on, name, f"Day off cancelled: called in {label}", user_id, "called_in",
                  ref=f"callin:{made}", after="on")
        return made

    def cancel_activity(self, program: str, on: date, activity_id: int, user_id: int) -> None:
        row = self.store.get_activity(activity_id)
        if row is None or row["program"] != program or row["shift_date"] != on.isoformat():
            raise ValueError("That activity is not on this day.")
        if row["kind"] == CALLED_IN:
            return self._cancel_call_in(program, on, row, user_id)
        self.store.delete_activity(activity_id)
        self._log(program, on, row["associate"], "Cancelled: " + self._describe(row["kind"], row["start"],
                                                                                row["end_min"], bool(row["billable"])),
                  user_id, _group_kind(row["kind"]), ref=f"activity:{activity_id}", before="on")

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
        left += [f"a {'cancelled' if r.get('cancelled') else 'moved'} {r['kind']}"
                 for r in self.store.list_actual_breaks(program, day) if r["associate"] == name]
        if left:
            listed = left[0] if len(left) == 1 else ", ".join(left[:-1]) + " and " + left[-1]
            raise ValueError(f"{name} still has {listed} on this shift: cancel or set those back first.")
        self.store.delete_activity(row["id"])
        self._log(program, on, name, f"Call-in cancelled: back to the day off (was {hm(row['start'])} - "
                  f"{hm(row['end_min'])})", user_id, "called_in", ref=f"callin:{row['id']}", before="on")

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
             billable: bool = False, with_whom: str = "", why: str = "", with_dept: str = "") -> None:
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
            self.add_activity(program, on, name, kind, hm(start), hm(start + minutes), user_id, billable=billable,
                              with_whom=with_whom, why=why, with_dept=with_dept)

    # ------------------------------------------------------------- retention
    def cleanup(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        cutoff = datetime.fromtimestamp(now, EGYPT).date() - timedelta(days=KEEP_DAYS)
        return self.store.delete_day_before(cutoff.isoformat())
