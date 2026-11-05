# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04): what is known about next week that the history cannot show, as numbers the forecast can use.

  * events: a promotion, launch, outage or holiday, with the channels it touches, its dates, the change it brings in percent, and (optionally) a dip or lift
    for some days after it ends;
  * AI and automation: a period in which a channel's contacts fall (or rise) by a percent, optionally with a share of what falls away coming back on another
    channel; a later period can reduce more, less, or reverse it;
  * growth: the customer or contact increase year over year per channel, used instead of the trend the history shows when the planner says so;
  * last year: the total of the same week a year ago per channel, grown by the year-over-year rate, offered as a second suggestion;
  * weeks the planner excludes from the history.

Everything here is pure: plain dicts and numbers in, plain dicts and numbers out, no store. Entry is strict (a bad figure is refused in words and nothing is
kept); ``clean_document`` is the one gate a stored document passes on its way in and out. Percent figures are changes (25 means 25 percent more, -10 means 10
percent fewer); a day's factor is the product of every driver on it, so two events on one day multiply.
"""
from __future__ import annotations

import copy
import math
import statistics
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .volumes_io import CHANNELS

KINDS = ("Promotion", "Launch", "Outage", "Holiday", "Other")
METHODS = ("measured", "growth")        # the trend the history shows, or the year-over-year rate the planner types
MAX_ROWS = 40                           # events, and AI periods, per list
MAX_EVENT_DAYS = 366
MAX_AI_DAYS = 731
MAX_AFTER_DAYS = 28
CHANGE_LOW, CHANGE_HIGH = -100.0, 500.0          # exclusive, inclusive: -100 would be no contacts at all
YOY_LOW, YOY_HIGH = -50.0, 200.0
MAX_NAME = 80
MAX_SKIPPED = 60
MAX_TOTAL = 5_000_000
FIRST, LAST = date(2020, 1, 1), date(2040, 12, 31)
LISTS = ("events", "ai")


# --- single figures ------------------------------------------------------------------------------------------------------------

def _number(value: Any, what: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{what} is a number.")
    if isinstance(value, str):
        text = value.strip().replace("%", "").replace(",", "").replace(" ", "")
        try:
            value = float(text)
        except ValueError:
            raise ValueError(f"{what} is a number.") from None
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} is a number.") from None
    if not math.isfinite(out):
        raise ValueError(f"{what} is a number.")
    return out


def _change(value: Any, what: str) -> float:
    out = _number(value, what)
    if not CHANGE_LOW < out <= CHANGE_HIGH:
        raise ValueError(f"{what} is in percent, more than -100 and at most {CHANGE_HIGH:.0f}. For example 25 means 25% more and -10 means 10% fewer.")
    return out


def _date(value: Any, what: str) -> date:
    if isinstance(value, date):
        out = value
    else:
        try:
            out = date.fromisoformat(str(value).strip())
        except ValueError:
            raise ValueError(f"{what} is a date as year-month-day.") from None
    if not FIRST <= out <= LAST:
        raise ValueError(f"{what} is between {FIRST.isoformat()} and {LAST.isoformat()}.")
    return out


def _on(text: str) -> date:
    return date.fromisoformat(text)


def _channel(value: Any, what: str) -> str:
    if value not in CHANNELS:
        raise ValueError(f"{what} is one of {', '.join(CHANNELS)}.")
    return value


def _name(value: Any) -> str:
    text = " ".join(str(value if value is not None else "").split())
    if not text:
        raise ValueError("Type a name, up to 80 characters.")
    if len(text) > MAX_NAME:
        raise ValueError(f"A name is at most {MAX_NAME} characters.")
    if text[0] in "=+-@" or any(ord(ch) < 32 for ch in text):
        raise ValueError("Start the name with a letter or a number (not = + - or @).")
    return text


def _span(start: date, end: date, longest: int) -> None:
    if end < start:
        raise ValueError("Pick an end date on or after the start date.")
    if (end - start).days + 1 > longest:
        raise ValueError(f"A period is at most {longest} days: split a longer one into two.")


# --- one event, one AI period ----------------------------------------------------------------------------------------------------

def clean_event(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("An event is a set of fields.")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise ValueError(f"The kind of event is one of {', '.join(KINDS)}.")
    channels = raw.get("channels")
    if isinstance(channels, str):
        channels = [channels]
    if not isinstance(channels, (list, tuple)) or not channels:
        raise ValueError("Choose at least one channel.")
    for ch in channels:
        _channel(ch, "A channel")
    start, end = _date(raw.get("start"), "The start date"), _date(raw.get("end"), "The end date")
    _span(start, end, MAX_EVENT_DAYS)
    change = _change(raw.get("change"), "The change")
    if change == 0:
        raise ValueError("The change is not zero: type a percent such as 25 or -10.")
    after_days_raw = raw.get("after_days", 0)
    after_days = 0 if after_days_raw in (None, "") else _number(after_days_raw, "The days after")
    if after_days != int(after_days) or not 0 <= after_days <= MAX_AFTER_DAYS:
        raise ValueError(f"The days after is a whole number from 0 to {MAX_AFTER_DAYS}.")
    after_days = int(after_days)
    after_raw = raw.get("after_change", 0)
    after_change = 0.0 if after_raw in (None, "") else _change(after_raw, "The change after")
    if after_days == 0 and after_change != 0:
        raise ValueError("Say how many days the change after lasts, or leave it empty.")
    if after_days and after_change == 0:
        raise ValueError("Say the change in percent for the days after, or set the days to 0.")
    return {"kind": kind, "name": _name(raw.get("name")), "channels": [ch for ch in CHANNELS if ch in channels],
            "start": start.isoformat(), "end": end.isoformat(), "change": change, "after_days": after_days, "after_change": after_change}


def clean_ai(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("An AI period is a set of fields.")
    channel = _channel(raw.get("channel"), "The channel")
    start, end = _date(raw.get("start"), "The start date"), _date(raw.get("end"), "The end date")
    _span(start, end, MAX_AI_DAYS)
    change = _change(raw.get("change"), "The change")
    if change == 0:
        raise ValueError("The change is not zero: type a percent such as 25 or -10.")
    move_to = raw.get("move_to") or ""
    share_raw = raw.get("move_share", 0)
    share = 0.0 if share_raw in (None, "") else _number(share_raw, "The share that moves")
    if not move_to:
        if share:
            raise ValueError("Choose the channel that share moves to, or set it to 0.")
        return {"channel": channel, "start": start.isoformat(), "end": end.isoformat(), "change": change, "move_to": "", "move_share": 0.0}
    _channel(move_to, "The channel it moves to")
    if move_to == channel:
        raise ValueError("It cannot move to the channel it leaves.")
    if change >= 0:
        raise ValueError("Only a reduction can move to another channel: type a negative change, or choose Nowhere.")
    if not 0 < share <= 100:
        raise ValueError("The share that moves is more than 0 and at most 100 percent.")
    return {"channel": channel, "start": start.isoformat(), "end": end.isoformat(), "change": change, "move_to": move_to, "move_share": share}


# --- the effect on days ----------------------------------------------------------------------------------------------------------

def day_factors(events: Iterable[Dict[str, Any]], ai_rows: Iterable[Dict[str, Any]], channel: str, days: Sequence[date]) -> List[float]:
    """For each day, what every event and AI period on ``channel`` multiplies the day's contacts by (1.0 when none touches it)."""
    events, ai_rows = list(events), list(ai_rows)
    out: List[float] = []
    for day in days:
        factor = 1.0
        for e in events:
            if channel not in e["channels"]:
                continue
            start, end = _on(e["start"]), _on(e["end"])
            if start <= day <= end:
                factor *= 1.0 + e["change"] / 100.0
            elif e["after_days"] and end < day <= end + timedelta(days=e["after_days"]):
                factor *= 1.0 + e["after_change"] / 100.0
        for r in ai_rows:
            if r["channel"] == channel and _on(r["start"]) <= day <= _on(r["end"]):
                factor *= 1.0 + r["change"] / 100.0
        out.append(factor)
    return out


