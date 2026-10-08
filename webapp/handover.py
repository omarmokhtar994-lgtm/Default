# © 2026 Omar Mokhtar. All rights reserved.
"""The shift handover note: one page per program and day.

What happened (absences, late and early, aux and activities, breaks moved and by
whom, short intervals, language gaps, team adherence) and what to watch tomorrow
(short intervals and language gaps in tomorrow's plan, and anyone already marked
absent). Read from the same day as the day page.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .adherence import person_day, team
from .day import ABSENT, AUX, LATE_EARLY, _hm


def _own(view: Dict[str, Any]) -> List[tuple]:
    return [(lane, seg) for lane in view["lanes"] for seg in lane["segments"] if seg["offset"] == 0]


def _activity_text(kind: str, lo: int, hi: int, billable: bool) -> str:
    if kind == "Called in":
        return f"Day off cancelled: called in {_hm(lo)} - {_hm(hi)}"
    if kind == "Overtime":
        return f"Overtime {_hm(lo)} to {_hm(hi)}"
    if kind == "VTO":
        return f"VTO {_hm(lo)} to {_hm(hi)}"
    if kind in ("Break", "Lunch"):  # added on the day in RTA
        return f"{kind} {_hm(lo)} to {_hm(hi)}"
    return f"{kind} {_hm(lo)} to {_hm(hi)} ({'billable' if billable else 'non-billable'})"


def note(days, program: str, on: date, measure: str = "interval") -> Optional[Dict[str, Any]]:
    page = days.page(program, on, measure)
    if page is None:
        return None
    v = page["view"]
    own = _own(v)
    absent = [{"name": l["name"], "status": s["status"], "shift": s["label"]} for l, s in own if s["status"] in ABSENT]
    late_early = [{"name": l["name"], "text": f"late, in at {_hm(s['away'][1])}" if s["status"] == "Late"
                   else f"left at {_hm(s['away'][0])}"} for l, s in own if s["status"] in LATE_EARLY]
    activities = []
    for l, s in own:
        if s["status"] in AUX and s["away"][0] < s["away"][1]:
            activities.append({"name": l["name"], "text": _activity_text(s["status"], s["away"][0], s["away"][1],
                                                                         s["billable"])})
        for a in s.get("activities", []):
            activities.append({"name": l["name"], "text": _activity_text(a["kind"], a["start"], a["end"],
                                                                         a.get("billable", False))})
    by_whom = {}
    for e in page["log"]:
        by_whom[(e["associate"], e["what"])] = e["by_name"]
    moves = []
    for l, s in own:
        for b in s["breaks"]:
            if b["moved"]:
                what = f"{b['kind']} moved {_hm(b['planned_start'])} to {_hm(b['start'])}"
                who = next((n for (a, w), n in by_whom.items() if a == l["name"] and w.startswith(what)), "")
                moves.append({"name": l["name"], "what": what, "by": who})
    people = [person_day(v, l["name"]) for l, s in own]
    whole = team(people)
    pms = [c["pm"] for c in v["cells"] if c["pm"] is not None]
    tiles = v["tiles"]
    gaps = [{"language": lang["name"], "times": [_hm(c["t"]) for c in lang["cells"] if c["cls"] in ("bad", "warn")]}
            for lang in v["languages"]]
    tomorrow_day = on + timedelta(days=1)
    later = days.page(program, tomorrow_day, measure)
    tomorrow: Dict[str, Any] = {"date": tomorrow_day, "planned": later is not None}
    if later is not None:
        tv = later["view"]
        tomorrow.update({
            "short": [(c["t"], c["plan_pm"]) for c in tv["cells"] if c["plan_pm"] is not None and c["plan_pm"] < 0],
            "absent": [{"name": l["name"], "status": s["status"]} for l, s in _own(tv) if s["status"] in ABSENT],
            "plan_short_hours": tv["tiles"]["plan_short_hours"],
            "language_gaps": [{"language": lang["name"],
                               "times": [_hm(c["t"]) for c in lang["cells"] if c["cls"] in ("bad", "warn")]}
                              for lang in tv["languages"]]})
    return {"program": program, "date": on, "version": page["version"], "note": page["note"], "measure": measure,
            "absent": absent, "late_early": late_early, "activities": activities, "moves": moves,
            "short": [(c["t"], c["pm"]) for c in v["cells"] if c["pm"] is not None and c["pm"] < 0],
            "language_gaps": [g for g in gaps if g["times"]], "tomorrow": tomorrow, "log": page["log"],
            "numbers": {"planned": tiles["planned"], "present": tiles["present"], "absent": tiles["absent"],
                        "late_early": tiles["late_early"], "aux": tiles["aux"], "moved": tiles["moved"],
                        "overtime_minutes": tiles["overtime"], "vto_minutes": tiles["vto"],
                        "called_in_minutes": tiles["called_in"],
                        "short_hours": tiles["short_hours"], "plan_short_hours": tiles["plan_short_hours"],
                        "over_hours": tiles["over_hours"], "tightest": min(pms) if pms else None,
                        "language_gaps": tiles["language_gaps"], "adherence": whole["adherence"],
                        "conformance": whole["conformance"], "changes": len(page["log"])}}
