# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: admin."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from flask import abort, flash, g, redirect, render_template, request, url_for

from ..access import Access, role
from ..app import MIN_PASSWORD, USERNAME_RULE, username_problem
from ..auth import manager_required
from ..bulk_users import new_password


def register(app, ctx) -> None:
    """Add the admin routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- admin
    ROLES = {"planner": "Planner", "associate": "Associate", "team_manager": "Team manager", "supervisor": "Supervisor",
             "admin": "Admin"}
    STAFF_ADDS = ("planner", "associate", "team_manager")  # what a supervisor may add for their programs

    ROSTER_WEEKS = 4  # Phase AO: the names on a program's last kept weeks, not only its newest (a partly filled newer week)

    def _roster_index(program_ids: list, tree: list) -> Dict[str, set]:
        """Phase AO: each name on the recent kept weeks' schedules of these programs' LOBs, with the ids of the
        programs holding it (Phase AG: an associate's account is linked to one of them)."""
        book, store = app.extensions.get("schedules"), app.extensions["store"]
        found: Dict[str, set] = {}
        if book is None:  # no package installed: no schedules kept, so no names
            return found
        for p in tree:
            if p["id"] not in program_ids:
                continue
            for key in p["units"]:
                for week in book.kept_weeks(key)[-ROSTER_WEEKS:]:
                    for v in store.list_schedules(program=key, week_start=week["week"]):
                        for a in json.loads(v["week"] or "{}").get("associates", []):
                            found.setdefault(a["name"], set()).add(p["id"])
        return found

    def _roster_names(program_ids: list, tree: list) -> List[str]:
        return sorted(_roster_index(program_ids, tree))

    def _roster_canonical(name: str, programs: list, tree: list) -> str:
        """``name`` as the schedule spells it: exactly, or else the one name that matches without regard to case or
        extra spaces; "" when none (or several) does."""
        names = _roster_names(programs, tree)
        if name in names:
            return name
        tidy = " ".join(name.split()).casefold()
        matches = [n for n in names if " ".join(n.split()).casefold() == tidy]
        return matches[0] if len(matches) == 1 else ""

    def _roster_problem(name: str, programs: list, tree: list, user_id: Optional[int] = None) -> str:
        """Why ``name`` cannot be an associate's name on the schedule of ``programs``, or ""."""
        if not name:
            return "Pick their name on the schedule."
        found = _roster_canonical(name, programs, tree)
        if not found:
            return f"{name} is not on a schedule of {_program_names(programs, tree) or 'the programs picked'}."
        for u in app.extensions["store"].list_users():
            if (u["is_associate"] and u["roster_name"] == found and u["id"] != user_id
                    and set(app.extensions["store"].user_program_ids(u["id"])) & set(programs)):
                return f"{found} already has an account ({u['username']})."
        return ""

    def _chosen_programs(access: Access, values: list, keep: Optional[list] = None) -> list:
        """Program ids picked on a form, checked against what this person may give; ``keep`` are the target's
        programs this person cannot see (a supervisor's change leaves them as they are)."""
        try:
            picked = {int(v) for v in values}
        except ValueError:
            raise ValueError("Pick programs from the list.") from None
        allowed = {p["id"] for p in access.grantable()}
        if picked - allowed:
            raise PermissionError("You can only give your own programs.")
        return sorted(picked | {pid for pid in (keep or []) if pid not in allowed})

    def _program_names(ids: list, tree: list) -> str:
        names = {p["id"]: p["name"] for p in tree}
        return ", ".join(names.get(i, "?") for i in ids)

    @app.route("/admin/users", methods=["GET", "POST"])
    @manager_required
    def admin_users():  # type: ignore[no-untyped-def]
        """People: admins manage everyone; supervisors the planners of their own programs."""
        store = app.extensions["store"]
        access = Access(store, g.user)
        admin = bool(g.user["is_admin"])
        error, made = "", []
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "").strip()  # a pasted password with a space at the end still works
            generated = not password  # Phase AR: left blank, one is made up and shown once
            if generated:
                password = new_password()
            kind = request.form.get("role") or ("admin" if request.form.get("is_admin") == "on" else "planner")
            everything = admin and request.form.get("all_programs") == "1" and kind != "associate"
            roster = request.form.get("roster_name", "").strip()
            try:
                programs = _chosen_programs(access, request.form.getlist("programs"))
            except (ValueError, PermissionError) as exc:
                programs, error = [], str(exc)
            if error:
                pass
            elif kind not in ROLES:
                error = "Pick a role."
            elif kind not in STAFF_ADDS and not admin:
                error = "Only an admin adds supervisors and admins."
            elif (not admin or kind == "associate") and not programs:
                error = "Give them at least one of your programs."
            elif kind == "associate" and _roster_problem(roster, programs, access.book.tree()):
                error = _roster_problem(roster, programs, access.book.tree())
            elif kind == "associate" and not (roster := _roster_canonical(roster, programs, access.book.tree())):
                error = "Pick their name on the schedule."
            elif username_problem(username):
                error = USERNAME_RULE
            elif any(u["username"] == username for u in store.list_users()):
                error = f"{username} already exists."
            elif len(password) < MIN_PASSWORD:
                error = f"Give a temporary password of at least {MIN_PASSWORD} characters, or leave it blank to make one."
            else:
                uid = store.add_user(username, request.form.get("display_name", ""), password,
                                     is_admin=kind == "admin", must_change=True)
                store.update_user(uid, is_supervisor=int(kind == "supervisor"), all_programs=int(everything),
                                  is_associate=int(kind == "associate"), roster_name=roster if kind == "associate" else "",
                                  is_team_manager=int(kind == "team_manager"))
                store.set_user_programs(uid, programs)
                ctx._record("user_added", subject=username,  # never the password
                        detail=f"{ROLES[kind]}; " + ("all programs" if everything else
                                                     _program_names(programs, access.book.tree()) or "no programs"))
                flash(f"Added {username}. They choose their own password at first sign-in.")
                if generated:  # shown on this answer only, never kept: the page is not a redirect
                    made = [(username, password)]
                else:
                    return redirect(url_for("admin_users"))
        tree = access.book.tree()
        names = {u["id"]: u["display_name"] for u in store.list_users()}
        people = [dict(u, role=role(u), programs=_program_names(store.user_program_ids(u["id"]), tree),
                       program_ids=store.user_program_ids(u["id"]), manageable=access.can_manage(u),
                       team_manager=names.get(u["team_manager_id"], ""),
                       team_choices=access.team_managers_for(u) if u["is_associate"] else [])
                  for u in store.list_users() if admin or access.can_manage(u)]
        held = app.extensions["throttle"].held_now() if admin else []
        return render_template("admin_users.html", users=people, users_page=ctx._paged(people, "people_page", "people-h"), error=error, made=made, grantable=access.grantable(),
                               held=held,
                               roles=ROLES if admin else {k: ROLES[k] for k in STAFF_ADDS}, admin=admin,
                               roster_names=sorted(_roster_index([p["id"] for p in access.grantable()], tree).items()))

    def _set_team_manager(access: Access, target: Dict[str, Any], value: str) -> str:
        """Phase AK: ``target``'s team manager from a form value (a user id, or "" for none). Returns what to say."""
        store = app.extensions["store"]
        if not target["is_associate"]:
            raise ValueError("Only an associate has a team manager.")
        if not access.can_manage(target):
            raise PermissionError
        if not value.strip():
            store.update_user(target["id"], team_manager_id=None)
            ctx._record("team_manager_set", subject=target["username"], detail="none")
            return f"{target['roster_name'] or target['display_name']} has no team manager."
        chosen = store.get_user(int(value)) if value.strip().isdigit() else None
        if chosen is None or not chosen["is_team_manager"] or not chosen["active"]:
            raise ValueError("Pick a team manager.")
        if chosen["id"] not in {u["id"] for u in access.team_managers_for(target)}:
            raise ValueError(f"{chosen['display_name']} has none of {target['roster_name'] or target['display_name']}'s "
                             "programs.")
        store.update_user(target["id"], team_manager_id=chosen["id"])
        ctx._record("team_manager_set", subject=target["username"], detail=chosen["display_name"])
        return f"{target['roster_name'] or target['display_name']}'s team manager is {chosen['display_name']}."

    @app.route("/admin/users/team", methods=["POST"])
    @manager_required
    def admin_users_team():  # type: ignore[no-untyped-def]
        """Phase AK: one team manager for several associates at once (each checked as if set alone)."""
        store = app.extensions["store"]
        access = Access(store, g.user)
        value = request.form.get("team_manager", "")
        done, refused = 0, []
        for who in request.form.getlist("who"):
            target = store.get_user(int(who)) if who.isdigit() else None
            if target is None:
                continue
            try:
                _set_team_manager(access, target, value)
                done += 1
            except PermissionError:
                abort(403)
            except ValueError as exc:
                refused.append(str(exc))
        chosen = store.get_user(int(value)) if value.isdigit() else None
        if done:
            flash(f"{done} associate{'s' if done != 1 else ''} now ha{'ve' if done != 1 else 's'} "
                  + (f"{chosen['display_name']} as their team manager." if chosen else "no team manager."))
        for said in refused[:3]:
            flash(said)
        if not done and not refused:
            flash("Pick the associates.")
        return redirect(url_for("admin_users"))

    ctx.ROLES = ROLES
    ctx.STAFF_ADDS = STAFF_ADDS
    ctx._chosen_programs = _chosen_programs
    ctx._program_names = _program_names
    ctx._roster_canonical = _roster_canonical
    ctx._roster_problem = _roster_problem
    ctx._set_team_manager = _set_team_manager
