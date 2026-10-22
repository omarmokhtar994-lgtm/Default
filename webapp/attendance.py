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

import contextvars
from collections import OrderedDict
import copy
import functools
import inspect
import json
import os
import logging
import re
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .clock import HOME, SHOWN, minute_now, pick_zone
from .day import (ABSENT, AUX, BIO, CALLED_IN, CANCELLED, EXTRA_BREAKS, LATE_EARLY, MEASURES, OVERTIME_MAX, STATUSES, STEP, TIMED,
                  BreakRefused, _busy, advice, at_target,
                  check_break, day_view, dayoff_offers, dayoff_proposals, meeting_slots, overtime_offers, pattern_breaks, planned,
                  read_inputs, replan, vto_offers, window_view)
from .notify import PRIVATE, left_out_now
from .schedules import EGYPT, KEEP_DAYS, ScheduleBook
from .window_tools import by_date, dates_of, in_own_day, rebase
from .versions import DAYS, channel_blocks, shift_span

HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
FALLBACK = "No version is marked in use for this week, so this is the tool's own schedule."
FALLBACK_READY = "No version is marked in use for this week, so this is the uploaded ready schedule."
ACTIVITY_KINDS = sorted(AUX) + list(EXTRA_BREAKS) + ["Overtime", "VTO", CALLED_IN]
WITH_MAX, WHY_MAX = 80, 200  # characters: who an aux is with, and why (Phase T)
# Phase AJ: someone not on the roster logging in to cover intervals (owner, 2026-10-15: "TM or support")
COVER_ROLES = ("Team manager", "Support")
COVER_NAME_MAX, COVER_MAX = 60, 12 * 60  # characters of a typed name; minutes one cover may last
DAY_OFF = "Day off cancelled"  # "+ Add" calls in someone off that day (owner, 2026-10-09)
QUARTER = 15  # typed call-in times go in 15-minute steps
# What RTA's "+ Add" offers in an interval (owner, 2026-10-08), grouped as the dialog shows them.
ADD_KINDS = {"Off the floor": ["Break", "Lunch", "Coaching", "Meeting", "Training", "System issue", "Task", "Bio break"],
             "Attendance": ["Unplanned leave", "Sick", "Public holiday", "Exam leave", "Late", "Left early"],
             "Hours": ["Overtime", "VTO"],
             "Day off": [DAY_OFF]}


def aux_details(kind: str, with_whom: str, why: str) -> Tuple[str, str]:
    """Who an aux (Coaching, Meeting, Training, System issue) is with and why, tidied: both are required, and a
    long answer is refused, never cut (owner, 2026-10-09). Anything else asks for neither: ("", "")."""
    if kind not in AUX or kind == BIO:
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


def swapped_week(week: Dict[str, Any], day: int, first: str, second: str) -> Dict[str, Any]:
    """A copy of ``week`` where two people swap their shift, breaks and channel stretches on ``day`` (Phase AG)."""
    out = copy.deepcopy(week)
    other = {first: second, second: first}
    cells = {a["name"]: a["days"][day] for a in out.get("associates", []) if a["name"] in other}
    for a in out.get("associates", []):
        if a["name"] in other and other[a["name"]] in cells:
            a["days"][day] = cells[other[a["name"]]]
    for key in ("breaks", "channels"):
        for item in out.get(key) or []:
            if item.get("day") == DAYS[day] and item.get("associate") in other:
                item["associate"] = other[item["associate"]]
    return out


def hm(minute: int) -> str:
    return plain_hm(minute + SHOWN.get())  # Phase AI: in the zone the RTA shows


def plain_hm(minute: int) -> str:
    """A time in the schedule's own time, whatever the page shows: for times handed on to be read again."""
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


PAGE_KEEP = 30  # Phase AV: seconds a built day is kept at most, as a safety net behind the write counter
PAGE_MAX = 256  # and how many days are kept
VERIFY_PAGES = os.environ.get("SCHEDULER_VERIFY_PAGES") == "1"  # tests: on every hit, build the day again and compare


def fingerprint(x: Any) -> Any:
    """A day as plain comparable values (functions by name, the replan counters by their numbers), for ``VERIFY_PAGES``."""
    t = type(x)
    if t is dict:
        return {k: fingerprint(v) for k, v in x.items()}
    if t in (list, tuple):
        return [fingerprint(v) for v in x]
    if t in (str, int, float, bool, type(None), date):
        return x
    if callable(x):
        return "<function>"
    if hasattr(x, "channel") and hasattr(x, "language"):  # ChannelHold
        return ["hold", x.day, x.step, fingerprint(x.channel), fingerprint(x.language)]
    return repr(x)


def first_difference(a: Any, b: Any, path: str = "") -> str:
    if type(a) != type(b):
        return f"{path}: {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                return f"{path}/{k}: only in one"
            found = first_difference(a[k], b[k], f"{path}/{k}")
            if found:
                return found
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            found = first_difference(x, y, f"{path}[{i}]")
            if found:
                return found
        return ""
    return "" if a == b else f"{path}: {a!r} != {b!r}"
UNDO_DEPTH = 2  # owner, 2026-10-11: "undo last move or 2 ... max 2 moves back"; your own only (answer 2)
NOTHING_TO_UNDO = "Nothing of yours to undo on this day: Undo goes back 2 changes at most."
_ACTION: contextvars.ContextVar = contextvars.ContextVar("day_action", default=None)


@dataclass
class DayAction:
    """One RTA change in the day's journal (Phase AD): a single change, a bulk change (Fix breaks, Rescue the day,
    Change several breaks) or an undo. ``id`` is its journal row while it runs; ``logs`` the day-log lines it made."""
    program: str
    on: date
    user_id: int
    label: str
    kind: str
    id: Optional[int] = None
    logs: List[Tuple[int, str, str]] = field(default_factory=list)
    hold: bool = False  # an undo's lines wait for Send (the change it takes back was a posted bulk change)
    silent: bool = False  # an undo's lines are never posted (the change it takes back never was)


def _diff(before: Dict[str, Dict[tuple, Dict[str, Any]]], after: Dict[str, Dict[tuple, Dict[str, Any]]]
          ) -> List[Dict[str, Any]]:
    out = []
    for table in before:
        for key in sorted(set(before[table]) | set(after[table]), key=str):
            old, new = before[table].get(key), after[table].get(key)
            if old != new:
                out.append({"table": table, "key": list(key), "before": old, "after": new})
    return out


def journaled(method):
    """Run a DayBook change as one journal entry (joined to an outer one when nested; a dry run is not kept)."""
    sig = inspect.signature(method)

    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        given = sig.bind(self, *args, **kwargs).arguments
        if given.get("dry_run"):
            return method(self, *args, **kwargs)
        with self.action(given["program"], given["on"], given["user_id"]):
            return method(self, *args, **kwargs)
    return wrapped


def _either(names: List[str]) -> str:
    """X, Y or Z."""
    return " or ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else "".join(names)


