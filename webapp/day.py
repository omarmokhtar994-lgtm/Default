# © 2026 Omar Mokhtar. All rights reserved.
"""The day: the schedule in use plus attendance and actual breaks, interval by interval.

Demand, language setup, shifts and planned breaks come from the version's own
workbook; everything else is what people recorded for the day. The input's
shrinkage is not used: it stands for absences, breaks and aux, which the day
counts as they happen (owner, 2026-10-08). Counted per 5 minutes: a person is
on the floor when on shift, present, not on a break and not in aux. Two
measures: "Interval compliance" counts a billable aux (say, billable coaching)
as on the floor; "Service level" takes everyone in aux off the floor. Per
interval (the workbook's own length):

  needed       = ceil(required)
  on the floor = the average of the interval's 5-minute counts
  plus/minus   = (on the floor - required) x interval hours

The previous day's overnight shifts (and their breaks) count in the early hours.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import load_workbook

from .versions import DAYS, shift_span

STEP = 5  # minutes: breaks move in 5-minute steps (owner, 2026-10-08)
PRESENT = "Present"
STATUSES = ["Present", "Unplanned leave", "Late", "Sick", "Left early", "Training", "Coaching", "Meeting",
            "System issue"]
ABSENT = {"Unplanned leave", "Sick"}  # the whole shift
LATE_EARLY = {"Late", "Left early"}
AUX = {"Training", "Coaching", "Meeting", "System issue"}  # billable or not, chosen when it is recorded
TIMED = LATE_EARLY | AUX  # may carry a from/to time
MEASURES = {"interval": "Interval compliance", "sl": "Service level"}
KEEP = 8  # workbooks kept read
_CACHE: Dict[Tuple[str, float], Dict[str, Any]] = {}


class BreakRefused(ValueError):
    """A break the day cannot take (outside the shift, on another break, not a 5-minute step)."""


def _norm(v: Any) -> str:
    return " ".join(str(v or "").split()).casefold()


def _minute(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    if hasattr(v, "hour"):
        return v.hour * 60 + v.minute
    m = re.search(r"(\d{1,2}):(\d{2})", str(v))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _instruction(wb, names) -> Any:
    ws = next((wb[n] for n in wb.sheetnames if _norm(n) == "instructions"), None)
    for row in (ws.iter_rows(values_only=True) if ws is not None else []):
        cells = list(row)
        for i, v in enumerate(cells):
            if _norm(v) in names:
                return next((x for x in cells[i + 1:] if x not in (None, "")), None)
    return None


def _grid(wb, name: str) -> Dict[int, Dict[int, float]]:
    """{day index: {minute: value}} from a demand or shrinkage tab."""
    ws = next((wb[n] for n in wb.sheetnames if _norm(n) == _norm(name)), None)
    out: Dict[int, Dict[int, float]] = {d: {} for d in range(7)}
    if ws is None:
        return out
    header = next(r for r in range(1, 10) if _norm(ws.cell(r, 1).value) == "interval")
    cols = {DAYS.index(str(ws.cell(header, c).value).strip()): c for c in range(2, ws.max_column + 1)
            if str(ws.cell(header, c).value or "").strip() in DAYS}
    for r in range(header + 1, ws.max_row + 1):
        t = _minute(ws.cell(r, 1).value)
        if t is None:
            continue
        for d, c in cols.items():
            try:
                out[d][t] = float(ws.cell(r, c).value or 0)
            except (TypeError, ValueError):
                out[d][t] = 0.0
    return out


def _languages(wb) -> List[Dict[str, Any]]:
    ws = next((wb[n] for n in wb.sheetnames if _norm(n) in ("language setup", "skill setup", "skills setup")), None)
    if ws is None:
        return []
    header = next((r for r in range(1, 10) if _norm(ws.cell(r, 1).value) == "language"), None)
    if header is None:
        return []
    cols = {_norm(ws.cell(header, c).value): c for c in range(1, ws.max_column + 1) if ws.cell(header, c).value}
    get = lambda r, k: ws.cell(r, cols[k]).value if k in cols else None  # noqa: E731
    rows = []
    for r in range(header + 1, ws.max_row + 1):
        name = str(get(r, "language") or "").strip()
        if not name or _norm(get(r, "active?")) in ("no", "n", "false"):
            continue
        covers = {_norm(x) for x in str(get(r, "can cover languages") or "").split(",") if x.strip()} | {_norm(name)}
        days_text = _norm(get(r, "coverage days"))
        days = list(range(7)) if days_text in ("", "all") else [DAYS.index(d) for d in DAYS if _norm(d) in days_text]
        try:
            minimum = int(float(get(r, "minimum per interval") or 0))
        except (TypeError, ValueError):
            minimum = 0
        start, end = _minute(get(r, "coverage start")) or 0, _minute(get(r, "coverage end")) or 0
        rows.append({"name": name, "covers": covers, "start": start, "end": end, "minimum": minimum, "days": days})
    return rows


def read_inputs(path: Path) -> Dict[str, Any]:
    """Demand, interval and language setup of a version's workbook (cached per file)."""
    key = (str(path), Path(path).stat().st_mtime)
    if key in _CACHE:
        return _CACHE[key]
    wb = load_workbook(path, data_only=True)
    step = int(float(_instruction(wb, ("interval minutes",)) or 30))
    demand = _grid(wb, str(_instruction(wb, ("requirements source",)) or f"FT Wise {step} Min"))
    previous = []
    ws = next((wb[n] for n in wb.sheetnames if _norm(n) == "previous week scheduled"), None)
    if ws is not None:
        for row in ws.iter_rows(min_row=3, values_only=True):
            if len(row) > 3 and row[1] and shift_span(row[3]):
                previous.append({"name": str(row[1]).strip(), "language": str(row[2] or "").strip(), "shift": str(row[3])})
    found = {"interval": step if 1440 % step == 0 else 30, "required": demand,
             "languages": _languages(wb), "previous_saturday": previous}
    while len(_CACHE) >= KEEP:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = found
    return found


