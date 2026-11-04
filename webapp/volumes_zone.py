# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "I may add actuals in EST and request required associates in Egypt time"): volumes across time zones.

Two jobs, both by the site's own clock (``webapp/clock.py``: named zones, so each region's clock changes land on their own dates):
  * ``convert_rows``: actuals typed, pasted or uploaded in one zone become rows in the program's zone. A time that does not exist or happens twice because a
    region's clocks changed cannot be placed and is refused, naming the day, rather than guessed. Rows that land on the same interval (the hour a region repeats
    in the target zone) are added up, the handle time weighted by volume.
  * ``rotate_grid``: a week's grid (days Sun to Sat, intervals down) shown in another zone. The same seven dates, each cell moved to the date and interval it has there;
    what spills over the edge of the week goes to the other end of the same week (this week's pattern stands in for the neighbouring week), so a total is never lost or
    made up. A forecast has no source clock to refuse, so the hour a region skips is placed by the clock without complaint.
Every zone the site offers has a whole-hour offset, so every interval (5 to 60 minutes) lines up after a move.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from .clock import HOME, ZONES, converted

NAMES = dict(ZONES)
Row = Tuple[str, int, float, Optional[float]]


def check_zone(value: Any, what: str = "The time zone") -> str:
    if not isinstance(value, str) or value not in NAMES:
        raise ValueError(f"{what} is one of the zones in the list.")
    return value


def _name(zone: str) -> str:
    return NAMES[zone].split(" (")[0]


def _constant_shift(day: date, src: ZoneInfo, dst: ZoneInfo) -> Optional[int]:
    """Minutes to add to every time of ``day`` in ``src`` to read it in ``dst``, when neither clock changes during the day or in the target's reading of it; else None."""
    start = datetime.combine(day, time(0), src)
    end = datetime.combine(day, time(23, 59), src)
    if start.utcoffset() != end.utcoffset():
        return None
    a, b = start.astimezone(dst), end.astimezone(dst)
    if a.utcoffset() != b.utcoffset():
        return None
    return int((a.replace(tzinfo=None) - start.replace(tzinfo=None)).total_seconds() // 60)


def convert_rows(rows: Sequence[Row], from_zone: Any, to_zone: Any, step: int) -> Tuple[List[Row], List[str]]:
    """``rows`` ``(day, minute, offered, aht)`` read in ``from_zone`` as rows in ``to_zone``, and the problems (one per day) for times that cannot be placed.
    The same zone returns the rows as they are."""
    src_key, dst_key = check_zone(from_zone, "The zone the file is in"), check_zone(to_zone, "The program's zone")
    if src_key == dst_key:
        return list(rows), []
    src, dst = ZoneInfo(src_key), ZoneInfo(dst_key)
    merged: Dict[Tuple[str, int], List[float]] = {}
    problems: List[str] = []
    refused: set = set()
    shifts: Dict[str, Optional[int]] = {}
    for day, minute, offered, aht in rows:
        if day in refused:
            continue
        shift = shifts.setdefault(day, _constant_shift(date.fromisoformat(day), src, dst))
        try:
            if shift is not None:
                moved = datetime.combine(date.fromisoformat(day), time()) + timedelta(minutes=int(minute) + shift)
            else:
                moved = converted(date.fromisoformat(day), int(minute), src_key, dst_key).replace(tzinfo=None)
        except ValueError as exc:
            refused.add(day)
            said = str(exc)
            at = f"{int(minute) // 60:02d}:{int(minute) % 60:02d}"
            if "does not exist" in said:
                problems.append(f"{day} {at} does not exist in {_name(src_key)} time because the clocks change that day. Take that time out of the file or send the day in the program's own zone.")
            else:
                problems.append(f"{day} {at} happens twice in {_name(src_key)} time because the clocks change that day, and the file does not say which. Send that day in the program's own zone.")
            continue
        key = (moved.date().isoformat(), moved.hour * 60 + moved.minute)
        got = merged.setdefault(key, [0.0, 0.0, 0.0])
        got[0] += float(offered)
        if aht is not None and offered > 0:
            got[1] += float(aht) * float(offered)
            got[2] += float(offered)
    out = [(d, m, v[0], (v[1] / v[2]) if v[2] > 0 else None) for (d, m), v in sorted(merged.items())]
    return ([] if problems else out), problems


def rotate_grid(grid: Sequence[Sequence[Any]], week_start: date, from_zone: Any, to_zone: Any, step: int, combine: str = "sum") -> List[List[Any]]:
    """The week's grid (``grid[day][interval]``, days Sun to Sat) read in ``to_zone`` instead of ``from_zone`` (see the module note). ``combine`` says what two
    cells that land on one do: "sum" (contacts), "max" (people needed) or "first" (a percentage; a blank stays blank)."""
    src_key, dst_key = check_zone(from_zone, "The zone the grid is in"), check_zone(to_zone, "The zone to show")
    slots = 1440 // step if step and 1440 % step == 0 else 0
    if not slots or len(grid) != 7 or any(len(r) != slots for r in grid):
        raise ValueError("A week's grid is seven days of whole intervals.")
    if combine not in ("sum", "max", "first"):
        raise ValueError("Cells that land together are added, or the larger is taken, or the first is kept.")
    if src_key == dst_key:
        return [list(r) for r in grid]
    src, dst = ZoneInfo(src_key), ZoneInfo(dst_key)
    start_idx = lambda d: (d.weekday() + 1) % 7                                    # Sunday first, as the input sheet is   # noqa: E731
    dates = {start_idx(week_start + timedelta(days=k)): week_start + timedelta(days=k) for k in range(7)}
    out: List[List[Any]] = [[None if combine == "first" else 0 for _ in range(slots)] for _ in range(7)]
    for d in range(7):
        for i in range(slots):
            value = grid[d][i]
            if value is None:
                continue
            wall = datetime.combine(dates[d], time()) + timedelta(minutes=i * step)
            there = wall.replace(tzinfo=src).astimezone(timezone.utc).astimezone(dst)
            day = week_start + timedelta(days=(there.date() - week_start).days % 7)
            j, k = start_idx(day), (there.hour * 60 + there.minute) // step
            if combine == "sum":
                out[j][k] += value
            elif combine == "max":
                out[j][k] = max(out[j][k], value)
            elif out[j][k] is None:
                out[j][k] = value
    return out
