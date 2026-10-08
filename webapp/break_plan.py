# © 2026 Omar Mokhtar. All rights reserved.
"""Planning a week's breaks on the website (Phase R): for a ready schedule (shifts made elsewhere, no breaks) or
any version whose breaks someone wants to set by hand.

The rules are the engine's own, read by its parser in a subprocess (``break_rules_cli``): which breaks a shift of
a given length takes and in what order, each break's window, the edge margin, the minimum, preferred and normal
maximum gaps, and how many people may be on a break at once. Breaks start on 15-minute steps, as the validator
checks. Suggest fills only the empty breaks: each at the time inside the rules that keeps the floor's buffer
highest over the break, spread across the shift; what people typed is kept."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from .day import STEP, _tightest, day_view
from .versions import DAYS, shift_span

QUARTER = 15
Starts = List[Optional[int]]


def hm(minute: int) -> str:
    return f"{(minute // 60) % 24:02d}:{minute % 60:02d}"


def slots_for(rules: Dict[str, Any], duration_min: int) -> List[Tuple[str, int]]:
    """The breaks a shift of ``duration_min`` minutes takes, in order: (label, minutes). The stated set with the
    largest threshold the shift reaches; without one, the workbook's global set (as the engine and validator)."""
    chosen = rules.get("segments") or []
    for threshold, segments in rules.get("by_length") or []:
        if duration_min >= threshold:
            chosen = segments
    return [(str(label), int(minutes)) for minutes, label in chosen]


def _span(label: str) -> Tuple[int, int]:
    span = shift_span(label)
    if not span:
        raise ValueError(f"{label} is not a shift.")
    return span


def check_row(rules: Dict[str, Any], label: str, starts: Starts) -> Tuple[str, str]:
    """("ok", "OK"), ("none", "Not placed yet") or ("warn", what breaks a rule, in plain words)."""
    lo, hi = _span(label)
    slots = slots_for(rules, hi - lo)
    starts = (list(starts) + [None] * len(slots))[:len(slots)]
    if all(s is None for s in starts):
        return "none", "Not placed yet"
    said: List[str] = []
    margin = rules.get("edge_margin")
    windows = rules.get("windows") or {}
    for (kind, minutes), s in zip(slots, starts):
        if s is None:
            said.append(f"{kind} is not placed yet")
            continue
        if s % QUARTER:
            said.append(f"{kind} {hm(s)}: breaks go in 15-minute steps")
        if s < lo or s + minutes > hi:
            said.append(f"{kind} {hm(s)} is outside the shift ({hm(lo)} to {hm(hi)})")
            continue
        rel = s - lo
        if margin is not None and (rel < margin or rel + minutes > hi - lo - margin):
            said.append(f"{kind} is within {margin} minutes of the shift's start or end")
        w = windows.get(kind.casefold()) or {}
        if (w.get("earliest") is not None and rel < w["earliest"]) or (w.get("latest") is not None and rel > w["latest"]):
            said.append(f"{kind} has to start between {w.get('earliest') or 0} and {w.get('latest')} minutes into the shift")
    placed = [(s, kind, minutes) for (kind, minutes), s in zip(slots, starts) if s is not None]
    if [k for _, k, _ in sorted(placed)] != [k for _, k, _ in placed]:
        said.append("The breaks are out of order: " + ", ".join(k for k, _ in slots))
    else:
        for (s1, k1, m1), (s2, k2, _) in zip(placed, placed[1:]):
            gap = s2 - (s1 + m1)
            if gap < (rules.get("min_gap") or 0):
                said.append(f"{k2} starts {gap} minutes after {k1} ends; the minimum gap is {rules.get('min_gap')}")
            elif rules.get("max_gap") and gap > rules["max_gap"]:
                said.append(f"{k2} starts {gap} minutes after {k1} ends; the normal maximum is {rules['max_gap']}")
    return ("warn", "; ".join(said)) if said else ("ok", "OK")


def week_with(week: Dict[str, Any], d: int, plan: Dict[str, Starts], rules: Dict[str, Any]) -> Dict[str, Any]:
    """The week with day ``d``'s breaks replaced by ``plan`` (the breaks placed so far)."""
    out = copy.deepcopy(week)
    out["breaks"] = [b for b in out.get("breaks", []) if b["day"] != DAYS[d]]
    shifts = {a["name"]: a["days"][d] for a in week.get("associates", [])}
    for name, starts in plan.items():
        span = shift_span(shifts.get(name, ""))
        if not span:
            continue
        for (kind, minutes), s in zip(slots_for(rules, span[1] - span[0]), starts):
            if s is not None:
                out["breaks"].append({"associate": name, "day": DAYS[d], "kind": kind, "start": hm(s), "minutes": minutes})
    return out


