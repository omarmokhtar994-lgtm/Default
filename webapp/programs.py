# © 2026 Omar Mokhtar. All rights reserved.
"""Programs and their LOBs, and the defaults a new schedule starts from.

Every table keeps its `program` text as the key of a schedule unit: a LOB, or a program without LOBs. This
registry says which program (and LOB) a key belongs to and what to call it. Keys never change, so adopting an
existing name such as "AE/AR B2B" into program AE as LOB "AR B2B" moves no data, and display names can change
freely."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _clean(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("Give it a name.")
    if len(name) > 80:
        raise ValueError("Keep names to 80 characters.")
    return name


class ProgramBook:
    def __init__(self, store):
        self.store = store

    def _claimed(self) -> set:
        return {p["key"] for p in self.store.list_programs()} | {l["key"] for l in self.store.list_lobs()}

    def sync(self) -> int:
        """Register each key runs were made under that no program or LOB claims yet, as a program."""
        claimed, names = self._claimed(), {p["name"] for p in self.store.list_programs()}
        added = 0
        for key in self.store.run_programs():
            if key not in claimed and key not in names:
                self.store.add_program_row(key, key)
                added += 1
        return added

    def tree(self) -> List[Dict[str, Any]]:
        """Programs with their LOBs, defaults and units (the keys their pages open)."""
        lobs: Dict[int, List[Dict[str, Any]]] = {}
        for l in self.store.list_lobs():
            lobs.setdefault(l["program_id"], []).append({"id": l["id"], "name": l["name"], "key": l["key"]})
        with_runs = set(self.store.run_programs())
        out = []
        for p in self.store.list_programs():
            mine = lobs.get(p["id"], [])
            units = [l["key"] for l in mine] + ([p["key"]] if not mine or p["key"] in with_runs else [])
            try:
                options = json.loads(p["options"] or "{}")
            except ValueError:
                options = {}
            out.append({"id": p["id"], "name": p["name"], "key": p["key"], "start_day": p["start_day"],
                        "run_mode": p["run_mode"], "options": options, "saved": bool(p["options"]),
                        "lobs": mine, "units": units})
        return out

    def program(self, program_id: int) -> Dict[str, Any]:
        found = next((p for p in self.tree() if p["id"] == program_id), None)
        if found is None:
            raise ValueError("There is no such program.")
        return found

    def unit(self, key: str) -> Optional[Dict[str, Any]]:
        """The program and LOB of a key, and its name: "AE, AR B2B", or "NMG" for a program without LOBs."""
        for p in self.tree():
            for l in p["lobs"]:
                if l["key"] == key:
                    return {"key": key, "program": p, "lob": l, "label": f"{p['name']}, {l['name']}"}
            if p["key"] == key:
                return {"key": key, "program": p, "lob": None, "label": p["name"]}
        return None

    def label(self, key: str) -> str:
        found = self.unit(key)
        return found["label"] if found else key

    def add_program(self, name: str) -> int:
        name = _clean(name)
        if any(p["name"].casefold() == name.casefold() for p in self.store.list_programs()) or name in self._claimed():
            raise ValueError(f"There is already a program called {name}.")
        return self.store.add_program_row(name, name)

    def add_lob(self, program_id: int, name: str) -> str:
        """A new LOB; its key is "<program> <LOB>"."""
        program, name = self.program(program_id), _clean(name)
        if any(l["name"].casefold() == name.casefold() for l in program["lobs"]):
            raise ValueError(f"{program['name']} already has a LOB called {name}.")
        key = f"{program['name']} {name}"
        if key in self._claimed() or key in self.store.run_programs():
            raise ValueError(f"The name {key} is already used; pick another LOB name.")
        self.store.add_lob_row(program_id, name, key)
        return key

    def adopt(self, key: str, program_id: int, lob_name: str) -> None:
        """An existing key (a program without LOBs so far) becomes a LOB of another program; no data moves."""
        target, lob_name = self.program(program_id), _clean(lob_name)
        if any(l["key"] == key for l in self.store.list_lobs()):
            raise ValueError(f"{key} is already a LOB.")
        bare = next((p for p in self.tree() if p["key"] == key), None)
        if bare is not None and bare["id"] == program_id:
            raise ValueError("Pick another program to put it in.")
        if bare is not None and bare["lobs"]:
            raise ValueError(f"{bare['name']} has LOBs of its own; move those first.")
        if bare is None and key not in self.store.run_programs():
            raise ValueError(f"There is nothing called {key}.")
        if any(l["name"].casefold() == lob_name.casefold() for l in target["lobs"]):
            raise ValueError(f"{target['name']} already has a LOB called {lob_name}.")
        if bare is not None:
            self.store.fold_program(bare["id"], program_id)
        self.store.add_lob_row(program_id, lob_name, key)

    def set_defaults(self, program_id: int, start_day: int, run_mode: str, options: Dict[str, Any]) -> None:
        from .runs import MODES
        self.program(program_id)
        if start_day not in range(7):
            raise ValueError("Pick the day schedules start on.")
        if run_mode not in MODES:
            raise ValueError("Pick a run length.")
        self.store.update_program(program_id, start_day=start_day, run_mode=run_mode,
                                  options=json.dumps(options or {}, sort_keys=True))

    def rename(self, program_id: Optional[int], lob_id: Optional[int], name: str) -> None:
        """New display names; keys stay as they are."""
        name = _clean(name)
        if lob_id is not None:
            lob = next((l for l in self.store.list_lobs() if l["id"] == lob_id), None)
            if lob is None:
                raise ValueError("There is no such LOB.")
            if any(l["name"].casefold() == name.casefold() and l["id"] != lob_id
                   for l in self.program(lob["program_id"])["lobs"]):
                raise ValueError(f"There is already a LOB called {name} there.")
            self.store.rename_lob(lob_id, name)
            return
        self.program(program_id)
        if any(p["name"].casefold() == name.casefold() and p["id"] != program_id for p in self.store.list_programs()):
            raise ValueError(f"There is already a program called {name}.")
        self.store.update_program(program_id, name=name)

    def usage(self, key: str) -> Dict[str, int]:
        return self.store.key_usage(key)

    def blocker(self, name: str, key: str) -> str:
        """Why ``name`` cannot be deleted yet (what is stored under its key), or "" when nothing is."""
        used = self.usage(key)
        records = sum(n for k, n in used.items() if k not in ("runs", "versions"))
        parts = [f"{used['runs']} run{'s' if used['runs'] != 1 else ''}" if used["runs"] else "",
                 f"{used['versions']} schedule version{'s' if used['versions'] != 1 else ''}" if used["versions"] else "",
                 f"{records} day record{'s' if records != 1 else ''}" if records else ""]
        parts = [p for p in parts if p]
        if not parts:
            return ""
        listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        return f"{name} still has {listed}: move them into a program or LOB first."

    def _refuse_if_used(self, name: str, key: str) -> None:
        said = self.blocker(name, key)
        if said:
            raise ValueError(said)

    def delete_lob(self, lob_id: int) -> str:
        """Delete a LOB nothing is stored under; returns its name."""
        lob = next((l for l in self.store.list_lobs() if l["id"] == lob_id), None)
        if lob is None:
            raise ValueError("There is no such LOB.")
        self._refuse_if_used(lob["name"], lob["key"])
        self.store.delete_lob_row(lob_id)
        return lob["name"]

    def delete_program(self, program_id: int) -> str:
        """Delete a program without LOBs that nothing is stored under; returns its name."""
        program = self.program(program_id)
        if program["lobs"]:
            raise ValueError("Delete or move its LOBs first.")
        self._refuse_if_used(program["name"], program["key"])
        self.store.delete_program_row(program_id)
        return program["name"]
