# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK (owner, 2026-10-15: "For fix the day, rescue, etc they should work on 24 hours based on day start at not
fixed 00;00"): Fix the day's breaks, Rescue the day and Change several breaks work on the 24 hours from the start
picked. Those tools read one day from minute 0; the window the Timeline shows (``day.window_view``) is handed to them
moved so that its start is minute 0 (``rebase``), and what they propose is moved back. Each person's shift keeps the
date it belongs to, so a change is kept on that date. A channel hold that spans the window's days answers for the
channels (``WindowHold``)."""
from __future__ import annotations

import copy
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .day import STEP


class WindowHold:
    """``channel_day.ChannelHold`` for a window: tick ``i`` of the rebased window is minute ``start + i * STEP`` from
    the first day's midnight, read from the hold of the day that holds it. Counter keys carry that day, so the same
    tick of two days never shares a counter."""

    def __init__(self, holds: Dict[int, Any], start: int):
        self.holds_by_day, self.start = holds, start

    def _at(self, i: int) -> Tuple[Optional[Any], int, int]:
        minute = self.start + i * STEP
        d = minute // 1440
        return self.holds_by_day.get(d), d, (minute - 1440 * d) // STEP

    def limits(self, name: str, i: int) -> List[Tuple[Tuple[int, Any], float]]:
        hold, d, k = self._at(i)
        return [((d, key), need) for key, need in hold.limits(name, k)] if hold is not None else []

    def current(self, key: Tuple[int, Any], i: int) -> float:
        hold, _, k = self._at(i)
        return hold.current(key[1], k) if hold is not None else 0

    def _split(self, change: Dict[int, int]) -> Dict[int, Tuple[Any, Dict[int, int]]]:
        out: Dict[int, Tuple[Any, Dict[int, int]]] = {}
        for i, delta in change.items():
            hold, d, k = self._at(i)
            if hold is not None:
                out.setdefault(d, (hold, {}))[1][k] = delta
        return out

    def holds(self, name: str, change: Dict[int, int]) -> bool:
        return all(hold.holds(name, part) for hold, part in self._split(change).values())

    def apply(self, name: str, change: Dict[int, int]) -> None:
        for hold, part in self._split(change).values():
            hold.apply(name, part)


def _moved(item: Dict[str, Any], by: int, *keys: str) -> Dict[str, Any]:
    return {**item, **{k: item[k] - by for k in keys if isinstance(item.get(k), int)}}


def rebase(view: Dict[str, Any], start: int, day_views: Dict[int, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """The window ``view`` (minutes from the first day's midnight, from ``start``) with ``start`` as minute 0, for the
    tools that read one day. People whose shift began before the window keep offset -1 (they are not moved); a person
    with two shifts starting in the window keeps the first one movable."""
    out = copy.copy(view)
    out["cells"] = [dict(c, t=c["t"] - start) for c in view["cells"]]
    out["languages"] = [dict(l, cells=[dict(c, t=c["t"] - start) for c in l["cells"]]) for l in view["languages"]]
    lanes = []
    for lane in view["lanes"]:
        segs, seen = [], False
        for s in sorted(lane["segments"], key=lambda s: s["start"]):
            seg = _moved(s, start, "start", "end")  # the marks "from" and "to" stay in the shift's own time
            seg["away"] = (s["away"][0] - start, s["away"][1] - start)
            seg["breaks"] = [_moved(b, start, "start", "planned_start") for b in s["breaks"]]
            seg["cancelled"] = [_moved(b, start, "start", "planned_start") for b in s.get("cancelled", [])]
            seg["activities"] = [_moved(a, start, "start", "end") for a in s.get("activities", [])]
            if seg["offset"] == 0:
                seg["offset"] = 1 if seen else 0
                seen = True
            segs.append(seg)
        lanes.append(dict(lane, segments=segs))
    out["lanes"] = lanes
    channels = view.get("channels")
    if channels:
        holds = {d: ((v or {}).get("channels") or {}).get("hold") for d, v in day_views.items()}
        out["channels"] = dict(channels, hold=WindowHold({d: h for d, h in holds.items() if h is not None}, start))
    out["start"] = 0
    return out


def dates_of(view: Dict[str, Any], on: date) -> Dict[Tuple[str, int], date]:
    """(name, break index) -> the date of the shift that break belongs to, for the people a tool may move."""
    return {(lane["name"], b["idx"]): s.get("date") or on for lane in view["lanes"] for s in lane["segments"]
            if s["offset"] == 0 for b in list(s["breaks"]) + list(s.get("cancelled", []))}


def in_own_day(minute: Optional[int], when: date, on: date) -> Optional[int]:
    """A window minute (from ``on``'s midnight) as a minute of ``when``'s own day."""
    return None if minute is None else minute - 1440 * (when - on).days


def by_date(items: Iterable[Tuple[str, int, Any, date]]) -> Dict[date, Dict[Tuple[str, int], Any]]:
    """(name, idx, value, date) grouped as {date: {(name, idx): value}} for ``DayBook.page(extra={"breaks": ...})``."""
    out: Dict[date, Dict[Tuple[str, int], Any]] = {}
    for name, idx, value, when in items:
        out.setdefault(when, {})[(name, idx)] = value
    return out
