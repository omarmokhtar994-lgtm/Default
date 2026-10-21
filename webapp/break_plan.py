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
import math
from typing import Any, Dict, List, Optional, Tuple

from .day import STEP, _tightest, at_target, day_view, planned
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


def edge_margin(rules: Dict[str, Any], duration_min: int) -> int:
    """Minutes kept clear of breaks at a shift's start and end: the workbook's Break Edge Margin Minutes, or, left
    blank, the engine's own per-shift margin of max(2, min(4, quarters // 10)) quarter-hours (Phase AF, X3)."""
    if rules.get("edge_margin") is not None:
        return int(rules["edge_margin"])
    return QUARTER * max(2, min(4, (duration_min // QUARTER) // 10))


# Phase AU (owner, 2026-10-21): the usual shape of a shift's breaks. A preferred shape, not a rule: Suggest tries it
# first and gives way when the interval floor needs it. Minutes.
FIRST_FROM, FIRST_TO = 120, 210      # the first break starts this long after the shift starts
LUNCH_FROM, LUNCH_TO = 120, 180      # the lunch starts this much work after the first break ends
LAST_CLEAR = 60                      # the last break ends at least this long before the shift ends
SHAPE_TOLERANCE = 0.25               # when no time keeps the buffer at or above the need, the hours it may give up (BREAKS_RULE.md)


def _fits(k: int, c: int, lo: int, hi: int, starts: Starts, slots: List[Tuple[str, int]]) -> Optional[bool]:
    """Does placing break ``k`` at ``c`` fit the shape, given the breaks placed before it? None: the shape says nothing."""
    kinds = [kind.casefold() for kind, _ in slots]
    if k == 0:
        return FIRST_FROM <= c - lo <= FIRST_TO
    verdicts: List[bool] = []
    if kinds[k] == "lunch" and starts[k - 1] is not None:
        verdicts.append(LUNCH_FROM <= c - (starts[k - 1] + slots[k - 1][1]) <= LUNCH_TO)
    if k == len(slots) - 1:
        if "lunch" in kinds[:k] and starts[kinds.index("lunch")] is not None:
            i = kinds.index("lunch")
            verdicts.append(c >= starts[i] + slots[i][1])
        verdicts.append(c + slots[k][1] <= hi - LAST_CLEAR)
    return all(verdicts) if verdicts else None


def shape_fit(lo: int, hi: int, starts: Starts, slots: List[Tuple[str, int]]) -> Tuple[Optional[bool], ...]:
    """(first break, lunch, last break) against the usual shape; None for a part that is not placed or not asked."""
    kinds = [kind.casefold() for kind, _ in slots]
    starts = (list(starts) + [None] * len(slots))[:len(slots)]
    first = None if starts[0] is None else _fits(0, starts[0], lo, hi, starts, slots)
    lunch = None
    if "lunch" in kinds[1:]:
        i = kinds.index("lunch")
        if starts[i] is not None and starts[i - 1] is not None:
            lunch = LUNCH_FROM <= starts[i] - (starts[i - 1] + slots[i - 1][1]) <= LUNCH_TO
    last = None
    if len(slots) >= 2 and starts[-1] is not None:
        last = bool(_fits(len(slots) - 1, starts[-1], lo, hi, starts, slots))
    return first, lunch, last


def check_row(rules: Dict[str, Any], label: str, starts: Starts) -> Tuple[str, str]:
    """("ok", "OK"), ("none", "Not placed yet") or ("warn", what breaks a rule, in plain words)."""
    lo, hi = _span(label)
    slots = slots_for(rules, hi - lo)
    starts = (list(starts) + [None] * len(slots))[:len(slots)]
    if all(s is None for s in starts):
        return "none", "Not placed yet"
    said: List[str] = []
    margin = edge_margin(rules, hi - lo)
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
        if rel < margin or rel + minutes > hi - lo - margin:
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
          rules: Dict[str, Any], target: Optional[float] = None) -> List[Dict[str, Any]]:
    """The day's intervals with these breaks: t, the buffer (hours, as RTA shows it), on the floor and its colour by
    the week's ``target`` (Phase AH; the workbook's own when not given), amber ones marked tight."""
    view = day_view(week_with(week, d, plan, rules), inputs, d, {}, {})
    found = at_target(view["cells"], inputs.get("target", 0.9) if target is None else target)
    return [{"t": c["t"], "pm": c["pm"], "now": c["now"], "cls": s["cls"], "tight": s["tight"]}
            for c, s in zip(view["cells"], found["cells"])]


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
    staffed = [0] * (2 * 1440 // QUARTER)  # people on shift per quarter, as the validator counts them
    for name, (lo, hi) in people:
        for q in range(lo // QUARTER, min(len(staffed), -(-hi // QUARTER))):
            staffed[q] += 1
        for (kind, minutes), s in zip(slots_for(rules, hi - lo), out[name]):
            if s is not None:
                for q in range(s // QUARTER, (s + minutes) // QUARTER):
                    on_break[q] += 1
    if d > 0:  # last night's people, still on shift (and on their breaks) in this day's first hours
        for a in week.get("associates", []):
            span = shift_span(a["days"][d - 1])
            if not span or span[1] <= 1440:
                continue
            for q in range(0, -(-(span[1] - 1440) // QUARTER)):
                staffed[q] += 1
            for b in planned(week, d - 1, a["name"]):
                for q in range(max(0, b["start"] - 1440) // QUARTER, max(0, b["start"] + b["minutes"] - 1440) // QUARTER):
                    on_break[q] += 1
    min_gap, preferred, most = rules.get("min_gap") or 0, rules.get("preferred_gap") or 0, rules.get("max_gap")
    absolute, share = rules.get("max_concurrent") or 0, rules.get("max_concurrent_ratio") or 0

    def allowed(q: int) -> int:
        """The engine's limit on people on break at once (maximum_concurrent_breaks): the smallest of the people
        on shift less one, their share and the absolute cap (each at least one when set)."""
        n = staffed[q]
        if n <= 1:
            return 0
        caps = [n - 1]
        if share:
            caps.append(max(1, math.floor(n * share + 1e-9)))
        if absolute:
            caps.append(max(1, absolute))
        return min(caps)

    windows = rules.get("windows") or {}
    for name, (lo, hi) in people:
        slots = slots_for(rules, hi - lo)
        margin = edge_margin(rules, hi - lo)
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
            found = []
            for c in range(first, last + 1, QUARTER):
                gap = c - (prev[0] + prev[1]) if prev else None
                quarters = range(c // QUARTER, (c + minutes) // QUARTER)
                crowded = any(on_break[q] >= allowed(q) for q in quarters if q < len(on_break))
                trial = list(slots_now)
                for t in range(c, c + minutes, STEP):
                    if 0 <= t < 1440:
                        trial[t // STEP] -= 1
                tight = _tightest(view, trial, c, c + minutes)
                found.append((c, not crowded, gap is None or most is None or gap <= most,
                              _fits(k, c, lo, hi, starts, slots) is not False,
                              tight if tight is not None else float("inf"),
                              -abs(c - ideal) - (abs(gap - preferred) if gap is not None and preferred else 0)))
            best, best_key = None, None
            # the shape is held while the interval stays at or above the need; only when no allowed time does that, a time
            # within SHAPE_TOLERANCE of the best buffer counts as safe (owner, 2026-10-21: "unless an interval goes short")
            room_ok = [f[4] for f in found if f[1] and f[2]]
            top = max(room_ok) if room_ok else None
            for c, calm, within, shaped, tight, near in found:
                safe = top is None or tight >= (min(0.0, top) - (SHAPE_TOLERANCE if top < 0 else 0.0))
                key = (calm, within, safe and shaped, tight, near)
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
