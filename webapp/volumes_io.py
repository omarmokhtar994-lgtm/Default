# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI: reading actual volumes in (owner, 2026-11-03: "adding actuals as input for volumes received per channel", "same as the input sheet,
days and intervals, so it is easy to copy and paste").

Two shapes are read, from a file (csv or xlsx) or from text pasted out of Excel:
  * long: one row per date and interval (Date, Interval, Channel, Offered, AHT); the channel may come from the page instead;
  * grid: the input sheet's layout, intervals down the side and Sun to Sat across (Interval, Sun, Mon, ...), one week and one channel; the
    handle time may be a second grid of the same shape.
Everything is checked before anything is kept: one bad row means no row is taken, and each reason names its row (never the text typed in it).
Finer rows than the program's interval are added up to it (the handle time weighted by volume); coarser rows that are a whole number of the program's
intervals (hourly rows in a 30-minute program) are shared evenly over them (Phase BM), others are refused in words.
"""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .bulk_users import _rows
from .upload_guard import look_rows
from .volumes_grain import share

CHANNELS = ("Phone", "Chat", "Email")
DAY_NAMES = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
MAX_ROWS = 400_000
MAX_VOLUME = 1_000_000          # offered in one interval; above this a cell is a typing slip
MAX_AHT = 7200.0                # seconds
FIRST_DAY = date(2015, 1, 1)
STEPS = (5, 10, 15, 20, 30, 60)
SHOWN_PROBLEMS = 20

CHANNEL_WORDS = {"phone": "Phone", "voice": "Phone", "call": "Phone", "calls": "Phone", "chat": "Chat", "messaging": "Chat", "email": "Email",
                 "e-mail": "Email", "mail": "Email", "back office": "Email"}
HEADERS = {
    "date": {"date", "day", "shift date", "interval date"},
    "interval": {"interval", "interval start", "start", "start time", "time", "interval time"},
    "channel": {"channel", "queue", "skill", "media"},
    "offered": {"offered", "volume", "calls", "calls offered", "contacts", "received", "offered volume", "chats", "emails", "contacts offered"},
    "aht": {"aht", "aht seconds", "aht (seconds)", "aht (s)", "handle time", "average handle time", "avg handle time"},
}


@dataclass
class ParsedVolumes:
    rows: Dict[str, List[Tuple[str, int, float, Optional[float]]]] = field(default_factory=dict)
    problems: List[str] = field(default_factory=list)
    summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)         # what was read or skipped and why, when it is not a problem


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "").strip().lower())


def read_table(data: bytes, filename: str) -> List[List[Any]]:
    """The cells of an uploaded csv or workbook (first sheet), after the site's own look at it (no card numbers, addresses or links out)."""
    if not filename.lower().endswith((".csv", ".xlsx")):
        raise ValueError("Upload a .csv or .xlsx file, or paste the table.")
    rows = _rows(data, filename)
    if len(rows) > MAX_ROWS:
        raise ValueError(f"At most {MAX_ROWS:,} rows at a time; this file has {len(rows):,}.")
    refused = look_rows(rows, "the volumes file")
    if refused:
        raise ValueError(refused)
    return rows


def parse_pasted(text: str) -> List[List[str]]:
    """Text copied out of Excel (tabs), or comma or semicolon separated, as rows of trimmed cells; blank lines dropped."""
    lines = [ln for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    if len(lines) > MAX_ROWS:
        raise ValueError(f"At most {MAX_ROWS:,} rows at a time; this text has {len(lines):,}.")
    head = "\n".join(lines[:30])
    delimiter = "\t" if "\t" in head else ";" if head.count(";") >= head.count(",") and ";" in head else ","
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)]


