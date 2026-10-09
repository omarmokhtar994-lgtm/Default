# © 2026 Omar Mokhtar. All rights reserved.
"""A finished run's summary for the website, read from the scheduler's files.

Everything comes from what the run wrote: the independent validator's
INDEPENDENT_VALIDATION.json (per half-hour coverage, counts, warnings), the
solver audit's capacity_diagnostics (roster, productive and needed hours,
the engine's own headcount estimates) and UNIVERSAL_RUN_STATUS.json (extra
headcount needed for breaks). Nothing is invented: a run without the
validator's file has no summary, and the page says so.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from .week import compact as week_compact

DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
VALIDATION = "INDEPENDENT_VALIDATION.json"
DEFAULT_TARGET_RATIO = 0.9
MAX_WINDOWS = 5


def _load(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _hhmm(minutes: int) -> str:
    minutes %= 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _case_dir(results_dir: Path) -> Optional[Path]:
    if not Path(results_dir).is_dir():
        return None
    cases = sorted(p for p in Path(results_dir).iterdir()
                   if p.is_dir() and not p.name.startswith("_") and (p / VALIDATION).is_file())
    return cases[0] if cases else None


def _cell_class(row: dict) -> str:
    if row.get("severe_overage"):
        return "over"
    pct = float(row.get("after_pct", 0))
    if pct + 1e-9 >= 1.0:
        return "covered"
    if pct + 1e-9 >= 0.9:
        return "short"
    return "gap"


def _people(n: float) -> str:
    n = int(n)
    return f"{n} person" if n == 1 else f"{n} people"


def _finding(item: dict, level: str) -> dict:
    """One validator warning or failure as a plain sentence."""
    kind = str(item.get("type", "")).upper()
    examples = item.get("examples") or []
    if kind == "BREAK_CONCURRENCY" and examples:
        e = examples[0]
        text = (f"{e['day']} {e['time']}: {_people(e['on_break'])} on break at the same time; "
                f"the limit is {e['maximum']} ({e['staffed']} on shift).")
        more = int(item.get("count", 1)) - 1
        if more > 0:
            text += f" {more} more half-hour{'s' if more > 1 else ''} like this."
        return {"level": level, "text": text}
    if kind == "WHOLE_WEEK_BALANCE":
        parts = []
        for issue in item.get("issues", []):
            ex = issue.get("examples") or []
            if issue.get("code") == "WHOLE_WEEK_OVERAGE_CAP_EXCEEDED" and ex:
                worst = max(ex, key=lambda x: float(x.get("avoidable_overage_fte", 0)))
                parts.append(f"{issue.get('actual')} half-hours have more people than the over-staffing cap "
                             f"allows, most at {worst['day']} {worst['interval']} ({worst['actual']} on the "
                             f"floor, cap {worst['cap']}).")
            else:
                parts.append(f"{_humanize(issue.get('code', 'balance issue'))}: {issue.get('actual', '')} "
                             f"(allowed {issue.get('maximum', '')}).")
        return {"level": level, "text": " ".join(parts) or "Whole-week balance: see the technical details."}
    if kind == "NEXT_SUNDAY_BALANCE":
        ex = examples[0] if examples else None
        text = (f"Next Sunday (the hours carried into the following week): "
                f"{item.get('overage_cap_violations', 0)} half-hours over the cap")
        text += f", for example {ex['interval']} ({ex['actual']} on the floor, cap {ex['cap']})." if ex else "."
        return {"level": level, "text": text}
    count = item.get("count")
    return {"level": level, "text": f"{_humanize(kind) or 'Validator note'}"
                                    + (f": {count} found" if count is not None else "")
                                    + "; see the technical details."}


def _humanize(code: str) -> str:
    words = str(code).replace("_", " ").strip().lower()
    return words[:1].upper() + words[1:]


def _windows(rows: List[dict], keep, step: int, people_of, key: str) -> List[dict]:
    """Group consecutive half-hours (same day) that match `keep`."""
    out: List[dict] = []
    for day_index, day in enumerate(DAYS):
        current: List[dict] = []
        for row in sorted((r for r in rows if r["day_index"] == day_index), key=lambda r: _minutes(r["interval"])):
            if keep(row) and (not current or _minutes(row["interval"]) - _minutes(current[-1]["interval"]) == step):
                current.append(row)
                continue
            if current:
                out.append(current)
            current = [row] if keep(row) else []
        if current:
            out.append(current)
    windows = []
    for group in out:
        start, last = group[0], group[-1]
        windows.append({
            "day": DAYS[start["day_index"]], "start": start["interval"],
            "end": _hhmm(_minutes(last["interval"]) + step), "half_hours": len(group),
            key: max(people_of(r) for r in group),
            "lowest_pct": int(round(min(float(r.get("after_pct", 0)) for r in group) * 100)),
        })
    windows.sort(key=lambda w: (-w[key], -w["half_hours"]))
    return windows[:MAX_WINDOWS]


def _per_person(row: dict) -> float:
    raw = row.get("after_raw_min") or 0
    return float(row.get("after_effective", 0)) / raw if raw else 1.0


def _staffing(case: Path, rows: List[dict], step: int) -> Optional[dict]:
    audit_file = next(iter(sorted(case.glob("*solver_audit.json"))), None)
    audit = _load(audit_file) if audit_file else None
    cap = (audit or {}).get("capacity_diagnostics")
    if not cap:
        return None
    bench = cap.get("coverage_benchmark") or {}
    status = (_load(case / "UNIVERSAL_RUN_STATUS.json") or {}).get("metrics") or {}
    roster = int(cap.get("roster_count") or 0)
    productive = float(cap.get("productive_hours_available") or 0)
    target = float(cap.get("target_hours_lower_bound") or 0)
    slack = float(cap.get("productive_minus_target_lower_bound", productive - target))
    ratio = float(bench.get("configured_target_ratio") or DEFAULT_TARGET_RATIO)
    adds = {"add_for_target": int(cap.get("estimated_additional_hc_for_aggregate_target") or 0),
            "add_for_floor": int(cap.get("estimated_additional_hc_for_aggregate_floor") or 0),
            "add_for_breaks": int(status.get("additional_headcount_for_breaks") or 0)}
    per_person = round(productive / roster, 1) if roster else 0.0
    release = int(math.floor(slack / per_person)) if per_person and slack > 0 and not any(adds.values()) else 0
    headroom = int(round(slack / target * 100)) if target else 0
    if any(adds.values()):
        most = max(adds.values())
        headline = (f"Estimate: add about {_people(most)} to reach what you requested "
                    f"(the scheduler's own lower-bound estimate).")
    elif release:
        headline = (f"Estimate: about {slack:.0f} spare productive hours this week ({headroom}% above the need), "
                    f"about {_people(release)}'s week at {per_person:g} h each. The same demand could be met "
                    f"with up to {release} fewer, if shifts, days off and languages allow.")
    else:
        headline = "Estimate: staffing matches the need closely; no headcount change suggested."
    short = _windows(rows, lambda r: float(r.get("after_pct", 0)) + 1e-9 < ratio, step,
                     lambda r: max(1, math.ceil((float(r.get("required", 0)) * ratio
                                                 - float(r.get("after_effective", 0))) / _per_person(r) - 1e-9)), "people_short")
    over = _windows(rows, lambda r: bool(r.get("severe_overage")), step,
                    lambda r: int(math.floor(float(r.get("avoidable_overage_fte", 0)) / _per_person(r) + 1e-9)), "people_over")
    return dict(roster=roster, productive_hours=productive, target_hours=target, slack_hours=slack,
                headroom_pct=headroom, target_ratio=ratio, per_person_hours=per_person,
                release_estimate=release, headline=headline, short_windows=short, over_windows=over,
                **adds, **{"class": str(bench.get("capacity_class") or "")})


TARGET_STEPS = (100, 95, 90, 85, 80)
CAUSES = (
    ("capacity", "Not enough people can work then"),
    ("breaks", "Breaks take it below 100%"),
    ("weekly_hours", "Not enough weekly hours overall"),
    ("rules", "Shift patterns and rules keep people elsewhere"),
)


def _audit(case: Path) -> dict:
    audit_file = next(iter(sorted(case.glob("*solver_audit.json"))), None)
    return ((_load(audit_file) if audit_file else None) or {}).get("capacity_diagnostics") or {}


def _analyses(rows: List[dict], step: int, cap: dict) -> Dict[str, Any]:
    """What-if targets, schedule efficiency, per-day coverage and the causes
    of every half-hour below 100% after breaks, from the validator's rows and
    the engine's own per-half-hour capacity bound."""
    pct = lambda r, key: float(r.get(key, 0)) + 1e-9
    targets = [{"pct": t, "after": sum(pct(r, "after_pct") >= t / 100 for r in rows),
                "before": sum(pct(r, "before_pct") >= t / 100 for r in rows)} for t in TARGET_STEPS]
    hours = step / 60.0
    required = sum(float(r.get("required", 0)) for r in rows) * hours
    under = sum(max(0.0, float(r.get("required", 0)) - float(r.get("after_effective", 0))) for r in rows) * hours
    over = sum(max(0.0, float(r.get("after_effective", 0)) - float(r.get("required", 0))) for r in rows) * hours
    efficiency = {"pct": max(0, int(round((1 - (under + over) / required) * 100))) if required else None,
                  "under_hours": round(under, 1), "over_hours": round(over, 1)}
    day_coverage = []
    for index, day in enumerate(DAYS):
        mine = [r for r in rows if int(r["day_index"]) == index]
        day_coverage.append({
            "day": day,
            "after_pct": int(round(100 * sum(pct(r, "after_pct") >= 1 for r in mine) / len(mine))) if mine else None,
            "before_pct": int(round(100 * sum(pct(r, "before_pct") >= 1 for r in mine) / len(mine))) if mine else None})
    bounds = {(b.get("day"), b.get("time")): b for b in cap.get("interval_capacity_upper_bounds") or []}
    weekly_short = float(cap.get("productive_minus_target_lower_bound", 0) or 0) < 0
    found: Dict[str, List[str]] = {key: [] for key, _ in CAUSES}
    for r in sorted(rows, key=lambda r: (int(r["day_index"]), _minutes(r["interval"]))):
        if pct(r, "after_pct") >= 1:
            continue
        where = f"{DAYS[int(r['day_index'])]} {r['interval']}"
        bound = bounds.get((DAYS[int(r["day_index"])], r["interval"]))
        cause = "rules"
        if bound is not None:
            shrink = float(bound.get("shrinkage", 0) or 0)
            need = math.ceil(float(r.get("required", 0)) / max(1e-9, 1 - shrink) - 1e-9)
            if int(bound.get("maximum_possible_raw_min", need)) < need:
                cause = "capacity"
        if cause == "rules" and pct(r, "before_pct") >= 1:
            cause = "breaks"
        elif cause == "rules" and weekly_short:
            cause = "weekly_hours"
        found[cause].append(where)
    restrictions = {"total": sum(len(v) for v in found.values()),
                    "causes": [{"key": key, "label": label, "count": len(found[key]), "examples": found[key][:4]}
                               for key, label in CAUSES]}
    short_cells = [f"{DAYS[int(r['day_index'])]} {r['interval']}" for r in rows if pct(r, "after_pct") < 1]
    return {"targets": targets, "efficiency": efficiency, "day_coverage": day_coverage,
            "restrictions": restrictions, "short_cells": short_cells}


