# © 2026 Omar Mokhtar. All rights reserved.
"""Who an aux can be with, per program (Phase U): departments and the people in each, kept by admins and
supervisors so that booking picks them from lists and later analysis groups the same names the same way (owner,
2026-10-09: "categorized as well by 2 things department and names ... added for each program by admin or supervisor
... popup as a drop down list while choosing them ... to ensure consitenty for later on analysis").

A program's LOBs share its lists. Records keep the department and name as text, so changing a list never rewrites
what was booked before."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .programs import ProgramBook

DEPT_MAX, NAME_MAX = 60, 80  # characters
SPLIT = re.compile(r"\t|,|;")  # "Department, Name", or two columns copied from Excel


def _tidy(text: str) -> str:
    return " ".join((text or "").split())


def _find(items: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    return next((x for x in items if x["name"].casefold() == name.casefold()), None)


def pick_contact(lists: List[Dict[str, Any]], kind: str, dept: str, name: str) -> Tuple[str, str]:
    """The department and person an aux is with, as the program's list spells them; refused when not listed."""
    dept, name, what = _tidy(dept), _tidy(name), kind.lower()
    if not dept:
        raise ValueError(f"Pick the department the {what} is with.")
    found = _find(lists, dept)
    if found is None:
        raise ValueError(f"{dept} is not a department on this program's list.")
    if not name:
        raise ValueError(f"Pick who in {found['name']} the {what} is with.")
    person = _find(found["people"], name)
    if person is None:
        raise ValueError(f"{name} is not on {found['name']}'s list for this program.")
    return found["name"], person["name"]


class ContactBook:
    def __init__(self, store):
        self.store = store

    def lists(self, program_id: int) -> List[Dict[str, Any]]:
        """The program's departments (by name), each with its people (by name)."""
        people = self.store.list_aux_people(program_id)
        return [{"id": d["id"], "name": d["name"],
                 "people": [{"id": p["id"], "name": p["name"]} for p in people if p["department_id"] == d["id"]]}
                for d in self.store.list_aux_departments(program_id)]

    def for_unit(self, key: str) -> List[Dict[str, Any]]:
        """The lists a program or LOB books from: its program's."""
        unit = ProgramBook(self.store).unit(key) if key else None
        return self.lists(unit["program"]["id"]) if unit else []

    @staticmethod
    def _check(lists: List[Dict[str, Any]], dept: str, name: str) -> Tuple[str, str]:
        """(department as listed or new, name): refused when empty, too long or already listed."""
        dept, name = _tidy(dept), _tidy(name)
        if not dept:
            raise ValueError("Give the department.")
        if len(dept) > DEPT_MAX:
            raise ValueError(f"Keep a department to {DEPT_MAX} characters.")
        if len(name) > NAME_MAX:
            raise ValueError(f"Keep a name to {NAME_MAX} characters.")
        found = _find(lists, dept)
        if found is not None and not name:
            raise ValueError(f"{found['name']} is already a department.")
        if found is not None and _find(found["people"], name):
            raise ValueError(f"{_find(found['people'], name)['name']} is already on {found['name']}'s list.")
        return (found["name"] if found else dept), name

    def add(self, program_id: int, dept: str, name: str, user_id: int) -> Tuple[str, str]:
        """A department, or a person in a department (made when new)."""
        dept, name = self._check(self.lists(program_id), dept, name)
        self.store.add_aux_entries(program_id, [(dept, name)])
        return dept, name

    def add_many(self, program_id: int, text: str, user_id: int) -> Tuple[int, int]:
        """A pasted list, one "Department, Name" (or just a department) per line: all of it or, when any line is
        wrong, none of it, naming the lines. Returns (departments added, people added)."""
        lists = [{"name": d["name"], "people": list(d["people"])} for d in self.lists(program_id)]
        entries: List[Tuple[str, str]] = []
        problems: List[str] = []
        for n, line in enumerate((text or "").splitlines(), 1):
            if not line.strip():
                continue
            parts = SPLIT.split(line, maxsplit=1)
            dept, name = parts[0], (parts[1] if len(parts) > 1 else "")
            try:
                dept, name = self._check(lists, dept, name)
            except ValueError as exc:
                problems.append(f"Line {n}: {exc}")
                continue
            found = _find(lists, dept)
            if found is None:
                found = {"name": dept, "people": []}
                lists.append(found)
            if name:
                found["people"].append({"name": name})
            entries.append((dept, name))
        if problems:
            raise ValueError("Nothing was added. " + " ".join(problems))
        if not entries:
            raise ValueError("Paste at least one line: Department, Name.")
        before = {d["name"] for d in self.lists(program_id)}
        self.store.add_aux_entries(program_id, entries)
        return len({d for d, _ in entries} - before), sum(1 for _, n in entries if n)

    def remove_person(self, program_id: int, person_id: int, user_id: int) -> Tuple[str, str]:
        row = self.store.get_aux_person(person_id)
        if row is None or row["program_id"] != program_id:
            raise ValueError("That person is not on this program's list.")
        self.store.delete_aux_person(person_id)
        return row["department"], row["name"]

    def remove_department(self, program_id: int, department_id: int, user_id: int) -> str:
        row = self.store.get_aux_department(department_id)
        if row is None or row["program_id"] != program_id:
            raise ValueError("That department is not on this program's list.")
        self.store.delete_aux_department(department_id)
        return row["name"]