def floor(week: Dict[str, Any], inputs: Dict[str, Any], d: int, plan: Dict[str, Starts],
          rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The day's intervals with these breaks: t, the buffer (hours, as RTA shows it) and its colour."""
    view = day_view(week_with(week, d, plan, rules), inputs, d, {}, {})
    return [{"t": c["t"], "pm": c["pm"], "cls": c["cls"]} for c in view["cells"]]


def suggest(week: Dict[str, Any], inputs: Dict[str, Any], rules: Dict[str, Any], d: int,
            plan: Dict[str, Starts]) -> Dict[str, Starts]:
    """Every working person's breaks for day ``d``: what ``plan`` holds is kept, each empty break is placed."""
    people = sorted(((a["name"], shift_span(a["days"][d])) for a in week.get("associates", [])
                     if shift_span(a["days"][d])), key=lambda p: (p[1][0], p[0]))
    out: Dict[str, Starts] = {}
    for name, (lo, hi) in people:
        slots = slots_for(rules, hi - lo)
        out[name] = (list(plan.get(name) or []) + [None] * len(slots))[:len(slots)]
    view = day_view(week_with(week, d, out, rules), inputs, d, {}, {})
    slots_now = [x for c in view["cells"] for x in c["slots"]]  # on the floor per 5 minutes, typed breaks taken
    on_break = [0] * (2 * 1440 // QUARTER)  # people on a break per quarter (this day and the night after)
    for name, (lo, hi) in people:
        for (kind, minutes), s in zip(slots_for(rules, hi - lo), out[name]):
            if s is not None:
                for q in range(s // QUARTER, (s + minutes) // QUARTER):
                    on_break[q] += 1
    margin = rules.get("edge_margin") or 0
    min_gap, preferred, most = rules.get("min_gap") or 0, rules.get("preferred_gap") or 0, rules.get("max_gap")
    cap = rules.get("max_concurrent") or 0
    windows = rules.get("windows") or {}
    for name, (lo, hi) in people:
        slots = slots_for(rules, hi - lo)
        starts = out[name]
        for k, (kind, minutes) in enumerate(slots):
            if starts[k] is not None:
                continue
            prev = next(((starts[j], slots[j][1]) for j in range(k - 1, -1, -1) if starts[j] is not None), None)
            nxt = next((j for j in range(k + 1, len(slots)) if starts[j] is not None), None)
            first = max(lo + margin, prev[0] + prev[1] + min_gap if prev else lo + margin)
            end = (starts[nxt] - min_gap) if nxt is not None else hi - margin
            later = range(k + 1, nxt if nxt is not None else len(slots))
            last = end - sum(slots[j][1] + min_gap for j in later) - minutes
            w = windows.get(kind.casefold()) or {}
            if w.get("earliest") is not None:
                first = max(first, lo + w["earliest"])
            if w.get("latest") is not None:
                last = min(last, lo + w["latest"])
            first += -first % QUARTER
            room = hi - lo
            ideal = lo + (k + 1) * room // (len(slots) + 1) - minutes // 2
            best, best_key = None, None
            for c in range(first, last + 1, QUARTER):
                gap = c - (prev[0] + prev[1]) if prev else None
                quarters = range(c // QUARTER, (c + minutes) // QUARTER)
                crowded = cap and any(on_break[q] >= cap for q in quarters if q < len(on_break))
                trial = list(slots_now)
                for t in range(c, c + minutes, STEP):
                    if 0 <= t < 1440:
                        trial[t // STEP] -= 1
                tight = _tightest(view, trial, c, c + minutes)
                key = (not crowded, gap is None or most is None or gap <= most,
                       tight if tight is not None else float("inf"),
                       -abs(c - ideal) - (abs(gap - preferred) if gap is not None and preferred else 0))
                if best_key is None or key > best_key:
                    best, best_key = c, key
            if best is None:
                continue  # no time fits the rules: left empty, and the row says why
            starts[k] = best
            for t in range(best, best + minutes, STEP):
                if 0 <= t < 1440:
                    slots_now[t // STEP] -= 1
            for q in range(best // QUARTER, (best + minutes) // QUARTER):
                if q < len(on_break):
                    on_break[q] += 1
    return out
