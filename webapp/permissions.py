# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK (owner, 2026-10-15: "i need to adjust as i wish the options they can have and supervisor can have and what
they can have access for etc make it adjustable"): what Planner, Team manager and Supervisor may see and do, set by an
admin on Roles. Admins keep everything; associates keep My week only. The defaults keep what planners and supervisors
did before; team managers start with seeing the pages and approving their team. Every route is checked on the server
(``ENDPOINTS``); the menu only hides what is not allowed."""
from __future__ import annotations

from typing import Any, Dict, Optional

ROLE_NAMES = ("Planner", "Team manager", "Supervisor")

# key: (what it allows, in the Roles page's words; defaults for Planner, Team manager, Supervisor)
CATALOGUE: Dict[str, tuple] = {
    "rta_view": ("RTA: see the day (Timeline, Interval board, Adherence, handover note)", (True, True, True)),
    "rta_change": ("RTA: change the day (attendance, breaks, overtime, cover, channels, Fix breaks, Rescue the day)",
                   (True, False, True)),
    "overview": ("Overview and wallboard", (True, True, True)),
    "schedules_view": ("Weeks and schedules: see and download", (True, True, True)),
    "schedules_change": ("Schedules: change shifts, breaks and channels, swap, set in use", (True, False, True)),
    "runs": ("Run and upload schedules", (True, False, True)),
    "analysis": ("Analysis and programs", (True, True, True)),
    "exports": ("Exports", (True, True, True)),
    "coaching": ("Coaching", (True, True, True)),
    "team": ("Team page", (True, True, True)),
    "approve_tm": ("Leave and swaps: first approval (their team; supervisors for any team)", (False, True, True)),
    "approve_rta": ("Leave: the RTA's approval (changes the schedule)", (True, False, True)),
    "people": ("People: add people, programs, passwords, team managers", (False, False, True)),
    "setup": ("Setup: departments, channels, targets, shrinkage, operating day, leave balances", (False, False, True)),
}

ENDPOINTS: Dict[str, str] = {
    **{e: "rta_view" for e in ("day_page", "day_handover", "day_daily_views")},
    **{e: "rta_change" for e in ("day_absences", "day_activity", "day_activity_cancel", "day_add", "day_add_preview",
                                 "day_attendance", "day_book", "day_session_move", "day_session_cancel", "day_break", "day_break_advice", "day_break_cancel",
                                 "day_bulk_apply", "day_channel", "day_channel_fix", "day_channel_preview", "day_cover",
                                 "day_cover_cancel", "day_replan_apply", "day_rescue_apply", "day_send", "day_undo",
                                 "day_undo_last", "request_change_decide")},
    **{e: "overview" for e in ("overview_page", "day_wallboard")},
    **{e: "schedules_view" for e in ("schedules_for", "week_page", "week_hours_needed", "run_detail", "run_status",
                                     "run_download", "run_schedule", "run_shortfall", "run_week", "run_schedules",
                                     "schedule_download", "schedule_week", "channel_plan_download",
                                     "channel_needs_download")},
    **{e: "schedules_change" for e in ("plan_breaks", "plan_channels", "auto_breaks", "schedule_change",
                                       "schedule_check", "schedule_in_use", "schedule_swap", "schedule_swap_check")},
    **{e: "runs" for e in ("submit_run", "run_zone", "week_check", "run_tag", "run_delete", "run_start", "run_stop",
                           "run_resume", "channel_needs_add")},
    **{e: "analysis" for e in ("program", "programs", "incidents_page")},
    **{e: "exports" for e in ("exports_page", "exports_download")},
    **{e: "coaching" for e in ("coach_page", "coach_download")},
    "team_page": "team",
    **{e: "people" for e in ("admin_users", "admin_user_action", "admin_users_team", "admin_users_bulk",
                                  "admin_users_bulk_template", "admin_users_bulk_add", "admin_users_bulk_passwords",
                                  "admin_users_export", "admin_users_switch")},
    **{e: "setup" for e in ("with_setup", "channel_setup", "day_shrinkage_map", "week_target", "day_operating_start",
                            "request_balances")},
}


def role_of(user: Dict[str, Any]) -> Optional[str]:
    """The adjustable role, or None for an admin or an associate (not adjustable)."""
    if user.get("is_admin") or user.get("is_associate"):
        return None
    if user.get("is_supervisor"):
        return "Supervisor"
    return "Team manager" if user.get("is_team_manager") else "Planner"


def matrix(store) -> Dict[str, Dict[str, bool]]:
    """role -> key -> allowed: what the admin set, the defaults where nothing is set yet."""
    kept = store.role_permissions()
    return {role: {key: kept.get((role, key), defaults[ROLE_NAMES.index(role)])
                   for key, (_, defaults) in CATALOGUE.items()} for role in ROLE_NAMES}


def allowed(store, user: Optional[Dict[str, Any]], key: str,
            grid: Optional[Dict[str, Dict[str, bool]]] = None) -> bool:
    """``grid`` is ``matrix(store)`` when the caller already read it (a page asks many times)."""
    if not user:
        return False
    if user.get("is_admin"):
        return True
    role = role_of(user)
    if role is None or key not in CATALOGUE:
        return False
    return (grid or matrix(store))[role][key]
