# © 2026 Omar Mokhtar. All rights reserved.
"""The Shrinkage page's figures (Phase AV; owner, 2026-10-22): out-of-office, in-office or both, day over day, week over
week and per interval, for any period, with what counts chosen on the page.

What counts is a set of ticks (``OUT_ITEMS`` and ``IN_ITEMS``) turned into the mapping ``shrinkage.day_shrinkage``
reads, so a figure here is the RTA's own figure for the same ticks. A day over day or week over week figure is a sum of
people-days (out of office) and minutes (in office), never an average of percentages."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .day import ABSENT, AUX, EXTRA_BREAKS
from .shrinkage import ITEMS, day_shrinkage, read_mapping

OUT_ITEMS = ("unplanned", "planned", "sick", "holiday", "exam")
IN_ITEMS = ("breaks", "aux", "aux_billable")
LABEL = {k: label for k, label, _ in ITEMS}
PRESETS = (("sutherland", "Sutherland", ("unplanned", "planned", "sick")),
           ("client", "The client's", ("unplanned", "planned", "sick", "holiday", "exam")))
SHOW = (("both", "Out and in office"), ("out", "Out of office"), ("in", "In office"))
BY = (("day", "Day over day"), ("week", "Week over week"), ("interval", "Per interval"))
STEPS = (15, 30, 60)
STATUS_KEY = {"Unplanned leave": "unplanned", "Sick": "sick", "Public holiday": "holiday", "Exam leave": "exam"}


def ticks_from(saved: Optional[Dict[str, Any]], out: Sequence[str], inn: Sequence[str]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """The ticked items (page choice), else the program's own mapping, else Sutherland's out and the default in office."""
    if out or inn:
        return (tuple(k for k in OUT_ITEMS if k in set(out)), tuple(k for k in IN_ITEMS if k in set(inn)))
    mapping = read_mapping(saved["mapping"] if saved else None)
    return (tuple(k for k in OUT_ITEMS if "sutherland" in mapping.get(k, ())),
            tuple(k for k in IN_ITEMS if "in" in mapping.get(k, ())))


def mapping_of(out: Iterable[str], inn: Iterable[str]) -> Dict[str, set]:
    """Ticks as the mapping ``day_shrinkage`` reads: the out-of-office figure under both its names, in office as ``in``."""
    found: Dict[str, set] = {k: set() for k in OUT_ITEMS + IN_ITEMS}
    for k in out:
        found[k] |= {"sutherland", "client"}
    for k in inn:
        found[k].add("in")
    return found


def _pct(n: float, d: float) -> Optional[float]:
    return round(100 * n / d, 1) if d else None


def week_begin(on: date, start_day: int = 0) -> date:
    """The first day of the week holding ``on``; ``start_day`` is the weekday the program's weeks begin on, Sunday 0."""
    return on - timedelta(days=((on.weekday() + 1) % 7 - start_day) % 7)


