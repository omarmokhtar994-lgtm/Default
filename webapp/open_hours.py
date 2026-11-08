# © 2026 Omar Mokhtar. All rights reserved.
"""The hours a channel is worked, and the minimum cover inside them (Phase BL, owner, 2026-11-07).

A channel's hours are kept as ``{"min_cover": n, "days": {"0": [from, to] | None}}``: day 0 is Sunday (the input sheet's order); a
window is minutes from that day's midnight, and ``to`` may run past 1440 (22:00 to 06:00 is [1320, 1800] and belongs to the day that
starts it); ``None`` is a day the channel is closed. A day that is not in ``days`` is as before this setting existed: open all day,
no minimum. Pure functions, no store."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .volumes_io import DAY_NAMES

MAX_COVER = 20
DEFAULT_COVER = 1
TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


def _minutes(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _window(raw: Any) -> Optional[Tuple[int, int]]:
    """A saved window as (from, to) when it is a real one, else None."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    start, end = _minutes(raw[0]), _minutes(raw[1])
    if start is None or end is None or not 0 <= start < 1440 or not start < end <= start + 1440:
        return None
    return start, end


def read(raw: Any) -> Dict[str, Any]:
    """A channel's saved hours, with anything damaged left out rather than trusted."""
    raw = raw if isinstance(raw, dict) else {}
    cover = _minutes(raw.get("min_cover"))
    days: Dict[str, Any] = {}
    for day, value in (raw.get("days") if isinstance(raw.get("days"), dict) else {}).items():
        if str(day) not in {str(i) for i in range(7)}:
            continue
        if value is None:
            days[str(day)] = None
        elif _window(value) is not None:
            days[str(day)] = list(_window(value) or ())
    return {"min_cover": cover if cover is not None and 0 <= cover <= MAX_COVER else DEFAULT_COVER, "days": days}


def ranges(hours: Dict[str, Any], day: int) -> Optional[List[Tuple[int, int]]]:
    """The minutes of day ``day`` (0 = Sunday) the channel is open, as (from, to) pairs inside 0..1440. None when nothing is set for the
    day (open all day, as before); an empty list when it is closed."""
    days = hours.get("days") or {}
    out: List[Tuple[int, int]] = []
    own = days.get(str(day), "unset")
    window = _window(own) if own not in ("unset", None) else None
    if window is not None:
        out.append((window[0], min(window[1], 1440)))
    spill = _window(days.get(str((day - 1) % 7)))
    if spill is not None and spill[1] > 1440:
        out.append((0, spill[1] - 1440))
    if out:
        return out
    return [] if own is None else None


def free_from(hours: Dict[str, Any], day: int) -> Optional[int]:
    """The minute from which an unset day is left alone because yesterday's overnight hours only spill into its start; None otherwise.
    A day with its own hours, or closed, has none: after the spill ends it is not open all day."""
    if str(day) in (hours.get("days") or {}):
        return None
    spill = _window((hours.get("days") or {}).get(str((day - 1) % 7)))
    return spill[1] - 1440 if spill is not None and spill[1] > 1440 else None


def apply(needs: Sequence[float], open_ranges: Optional[Sequence[Tuple[int, int]]], step: int, min_cover: int,
          free_from_minute: Optional[int] = None) -> List[float]:
    """One day's people-needed row with the hours applied: nobody outside them, at least ``min_cover`` inside them. From
    ``free_from_minute`` (an unset day after an overnight day) the intervals outside the spill keep what they were."""
    if open_ranges is None:
        return list(needs)
    out: List[float] = []
    for i, n in enumerate(needs):
        start, end = i * step, (i + 1) * step
        inside = any(start < hi and end > lo for lo, hi in open_ranges)
        if inside:
            out.append(max(n, min_cover))
        else:
            out.append(n if free_from_minute is not None else 0)
    return out


def clock_minutes(text: str, label: str) -> int:
    """A time typed as 09:00 (up to 24:00) as minutes from midnight; ValueError in words, starting with ``label``, otherwise."""
    found = TIME.match(text.strip())
    if not found:
        raise ValueError(f"{label}: type the time as 09:00 (24 hour clock).")
    hour, minute = int(found.group(1)), int(found.group(2))
    if minute > 59 or hour > 24 or (hour == 24 and minute):
        raise ValueError(f"{label}: type the time as 09:00 (24 hour clock), up to 24:00.")
    return hour * 60 + minute


def from_form(form: Dict[str, Any], channel: str) -> Dict[str, Any]:
    """The hours a Settings form typed, checked whole: ``min_cover`` and, per day, ``{d}.from``, ``{d}.to`` and ``{d}.closed``. Both
    times empty leaves the day unset. Email keeps no minimum cover."""
    try:
        cover = int(str(form.get("min_cover", DEFAULT_COVER)).strip())
    except ValueError:
        raise ValueError(f"{channel}: the minimum cover is a whole number from 0 to {MAX_COVER}.") from None
    if not 0 <= cover <= MAX_COVER:
        raise ValueError(f"{channel}: the minimum cover is a whole number from 0 to {MAX_COVER}.")
    days: Dict[str, Any] = {}
    for d in range(7):
        label = f"{channel}, {DAY_NAMES[d]}"
        if str(form.get(f"{d}.closed", "")).strip() in ("1", "on", "true"):
            days[str(d)] = None
            continue
        opening, closing = str(form.get(f"{d}.from", "")).strip(), str(form.get(f"{d}.to", "")).strip()
        if not opening and not closing:
            continue
        if not opening or not closing:
            raise ValueError(f"{label}: type both the opening and the closing time, or tick closed.")
        start, end = clock_minutes(opening, label), clock_minutes(closing, label)
        if start >= 1440:
            raise ValueError(f"{label}: the opening time is before 24:00.")
        if end == start:
            raise ValueError(f"{label}: opening and closing are the same time. Type 00:00 to 24:00 for a day that is open all day.")
        if end < start:
            end += 1440
        days[str(d)] = [start, end]
    return {"min_cover": 0 if channel == "Email" else cover, "days": days}
