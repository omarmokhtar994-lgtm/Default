# © 2026 Omar Mokhtar. All rights reserved.
"""Correcting a run's details (program, schedule week, who submitted it, workbook name), and
renaming or merging a program.

A run's schedule versions carry its program and week, so they move with it. What
a change would do is worked out before it is made: a version that stops being in
use because the week it moves to already uses another, and day records (kept by
program and date) that stay where they are while the schedule they are read
against changes. Every change is kept in the record with who, when and why."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .attendance import pick_version

FIELDS = {"program": "Program", "week_start": "Schedule starts", "user_id": "Submitted by", "workbook": "Workbook"}


PICK_UNIT = "Pick a program and LOB set up under LOBs and defaults."


def unit_keys(store) -> set:
    """Every program and LOB a run can be filed under: LOB keys, and the keys of programs without LOBs
    (or with runs of their own). People pick these; typed names made stray programs (owner, 2026-10-08)."""
    from .programs import ProgramBook
    book = ProgramBook(store)
    book.sync()
    return {k for p in book.tree() for k in p["units"]}


def _shown(store, key: str, value: Any) -> str:
    if key == "user_id":
        person = store.get_user(value) if value is not None else None
        return person["display_name"] if person else "nobody"
    if key == "week_start" and value:
        return f"{date.fromisoformat(value):%a %d %b %Y}"
    return value or "none"


def _check(store, new: Dict[str, Any]) -> None:
    """Refuse values a run cannot hold (the page cleans what people type; this is the last word)."""
    unknown = set(new) - set(FIELDS)
    if unknown:
        raise ValueError(f"Not a run detail: {', '.join(sorted(unknown))}.")
    if len(new.get("program") or "") > 80:
        raise ValueError("Keep the program name to 80 characters.")
    week = new.get("week_start")
    if week:  # the schedule's first date: any weekday (Sunday, or Monday for programs starting then)
        try:
            date.fromisoformat(week)
        except ValueError:
            raise ValueError("Pick the date the schedule starts.") from None
    if "user_id" in new and store.get_user(new["user_id"]) is None:
        raise ValueError("Pick someone on the team.")
    if "workbook" in new and not (1 <= len((new["workbook"] or "").strip()) <= 120):
        raise ValueError("Give the workbook a name (up to 120 characters).")


def _week_records(store, program: str, week: str) -> Dict[str, int]:
    if not (program and week):
        return {}
    end = (date.fromisoformat(week) + timedelta(days=6)).isoformat()
    return store.day_record_counts(program, week, end)


def _name(store, version: Optional[Dict[str, Any]]) -> Optional[str]:
    if version is None:
        return None
    run = store.get_run(version["run_id"])
    return f"{version['label']} of {run['workbook']}" if run else version["label"]


def _read_from(store, program: str, day: date, drop_run: str = "", add: List[Dict[str, Any]] = ()):
    """The version ``day`` is read from, without the versions of ``drop_run`` and with ``add`` (moved ones)."""
    versions = [v for v in store.list_schedules(program=program, covering=day.isoformat()) if v["run_id"] != drop_run]
    versions += [v for v in add if v["program"] == program and v["week_start"]
                 and 0 <= (day - date.fromisoformat(v["week_start"])).days <= 6]
    return pick_version(versions)[0]


def _days_changed(store, program: str, first: str, run_id: str, moved: List[Dict[str, Any]]) -> Dict[str, Any]:
    """For the seven days from ``first``: day records held, and whether any day holding records would be
    read from another version once the run has moved."""
    found = {"records": _week_records(store, program, first), "affected": False, "before": None, "after": None}
    for n in range(7):
        day = date.fromisoformat(first) + timedelta(days=n)
        before = _read_from(store, program, day)
        after = _read_from(store, program, day, drop_run=run_id, add=moved)
        if n == 0:
            found["before"], found["after"] = _name(store, before), _name(store, after)
        if (before or {}).get("id") != (after or {}).get("id") and \
                any(store.day_record_counts(program, day.isoformat(), day.isoformat()).values()):
            found["affected"] = True
    return found


def preview_run_change(store, run: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """What changing ``run`` to ``new`` would do, without doing it."""
    _check(store, new)
    changed = {k: v for k, v in new.items() if v != run.get(k)}
    changes = [(FIELDS[k], _shown(store, k, run.get(k)), _shown(store, k, changed[k])) for k in FIELDS if k in changed]
    old_p, old_w = run.get("program") or "", run.get("week_start") or ""
    new_p, new_w = changed.get("program", old_p), changed.get("week_start", old_w)
    found = {"changes": changes, "changed": changed, "stop_in_use": [], "kept_by_target": None,
             "old_records": {}, "old_week_after": None, "old_affected": False,
             "target_records": {}, "target_before": None, "target_after": None, "target_affected": False,
             "old": (old_p, old_w), "new": (new_p, new_w)}
    if "program" in changed or "week_start" in changed:
        mine = store.list_schedules(run_id=run["id"])
        others = [v for v in store.list_schedules(program=new_p, week_start=new_w) if v["run_id"] != run["id"]] \
            if new_p and new_w else []
        target = next((v for v in others if v["in_use"]), None)
        if target is not None:
            found["stop_in_use"] = [{"id": v["id"], "label": v["label"]} for v in mine if v["in_use"]]
            found["kept_by_target"] = target["label"] if found["stop_in_use"] else None
        stopped = {s["id"] for s in found["stop_in_use"]}
        moved = [{**v, "program": new_p, "week_start": new_w, "in_use": 0 if v["id"] in stopped else v["in_use"]}
                 for v in mine]
        if old_p and old_w:
            old = _days_changed(store, old_p, old_w, run["id"], moved)
            found["old_records"], found["old_week_after"], found["old_affected"] = \
                old["records"], old["after"], old["affected"]
        if new_p and new_w:
            target_days = _days_changed(store, new_p, new_w, run["id"], moved)
            found["target_records"], found["target_affected"] = target_days["records"], target_days["affected"]
            found["target_before"], found["target_after"] = target_days["before"], target_days["after"]
    found["needs_check"] = bool(found["stop_in_use"] or found["old_affected"] or found["target_affected"])
    return found


def apply_run_change(store, run: Dict[str, Any], new: Dict[str, Any], user_id: int, reason: str) -> Dict[str, Any]:
    """Make the change previewed for ``new`` and keep it in the record; the preview it applied."""
    found = preview_run_change(store, run, new)
    if not found["changes"]:
        raise ValueError("Nothing to change: the details are the same.")
    store.move_run(run["id"], found["changed"], [s["id"] for s in found["stop_in_use"]])
    said: List[str] = [f"{label}: {old} → {now}" for label, old, now in found["changes"]]
    said += [f"{s['label']} no longer in use ({found['kept_by_target']} kept)" for s in found["stop_in_use"]]
    if (reason or "").strip():
        said.append(f"Reason: {reason.strip()}")
    new_p, new_w = found["new"]
    store.add_event(kind="run_details_changed", user_id=user_id, program=new_p, week_start=new_w, run_id=run["id"],
                    subject=found["changed"].get("workbook", run.get("workbook") or ""), detail="; ".join(said))
    return found


def preview_rename(store, old: str, new: str) -> Dict[str, Any]:
    """What renaming program ``old`` to ``new`` would do (a merge when ``new`` is already a program)."""
    new = " ".join((new or "").split())
    if not new:
        raise ValueError("Give the new program name.")
    if len(new) > 80:
        raise ValueError("Keep the program name to 80 characters.")
    if new == old:
        raise ValueError("That is already its name.")
    runs = [r for r in store.list_runs(limit=1000000) if r["program"] == old]
    if not runs:
        raise ValueError(f"There is no program called {old}.")
    versions = store.list_schedules(program=old)
    theirs = {v["week_start"]: v for v in store.list_schedules(program=new) if v["in_use"] and v["week_start"]}
    stop = [{"id": v["id"], "week": v["week_start"], "label": v["label"]} for v in versions
            if v["in_use"] and v["week_start"] in theirs]
    clashes = []
    for c in store.program_clashes(old, new):
        day = date.fromisoformat(c["shift_date"]).strftime("%d %b")
        clashes.append(f"both have attendance for {c['associate']} on {day}" if c["what"] == "attendance" else
                       f"both have {c['associate']}'s {c['kind']} moved on {day}")
    return {"old": old, "new": new, "merge": any(r["program"] == new for r in store.list_runs(limit=1000000)),
            "runs": len(runs), "versions": len(versions),
            "records": store.day_record_counts(old, "0000-01-01", "9999-12-31"),
            "stop_in_use": stop, "clashes": clashes}


def apply_rename(store, old: str, new: str, user_id: int, reason: str) -> Dict[str, Any]:
    """Rename (or merge) program ``old`` into ``new`` and keep it in the record; refused on clashing records."""
    found = preview_rename(store, old, new)
    if found["clashes"]:
        raise ValueError("These cannot be merged while " + "; ".join(found["clashes"]) +
                         ". Set one of each back on the day page first.")
    moved = store.rename_program(old, found["new"], [s["id"] for s in found["stop_in_use"]])
    said = [f"{old} → {found['new']}" + (" (merged)" if found["merge"] else ""),
            f"{moved['runs']} runs, {moved['versions']} versions, "
            f"{sum(moved[k] for k in ('attendance', 'breaks', 'activities', 'log'))} day records moved"]
    said += [f"{s['label']} for the week of {s['week']} no longer in use" for s in found["stop_in_use"]]
    if (reason or "").strip():
        said.append(f"Reason: {reason.strip()}")
    store.add_event(kind="program_renamed", user_id=user_id, program=found["new"], subject=old, detail="; ".join(said))
    return found
