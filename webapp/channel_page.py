# © 2026 Omar Mokhtar. All rights reserved.
"""Phase V: what the "Plan channels" page shows and changes for one day of a version: the plan (the draft's, else
the version's), the people as the planner sees them, a block set by hand (checked), the grid, the coverage per
channel and language, and the plan in words for the change log."""
from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional

from .break_plan import hm, slots_for
from .channel_people import can_work
from .channel_plan import allowed, counts_for, coverage_slots, fixed_cover, need_at
from .channels import CHANNELS, QUARTER, blended_at, inside
from .day import planned
from .versions import DAYS, channel_blocks, shift_span

NAMES = {**CHANNELS, "A": "All channels"}
FULL = {"Sun": "Sunday", "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday",
        "Sat": "Saturday"}


def version_plan(week: Dict[str, Any], d: int, rules: Dict[str, Any]) -> Dict[str, Any]:
    """The version's own plan for day ``d``: blocks (name -> [[start, end, letter]]) and breaks (name -> starts in
    the rules' break order, None where the version has none)."""
    out: Dict[str, Any] = {"blocks": {}, "breaks": {}, "moved": [], "note": ""}
    for a in week.get("associates", []):
        span = shift_span(a["days"][d])
        if not span:
            continue
        mine = planned(week, d, a["name"])
        out["breaks"][a["name"]] = [next((b["start"] for b in mine if b["kind"] == kind), None)
                                    for kind, _ in slots_for(rules, span[1] - span[0])]
        out["blocks"][a["name"]] = [[b["start"], b["end"], b["channel"]] for b in channel_blocks(week, d, a["name"])]
    return out