def minute_of(value: Any) -> Optional[int]:
    """A time of day as minutes after midnight: 09:30, 9:30, 09:30:00, 1:15 PM, a spreadsheet time or day fraction; None when it is not one."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.hour * 60 + value.minute
    if hasattr(value, "hour"):
        return value.hour * 60 + value.minute
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 0 <= value < 1:
            return int(round(value * 1440)) % 1440
        return None
    text = str(value).strip()
    found = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?", text)
    if not found:
        return None
    hour, minute, suffix = int(found.group(1)), int(found.group(2)), (found.group(3) or "").lower()
    if minute > 59:
        return None
    if suffix:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if suffix == "pm" else 0)
    elif hour > 23:
        return None
    return hour * 60 + minute


def date_of(value: Any) -> Optional[date]:
    """A date from a spreadsheet date, 2026-10-26, 26/10/2026 or 26-10-2026 (day first); None when it is not one."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value if value is not None else "").strip()
    for pattern, order in ((r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"), (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "dmy")):
        found = re.fullmatch(pattern, text)
        if found:
            a, b, c = (int(x) for x in found.groups())
            try:
                return date(a, b, c) if order == "ymd" else date(c, b, a)
            except ValueError:
                return None
    return None


def _number(value: Any) -> Optional[float]:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    text = str(value).strip().replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    return float(text)


def _channel(value: Any) -> Optional[str]:
    return CHANNEL_WORDS.get(_norm(value)) or (str(value).strip().title() if str(value).strip().title() in CHANNELS else None)


def _file_step(minutes: Sequence[int]) -> int:
    ordered = sorted(set(minutes))
    gaps = [b - a for a, b in zip(ordered, ordered[1:])]
    if not gaps:
        return 0
    from math import gcd
    from functools import reduce
    return reduce(gcd, gaps)


def _finish(by_channel: Dict[str, Dict[Tuple[str, int], Tuple[float, Optional[float]]]], step: int,
            problems: List[str]) -> ParsedVolumes:
    """Check the step, add finer rows up to the program's interval, and build the summary."""
    out = ParsedVolumes(problems=problems)
    if problems:
        return _capped(out)
    for channel, cells in by_channel.items():
        minutes = [m for (_d, m) in cells]
        file_step = _file_step(minutes)
        if file_step and file_step not in STEPS:
            problems.append(f"{channel}: the intervals are {file_step} minutes apart; use 5, 10, 15, 20, 30 or 60.")
            continue
        if file_step > step and file_step % step:
            problems.append(f"{channel}: the file's intervals are {file_step}-minute; this program's are {step}-minute. Upload the finer data.")
            continue
        if file_step > step:  # Phase BM: hourly rows in a 30-minute program are hourly history: each row is shared over the program's intervals
            parts = file_step // step
            cells = {(day, minute + i * step): (part, aht) for (day, minute), (offered, aht) in cells.items()
                     for i, part in enumerate(share(offered, parts))}
            out.notes.append(f"{channel}: the rows are {'hourly' if file_step == 60 else f'{file_step} minutes apart'}, so each is shared evenly over this program's "
                             f"{step}-minute intervals.")
            file_step = step
        if file_step and step % file_step:
            problems.append(f"{channel}: {file_step}-minute rows do not add up to this program's {step}-minute intervals.")
            continue
        if any(m % file_step for m in minutes) if file_step else False:
            problems.append(f"{channel}: some times are off the {file_step}-minute grid.")
            continue
        if not file_step and any(m % step for m in minutes):
            problems.append(f"{channel}: a time is off the {step}-minute grid.")
            continue
        merged: Dict[Tuple[str, int], List[float]] = {}
        for (day, minute), (offered, aht) in cells.items():
            slot = (day, minute // step * step)
            got = merged.setdefault(slot, [0.0, 0.0, 0.0])  # offered, aht seconds x offered, offered with an aht
            got[0] += offered
            if aht is not None and offered > 0:
                got[1] += aht * offered
                got[2] += offered
        rows = [(day, minute, vals[0], (vals[1] / vals[2]) if vals[2] > 0 else None) for (day, minute), vals in sorted(merged.items())]
        out.rows[channel] = rows
        days = sorted({r[0] for r in rows})
        out.summary[channel] = {"rows": len(rows), "days": len(days), "first": days[0], "last": days[-1]}
    if problems:
        out.rows, out.summary = {}, {}
    return _capped(out)


def _capped(parsed: ParsedVolumes) -> ParsedVolumes:
    if len(parsed.problems) > SHOWN_PROBLEMS:
        extra = len(parsed.problems) - SHOWN_PROBLEMS
        parsed.problems = parsed.problems[:SHOWN_PROBLEMS] + [f"... and {extra} more."]
    return parsed


def _header(table: Sequence[Sequence[Any]], want: Sequence[str]) -> Tuple[int, Dict[str, int]]:
    for i, row in enumerate(table[:30]):
        found: Dict[str, int] = {}
        for j, cell in enumerate(row):
            for key, words in HEADERS.items():
                if _norm(cell) in words and key not in found:
                    found[key] = j
        if all(k in found for k in want):
            return i, found
    raise ValueError("The table needs a header row with Date, Interval and Offered (and Channel and AHT if you have them).")


def parse_long(table: Sequence[Sequence[Any]], channel: Optional[str], step: int, today: date) -> ParsedVolumes:
    """A long table (a row per date and interval) as rows per channel; ``channel`` fills in for a table with no channel column.

    Email may instead be a table of day totals (Date, Emails and an optional AHT; Phase BL, owner, 2026-11-07: "for emails I can share historical day by
    day, not per interval, as it doesn't matter"). A day total is kept spread evenly over the day's intervals, every email counted."""
    daily = False
    try:
        head, cols = _header(table, ("date", "interval", "offered"))
    except ValueError:
        head, cols = _header(table, ("date", "offered"))
        if channel and _channel(channel) != "Email":
            raise ValueError("A date and a count with no interval is only for email. Phone and chat need a row for each date and interval.") from None
        daily = True
    problems: List[str] = []
    by_channel: Dict[str, Dict[Tuple[str, int], Tuple[float, Optional[float]]]] = {}
    default = _channel(channel) if channel else None
    if "channel" not in cols and not default:
        problems.append("The table has no Channel column: pick the channel on the page.")
    count = 0
    for n, row in enumerate(table[head + 1:], start=head + 2):
        if not any(str(c or "").strip() for c in row):
            continue
        count += 1
        get = lambda key: row[cols[key]] if key in cols and cols[key] < len(row) else None  # noqa: E731
        day, minute = date_of(get("date")), (0 if daily else minute_of(get("interval")))
        ch = _channel(get("channel")) if "channel" in cols else default
        offered, aht = _number(get("offered")), _number(get("aht"))
        why = []
        if day is None:
            why.append("the date is not a date")
        elif day < FIRST_DAY or day > today:
            why.append("the date is outside the range (after 2015 and not in the future)")
        if minute is None:
            why.append("the interval is not a time")
        if ch is None:
            why.append("the channel is not Phone, Chat or Email")
        elif daily and ch != "Email":
            why.append("a day total is only for email")
        if offered is None:
            why.append("the volume is not a number")
        elif offered < 0 or offered != int(offered) or offered > MAX_VOLUME:
            why.append("the volume must be a whole number, 0 to 1,000,000")
        if get("aht") not in (None, "") and (aht is None or not 1 <= aht <= MAX_AHT):
            why.append("the handle time is 1 to 7,200 seconds")
        if why:
            problems.append(f"Row {n}: " + "; ".join(why) + ".")
            continue
        key = (day.isoformat(), minute)
        cells = by_channel.setdefault(ch, {})
        if key in cells:
            problems.append(f"Row {n}: {day.isoformat()} {ch} is in the table twice." if daily
                            else f"Row {n}: {day.isoformat()} {minute // 60:02d}:{minute % 60:02d} {ch} is in the table twice.")
            continue
        if daily:                                           # spread the day evenly, whole emails, none lost
            slots = 1440 // step
            for k in range(slots):
                cells[(day.isoformat(), k * step)] = (float(round((k + 1) * offered / slots) - round(k * offered / slots)), aht)
            continue
        cells[key] = (offered, aht)
    if not count and not problems:
        problems.append("The table has no rows under its header.")
    parsed = _finish(by_channel, step, problems)
    if daily and parsed.rows:
        parsed.notes.append("These are day totals: each day's emails were spread evenly over its intervals, with every email kept.")
    return parsed


def _date_for(week_start: date, day_name: str) -> date:
    """The date in the week that starts on ``week_start`` that falls on ``day_name`` (a Monday-start week has its Sunday last)."""
    index = DAY_NAMES.index(day_name)  # Sun = 0
    for k in range(7):
        d = week_start + timedelta(days=k)
        if (d.weekday() + 1) % 7 == index:
            return d
    raise ValueError("No such day in that week.")


def _grid_cells(table: Sequence[Sequence[Any]], what: str) -> Tuple[Dict[Tuple[str, int], Optional[float]], List[str]]:
    for i, row in enumerate(table[:30]):
        names = {j: str(c).strip().title()[:3] for j, c in enumerate(row) if str(c or "").strip().title()[:3] in DAY_NAMES and j > 0}
        if _norm(row[0] if row else None) == "interval" and names:
            head = i
            break
    else:
        raise ValueError(f"The {what} needs a header row with Interval and the days (Sun, Mon, ... Sat), like the input sheet.")
    cells: Dict[Tuple[str, int], Optional[float]] = {}
    problems: List[str] = []
    for n, row in enumerate(table[head + 1:], start=head + 2):
        minute = minute_of(row[0] if row else None)
        if minute is None:
            if row and str(row[0] or "").strip():
                problems.append(f"Row {n}: the interval is not a time.")
            continue
        for j, day in names.items():
            value = row[j] if j < len(row) else None
            if value is None or str(value).strip() == "":
                cells[(day, minute)] = None
                continue
            number = _number(value)
            if number is None or number < 0:
                problems.append(f"Row {n}, {day}: the {what} is not a number of zero or more.")
                continue
            cells[(day, minute)] = number
    return cells, problems


def parse_grid(table: Sequence[Sequence[Any]], week_start: date, channel: str, aht_table: Optional[Sequence[Sequence[Any]]],
               step: int, today: date) -> ParsedVolumes:
    """The input sheet's layout (Interval, Sun to Sat) for the week that starts on ``week_start`` and one channel, with an optional second grid for
    the handle time. A day column with nothing in it is left out; a blank among numbers is zero."""
    ch = _channel(channel)
    if ch is None:
        raise ValueError("Pick the channel: Phone, Chat or Email.")
    cells, problems = _grid_cells(table, "volume")
    aht_cells: Dict[Tuple[str, int], Optional[float]] = {}
    if aht_table:
        aht_cells, more = _grid_cells(aht_table, "handle time")
        problems += more
    by_cell: Dict[Tuple[str, int], Tuple[float, Optional[float]]] = {}
    live_days = {day for (day, _m), v in cells.items() if v is not None}
    for (day, minute), value in cells.items():
        if day not in live_days:
            continue
        when = _date_for(week_start, day)
        if when < FIRST_DAY or when > today:
            problems.append(f"{day} {when.isoformat()} is outside the range (after 2015 and not in the future).")
            continue
        aht = aht_cells.get((day, minute))
        if aht is not None and not 1 <= aht <= MAX_AHT:
            problems.append(f"{day} {minute // 60:02d}:{minute % 60:02d}: the handle time is 1 to 7,200 seconds.")
            continue
        offered = value or 0.0
        if offered != int(offered) or offered > MAX_VOLUME:
            problems.append(f"{day} {minute // 60:02d}:{minute % 60:02d}: the volume must be a whole number, 0 to 1,000,000.")
            continue
        by_cell[(when.isoformat(), minute)] = (offered, aht)
    if not by_cell and not problems:
        problems.append("The grid has no numbers in it.")
    return _finish({ch: by_cell}, step, problems)
