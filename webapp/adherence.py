# © 2026 Omar Mokhtar. All rights reserved.
"""Adherence, conformance and actual shrinkage, from the day's records.

Per person and shift, minute by minute (5-minute steps): the schedule says
"work" or "break" (the planned breaks); what happened is "away" (unplanned
leave, sick, late, left early: no break taken while away), "break" (the break
as taken), "aux" (training, coaching, meeting, system issue) or "work".

  adherence   = minutes doing what the schedule says / the shift's minutes
  conformance = minutes worked / minutes scheduled to work (shift less planned breaks)

Under Interval compliance a billable aux counts as work (it stays billable);
under Service level it does not. An absence has no percentages and is left out
of the team's figures (it is shrinkage, shown as such).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .day import ABSENT, AUX, EXTRA_BREAKS, LATE_EARLY, STEP


def _pct(part: int, whole: int) -> Optional[int]:
    return round(100 * part / whole) if whole else None


def person_day(view: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Minutes and percentages for ``name``'s shift that starts this day."""
    seg = next(s for l in view["lanes"] if l["name"] == name for s in l["segments"] if s["offset"] == 0)
    planned = [(b["planned_start"], b["planned_start"] + b["minutes"]) for b in seg["breaks"]]
    taken = [(b["start"], b["start"] + b["minutes"]) for b in seg["breaks"]]
    taken += [(a["start"], a["end"]) for a in seg.get("activities", []) if a["kind"] in EXTRA_BREAKS]  # added on the day
    status, (lo, hi) = seg["status"], seg["away"]
    interval = view["measure"] == "interval"
    billable_counts = seg["billable"] and interval
    acts = seg.get("activities", [])
    vto = [(a["start"], a["end"]) for a in acts if a["kind"] == "VTO"]
    aux = [a for a in acts if a["kind"] in AUX]
    out = {"name": name, "shift": seg["label"], "status": status, "billable": seg["billable"], "scheduled": 0,
           "worked": 0, "late": 0, "early": 0, "absent": 0, "aux_billable": 0, "aux_unbillable": 0,
           "breaks_planned": 0, "breaks_taken": 0, "out_of_schedule": 0,
           "vto": 0, "overtime": 0}
    for t in range(seg["start"], seg["end"], STEP):
        if status not in ABSENT and any(a <= t < b for a, b in vto):
            out["vto"] += STEP  # agreed time off: out of the schedule, not against it
            continue
        out["scheduled"] += STEP
        booked = next((a for a in aux if a["start"] <= t < a["end"]), None)
        due = "break" if any(a <= t < b for a, b in planned) else "work"
        out["breaks_planned"] += STEP if due == "break" else 0
        if status in ABSENT:
            now = "away"
            out["absent"] += STEP
        elif status in LATE_EARLY and lo <= t < hi:
            now = "away"
            out["late" if status == "Late" else "early"] += STEP
        elif any(a <= t < b for a, b in taken):
            now = "break"
            out["breaks_taken"] += STEP
        elif status in AUX and lo <= t < hi:
            now = "work" if billable_counts else "aux"
            out["aux_billable" if seg["billable"] else "aux_unbillable"] += STEP
        elif booked is not None:
            now = "work" if booked.get("billable") and interval else "aux"
            out["aux_billable" if booked.get("billable") else "aux_unbillable"] += STEP
        else:
            now = "work"
        if now == "work":
            out["worked"] += STEP
        if now != due:
            out["out_of_schedule"] += STEP
    if status not in ABSENT:
        out["overtime"] = sum(max(0, min(a["end"], seg["start"]) - a["start"]) + max(0, a["end"] - max(a["start"], seg["end"]))
                              for a in acts if a["kind"] == "Overtime")
    out["scheduled_work"] = out["scheduled"] - out["breaks_planned"]
    gone = status in ABSENT
    out["adherence"] = None if gone else _pct(out["scheduled"] - out["out_of_schedule"], out["scheduled"])
    out["conformance"] = None if gone else _pct(out["worked"], out["scheduled_work"])
    return out


def team(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Time-weighted team figures over the shifts that were worked (absences left out)."""
    worked = [r for r in rows if r["adherence"] is not None]
    scheduled = sum(r["scheduled"] for r in worked)
    work = sum(r["scheduled_work"] for r in worked)
    return {"people": len(worked), "absent": len(rows) - len(worked),
            "adherence": _pct(sum(r["scheduled"] - r["out_of_schedule"] for r in worked), scheduled),
            "conformance": _pct(sum(r["worked"] for r in worked), work),
            "late": sum(r["late"] for r in rows), "early": sum(r["early"] for r in rows),
            "aux_billable": sum(r["aux_billable"] for r in rows), "aux_unbillable": sum(r["aux_unbillable"] for r in rows)}


def interval_shrinkage(view: Dict[str, Any], inputs: Dict[str, Any], day: int) -> List[Dict[str, Any]]:
    """Per interval: people paid on shift (5-minute average), on the floor, actual shrinkage
    (1 - on the floor / paid) and the input's planned shrinkage for that interval."""
    step = view["interval"]
    planned = inputs.get("planned_shrinkage", {}).get(day, {})
    rows = []
    for c in view["cells"]:
        t = c["t"]
        ticks = range(t, t + step, STEP)
        paid = sum(sum(1 for l in view["lanes"] for s in l["segments"] if s["start"] <= x < s["end"])
                   for x in ticks) / len(ticks)
        if not paid:
            continue
        rows.append({"t": t, "paid": round(paid, 1), "on_floor": c["now"], "actual": round(1 - c["now"] / paid, 3),
                     "input": planned.get(t, 0.0)})
    return rows