def current(week: Dict[str, Any], d: int, rules: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(draft.get(DAYS[d]) or version_plan(week, d, rules))


def people_for(week: Dict[str, Any], d: int, rules: Dict[str, Any], plan: Dict[str, Any], skills: Dict[str, str],
               language_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Everyone working day ``d``, as the planner takes them, with the plan's break times."""
    rows = list(language_rows)
    people = []
    for a in week.get("associates", []):
        span = shift_span(a["days"][d])
        if not span:
            continue
        slots = slots_for(rules, span[1] - span[0])
        starts = (list(plan["breaks"].get(a["name"]) or []) + [None] * len(slots))[:len(slots)]
        people.append({"name": a["name"], "language": a.get("language", ""), "label": a["days"][d],
                       "start": span[0], "end": span[1],
                       "breaks": [(kind, s, minutes) for (kind, minutes), s in zip(slots, starts)],
                       "skills": can_work(skills, a["name"]), "counts_for": counts_for(a.get("language", ""), rows)})
    return sorted(people, key=lambda p: (p["start"], p["name"]))


def carry(week: Dict[str, Any], rules: Dict[str, Any], draft: Dict[str, Any], d: int) -> Dict[str, Dict[str, int]]:
    """Minutes per channel each person has on the days before ``d`` this week (for the fair spread)."""
    out: Dict[str, Dict[str, int]] = {}
    for e in range(d):
        for name, blocks in current(week, e, rules, draft)["blocks"].items():
            for start, end, letter in blocks:
                if letter in CHANNELS:
                    out.setdefault(name, {}).setdefault(letter, 0)
                    out[name][letter] += end - start
    return out


def before(week: Dict[str, Any], rules: Dict[str, Any], draft: Dict[str, Any], d: int,
           skills: Dict[str, str], language_rows=(), previous_week=None) -> Dict[str, Dict[int, int]]:
    """Fixed overnight coverage, including skills, languages and breaks; Sunday can use the prior week."""
    if d == 0 and previous_week is None:
        return {}
    source, previous_day = (previous_week, 6) if d == 0 else (week, d - 1)
    plan = current(source, previous_day, rules, {} if d == 0 else draft)
    people = people_for(source, previous_day, rules, plan, skills, language_rows)
    at = _at(people, plan)
    out = {}
    for p in people:
        for t in range(max(1440, p["start"]), p["end"], QUARTER):
            letter = at.get((p["name"], t), "")
            for c in (p["skills"] if letter == "A" else letter if letter in "PCE" else ""):
                for key in [c] + [f"{c}:{lang}" for lang in p["counts_for"]]:
                    out.setdefault(key, {})[t - 1440] = out.get(key, {}).get(t - 1440, 0) + 1
    return out


def _runs(slots: Dict[int, str]) -> List[List[Any]]:
    runs: List[List[Any]] = []
    for t in sorted(slots):
        if runs and runs[-1][1] == t and runs[-1][2] == slots[t]:
            runs[-1][1] = t + QUARTER
        else:
            runs.append([t, t + QUARTER, slots[t]])
    return runs


def apply_edit(plan: Dict[str, Any], person: Dict[str, Any], start: int, end: int, letter: str,
               setup: Dict[str, Any], d: int) -> Dict[str, Any]:
    """The plan with ``person`` on ``letter`` from ``start`` to ``end``; refused (ValueError, plain words) outside the
    shift, off the quarter hours, on a break, in all-channels time, outside Email Hours' window, or for a channel
    the person cannot work."""
    name = person["name"]
    if letter not in CHANNELS:
        raise ValueError("Pick Phone, Chat or Email.")
    if start % QUARTER or end % QUARTER:
        raise ValueError("Blocks go in 15-minute steps.")
    if not (person["start"] <= start < end <= person["end"]):
        raise ValueError(f"{hm(start)} to {hm(end)} is outside {name}'s shift ({person['label']}).")
    if letter not in person["skills"]:
        raise ValueError(f"{name} cannot work {CHANNELS[letter]} (see Associate channels).")
    for (kind, _, minutes), s in zip(person["breaks"], plan["breaks"].get(name) or []):
        if s is not None and s < end and start < s + minutes:
            raise ValueError(f"{name} is on a break then ({kind} at {hm(s)}).")
    for t in range(start, end, QUARTER):
        if blended_at(setup, d, t):
            raise ValueError(f"{hm(t)} is an all-channels time: there everyone covers every channel they work.")
        if letter not in allowed(setup, d, person, t):
            window = setup["email_hours"][d]
            raise ValueError(f"Email Hours are planned between {hm(window['start'])} and {hm(window['end'])} on "
                             f"{FULL[DAYS[d]]}.")
    slots = {t: x for a, b, x in plan["blocks"].get(name, []) for t in range(a, b, QUARTER)}
    slots.update({t: letter for t in range(start, end, QUARTER)})
    changed = copy.deepcopy(plan)
    changed["blocks"][name] = _runs(slots)
    return changed


def describe(blocks: Iterable[Iterable[Any]]) -> str:
    """"Phone 10:00 to 12:00, Chat 12:00 to 14:00", or "no channel plan"."""
    said = [f"{NAMES[x]} {hm(a)} to {hm(b)}" for a, b, x in blocks]
    return ", ".join(said) or "no channel plan"


def _at(people: List[Dict[str, Any]], plan: Dict[str, Any]) -> Dict[Any, str]:
    """(name, slot) -> P, C, E, A, B (break) or L (lunch)."""
    at: Dict[Any, str] = {}
    for p in people:
        for (kind, _, minutes), s in zip(p["breaks"], plan["breaks"].get(p["name"]) or []):
            if s is not None:
                for t in range(s - s % QUARTER, s + minutes, QUARTER):
                    at[p["name"], t] = "L" if "lunch" in kind.casefold() else "B"
        for a, b, x in plan["blocks"].get(p["name"], []):
            for t in range(a, b, QUARTER):
                at.setdefault((p["name"], t), x)
    return at


def grid(people: List[Dict[str, Any]], plan: Dict[str, Any]) -> Dict[str, Any]:
    """The 15-minute grid: hours across, people down; each cell's letter (empty where nothing is planned)."""
    if not people:
        return {"cols": [], "hours": [], "rows": []}
    lo = min(p["start"] for p in people)
    hi = max(p["end"] for p in people)
    cols = list(range(lo - lo % 60, hi + (-hi % 60), QUARTER))
    at = _at(people, plan)
    rows = []
    for p in people:
        cells, runs = [], []
        for t in cols:
            if not p["start"] <= t < p["end"]:
                cells.append({"t": t, "letter": "", "cls": "off"})
            else:
                letter = at.get((p["name"], t), "")
                cells.append({"t": t, "letter": letter, "cls": f"ch-{letter}" if letter else "none"})
                if runs and runs[-1][1] == t and runs[-1][2] == letter:  # Phase AF (C1): one box per stretch
                    runs[-1] = (runs[-1][0], t + QUARTER, letter)
                else:
                    runs.append((t, t + QUARTER, letter))
        rows.append({"name": p["name"], "language": p["language"], "label": p["label"], "skills": p["skills"],
                     "start": p["start"], "end": p["end"], "cells": cells, "runs": runs})
    return {"cols": cols, "hours": [t for t in cols if t % 60 == 0], "rows": rows}


def coverage(people: List[Dict[str, Any]], plan: Dict[str, Any], setup: Dict[str, Any], d: int,
             step: int, before=None, horizon=None) -> List[Dict[str, Any]]:
    """Per interval: people on each channel (the average of its 15-minute slots) against the need, and each language
    minimum (its lowest slot) against the minimum. Email Hours shows people on Email only."""
    at = _at(people, plan)
    quarters = coverage_slots(people, before, horizon)
    times = sorted({t - t % step for t in quarters})

    def count(t: int, letter: str, who: Optional[str] = None) -> int:
        return fixed_cover(before, letter, t, who) + sum(1 for p in people if (who is None or who in p["counts_for"])
                   and (at.get((p["name"], t)) == letter or (at.get((p["name"], t)) == "A" and letter in p["skills"])))

    rows = []
    for letter in [c for c in "PCE" if c in setup["need"]] + (["E"] if setup["email_mode"] == "hours" else []):
        cells = []
        for t in times:
            have = sum(count(s, letter) for s in range(t, t + step, QUARTER)) / (step // QUARTER)
            if letter in setup["need"]:
                need = need_at(setup, letter, d, t)
                cls = "none" if not need and not have else ("ok" if have >= need else
                                                             ("warn" if have > need - 1 else "bad"))
                cells.append({"t": t, "text": f"{have:g}/{need:g}" if need or have else "", "cls": cls})
            else:
                cells.append({"t": t, "text": f"{have:g}" if have else "", "cls": "em" if have else "none"})
        rows.append({"name": CHANNELS[letter], "cells": cells})
    for rule in setup["languages"]:
        if not rule["active"] or rule["minimum"] <= 0:
            continue
        cells = []
        for t in times:
            if not inside(rule["days"], rule["start"], rule["end"], (d + t // 1440) % 7, t % 1440):
                cells.append({"t": t, "text": "", "cls": "none"})
                continue
            low = min(count(s, rule["channel"], rule["language"].casefold()) for s in range(t, t + step, QUARTER))
            cells.append({"t": t, "text": f"{low}/{rule['minimum']}",
                          "cls": "ok" if low >= rule["minimum"] else "bad"})
        rows.append({"name": f"{CHANNELS[rule['channel']]} · {rule['language']} (at least {rule['minimum']})",
                     "cells": cells})
    return rows


def planned_anything(plan: Dict[str, Any]) -> bool:
    return any(plan["blocks"].values())
