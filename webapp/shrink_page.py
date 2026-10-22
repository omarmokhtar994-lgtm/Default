# © 2026 Omar Mokhtar. All rights reserved.
"""What the Shrinkage page draws (Phase AV): tiles, a chart and a table for the view chosen."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from . import charts
from .shrink_view import interval_grid, interval_series, periods


def _day(key: str) -> str:
    return date.fromisoformat(key).strftime("%a %d %b").replace(" 0", " ")


def _hm(t: int) -> str:
    return f"{t // 60 % 24:02d}:{t % 60:02d}"


def _hours(minutes: float) -> str:
    return f"{minutes / 60:.1f} h"


def build(facts: List[Dict[str, Any]], per_day: Dict[str, Dict[int, List[float]]], show: str, by: str,
          out_ticks: Sequence[str], in_ticks: Sequence[str], step: int, first: int, last: int, focus: str) -> Dict[str, Any]:
    """The page's figures for ``show`` (both, out or in) laid out ``by`` day, week or interval."""
    both = periods(facts, "day")
    whole_shifts = sum(r["shifts"] for r in both)
    n_out, minutes, sched = sum(r["out_n"] for r in both), sum(r["in_min"] for r in both), sum(r["sched_min"] for r in both)
    found: Dict[str, Any] = {
        "empty": not facts, "days": len(both), "shifts": whole_shifts,
        "tiles": [("Out of office", round(100 * n_out / whole_shifts, 1) if whole_shifts else None,
                   f"{n_out} person-days out of {whole_shifts} shifts scheduled") if show != "in" else None,
                  ("In office", round(100 * minutes / sched, 1) if sched else None,
                   f"{_hours(minutes)} off the floor of {_hours(sched)} scheduled") if show != "out" else None]}
    found["tiles"] = [t for t in found["tiles"] if t]
    series = []
    if by in ("day", "week"):
        rows = periods(facts, by)
        labels = [_day(r["key"]) if by == "day" else "Week of " + _day(r["key"]) for r in rows]
        if show != "in":
            series.append(("Out of office", charts.ORANGE, [r["out"] for r in rows]))
        if show != "out":
            series.append(("In office", charts.AQUA, [r["inn"] for r in rows]))
        top = max([v for _, _, vals in series for v in vals if v is not None] + [1])
        found["chart"] = charts.lines(labels, series, y_max=charts.nice(top * 1.15), y_min=0,
                                      label=f"Shrinkage {('by day' if by == 'day' else 'by week')}") if rows else charts.EMPTY
        found["table"] = [{"label": l, "days": r["days"], "shifts": r["shifts"], "out": r["out"], "out_n": r["out_n"],
                           "inn": r["inn"], "in_h": _hours(r["in_min"])} for l, r in zip(labels, rows)]
    else:
        cells = interval_series(per_day, first, last)
        labels = [_hm(c["t"]) for c in cells]
        if show != "in":
            series.append(("Out of office", charts.ORANGE, [c["out"] for c in cells]))
        if show != "out":
            series.append(("In office", charts.AQUA, [c["inn"] for c in cells]))
        top = max([v for _, _, vals in series for v in vals if v is not None] + [1])
        found["chart"] = charts.lines(labels, series, y_max=charts.nice(top * 1.15), y_min=0,
                                      label="Shrinkage by interval, days added together") if cells else charts.EMPTY
        key = "out" if show == "out" else ("inn" if show == "in" else focus)
        cols, grid = interval_grid(per_day, key, first, last)
        top_cell = max([v for r in grid for v in r["cells"] if v is not None] + [0])
        found["heat_cols"] = [_hm(c) for c in cols]
        found["heat_title"] = "Out of office" if key == "out" else "In office"
        found["heat"] = [{"day": _day(r["day"]), "cells": [
            (v, 0 if v is None or not v else min(3, 1 + int(3 * v / top_cell)) if top_cell else 0) for v in r["cells"]]}
            for r in grid]
        found["table"] = [{"label": l, "out": c["out"], "inn": c["inn"]} for l, c in zip(labels, cells)]
    found["both_shown"] = show == "both"
    return found
