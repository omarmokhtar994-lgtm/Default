# © 2026 Omar Mokhtar. All rights reserved.
"""The week view: what one run achieved in every interval of the week, where
overtime is needed and where extra hours are available.

Counted in whole associates, from the independent validator's interval rows:
needed for 100% = ceil(required / one person's productive share), the share
being that interval's effective staffing / people on the floor (with nobody on
the floor, the week's median share). Overtime = needed - on the floor; extra =
on the floor - needed; hours = associates x the interval length.
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional

DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
# compact row: [day_index, "HH:MM", required, after_eff, after_raw, before_eff, before_raw, severe_overage]
SIDES = {"after": (3, 4), "before": (5, 6)}


def compact(rows: List[dict]) -> List[list]:
    """The validator's interval rows, kept with the run's figures (counts and times only)."""
    out = []
    for r in rows:
        out.append([int(r.get("day_index", 0)), str(r.get("interval", "00:00")), round(float(r.get("required") or 0), 3),
                    round(float(r.get("after_effective") or 0), 3), int(r.get("after_raw_min") or 0),
                    round(float(r.get("before_effective") or 0), 3), int(r.get("before_raw_min") or 0),
                    1 if r.get("severe_overage") else 0])
    return out


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _step(rows: List[list]) -> int:
    starts = sorted({_minutes(r[1]) for r in rows})
    gaps = [b - a for a, b in zip(starts, starts[1:]) if b > a]
    step = min(gaps) if gaps else 30
    return step if 1440 % step == 0 else 30


def view(intervals: List[list], side: str = "after") -> Optional[Dict[str, Any]]:
    if not intervals:
        return None
    eff_i, raw_i = SIDES[side]
    shares = [r[eff_i] / r[raw_i] for r in intervals if r[raw_i] > 0 and r[eff_i] > 0]
    median = statistics.median(shares) if shares else 1.0
    step = _step(intervals)
    cells: Dict[tuple, dict] = {}
    short, extra = [], []
    for r in sorted(intervals, key=lambda r: (r[0], _minutes(r[1]))):
        day, time, req, eff, have = DAYS[r[0] % 7], r[1], r[2], r[eff_i], r[raw_i]
        if req <= 0:
            cells[(r[0], time)] = {"day": day, "time": time, "cls": "none"}
            continue
        share = eff / have if have > 0 and eff > 0 else median
        need = math.ceil(req / share - 1e-9)
        ratio = eff / req
        cls = ("over" if side == "after" and r[7] else "covered" if ratio + 1e-9 >= 1
               else "short" if ratio + 1e-9 >= 0.9 else "gap")
        cell = {"day": day, "time": time, "cls": cls, "pct": int(round(100 * ratio)), "need": need, "have": have,
                "full": ratio + 1e-9 >= 1}
        cells[(r[0], time)] = cell
        if have != need:
            people = abs(need - have)
            entry = dict(day=day, time=time, need=need, have=have, pct=cell["pct"], people=people,
                         hours=people * step / 60)
            (short if have < need else extra).append(entry)
    grid: List[dict] = []
    folded: List[int] = []

    def close_fold(end: int) -> None:
        if len(folded) > 1:
            grid.append({"fold": f"{_hhmm(folded[0])} to {_hhmm(end)}"})
        else:
            for m in folded:
                grid.append({"time": _hhmm(m), "cells": [cells.get((d, _hhmm(m)), {"cls": "none"}) for d in range(7)]})
        folded.clear()

    for m in range(0, 1440, step):
        row = [cells.get((d, _hhmm(m)), {"cls": "none"}) for d in range(7)]
        if all(c["cls"] == "none" for c in row):
            folded.append(m)
            continue
        close_fold(m)
        grid.append({"time": _hhmm(m), "cells": row})
    close_fold(1440)
    active = [c for c in cells.values() if c["cls"] != "none"]
    days_at_full = []
    for d in DAYS:
        mine = [c for c in active if c["day"] == d]
        days_at_full.append(int(round(100 * sum(c["full"] for c in mine) / len(mine))) if mine else None)
    totals = {"active": len(active), "full": sum(c["full"] for c in active),
              "overtime_people": sum(r["people"] for r in short), "overtime_hours": sum(r["hours"] for r in short),
              "extra_people": sum(r["people"] for r in extra), "extra_hours": sum(r["hours"] for r in extra)}
    return {"step": step, "side": side, "grid": grid, "days": DAYS, "days_at_full": days_at_full,
            "short": short, "extra": extra, "totals": totals}
