# © 2026 Omar Mokhtar. All rights reserved.
"""Program history, trends, insights and suggestions, from run rows.

A program week's figures come from one run: the latest finished run for that
program and week whose outcome was Approved or Needs review (the run page and
the program page say which run, and how many runs that week had). Every
sentence is computed from the stored figures; estimates say they are estimates.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

EGYPT = timezone(timedelta(hours=3))
COUNTED = ("DONE", "REVIEW")
UNTAGGED = "Untagged"


def _metrics(run: dict) -> Optional[dict]:
    try:
        m = json.loads(run.get("metrics") or "")
    except ValueError:
        return None
    return m if isinstance(m, dict) and m.get("active") else None


def _sunday(epoch: float) -> str:
    day = datetime.fromtimestamp(epoch, EGYPT).date()
    return (day - timedelta(days=(day.weekday() + 1) % 7)).isoformat()


def share(part: Optional[float], whole: Optional[float]) -> Optional[int]:
    return int(round(100 * part / whole)) if part is not None and whole else None


def _figures(m: dict) -> Dict[str, Any]:
    eff = m.get("efficiency") or {}
    return {
        "associates": m.get("associates"),
        "after_pct": share(m.get("fully_covered"), m.get("active")),
        "before_pct": share(m.get("before_full"), m.get("active")),
        "at90_pct": share(m.get("at_90"), m.get("active")),
        "efficiency": eff.get("pct"),
        "over_hours": eff.get("over_hours"),
        "under_hours": eff.get("under_hours"),
        "slack_hours": m.get("slack_hours"),
        "productive_hours": m.get("productive_hours"),
        "target_hours": m.get("target_hours"),
    }


def program_weeks(runs: List[dict]) -> Dict[str, List[dict]]:
    chosen: Dict[tuple, dict] = {}
    counts: Counter = Counter()
    for run in runs:
        m = _metrics(run)
        outcome = (m or {}).get("outcome") or run.get("status")
        if m is None or outcome not in COUNTED:
            continue
        program = run.get("program") or UNTAGGED
        week = run.get("week_start") or _sunday(run.get("created") or 0)
        key = (program, week)
        counts[key] += 1
        when = run.get("finished") or run.get("created") or 0
        if key not in chosen or when >= (chosen[key]["finished"] or 0):
            chosen[key] = {"program": program, "week": week, "run_id": run["id"], "workbook": run.get("workbook"),
                           "by_name": run.get("by_name"), "mode": run.get("mode"), "finished": when,
                           "week_basis": "set" if run.get("week_start") else "run date", "m": m,
                           "f": _figures(m)}
    out: Dict[str, List[dict]] = {}
    for (program, week), row in sorted(chosen.items()):
        row["runs_that_week"] = counts[(program, week)]
        out.setdefault(program, []).append(row)
    for weeks in out.values():
        for i, row in enumerate(weeks):
            prev = weeks[i - 1]["f"] if i else None
            row["delta"] = {k: (None if prev is None or row["f"][k] is None or prev[k] is None
                                else round(row["f"][k] - prev[k], 1)) for k in row["f"]}
    return out


def _signed(value: float, unit: str = "") -> str:
    value = round(value, 1)
    value = int(value) if float(value).is_integer() else value
    if value > 0:
        return f"up {value}{unit}"
    if value < 0:
        return f"down {abs(value)}{unit}"
    return "unchanged"


def _date(week: str) -> str:
    return datetime.strptime(week, "%Y-%m-%d").strftime("%d %b")


def recurring(weeks: List[dict], last: int = 8) -> Dict[str, Any]:
    recent = weeks[-last:]
    counts: Counter = Counter()
    for row in recent:
        counts.update(set(row["m"].get("short_cells") or []))
    return {"weeks": len(recent), "counts": dict(counts),
            "top": sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]}


def insights(weeks: List[dict]) -> List[dict]:
    """Plain sentences about what happened, newest week first."""
    if not weeks:
        return []
    out: List[dict] = []
    now, f, d, m = weeks[-1], weeks[-1]["f"], weeks[-1]["delta"], weeks[-1]["m"]
    prev = weeks[-2] if len(weeks) > 1 else None
    since = f" from {prev['f']['associates']} in the week of {_date(prev['week'])}" if prev else ""
    if prev is None:
        out.append({"level": "info", "text": f"First week on record for this program (week of {_date(now['week'])})."})
    if f["associates"] is not None:
        trend = f", {_signed(d['associates'])}{since}" if d["associates"] is not None else ""
        span = [w["f"]["associates"] for w in weeks if w["f"]["associates"] is not None]
        rng = f" Over {len(span)} weeks: {min(span)} to {max(span)}." if len(span) > 2 else ""
        out.append({"level": "info", "text": f"Associates: {f['associates']} this week{trend}.{rng}"})
    if f["after_pct"] is not None:
        trend = f", {_signed(d['after_pct'], ' points')} from last week" if d["after_pct"] is not None else ""
        out.append({"level": "up" if (d["after_pct"] or 0) > 0 else "down" if (d["after_pct"] or 0) < 0 else "info",
                    "text": f"Half-hours fully covered after breaks: {f['after_pct']}% "
                            f"({m['fully_covered']} of {m['active']}){trend}."})
    if f["before_pct"] is not None and f["after_pct"] is not None:
        lost = f["before_pct"] - f["after_pct"]
        out.append({"level": "info", "text": f"Fully covered before breaks: {f['before_pct']}%, so breaks cost "
                                             f"{lost} points this week."})
    if f["efficiency"] is not None:
        trend = f", {_signed(d['efficiency'], ' points')}" if d["efficiency"] is not None else ""
        out.append({"level": "info", "text": f"Schedule efficiency {f['efficiency']}%{trend}: {f['over_hours']} staffed "
                                             f"hours above need and {f['under_hours']} below."})
    causes = sorted((m.get("restrictions") or {}).get("causes") or [], key=lambda c: -c["count"])
    total = (m.get("restrictions") or {}).get("total") or 0
    if total and causes and causes[0]["count"]:
        top = causes[0]
        out.append({"level": "info", "text": f"Main reason for missing 100%: {top['label'][0].lower() + top['label'][1:]}"
                                             f" ({top['count']} of {total} half-hours)."})
    rec = recurring(weeks)
    if rec["weeks"] >= 3:
        for cell, count in rec["top"][:3]:
            if count >= max(3, rec["weeks"] // 2 + 1):
                out.append({"level": "down", "text": f"{cell} was short in {count} of the last {rec['weeks']} weeks."})
    return out


def suggestions(m: dict) -> List[dict]:
    """What would move this week closer to 100%, from its own figures."""
    out: List[dict] = []
    active = m.get("active") or 0
    targets = {t["pct"]: t["after"] for t in m.get("targets") or []}
    if active and targets:
        parts = [f"at {p}% it is met in {share(targets[p], active)}%" for p in (95, 90, 85) if p in targets]
        out.append({"level": "target", "text": f"Interval target: 100% is met in {share(targets.get(100), active)}% "
                                               f"of half-hours; " + "; ".join(parts) + ". If your service goal allows "
                                               f"90% per half-hour, this schedule meets it {share(targets.get(90), active)}% "
                                               "of the time."})
    causes = {c["key"]: c for c in (m.get("restrictions") or {}).get("causes") or []}
    total = (m.get("restrictions") or {}).get("total") or 0
    if total and causes.get("breaks", {}).get("count", 0) * 2 >= total:
        c = causes["breaks"]
        out.append({"level": "breaks", "text": f"Breaks cause {c['count']} of the {total} half-hours below 100% "
                                               f"(for example {', '.join(c['examples'][:3])}). Review the break rules: "
                                               "wider break windows or fewer people allowed on break at once in these "
                                               "hours would keep them covered."})
    if causes.get("capacity", {}).get("count"):
        c = causes["capacity"]
        out.append({"level": "capacity", "text": f"{c['count']} half-hours cannot reach 100% even if everyone who "
                                                 f"can work then did (for example {', '.join(c['examples'][:3])}): "
                                                 "add people available at those hours, or shift start times that "
                                                 "cover them."})
    if causes.get("weekly_hours", {}).get("count"):
        add = max(m.get("add_for_target") or 0, m.get("add_for_floor") or 0)
        out.append({"level": "capacity", "text": "Total weekly hours are below what the target needs"
                                                 + (f": about {add} more people (the scheduler's estimate)." if add else ".")})
    if causes.get("rules", {}).get("count"):
        c = causes["rules"]
        out.append({"level": "rules", "text": f"{c['count']} half-hours are short although enough people exist "
                                              f"(for example {', '.join(c['examples'][:3])}): rest rules, days off or "
                                              "the shift start times on offer keep them elsewhere. More start-time "
                                              "options or flexible days off would help."})
    eff = m.get("efficiency") or {}
    over = eff.get("over_hours") or 0
    if over >= 10 and over > 2 * (eff.get("under_hours") or 0):
        top = (m.get("over_windows") or [{}])[0]
        short = (m.get("short_windows") or [{}])[0]
        where = f", most at {top['day']} {top['start']} to {top['end']}" if top.get("day") else ""
        to = f" Moving shift hours from there toward {short['day']} {short['start']} could lift coverage." if short.get("day") else ""
        out.append({"level": "over", "text": f"{over} staffed hours above need this week{where}.{to}"})
    if m.get("release_estimate"):
        out.append({"level": "hc", "text": f"Estimate: the same demand could be met with up to {m['release_estimate']} "
                                           "fewer associates, if shifts, days off and languages allow."})
    adds = max(m.get("add_for_target") or 0, m.get("add_for_floor") or 0, m.get("add_for_breaks") or 0)
    if adds:
        out.append({"level": "hc", "text": f"Estimate: about {adds} more associates would be needed to reach the target."})
    return out


def team(runs: List[dict]) -> List[dict]:
    people: Dict[str, dict] = {}
    for run in runs:
        name = run.get("by_name") or "Unknown"
        p = people.setdefault(name, {"name": name, "runs": 0, "approved": 0, "review": 0, "not_approved": 0,
                                     "rejected": 0, "other": 0, "programs": set(), "minutes": [], "last": 0})
        outcome = ((_metrics(run) or {}).get("outcome")) or run.get("status")
        p["runs"] += 1
        key = {"DONE": "approved", "REVIEW": "review", "FAILED": "not_approved", "REJECTED": "rejected"}.get(outcome, "other")
        p[key] += 1
        p["programs"].add(run.get("program") or UNTAGGED)
        if run.get("started") and run.get("finished") and outcome in COUNTED:
            p["minutes"].append((run["finished"] - run["started"]) / 60)
        p["last"] = max(p["last"], run.get("created") or 0)
    rows = []
    for p in people.values():
        minutes = p.pop("minutes")
        p["programs"] = sorted(p["programs"])
        p["avg_minutes"] = round(sum(minutes) / len(minutes)) if minutes else None
        rows.append(p)
    return sorted(rows, key=lambda r: (-r["runs"], r["name"]))
