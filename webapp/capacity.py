# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BS (owner, 2026-11-18: "then add capacity plan"): the people a channel needs week by week against the people it will have, and the
hiring that closes the gap.

Needed: the agent hours the forecast puts on the floor in a week, over the productive hours of one person (hours a week times one minus the
channel's shrinkage). Available: the head count today, shrunk each week by the monthly attrition the planner types, plus each class from its start
(nothing while in training, part while nesting, whole after; a class shrinks by attrition too). The first week short gets a suggested class,
started early enough to be ready that week. Pure: dicts and numbers in, dicts out, no store. Entry is strict: a bad figure is refused in words."""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

WEEKS_A_MONTH = 4.345
MAX_CLASSES = 20
CLASS_LOOKBACK_WEEKS = 26
DEFAULTS = {"hours_per_week": 40.0, "attrition": 0.0, "training_weeks": 4, "nesting_weeks": 2, "nesting_output": 50.0}


def _number(raw: Any, default: Optional[float], low: float, high: float, message: str, whole: bool = False) -> float:
    text = "" if raw is None else str(raw).replace(",", "").rstrip("% ").strip()
    if text == "":
        if default is None:
            raise ValueError(message)
        return default
    try:
        value = float(text)
    except ValueError:
        raise ValueError(message) from None
    if not math.isfinite(value) or not low <= value <= high or (whole and value != int(value)):
        raise ValueError(message)
    return value


def check_inputs(raw: Dict[str, Any], first_week: date) -> Dict[str, Any]:
    """The planner's figures, checked; blanks take ``DEFAULTS`` except the head count, which is required."""
    out: Dict[str, Any] = {
        "head_count": _number(raw.get("head_count"), None, 0, 5000, "Type the people you have now (head count): a number from 0 to 5,000."),
        "hours_per_week": _number(raw.get("hours_per_week"), DEFAULTS["hours_per_week"], 10, 60, "Hours a week per person are 10 to 60."),
        "attrition": _number(raw.get("attrition"), DEFAULTS["attrition"], 0, 30, "Attrition is a percent a month from 0 to 30."),
        "training_weeks": int(_number(raw.get("training_weeks"), DEFAULTS["training_weeks"], 0, 26, "Training is whole weeks from 0 to 26.", True)),
        "nesting_weeks": int(_number(raw.get("nesting_weeks"), DEFAULTS["nesting_weeks"], 0, 12, "Nesting is whole weeks from 0 to 12.", True)),
        "nesting_output": _number(raw.get("nesting_output"), DEFAULTS["nesting_output"], 10, 100, "Nesting output is 10 to 100 percent of a trained person."),
    }
    classes = list(raw.get("classes") or [])
    if len(classes) > MAX_CLASSES:
        raise ValueError(f"Up to {MAX_CLASSES} classes can be planned.")
    earliest = first_week - timedelta(weeks=CLASS_LOOKBACK_WEEKS)
    kept: List[Dict[str, Any]] = []
    for row in classes:
        try:
            start = date.fromisoformat(str(row.get("week", "")).strip())
        except ValueError:
            raise ValueError("A class starts on a date, such as 2026-12-06.") from None
        if start.weekday() != 6:
            raise ValueError(f"A class starts on a week start (a Sunday); {start.isoformat()} is not one.")
        if start < earliest:
            raise ValueError(f"A class starts no more than {CLASS_LOOKBACK_WEEKS} weeks before the plan.")
        people = int(_number(row.get("people"), None, 1, 500, "A class is 1 to 500 people, a whole number.", True))
        kept.append({"week": start.isoformat(), "people": people})
    out["classes"] = sorted(kept, key=lambda c: c["week"])
    return out


def plan(weeks: Sequence[Dict[str, Any]], inputs: Dict[str, Any], shrinkage: float) -> Dict[str, Any]:
    """Each week of ``weeks`` ({"week", "hours", "low", "high"}: agent hours needed on the floor) with the people needed, available and the gap;
    the first short week and a suggested class for it. ``shrinkage`` is a share (0.3 for 30 percent)."""
    if not 0.0 <= shrinkage < 1.0:
        raise ValueError("Shrinkage is 0 to under 100 percent.")
    if not weeks:
        return {"weeks": [], "first_short": None, "suggestion": None}
    keep = (1.0 - inputs["attrition"] / 100.0) ** (1.0 / WEEKS_A_MONTH)
    per_person = inputs["hours_per_week"] * (1.0 - shrinkage)
    training, nesting = inputs["training_weeks"], inputs["nesting_weeks"]
    first = date.fromisoformat(weeks[0]["week"])
    rows: List[Dict[str, Any]] = []
    short: Optional[int] = None
    shortfall = 0.0
    for i, w in enumerate(weeks):
        live = 0.0
        for c in inputs["classes"]:
            k = (date.fromisoformat(w["week"]) - date.fromisoformat(c["week"])).days // 7
            if k < training:
                continue
            factor = inputs["nesting_output"] / 100.0 if k < training + nesting else 1.0
            live += c["people"] * keep ** k * factor
        available = inputs["head_count"] * keep ** i + live
        needed = w["hours"] / per_person
        if short is None and available < needed - 1e-9:
            short, shortfall = i, needed - available
        rows.append({"week": w["week"], "needed": round(needed, 1), "needed_low": round(w["low"] / per_person, 1),
                     "needed_high": round(w["high"] / per_person, 1), "available": round(available, 1), "gap": round(available - needed, 1),
                     "classes_live": round(live, 1)})
    suggestion = None
    if short is not None:
        lead = training + nesting
        people = math.ceil(shortfall / keep ** lead - 1e-9)
        wanted = first + timedelta(weeks=short - lead)
        start = max(first, wanted)
        suggestion = {"start": start.isoformat(), "people": people, "ready": (start + timedelta(weeks=lead)).isoformat(), "late": wanted < first}
    return {"weeks": rows, "first_short": rows[short]["week"] if short is not None else None, "suggestion": suggestion}
