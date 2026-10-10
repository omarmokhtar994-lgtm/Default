# © 2026 Omar Mokhtar. All rights reserved.
"""Schedule versions: the tool's own schedules and the edits made to them.

When a run finishes, its schedules (after breaks, and before breaks when there
is one) and its input workbook are copied under DATA_DIR/schedules/<run>/, so
they outlive the run's own files (deleted after 30 days) and can still be
edited, checked and downloaded. They are kept 13 months after their week.

An edit never touches a tool version or the version in use: it lands in a
draft (copied first when needed). Every edit is checked by the independent
validator and logged with who, when, what and why, and the severity of what
it added.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import shutil
import tempfile
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .versions import (DAYS, added, apply_change, channel_blocks, marks, problems, read_week, shift_span, swap_slots,
                       validate, write_breaks, write_channels)

KEEP_DAYS = 395  # 13 months after the schedule's week (owner, 2026-10-08)
EGYPT = timezone(timedelta(hours=3))
RANK = {"ok": 0, "yellow": 1, "red": 2}
WEEK = "Week"  # the change log's day for a slot swap


def _working_cells(week: Dict[str, Any]) -> Set[Tuple[str, str]]:
    """Every (person, day) with a shift in a week."""
    return {(a["name"], DAYS[i]) for a in week.get("associates", []) for i, v in enumerate(a["days"]) if shift_span(v)}


def not_worse(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    """Phase W's rule for breaks planned again (fixed before measuring, accepted by the owner): the new version is
    put in use only when it fully covers at least as many intervals after breaks and breaks no more rules."""
    return after["covered"] >= before["covered"] and after["broken"] <= before["broken"]


def worst(found: List[Dict[str, Any]]) -> str:
    return max((p["severity"] for p in found), key=RANK.get, default="ok")


def group_changes(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """A version's change log as saves (Phase Z): consecutive changes by one person, each within 2 seconds of the one
    before (Phase AC: a save written over several seconds stays one save), with the same reason and the same problems,
    are one save. A save's warning belongs to the save, so it is said once (it used to be copied onto each of a break
    plan's 184 lines)."""
    groups: List[Dict[str, Any]] = []
    for c in changes:
        last = groups[-1] if groups else None
        if last and last["user_id"] == c.get("user_id") and abs(c["at"] - last["items"][-1]["at"]) <= 2 \
                and last["reason"] == (c.get("reason") or "") and last["raw_problems"] == (c.get("problems") or "[]"):
            last["items"].append(c)
            continue
        try:
            said = json.loads(c.get("problems") or "[]")
        except ValueError:
            said = []
        groups.append({"at": c["at"], "user_id": c.get("user_id"), "by_name": c.get("by_name"),
                       "reason": c.get("reason") or "", "severity": c.get("severity") or "",
                       "raw_problems": c.get("problems") or "[]", "problems": said if isinstance(said, list) else [],
                       "items": [c]})
    for gr in groups:
        gr["people"] = len({c["associate"] for c in gr["items"]})
    return groups


