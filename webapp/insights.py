# © 2026 Omar Mokhtar. All rights reserved.
"""Incidents and shrinkage over a period (Phase AV; owner, 2026-10-22).

One fact row per person and day, worked out from the day the RTA already shows (``DayBook.page``), the incidents ticked
when a break was moved, the approved leave and the program's shrinkage mapping. Everything on the Incidents page is a
sum of those rows: per associate, per LOB, per program, or the whole selection. Nothing here writes anything."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .adherence import person_day
from .day import ABSENT, AUX, LATE_EARLY
from .shrinkage import day_shrinkage, read_mapping

# (key, label, what a count is): the incident types, in the order they are shown
KINDS: Tuple[Tuple[str, str], ...] = (
    ("missed_break", "Missed breaks"), ("unplanned", "Unplanned leave"), ("sick", "Sick"),
    ("planned", "Planned leave"), ("late", "Late logins"), ("early", "Early leave"), ("coaching", "Coaching"),
    ("training", "Training"), ("meeting", "Meetings"), ("system_issue", "System issues"), ("task", "Tasks"),
    ("non_adherence", "Out of adherence"))
LABEL = dict(KINDS)
BEHAVIOUR = ("missed_break", "unplanned", "late", "early", "non_adherence")  # what a team manager coaches on
AUX_KEY = {"Coaching": "coaching", "Training": "training", "Meeting": "meeting", "System issue": "system_issue",
           "Task": "task"}
LEAVE_KEY = {"Unplanned leave": "unplanned", "Sick": "sick"}


def _zero() -> Dict[str, List[int]]:
    return {k: [0, 0] for k, _ in KINDS}


def day_facts(page: Dict[str, Any], unit: str, program: str, lob: str, mapping: Dict[str, Any],
              leave_kinds: Dict[str, str], missed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One fact row per person of the day ``page`` (shifts that start on it, and planned leave from the schedule)."""
    view, week, day = page["view"], page["week"], page["day"]
    on = page["date"].isoformat() if hasattr(page["date"], "isoformat") else str(page["date"])
    cells = {a["name"]: a for a in week.get("associates", [])}
    rows: List[Dict[str, Any]] = []

    def base(name: str) -> Dict[str, Any]:
        return {"unit": unit, "program": program, "lob": lob, "date": on, "name": name, "shifts": 0, "sched_min": 0,
                "adh_num": 0, "adh_den": 0, "out": 0, "client": 0, "in_off": 0, "in_sched": 0, "inc": _zero()}

    def shrink(r: Dict[str, Any], lane_view: Dict[str, Any], name: str) -> None:
        one = {"associates": [cells[name]]} if name in cells else {"associates": []}
        s = day_shrinkage(lane_view, one, day, mapping, None, leave_kinds)
        r["out"] = round((s["sutherland"]["pct"] or 0) * s["sutherland"]["scheduled"])
        r["client"] = round((s["client"]["pct"] or 0) * s["client"]["scheduled"])
        r["in_off"], r["in_sched"] = s["in_office"]["minutes"], s["in_office"]["scheduled"]

    working = set()
    for lane in view["lanes"]:
        seg = next((s for s in lane["segments"] if s["offset"] == 0), None)
        if seg is None:
            continue
        name = lane["name"]
        working.add(name)
        pd = person_day(view, name)
        r = base(name)
        r["shifts"], r["sched_min"] = 1, pd["scheduled"]
        status = seg["status"]
        if status in ABSENT:
            if status in LEAVE_KEY:
                r["inc"][LEAVE_KEY[status]] = [1, seg["end"] - seg["start"]]
        else:
            r["adh_num"], r["adh_den"] = pd["scheduled"] - pd["out_of_schedule"], pd["scheduled"]
            if status == "Late":
                r["inc"]["late"] = [1, pd["late"]]
            elif status == "Left early":
                r["inc"]["early"] = [1, pd["early"]]
            elif status in AUX_KEY and seg["away"][1] > seg["away"][0]:
                r["inc"][AUX_KEY[status]][0] += 1
                r["inc"][AUX_KEY[status]][1] += seg["away"][1] - seg["away"][0]
            for a in seg.get("activities", []):
                if a["kind"] in AUX_KEY:
                    r["inc"][AUX_KEY[a["kind"]]][0] += 1
                    r["inc"][AUX_KEY[a["kind"]]][1] += a["end"] - a["start"]
            if pd["out_of_schedule"] > 0:
                r["inc"]["non_adherence"] = [1, pd["out_of_schedule"]]
        for m in missed:
            if m["associate"] == name:
                r["inc"]["missed_break"][0] += 1
                r["inc"]["missed_break"][1] += m["minutes"]
        shrink(r, {"lanes": [lane]}, name)
        rows.append(r)
    for a in week.get("associates", []):  # planned leave: on the schedule, not on the floor
        if a["name"] in working:
            continue
        cell = " ".join(str(a["days"][day]).split()).casefold()
        if cell in ("leave", "planned", "planned leave") and leave_kinds.get(a["name"], "") not in ("Public holiday", "Exam leave"):
            r = base(a["name"])
            r["shifts"] = 1
            r["inc"]["planned"] = [1, 0]
            shrink(r, {"lanes": []}, a["name"])
            rows.append(r)
    return rows


