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
import shutil
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .versions import added, apply_change, marks, problems, read_week, validate

KEEP_DAYS = 395  # 13 months after the schedule's week (owner, 2026-10-08)
EGYPT = timezone(timedelta(hours=3))
RANK = {"ok": 0, "yellow": 1, "red": 2}


def worst(found: List[Dict[str, Any]]) -> str:
    return max((p["severity"] for p in found), key=RANK.get, default="ok")


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

    def versions(self, run_id: str) -> List[Dict[str, Any]]:
        return self.store.list_schedules(run_id=run_id)

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
        for row in self.lineage(schedule_id):
            cells |= {(c["associate"], c["day"]) for c in self.store.list_changes(row["id"])}
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
        return {"row": row, "week": json.loads(row["week"] or "{}"), "problems": found, "added": new,
                "marks": marks(new, edited=edited), "edited": sorted(edited),
                "metrics": json.loads(row["checks"] or "{}").get("metrics") or {},
                "changes": [c for r in reversed(self.lineage(schedule_id)) for c in self.store.list_changes(r["id"])]}

    def check(self, schedule_id: int, name: str, day: str, value: str) -> Dict[str, Any]:
        """What one change would add, checked on a copy (nothing is saved)."""
        row = self.store.get_schedule(schedule_id)
        edited = self.edited_cells(schedule_id) | {(name, day)}
        with tempfile.TemporaryDirectory() as tmp:
            trial = Path(tmp) / "trial.xlsx"
            apply_change(self.path(schedule_id), trial, name, day, value)
            result = self._check(row["run_id"], trial)
        settings = json.loads(row["week"] or "{}").get("settings") or {}
        now = problems(result, edited, settings)
        new = added(self._problems(row, edited), now)
        return {"added": new, "severity": worst(new), "problems": now, "metrics": result.get("metrics") or {}}

    def _draft_from(self, row: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        number = max(v["number"] for v in self.store.list_schedules(run_id=row["run_id"])) + 1
        user = self.store.get_user(user_id) or {}
        name = f"v{number}.xlsx"
        shutil.copyfile(self.root / row["file"], self.root / row["run_id"] / name)
        new_id = self.store.add_schedule(run_id=row["run_id"], program=row["program"], week_start=row["week_start"],
                                         kind="edited", number=number,
                                         label=f"Version {number}: {user.get('display_name', 'someone')}'s edit",
                                         base_id=row["id"], user_id=user_id, file=f"{row['run_id']}/{name}",
                                         week=row["week"], checks=row["checks"])
        return self.store.get_schedule(new_id)

    def change(self, schedule_id: int, user_id: int, name: str, day: str, value: str, reason: str) -> int:
        """Apply one change; returns the version it was saved in (a new draft unless the
        version given is already a draft that is not in use)."""
        first = self.store.get_schedule(schedule_id)
        if first is None:
            raise KeyError(schedule_id)
        with self._lock(first["run_id"]):
            row = self.store.get_schedule(schedule_id)
            current = next((a["days"][["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].index(day)]
                            for a in json.loads(row["week"] or "{}").get("associates", []) if a["name"] == name), None)
            if current is not None and current.strip().casefold() == value.strip().casefold():
                return int(row["id"])  # nothing changes, nothing is logged
            if row["kind"] != "edited" or row["in_use"]:
                row = self._draft_from(row, user_id)
            target = self.root / row["file"]
            week = json.loads(row["week"] or "{}")
            old = next((a["days"][["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].index(day)]
                        for a in week.get("associates", []) if a["name"] == name), "")
            edited_before = self.edited_cells(row["id"])
            before = self._problems(row, edited_before | {(name, day)})
            fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=str(target.parent))
            os.close(fd)
            try:
                apply_change(target, Path(tmp), name, day, value)
                os.replace(tmp, target)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            week = read_week(target)
            result = self._check(row["run_id"], target)
            result["problems"] = problems(result, edited_before | {(name, day)}, week["settings"])
            new = added(before, result["problems"])
            self.store.update_schedule(row["id"], week=json.dumps(week), checks=json.dumps(result), updated=time.time())
            self.store.add_change(schedule_id=row["id"], user_id=user_id, associate=name, day=day, old=old, new=value,
                                  reason=reason, severity=worst(new), problems=json.dumps([p["text"] for p in new]))
            return int(row["id"])

    def set_in_use(self, schedule_id: int, user_id: int) -> None:
        row = self.store.get_schedule(schedule_id)
        with self._lock(row["run_id"]):
            scope = (self.store.list_schedules(program=row["program"], week_start=row["week_start"])
                     if row["program"] and row["week_start"] else self.store.list_schedules(run_id=row["run_id"]))
            for v in scope:
                if v["in_use"]:
                    self.store.update_schedule(v["id"], in_use=0)
            self.store.update_schedule(schedule_id, in_use=1)

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