class ScheduleBook:
    def __init__(self, store, data_dir: Path, package_root: Path):
        self.store = store
        self.root = Path(data_dir) / "schedules"
        self.package_root = Path(package_root)
        self._locks: Dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    # ------------------------------------------------------------- where things are
    def path(self, schedule_id: int) -> Path:
        row = self.store.get_schedule(schedule_id)
        if row is None:
            raise KeyError(schedule_id)
        return self.root / row["file"]

    def input_path(self, run_id: str) -> Path:
        return self.root / run_id / "input.xlsx"

    def channel_path(self, run_id: str) -> Optional[Path]:
        """Where a run's channel needs are read from (Phase Z): the channel needs added to it, else its input
        workbook when its channel tabs ask for someone, else None. The requirement and the inputs stay the input
        workbook's."""
        from .channels import has_channel_needs
        added_needs = self.root / run_id / "channels.xlsx"
        if added_needs.is_file():
            return added_needs
        source = self.input_path(run_id)
        return source if source.is_file() and has_channel_needs(source) else None

    def attach_channels(self, run_id: str, upload: Path) -> List[Tuple[str, str]]:
        """Add channel needs to a run without a new run (Phase Z): read at the run's interval and kept as its
        channels.xlsx, replacing any added before. Refused (ValueError naming the tab and row) when they cannot be
        used; then nothing is kept. Returns what the check says against the requirement tab."""
        from openpyxl.utils.exceptions import InvalidFileException
        from zipfile import BadZipFile

        from .channels import check_lines, has_channel_needs, read_channels
        from .day import read_inputs
        source = self.input_path(run_id)
        if not source.is_file():
            raise ValueError("This schedule's input workbook is missing, so channel needs cannot be added to it.")
        inputs = read_inputs(source)
        step = inputs["interval"]
        with self._lock(run_id):
            fd, name = tempfile.mkstemp(suffix=".xlsx", prefix=".channels-", dir=self.root / run_id)
            os.close(fd)
            trial = Path(name)
            try:
                shutil.copyfile(upload, trial)
                try:
                    setup = read_channels(trial, step)
                except (BadZipFile, InvalidFileException, KeyError, OSError):
                    raise ValueError("This file is not an Excel workbook (.xlsx).") from None
                if setup is None:
                    raise ValueError(f"This workbook has no channel tabs (Chat {step} Min, Phone {step} Min, Email "
                                     f"{step} Min, Email Hours or Channel Setup).")
                if not has_channel_needs(trial):
                    raise ValueError("This workbook asks for nobody on any channel: fill in how many people Chat, "
                                     "Phone or Email need (or Email Hours), then add it again.")
                os.replace(trial, self.root / run_id / "channels.xlsx")
            finally:
                trial.unlink(missing_ok=True)
        return check_lines(setup, inputs, source)

    def _options(self, run_id: str) -> Dict[str, str]:
        run = self.store.get_run(run_id) or {}
        try:
            data = json.loads(run.get("options") or "{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _check(self, run_id: str, schedule: Path) -> Dict[str, Any]:
        return validate(self.input_path(run_id), schedule, self.package_root, self._options(run_id))

    # ------------------------------------------------------------- versions
    def ensure(self, run: Dict[str, Any], input_path: Optional[Path], after_path: Optional[Path],
               before_path: Optional[Path]) -> List[Dict[str, Any]]:
        """Copy a finished run's schedules in as the tool's versions (once)."""
        with self._lock(run["id"]):
            existing = self.store.list_schedules(run_id=run["id"])
            if existing or input_path is None or not Path(input_path).is_file():
                return existing
            folder = self.root / run["id"]
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(input_path, self.input_path(run["id"]))
            number = 1
            for kind, label, source, name in (("tool_after", "Tool, after breaks", after_path, "tool_after.xlsx"),
                                              ("tool_before", "Tool, before breaks", before_path, "tool_before.xlsx")):
                if not source or not Path(source).is_file():
                    continue
                target = folder / name
                shutil.copyfile(source, target)
                week = read_week(target)
                result = self._check(run["id"], target)
                result["problems"] = problems(result, settings=week["settings"])
                self.store.add_schedule(run_id=run["id"], program=run.get("program") or "",
                                        week_start=run.get("week_start") or "", kind=kind, number=number, label=label,
                                        file=f"{run['id']}/{name}", week=json.dumps(week), checks=json.dumps(result))
                number += 1
            return self.store.list_schedules(run_id=run["id"])

    def ensure_ready(self, run: Dict[str, Any], input_path: Path) -> List[Dict[str, Any]]:
        """A ready schedule's workbook kept as the run's version 1 (kind "ready"); checked like any other."""
        with self._lock(run["id"]):
            existing = self.store.list_schedules(run_id=run["id"])
            if existing:
                return existing
            folder = self.root / run["id"]
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(input_path, self.input_path(run["id"]))
            target = folder / "ready.xlsx"
            shutil.copyfile(input_path, target)
            week = read_week(target)
            result = self._check(run["id"], target)
            result["problems"] = problems(result, _working_cells(week), week["settings"])
            self.store.add_schedule(run_id=run["id"], program=run.get("program") or "",
                                    week_start=run.get("week_start") or "", kind="ready", number=1,
                                    label="Ready schedule (uploaded)", file=f"{run['id']}/ready.xlsx",
                                    week=json.dumps(week), checks=json.dumps(result))
            return self.store.list_schedules(run_id=run["id"])

    def versions(self, run_id: str) -> List[Dict[str, Any]]:
        return self.store.list_schedules(run_id=run_id)

    def week_list(self, program: str, week_start: str) -> List[Dict[str, Any]]:
        """Every schedule (run) kept for one program and week (Phase Z: "i cant find the one was not used"), the one
        in use first, then the newest: its run, the version shown (the one in use, else its newest), how many versions
        it has, whether it is in use, intervals fully covered after breaks of the version shown, and whether that
        version has breaks. Empty without a program or a week."""
        if not program or not week_start:
            return []
        by_run: Dict[str, List[Dict[str, Any]]] = {}
        for v in self.store.list_schedules(program=program, week_start=week_start):
            by_run.setdefault(v["run_id"], []).append(v)
        out = []
        for run_id, versions in by_run.items():
            in_use = next((v for v in versions if v["in_use"]), None)
            shown = in_use or max(versions, key=lambda v: (v["kind"] != "tool_before", v["created"], v["id"]))
            metrics = json.loads(shown["checks"] or "{}").get("metrics") or {}
            out.append({"run": self.store.get_run(run_id) or {"id": run_id, "workbook": run_id, "created": 0},
                        "shown": shown, "count": len(versions), "in_use": in_use is not None,
                        "covered": (metrics.get("after_100") or 0, metrics["active_intervals"])
                        if metrics.get("active_intervals") else None,
                        "has_breaks": bool(json.loads(shown["week"] or "{}").get("breaks"))})
        out.sort(key=lambda e: (not e["in_use"], -(e["run"].get("created") or 0)))
        return out

    def delete_run(self, run_id: str) -> int:
        """Delete a schedule (run) that is not in use, with its versions and its kept files (Phase AA). Refused
        (ValueError) while one of its versions is the one in use for its week. Returns how many versions went."""
        with self._lock(run_id):
            if any(v["in_use"] for v in self.store.list_schedules(run_id=run_id)):
                workbook = (self.store.get_run(run_id) or {}).get("workbook") or "This schedule"
                raise ValueError(f"{workbook} is the schedule in use for the week, so it cannot be deleted. Set "
                                 "another schedule in use first.")
            count = self.store.delete_run(run_id)
            shutil.rmtree(self.root / run_id, ignore_errors=True)
        return count

    def kept_weeks(self, program: str) -> List[Dict[str, Any]]:
        """The weeks with a kept schedule for ``program``, oldest first, each with how many schedules (runs) it has
        (Phase AA: the Schedules page's week picker)."""
        runs: Dict[str, Set[str]] = {}
        for v in self.store.list_schedules(program=program):
            if v["week_start"]:
                runs.setdefault(v["week_start"], set()).add(v["run_id"])
        return [{"week": week, "count": len(ids)} for week, ids in sorted(runs.items())]

    def week_compare(self, program: str, week_start: str) -> List[Dict[str, Any]]:
        """The week's schedules side by side (Phase AA, approved sample 03): each ``week_list`` entry with the figures
        its week view already works out (after breaks), where its channel needs come from, and which figures are the
        better ones. "Better" is marked only when every schedule has its breaks planned and its figures: a schedule
        without breaks always looks better than it will be."""
        from .week import view as week_view
        entries = self.week_list(program, week_start)
        for e in entries:
            intervals = json.loads(e["shown"]["checks"] or "{}").get("intervals") or []
            seen = week_view(intervals, "after") if intervals else None
            t = seen["totals"] if seen else None
            e["figures"] = {"full": t["full"], "active": t["active"], "overtime": t["overtime_hours"],
                            "extra": t["extra_hours"], "step": seen["step"]} if t else None
            path = self.channel_path(e["run"]["id"])
            e["channels"] = None if path is None else ("added" if path.name == "channels.xlsx" else "workbook")
            e["channels_at"] = path.stat().st_mtime if e["channels"] == "added" else None
            e["better"] = set()
        if len(entries) > 1 and all(e["has_breaks"] and e["figures"] for e in entries):
            for key, best in (("full", max), ("overtime", min), ("extra", max)):
                values = [e["figures"][key] for e in entries]
                if len(set(values)) > 1:
                    for e in entries:
                        if e["figures"][key] == best(values):
                            e["better"].add(key)
        return entries

    def in_use(self, program: str, week_start: str) -> Optional[Dict[str, Any]]:
        return next((v for v in self.store.list_schedules(program=program, week_start=week_start) if v["in_use"]), None)

    def lineage(self, schedule_id: int) -> List[Dict[str, Any]]:
        """This version and the versions it was copied from, newest first."""
        out, seen = [], set()
        row = self.store.get_schedule(schedule_id)
        while row is not None and row["id"] not in seen:
            seen.add(row["id"])
            out.append(row)
            row = self.store.get_schedule(row["base_id"]) if row["base_id"] else None
        return out

    def edited_cells(self, schedule_id: int) -> Set[Tuple[str, str]]:
        cells: Set[Tuple[str, str]] = set()
        lineage = self.lineage(schedule_id)
        if lineage and lineage[-1]["kind"] == "ready":  # its breaks are planned on the website, so every
            cells |= _working_cells(json.loads(lineage[-1]["week"] or "{}"))  # missing one is "planned next"
        for row in lineage:
            for c in self.store.list_changes(row["id"]):  # a slot swap ("Week") changes all seven days
                cells |= {(c["associate"], d) for d in (DAYS if c["day"] == WEEK else [c["day"]])}
        return cells

    def _problems(self, row: Dict[str, Any], edited: Set[Tuple[str, str]]) -> List[Dict[str, Any]]:
        settings = json.loads(row["week"] or "{}").get("settings") or {}
        return problems(json.loads(row["checks"] or "{}"), edited, settings)

    def view(self, schedule_id: int) -> Dict[str, Any]:
        """A version with its problems, what its edits added over the tool's version, and marks."""
        row = self.store.get_schedule(schedule_id)
        edited = self.edited_cells(schedule_id)
        found = self._problems(row, edited)
        tool = self.lineage(schedule_id)[-1]
        base = self._problems(tool, edited) if tool["id"] != row["id"] else found
        new = added(base, found) if tool["id"] != row["id"] else []
        keys = {p["key"] for p in new}
        tool_days = {a["name"]: a["days"] for a in json.loads(tool["week"] or "{}").get("associates", [])}
        return {"row": row, "week": json.loads(row["week"] or "{}"), "problems": found, "added": new,
                "inherited": [p for p in found if p["key"] not in keys], "tool_days": tool_days, "tool": tool,
                "marks": marks(new, edited=edited), "edited": sorted(edited),
                "metrics": json.loads(row["checks"] or "{}").get("metrics") or {},
                "changes": [c for r in reversed(self.lineage(schedule_id)) for c in self.store.list_changes(r["id"])],
                "uploaded": tool["kind"] == "ready"}

    def _trial(self, schedule_id: int, edit, cells: Set[Tuple[str, str]]) -> Dict[str, Any]:
        """What an edit would add, checked on a copy (nothing is saved)."""
        row = self.store.get_schedule(schedule_id)
        edited = self.edited_cells(schedule_id) | cells
        with tempfile.TemporaryDirectory() as tmp:
            trial = Path(tmp) / "trial.xlsx"
            edit(self.path(schedule_id), trial)
            result = self._check(row["run_id"], trial)
        settings = json.loads(row["week"] or "{}").get("settings") or {}
        now = problems(result, edited, settings)
        new = added(self._problems(row, edited), now)
        return {"added": new, "severity": worst(new), "problems": now, "metrics": result.get("metrics") or {}}

    def check(self, schedule_id: int, name: str, day: str, value: str) -> Dict[str, Any]:
        """What one change would add."""
        return self._trial(schedule_id, lambda src, dst: apply_change(src, dst, name, day, value), {(name, day)})

    def check_swap(self, schedule_id: int, first: str, second: str) -> Dict[str, Any]:
        """What two people swapping slots would add."""
        return self._trial(schedule_id, lambda src, dst: swap_slots(src, dst, first, second),
                           {(n, d) for n in (first, second) for d in DAYS})

    def _draft_from(self, row: Dict[str, Any], user_id: int, label: Optional[str] = None) -> Dict[str, Any]:
        number = max(v["number"] for v in self.store.list_schedules(run_id=row["run_id"])) + 1
        user = self.store.get_user(user_id) or {}
        name = f"v{number}.xlsx"
        shutil.copyfile(self.root / row["file"], self.root / row["run_id"] / name)
        new_id = self.store.add_schedule(run_id=row["run_id"], program=row["program"], week_start=row["week_start"],
                                         kind="edited", number=number,
                                         label=f"Version {number}: " + (label or f"{user.get('display_name', 'someone')}'s edit"),
                                         base_id=row["id"], user_id=user_id, file=f"{row['run_id']}/{name}",
                                         week=row["week"], checks=row["checks"])
        made = self.store.get_schedule(new_id)
        self.store.add_event(kind="version_created", user_id=user_id, program=row["program"],
                             week_start=row["week_start"], run_id=row["run_id"], schedule_id=new_id,
                             subject=made["label"], detail=f"copied from {row['label']}")
        return made

    def _save(self, row: Dict[str, Any], user_id: int, edit, cells: Set[Tuple[str, str]], fresh: bool = False,
              label: Optional[str] = None) -> Tuple[Dict[str, Any], List]:
        """Apply an edit to ``row`` (a new draft unless it is a draft not in use; always a new one when ``fresh``,
        named ``label``), re-check it and return the version saved in and what the edit added. The caller holds the
        run's lock."""
        with tempfile.TemporaryDirectory() as tmp:  # a refused edit (ValueError) must not leave an empty draft
            edit(self.root / row["file"], Path(tmp) / "trial.xlsx")
        if fresh or row["kind"] != "edited" or row["in_use"]:
            row = self._draft_from(row, user_id, label)
        target = self.root / row["file"]
        edited = self.edited_cells(row["id"]) | cells
        before = self._problems(row, edited)
        fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=str(target.parent))
        os.close(fd)
        try:
            edit(target, Path(tmp))
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        week = read_week(target)
        result = self._check(row["run_id"], target)
        result["problems"] = problems(result, edited, week["settings"])
        self.store.update_schedule(row["id"], week=json.dumps(week), checks=json.dumps(result), updated=time.time())
        return row, added(before, result["problems"])

    def change(self, schedule_id: int, user_id: int, name: str, day: str, value: str, reason: str) -> int:
        """Apply one change; returns the version it was saved in (a new draft unless the
        version given is already a draft that is not in use)."""
        first = self.store.get_schedule(schedule_id)
        if first is None:
            raise KeyError(schedule_id)
        with self._lock(first["run_id"]):
            row = self.store.get_schedule(schedule_id)
            old = next((a["days"][DAYS.index(day)] for a in json.loads(row["week"] or "{}").get("associates", [])
                        if a["name"] == name), None) if day in DAYS else None
            if old is not None and old.strip().casefold() == value.strip().casefold():
                return int(row["id"])  # nothing changes, nothing is logged
            row, new = self._save(row, user_id, lambda src, dst: apply_change(src, dst, name, day, value),
                                  {(name, day)})
            self.store.add_change(schedule_id=row["id"], user_id=user_id, associate=name, day=day, old=old or "",
                                  new=value, reason=reason, severity=worst(new),
                                  problems=json.dumps([p["text"] for p in new]))
            return int(row["id"])

    def swap(self, schedule_id: int, user_id: int, first: str, second: str, reason: str) -> int:
        """Two people swap slots (each keeps the other's shifts and breaks); logged once per person."""
        start = self.store.get_schedule(schedule_id)
        if start is None:
            raise KeyError(schedule_id)
        with self._lock(start["run_id"]):
            row = self.store.get_schedule(schedule_id)
            slot = {a["name"]: a.get("slot") or "?" for a in json.loads(row["week"] or "{}").get("associates", [])}
            row, new = self._save(row, user_id, lambda src, dst: swap_slots(src, dst, first, second),
                                  {(n, d) for n in (first, second) for d in DAYS})
            for who, mine, theirs in ((first, slot.get(first), slot.get(second)), (second, slot.get(second), slot.get(first))):
                self.store.add_change(schedule_id=row["id"], user_id=user_id, associate=who, day=WEEK,
                                      old=f"Slot {mine}", new=f"Slot {theirs}", reason=reason, severity=worst(new),
                                      problems=json.dumps([p["text"] for p in new]))
            return int(row["id"])

    # ------------------------------------------------------------- a week's breaks (Phase R)
    def break_rules(self, schedule_id: int) -> Dict[str, Any]:
        """The break rules of a version's workbook, read by the engine's own parser in a subprocess (as the
        validator is) and kept with the run, since every version of a run shares its input."""
        row = self.store.get_schedule(schedule_id)
        cache = self.root / row["run_id"] / "break_rules.json"
        if cache.is_file():
            return json.loads(cache.read_text(encoding="utf-8"))
        cmd = [sys.executable, str(Path(__file__).with_name("break_rules_cli.py")), "--input",
               str(self.input_path(row["run_id"])), "--engine",
               str(Path(self.package_root) / "engine" / "_tools" / "l632_universal_scheduler.py")]
        try:
            proc = subprocess.run(cmd, cwd=str(self.package_root), capture_output=True, text=True, timeout=120)
            found = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            detail = (getattr(locals().get("proc"), "stderr", "") or "").strip().splitlines()
            raise ValueError("The break rules could not be read from this schedule's workbook"
                             + (f": {detail[-1]}" if detail else ".")) from None
        cache.write_text(json.dumps(found), encoding="utf-8")
        return found

    def save_breaks(self, schedule_id: int, user_id: int, plan: Dict[str, Dict[str, List[Optional[int]]]],
                    reason: str, use: bool = False, fresh: bool = False,
                    version_label: Optional[str] = None) -> Tuple[int, List[str]]:
        """Write the planned breaks (day -> person -> starts) as a new version (or into a draft not in use),
        checked like any edit; one change row per person and day. Returns the version and what was left out
        (people not working that day), said in plain words. ``use`` also marks the version in use."""
        from .break_plan import hm, slots_for
        first = self.store.get_schedule(schedule_id)
        if first is None:
            raise KeyError(schedule_id)
        rules = self.break_rules(schedule_id)
        left_out: List[str] = []
        with self._lock(first["run_id"]):
            row = self.store.get_schedule(schedule_id)
            week = json.loads(row["week"] or "{}")
            shifts = {a["name"]: a["days"] for a in week.get("associates", [])}
            rows, changes = {}, []
            for day in DAYS:
                for name, starts in sorted((plan.get(day) or {}).items()):
                    if name not in shifts:
                        left_out.append(f"{name}, {day}: not on this schedule, so these breaks were left out.")
                        continue
                    label = shifts[name][DAYS.index(day)]
                    span = shift_span(label)
                    if not span:
                        if any(s is not None for s in starts):
                            left_out.append(f"{name}, {day}: no shift that day ({label}), so these breaks were left out.")
                        continue
                    entries = [(kind, s, minutes) for (kind, minutes), s in zip(slots_for(rules, span[1] - span[0]), starts)
                               if s is not None]
                    old = ", ".join(f"{b['kind']} {b['start']}" for b in week.get("breaks", [])
                                    if b["associate"] == name and b["day"] == day) or "no breaks"
                    new_text = ", ".join(f"{kind} {hm(s)}" for kind, s, _ in entries) or "no breaks"
                    if old != new_text:
                        rows[(name, day)] = (label, entries)
                        changes.append((name, day, old, new_text))
            if not rows:
                return int(row["id"]), left_out
            row, added_now = self._save(row, user_id, lambda src, dst: write_breaks(src, dst, rows), set(rows),
                                        fresh=fresh, label=version_label)
            for name, day, old, new_text in changes:
                self.store.add_change(schedule_id=row["id"], user_id=user_id, associate=name, day=day, old=old,
                                      new=new_text, reason=reason, severity=worst(added_now),
                                      problems=json.dumps([p["text"] for p in added_now]))
        if use:
            self.set_in_use(int(row["id"]), user_id)
        return int(row["id"]), left_out

    def _standing(self, schedule_id: int) -> Dict[str, Any]:
        """A version's figures the re-plan rule compares: intervals fully covered after breaks (of those with
        demand) and rules broken, as its own validator run says."""
        checks = json.loads(self.store.get_schedule(schedule_id)["checks"] or "{}")
        metrics = checks.get("metrics") or {}
        return {"covered": metrics.get("after_100") or 0, "active": metrics.get("active_intervals") or 0,
                "broken": sum(1 for p in checks.get("problems") or [] if p.get("severity") == "red")}

    def auto_breaks(self, schedule_id: int, user_id: int, use: bool) -> Dict[str, Any]:
        """Every break of the week planned at once (Phase W), inside the workbook's break rules: the Plan breaks
        page's Suggest, day after day on the week so far (so last night's breaks are counted). A version without
        breaks is filled; one with breaks has them all planned again. Always a new version (the one clicked on stays
        as it is); ``use`` puts it in use, a re-plan only when ``not_worse``. Returns what happened and a sentence."""
        from .break_plan import suggest, week_with
        from .day import read_inputs
        row = self.store.get_schedule(schedule_id)
        if row is None:
            raise KeyError(schedule_id)
        week = json.loads(row["week"] or "{}")
        rules = self.break_rules(schedule_id)
        inputs = read_inputs(self.input_path(row["run_id"]))
        mode = "replan" if week.get("breaks") else "fill"
        work, plan, placed, empty = week, {}, 0, 0
        for d, day in enumerate(DAYS):
            got = suggest(work, inputs, rules, d, {})
            work = week_with(work, d, got, rules)
            plan[day] = got
            placed += sum(1 for starts in got.values() for s in starts if s is not None)
            empty += sum(1 for starts in got.values() for s in starts if s is None)
        saved, _ = self.save_breaks(schedule_id, user_id, plan, "Breaks planned automatically", use=False,
                                    fresh=True, version_label="breaks planned automatically")
        people = len(week.get("associates", []))
        holes = " none left empty" if not empty else f" {empty} left empty (no time fits the rules; Plan breaks lists them)"
        if saved == schedule_id:  # the same breaks it already has
            if use:
                self.set_in_use(schedule_id, user_id)
            return {"id": schedule_id, "mode": mode, "placed": placed, "empty": empty, "used": bool(use),
                    "said": "The breaks planned automatically are the ones this version already has, so nothing "
                            "changed." + (" It is now the schedule in use for this week." if use else "")}
        made = self.store.get_schedule(saved)
        before, after = self._standing(schedule_id), self._standing(saved)
        used = bool(use) and (mode == "fill" or not_worse(before, after))
        if used:
            self.set_in_use(saved, user_id)
        verb = "Breaks planned automatically" if mode == "fill" else "Breaks planned again"
        said = f"{verb} for 7 days: {placed} breaks placed for {people} people,{holes}. Saved as {made['label']}, "
        if mode == "fill":
            said += "checked by the validator" + (", and in use for this week." if used else ".")
        elif used:
            said += (f"checked by the validator, and in use for this week: it fully covers {after['covered']} of "
                     f"{after['active']} intervals after breaks (before: {before['covered']}).")
        elif use:
            worse = [f"it fully covers {after['covered']} of {after['active']} intervals after breaks against "
                     f"{before['covered']} before"] if after["covered"] < before["covered"] else []
            if after["broken"] > before["broken"]:
                worse.append(f"it breaks {after['broken'] - before['broken']} more rule"
                             f"{'s' if after['broken'] - before['broken'] != 1 else ''}")
            said += ("checked by the validator, but not put in use: " + (" and ".join(worse) or "it is not better")
                     + ". The schedule in use did not change.")
        else:
            said += "checked by the validator."
        if week.get("channels"):
            said += " Channels were planned for the old breaks: open Plan channels to plan them again."
        return {"id": saved, "mode": mode, "placed": placed, "empty": empty, "used": used, "said": said,
                "before": before, "after": after}

    def save_channels(self, schedule_id: int, user_id: int, draft: Dict[str, Dict[str, Any]], reason: str,
                      use: bool = False) -> Tuple[int, List[str]]:
        """Phase V: write the planned channels (and the breaks the plan moved or placed) of each drafted day as a new
        version (or into a draft not in use), checked like any edit; one change row per person, day and kind.
        Returns the version and what was left out (people not working that day), in plain words."""
        from .break_plan import hm, slots_for
        from .channel_page import describe
        first = self.store.get_schedule(schedule_id)
        if first is None:
            raise KeyError(schedule_id)
        rules = self.break_rules(schedule_id)
        left_out: List[str] = []
        with self._lock(first["run_id"]):
            row = self.store.get_schedule(schedule_id)
            week = json.loads(row["week"] or "{}")
            shifts = {a["name"]: a["days"] for a in week.get("associates", [])}
            channel_rows, break_rows, changes = {}, {}, []
            for day in DAYS:
                plan = draft.get(day)
                if not plan:
                    continue
                d = DAYS.index(day)
                for name in sorted(set(plan.get("blocks", {})) | set(plan.get("breaks", {}))):
                    if name not in shifts:
                        left_out.append(f"{name}, {day}: not on this schedule, so this plan was left out.")
                        continue
                    label = shifts[name][d]
                    span = shift_span(label)
                    if not span:
                        left_out.append(f"{name}, {day}: no shift that day ({label}), so this plan was left out.")
                        continue
                    blocks = [(int(a), int(b), x) for a, b, x in plan.get("blocks", {}).get(name, [])]
                    old = [(b["start"], b["end"], b["channel"]) for b in channel_blocks(week, d, name)]
                    rows_now = sum(1 for c in week.get("channels", []) if c["associate"] == name and c["day"] == day)
                    if blocks != old or rows_now != len(old):
                        channel_rows[(name, day)] = (label, blocks)
                        changes.append((name, day, describe(old), describe(blocks)))
                    starts = plan.get("breaks", {}).get(name)
                    if starts is not None:
                        entries = [(kind, s, minutes) for (kind, minutes), s in
                                   zip(slots_for(rules, span[1] - span[0]), starts) if s is not None]
                        was = ", ".join(f"{b['kind']} {b['start']}" for b in week.get("breaks", [])
                                        if b["associate"] == name and b["day"] == day) or "no breaks"
                        now = ", ".join(f"{kind} {hm(s)}" for kind, s, _ in entries) or "no breaks"
                        if was != now:
                            break_rows[(name, day)] = (label, entries)
                            changes.append((name, day, was, now))
            if not channel_rows and not break_rows:
                return int(row["id"]), left_out

            def edit(src: Path, dst: Path) -> None:
                middle = Path(dst).with_name(Path(dst).stem + "_breaks.xlsx")
                try:
                    if break_rows:
                        write_breaks(src, middle, break_rows)
                    write_channels(middle if break_rows else src, dst, channel_rows)
                finally:
                    middle.unlink(missing_ok=True)

            row, added_now = self._save(row, user_id, edit, set(channel_rows) | set(break_rows))
            for name, day, old_text, new_text in changes:
                self.store.add_change(schedule_id=row["id"], user_id=user_id, associate=name, day=day, old=old_text,
                                      new=new_text, reason=reason, severity=worst(added_now),
                                      problems=json.dumps([p["text"] for p in added_now]))
        if use:
            self.set_in_use(int(row["id"]), user_id)
        return int(row["id"]), left_out

    def week_note(self, program: str, week_start: str, unit: str) -> Dict[str, Any]:
        """What a week already has (Phase W): how many schedules (one per run: an upload or an engine run), the
        version in use and its workbook, and a sentence saying so for an upload (empty when there is none)."""
        rows = self.store.list_schedules(program=program, week_start=week_start) if program and week_start else []
        runs = {v["run_id"] for v in rows}
        if not runs:
            return {"count": 0, "in_use": None, "text": ""}
        used = next((v for v in rows if v["in_use"]), None)
        n = len(runs)
        when = f"{date.fromisoformat(week_start):%a %d %b}"
        text = f"{unit} has {n} schedule{'s' if n != 1 else ''} for the week of {when}. "
        if used:
            workbook = (self.store.get_run(used["run_id"]) or {}).get("workbook", "")
            text += f"In use: {used['label']}" + (f" from {workbook}. " if workbook else ". ")
        else:
            text += "None is in use; the RTA reads the newest. "
        text += (f"Yours is kept next to {'them' if n != 1 else 'it'}. The RTA keeps reading the one in use until you "
                 "choose another on the Schedules page.")
        return {"count": n, "in_use": used, "text": text}

    def set_in_use(self, schedule_id: int, user_id: int) -> None:
        row = self.store.get_schedule(schedule_id)
        with self._lock(row["run_id"]):
            scope = (self.store.list_schedules(program=row["program"], week_start=row["week_start"])
                     if row["program"] and row["week_start"] else self.store.list_schedules(run_id=row["run_id"]))
            before = [v["label"] for v in scope if v["in_use"] and v["id"] != schedule_id]
            for v in scope:
                if v["in_use"]:
                    self.store.update_schedule(v["id"], in_use=0)
            self.store.update_schedule(schedule_id, in_use=1)
            self.store.add_event(kind="set_in_use", user_id=user_id, program=row["program"],
                                 week_start=row["week_start"], run_id=row["run_id"], schedule_id=schedule_id,
                                 subject=row["label"], detail=f"instead of {before[0]}" if before else "")

    # ------------------------------------------------------------- retention
    def cleanup(self, now: Optional[float] = None) -> int:
        """Delete versions 13 months after their week (or after they were made, without a week)."""
        now = time.time() if now is None else now
        gone = 0
        for row in self.store.list_schedules():
            try:
                start = datetime.strptime(row["week_start"], "%Y-%m-%d").replace(tzinfo=EGYPT).timestamp()
            except (TypeError, ValueError):
                start = row["created"]
            if now - start <= KEEP_DAYS * 86400:
                continue
            path = self.root / row["file"]
            if path.is_file():
                path.unlink()
            self.store.delete_schedule(row["id"])
            gone += 1
            if not self.store.list_schedules(run_id=row["run_id"]):
                shutil.rmtree(self.root / row["run_id"], ignore_errors=True)
        return gone