def planned(week: Dict[str, Any], d: int, name: str) -> List[Dict[str, Any]]:
    """A person's planned breaks on day ``d`` in time order: idx, kind, start (minutes from
    that day's midnight; after midnight reads +24h) and minutes."""
    span = next((shift_span(a["days"][d]) for a in week.get("associates", []) if a["name"] == name), None)
    if not span:
        return []
    found = []
    for b in week.get("breaks", []):
        m = _minute(b["start"])
        if b["associate"] == name and b["day"] == DAYS[d] and m is not None:
            found.append({"kind": b["kind"], "start": m + (1440 if m < span[0] else 0), "minutes": int(b["minutes"])})
    return [{"idx": i, **b} for i, b in enumerate(sorted(found, key=lambda b: b["start"]))]


def _segments(week: Dict[str, Any], inputs: Dict[str, Any], day: int) -> List[Dict[str, Any]]:
    """Shift pieces touching this day: the day's own shifts and the previous day's overnight ones."""
    out = []
    for offset, d in ((-1, day - 1), (0, day)):
        if d < 0:  # Sunday: last Saturday's overnight shifts, from the Previous week scheduled tab
            for p in inputs.get("previous_saturday", []):
                span = shift_span(p["shift"])
                if span and span[1] > 1440:
                    out.append({"name": p["name"], "slot": "", "language": p["language"], "offset": -1,
                                "label": p["shift"],
                                "start": span[0] - 1440, "end": span[1] - 1440, "planned": []})
            continue
        for a in week.get("associates", []):
            span = shift_span(a["days"][d])
            if not span:
                continue
            start, end = span[0] + 1440 * offset, span[1] + 1440 * offset
            if end <= 0 or start >= 1440:
                continue
            out.append({"name": a["name"], "slot": a.get("slot", ""), "language": a["language"], "offset": offset,
                        "label": a["days"][d],
                        "start": start, "end": end,
                        "planned": [{**b, "start": b["start"] + 1440 * offset} for b in planned(week, d, a["name"])]})
    return out