def metrics(summary: Dict[str, Any]) -> Dict[str, Any]:
    """The compact, names-free figures kept on the run row (they outlive the
    run's files, which are deleted after 30 days)."""
    n, st = summary["numbers"], summary.get("staffing") or {}
    before = {t["pct"]: t["before"] for t in summary.get("targets", [])}
    return {
        "interval_minutes": summary["interval_minutes"], "active": n["active"],
        "fully_covered": n["fully_covered"], "at_90": n["at_90"], "floor_gaps": n["floor_gaps"],
        "losses_from_breaks": n["losses_from_breaks"], "before_full": before.get(100), "before_90": before.get(90),
        "associates": st.get("roster"), "productive_hours": st.get("productive_hours"),
        "target_hours": st.get("target_hours"), "slack_hours": st.get("slack_hours"),
        "headroom_pct": st.get("headroom_pct"), "capacity_class": st.get("class"),
        "add_for_target": st.get("add_for_target"), "add_for_floor": st.get("add_for_floor"),
        "add_for_breaks": st.get("add_for_breaks"), "release_estimate": st.get("release_estimate"),
        "per_person_hours": st.get("per_person_hours"), "target_ratio": st.get("target_ratio"),
        "short_windows": st.get("short_windows", []), "over_windows": st.get("over_windows", []),
        "efficiency": summary.get("efficiency"), "targets": summary.get("targets"),
        "day_coverage": summary.get("day_coverage"), "restrictions": summary.get("restrictions"),
        "short_cells": summary.get("short_cells", []), "findings": len(summary.get("findings", [])),
        "hard_fail_count": summary.get("hard_fail_count", 0),
        "intervals": summary.get("intervals", []),  # counts and times per interval: the week view
    }


