# © 2026 Omar Mokhtar. All rights reserved.
"""Who sees which programs, and who manages whom.

Admins see and manage everything. Everyone else sees the programs assigned to them (or every program, for
people marked so, which is how people from before program assignments keep their access). Supervisors manage
the planners of their own programs: their programs, passwords, switched on or off."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .programs import ProgramBook


def role(user: Dict[str, Any]) -> str:
    if user.get("is_admin"):
        return "Admin"
    return "Supervisor" if user.get("is_supervisor") else "Planner"


class Access:
    def __init__(self, store, user: Dict[str, Any]):
        self.store, self.user = store, user
        self.book = ProgramBook(store)
        self.book.sync()

    def everything(self) -> bool:
        return bool(self.user.get("is_admin") or self.user.get("all_programs"))

    def program_ids(self) -> Set[int]:
        return set(self.store.user_program_ids(self.user["id"]))

    def programs(self) -> List[Dict[str, Any]]:
        tree = self.book.tree()
        if self.everything():
            return tree
        mine = self.program_ids()
        return [p for p in tree if p["id"] in mine]

    def keys(self) -> Optional[Set[str]]:
        """The keys this person may open; None means every key."""
        if self.everything():
            return None
        return {k for p in self.programs() for k in p["units"]}

    def can_open(self, key: str) -> bool:
        keys = self.keys()
        return keys is None or key in keys

    def can_manage(self, target: Dict[str, Any]) -> bool:
        """Admins manage anyone else; supervisors the planners who share a program with them."""
        if target["id"] == self.user["id"]:
            return False
        if self.user.get("is_admin"):
            return True
        if not self.user.get("is_supervisor") or target.get("is_admin") or target.get("is_supervisor"):
            return False
        if self.everything():
            return True
        if target.get("all_programs"):
            return False
        return bool(self.program_ids() & set(self.store.user_program_ids(target["id"])))

    def grantable(self) -> List[Dict[str, Any]]:
        """The programs this person may give to others."""
        if self.user.get("is_admin"):
            return self.book.tree()
        return self.programs() if self.user.get("is_supervisor") else []