def ai_moves(ai_rows: Iterable[Dict[str, Any]], channel: str, days: Sequence[date], before_ai: Sequence[float]) -> Dict[str, List[float]]:
    """The contacts that leave ``channel`` for another one because of AI, by destination and day. ``before_ai`` is each day's contacts on ``channel`` before
    AI took any away; the share that moves is the share of what AI removed that day."""
    if len(before_ai) != len(days):
        raise ValueError("One figure for each day.")
    out: Dict[str, List[float]] = {}
    for r in ai_rows:
        if r["channel"] != channel or not r["move_to"]:
            continue
        start, end = _on(r["start"]), _on(r["end"])
        row = [before_ai[i] * (-r["change"]) * r["move_share"] / 10000.0 if start <= day <= end else 0.0 for i, day in enumerate(days)]
        if any(row):
            acc = out.setdefault(r["move_to"], [0.0] * len(days))
            out[r["move_to"]] = [a + b for a, b in zip(acc, row)]
    return out


# --- growth and last year --------------------------------------------------------------------------------------------------------

def clean_growth(yoy: Any, method: Any) -> Dict[str, Any]:
    if method not in METHODS:
        raise ValueError("Choose the measured trend or the year-over-year rate.")
    if not isinstance(yoy, dict):
        raise ValueError("The year-over-year rates are a set of fields.")
    out: Dict[str, float] = {}
    for ch, value in yoy.items():
        _channel(ch, "A channel")
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        rate = _number(value, f"The {ch} year-over-year rate")
        if not YOY_LOW <= rate <= YOY_HIGH:
            raise ValueError(f"The {ch} year-over-year rate is from {YOY_LOW:.0f} to {YOY_HIGH:.0f} percent.")
        out[ch] = rate
    return {"yoy": {ch: out[ch] for ch in CHANNELS if ch in out}, "method": method}


