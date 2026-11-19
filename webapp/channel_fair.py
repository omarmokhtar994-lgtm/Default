# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AL (owner, 2026-10-15: "We need to add fairness for channels now as a start during the day/week etc";
answers: same share and turns, the week mainly and the day where the week cannot, coverage wins, a view first,
compared among people with the same channels and the same language).

Counted from the plan the Plan channels page shows (the version's, or its unsaved draft day by day), in 15-minute
slots. A break is not channel time; it does not end a turn either. "All channels at once" (A) is its own column.
Nothing here changes the plan or the coverage."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .channel_page import _at, current, people_for
from .channel_people import can_work, channel_words
from .channels import QUARTER
from .versions import DAYS, shift_span

LETTERS = "PCEA"
FURTHEST = 10.0  # points from even, at least, to be named the furthest in a group


def _day_counts(week: Dict[str, Any], rules: Dict[str, Any], draft: Dict[str, Any], skills: Dict[str, str],
                language_rows: List[Dict[str, Any]], d: int) -> Dict[str, Dict[str, Any]]:
    """name -> {"minutes": {letter: int}, "longest": int} for day ``d``."""
    if not any(shift_span(a["days"][d]) for a in week.get("associates", [])):
        return {}
    plan = current(week, d, rules, draft)
    people = people_for(week, d, rules, plan, skills, language_rows)
    at = _at(people, plan)
    out: Dict[str, Dict[str, Any]] = {}
    for p in people:
        minutes = dict.fromkeys(LETTERS, 0)
        longest = run = 0
        letter = ""
        for t in range(p["start"], p["end"], QUARTER):
            x = at.get((p["name"], t), "")
            if x in ("B", "L"):
                continue  # a break: no channel time, and the turn goes on after it
            if not x or x not in LETTERS:
                letter, run = "", 0
                continue
            minutes[x] += QUARTER
            run = run + QUARTER if x == letter else QUARTER
            letter = x
            longest = max(longest, run)
        out[p["name"]] = {"minutes": minutes, "longest": longest}
    return out


def _groups(rows: Dict[str, Dict[str, Any]], week: Dict[str, Any], skills: Dict[str, str]) -> List[Dict[str, Any]]:
    language = {a["name"]: a.get("language", "") for a in week.get("associates", [])}
    by_key: Dict[Any, List[Dict[str, Any]]] = {}
    for name, r in rows.items():
        total = sum(r["minutes"].values())
        if not total:
            continue
        share = {c: r["minutes"][c] / total for c in LETTERS}
        key = ("".join(sorted(can_work(skills, name))), language.get(name, ""))
        by_key.setdefault(key, []).append({"name": name, "minutes": r["minutes"], "share": share, "gap": None,
                                           "longest": r["longest"], "longest_day": r.get("longest_day", ""),
                                           "furthest": False})
    out = []
    for (letters, lang), people in sorted(by_key.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        even = {c: sum(p["share"][c] for p in people) / len(people) for c in LETTERS}
        if len(people) > 1:
            for p in people:
                p["gap"] = round(max(abs(p["share"][c] - even[c]) for c in LETTERS) * 100, 1)
            top = max(p["gap"] for p in people)
            for p in people:
                p["furthest"] = top >= FURTHEST and p["gap"] == top
        people.sort(key=lambda p: (-(p["gap"] or 0), p["name"]))
        words = "All three channels" if set(letters) == set("PCE") else channel_words(letters)
        out.append({"label": f"{words}, {lang or 'no language'}", "people": people, "even": even})
    return out


def fairness(week: Dict[str, Any], rules: Dict[str, Any], draft: Dict[str, Any], skills: Dict[str, str],
             language_rows: Iterable[Dict[str, Any]], d: int) -> Dict[str, List[Dict[str, Any]]]:
    """Who works which channel, for the week and for day ``d``: groups of people with the same channels and language,
    each person's minutes and share per channel, how far the share is from the group's even share (points), whether
    they are the furthest from even, and their longest time on one channel in a day."""
    rows = list(language_rows)
    days = {e: _day_counts(week, rules, draft, skills, rows, e) for e in range(7)}
    total: Dict[str, Dict[str, Any]] = {}
    for e, counts in days.items():
        for name, r in counts.items():
            t = total.setdefault(name, {"minutes": dict.fromkeys(LETTERS, 0), "longest": 0, "longest_day": ""})
            for c in LETTERS:
                t["minutes"][c] += r["minutes"][c]
            if r["longest"] > t["longest"]:
                t["longest"], t["longest_day"] = r["longest"], DAYS[e]
    today = {name: dict(r, longest_day=DAYS[d]) for name, r in days[d].items()}
    return {"week": _groups(total, week, skills), "day": _groups(today, week, skills)}
