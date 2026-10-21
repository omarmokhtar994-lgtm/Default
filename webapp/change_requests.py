# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AS (owner, 2026-10-21): the times an associate may ask a break to move to, and the times a team manager may ask
coaching for, each with its buffer: the people on the floor above the need in the tightest interval it touches, once the
person (or people) are off the queue. One above the need is High, at the need Moderate, below it Low (the owner's answer).

The views are the RTA's: a day view or a window view whose minutes start at ``view["start"]`` (a shift past 00:00 needs
the window), with the shifts' breaks and activities as the RTA holds them."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .day import MEETING_MARGIN, STEP, _busy, _own, break_window

HIGH, MODERATE, LOW = "high", "moderate", "low"
PEOPLE_FOR_HIGH = 1  # people above the need that make the buffer High


def level_of(people_above: Optional[float]) -> str:
    """High, Moderate or Low for ``people_above`` (None: no demand in the intervals touched, nothing to protect)."""
    if people_above is None or people_above >= PEOPLE_FOR_HIGH - 1e-9:
        return HIGH
    return MODERATE if people_above >= -1e-9 else LOW


def _slots(view: Dict[str, Any]) -> List[float]:
    return [x for c in view["cells"] for x in c["slots"]]


def _tightest(view: Dict[str, Any], slots: List[float], lo: int, hi: int) -> Optional[float]:
    """The smallest (people on the floor - people needed) over the intervals that overlap minutes ``lo`` to ``hi``."""
    step, v0 = view["interval"], view.get("start", 0)
    found = []
    for c in view["cells"]:
        if c["required"] > 0 and c["t"] < hi and lo < c["t"] + step:
            here = slots[(c["t"] - v0) // STEP:(c["t"] - v0 + step) // STEP]
            found.append(sum(here) / len(here) - c["required"])
    return round(min(found), 2) if found else None


def break_choices(view: Dict[str, Any], inputs: Dict[str, Any], name: str, idx: int, now: int,
                  step: int = 15) -> Dict[str, Any]:
    """Every legal start for break ``idx`` of ``name``'s shift in ``view`` that begins at or after ``now`` (minutes of the
    view): inside the shift, off the other breaks and within the program's gaps. Each is {"start", "end",
    "people_above", "level", "current"}; the time it has now is among them."""
    seg = _own(view, name)
    if seg is None:
        raise ValueError(f"{name} has no shift this day.")
    me = next((b for b in seg["breaks"] if b["idx"] == idx), None)
    if me is None:
        raise ValueError("That break is not on the plan.")
    lo, hi = break_window(seg, me, {b["idx"]: b["start"] for b in seg["breaks"]}, now,
                          inputs.get("gap_min"), inputs.get("gap_max"))
    others = [b for b in seg["breaks"] if b["idx"] != idx]
    v0, base = view.get("start", 0), _slots(view)
    counts_away = not (seg["billable"] and view["measure"] == "interval")

    def free(t: int) -> bool:  # on the floor at t, this break aside
        if not seg["start"] <= t < seg["end"] or (counts_away and seg["away"][0] <= t < seg["away"][1]):
            return False
        return not any(b["start"] <= t < b["start"] + b["minutes"] for b in others)

    def slot(t: int) -> Optional[int]:
        i = (t - v0) // STEP
        return i if 0 <= i < len(base) else None

    given = list(base)
    for t in range(me["start"], me["start"] + me["minutes"], STEP):  # as if this break were not taken
        if free(t) and slot(t) is not None:
            given[slot(t)] += 1
    choices = []
    wanted = list(range(lo + (-lo) % step, hi + 1, step))
    if lo <= me["start"] <= hi and me["start"] not in wanted:
        wanted = sorted(wanted + [me["start"]])
    for m in wanted:
        trial = list(given)
        for t in range(m, m + me["minutes"], STEP):
            if free(t) and slot(t) is not None:
                trial[slot(t)] -= 1
        above = _tightest(view, trial, m, m + me["minutes"])
        choices.append({"start": m, "end": m + me["minutes"], "people_above": above, "level": level_of(above),
                        "current": m == me["start"]})
    return {"kind": me["kind"], "minutes": me["minutes"], "planned": me["planned_start"], "current": me["start"],
            "choices": choices}


def coaching_choices(view: Dict[str, Any], names: List[str], minutes: int, earliest: int, latest: int,
                     billable: bool = False, now: Optional[int] = None, step: int = 15) -> List[Dict[str, Any]]:
    """The starts (every ``step`` minutes) at which every one of ``names`` is on shift, present and free (ten minutes
    clear of a break, not away or in another activity) for ``minutes``, each with the buffer once they are all off the
    queue (a billable session under interval compliance keeps them on)."""
    segs = []
    for name in names:
        seg = _own(view, name)
        if seg is None:
            raise ValueError(f"{name} has no shift this day.")
        segs.append(seg)
    if minutes <= 0 or minutes % STEP:
        raise ValueError("Pick a length in 5-minute steps.")
    v0, base = view.get("start", 0), _slots(view)
    off_floor = 0 if (billable and view["measure"] == "interval") else len(names)
    first = max(earliest, now if now is not None else earliest)
    out = []
    for start in range(first + (-first) % step, latest - minutes + 1, step):
        if any(_busy(seg, t, MEETING_MARGIN) for seg in segs for t in range(start, start + minutes, STEP)):
            continue
        trial = list(base)
        for t in range(start, start + minutes, STEP):
            i = (t - v0) // STEP
            if 0 <= i < len(trial):
                trial[i] -= off_floor
        above = _tightest(view, trial, start, start + minutes)
        out.append({"start": start, "end": start + minutes, "people_above": above, "level": level_of(above)})
    return out
