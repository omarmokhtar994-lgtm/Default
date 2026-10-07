# © 2026 Omar Mokhtar. All rights reserved.
"""What the program page shows, built from a program's weeks (analytics.py).

Each chart comes with the rows of its table view, so every number drawn is
also readable as text. Weeks are labelled by the Sunday they start.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import charts
from .analytics import _date, insights, recurring, share, suggestions
from .results import DAYS

CAUSE_COLOURS = {"capacity": charts.BLUE, "breaks": charts.AQUA, "weekly_hours": charts.ORANGE,
                 "rules": charts.YELLOW}  # fixed per cause: a filter never repaints one


def _hours(value: Optional[float]) -> Optional[int]:
    return None if value is None else int(round(value))


def heat_grid(weeks: List[dict]) -> Dict[str, Any]:
    """Per day and hour, in how many of the recent weeks any half-hour of that
    hour was below 100% after breaks."""
    rec = recurring(weeks)
    per: Dict[tuple, int] = {}
    for cell, count in rec["counts"].items():
        day, _, clock = cell.partition(" ")
        if day in DAYS and clock[:2].isdigit():
            key = (day, int(clock[:2]))
            per[key] = max(per.get(key, 0), count)
    grid = [[per.get((day, hour), 0) for hour in range(24)] for day in DAYS]
    return {"weeks": rec["weeks"], "grid": grid, "top": rec["top"]}


def build(weeks: List[dict], all_weeks: List[dict]) -> Dict[str, Any]:
    """``weeks`` is the range on screen; ``all_weeks`` the program's whole
    history (insights compare with the week before, even off screen)."""
    labels = [_date(w["week"]) for w in weeks]
    f = [w["f"] for w in weeks]
    latest = weeks[-1]
    m = latest["m"]

    associates = [x["associates"] for x in f]
    chart_people = charts.columns(labels, associates, unit=" associates",
                                  deltas=[w["delta"]["associates"] for w in weeks],
                                  label="Associates scheduled per week")
    before, after = [x["before_pct"] for x in f], [x["after_pct"] for x in f]
    chart_cover = charts.lines(labels, [("Before breaks", charts.BLUE, before), ("After breaks", charts.AQUA, after)],
                               label="Share of half-hours fully covered, before and after breaks")
    have, need = [_hours(x["productive_hours"]) for x in f], [_hours(x["target_hours"]) for x in f]
    top = max([v for v in have + need if v is not None] or [1])
    chart_hours = charts.lines(labels, [("Hours available", charts.BLUE, have),
                                        ("Hours needed, at least", charts.ORANGE, need)],
                               y_max=charts.nice(top * 1.1), y_min=0, unit=" h",
                               label="Productive hours available and the least the target needs")

    restr = m.get("restrictions") or {}
    causes = sorted(restr.get("causes") or [], key=lambda c: -c["count"])
    chart_causes = charts.hbars([(c["label"], c["count"], CAUSE_COLOURS.get(c["key"], charts.BLUE)) for c in causes],
                                unit=" half-hours", label="Half-hours below 100% by reason") if restr.get("total") else charts.EMPTY

    active = m.get("active") or 0
    targets = m.get("targets") or []
    met = [share(t["after"], active) for t in targets]
    chart_targets = charts.columns([f"{t['pct']}%" for t in targets], met, unit="% of half-hours", y_max=100,
                                   colour=charts.AQUA, label="Share of half-hours meeting each interval target")

    heat = heat_grid(weeks)
    chart_heat = charts.heat(DAYS, [f"{h:02d}" for h in range(24)], heat["grid"],
                             tip_unit=f" of {heat['weeks']} weeks short",
                             label="Hours below 100% after breaks, counted across weeks")

    def tile(key: str, unit: str = "", good: Optional[str] = None) -> Dict[str, Any]:
        return {"value": latest["f"][key], "unit": unit, "delta": latest["delta"][key], "good": good}

    return {
        "latest": latest, "labels": labels,
        "insights": insights(all_weeks[: all_weeks.index(latest) + 1]),
        "suggestions": suggestions(m),
        "tiles": [("Associates", tile("associates")), ("Fully covered after breaks", tile("after_pct", "%", "up")),
                  ("Fully covered before breaks", tile("before_pct", "%", "up")),
                  ("Schedule efficiency", tile("efficiency", "%", "up"))],
        "charts": [
            {"id": "people", "title": "Associates per week",
             "note": "People on the schedule each week, with the change from the week before.",
             "svg": chart_people, "head": ["Week", "Associates", "Change"],
             "rows": [[w["week"], x, w["delta"]["associates"]] for w, x in zip(weeks, associates)]},
            {"id": "cover", "title": "Coverage before and after breaks",
             "note": "Share of half-hours with everyone needed on shift. The space between the lines is what breaks cost.",
             "svg": chart_cover, "head": ["Week", "Before breaks", "After breaks"],
             "rows": [[w["week"], b, a] for w, b, a in zip(weeks, before, after)]},
            {"id": "hours", "title": "Hours available and needed",
             "note": "Productive hours the roster can give against the least the coverage target needs.",
             "svg": chart_hours, "head": ["Week", "Hours available", "Hours needed, at least"],
             "rows": [[w["week"], h, n] for w, h, n in zip(weeks, have, need)]},
            {"id": "causes", "title": "What stops 100%",
             "note": f"The {restr.get('total') or 0} half-hours below 100% after breaks in the week of "
                     f"{_date(latest['week'])}, by reason.",
             "svg": chart_causes, "head": ["Reason", "Half-hours", "For example"],
             "rows": [[c["label"], c["count"], ", ".join(c["examples"][:3])] for c in causes]},
            {"id": "targets", "title": "If the interval target were lower",
             "note": f"Share of half-hours that meet each target in the week of {_date(latest['week'])}: "
                     "how far the schedule is from 100%, 95% or 90% per half-hour.",
             "svg": chart_targets, "head": ["Target per half-hour", "Half-hours meeting it", "Share"],
             "rows": [[f"{t['pct']}%", f"{t['after']} of {active}", f"{s}%"] for t, s in zip(targets, met)]},
            {"id": "heat", "title": "Hours that keep coming up short",
             "note": f"In how many of the last {heat['weeks']} weeks each hour had a half-hour below 100% after breaks.",
             "svg": chart_heat, "head": ["Day and time", "Weeks short"],
             "rows": [[cell, f"{count} of {heat['weeks']}"] for cell, count in heat["top"]]},
        ],
        "table": [{"week": w["week"], "run_id": w["run_id"], "workbook": w["workbook"], "by": w["by_name"],
                   "runs": w["runs_that_week"], "basis": w["week_basis"], "f": w["f"], "d": w["delta"]}
                  for w in reversed(weeks)],
    }


def weeks_to_show(text: str, default: int = 12) -> Optional[int]:
    """The range filter: a number of weeks, or None for all of them."""
    if text == "all":
        return None
    try:
        n = int(text)
    except (TypeError, ValueError):
        return default
    return n if 0 < n <= 520 else default


def overview(programs: Dict[str, List[dict]]) -> List[Dict[str, Any]]:
    rows = []
    for name, weeks in programs.items():
        last = weeks[-1]
        recent = weeks[-12:]
        rows.append({"name": name, "weeks": len(weeks), "first": weeks[0]["week"], "latest": last,
                     "spark_after": charts.spark([w["f"]["after_pct"] for w in recent],
                                                 label=f"After breaks, last {len(recent)} weeks"),
                     "spark_people": charts.spark([w["f"]["associates"] for w in recent], colour=charts.BLUE,
                                                  label=f"Associates, last {len(recent)} weeks")})
    return sorted(rows, key=lambda r: (r["name"] == "Untagged", r["name"].lower()))