def collect(days, store, leave, units: Dict[str, Tuple[str, str]], start: date, end: date, measure: str,
            check: Callable[[], None] = lambda: None) -> List[Dict[str, Any]]:
    """Every fact row for ``units`` (key: (program name, LOB name)) over ``start`` to ``end``."""
    facts: List[Dict[str, Any]] = []
    span = [(start + timedelta(days=i)) for i in range((end - start).days + 1)]
    for unit, (program, lob) in units.items():
        kept = store.get_shrinkage_map(unit)
        mapping = read_mapping(kept["mapping"] if kept else None)
        missed = store.list_incidents(unit, [d.isoformat() for d in span])
        for day in span:
            check()
            try:
                page = days.page(unit, day, measure)
            except ValueError:  # the input workbook is gone: said on the day page, skipped here
                continue
            if page is None:
                continue
            kinds = leave.approved_on(unit, day) if leave is not None else {}
            facts += day_facts(page, unit, program, lob, mapping, kinds,
                               [m for m in missed if m["shift_date"] == day.isoformat() and m["kind"] == "missed_break"])
    return facts


def _pct(num: float, den: float) -> Optional[float]:
    return round(100 * num / den, 1) if den else None


def figures(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """The totals over some fact rows: counts and minutes per incident, and the percentages."""
    inc = _zero()
    t = {"people": set(), "shifts": 0, "out": 0, "client": 0, "in_off": 0, "in_sched": 0, "adh_num": 0, "adh_den": 0}
    for r in rows:
        t["people"].add(r["name"])
        for k in ("shifts", "out", "client", "in_off", "in_sched", "adh_num", "adh_den"):
            t[k] += r[k]
        for k, (n, m) in r["inc"].items():
            inc[k][0] += n
            inc[k][1] += m
    absent = inc["unplanned"][0] + inc["sick"][0]
    return {"people": len(t["people"]), "shifts": t["shifts"], "incidents": {k: {"n": v[0], "min": v[1]} for k, v in inc.items()},
            "total": sum(inc[k][0] for k in BEHAVIOUR), "absenteeism": _pct(absent, t["shifts"]),
            "shrink_out": _pct(t["out"], t["shifts"]), "shrink_client": _pct(t["client"], t["shifts"]),
            "shrink_in": _pct(t["in_off"], t["in_sched"]), "adherence": _pct(t["adh_num"], t["adh_den"])}


def grouped(facts: List[Dict[str, Any]], level: str) -> List[Dict[str, Any]]:
    """Figures per associate, LOB or program, the most incidents first."""
    key = {"associates": lambda r: (r["name"], r["lob"], r["program"]), "lobs": lambda r: (r["lob"], r["program"]),
           "programs": lambda r: (r["program"],)}[level]
    found: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    for r in facts:
        found.setdefault(key(r), []).append(r)
    out = []
    for k, rows in found.items():
        f = figures(rows)
        out.append({"key": "|".join(k), "name": k[0], "lob": rows[0]["lob"], "program": rows[0]["program"], **f})
    return sorted(out, key=lambda g: (-g["total"], g["name"].casefold()))


def trend(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Figures per day, oldest first, for the charts."""
    by_day: Dict[str, List[Dict[str, Any]]] = {}
    for r in facts:
        by_day.setdefault(r["date"], []).append(r)
    return [{"date": d, **figures(rows)} for d, rows in sorted(by_day.items())]


def person(facts: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    """One associate: the totals, and each day with something recorded (newest first)."""
    mine = [r for r in facts if r["name"] == name]
    days = [{"date": r["date"], "lob": r["lob"], "incidents": {k: v for k, v in r["inc"].items() if v[0]}}
            for r in sorted(mine, key=lambda r: r["date"], reverse=True) if any(v[0] for v in r["inc"].values())]
    return {"name": name, **figures(mine), "days": days}
