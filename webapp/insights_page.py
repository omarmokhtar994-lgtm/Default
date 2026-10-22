# © 2026 Omar Mokhtar. All rights reserved.
"""What the Incidents page shows (Phase AV): the figures of ``insights`` laid out as tiles, charts and tables.
Seniors open on the overview (programs and LOBs side by side); team managers open on their associates."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from . import charts
from .insights import BEHAVIOUR, KINDS, LABEL, figures, grouped, person, trend

LEVELS = (("overview", "Overview"), ("lobs", "LOBs"), ("associates", "Associates"))
SHORT = {"missed_break": "Missed", "unplanned": "Unplanned", "sick": "Sick", "planned": "Planned", "late": "Late",
         "early": "Early", "coaching": "Coaching", "training": "Training", "meeting": "Meetings",
         "system_issue": "System", "task": "Tasks", "non_adherence": "Adherence"}
TILES = (("absenteeism", "Absenteeism", "unplanned leave and sick, of shifts scheduled", True),
         ("shrink_out", "Shrinkage, out of office", "unplanned, planned and sick, of shifts scheduled", True),
         ("shrink_client", "Shrinkage, the client's", "adds public holiday and exam leave", True),
         ("shrink_in", "Shrinkage, in office", "time off the floor, of minutes scheduled", True),
         ("adherence", "Adherence", "scheduled time spent as scheduled", False))


def dur(minutes: Any) -> str:
    """90 as "1 h 30 min", 45 as "45 min", 0 as "-"."""
    minutes = int(minutes or 0)
    if minutes <= 0:
        return "-"
    h, m = divmod(minutes, 60)
    return f"{h} h {m:02d} min" if h and m else (f"{h} h" if h else f"{m} min")


def _short(day: str) -> str:
    return date.fromisoformat(day).strftime("%d %b").lstrip("0")


def _tiles(total: Dict[str, Any], days: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for key, label, note, lower_is_better in TILES:
        values = [d[key] for d in days]
        out.append({"label": label, "note": note, "value": total[key], "unit": "%", "lower_is_better": lower_is_better,
                    "spark": charts.spark(values, charts.AQUA, f"{label} by day")})
    out.append({"label": "Incidents", "note": "missed breaks, unplanned leave, late, early and out of adherence",
                "value": total["total"], "unit": "", "lower_is_better": True,
                "spark": charts.spark([d["total"] for d in days], charts.ORANGE, "Incidents by day")})
    return out


def _mix(total: Dict[str, Any]) -> Dict[str, Any]:
    kinds = [(LABEL[k], total["incidents"][k]) for k, _ in KINDS if total["incidents"][k]["n"]]
    return {"count": charts.hbars([(name, v["n"], charts.BLUE) for name, v in kinds], "", "Incidents by type"),
            "time": charts.hbars([(name, round(v["min"] / 60, 1), charts.AQUA) for name, v in kinds if v["min"]],
                                 " h", "Time by type, in hours")}


def _heat(rows: List[Dict[str, Any]], limit: int = 14) -> List[Dict[str, Any]]:
    """A table of counts, a row per group and a column per incident type, each cell level 0 (none) to 4 (the most)."""
    shown = rows[:limit]
    top = max([r["incidents"][k]["n"] for r in shown for k, _ in KINDS] + [1])
    return [{"name": r["name"], "cells": [(r["incidents"][k]["n"], 0 if not r["incidents"][k]["n"] else
                                           min(4, 1 + int(3 * (r["incidents"][k]["n"] - 1) / max(1, top - 1) + 0.5)))
                                          for k, _ in KINDS]} for r in shown]


def _trend_chart(days: List[Dict[str, Any]]) -> Any:
    labels = [_short(d["date"]) for d in days]
    top = max([d[k] or 0 for d in days for k in ("absenteeism", "shrink_out", "shrink_in")] + [1])
    return charts.lines(labels, [("Absenteeism", charts.BLUE, [d["absenteeism"] for d in days]),
                                 ("Out of office", charts.ORANGE, [d["shrink_out"] for d in days]),
                                 ("In office", charts.AQUA, [d["shrink_in"] for d in days])],
                        y_max=charts.nice(top * 1.15), y_min=0, label="Absenteeism and shrinkage by day")


def build(facts: List[Dict[str, Any]], level: str, who: str, start: date, end: date) -> Dict[str, Any]:
    """Everything the page draws for ``level`` (overview, lobs or associates), and ``who`` when one associate is open."""
    total, days = figures(facts), trend(facts)
    found: Dict[str, Any] = {"level": level, "total": total, "empty": not facts, "tiles": _tiles(total, days),
                             "trend": _trend_chart(days), "mix": _mix(total), "kinds": KINDS, "short": SHORT,
                             "behaviour": BEHAVIOUR, "days": len(days)}
    found["programs"] = grouped(facts, "programs")
    found["lobs"] = grouped(facts, "lobs")
    found["associates"] = grouped(facts, "associates")
    rows = {"overview": found["lobs"], "lobs": found["lobs"], "associates": found["associates"]}[level]
    found["heat"] = _heat(rows)
    found["heat_title"] = {"overview": "LOBs", "lobs": "LOBs", "associates": "Associates with the most incidents"}[level]
    found["top"] = [r for r in found["associates"] if r["total"]][:5]
    found["top_chart"] = charts.hbars([(f"{r['name']} ({r['lob']})", r["total"], charts.ORANGE) for r in found["top"]], "",
                                      "Associates with the most incidents")
    found["day_columns"] = charts.columns([_short(d["date"]) for d in days], [d["total"] for d in days], "",
                                          None, charts.BLUE, "Incidents by day")
    found["person"] = None
    if who:
        found["person"] = person(facts, who)
        mine = [r for r in facts if r["name"] == who]
        mine_days = trend(mine)
        found["person_tiles"] = _tiles(found["person"], mine_days)
        found["person_trend"] = _trend_chart(mine_days)
    return found
