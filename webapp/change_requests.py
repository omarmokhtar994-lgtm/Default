# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AS (owner, 2026-10-21): the times an associate may ask a break to move to, and the times a team manager may ask
coaching for, each with its buffer: the people on the floor above the need in the tightest interval it touches, once the
person (or people) are off the queue. One above the need is High, at the need Moderate, below it Low (the owner's answer).

The views are the RTA's: a day view or a window view whose minutes start at ``view["start"]`` (a shift past 00:00 needs
the window), with the shifts' breaks and activities as the RTA holds them."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .day import MEETING_MARGIN, STEP, _busy, _own, break_window

HIGH, MODERATE, LOW = "high", "moderate", "low"
PEOPLE_FOR_HIGH = 1  # people above the need that make the buffer High


def level_of(people_above: Optional[float]) -> str:
    """High, Moderate or Low for ``people_above`` (None: no demand in the intervals touched, nothing to protect)."""
    if people_above is None or people_above >= PEOPLE_FOR_HIGH - 1e-9:
        return HIGH
    return MODERATE if people_above >= -1e-9 else LOW


def _slots(view: Dict[str, Any]) -> List[float]:
    return [x for c in view["cells"] for x in c["slots"]]


def _tightest(view: Dict[str, Any], slots: List[float], lo: int, hi: int) -> Optional[float]:
    """The smallest (people on the floor - people needed) over the intervals that overlap minutes ``lo`` to ``hi``."""
    step, v0 = view["interval"], view.get("start", 0)
    found = []
    for c in view["cells"]:
        if c["required"] > 0 and c["t"] < hi and lo < c["t"] + step:
            here = slots[(c["t"] - v0) // STEP:(c["t"] - v0 + step) // STEP]
            found.append(sum(here) / len(here) - c["required"])
    return round(min(found), 2) if found else None


def break_choices(view: Dict[str, Any], inputs: Dict[str, Any], name: str, idx: int, now: int,
                  step: int = 15) -> Dict[str, Any]:
    """Every legal start for break ``idx`` of ``name``'s shift in ``view`` that begins at or after ``now`` (minutes of the
    view): inside the shift, off the other breaks and within the program's gaps. Each is {"start", "end",
    "people_above", "level", "current"}; the time it has now is among them."""
    seg = _own(view, name)
    if seg is None:
        raise ValueError(f"{name} has no shift this day.")
    me = next((b for b in seg["breaks"] if b["idx"] == idx), None)
    if me is None:
        raise ValueError("That break is not on the plan.")
    lo, hi = break_window(seg, me, {b["idx"]: b["start"] for b in seg["breaks"]}, now,
                          inputs.get("gap_min"), inputs.get("gap_max"))
    others = [b for b in seg["breaks"] if b["idx"] != idx]
    v0, base = view.get("start", 0), _slots(view)
    counts_away = not (seg["billable"] and view["measure"] == "interval")

    def free(t: int) -> bool:  # on the floor at t, this break aside
        if not seg["start"] <= t < seg["end"] or (counts_away and seg["away"][0] <= t < seg["away"][1]):
            return False
        return not any(b["start"] <= t < b["start"] + b["minutes"] for b in others)

    def slot(t: int) -> Optional[int]:
        i = (t - v0) // STEP
        return i if 0 <= i < len(base) else None

    given = list(base)
    for t in range(me["start"], me["start"] + me["minutes"], STEP):  # as if this break were not taken
        if free(t) and slot(t) is not None:
            given[slot(t)] += 1
    choices = []
    wanted = list(range(lo + (-lo) % step, hi + 1, step))
    if lo <= me["start"] <= hi and me["start"] not in wanted:
        wanted = sorted(wanted + [me["start"]])
    for m in wanted:
        trial = list(given)
        for t in range(m, m + me["minutes"], STEP):
            if free(t) and slot(t) is not None:
                trial[slot(t)] -= 1
        above = _tightest(view, trial, m, m + me["minutes"])
        choices.append({"start": m, "end": m + me["minutes"], "people_above": above, "level": level_of(above),
                        "current": m == me["start"]})
    return {"kind": me["kind"], "minutes": me["minutes"], "planned": me["planned_start"], "current": me["start"],
            "choices": choices}


def coaching_choices(view: Dict[str, Any], names: List[str], minutes: int, earliest: int, latest: int,
                     billable: bool = False, now: Optional[int] = None, step: int = 15) -> List[Dict[str, Any]]:
    """The starts (every ``step`` minutes) at which every one of ``names`` is on shift, present and free (ten minutes
    clear of a break, not away or in another activity) for ``minutes``, each with the buffer once they are all off the
    queue (a billable session under interval compliance keeps them on)."""
    segs = []
    for name in names:
        seg = _own(view, name)
        if seg is None:
            raise ValueError(f"{name} has no shift this day.")
        segs.append(seg)
    if minutes <= 0 or minutes % STEP:
        raise ValueError("Pick a length in 5-minute steps.")
    v0, base = view.get("start", 0), _slots(view)
    off_floor = 0 if (billable and view["measure"] == "interval") else len(names)
    first = max(earliest, now if now is not None else earliest)
    out = []
    for start in range(first + (-first) % step, latest - minutes + 1, step):
        if any(_busy(seg, t, MEETING_MARGIN) for seg in segs for t in range(start, start + minutes, STEP)):
            continue
        trial = list(base)
        for t in range(start, start + minutes, STEP):
            i = (t - v0) // STEP
            if 0 <= i < len(trial):
                trial[i] -= off_floor
        above = _tightest(view, trial, start, start + minutes)
        out.append({"start": start, "end": start + minutes, "people_above": above, "level": level_of(above)})
    return out


# ----------------------------------------------------------------------------- the impact the RTA sees
def _rows(view: Dict[str, Any], before: List[float], after: List[float], spans: List[Any]) -> List[Dict[str, Any]]:
    """For each interval of ``view`` that overlaps one of ``spans`` ((lo, hi) minutes): the people needed, on the floor
    before and after (averaged over the interval), the people above the need after, and its buffer word."""
    step, v0 = view["interval"], view.get("start", 0)
    out = []
    for c in view["cells"]:
        if not any(c["t"] < hi and lo < c["t"] + step for lo, hi in spans):
            continue
        i, j = (c["t"] - v0) // STEP, (c["t"] - v0 + step) // STEP
        if not (0 <= i < len(before)) or not before[i:j]:
            continue
        was, now = sum(before[i:j]) / len(before[i:j]), sum(after[i:j]) / len(after[i:j])
        above = round(now - c["required"], 2) if c["required"] > 0 else None
        out.append({"t": c["t"], "need": c["required"], "before": round(was, 2), "after": round(now, 2),
                    "people_above": above, "level": level_of(above)})
    return out


def break_impact(view: Dict[str, Any], name: str, idx: int, to: int) -> List[Dict[str, Any]]:
    """What moving break ``idx`` of ``name`` to ``to`` does to the intervals it leaves and the ones it lands on."""
    seg = _own(view, name)
    me = next(b for b in seg["breaks"] if b["idx"] == idx)
    others = [b for b in seg["breaks"] if b["idx"] != idx]
    v0, before = view.get("start", 0), _slots(view)
    after = list(before)
    counts_away = not (seg["billable"] and view["measure"] == "interval")

    def free(t: int) -> bool:
        if not seg["start"] <= t < seg["end"] or (counts_away and seg["away"][0] <= t < seg["away"][1]):
            return False
        return not any(b["start"] <= t < b["start"] + b["minutes"] for b in others)

    for t in range(me["start"], me["start"] + me["minutes"], STEP):
        i = (t - v0) // STEP
        if free(t) and 0 <= i < len(after):
            after[i] += 1
    for t in range(to, to + me["minutes"], STEP):
        i = (t - v0) // STEP
        if free(t) and 0 <= i < len(after):
            after[i] -= 1
    return _rows(view, before, after, [(me["start"], me["start"] + me["minutes"]), (to, to + me["minutes"])])


def coaching_impact(view: Dict[str, Any], names: List[str], start: int, minutes: int,
                    billable: bool = False) -> List[Dict[str, Any]]:
    """What taking ``names`` off the queue from ``start`` for ``minutes`` does to the intervals it covers."""
    v0, before = view.get("start", 0), _slots(view)
    after = list(before)
    off = 0 if (billable and view["measure"] == "interval") else len(names)
    for t in range(start, start + minutes, STEP):
        i = (t - v0) // STEP
        if 0 <= i < len(after):
            after[i] -= off
    return _rows(view, before, after, [(start, start + minutes)])


# ----------------------------------------------------------------------------- the requests
import json  # noqa: E402
import time  # noqa: E402
from datetime import date, datetime, timedelta  # noqa: E402

from .attendance import BreakRefused, hm  # noqa: E402

BREAK, COACHING = "break", "coaching"
WAITING = "waiting"
LEAD_MINUTES = 0  # a time must be at or after now: the RTA still decides on the day
WINDOW_BEFORE = 120  # minutes before a shift starts that the window opens, so the whole shift and its after-midnight half fit


def _minute(clock: str) -> int:
    try:
        hh, mm = clock.strip().split(":")
        return int(hh) * 60 + int(mm)
    except ValueError:
        raise ValueError("Give the time like 13:05.") from None


class ChangeBook:
    """Break changes an associate asks for on the running day, and coaching a team manager asks for; the RTA decides
    each with the impact in front of them (Phase AS)."""

    def __init__(self, store, days):
        self.store, self.days = store, days

    # ------------------------------------------------------------------ the running shift
    def _window(self, program: str, on: date, start: int) -> Dict[str, Any]:
        return self.days.window_page(program, on, start)

    def running_shift(self, program: str, name: str, now: datetime) -> Optional[Dict[str, Any]]:
        """The shift ``name`` is on now or starts later today, in the schedule's own time (``now`` is read there): the
        day it started on, the window the RTA shows it in and ``now`` in that window's minutes; None when there is none
        (nothing yet today, or it is over). An overnight shift that began yesterday counts until it ends."""
        today = now.date()
        for on in (today - timedelta(days=1), today):
            try:
                page = self.days.page(program, on)
            except ValueError:
                continue
            seg = next((s for lane in (page["view"]["lanes"] if page else []) if lane["name"] == name
                        for s in lane["segments"] if s["offset"] == 0), None)
            if seg is None:
                continue
            at = (today - on).days * 1440 + now.hour * 60 + now.minute
            if seg["end"] <= at or (on < today and seg["end"] <= 1440):
                continue  # over, or yesterday's day shift
            start = max(0, seg["start"] - WINDOW_BEFORE)
            window = self._window(program, on, start - start % page["view"]["interval"])
            return {"on": on, "page": window, "view": window["view"], "inputs": window["inputs"], "now": at,
                    "start": seg["start"], "end": seg["end"], "label": f"{hm(seg['start'])} - {hm(seg['end'])}"}
        return None

    # ------------------------------------------------------------------ break changes
    def break_options(self, program: str, name: str, idx: int, now: datetime) -> Dict[str, Any]:
        found = self.running_shift(program, name, now)
        if found is None:
            raise ValueError("You have no shift running today to change a break in.")
        options = break_choices(found["view"], found["inputs"], name, idx, found["now"] + LEAD_MINUTES)
        return {**options, "shift": found}

    def ask_break(self, program: str, name: str, user: Dict[str, Any], idx: int, to: str, why: str,
                  now: datetime) -> int:
        options = self.break_options(program, name, idx, now)
        found = options["shift"]
        m = _minute(to)
        m += 1440 if m < found["start"] else 0
        chosen = next((c for c in options["choices"] if c["start"] == m), None)
        if chosen is None:
            raise ValueError("Pick one of the times in the list.")
        if chosen["current"]:
            raise ValueError("That is the time the break has now. Pick another.")
        for r in self.store.list_change_requests(program=program, statuses=[WAITING], kind=BREAK):
            d = json.loads(r["detail"])
            if r["shift_date"] == found["on"].isoformat() and json.loads(r["names"]) == [name] and d["idx"] == idx:
                raise ValueError("You already asked to move this break. Cancel that request first.")
        detail = {"idx": idx, "kind": options["kind"], "minutes": options["minutes"], "from": options["current"],
                  "to": m, "level": chosen["level"], "people_above": chosen["people_above"]}
        return self.store.add_change_request(kind=BREAK, program=program, shift_date=found["on"].isoformat(),
                                     names=json.dumps([name]), requester_id=user["id"],
                                     requester_name=user["display_name"], detail=json.dumps(detail),
                                     why=" ".join((why or "").split())[:200])

    # ------------------------------------------------------------------ coaching
    def coaching_view(self, program: str, on: date, names: List[str]) -> Dict[str, Any]:
        """The window the RTA shows ``on`` that holds every one of ``names``'s shifts that start that day."""
        page = self.days.page(program, on)
        if page is None:
            raise ValueError("There is no schedule for that day.")
        starts = []
        for name in names:
            seg = next((s for lane in page["view"]["lanes"] if lane["name"] == name for s in lane["segments"]
                        if s["offset"] == 0), None)
            if seg is None:
                raise ValueError(f"{name} has no shift on {on:%a %d %b}.")
            starts.append(seg["start"])
        start = max(0, min(starts) - WINDOW_BEFORE)
        window = self._window(program, on, start - start % page["view"]["interval"])
        return {"view": window["view"], "page": window, "lo": min(starts), "hi": min(window["view"]["start"] + 1440, 1440 + 600)}

    def coaching_options(self, program: str, on: date, names: List[str], minutes: int, now: datetime,
                         billable: bool = False) -> List[Dict[str, Any]]:
        if on < now.date():
            raise ValueError("Pick today or a later day.")
        found = self.coaching_view(program, on, names)
        at = (now.date() - on).days * 1440 + now.hour * 60 + now.minute if on == now.date() else None
        spans = [s for n in names for lane in found["view"]["lanes"] if lane["name"] == n for s in lane["segments"]
                 if s["offset"] == 0]
        return coaching_choices(found["view"], names, minutes, min(s["start"] for s in spans),
                                max(s["end"] for s in spans), billable=billable, now=at)

    def ask_coaching(self, program: str, names: List[str], user: Dict[str, Any], on: date, start: str, minutes: int,
                     dept: str, why: str, now: datetime, billable: bool = False) -> int:
        if not names:
            raise ValueError("Pick who the coaching is for.")
        options = self.coaching_options(program, on, names, minutes, now, billable=billable)
        found = self.coaching_view(program, on, names)
        m = _minute(start)
        m += 1440 if m < found["lo"] - 240 else 0
        chosen = next((c for c in options if c["start"] == m), None)
        if chosen is None:
            raise ValueError("Pick one of the times in the list.")
        detail = {"start": m, "end": m + minutes, "minutes": minutes, "dept": " ".join((dept or "").split())[:80],
                  "billable": bool(billable), "level": chosen["level"], "people_above": chosen["people_above"]}
        return self.store.add_change_request(kind=COACHING, program=program, shift_date=on.isoformat(),
                                     names=json.dumps(sorted(names)), requester_id=user["id"],
                                     requester_name=user["display_name"], detail=json.dumps(detail),
                                     why=" ".join((why or "").split())[:200])

    # ------------------------------------------------------------------ what the RTA sees, and decides
    def impact(self, row: Dict[str, Any], billable: Optional[bool] = None) -> List[Dict[str, Any]]:
        names, d, on = json.loads(row["names"]), json.loads(row["detail"]), date.fromisoformat(row["shift_date"])
        if row["kind"] == BREAK:
            page = self.days.page(row["program"], on)
            seg = next(s for lane in page["view"]["lanes"] if lane["name"] == names[0] for s in lane["segments"]
                       if s["offset"] == 0)
            start = max(0, seg["start"] - WINDOW_BEFORE)
            view = self._window(row["program"], on, start - start % page["view"]["interval"])["view"]
            return break_impact(view, names[0], d["idx"], d["to"])
        found = self.coaching_view(row["program"], on, names)
        return coaching_impact(found["view"], names, d["start"], d["minutes"],
                               d.get("billable", False) if billable is None else billable)

    def _all_options(self, row: Dict[str, Any], now: datetime, billable: Optional[bool] = None):
        """Every time the request could be at now (from today's records), and the time it asks for: (options, asked)."""
        names, d, on = json.loads(row["names"]), json.loads(row["detail"]), date.fromisoformat(row["shift_date"])
        if row["kind"] == BREAK:
            got = self.break_options(row["program"], names[0], d["idx"], now)
            return [c for c in got["choices"] if not c["current"]], d["to"]
        want = d.get("billable", False) if billable is None else billable
        return self.coaching_options(row["program"], on, names, d["minutes"], now, billable=want), d["start"]

    def alternatives(self, row: Dict[str, Any], now: datetime, billable: Optional[bool] = None,
                     top: int = 3) -> List[Dict[str, Any]]:
        """The times nearest to the one asked for, nearest first: the ones with High or Moderate buffer when there are
        any, else the nearest Low ones. The time asked for is not among them."""
        options, asked = self._all_options(row, now, billable)
        others = [dict(c, distance=abs(c["start"] - asked)) for c in options if c["start"] != asked]
        good = [c for c in others if c["level"] != LOW]
        pool = good or others
        return sorted(pool, key=lambda c: (c["distance"], c["start"]))[:top]

    def _label(self, row: Dict[str, Any]) -> Dict[str, Any]:
        d = json.loads(row["detail"])
        names = json.loads(row["names"])
        words = {"waiting": "waiting for the RTA", "approved": "approved", "rejected": "rejected",
                 "cancelled": "cancelled", "refused": "could not be applied"}
        if row["kind"] == BREAK:
            what = f"{d['kind']} from {hm(d['from'])} to {hm(d['to'] if 'asked_to' not in d else d['asked_to'])}"
        else:
            what = (f"Coaching {hm(d['start'] if 'asked_start' not in d else d['asked_start'])} to "
                    f"{hm(d['end'] if 'asked_start' not in d else d['asked_start'] + d['minutes'])}, "
                    f"{'billable' if d.get('asked_billable', d.get('billable')) else 'not billable'}"
                    + (f" ({d['dept']})" if d.get("dept") else ""))
        said = words.get(row["status"], row["status"])
        if row["status"] == "approved":
            if "asked_to" in d:
                said = f"approved at {hm(d['to'])} instead of {hm(d['asked_to'])}"
            elif "asked_start" in d:
                said = f"approved at {hm(d['start'])} instead of {hm(d['asked_start'])}"
            if "asked_billable" in d:
                said += f", changed to {'billable' if d['billable'] else 'not billable'}"
        return {**row, "names_list": names, "d": d, "what": what, "status_words": said,
                "on": date.fromisoformat(row["shift_date"])}

    def waiting(self, program: str) -> List[Dict[str, Any]]:
        return [self._label(r) for r in self.store.list_change_requests(program=program, statuses=[WAITING])]

    def decided(self, program: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.store.list_change_requests(program=program, statuses=["approved", "rejected", "refused", "cancelled"])
        rows.sort(key=lambda r: -(r["decided_at"] or r["asked"]))
        return [self._label(r) for r in rows[:limit]]

    def mine(self, program: str, user_id: int) -> List[Dict[str, Any]]:
        return [self._label(r) for r in reversed(self.store.list_change_requests(program=program, requester_id=user_id))][:20]

    def count(self, program: str) -> int:
        return len(self.store.list_change_requests(program=program, statuses=[WAITING]))

    def cancel(self, request_id: int, user: Dict[str, Any]) -> None:
        row = self.store.get_change_request(request_id)
        if row is None or row["requester_id"] != user["id"]:
            raise ValueError("That is not your request.")
        if row["status"] != WAITING:
            raise ValueError("That request has been decided already.")
        self.store.update_change_request(request_id, status="cancelled", decided_at=time.time(), decided_by=user["id"])

    def decide(self, request_id: int, user: Dict[str, Any], approve: bool, reason: str, now: datetime,
               at: Optional[int] = None, billable: Optional[bool] = None) -> str:
        """The RTA's answer. Approve makes the change on the day with every check the RTA's own forms run; if one
        refuses, nothing is changed and the request says it could not be applied. Reject needs a reason. ``at`` (minutes,
        one of the times the request could be at) approves it at that time instead, and needs a reason too; ``billable``
        corrects whether coaching is billable."""
        row = self.store.get_change_request(request_id)
        if row is None:
            raise ValueError("There is no such request.")
        if row["status"] != WAITING:
            raise ValueError("That request has been decided already.")
        reason = " ".join((reason or "").split())[:200]
        label = self._label(row)
        who = f"{', '.join(label['names_list'])}"
        if not approve:
            if not reason:
                raise ValueError("Say why it is rejected: the person sees it.")
            self.store.update_change_request(request_id, status="rejected", decided_by=user["id"], decided_at=time.time(),
                                     decision=reason)
            return f"Rejected: {who}, {label['what'].lower()}."
        on, d = label["on"], label["d"]
        asked = d["to"] if row["kind"] == BREAK else d["start"]
        if at is not None and at != asked:
            if not reason:
                raise ValueError("Say why you changed the time: the person sees it.")
            options, _ = self._all_options(row, now, billable)
            if at not in {c["start"] for c in options}:
                raise ValueError("That time is not one the request can be moved to.")
            d = dict(d, **({"asked_to": d["to"], "to": at} if row["kind"] == BREAK else
                           {"asked_start": d["start"], "start": at, "end": at + d["minutes"]}))
        if row["kind"] == COACHING and billable is not None and bool(billable) != bool(d.get("billable")):
            d = dict(d, asked_billable=bool(d.get("billable")), billable=bool(billable))
        try:
            if row["kind"] == BREAK:
                clock_at = (now.date() - on).days * 1440 + now.hour * 60 + now.minute
                if d["to"] < clock_at or d["from"] < clock_at:
                    raise ValueError("That time has passed: ask again for a later one.")
                self.days.move_break(row["program"], on, label["names_list"][0], d["idx"], hm(d["to"]), user["id"],
                                     suffix=f" (asked by {row['requester_name']})")
            else:
                clock_at = (now.date() - on).days * 1440 + now.hour * 60 + now.minute
                if d["start"] < clock_at:
                    raise ValueError("That time has passed: ask again for a later one.")
                for name in label["names_list"]:  # every check first, then the changes
                    self.days.add_activity(row["program"], on, name, "Coaching", hm(d["start"]), hm(d["end"]), user["id"],
                                           billable=bool(d.get("billable")), dry_run=True, with_whom=row["requester_name"],
                                           why=row["why"] or "Coaching", with_dept=d.get("dept", ""))
                for name in label["names_list"]:
                    self.days.add_activity(row["program"], on, name, "Coaching", hm(d["start"]), hm(d["end"]), user["id"],
                                           billable=bool(d.get("billable")), with_whom=row["requester_name"],
                                           why=row["why"] or "Coaching", with_dept=d.get("dept", ""))
        except (ValueError, BreakRefused) as exc:
            self.store.update_change_request(request_id, status="refused", decided_by=user["id"], decided_at=time.time(),
                                    outcome=str(exc))
            raise ValueError(f"Not applied: {exc}") from exc
        self.store.update_change_request(request_id, status="approved", decided_by=user["id"], decided_at=time.time(),
                                 decision=reason, detail=json.dumps(d))
        return f"Approved: {who}, {label['what'].lower()}."