def version_summary(checks: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A kept version's coverage in the run summary's shape (numbers, the week wall), from the validator's figures
    kept with it: its canonical metrics and each interval's counts. A ready schedule has no engine run, so its run
    page and Home read this (Phase S); None without interval figures."""
    rows = checks.get("intervals") or []
    if not rows:
        return None
    starts = sorted({_minutes(r[1]) for r in rows})
    gaps = [b - a for a, b in zip(starts, starts[1:]) if b > a]
    step = min(gaps) if gaps else 30
    if 1440 % step:
        step = 30
    slots = [_hhmm(m) for m in range(0, 1440, step)]
    cells: List[List[Optional[dict]]] = [[None] * len(slots) for _ in DAYS]
    for day, time, required, after_eff, after_raw, before_eff, before_raw, severe in rows:
        if required <= 0:
            continue  # no requirement: drawn as an empty cell, as on the run's own wall
        after, before = after_eff / required, before_eff / required
        pct = int(round(after * 100))
        cells[int(day) % 7][_minutes(time) // step] = {
            "cls": _cell_class({"after_pct": after, "severe_overage": severe}), "pct": pct, "people": after_raw,
            "before_pct": int(round(before * 100)), "before_cls": _cell_class({"after_pct": before}),
            "title": (f"{DAYS[int(day) % 7]} {time}: {pct}% of need, {_people(after_raw)} on the floor "
                      f"(needs {required:g}, has {after_eff:.2g})"),
        }
    m = checks.get("metrics") or {}
    numbers = {"active": int(m.get("active_intervals", len(rows))), "fully_covered": int(m.get("after_100", 0)),
               "at_90": int(m.get("after_90", 0)), "floor_gaps": int(m.get("floor_gap_count", 0)),
               "zero_staffed": int(m.get("zero_staffed_active_quarters", 0)),
               "losses_from_breaks": int(m.get("target_losses_from_breaks", 0))}
    findings = _folded(checks.get("failures") or [], "gap") + _folded(checks.get("warnings") or [], "review")
    return {"interval_minutes": step, "days": DAYS, "slots": slots, "cells": cells, "numbers": numbers,
            "findings": findings, "intervals": rows}


def _folded(items: List[dict], level: str) -> List[dict]:
    """One finding per kind: the validator lists some per shift (a week without breaks is a line per shift)."""
    groups: Dict[str, List[dict]] = {}
    for item in items:
        groups.setdefault(str(item.get("type", "")), []).append(item)
    out = []
    for kind, group in groups.items():
        if kind.upper() == "BREAK_SEGMENT_COUNT_OR_DURATION":
            none = sum(1 for g in group if not g.get("actual"))
            parts = [f"{none} shift{'s have' if none != 1 else ' has'} no breaks yet; Plan breaks adds them inside "
                     "the program's rules."] if none else []
            if len(group) > none:
                other = len(group) - none
                parts.append(f"{other} shift{'s have' if other != 1 else ' has'} breaks that differ from the ones "
                             "their length takes.")
            out.append({"level": "review" if len(group) == none else level, "text": " ".join(parts)})
            continue
        first = _finding(group[0], level)
        if len(group) > 1:
            first["text"] += f" {len(group) - 1} more like this."
        out.append(first)
    return out


def summarize(results_dir: Path) -> Optional[Dict[str, Any]]:
    case = _case_dir(Path(results_dir))
    if case is None:
        return None
    data = _load(case / VALIDATION)
    if not data or not data.get("interval_rows"):
        return None
    rows = data["interval_rows"]
    starts = sorted({_minutes(r["interval"]) for r in rows})
    gaps = [b - a for a, b in zip(starts, starts[1:]) if b > a]
    step = min(gaps) if gaps else 30
    if 1440 % step:
        step = 30
    slots = [_hhmm(m) for m in range(0, 1440, step)]
    cells: List[List[Optional[dict]]] = [[None] * len(slots) for _ in DAYS]
    for row in rows:
        pct = int(round(float(row.get("after_pct", 0)) * 100))
        people = int(row.get("after_raw_min") or 0)
        cells[int(row["day_index"])][_minutes(row["interval"]) // step] = {
            "cls": _cell_class(row), "pct": pct, "people": people,
            "before_pct": int(round(float(row.get("before_pct", 0)) * 100)),
            "before_cls": _cell_class({"after_pct": row.get("before_pct", 0)}),
            "title": (f"{DAYS[int(row['day_index'])]} {row['interval']}: {pct}% of need after breaks, "
                      f"{_people(people)} on the floor (needs {float(row.get('required', 0)):g}, "
                      f"has {float(row.get('after_effective', 0)):.2g})"),
        }
    m = data.get("canonical_metrics") or {}
    numbers = {"active": int(m.get("active_intervals", len(rows))), "fully_covered": int(m.get("after_100", 0)),
               "at_90": int(m.get("after_90", 0)), "floor_gaps": int(m.get("floor_gap_count", 0)),
               "zero_staffed": int(m.get("zero_staffed_active_quarters", 0)),
               "losses_from_breaks": int(m.get("target_losses_from_breaks", 0))}
    findings = [_finding(f, "gap") for f in data.get("failures") or []]
    findings += [_finding(w, "review") for w in data.get("warnings") or []]
    return {"case": case.name, "interval_minutes": step, "days": DAYS, "slots": slots, "cells": cells,
            "numbers": numbers, "findings": findings, "hard_fail_count": int(data.get("hard_fail_count", 0)),
            "staffing": _staffing(case, rows, step), **_analyses(rows, step, _audit(case)),
            "intervals": week_compact(rows)}
