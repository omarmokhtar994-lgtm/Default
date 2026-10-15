# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK (owner, 2026-10-15): who gives the first approval of an associate's leave or swap. Each associate may
have a team manager (People page); that team manager approves their requests. Admins and supervisors approve in any
team manager's place. An associate with no team manager is approved by any team manager (ruling: as before, no
request is left without someone who may decide it)."""
from __future__ import annotations

from typing import Any, Dict, Optional


def is_backup(user: Dict[str, Any]) -> bool:
    """Admins and supervisors: they may approve for any team manager."""
    return bool(user.get("is_admin") or user.get("is_supervisor"))


def may_first_approve(user: Dict[str, Any]) -> bool:
    """Whether this person gives first approvals at all."""
    return is_backup(user) or bool(user.get("is_team_manager"))


def team_manager_of(store, associate_user_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """The active team manager an associate's account is linked to, or None."""
    associate = store.get_user(associate_user_id) if associate_user_id else None
    manager = store.get_user(associate["team_manager_id"]) if associate and associate["team_manager_id"] else None
    return manager if manager and manager["active"] and manager["is_team_manager"] else None


def may_approve_for(store, user: Dict[str, Any], associate_user_id: Optional[int]) -> bool:
    """Whether ``user`` may give the first approval of a request by this associate."""
    if not user or not user.get("active", 1) or not may_first_approve(user):
        return False
    if is_backup(user):
        return True
    manager = team_manager_of(store, associate_user_id)
    return manager is None or manager["id"] == user["id"]


def who_approves(store, associate_user_id: Optional[int], name: str) -> str:
    """"Team Manager 01, the team manager of Associate 003", or "a team manager" when none is assigned."""
    manager = team_manager_of(store, associate_user_id)
    return f"{manager['display_name']}, the team manager of {name}" if manager else "a team manager"
