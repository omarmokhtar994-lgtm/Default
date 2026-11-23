# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "I may add actuals in EST and request required associates in Egypt time"): volumes across time zones.

Two jobs, both by the site's own clock (``webapp/clock.py``: named zones, so each region's clock changes land on their own dates):
  * ``convert_rows``: actuals typed, pasted or uploaded in one zone become rows in the program's zone. The hour a region's clocks repeat is read as its first
    occurrence (an export by local day has that hour once), and the note says so. The hour they skip does not exist: its empty rows are left out (said in a note) and a row
    with volume in it is refused, naming the day. Rows that land on the same interval (the hour the target repeats) are added up, the handle time weighted by volume.
  * ``rotate_grid``: a week's grid (days Sun to Sat, intervals down) shown in another zone. The same seven dates, each cell moved to the date and interval it has there;
    what spills over the edge of the week goes to the other end of the same week (this week's pattern stands in for the neighbouring week), so a total is never lost or
    made up. A forecast has no source clock to refuse, so the hour a region skips is placed by the clock without complaint.
Every zone the site offers has a whole-hour offset, so every interval (5 to 60 minutes) lines up after a move.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from .clock import HOME, ZONES as SITE_ZONES

# The site's zones, and US Eastern all year for exports that never change with the seasons (no repeated or skipped hour).
ZONES = SITE_ZONES + (("Etc/GMT+5", "EST (US Eastern, no daylight saving)"),)
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


def convert_rows(rows: Sequence[Row], from_zone: Any, to_zone: Any, step: int, notes: Optional[List[str]] = None) -> Tuple[List[Row], List[str]]:
    """``rows`` ``(day, minute, offered, aht)`` read in ``from_zone`` as rows in ``to_zone``, and the problems (one per day) for volume in an hour that does not exist.
    What was read as the first of a repeated hour, or left out as an empty skipped hour, is added to ``notes`` (one line per day). The same zone returns the rows as they are."""
    src_key, dst_key = check_zone(from_zone, "The zone the file is in"), check_zone(to_zone, "The program's zone")
    if src_key == dst_key:
        return list(rows), []
    src, dst = ZoneInfo(src_key), ZoneInfo(dst_key)
    merged: Dict[Tuple[str, int], List[float]] = {}
    problems: List[str] = []
    said: set = set()
    shifts: Dict[str, Optional[int]] = {}
    refused: set = set()
    for day, minute, offered, aht in rows:
        if day in refused:
            continue
        shift = shifts.setdefault(day, _constant_shift(date.fromisoformat(day), src, dst))
        if shift is not None:
            moved = datetime.combine(date.fromisoformat(day), time()) + timedelta(minutes=int(minute) + shift)
        else:
            wall = datetime.combine(date.fromisoformat(day), time()) + timedelta(minutes=int(minute))
            there = wall.replace(tzinfo=src, fold=0)
            at = f"{int(minute) // 60:02d}:{int(minute) % 60:02d}"
            if there.astimezone(timezone.utc).astimezone(src).replace(tzinfo=None) != wall:       # the clocks jump over this time
                if float(offered) == 0:
                    if (day, "skip") not in said:
                        said.add((day, "skip"))
                        if notes is not None:
                            notes.append(f"{day}: the clocks in {_name(src_key)} skip {at}, so its empty rows were left out.")
                    continue
                refused.add(day)
                problems.append(f"{day} {at} does not exist in {_name(src_key)} time because the clocks change that day, yet it holds contacts. Check the file's times for that day.")
                continue
            if there.utcoffset() != there.replace(fold=1).utcoffset() and (day, "twice") not in said:
                said.add((day, "twice"))
                if notes is not None:
                    notes.append(f"{day}: {at} happens twice in {_name(src_key)} time because the clocks change that day; it was read as the first one.")
            moved = there.astimezone(dst).replace(tzinfo=None)
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


def stitch(before: Optional[Sequence[Sequence[Any]]], this: Sequence[Sequence[Any]], after: Optional[Sequence[Sequence[Any]]], week_start: date,
           from_zone: Any, to_zone: Any, step: int, combine: str = "sum") -> List[List[Any]]:
    """Phase BM: the week starting ``week_start`` read in ``to_zone``, from three weeks of grids kept in ``from_zone`` (the week before, the week,
    the week after; days Sun to Sat). The hours past the week's edge come from the neighbouring week; a neighbour that is None is taken to look like
    this week (which is what ``rotate_grid`` assumes for both). ``combine`` as in ``rotate_grid``."""
    src_key, dst_key = check_zone(from_zone, "The zone the grid is in"), check_zone(to_zone, "The zone to show")
    slots = 1440 // step if step and 1440 % step == 0 else 0
    if not slots or any(g is not None and (len(g) != 7 or any(len(r) != slots for r in g)) for g in (before, this, after)) or this is None:
        raise ValueError("A week's grid is seven days of whole intervals.")
    if combine not in ("sum", "max", "first"):
        raise ValueError("Cells that land together are added, or the larger is taken, or the first is kept.")
    if src_key == dst_key:
        return [list(r) for r in this]
    src, dst = ZoneInfo(src_key), ZoneInfo(dst_key)
    out: List[List[Any]] = [[None if combine == "first" else 0 for _ in range(slots)] for _ in range(7)]
    for offset, grid in ((-7, before if before is not None else this), (0, this), (7, after if after is not None else this)):
        for d in range(7):
            day = week_start + timedelta(days=offset + d)
            for i in range(slots):
                value = grid[d][i]
                if value is None:
                    continue
                there = (datetime.combine(day, time()) + timedelta(minutes=i * step)).replace(tzinfo=src).astimezone(timezone.utc).astimezone(dst)
                j = (there.date() - week_start).days
                if not 0 <= j < 7:
                    continue
                k = (there.hour * 60 + there.minute) // step
                if combine == "sum":
                    out[j][k] += value
                elif combine == "max":
                    out[j][k] = max(out[j][k], value)
                elif out[j][k] is None:
                    out[j][k] = value
    return out


def minutes_between(from_zone: Any, to_zone: Any, on: date) -> int:
    """Minutes to add to a time in ``from_zone`` to read it in ``to_zone`` on the date ``on`` (taken at noon)."""
    src, dst = check_zone(from_zone, "The zone the hours are typed in"), check_zone(to_zone, "The program's zone")
    noon = datetime.combine(on, time(12))
    return int((noon.replace(tzinfo=ZoneInfo(src)).utcoffset() - noon.replace(tzinfo=ZoneInfo(dst)).utcoffset()).total_seconds() // -60)


DAY_WORDS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def shift_hours(days: Dict[str, Any], minutes: int) -> Dict[str, Any]:
    """Hours worked (weekday "0" = Sunday -> [opens, closes] in minutes, None for closed, absent for unset) moved ``minutes`` later (earlier when
    negative). A window keeps its length and belongs to the weekday its opening lands on; a day whose hours left and got none is closed; closed and
    unset days otherwise stay. Two windows landing on one weekday cannot be kept and are refused in words."""
    if not minutes:
        return dict(days)
    out: Dict[str, Any] = {d: None for d, v in days.items() if v is None}
    landed: Dict[str, List[int]] = {}
    for d, window in days.items():
        if window is None:
            continue
        start = int(window[0]) + minutes
        day = str((int(d) + start // 1440) % 7)
        if day in landed:
            raise ValueError(f"Moved into the program's time zone, {DAY_WORDS[int(day)]} would have two sets of hours. Type the hours in the program's zone.")
        landed[day] = [start % 1440, start % 1440 + int(window[1]) - int(window[0])]
        out.setdefault(str(d), None)                                # where it left: closed unless a window lands there
    out.update(landed)
    return out