def weekly_factor(yoy: float, weeks: float) -> float:
    """What a year-over-year rate multiplies a week's contacts by over ``weeks`` weeks (a year is 52): the rate compounds, so half a year is its square root."""
    base = 1.0 + yoy / 100.0
    if base <= 0:
        raise ValueError("A rate of -100 percent or less is not a rate.")
    return base ** (weeks / 52.0)


def growth_level(points: Sequence[Tuple[int, float]], yoy: float) -> float:
    """The weekly contacts expected in the forecast week at ``yoy`` percent a year. ``points`` are (weeks from the forecast week, a negative number, total).
    Every past week is brought forward to the forecast week; the middle of those is the level, so one odd week cannot move it."""
    if not points:
        raise ValueError("There is no history to bring forward.")
    return float(statistics.median(total * weekly_factor(yoy, -offset) for offset, total in points))


def last_year_total(total: Any, yoy: Optional[float]) -> int:
    """Last year's total for the week, grown by the year-over-year rate when there is one."""
    value = _number(total, "Last year's total")
    if value < 0:
        raise ValueError("Last year's total cannot be negative.")
    return int(round(value * (1.0 + (yoy or 0.0) / 100.0)))


# --- the document: what is stored for one site key ----------------------------------------------------------------------------------

def _empty() -> Dict[str, Any]:
    return {"events": [], "ai": [], "growth": {"yoy": {}, "method": "measured"}, "skip_weeks": [], "last_year": {}, "seq": 0}


def _whole_total(value: Any, what: str) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{what} is a whole number.")
    text = str(value).strip().replace(",", "").replace(" ", "")
    if not text.isdecimal() or int(text) > MAX_TOTAL:           # not isdigit: "²" is a digit that int() cannot read
        raise ValueError(f"{what} is a whole number from 0 to {MAX_TOTAL:,}.")
    return int(text)


def _weeks(values: Any, strict: bool) -> List[str]:
    if not isinstance(values, (list, tuple)):
        if strict:
            raise ValueError("Weeks are a list of dates.")
        return []
    out = set()
    for v in values:
        try:
            out.add(_date(v, "A week").isoformat())
        except ValueError:
            if strict:
                raise
    if len(out) > MAX_SKIPPED:
        raise ValueError(f"At most {MAX_SKIPPED} weeks can be left out.")
    return sorted(out)


def _last_year(raw: Any, strict: bool) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    if not isinstance(raw, dict):
        return out
    for week, values in raw.items():
        try:
            key = _date(week, "A week").isoformat()
        except ValueError:
            if strict:
                raise
            continue
        if not isinstance(values, dict):
            if strict:
                raise ValueError("Last year's totals are a set of fields.")
            continue
        row: Dict[str, int] = {}
        for ch, v in values.items():
            if ch not in CHANNELS:
                if strict:
                    raise ValueError(f"A channel is one of {', '.join(CHANNELS)}.")
                continue
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            row[ch] = _whole_total(v, f"Last year's {ch} total")
        if row:
            out[key] = {ch: row[ch] for ch in CHANNELS if ch in row}
    return out


def _id(raw: Any, used: set, seq: int) -> Tuple[str, int]:
    text = raw if isinstance(raw, str) else ""
    if text.isdigit() and len(text) <= 9 and text not in used:
        return text, max(seq, int(text))
    seq += 1
    while str(seq) in used:
        seq += 1
    return str(seq), seq