def operating_span(view: Dict[str, Any]) -> int:
    """Phase AU: minutes from the start of a 24-hour window to the end of the last shift that starts in it, rounded up to
    a whole interval; ValueError when no shift starts in it (the window then stays 24 hours)."""
    ends = [s["end"] for ln in view["lanes"] for s in ln["segments"] if s["offset"] == 0]
    if not ends:
        raise ValueError("No shift starts in the operating day.")
    step = view["interval"]
    length = -(-(max(ends) - view["start"]) // step) * step
    if length <= 0:
        raise ValueError("The last shift ends before the operating day starts.")
    return min(length, 1440)


class DayBook:
    def __init__(self, store, book: ScheduleBook):
        self.store = store
        self.book = book
        self.measure_of = lambda program: "interval"  # the program's own measure; the site sets it (Phase AU)
        self.notifier = None  # Phase AB: hands each change to its LOB's group rule (webapp/notify.py)
        self._locks: Dict[Tuple[str, str], threading.RLock] = {}  # Phase AD: one change at a time per LOB and day
        self._locks_lock = threading.Lock()
        self._pages: "OrderedDict[Tuple[str, date, str, int], Tuple[int, float, Dict[str, Any]]]" = OrderedDict()  # Phase AV
        self._build_lock = threading.Lock()

    def _log(self, program: str, on: date, name: str, what: str, user_id: int, kind: str, post: str = "",
             ref: str = "", before: str = "", after: str = "") -> None:
        """Keep a line in the day's log, and hand it to the LOB's group rule (Phase AB): ``post`` is the text a
        group may see (the why of an aux stays on the website); ``ref``, ``before`` and ``after`` let a change
        undone before it is posted drop out. The change is kept even if the hand-over fails; the failure is logged."""
        log_id = self.store.add_day_log(program=program, shift_date=on.isoformat(), associate=name, what=what,
                                        user_id=user_id)
        running = _ACTION.get()
        if running is not None:
            running.logs.append((log_id, name, what))
        if self.notifier is None:
            return
        try:
            user = self.store.get_user(user_id) or {}
            self.notifier.queue(log_id, program, on.isoformat(), name, kind, post or what,
                                user.get("display_name", ""), ref=ref, before=before, after=after,
                                left_out=left_out_now(), action_id=running.id if running else None,
                                held=bool(running and (running.kind == "bulk" or running.hold)),
                                skip_reason="undone before it was posted" if running and running.silent else "")
        except Exception:  # noqa: BLE001 (the RTA change stands; the group post is what is lost, and logged)
            logging.getLogger(__name__).exception("group posts: could not queue a change for %s", program)

    # ------------------------------------------------------------- the change journal and Undo (Phase AD)
    def _lock(self, program: str, on: date) -> threading.RLock:
        with self._locks_lock:
            return self._locks.setdefault((program, on.isoformat()), threading.RLock())

    @contextmanager
    def action(self, program: str, on: date, user_id: int, label: str = "", bulk: bool = False,
               kind: str = "") -> Iterator[DayAction]:
        """Keep everything changed inside as one journal entry: the records of ``program`` on ``on`` and the day
        before, as they were and as they are after. A nested call joins the running entry (a bulk one makes it
        bulk). Nothing is kept when nothing changed; what changed before a refusal is kept, so Undo can take it back."""
        outer = _ACTION.get()
        if outer is not None:
            if bulk:
                outer.kind, outer.label = "bulk", label or outer.label
            yield outer
            return
        act = DayAction(program, on, user_id, label, kind or ("bulk" if bulk else "single"))
        # Phase AK: the day after too, so a change on the 24 hours from a later start is one entry for Undo
        dates = [on.isoformat(), (on - timedelta(days=1)).isoformat(), (on + timedelta(days=1)).isoformat()]
        with self._lock(program, on):
            before = self.store.day_rows(program, dates)
            act.id = self.store.add_day_action(program=program, shift_date=on.isoformat(), user_id=user_id,
                                               at=time.time(), label=label, kind=act.kind)
            token = _ACTION.set(act)
            try:
                yield act
            finally:
                _ACTION.reset(token)
                changes = _diff(before, self.store.day_rows(program, dates))
                if changes:
                    self.store.set_day_action(act.id, changes=json.dumps(changes), kind=act.kind,
                                              log_ids=json.dumps([log_id for log_id, _, _ in act.logs]),
                                              label=act.label or self._label(act, changes))
                else:
                    self.store.delete_day_action(act.id)
                    act.id = None

    @staticmethod
    def _label(act: DayAction, changes: List[Dict[str, Any]]) -> str:
        if len(act.logs) == 1:
            return f"{act.logs[0][1]}, {act.logs[0][2]}"
        if act.logs:
            return f"{act.logs[0][1]}, {act.logs[0][2]} and {len(act.logs) - 1} more"
        return f"{len(changes)} change{'s' if len(changes) != 1 else ''}"

    def undoable(self, program: str, on: date, user_id: int) -> Optional[Dict[str, Any]]:
        """The journal entry Undo would take back for ``user_id``: the newest of their own last 2 changes on this
        LOB's day not taken back yet, or None."""
        mine = [a for a in self.store.day_actions(program, on.isoformat())
                if a["user_id"] == user_id and a["kind"] in ("single", "bulk")][-UNDO_DEPTH:]
        return next((a for a in reversed(mine) if not a["undone_at"]), None)

    def undo_last(self, program: str, on: date, user_id: int) -> str:
        """Take back the user's newest change (see ``undoable``) exactly as it was before; refused, with nothing
        changed, when anything it touched was changed again since. Returns what to tell the user."""
        act = self.undoable(program, on, user_id)
        if act is None:
            raise ValueError(NOTHING_TO_UNDO)
        changes = json.loads(act["changes"])
        with self.action(program, on, user_id, label=f"Undo: {act['label']}", kind="undo") as undo:
            stale = self.store.restore_day_rows(changes)
            if stale:
                raise ValueError(self._changed_since(program, on, act, stale[0]))
            # Phase AD: a change the group never saw goes quietly, with its undo; a posted one gets its correction
            # (a bulk change's waits for Send, a single change's posts by itself, as it did)
            items = self.store.notify_items(action_id=act["id"])
            posted = [i for i in items if i["status"] not in ("waiting", "held", "skipped")]
            if not posted:
                self.store.set_notify_items([i["id"] for i in items if i["status"] in ("waiting", "held")],
                                            status="skipped", reason="undone before it was posted")
                undo.silent = True
            else:
                undo.hold = act["kind"] == "bulk"
            for c in changes:
                self._log_undone(program, c, user_id)
            self.store.set_day_action(act["id"], undone_at=time.time(), undone_by=undo.id)
            self.store.set_day_action(undo.id, undo_of=act["id"])
        return f"Undone: {act['label']}."

    @staticmethod
    def _thing(c: Dict[str, Any]) -> str:
        row = c["after"] or c["before"]
        if c["table"] == "actual_breaks":
            return f"{row['associate']}'s {row['kind']}"
        if c["table"] == "attendance":
            return f"{row['associate']}'s attendance"
        if c["table"] == "outside_cover":
            return f"{row['associate']}'s cover {hm(row['start'])} to {hm(row['end_min'])}"
        if c["table"] == "incidents":
            return f"{row['associate']}'s missed-break note"
        if c["table"] == "channel_moves":
            return f"{row['associate']}'s channel change {hm(row['start'])} to {hm(row['end_min'])}"
        return f"{row['associate']}'s {row['kind']} {hm(row['start'])} to {hm(row['end_min'])}"

    def _changed_since(self, program: str, on: date, act: Dict[str, Any], c: Dict[str, Any]) -> str:
        later = [a for a in self.store.day_actions(program, on.isoformat()) if a["id"] > act["id"]]
        by = next((a["by_name"] for a in reversed(later)
                   if any(x["table"] == c["table"] and x["key"] == c["key"] for x in json.loads(a["changes"]))), "")
        return f"Not undone: {self._thing(c)} was changed again after it" + (f", by {by}." if by else ".")

    def _planned_start(self, program: str, on: date, name: str, idx: int) -> Optional[int]:
        try:
            _, week, _ = self._shift(program, on, name)
        except ValueError:
            return None
        return next((b["start"] for b in self.plan_for(program, on, name, week) if b["idx"] == idx), None)

    def _log_undone(self, program: str, c: Dict[str, Any], user_id: int) -> None:
        """One day-log line for a record put back by Undo, handed to the group rule like any change (a change never
        posted and its undo then drop out together: same ref, before and after swapped)."""
        old, new = c["before"], c["after"]
        row = new or old
        on, name = date.fromisoformat(row["shift_date"]), row["associate"]
        if c["table"] == "actual_breaks":
            kind = row["kind"]
            was = "cancelled" if new and new.get("cancelled") else (hm(new["start"]) if new else "")
            if old is None:
                plan = self._planned_start(program, on, name, row["idx"])
                what, now_is = f"{kind} back to plan (undone)", hm(plan) if plan is not None else ""
            elif old.get("cancelled"):
                what, now_is = f"{kind} cancelled again (undone)", "cancelled"
            else:
                what, now_is = f"{kind} back to {hm(old['start'])} (undone)", hm(old["start"])
            self._log(program, on, name, what, user_id, "break", ref=f"break:{name}:{row['idx']}", before=was,
                      after=now_is)
        elif c["table"] == "attendance":
            status = old["status"] if old else "Present"
            self._log(program, on, name, f"Attendance back to {status} (undone)", user_id, PRIVATE,
                      ref=f"status:{name}", before=new["status"] if new else "Present", after=status)
        elif c["table"] == "incidents":
            self._log(program, on, name, "Missed-break note " + ("removed" if new else "back") + " (undone)", user_id,
                      PRIVATE, ref=f"incident:{row['id']}", before="on" if new else "", after="" if new else "on")
        elif c["table"] == "outside_cover":
            ref = f"cover:{row['id']}"
            if old is None:
                what, before, after = f"Cover {hm(new['start'])} to {hm(new['end_min'])} removed (undone)", "on", ""
            else:
                what, before, after = f"Cover {hm(old['start'])} to {hm(old['end_min'])} back (undone)", "", "on"
            self._log(program, on, name, what, user_id, "overtime", ref=ref, before=before, after=after)
        else:
            channel = c["table"] == "channel_moves"
            ref = f"channel:{row['id']}" if channel else (f"callin:{row['id']}" if row["kind"] == CALLED_IN
                                                          else f"activity:{row['id']}")
            kind = "channel" if channel else _group_kind(row["kind"])
            label = "Channel change" if channel else row["kind"]
            if old is None:
                what, before, after = f"{label} {hm(new['start'])} to {hm(new['end_min'])} removed (undone)", "on", ""
            elif new is None:
                what, before, after = f"{label} {hm(old['start'])} to {hm(old['end_min'])} back (undone)", "", "on"
            else:
                what = f"{label} back to {hm(old['start'])} to {hm(old['end_min'])} (undone)"
                before, after = hm(new["start"]), hm(old["start"])
            self._log(program, on, name, what, user_id, kind, ref=ref, before=before, after=after)

    # ------------------------------------------------------------- what the day reads
    def programs(self) -> List[str]:
        return sorted({v["program"] for v in self.store.list_schedules() if v["program"]}, key=str.lower)

    def version(self, program: str, on: date) -> Tuple[Optional[Dict[str, Any]], str]:
        """The version in use for the week holding ``on``, else the tool's own (after breaks first)."""
        return pick_version(self.store.list_schedules(program=program, covering=on.isoformat()))

    def _week(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(row["week"] or "{}")

    def roster(self, program: str, on: date) -> List[Tuple[str, str]]:
        """(name, that day's cell: a shift, OFF or Leave) for everyone on the schedule holding ``on`` (Phase AG)."""
        row, _ = self.version(program, on)
        if row is None:
            return []
        return [(a["name"], a["days"][day_index(on)]) for a in self._week(row).get("associates", [])]

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

    def _rest(self, program: str, on: date, row: Dict[str, Any], name: str, lo: int, hi: int, rest: int,
              refuse: bool = True) -> str:
        """Refuse work from ``lo`` to ``hi`` on ``on`` that leaves less than ``rest`` minutes off either side; with
        ``refuse`` False, say why instead (Phase AJ: overtime is kept with a warning). "" when the rest is kept."""
        if not rest:
            return ""
        near = self.neighbours(program, on, row)
        prv, nxt = near["prev"].get(name), near["next"].get(name)
        said = ""
        if prv and lo + 1440 - prv[1] < rest:
            said = (f"{name} would rest {(lo + 1440 - prv[1]) / 60:g} hours after the previous shift; "
                    f"the rule is {rest / 60:g}.")
        elif nxt and nxt[0] + 1440 - hi < rest:
            said = (f"{name} would rest {(nxt[0] + 1440 - hi) / 60:g} hours before the next shift; "
                    f"the rule is {rest / 60:g}.")
        if said and refuse:
            raise ValueError(said)
        return said

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

    def page(self, program: str, on: date, measure: Optional[str] = None,
             extra: Optional[Dict[str, Any]] = None, recorded: bool = True,
             cover: bool = True, version_id: Optional[int] = None, shared: bool = False) -> Optional[Dict[str, Any]]:
        """The day, kept (Phase AV): the plain day of a program, date and measure is built once and handed out as a
        copy until anything is written to the database (``Store.generation``) or ``PAGE_KEEP`` seconds pass. A day
        asked for with ``extra``, as planned, without cover or as another version, or from inside an open change (whose own
        writes are not committed yet), is built every time. See
        ``_build_page`` for what a day is. With ``shared`` the kept day itself is returned, not a copy: only for a caller
        that reads it and never changes it."""
        if measure is None:
            measure = self.measure_of(program)
        if extra or not recorded or not cover or version_id is not None or self.store.in_transaction:
            return self._build_page(program, on, measure, extra, recorded, cover, version_id)
        key = (program, on, measure, SHOWN.get())  # the wording is in the zone the viewer has chosen
        found = self._kept(key, shared)
        if found is not None:
            if VERIFY_PAGES:
                self._verify(key, found, program, on, measure)
            return found
        with self._build_lock:  # one thread builds a day, the others wait for it rather than build it too
            found = self._kept(key, shared)
            if found is not None:
                return found
            generation, built_at = self.store.generation, time.monotonic()  # read before building: a write during it
            page = self._build_page(program, on, measure, None, True, True, None)  # leaves the copy out of date
            if page is not None:
                self._pages[key] = (generation, built_at, page)
                self._pages.move_to_end(key)
                while len(self._pages) > PAGE_MAX:
                    self._pages.popitem(last=False)
            return page if shared else self._copy(page)

    def _verify(self, key, found, program, on, measure) -> None:
        """Checking mode: the day kept must equal a fresh build of it. Another thread may be writing, so a comparison
        counts only when the kept day is still the one kept and no write happened while the fresh day was built; a
        difference that stands under those two conditions is a day kept out of date."""
        for _ in range(8):
            entry = self._pages.get(key)
            if entry is None or entry[0] != self.store.generation:
                return  # no longer kept: a write got there first
            before = self.store.generation
            fresh = self._build_page(program, on, measure, None, True, True, None)  # under the same zone as the hit
            if self.store.generation != before:
                time.sleep(0.02)
                continue  # a write happened while it was built: try again
            same = first_difference(fingerprint({k: v for k, v in entry[2].items() if k != "inputs"}),
                                    fingerprint({k: v for k, v in (fresh or {}).items() if k != "inputs"}))
            if not same:
                return
            raise AssertionError(f"A kept day differs from a fresh build of it ({key}): {same}")

    def _kept(self, key, shared: bool = False):
        entry = self._pages.get(key)
        if entry is None:
            return None
        generation, built_at, page = entry
        if generation != self.store.generation or time.monotonic() - built_at > PAGE_KEEP:
            self._pages.pop(key, None)
            return None
        return page if shared else self._copy(page)

    @staticmethod
    def _copy(page):
        """A copy a caller may change; the workbook's inputs (read once, never changed) are shared, not copied."""
        if page is None:
            return None
        shared = page["inputs"]

        def clone(x):
            t = type(x)
            if t is dict:
                return {k: clone(v) for k, v in x.items()}
            if t is list:
                return [clone(v) for v in x]
            if t is tuple:
                return tuple(clone(v) for v in x)
            if t in (str, int, float, bool, type(None), date):
                return x
            return copy.deepcopy(x)  # anything else a day holds: copied the slow, sure way

        return {k: (v if v is shared else clone(v)) for k, v in page.items()}

    def _build_page(self, program: str, on: date, measure: Optional[str] = None,
                    extra: Optional[Dict[str, Any]] = None, recorded: bool = True,
                    cover: bool = True, version_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """The day; ``extra`` (from ``add_item(..., dry_run=True)``) is counted as if it were recorded. With
        ``recorded`` False, the day as planned: the RTA's records (attendance, break moves, activities) left out
        (Phase AH, the Weeks page's "As planned"). With ``cover`` False, people covering from outside the roster
        (Phase AJ) are left out of the figures. ``version_id`` (Phase AM, the Weeks page's Version pick): that version
        of the program's week holding ``on`` in place of the one in use; any other is refused (ValueError). With no
        ``measure`` the program's own is used (Phase AU: LOBs and defaults)."""
        if measure is None:
            measure = self.measure_of(program)
        if measure not in MEASURES:
            raise ValueError(f"Unknown measure: {measure}.")
        row, note = self.version(program, on)
        if version_id is not None:
            row = next((v for v in self.store.list_schedules(program=program, covering=on.isoformat())
                        if v["id"] == version_id), None)
            if row is None:
                raise ValueError("That version is not one of this week's schedules.")
            note = ""
        if row is None:
            return None
        week = self._week(row)
        if extra and extra.get("swap"):  # Phase AG: two people swapping this day, counted as if done
            week = swapped_week(week, day_index(on), *extra["swap"])
        source = self.book.input_path(row["run_id"])
        if not source.is_file():
            raise ValueError(f"The input workbook kept with {row['label']} is missing, so the day cannot be worked "
                             "out. Run the week again, or ask the admin to restore the server's data folder.")
        inputs = read_inputs(source)
        attendance, actual, stale, acts = self._records(program, on, row) if recorded else ({}, {}, 0, {})
        if extra and extra.get("break"):  # a break at another time (the break advice's channel effect)
            name, idx, minute = extra["break"]
            actual[(0, name, idx)] = minute
        elif extra and "breaks" in extra:  # Phase AD: several breaks changed (a minute, CANCELLED, or None: the plan)
            for (name, idx), minute in extra["breaks"].items():
                if minute is None:
                    actual.pop((0, name, idx), None)
                else:
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
        if channels and extra and extra.get("channel"):  # Phase AF (C3): a channel change counted as if kept
            who, lo, hi, letter = extra["channel"]
            channels["moves"].setdefault((0, who), []).append({"id": 0, "start": lo, "end": hi, "channel": letter})
        covering = []
        if recorded and cover:  # Phase AJ: today's, and last night's that ran past midnight
            for shift, when in ((0, on), (-1440, on - timedelta(days=1))):
                covering += [{"start": r["start"] + shift, "end": r["end_min"] + shift, "channel": r["channel"],
                              "name": r["associate"], "role": r["role"], "language": r.get("language", "")}
                             for r in self.store.list_cover(program, [when.isoformat()])]
        view = day_view(week, inputs, day_index(on), attendance, actual, measure, acts, before, channels=channels,
                        cover=covering)
        if recorded:  # Phase AX: breaks ticked as missed are out of adherence (once each, however often they were moved)
            missed: Dict[str, Dict[int, int]] = {}
            for r in self.store.list_incidents(program, [on.isoformat()]):
                if r["kind"] == "missed_break":
                    missed.setdefault(r["associate"], {})[r["idx"]] = int(r["minutes"] or 0)
            for lane in view["lanes"]:
                if lane["name"] in missed:
                    for seg in lane["segments"]:
                        if seg["offset"] == 0:
                            seg["missed_min"] = sum(missed[lane["name"]].values())
        ratio, source_of_target = self.target_for(program, on, row, inputs)
        standing = at_target(view["cells"], ratio)
        for c, s in zip(view["cells"], standing["cells"]):  # Phase AH: every page colours by the week's target
            c.update(cls=s["cls"], tight=s["tight"], over=s["over"])
        return {"version": row, "note": note, "view": view, "stale": stale, "date": on,
                "unlisted": self._unlisted(program, on, view, attendance, acts),
                "target": standing, "target_source": source_of_target,
                "channel_problem": channel_problem,
                "week_start": row["week_start"], "day": day_index(on), "inputs": inputs, "week": week,
                "log": self.store.list_day_log(program, on.isoformat())}

    def window_page(self, program: str, on: date, start: int, measure: Optional[str] = None,
                    extras: Optional[Dict[date, Dict[str, Any]]] = None, fit: bool = False) -> Optional[Dict[str, Any]]:
        """Phase AK: the page for the 24 hours from minute ``start`` of ``on`` (Phase AI's window, as the Timeline shows
        it), with ``extras`` counted as if kept, per shift date (``page(extra=...)``). ``views`` holds each day's own
        view by its distance from ``on``. From minute 0 it is the day's own page. With ``fit`` (Phase AU, the operating
        day) the window ends with the last shift that starts in it, or runs the 24 hours when that cannot be worked out."""
        extras = extras or {}
        measure = measure or self.measure_of(program)
        page = self.page(program, on, measure, extras.get(on))
        if page is None:
            return None
        views: Dict[int, Optional[Dict[str, Any]]] = {0: page["view"]}
        if not start:
            return dict(page, views=views, start=0)
        for d in range(start // 1440, (start + 1439) // 1440 + 1):
            if d:
                try:
                    found = self.page(program, on + timedelta(days=d), measure, extras.get(on + timedelta(days=d)))
                except ValueError:  # a workbook that cannot be read: its hours stay empty
                    found = None
                views[d] = (found or {}).get("view")
        view = window_view(views, start, on)
        if fit:
            try:
                length = operating_span(view)
            except (ValueError, KeyError, TypeError, StopIteration):
                length = 1440
            if length < 1440:
                view = window_view(views, start, on, length)
        return dict(page, view=view, target=at_target(view["cells"], page["target"]["target"]), views=views,
                    start=start)

    def target_for(self, program: str, on: date, row: Optional[Dict[str, Any]] = None,
                   inputs: Optional[Dict[str, Any]] = None) -> Tuple[float, Dict[str, Any]]:
        """The interval target of the week holding ``on`` (Phase W): the one set for this program and week (with who
        set it), else the program's default, else the workbook's own "Target"; (0.9, workbook) when there is no schedule."""
        if row is None:
            row, _ = self.version(program, on)
        if row is None:
            return 0.9, {"kind": "workbook"}
        kept = self.store.get_interval_target(program, row["week_start"])
        if kept:
            return kept["target"] / 100, {"kind": "set", "by": kept.get("by_name") or "someone", "at": kept["at"]}
        default = self.store.rta_default(program, "target")  # Phase AU: LOBs and defaults
        if default:
            return int(default) / 100, {"kind": "program"}
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
        row, _ = self.version(program, on)
        run = self.store.get_run(row["run_id"]) if row else None
        zone = pick_zone((run or {}).get("tz") or HOME)
        at = minute_now(on, zone, datetime.now(EGYPT))
        after = max(0, min(at, 1440))
        return {"setup": setup, "skills": ChannelPeople(self.store).skills_for_unit(program),
                "language_rows": inputs["languages"], "blocks": blocks, "moves": moves, "after": after,
                "gaps": (inputs.get("gap_min"), inputs.get("gap_max")), "today": 0 <= at < 1440}, ""

    @journaled
    def channel_move(self, program: str, on: date, name: str, start: Any, end: Any, channel: str,
                     user_id: int) -> int:
        """Put ``name`` on ``channel`` from ``start`` to ``end`` (minutes, or HH:MM) for the shift that starts on
        ``on``; kept and said in the day log. Refused outside the shift, off the 5-minute steps, in all-channels
        time, or for a channel the person cannot work."""
        from .channels import CHANNELS
        lo, hi, was = self._channel_change(program, on, name, start, end, channel)
        made = self.store.add_channel_move(program=program, shift_date=on.isoformat(), associate=name, start=lo,
                                           end_min=hi, channel=channel, user_id=user_id)
        what = f"{CHANNELS[channel]} from {hm(lo)} to {hm(hi)}" + (f" (was {CHANNELS[was]})" if was in CHANNELS else "")
        self._log(program, on, name, what, user_id, "channel", ref=f"channel:{made}", after="on")
        return made

    def channel_preview(self, program: str, on: date, name: str, start: Any, end: Any, channel: str,
                        measure: str = "interval") -> Dict[str, Any]:
        """Phase AF (C3): what putting ``name`` on ``channel`` from ``start`` to ``end`` would do, before anything is
        kept: the channel warnings it would add and the fixes proposed for them. Refused as the change itself
        would be (ValueError)."""
        from .channels import CHANNELS
        lo, hi, was = self._channel_change(program, on, name, start, end, channel)
        before = self.page(program, on, measure)["view"]["channels"]
        after = self.page(program, on, measure, extra={"channel": (name, lo, hi, channel)})["view"]["channels"]
        old = {w["text"] for w in before["warnings"]}
        new = [w for w in after["warnings"] if w["text"] not in old]
        text = f"{name}: {CHANNELS[channel]} from {hm(lo)} to {hm(hi)}" + (
            f" (was {CHANNELS[was]})" if was in CHANNELS else "")
        return {"text": text, "level": "bad" if new else "ok", "warnings": [w["text"] for w in new],
                "fixes": [f["text"] for w in new for f in w["fixes"]][:3]}

    def _channel_change(self, program: str, on: date, name: str, start: Any, end: Any,
                        channel: str) -> Tuple[int, int, Optional[str]]:
        """The checks a channel change passes (see channel_move): its minutes and the channel it replaces."""
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
        return lo, hi, letter_at(blocks, moved, lo, False)

    def channel_fix_plan(self, program: str, on: date, now: Optional[int] = None) -> Dict[str, Any]:
        """Phase AM (owner, 2026-10-16: one click to fix the channels on the RTA; answers: the channel planner
        re-plans channels from now on, channels only, coverage first then fairness): what re-planning today's shifts
        from the next quarter hour would change, before anything is kept.

        People: today's shifts that are on the floor (whole-shift absences left out), from the next quarter hour
        after ``now`` (the clock's minute when None) to the end of the shift or its overtime. Their breaks, away
        time and activities other than overtime stay where they are (the planner may not move them). Last night's
        people count on the channels they are on. Carrying on with the channel someone is on is free; each
        change of channel costs, and fairness over the week decides between plans that cover the same.

        Returns ``changes`` [(name, start, end, channel, was)], the shortfall in person-hours per channel from then
        on before and after (``short_before``, ``short_after``), ``from`` and ``seconds``."""
        from .channel_people import can_work
        from .channel_plan import NoPlan, counts_for, need_at, plan_day
        from .channels import QUARTER, blended_at, inside as channel_inside
        page = self.page(program, on)
        if page is None:
            raise ValueError(f"No schedule for {program} on {on:%d %b}.")
        view = page["view"]
        ch_view = view.get("channels")
        if not ch_view:
            raise ValueError(page.get("channel_problem") or "This day has no channel needs, so there are no channels "
                             "to fix.")
        hold = ch_view["hold"]
        setup = dict(hold.setup, rules=dict(hold.setup["rules"], fair=True))  # fairness between equal plans
        skills, rows, d = hold.ch["skills"], hold.ch["language_rows"], day_index(on)
        if now is None:
            run = self.store.get_run(page["version"]["run_id"]) or {}
            now = minute_now(on, pick_zone(run.get("tz") or HOME), datetime.now(EGYPT))
        if now >= 1440 and not any(s["end"] > now for l in view["lanes"] for s in l["segments"] if s["offset"] == 0):
            raise ValueError("This day is over: nothing is left to fix.")
        first = -(-max(now + 1, 0) // QUARTER) * QUARTER
        runs = ch_view["runs"]

        def letter(name: str, t: int) -> str:
            return next((c for a, b, c in runs.get(name, []) if a <= t < b), "")

        people, carry_in, before = [], {}, {}
        for lane in view["lanes"]:
            for seg in lane["segments"]:
                if seg["status"] in ABSENT:
                    continue
                if seg["offset"] == -1:  # last night's people: held, and counted on the channels they are on
                    for t in range(first, seg["end"], QUARTER):
                        c = letter(lane["name"], t)
                        channels = can_work(skills, lane["name"]) if c == "A" else c if c in "PCE" else ""
                        languages = counts_for(lane.get("language", ""), rows)
                        for channel in channels:
                            for key in [channel] + [f"{channel}:{lang}" for lang in languages]:
                                before.setdefault(key, {}).setdefault(t, 0)
                                before[key][t] += 1
                    continue
                if seg["offset"] != 0 or seg["status"] in ABSENT:
                    continue
                extra = [a for a in seg.get("activities", []) if a["kind"] in ("Overtime", CALLED_IN)]
                lo = max(first, min([seg["start"]] + [a["start"] for a in extra]))
                hi = max([seg["end"]] + [a["end"] for a in extra]) // QUARTER * QUARTER
                lo = -(-lo // QUARTER) * QUARTER
                if hi - lo < QUARTER:
                    continue
                busy = [(b["start"], b["minutes"]) for b in seg["breaks"]]
                busy += [(a["start"], a["end"] - a["start"]) for a in seg.get("activities", [])
                         if a["kind"] not in ("Overtime", CALLED_IN)]
                if seg["away"][1] > seg["away"][0]:
                    busy.append((seg["away"][0], seg["away"][1] - seg["away"][0]))
                busy = [(s, m) for s, m in busy if s < hi and s + m > lo and m > 0]
                people.append({"name": lane["name"], "language": lane.get("language", ""), "start": lo, "end": hi,
                               "breaks": [("Busy", s, m) for s, m in sorted(busy)],
                               "skills": can_work(skills, lane["name"]),
                               "counts_for": counts_for(lane.get("language", ""), rows)})
                was = letter(lane["name"], lo - STEP)
                if was in ("P", "C", "E"):
                    carry_in[lane["name"]] = was
        if not people:
            return {"changes": [], "short_before": {}, "short_after": {}, "from": first, "seconds": 0.0}
        # Outside cover stays fixed, just like the prior night's shifts.
        for cover in view.get("outside", []):
            channel = cover.get("channel")
            if channel not in ("P", "C", "E"):
                continue
            languages = counts_for(cover.get("language", ""), rows) if cover.get("language") else set()
            lo = -(-max(first, cover["start"]) // QUARTER) * QUARTER
            for t in range(lo, cover["end"] - QUARTER + 1, QUARTER):
                for key in [channel] + [f"{channel}:{lang}" for lang in languages]:
                    before.setdefault(key, {}).setdefault(t, 0)
                    before[key][t] += 1
        week = page["week"]
        carry: Dict[str, Dict[str, int]] = {}
        for e in range(d):  # the week so far, from the schedule (fair spread)
            for a in week.get("associates", []):
                for b in channel_blocks(week, e, a["name"]):
                    carry.setdefault(a["name"], {}).setdefault(b["channel"], 0)
                    carry[a["name"]][b["channel"]] += b["end"] - b["start"]
        for p in people:  # and today before the plan starts
            for t in range(0, p["start"], STEP):
                c = letter(p["name"], t)
                if c in ("P", "C", "E"):
                    carry.setdefault(p["name"], {}).setdefault(c, 0)
                    carry[p["name"]][c] += STEP
        try:
            found = plan_day(people, setup, {}, d, carry=carry, move_breaks=False, before=before, carry_in=carry_in,
                             keep={(p["name"], t): letter(p["name"], t) for p in people
                                   for t in range(p["start"], p["end"], QUARTER)},
                             horizon=(first, max(p["end"] for p in people)))
        except NoPlan as exc:
            raise ValueError(f"The channels cannot be re-planned now: {exc}") from exc
        new = {(p["name"], t): c for p in people for a, b, c in found["blocks"].get(p["name"], [])
               for t in range(a, b, QUARTER)}

        def shortfall(read) -> Dict[str, float]:
            out = {}
            for c in setup["need"]:
                missing = 0.0
                for t in range(first, max(p["end"] for p in people), QUARTER):
                    need = need_at(setup, c, d, t)
                    if need <= 0:
                        continue
                    have = before.get(c, {}).get(t, 0) + sum(
                        1 for p in people if p["start"] <= t < p["end"]
                        and (read(p, t) == c or (read(p, t) == "A" and c in p["skills"])))
                    missing += max(need - have, 0)
                out[c] = round(missing * QUARTER / 60, 2)
            missing = 0.0  # the Language Setup minimums per channel ("Phone, Arabic: at least 1")
            for rule in setup["languages"]:
                if not rule["active"] or rule["minimum"] <= 0:
                    continue
                lang = rule["language"].casefold()
                for t in range(first, max(p["end"] for p in people), QUARTER):
                    if channel_inside(rule["days"], rule["start"], rule["end"], (d + t // 1440) % 7, t % 1440):
                        have = before.get(f"{rule['channel']}:{lang}", {}).get(t, 0) + sum(
                            1 for p in people if p["start"] <= t < p["end"] and lang in p["counts_for"]
                                   and (read(p, t) == rule["channel"]
                                        or (read(p, t) == "A" and rule["channel"] in p["skills"])))
                        missing += max(rule["minimum"] - have, 0)
            out["languages"] = round(missing * QUARTER / 60, 2)
            return out

        changes: List[Tuple[str, int, int, str, str]] = []
        for p in people:
            for t in range(p["start"], p["end"], QUARTER):
                c, old = new.get((p["name"], t)), letter(p["name"], t)
                if c not in ("P", "C", "E") or c == old or blended_at(setup, d, t):
                    continue
                if changes and changes[-1][0] == p["name"] and changes[-1][2] == t and changes[-1][3] == c:
                    changes[-1] = (p["name"], changes[-1][1], t + QUARTER, c, changes[-1][4])
                else:
                    changes.append((p["name"], t, t + QUARTER, c, old))
        return {"changes": changes, "from": first, "seconds": found.get("seconds", 0.0),
                "short_before": shortfall(lambda p, t: letter(p["name"], t)),
                "short_after": shortfall(lambda p, t: new.get((p["name"], t), ""))}

    def apply_channel_fix(self, program: str, on: date, changes: List[Tuple[str, int, int, str]], user_id: int,
                          now: Optional[int] = None) -> int:
        """Validate today's complete batch and commit it atomically as one Undo step."""
        prepared = []
        # Match other day edits' lock order: day lock first, then SQLite. The
        # action below re-enters this same RLock while using the shared transaction.
        with self._lock(program, on), self.store.transaction():
            for name, lo, hi, channel in changes:
                if now is not None and lo <= now:
                    raise ValueError(f"{hm(lo)} has passed: open Fix channels again.")
                self._channel_change(program, on, name, lo, hi, channel)
                prepared.append((name, lo, hi, channel))
            with self.action(program, on, user_id, bulk=True) as act:
                for name, lo, hi, channel in prepared:
                    self.channel_move(program, on, name, lo, hi, channel, user_id)
                done = len(prepared)
                act.label = f"Fix channels changed {done} stretch{'es' if done != 1 else ''}"
        return len(prepared)

    @journaled
    def cancel_channel_move(self, program: str, on: date, move_id: int, user_id: int) -> None:
        from .channels import CHANNELS
        r = self.store.get_channel_move(move_id)
        if r is None or r["program"] != program or r["shift_date"] != on.isoformat():
            raise ValueError("That channel change is not on this day.")
        self.store.delete_channel_move(move_id)
        self._log(program, on, r["associate"], f"{CHANNELS[r['channel']]} from {hm(r['start'])} to {hm(r['end_min'])} "
                  "taken back", user_id, "channel", ref=f"channel:{move_id}", before="on")

    @journaled
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
            rec = self.add_activity(program, on, r["associate"], r["kind"], start, plain_hm(lo + r["end_min"] - r["start"]),
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
    @journaled
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
            kind = status if status == BIO else f"{status} ({'billable' if billable else 'non-billable'})"
            what = f"{kind} {hm(lo)} to {hm(hi)}" if lo is not None else f"{kind}, whole shift"
        else:
            lo = hi = None
            what = status
        with_whom, why, with_dept = (_tidy(with_whom), _tidy(why), _tidy(with_dept)) if status in AUX else ("", "", "")
        post = what + with_text(with_whom, "", with_dept)  # Phase AB: what a group may see, never the why
        what += with_text(with_whom, why, with_dept)
        record = {"name": name, "status": status, "from": lo, "to": hi, "billable": bool(billable) and status in AUX and status != BIO,
                  "what": what, "span": span, "with_whom": with_whom, "why": why, "with_dept": with_dept}
        if dry_run:
            return record
        was = next((r["status"] for r in self.store.list_attendance(program, [on.isoformat()])
                    if r["associate"] == name), "Present")
        self.store.set_attendance(program=program, shift_date=on.isoformat(), associate=name, status=status,
                                  from_min=lo, to_min=hi, billable=int(bool(billable) and status in AUX and status != BIO),
                                  user_id=user_id, with_whom=with_whom, why=why, with_dept=with_dept)
        kind = "late" if status in LATE_EARLY else "aux" if status in AUX else PRIVATE  # sick, leave, present
        self._log(program, on, name, what, user_id, kind, post=post, ref=f"status:{name}", before=was, after=status)
        return record

    @journaled
    def move_break(self, program: str, on: date, name: str, idx: int, at: Optional[str], user_id: int,
                   suffix: str = "", missed: bool = False) -> None:
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
        if missed:  # Phase AV: the associate missed this break; kept as an incident for the analysis
            self.store.add_incident(program=program, shift_date=on.isoformat(), associate=name, kind="missed_break",
                                    idx=idx, minutes=int(plan[idx].get("minutes") or 0), note=plan[idx]["kind"],
                                    user_id=user_id, at=time.time())
        self._log(program, on, name, what, user_id, "break", ref=f"break:{name}:{idx}",
                  before="cancelled" if was_cancelled else hm(was), after=hm(plan[idx]["start"] if at is None else m))

    @journaled
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
        found["warnings"] += self._default_words(program, on, page["view"], name, idx, m)
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
        if kind in EXTRA_BREAKS or kind == BIO:
            return f"{kind} {hm(lo)} to {hm(hi)}"
        return (f"{kind} {hm(lo)} to {hm(hi)} ({'billable' if billable else 'non-billable'})"
                + with_text(with_whom, why, with_dept))

    @journaled
    def add_activity(self, program: str, on: date, name: str, kind: str, start: str, end: str, user_id: int,
                     billable: bool = False, note: str = "", dry_run: bool = False, with_whom: str = "",
                     why: str = "", with_dept: str = "", session: str = "") -> Any:
        """Record an activity for the shift that starts on ``on``: an aux, a break or lunch added on the day,
        or VTO (each inside the shift), or overtime (touching the shift, at most OVERTIME_MAX, keeping the rest
        gap). Returns its id; with ``dry_run`` every check runs, nothing is kept, and the record is returned."""
        if kind not in ACTIVITY_KINDS:
            raise ValueError(f"Unknown activity: {kind}.")
        if kind == CALLED_IN:
            return self._call_in(program, on, name, start, end, user_id, note)
        row, week, span = self._shift(program, on, name)
        warning = ""
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
            # owner, 2026-10-15: overtime that breaks the rest gap is kept, with a warning
            warning = self._rest(program, on, row, name, lo, hi, rest, refuse=False)
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
        billable = bool(billable) and kind in AUX and kind != BIO or kind == "Overtime"
        with_whom, why, with_dept = (_tidy(with_whom), _tidy(why), _tidy(with_dept)) if kind in AUX else ("", "", "")
        what = self._describe(kind, lo, hi, billable, with_whom, why, with_dept)
        if dry_run:
            return {"name": name, "kind": kind, "start": lo, "end": hi, "billable": billable, "what": what,
                    "with_whom": with_whom, "why": why, "with_dept": with_dept, "warning": warning}
        made = self.store.add_activity(program=program, shift_date=on.isoformat(), associate=name, kind=kind, start=lo,
                                       end_min=hi, billable=int(billable), note=" ".join(note.split())[:200],
                                       user_id=user_id, with_whom=with_whom, why=why, with_dept=with_dept,
                                       session=session)
        self._log(program, on, name, what + (f". Warning: {warning}" if warning else ""), user_id, _group_kind(kind),
                  post=self._describe(kind, lo, hi, billable, with_whom, "", with_dept), ref=f"activity:{made}",
                  after="on")
        return made

    @journaled
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
            start = plain_hm(span[1] if side == "after" else span[0] - minutes)
        lo = _clock(start)
        if lo is None:
            raise ValueError("Give the start like 13:05.")
        if not isinstance(minutes, int) or minutes <= 0 or minutes % STEP:
            raise ValueError("Pick a length in 5-minute steps.")
        end = plain_hm(lo + minutes)
        rec = self.add_activity(program, on, name, what, start, end, user_id, billable=billable, note=note,
                                dry_run=True, with_whom=with_whom, why=why, with_dept=with_dept)
        if not dry_run:
            self.add_activity(program, on, name, what, start, end, user_id, billable=billable, note=note,
                              with_whom=with_whom, why=why, with_dept=with_dept)
        return {"text": rec["what"], "lo": rec["start"], "hi": rec["end"], "record": rec,
                "warning": rec.get("warning", "")}

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
        if found.get("warning"):  # Phase AJ: kept, but the rest gap is broken
            result["text"] += f" Warning: {found['warning']}"
            result["level"] = "bad" if result["level"] == "bad" else "warn"
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
                rec = self.add_item(program, on, name, what, plain_hm(s), minutes, 0, billable=billable, dry_run=True,
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

    # ------------------------------------------------------------- cover from outside the roster (Phase AJ)
    def covers(self, program: str, on: date) -> List[Dict[str, Any]]:
        """The cover kept for ``on`` (times from that day's midnight; an end past 1440 runs into the next day)."""
        return self.store.list_cover(program, [on.isoformat()])

    @staticmethod
    def _cover_text(name: str, role: str, lo: int, hi: int, channel: str = "", language: str = "") -> str:
        from .channels import CHANNELS
        return (f"Cover from outside the roster ({role}) {hm(lo)} to {hm(hi)}"  # the log line and post name them
                + (f", {CHANNELS.get(channel, channel)}" if channel else "") + (f", {language}" if language else ""))

    @staticmethod
    def cover_languages(page: Optional[Dict[str, Any]]) -> List[str]:
        """The languages a cover can take (Phase AJ): the day's language rules and the channels' language rules."""
        if not page:
            return []
        view = page["view"]
        names = [l["name"] for l in view["languages"]]
        names += [r["language"] for r in (view.get("channels") or {}).get("rows", []) if r.get("language")]
        found: Dict[str, str] = {}
        for n in names:
            found.setdefault(n.strip().casefold(), n.strip())
        return sorted(found.values(), key=str.casefold)

    @journaled
    def add_cover(self, program: str, on: date, name: str, role: str, start: str, end: str, user_id: int,
                  channel: str = "", dry_run: bool = False, language: str = "") -> Any:
        """Keep a team manager or support member, not on the roster, logging in from ``start`` to ``end`` on ``on``
        (an end at or before the start runs past midnight). They count as one person on the floor for those minutes,
        on ``channel`` when the program has channels (then it must be one of them). Returns the id; with ``dry_run``
        every check runs, nothing is kept, and the record is returned."""
        from .channels import CHANNELS
        name = _tidy(name)
        if not name:
            raise ValueError("Type the name of the person covering.")
        if len(name) > COVER_NAME_MAX:
            raise ValueError(f"Keep the name to {COVER_NAME_MAX} characters.")
        if role not in COVER_ROLES:
            raise ValueError(f"Pick {_either(list(COVER_ROLES))}.")
        lo, hi = _clock(start), _clock(end)
        if lo is None or hi is None:
            raise ValueError("Give the start and end like 13:05.")
        if lo % STEP or hi % STEP:
            raise ValueError("Pick times in 5-minute steps, like 10:05.")
        if hi == lo:
            raise ValueError("The end time must be after the start time.")
        hi += 1440 if hi < lo else 0
        if hi - lo > COVER_MAX:
            raise ValueError(f"Keep a cover to {COVER_MAX // 60} hours or less, and add a second one for the rest.")
        page = self.page(program, on)
        if page is None:
            raise ValueError(f"There is no schedule for {program} in the week of {week_start(on):%d %b}.")
        ch = page["view"].get("channels")
        letters = [r["letter"] for r in ch["rows"] if "language" not in r] if ch else []
        channel = (channel or "").strip()
        if not letters and channel:
            raise ValueError("This program has no channels set up, so there is no channel to pick.")
        if letters and channel not in letters:
            raise ValueError(f"Pick the channel {name} takes: {_either([CHANNELS[c] for c in letters])}.")
        offered = self.cover_languages(page)  # Phase AJ: counts for that language too (owner, 2026-10-15)
        language = _tidy(language)
        if language:
            language = next((n for n in offered if n.casefold() == language.casefold()), "")
            if not language:
                raise ValueError(f"Pick the language {name} takes: {', '.join(offered) or 'none'}, or none."
                                 if offered else "This program has no languages set up, so there is none to pick.")
        for r in self.covers(program, on):
            if r["associate"].casefold() == name.casefold() and r["start"] < hi and lo < r["end_min"]:
                raise ValueError(f"{r['associate']} already covers {hm(r['start'])} to {hm(r['end_min'])}. Pick another "
                                 "time, or delete that cover first.")
        what = self._cover_text(name, role, lo, hi, channel, language)  # logged under the name
        if dry_run:
            return {"name": name, "role": role, "start": lo, "end": hi, "channel": channel, "language": language,
                    "what": what}
        made = self.store.add_cover(program=program, shift_date=on.isoformat(), associate=name, role=role, start=lo,
                                    end_min=hi, channel=channel, language=language, user_id=user_id)
        self._log(program, on, name, what, user_id, "overtime", ref=f"cover:{made}", after="on")
        return made

    @journaled
    def cancel_cover(self, program: str, on: date, cover_id: int, user_id: int) -> None:
        row = self.store.get_cover(cover_id)
        if row is None or row["program"] != program or row["shift_date"] != on.isoformat():
            raise ValueError("That cover is not on this day.")
        self.store.delete_cover(cover_id)
        text = self._cover_text(row["associate"], row["role"], row["start"], row["end_min"], row["channel"],
                                row.get("language", ""))
        self._log(program, on, row["associate"], "Cancelled: c" + text[1:], user_id, "overtime",
                  ref=f"cover:{cover_id}", before="on")

    @journaled
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

    def dayoff_plan(self, page: Dict[str, Any], after: int = 0, aim: Optional[float] = None) -> Dict[str, Any]:
        """Rescue the day's days off to cancel, then overtime for what is left (Phase AF, F1 and F2), from ``after``;
        to 100%, or with ``aim`` (the week's target) to the target with 10 minutes to spare (Phase AH)."""
        week = self._week(page["version"])
        rest = float(week.get("settings", {}).get("rest_gap_hours") or 0)
        near = self.neighbours(page["version"]["program"], page["date"], page["version"])
        return {**dayoff_proposals(page["view"], week, page["day"], rest, after=after, near=near, aim=aim),
                "next_known": near["next_known"]}

    LATER_MAX = 14  # days: how far one entry of absences known for later days may reach

    def record_absences(self, program: str, name: str, status: str, first: date, last: date,
                        user_id: int) -> Dict[str, List[date]]:
        """Absences already known for later days (Phase AF, F3): ``status`` (a whole-shift absence) for ``name`` on
        every day from ``first`` to ``last`` that they work. Returns the days ``done``, the days they are ``off`` and
        the days with no schedule here (``missing``); nothing is recorded on those."""
        if status not in ABSENT:
            raise ValueError("Pick unplanned leave, sick, public holiday or exam leave.")
        if last < first:
            raise ValueError("The last day must be on or after the first.")
        if (last - first).days >= self.LATER_MAX:
            raise ValueError(f"Pick {self.LATER_MAX} days at most.")
        found: Dict[str, List[date]] = {"done": [], "off": [], "missing": []}
        on = first
        while on <= last:
            page = self.page(program, on)
            if page is None:
                found["missing"].append(on)
            elif any(s["offset"] == 0 for lane in page["view"]["lanes"] if lane["name"] == name
                     for s in lane["segments"]):
                self.set_status(program, on, name, status, user_id)
                found["done"].append(on)
            else:
                found["off"].append(on)
            on += timedelta(days=1)
        return found

    def outlook(self, program: str, week_start: date, today: date) -> List[Dict[str, Any]]:
        """The rest of the week (Phase AF, F4): for each day of the week after ``today``, the absences already known,
        the hours and intervals short, the overtime needed and the days off to cancel (Rescue the day's proposals for
        that day). A week that is over gives nothing; a week to come gives every day."""
        rows = []
        for i in range(7):
            on = week_start + timedelta(days=i)
            if on <= today:
                continue
            page = self.page(program, on)
            if page is None:
                continue
            view = page["view"]
            plan = self.dayoff_plan(page)
            away = [s["status"] for lane in view["lanes"] for s in lane["segments"]
                    if s["offset"] == 0 and s["status"] in ABSENT]
            kinds = sorted(set(away), key=lambda k: (-away.count(k), STATUSES.index(k)))
            rows.append({"date": on, "absent": [f"{lane['name']} ({s['status'].lower()})" for lane in view["lanes"]
                                                for s in lane["segments"] if s["offset"] == 0 and s["status"] in ABSENT],
                         # Phase AI: one short row a day
                         "absent_text": ", ".join(f"{away.count(k)} {k.lower()}" for k in kinds) or "Nobody",
                         "overtime_hours": sum(o["people"] * (o["end"] - o["start"]) for o in plan["overtime"]) / 60,
                         "dayoff_people": sum(p["people"] for p in plan["proposals"]),
                         "short_hours": view["tiles"]["short_hours"], "short_intervals": view["tiles"]["short_intervals"],
                         "overtime": [o["text"] for o in plan["overtime"]],
                         "dayoff": [p["text"] + "; possible: " + _either([c["name"] for c in p["candidates"]])
                                    for p in plan["proposals"]]})
        return rows

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
        """The autopilot's proposal for the breaks not yet started (nothing is kept); with the week's target, it keeps
        the most intervals 10 minutes over it (Phase AH)."""
        return replan(page["view"], page["inputs"], now, target=page["target"]["target"],
                      fit=self.fit_for(page["version"]["program"], page["date"], 0, page["view"]))

    def _window(self, program: str, on: date, start: int, measure: str = "interval",
                extras: Optional[Dict[date, Dict[str, Any]]] = None) -> Dict[str, Any]:
        page = self.window_page(program, on, start, measure, extras)
        if page is None:
            raise ValueError(f"No schedule for {program} on {on:%d %b}.")
        return page

    @staticmethod
    def _dated(moves: List[Dict[str, Any]], view: Dict[str, Any], on: date, start: int,
               keys: Tuple[str, ...] = ("from", "to")) -> List[Dict[str, Any]]:
        """Moves a tool made on the rebased window, back in the window's minutes, each with its shift's ``date`` and
        ``day_to`` (the new minute in that date's own day; ``day_new`` for Change several breaks)."""
        when = dates_of(view, on)
        out = []
        for m in moves:
            d = when[(m["name"], m["idx"])]
            moved = {**m, **{k: m[k] + start for k in keys if isinstance(m.get(k), int)}, "date": d}
            last = keys[-1]
            moved["day_to" if last == "to" else "day_new"] = (in_own_day(moved[last], d, on)
                                                              if isinstance(moved.get(last), int) else moved.get(last))
            out.append(moved)
        return out

    def replan_window(self, program: str, on: date, start: int, now: int = 0,
                      measure: str = "interval") -> Dict[str, Any]:
        """Phase AK: Fix the day's breaks on the 24 hours from ``start`` (``now`` a minute of that window, 0 for none
        started): the moves in the window's minutes, each with its shift's date."""
        page = self._window(program, on, start, measure)
        view = rebase(page["view"], start, page["views"])
        found = replan(view, page["inputs"], max(now - start, 0) if now else 0, target=page["target"]["target"],
                       fit=self.fit_for(program, on, start, view))
        return {**found, "moves": self._dated(found["moves"], view, on, start)}

    def _default_words(self, program: str, on: date, view: Dict[str, Any], name: str, idx: int, at: int) -> List[str]:
        """Phase AX (owner: "prioritize the default, followed by the engine"): what moving break ``idx`` of ``name`` to ``at``
        takes the person's breaks out of (the usual shape, then the engine's rules); nothing when the rules cannot be read.
        A warning, not a refusal: the move can be kept anyway."""
        from .break_plan import fit_words, slots_for
        people = self._rule_people(program, on, view)
        found = (people or {}).get(name)
        seg = next((s for l in view["lanes"] if l["name"] == name for s in l["segments"] if s["offset"] == 0), None)
        if found is None or seg is None or any(b["idx"] >= found[2] for b in seg["breaks"]):
            return []
        rules, label, count, _ = found
        before: List[Optional[int]] = [None] * count
        for b in seg["breaks"]:
            before[b["idx"]] = b["start"]
        after = list(before)
        after[idx] = at
        return fit_words(rules, label, before, after)

    def _rule_people(self, program: str, on: date, view: Dict[str, Any]):  # type: ignore[no-untyped-def]
        """name -> (the break rules, the shift's label, the breaks the rules give it, the shift's date offset in minutes) for
        the people of a window's ``view`` who have breaks; None when the rules cannot be read."""
        from .break_plan import slots_for
        people: Dict[str, Tuple[Dict[str, Any], str, int, int]] = {}
        try:
            weeks: Dict[date, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
            for lane in view["lanes"]:
                seg = next((s for s in lane["segments"] if s["offset"] == 0), None)
                if seg is None or not seg["breaks"]:
                    continue
                day = seg.get("date") or on
                if day not in weeks:
                    row, _ = self.version(program, day)
                    weeks[day] = (self._week(row), self.book.break_rules(row["id"])) if row else ({}, {})
                week, rules = weeks[day]
                a = next((x for x in week.get("associates", []) if x["name"] == lane["name"]), None)
                span = shift_span(a["days"][day_index(day)]) if a else None
                if span:
                    people[lane["name"]] = (rules, a["days"][day_index(day)], len(slots_for(rules, span[1] - span[0])),
                                            1440 * (day - on).days)
        except ValueError:
            return None
        return people

    def fit_for(self, program: str, on: date, start: int, view: Dict[str, Any]):  # type: ignore[no-untyped-def]
        """Phase AX (owner: "prioritize the default, followed by the engine"; "to the nearest"): for the tools that move breaks
        on a window (``rebase``d ``view``), ``(name, break index -> start in the window) -> (minutes off the usual shape,
        minutes off the engine's rules)``, from the program's break rules; None when they cannot be read (the tools then work
        as before)."""
        from .break_plan import fit as break_fit
        people = self._rule_people(program, on, view)
        if people is None:
            return None

        def fit(name: str, starts: Dict[int, int]) -> Tuple[int, int]:
            found = people.get(name)
            if found is None or any(i >= found[2] for i in starts):
                return (0, 0)
            rules, label, count, shift = found
            own: List[Optional[int]] = [None] * count
            for i, at in starts.items():
                own[i] = at + start - shift
            return break_fit(rules, label, own)
        return fit

    def defaults_for(self, program: str, on: date, start: int, view: Dict[str, Any]):  # type: ignore[no-untyped-def]
        """What Rescue weighs: ``(name, break index, start in the window) -> (minutes off the usual shape, minutes off the
        engine's margin and window for that break)``; None when the rules cannot be read."""
        from .break_plan import break_default
        people = self._rule_people(program, on, view)
        if people is None:
            return None

        def defaults(name: str, idx: int, at: int) -> Tuple[int, int]:
            found = people.get(name)
            if found is None or idx >= found[2]:
                return (0, 0)
            rules, label, count, shift = found
            return break_default(rules, label, idx, count, at + start - shift)
        return defaults

    def fresh_replan_window(self, program: str, on: date, start: int, now: int = 0,
                            measure: str = "interval") -> Dict[str, Any]:
        """Phase AX, "Replan the day's breaks" (owner, 2026-10-22: "it is not rescheduling based on the default"): every
        break not yet started on the 24 hours from ``start`` (``now``: a minute from ``on``'s midnight, 0 for none
        started) is placed as the program's default break rules place it (``break_plan.suggest``, the planner behind
        Plan breaks), the breaks that have started kept where they are. A time the day itself refuses (away time, an
        activity, a gap, a language below its minimum) gives way to the nearest allowed one. The moves, dated as the
        other tools' are; ``note`` says when the rules could not be read and the day's own score was used instead."""
        from .break_plan import slots_for, suggest
        page = self._window(program, on, start, measure)
        view = rebase(page["view"], start, page["views"])
        by_day: Dict[date, List[Tuple[str, Dict[str, Any]]]] = {}
        for lane in view["lanes"]:
            for seg in lane["segments"]:
                if seg["offset"] == 0 and seg["status"] not in ABSENT and seg["breaks"]:
                    by_day.setdefault(seg.get("date") or on, []).append((lane["name"], seg))
        desired: Dict[Tuple[str, int], int] = {}
        note = ""
        try:
            for day, people in sorted(by_day.items()):
                row, _ = self.version(program, day)
                if row is None:
                    continue
                week, rules = self._week(row), self.book.break_rules(row["id"])
                inputs = read_inputs(self.book.input_path(row["run_id"]))
                d, shift = day_index(day), 1440 * (day - on).days
                spans = {a["name"]: shift_span(a["days"][d]) for a in week.get("associates", [])}
                plan: Dict[str, List[Optional[int]]] = {
                    n: [None] * len(slots_for(rules, sp[1] - sp[0])) for n, sp in spans.items() if sp}
                movable = []
                for name, seg in people:
                    sp = spans.get(name)
                    slots = slots_for(rules, sp[1] - sp[0]) if sp else []
                    live = sorted(list(seg["breaks"]) + list(seg.get("cancelled", [])), key=lambda b: b["idx"])
                    if [b["idx"] for b in live] != list(range(len(slots))) or any(
                            str(b["kind"]).casefold() != k.casefold() for b, (k, _) in zip(live, slots)):
                        for b in seg["breaks"]:  # not the rules' shape of breaks: kept as it is, for the others' sake
                            if b["idx"] < len(plan.get(name, [])):
                                plan[name][b["idx"]] = b["start"] + start - shift
                        continue
                    for b in seg["breaks"]:
                        at = b["start"] + start - shift  # in the shift's own day
                        if now and at < now - shift:  # started: where it is
                            plan[name][b["idx"]] = at
                    movable.append((name, seg))
                want = suggest(week, inputs, rules, d, plan)
                for name, seg in movable:
                    for b in seg["breaks"]:
                        got = want.get(name, [None] * (b["idx"] + 1))[b["idx"]]
                        if got is not None and not (now and b["start"] + start < now):
                            desired[(name, b["idx"])] = got + shift - start
        except ValueError:
            desired, note = {}, ("The program's break rules could not be read from the schedule's workbook, so the "
                                 "breaks were placed by the day page's own rules and score instead.")
        found = replan(view, page["inputs"], max(now - start, 0) if now else 0, target=page["target"]["target"],
                       fresh=True, desired=desired or None)
        return {**found, "note": note, "moves": self._dated(found["moves"], view, on, start)}

    @journaled
    def apply_replan(self, program: str, on: date, moves: List[Tuple[Any, ...]], user_id: int) -> int:
        """Keep the approved moves (each checked again: the day may have changed since the preview). A move is
        (name, idx, minute) on ``on``, or (name, idx, minute, date) on its shift's own date (Phase AK)."""
        done = 0
        for name, idx, start, *when in moves:
            self.move_break(program, when[0] if when else on, name, idx, plain_hm(start), user_id, suffix=" (autopilot)")
            done += 1
        return done

    # ------------------------------------------------------------- Change several breaks (Phase AD, sample 04)
    @staticmethod
    def _figures(page: Dict[str, Any]) -> Dict[str, Any]:
        return {"now": page["target"]["now"], "intervals": page["target"]["intervals"],
                "target": page["target"]["target"], "short_hours": page["view"]["tiles"]["short_hours"],
                "safe": page["target"]["safe"], "tight": page["target"]["tight"]}

    def _bulk_found(self, program: str, on: date, names: List[str], which: str, action: str, amount: int, at: str,
                    now: Optional[int], start: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """(the page, ``bulk_breaks.plan`` on it): on the day, or (Phase AK) on the 24 hours from ``start``, where
        ``at`` (a time of ``on``) and ``now`` (a minute of the window) are read in the window and each change gets
        its shift's ``date`` and ``day_new``."""
        from .bulk_breaks import plan as bulk_plan
        if not start:
            page = self.page(program, on)
            if page is None:
                raise ValueError(f"No schedule for {program} on {on:%d %b}.")
            found = bulk_plan(page["view"], names, which, action, amount, at, now)
            found["changes"] = [dict(c, date=on, day_new=c["new"]) for c in found["changes"]]
            return page, found
        page = self._window(program, on, start)
        view = rebase(page["view"], start, page["views"])
        minute = _clock(at)
        if minute is not None:
            at = plain_hm(minute + (1440 if minute < start % 1440 else 0) - start % 1440)
        found = bulk_plan(view, names, which, action, amount, at, None if now is None else max(now - start, -1))
        found["changes"] = self._dated(found["changes"], view, on, start, keys=("start", "new"))
        return page, found

    def _recount(self, program: str, on: date, start: int, breaks: List[Tuple[str, int, Any, date]]) -> Dict[str, Any]:
        """The page (or the window from ``start``) with breaks at other times, as if kept: (name, idx, minute of the
        shift's own day, ``CANCELLED`` or None for the plan, date)."""
        if not start:
            return self.page(program, on, extra={"breaks": {(n, i): v for n, i, v, _ in breaks}})
        return self._window(program, on, start, extras={d: {"breaks": v} for d, v in by_date(breaks).items()})

    def bulk_preview(self, program: str, on: date, names: List[str], which: str, action: str, amount: int = 0,
                     at: str = "", why: str = "", now: Optional[int] = None, start: int = 0) -> Dict[str, Any]:
        """What Change several breaks would do (``bulk_breaks.plan``) and the day before and after it (intervals at
        the target, hours short), counted by the page itself. Nothing is kept. Phase AK: ``start`` works on the 24
        hours from there."""
        page, found = self._bulk_found(program, on, names, which, action, amount, at, now, start)
        after = self._recount(program, on, start, [(c["name"], c["idx"], c["day_new"], c["date"])
                                                    for c in found["changes"]])
        views: Dict[date, Dict[str, Any]] = {}
        for c in found["changes"]:  # Phase AX: what a change takes the person's breaks out of (said, not refused)
            if isinstance(c.get("day_new"), int):
                if c["date"] not in views:
                    views[c["date"]] = (self.page(program, c["date"]) or {}).get("view") or {"lanes": []}
                c["words"] = self._default_words(program, c["date"], views[c["date"]], c["name"], c["idx"], c["day_new"])
        return {**found, "before": self._figures(page), "after": self._figures(after)}

    def apply_bulk(self, program: str, on: date, names: List[str], which: str, action: str, user_id: int,
                   amount: int = 0, at: str = "", why: str = "", now: Optional[int] = None, start: int = 0,
                   missed: bool = False) -> int:
        """Keep a Change several breaks as one bulk change (one step for Undo, held from the group until Send): each
        change checked again as it is kept. Returns how many breaks changed. Phase AK: ``start`` as in
        ``bulk_preview``, each change kept on its shift's own date."""
        from .bulk_breaks import verb
        if action == "cancel" and not _tidy(why):
            raise ValueError("Say why the breaks are cancelled.")
        _, found = self._bulk_found(program, on, names, which, action, amount, at, now, start)
        if not found["changes"]:
            left = "; ".join(f"{x['name']}: {x['why']}" for x in found["skipped"][:3])
            raise ValueError("Nothing to change" + (f" ({left})." if left else ": pick people and a break."))
        done = 0
        with self.action(program, on, user_id, bulk=True) as act:
            try:
                for c in found["changes"]:
                    when = c["date"]
                    if c["new"] == CANCELLED:
                        self.cancel_break(program, when, c["name"], c["idx"], why, user_id,
                                          now=in_own_day(now, when, on))
                    else:
                        self.move_break(program, when, c["name"], c["idx"],
                                        None if c["day_new"] is None else plain_hm(c["day_new"]), user_id,
                                        missed=missed)
                    done += 1
            finally:
                act.label = f"Change several breaks: {verb(action, done)}"
        return done

    # ------------------------------------------------------------- Rescue the day (Phase AD, sample 02)
    def rescue_plan(self, program: str, on: date, now: Optional[int] = None,
                    page: Optional[Dict[str, Any]] = None, start: int = 0) -> Dict[str, Any]:
        """What Rescue the day proposes (``rescue.solve``), counted again by the page itself: the figures, the
        intervals given up and rescued and the strips come from ``page(extra=...)``, never from the model. ``now``
        is minutes past midnight today (None for another day): intervals over by then that missed the target count
        toward the day's 3. A proposal the page's own count does not confirm (no gain, more given up than allowed,
        an interval below 50%) is not offered, and that is said. Nothing is kept."""
        from .rescue import FLOOR, LIMIT, allowance, lost_so_far, solve
        if start:  # Phase AK: the 24 hours from ``start``; ``now`` is a minute of that window
            page = self._window(program, on, start)
        page = page or self.page(program, on)
        if page is None:
            raise ValueError(f"No schedule for {program} on {on:%d %b}.")
        view, target = page["view"], page["target"]
        if view["measure"] != "interval":
            raise ValueError("Rescue the day counts intervals by interval compliance.")
        step = view["interval"]
        lost = [(c["t"], c["pct"]) for c in lost_so_far(target["cells"], now, step)] if now is not None else []
        may = allowance(lost)
        if start:
            solving = rebase(view, start, page["views"])
            found = solve(solving, page["inputs"], target["target"], None if now is None else now - start, may,
                          defaults=self.defaults_for(program, on, start, solving))
            found["moves"] = self._dated(found["moves"], solving, on, start)
        else:
            found = solve(view, page["inputs"], target["target"], now, may,
                          defaults=self.defaults_for(program, on, 0, view))
            found["moves"] = [dict(m, date=on, day_to=m["to"]) for m in found["moves"]]
        out: Dict[str, Any] = {"before": self._figures(page), "after": self._figures(page), "lost": lost, "may": may,
                               "limit": LIMIT, "moves": [], "given_up": [], "rescued": [], "cushioned": [],
                               "said": [], "now": now,
                               "status": found["status"], "solver": found["solver"], "seconds": found["seconds"]}
        after = page
        if found["moves"]:
            after = self._recount(program, on, start, [(m["name"], m["idx"], m["day_to"], m["date"])
                                                       for m in found["moves"]])
            given, rescued, low, cushioned = [], [], [], []
            for vb, va, tb, ta in zip(view["cells"], after["view"]["cells"], target["cells"], after["target"]["cells"]):
                if tb["ok"] is None:
                    continue
                if not tb["ok"] and ta["ok"]:
                    rescued.append(vb["t"])
                elif tb["tight"] and ta["ok"] and not ta["tight"]:  # Phase AH: now 10 minutes over the target
                    cushioned.append(vb["t"])
                if not ta["ok"] and va["now"] < vb["now"] - 1e-9:
                    given.append((vb["t"], ta["pct"]))
                    if va["now"] < min(vb["now"], FLOOR * vb["required"]) - 1e-9:
                        low.append(vb["t"])
            gain = (after["target"]["now"], after["target"]["safe"]) > (target["now"], target["safe"])
            problem = ("it puts no more of the day at the target, or 10 minutes over it" if not gain else
                       f"it gives up {len(given)}, more than the {may} allowed" if len(given) > may else
                       f"{hm(low[0])} would fall below 50% of demand" if low else "")
            if problem:
                logging.getLogger(__name__).error("rescue the day: the page does not confirm the plan for %s %s: %s",
                                                  program, on, problem)
                out["said"].append(f"Rescue the day found moves, but the page's own count does not confirm them "
                                   f"({problem}), so none are offered. Nothing was changed.")
                out["status"] = "refused"
                after = page
            else:
                given_at = {t for t, _ in given}
                for m in found["moves"]:
                    m["why"] = self._rescue_why(m, step, given_at, set(rescued))
                out.update(moves=found["moves"], given_up=given, rescued=rescued, cushioned=cushioned,
                           after=self._figures(after))
        if not out["moves"] and out["status"] != "refused":
            ahead = [c for c in target["cells"] if c["ok"] is not None and (now is None or c["t"] + step > now)]
            if found["status"] == "not solved":
                said = (f"No answer was found in the time ({found['seconds']} s), so nothing is proposed. Try again, "
                        "or use Fix the rest of the day's breaks.")
            elif all(c["ok"] and not c["tight"] for c in ahead):
                said = (f"Nothing to rescue: every interval {'still ahead' if now is not None else 'of the day'} "
                        "is at the target with 10 minutes or more over it.")
            else:
                said = ("Nothing to rescue: no move of the breaks left puts more of the day at the target, or 10 "
                        "minutes over it, within the rules.")
            out["said"].append(said)
        elif out["moves"] and found["solver"] == "FEASIBLE":
            out["said"].append("The best found in the time, not proven the best possible.")
        gone, saved = {t for t, _ in out["given_up"]}, set(out["rescued"])

        def mark(c: Dict[str, Any], kind: str) -> Dict[str, Any]:
            return {"cls": kind, "pct": c["pct"], "over": now is not None and c["t"] + step <= now,
                    "tight": bool(c.get("tight")) and kind == "ok"}

        out["strip"] = [{"t": tb["t"],
                         "before": mark(tb, "none" if tb["ok"] is None else "ok" if tb["ok"] else "below"),
                         "after": mark(ta, "none" if ta["ok"] is None else "gone" if ta["t"] in gone else
                                       "saved" if ta["t"] in saved else "ok" if ta["ok"] else "below")}
                        for tb, ta in zip(target["cells"], after["target"]["cells"])]
        runs: List[List[int]] = []
        for t in out["rescued"]:
            if runs and runs[-1][1] == t:
                runs[-1][1] = t + step
            else:
                runs.append([t, t + step])
        out["rescued_runs"] = runs
        return out

    @staticmethod
    def _rescue_why(move: Dict[str, Any], step: int, given: set, rescued: set) -> str:
        came, goes = move["from"] - move["from"] % step, move["to"] - move["to"] % step
        if goes in given:
            return f"into {hm(goes)} (given up)"
        if came in rescued:
            return f"out of {hm(came)}"
        if came == goes:
            return f"spread inside {hm(came)} to {hm(came + step)}"
        return f"from {hm(came)} to {hm(goes)}"

    def apply_rescue(self, program: str, on: date, moves: List[Tuple[Any, ...]], user_id: int,
                     now: Optional[int] = None, start: int = 0) -> int:
        """Keep the approved Rescue the day moves as one bulk change (one step for Undo, held from the group until
        Send), each checked again as it is kept. A person's breaks are moved in an order that never has one land on
        another on the way (earlier moves first from the earliest, then later moves from the latest). ``now``
        (today) refuses a break that has started since the preview. Returns how many breaks moved. Phase AK: a move
        is (name, idx, minute) on ``on`` or (name, idx, minute of its own day, date); with ``start``, ``now`` is a
        minute of the 24 hours from there."""
        page = self._window(program, on, start) if start else self.page(program, on)
        if page is None:
            raise ValueError(f"No schedule for {program} on {on:%d %b}.")
        where = {(l["name"], b["idx"]): b["start"] for l in page["view"]["lanes"] for s in l["segments"]
                 if s["offset"] == 0 for b in s["breaks"]}
        dated = []  # (name, idx, minute from on's midnight, date, minute of that date)
        for name, idx, minute, *when in moves:
            d = when[0] if when else on
            dated.append((name, idx, minute + 1440 * (d - on).days, d, minute))
        first = {move[0]: i for i, move in reversed(list(enumerate(dated)))}

        def order(move):
            name, idx, at = move[:3]
            later = at > where.get((name, idx), at)
            return first[name], later, -idx if later else idx

        done = 0
        with self.action(program, on, user_id, bulk=True) as act:
            try:
                for name, idx, at, d, minute in sorted(dated, key=order):
                    was = where.get((name, idx))
                    if now is not None and was is not None and was <= now:
                        raise ValueError(f"{name}'s break at {hm(was)} has started since the preview: open Rescue "
                                         "the day again.")
                    if now is not None and at <= now:
                        raise ValueError(f"{hm(at)} has passed: open Rescue the day again.")
                    self.move_break(program, d, name, idx, plain_hm(minute), user_id, suffix=" (rescue)")
                    done += 1
            finally:
                act.label = f"Rescue the day moved {done} break{'s' if done != 1 else ''}"
        return done

    @journaled
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
        session = uuid.uuid4().hex[:8]  # Phase AV: these people stay a group, to move or remove together later
        for name in names:
            self.add_activity(program, on, name, kind, plain_hm(start), plain_hm(start + minutes), user_id, billable=billable,
                              with_whom=with_whom, why=why, with_dept=with_dept, session=session)

    def sessions(self, program: str, on: date) -> List[Dict[str, Any]]:
        """Phase AV: the day's booked sessions, earliest first, each with its members (activity id and name)."""
        found: Dict[str, Dict[str, Any]] = {}
        for r in self.store.list_activities(program, [on.isoformat()]):
            if not r.get("session"):
                continue
            s = found.setdefault(r["session"], {"session": r["session"], "kind": r["kind"], "start": r["start"],
                                                "end": r["end_min"], "with_whom": r.get("with_whom", ""),
                                                "why": r.get("why", ""), "billable": bool(r["billable"]), "members": []})
            s["members"].append({"id": r["id"], "name": r["associate"], "start": r["start"], "end": r["end_min"]})
        return sorted(found.values(), key=lambda s: (s["start"], s["session"]))

    def session_start(self, program: str, on: date, names: List[str], at: str, session: str = "") -> int:
        """Phase AV: a typed time (HH:MM) as minutes in the day those people work: the day's own, or the next day when it
        falls before their shift starts (an overnight shift)."""
        m = _clock(at)
        if m is None:
            raise ValueError("Give the time like 13:05.")
        page = self.page(program, on)
        if page is None:
            raise ValueError("There is no schedule for this day.")
        if session:
            names = names or [r["associate"] for r in self.store.list_activities(program, [on.isoformat()])
                              if r.get("session") == session]
        starts = [s["start"] for l in page["view"]["lanes"] if l["name"] in names for s in l["segments"]
                  if s["offset"] == 0]
        return m + (1440 if starts and m < min(starts) else 0)

    def _session_rows(self, program: str, on: date, session: str, names: List[str]) -> List[Dict[str, Any]]:
        rows = [r for r in self.store.list_activities(program, [on.isoformat()]) if r.get("session") == session]
        if not rows:
            raise ValueError("That session is not on this day.")
        chosen = [r for r in rows if r["associate"] in names] if names else []
        if not chosen:
            raise ValueError("Pick who in the session to change.")
        return chosen

    @journaled
    def move_session(self, program: str, on: date, session: str, names: List[str], start: int, user_id: int) -> None:
        """Phase AV: move the chosen members of a session to ``start`` (minutes), each keeping its length; all of them or
        none, and nobody is booked on top of a break, an absence or another activity (their own old time is theirs)."""
        chosen = self._session_rows(program, on, session, names)
        page = self.page(program, on)
        if page is None:
            raise ValueError("There is no schedule for this day.")
        busy = []
        for r in chosen:
            seg = next((s for l in page["view"]["lanes"] if l["name"] == r["associate"] for s in l["segments"]
                        if s["offset"] == 0), None)
            span = r["end_min"] - r["start"]
            if seg is None or any(_busy(seg, t) and not r["start"] <= t < r["end_min"]
                                  for t in range(start, start + span, STEP)):
                busy.append(r["associate"])
        if busy:
            raise ValueError(f"Not free then: {', '.join(busy)}. Nobody was moved.")
        for r in chosen:
            span = r["end_min"] - r["start"]
            self.store.update_activity(r["id"], start=start, end_min=start + span)
            self._log(program, on, r["associate"], f"{r['kind']} {hm(r['start'])} to {hm(r['end_min'])} moved to "
                      f"{hm(start)} to {hm(start + span)}", user_id, _group_kind(r["kind"]), ref=f"activity:{r['id']}",
                      before=hm(r["start"]), after=hm(start))

    @journaled
    def cancel_session(self, program: str, on: date, session: str, names: List[str], user_id: int) -> None:
        """Phase AV: take the chosen members out of a session (the others stay)."""
        for r in self._session_rows(program, on, session, names):
            self.cancel_activity(program, on, r["id"], user_id)

    # ------------------------------------------------------------- retention
    def cleanup(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        cutoff = datetime.fromtimestamp(now, EGYPT).date() - timedelta(days=KEEP_DAYS)
        return self.store.delete_day_before(cutoff.isoformat())
