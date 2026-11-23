# © 2026 Omar Mokhtar. All rights reserved.
"""Shrinkage in and out of office for one day on the RTA (Phase AF, E1; owner, 2026-10-14).

Out of office counts people: Sutherland's is (unplanned leave + planned leave + sick) / scheduled employees, anyone
on a day off left out; the client's adds public holiday (and exam leave, Phase AI) to the top line. Planned leave is read from the schedule (the
RTA has no Planned leave status). In office counts minutes: the time present people spend off the floor on what the
program maps as in-office shrinkage (breaks and lunch, and aux that is not billable, to start with) over their
scheduled minutes. What counts is a program setting that the admin or a supervisor maps.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Set

from .day import ABSENT, AUX, EXTRA_BREAKS

# (key, label, the measures it can count for), in the order of the owner's formula
ITEMS = (("breaks", "Breaks and lunch", ("in",)),
         ("aux", "Aux, not billable (training, coaching, meeting, system issue, task, bio break)", ("in",)),
         ("aux_billable", "Aux, billable", ("in",)),
         ("unplanned", "Unplanned leave", ("sutherland", "client")),
         ("planned", "Planned leave (from the schedule)", ("sutherland", "client")),
         ("sick", "Sick", ("sutherland", "client")),
         ("holiday", "Public holiday", ("sutherland", "client")),
         ("exam", "Exam leave", ("sutherland", "client")))  # Phase AI: the client's, not Sutherland's
DEFAULT: Dict[str, Set[str]] = {"breaks": {"in"}, "aux": {"in"}, "aux_billable": set(),
                                "unplanned": {"sutherland", "client"}, "sick": {"sutherland", "client"},
                                "planned": {"sutherland", "client"}, "holiday": {"client"}, "exam": {"client"}}
STATUS_OF = {"unplanned": "Unplanned leave", "sick": "Sick", "holiday": "Public holiday", "exam": "Exam leave"}
WORDS = {"breaks": "breaks and lunch", "aux": "aux not billable", "aux_billable": "aux billable",
         "unplanned": "unplanned", "sick": "sick", "planned": "planned", "holiday": "public holiday",
         "exam": "exam leave"}
NAMES = {"sutherland": "Sutherland", "client": "the client"}
LEAVE = {"leave", "planned", "planned leave"}  # a schedule cell for planned leave
ITEM_OF_KIND = {"Public holiday": "holiday", "Exam leave": "exam"}  # an approved request's Leave cell (Phase AI)


def read_mapping(saved: Optional[str]) -> Dict[str, Set[str]]:
    """The saved mapping (JSON) or the default. An item the saved mapping does not name keeps its default, and a
    measure the item cannot count for is dropped."""
    found = {k: set(v) for k, v in DEFAULT.items()}
    if saved:
        data = json.loads(saved)
        for key, _, allowed in ITEMS:
            if key in data:
                found[key] = {m for m in data[key] if m in allowed}
    return found


def mapping_from_form(form: Mapping[str, Any]) -> Dict[str, List[str]]:
    """What the settings form ticked: one ``<item>:<measure>`` box per item and measure it can count for."""
    return {key: [m for m in allowed if form.get(f"{key}:{m}")] for key, _, allowed in ITEMS}


def _norm(text: Any) -> str:
    return " ".join(str(text or "").split()).casefold()


def day_shrinkage(view: Dict[str, Any], week: Dict[str, Any], day: int, mapping: Dict[str, Set[str]],
                  inputs: Optional[Dict[str, Any]] = None,
                  leave_kinds: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """The day's three figures: ``in_office``, ``sutherland`` and ``client`` (``pct`` is None with nobody to count).
    Only shifts that start on the day count (last night's belong to yesterday). ``leave_kinds`` names the kind of an
    approved leave request on the day (Phase AI): its Leave cell counts as a public holiday or exam leave, not as
    planned leave."""
    own = [s for lane in view["lanes"] for s in lane["segments"] if s["offset"] == 0]
    working = {lane["name"] for lane in view["lanes"] if any(s["offset"] == 0 for s in lane["segments"])}
    counts = {k: sum(1 for s in own if s["status"] == status) for k, status in STATUS_OF.items()}
    on_leave = [a["name"] for a in week.get("associates", [])
                if a["name"] not in working and _norm(a["days"][day]) in LEAVE]
    counts["planned"] = 0
    for name in on_leave:
        counts[ITEM_OF_KIND.get((leave_kinds or {}).get(name, ""), "planned")] += 1
    scheduled = len(working) + len(on_leave)
    found: Dict[str, Any] = {}
    for measure in ("sutherland", "client"):
        parts = [k for k, _, _ in ITEMS if k in counts and measure in mapping.get(k, ())]
        only = [k for k in parts if not any(measure != m and m in mapping.get(k, ()) for m in NAMES)]
        found[measure] = {
            "pct": sum(counts[k] for k in parts) / scheduled if scheduled else None, "scheduled": scheduled,
            "text": ("(" + " + ".join(f"{WORDS[k]} {counts[k]}" for k in parts) + f") / {scheduled} scheduled")
            if parts else "Nothing is counted for it.",
            "notes": ["Days off are not counted"] + [f"{WORDS[k].capitalize()} counts for {NAMES[measure]} only"
                                                     for k in only]}
    present = [s for s in own if s["status"] not in ABSENT]
    off = {"breaks": 0, "aux": 0, "aux_billable": 0}
    for s in present:
        off["breaks"] += sum(b["minutes"] for b in s["breaks"])
        off["breaks"] += sum(a["end"] - a["start"] for a in s["activities"] if a["kind"] in EXTRA_BREAKS)
        if s["status"] in AUX and s["away"][1] > s["away"][0]:
            off["aux_billable" if s["billable"] else "aux"] += s["away"][1] - s["away"][0]
        for a in s["activities"]:
            if a["kind"] in AUX:
                off["aux_billable" if a.get("billable") else "aux"] += a["end"] - a["start"]
    counted = [k for k in off if "in" in mapping.get(k, ())]
    minutes = sum(s["end"] - s["start"] for s in present)
    planned = None
    if inputs:  # the input's Shrinkage tab, over the day's intervals that have demand
        need = inputs.get("required", {}).get(day, {})
        values = [v for t, v in inputs.get("planned_shrinkage", {}).get(day, {}).items() if need.get(t, 0) > 0]
        planned = sum(values) / len(values) if values else None
    found["in_office"] = {"pct": sum(off[k] for k in counted) / minutes if minutes else None,
                          "minutes": sum(off[k] for k in counted), "scheduled": minutes,
                          "counted": ", ".join(WORDS[k] for k in counted) or "nothing", "planned": planned}
    return found