def clean_document(raw: Any) -> Dict[str, Any]:
    """The one gate a stored document passes: only the known parts are kept; a damaged event or AI period is an error (nothing is quietly dropped);
    unknown keys, and weeks or channels that are not part of the document, are left out."""
    doc = _empty()
    if not isinstance(raw, dict):
        return doc
    seq_raw = raw.get("seq")
    seq = seq_raw if isinstance(seq_raw, int) and not isinstance(seq_raw, bool) and 0 <= seq_raw < 10 ** 9 else 0
    used: set = set()
    for key, cleaner in (("events", clean_event), ("ai", clean_ai)):
        rows = raw.get(key) or []
        if not isinstance(rows, (list, tuple)):
            raise ValueError("The list of events and AI periods is a list.")
        if len(rows) > MAX_ROWS:
            raise ValueError(f"At most {MAX_ROWS} rows in a list.")
        for row in rows:
            cleaned = cleaner(row)
            ident, seq = _id(row.get("id"), used, seq)
            used.add(ident)
            doc[key].append({"id": ident, **cleaned})
    g = raw.get("growth")
    doc["growth"] = clean_growth(g.get("yoy") or {}, g.get("method") or "measured") if isinstance(g, dict) else doc["growth"]
    doc["skip_weeks"] = _weeks(raw.get("skip_weeks"), strict=False)
    doc["last_year"] = _last_year(raw.get("last_year"), strict=False)
    doc["seq"] = seq
    return doc


def add_row(doc: Dict[str, Any], key: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """A new document with the event or AI period added (checked here again); the document given is not changed."""
    if key not in LISTS:
        raise ValueError("Events and AI periods are the two lists.")
    out = copy.deepcopy(clean_document(doc))
    cleaned = (clean_event if key == "events" else clean_ai)(row)
    if len(out[key]) >= MAX_ROWS:
        raise ValueError(f"There are already {MAX_ROWS}; remove one first.")
    if key == "ai":
        start, end = _on(cleaned["start"]), _on(cleaned["end"])
        for other in out["ai"]:
            if other["channel"] == cleaned["channel"] and _on(other["start"]) <= end and start <= _on(other["end"]):
                raise ValueError(f"That overlaps the {other['channel']} period {other['start']} to {other['end']}: start the next period the day after that one ends.")
    out["seq"] += 1
    out[key].append({"id": str(out["seq"]), **cleaned})
    return out


def remove_row(doc: Dict[str, Any], key: str, ident: str) -> Dict[str, Any]:
    if key not in LISTS:
        raise ValueError("Events and AI periods are the two lists.")
    out = copy.deepcopy(clean_document(doc))
    out[key] = [r for r in out[key] if r["id"] != ident]
    return out


def with_growth(doc: Dict[str, Any], yoy: Any, method: Any) -> Dict[str, Any]:
    out = copy.deepcopy(clean_document(doc))
    out["growth"] = clean_growth(yoy, method)
    return out


def with_last_year(doc: Dict[str, Any], week: Any, values: Any) -> Dict[str, Any]:
    """Last year's totals for the week starting ``week`` (a blank figure clears that channel; all blank clears the week)."""
    out = copy.deepcopy(clean_document(doc))
    key = _date(week, "The week").isoformat()
    row = _last_year({key: values}, strict=True).get(key)
    if row:
        out["last_year"][key] = row
    else:
        out["last_year"].pop(key, None)
    return out


def with_skip_weeks(doc: Dict[str, Any], weeks: Any) -> Dict[str, Any]:
    out = copy.deepcopy(clean_document(doc))
    out["skip_weeks"] = _weeks(weeks, strict=True)
    return out


# --- a week, one driver at a time ----------------------------------------------------------------------------------------------------

def waterfall(base: int, shares: Sequence[float], days: Sequence[date], channel: str, events: Sequence[Dict[str, Any]],
              ai_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The week's contacts after each driver in turn: events first, then AI periods, each in the order stored. ``shares`` is each day's share of the week
    (adds to 1 over the open days). A step is the total after that driver less the total before it, both whole numbers, so ``base`` plus the steps is the
    total exactly. Drivers that touch no day of this week on this channel are not steps. Returns the steps, the combined factor of each day, and the total."""
    if len(shares) != len(days):
        raise ValueError("One share for each day.")
    factors = [1.0] * len(days)
    steps: List[Dict[str, Any]] = []
    before = int(base)
    for kind, rows in (("event", events), ("ai", ai_rows)):
        for row in rows:
            one = day_factors([row] if kind == "event" else [], [row] if kind == "ai" else [], channel, days)
            hit = [i for i, f in enumerate(one) if f != 1.0]
            if not hit:
                continue
            factors = [a * b for a, b in zip(factors, one)]
            total = int(round(base * sum(s * f for s, f in zip(shares, factors))))
            steps.append({"kind": kind, "id": row.get("id"), "name": row["name"] if kind == "event" else f"AI on {channel}", "change": row["change"],
                          "after_days": row.get("after_days", 0), "after_change": row.get("after_change", 0.0),
                          "days": hit, "delta": total - before, "total": total})
            before = total
    return {"steps": steps, "factors": factors, "total": before}