def periods(facts: List[Dict[str, Any]], by: str, start_days: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    """Out and in office per day, or per week (each LOB's weeks begin on its program's start day, from the LOBs and
    defaults settings; Sunday when not set), oldest first."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in facts:
        on = date.fromisoformat(r["date"])
        key = r["date"] if by == "day" else week_begin(on, (start_days or {}).get(r["unit"], 0)).isoformat()
        groups.setdefault(key, []).append(r)
    out = []
    for key, rows in sorted(groups.items()):
        shifts = sum(r["shifts"] for r in rows)
        out.append({"key": key, "days": len({r["date"] for r in rows}), "shifts": shifts,
                    "out": _pct(sum(r["out"] for r in rows), shifts),
                    "inn": _pct(sum(r["in_off"] for r in rows), sum(r["in_sched"] for r in rows)),
                    "out_n": sum(r["out"] for r in rows), "in_min": sum(r["in_off"] for r in rows),
                    "sched_min": sum(r["in_sched"] for r in rows)})
    return out


def _overlap(a: int, b: int, lo: int, hi: int) -> int:
    return max(0, min(b, hi) - max(a, lo))


def interval_rows(page: Dict[str, Any], out: Sequence[str], inn: Sequence[str], step: int) -> Dict[int, List[float]]:
    """For each interval start (minutes from the day's midnight) of the shifts that start on this day:
    ``[absent minutes counted, scheduled minutes, off-floor minutes counted, present minutes]``."""
    found: Dict[int, List[float]] = {}
    for lane in page["view"]["lanes"]:
        for seg in lane["segments"]:
            if seg["offset"] != 0:
                continue
            gone = seg["status"] in ABSENT
            counted_out = gone and STATUS_KEY.get(seg["status"]) in out
            off: List[Tuple[int, int]] = []
            if not gone:
                if "breaks" in inn:
                    off += [(b["start"], b["start"] + b["minutes"]) for b in seg["breaks"]]
                    off += [(a["start"], a["end"]) for a in seg["activities"] if a["kind"] in EXTRA_BREAKS]
                if seg["status"] in AUX and seg["away"][1] > seg["away"][0]:
                    if ("aux_billable" if seg["billable"] else "aux") in inn:
                        off.append(tuple(seg["away"]))
                for a in seg["activities"]:
                    if a["kind"] in AUX and ("aux_billable" if a.get("billable") else "aux") in inn:
                        off.append((a["start"], a["end"]))
            for t in range((seg["start"] // step) * step, seg["end"], step):
                sched = _overlap(seg["start"], seg["end"], t, t + step)
                if not sched:
                    continue
                row = found.setdefault(t, [0.0, 0.0, 0.0, 0.0])
                row[1] += sched
                if counted_out:
                    row[0] += sched
                if not gone:
                    row[3] += sched
                    row[2] += min(sched, sum(_overlap(a, b, max(t, seg["start"]), min(t + step, seg["end"])) for a, b in off))
    return found


def interval_series(per_day: Dict[str, Dict[int, List[float]]], first: int = 0, last: int = 1440) -> List[Dict[str, Any]]:
    """Time of day, the days added together: out and in office per interval start (shifts past midnight wrap round)."""
    total: Dict[int, List[float]] = {}
    for rows in per_day.values():
        for t, v in rows.items():
            slot = total.setdefault(t % 1440, [0.0, 0.0, 0.0, 0.0])
            for i in range(4):
                slot[i] += v[i]
    return [{"t": t, "out": _pct(v[0], v[1]), "inn": _pct(v[2], v[3]), "sched": v[1]}
            for t, v in sorted(total.items()) if first <= t < last]


def interval_grid(per_day: Dict[str, Dict[int, List[float]]], which: str, first: int = 0, last: int = 1440) -> Tuple[List[int], List[Dict[str, Any]]]:
    """A row per day and a column per interval (``which`` is ``out`` or ``inn``): the figure, None where nobody was scheduled."""
    cols = sorted({t % 1440 for rows in per_day.values() for t in rows if first <= t % 1440 < last})
    rows = []
    for day, found in sorted(per_day.items()):
        by_slot: Dict[int, List[float]] = {}
        for t, v in found.items():
            slot = by_slot.setdefault(t % 1440, [0.0, 0.0, 0.0, 0.0])
            for i in range(4):
                slot[i] += v[i]
        cells = []
        for t in cols:
            v = by_slot.get(t)
            cells.append(None if not v else (_pct(v[0], v[1]) if which == "out" else _pct(v[2], v[3])))
        rows.append({"day": day, "cells": cells})
    return cols, rows


def collect_intervals(days, units: Iterable[str], start: date, end: date, measure: str, out: Sequence[str],
                      inn: Sequence[str], step: int, check: Callable[[], None] = lambda: None) -> Dict[str, Dict[int, List[float]]]:
    """Per day, the interval rows of every unit added together."""
    per_day: Dict[str, Dict[int, List[float]]] = {}
    for unit in units:
        for i in range((end - start).days + 1):
            check()
            day = start + timedelta(days=i)
            try:
                page = days.page(unit, day, measure)
            except ValueError:
                continue
            if page is None:
                continue
            mine = per_day.setdefault(day.isoformat(), {})
            for t, v in interval_rows(page, out, inn, step).items():
                slot = mine.setdefault(t, [0.0, 0.0, 0.0, 0.0])
                for k in range(4):
                    slot[k] += v[k]
    return {d: rows for d, rows in per_day.items() if rows}