def _away(seg: Dict[str, Any], mark: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    """The (from, to) minutes this person is off the floor in this segment; (0, 0) when present."""
    if not mark or mark.get("status", PRESENT) == PRESENT:
        return (0, 0)
    status = mark["status"]
    shift = 1440 * seg["offset"]
    lo = mark.get("from")
    hi = mark.get("to")
    lo = seg["start"] if lo is None else lo + shift
    hi = seg["end"] if hi is None else hi + shift
    if status == "Late":
        lo = seg["start"]
    if status == "Left early":
        hi = seg["end"]
    if status not in TIMED:
        lo, hi = seg["start"], seg["end"]
    return (max(lo, seg["start"]), min(hi, seg["end"]))


def check_break(week: Dict[str, Any], day: int, offset: int, name: str, idx: int, start: int,
                actual: Dict[Tuple[int, str, int], int], inputs: Optional[Dict[str, Any]] = None) -> None:
    """Refuse a break that leaves the shift, overlaps another break, or is not on a 5-minute step.
    ``start`` is minutes from the shift's own day's midnight."""
    if start % STEP:
        raise BreakRefused("Breaks move in 5-minute steps.")
    segs = [s for s in _segments(week, inputs or {"previous_saturday": []}, day + offset if offset == -1 else day)
            if s["name"] == name and s["offset"] == 0]
    if not segs:
        raise BreakRefused(f"{name} has no shift that day.")
    seg = segs[0]
    mine = {b["idx"]: b for b in seg["planned"]}
    if idx not in mine:
        raise BreakRefused("That break is not on the plan.")
    length = mine[idx]["minutes"]
    if start < seg["start"] or start + length > seg["end"]:
        raise BreakRefused(f"The break would fall outside {name}'s shift ({seg['label']}).")
    for other, b in mine.items():
        if other == idx:
            continue
        s = actual.get((offset, name, other), b["start"])
        if start < s + b["minutes"] and s < start + length:
            raise BreakRefused(f"The break would overlap {name}'s {b['kind']}.")


def day_view(week: Dict[str, Any], inputs: Dict[str, Any], day: int,
             attendance: Dict[Tuple[int, str], Dict[str, Any]],
             actual: Dict[Tuple[int, str, int], int], measure: str = "interval") -> Dict[str, Any]:
    """The day's lanes, interval cells, language rows and tiles. ``attendance`` and
    ``actual`` are keyed by (day offset, name[, break index]): 0 for this day's
    shifts, -1 for the previous day's; times are minutes from that shift's own
    midnight. ``measure`` is "interval" (billable aux stays on the floor) or "sl"."""
    if measure not in MEASURES:
        raise ValueError(f"unknown measure {measure!r}")
    step = inputs["interval"]
    slots = 1440 // STEP
    now = [[] for _ in range(slots)]
    plan = [[] for _ in range(slots)]
    lanes: Dict[str, Dict[str, Any]] = {}
    pieces = []
    for seg in _segments(week, inputs, day):
        mark = attendance.get((seg["offset"], seg["name"])) or {}
        status = mark.get("status", PRESENT)
        billable = status in AUX and bool(mark.get("billable"))
        away = _away(seg, mark)
        counts_away = not (billable and measure == "interval")
        breaks = []
        for b in seg["planned"]:
            moved = actual.get((seg["offset"], seg["name"], b["idx"]))
            start = b["start"] if moved is None else moved + 1440 * seg["offset"]
            breaks.append({**b, "planned_start": b["start"], "start": start, "moved": moved is not None})
        for i in range(slots):
            t = i * STEP
            if not seg["start"] <= t < seg["end"]:
                continue
            if not any(b["planned_start"] <= t < b["planned_start"] + b["minutes"] for b in breaks):
                plan[i].append(seg)
            if any(b["start"] <= t < b["start"] + b["minutes"] for b in breaks):
                continue
            if counts_away and away[0] <= t < away[1]:
                continue
            now[i].append(seg)
        pieces.append((seg, status, away, breaks))
        lane = lanes.setdefault(seg["name"], {"name": seg["name"], "slot": seg["slot"], "language": seg["language"],
                                              "segments": []})
        lane["segments"].append({"offset": seg["offset"], "label": seg["label"], "start": seg["start"],
                                 "end": seg["end"], "status": status, "billable": billable,
                                 "from": mark.get("from"), "to": mark.get("to"), "away": away, "breaks": breaks})

    def overlapping(lo: int, hi: int, t: int) -> bool:
        return lo < t + step and t < hi

    cells = []
    req = inputs["required"].get(day, {})
    for t in range(0, 1440, step):
        r = req.get(t, 0.0)
        idx = range(t // STEP, (t + step) // STEP)
        ticks = [len(now[i]) for i in idx]
        here = sum(ticks) / len(ticks)
        planned_here = sum(len(plan[i]) for i in idx) / len(idx)
        counts = {"absent": sum(1 for seg, st, away, br in pieces if st in ABSENT and overlapping(seg["start"], seg["end"], t)),
                  "aux": sum(1 for seg, st, away, br in pieces if st in AUX and away[0] < away[1]
                             and overlapping(away[0], away[1], t)),
                  "late_early": sum(1 for seg, st, away, br in pieces if st in LATE_EARLY and away[0] < away[1]
                                    and overlapping(away[0], away[1], t)),
                  "breaks": sum(1 for seg, st, away, br in pieces if st not in ABSENT
                                and any(overlapping(b["start"], b["start"] + b["minutes"], t) for b in br))}
        cell = {"t": t, "required": r, "plan": round(planned_here, 1), "now": round(here, 1), "slots": ticks,
                "low": min(ticks), **counts}
        if r <= 0:
            cells.append({**cell, "need": 0, "pm": None, "plan_pm": None, "cls": "none"})
            continue
        pm = (here - r) * step / 60
        cls = "ok" if pm >= -1e-9 else ("warn" if here > r - 1 else "bad")
        cells.append({**cell, "need": math.ceil(r - 1e-9), "pm": round(pm, 2),
                      "plan_pm": round((planned_here - r) * step / 60, 2), "cls": cls})
    languages = []
    for rule in inputs["languages"]:
        eligible = {_norm(r["name"]) for r in inputs["languages"] if _norm(rule["name"]) in r["covers"]}
        row = []
        for t in range(0, 1440, step):
            if rule["start"] == rule["end"]:
                inside = True
            elif rule["start"] < rule["end"]:
                inside = rule["start"] <= t < rule["end"]
            else:
                inside = t >= rule["start"] or t < rule["end"]
            if not inside or day not in rule["days"]:
                row.append({"t": t, "count": None, "cls": "none"})
                continue
            count = min(sum(1 for seg in now[i] if _norm(seg["language"]) in eligible)
                        for i in range(t // STEP, (t + step) // STEP))
            cls = "bad" if count < rule["minimum"] else ("warn" if count == 0 else "lok")
            row.append({"t": t, "count": count, "cls": cls})
        languages.append({"name": rule["name"], "start": rule["start"], "end": rule["end"], "minimum": rule["minimum"],
                          "cells": row, "gaps": sum(1 for c in row if c["cls"] in ("bad", "warn"))})
    mine = [(seg, st) for seg, st, away, br in pieces if seg["offset"] == 0]
    absent = sum(1 for seg, st in mine if st in ABSENT)
    short = sum(-c["pm"] for c in cells if c["pm"] is not None and c["pm"] < 0)
    plan_short = sum(-c["plan_pm"] for c in cells if c["plan_pm"] is not None and c["plan_pm"] < 0)
    over = sum(c["pm"] for c in cells if c["pm"] is not None and c["pm"] > 0)
    tiles = {"planned": len(mine), "present": len(mine) - absent, "absent": absent,
             "late_early": sum(1 for seg, st in mine if st in LATE_EARLY),
             "aux": sum(1 for seg, st in mine if st in AUX),
             "moved": sum(1 for seg, st, away, br in pieces for b in br if b["moved"]),
             "short_hours": round(short, 1), "plan_short_hours": round(plan_short, 1),
             "short_intervals": sum(1 for c in cells if c["pm"] is not None and c["pm"] < 0),
             "over_hours": round(over, 1), "language_gaps": sum(l["gaps"] for l in languages)}

    def first(lane):  # last night's people first, then by the day's start time
        own = [s["start"] for s in lane["segments"] if s["offset"] == 0]
        return (min(own) + 1440 if own else min(s["start"] for s in lane["segments"]), lane["name"])

    order = sorted(lanes.values(), key=first)
    return {"interval": step, "measure": measure, "lanes": order, "cells": cells, "languages": languages,
            "tiles": tiles}
