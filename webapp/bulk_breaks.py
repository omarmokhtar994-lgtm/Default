# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AD (owner, 2026-10-11: "the ability to bulk delete or change breaks for several associates at the same time";
sample 04): what one Change several breaks does to the day, worked out before anything is kept.

People are picked by name; ``which`` is a break kind ("Break 1", "Lunch", ...) or "all" (every break not started);
``action`` is "cancel", "shift" (the same amount earlier or later), "set" (the same start for everyone) or "plan"
(back to the plan). A break that has started, and a change a person's shift or other breaks do not allow, is left as
it is and said why, the way a single move would be refused."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .day import ABSENT, CANCELLED, STEP

ACTIONS = ("cancel", "shift", "set", "plan")
SHIFTS = (-30, -15, -10, -5, 5, 10, 15, 30)  # minutes, as the panel offers them
ALL = "all"


def _clock(text: str) -> Optional[int]:
    try:
        hh, mm = (int(x) for x in (text or "").split(":"))
    except ValueError:
        return None
    return hh * 60 + mm if 0 <= hh < 24 and 0 <= mm < 60 else None


def plan(view: Dict[str, Any], names: List[str], which: str, action: str, amount: int = 0, at: str = "",
         now: Optional[int] = None) -> Dict[str, Any]:
    """The changes (name, idx, kind, minutes, start, new: a minute, ``CANCELLED``, or None for the plan) and the
    people left as they are (name, kind, why), in the order picked. Raises ValueError for a request it cannot read."""
    if action not in ACTIONS:
        raise ValueError("Pick what to do with the breaks.")
    if action == "shift" and amount not in SHIFTS:
        raise ValueError("Pick how much earlier or later.")
    minute = _clock(at) if action == "set" else None
    if action == "set" and minute is None:
        raise ValueError("Give the time like 16:00.")
    segs = {l["name"]: s for l in view["lanes"] for s in l["segments"] if s["offset"] == 0}
    changes: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for name in dict.fromkeys(names):  # each person once, in the order picked
        seg = segs.get(name)
        if seg is None:
            skipped.append({"name": name, "kind": which if which != ALL else "", "why": "no shift starts today"})
            continue
        if seg["status"] in ABSENT:
            skipped.append({"name": name, "kind": which if which != ALL else "",
                            "why": f"marked {seg['status'].lower()}"})
            continue
        live = [dict(b, cancelled=False) for b in seg["breaks"]]
        gone = [dict(b, start=b["planned_start"], cancelled=True) for b in seg.get("cancelled", [])]
        pool = sorted(live + gone, key=lambda b: b["idx"])
        picked = [b for b in pool if which == ALL or b["kind"] == which]
        if which == ALL:
            picked = [b for b in picked if now is None or b["start"] > now]
        if not picked:
            skipped.append({"name": name, "kind": which if which != ALL else "",
                            "why": f"has no {which}" if which != ALL else "has no break left today"})
            continue
        starts = {b["idx"]: (None if b["cancelled"] else b["start"]) for b in pool}  # as changed so far
        for b in picked:
            why, new = _one(seg, b, starts, action, amount, minute, now)
            if why:
                skipped.append({"name": name, "kind": b["kind"], "why": why})
                continue
            starts[b["idx"]] = None if new == CANCELLED else (b["planned_start"] if new is None else new)
            changes.append({"name": name, "idx": b["idx"], "kind": b["kind"], "minutes": b["minutes"],
                            "start": b["start"], "cancelled": b["cancelled"], "new": new})
    return {"changes": changes, "skipped": skipped}


def _one(seg: Dict[str, Any], b: Dict[str, Any], starts: Dict[int, Optional[int]], action: str, amount: int,
         minute: Optional[int], now: Optional[int]):
    """(why it is left as it is, or "") and the new start for one break."""
    started = now is not None and b["start"] <= now and not b["cancelled"]
    if action == "plan":
        if not b["cancelled"] and b["start"] == b["planned_start"]:
            return "already at its plan time", None
        if started:
            return "it has started", None
        return "", None
    if started:
        return "it has started", None
    if action == "cancel":
        return ("already cancelled", None) if b["cancelled"] else ("", CANCELLED)
    if b["cancelled"]:
        return "it is cancelled: put it back to plan first", None
    if action == "shift":
        new = b["start"] + amount
    else:
        new = minute + (1440 if minute < seg["start"] and minute + 1440 < seg["end"] else 0)
    if new % STEP:
        return "breaks move in 5-minute steps", None
    if now is not None and new < now:
        return "that time has passed", None
    if new < seg["start"] or new + b["minutes"] > seg["end"]:
        return f"it would fall outside the shift ({seg['label']})", None
    for idx, s in starts.items():
        other = next((o for o in seg["breaks"] + seg.get("cancelled", []) if o["idx"] == idx), None)
        if idx == b["idx"] or s is None or other is None:
            continue
        if new < s + other["minutes"] and s < new + b["minutes"]:
            return f"it would overlap their {other['kind']}", None
    return "", new


def verb(action: str, n: int) -> str:
    """"cancelled 4 breaks", "moved 2 breaks", ... for the journal and the flash."""
    word = {"cancel": "cancelled", "shift": "moved", "set": "set", "plan": "put back to plan"}[action]
    return f"{word} {n} break{'s' if n != 1 else ''}"
