# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: people from a file."""
from __future__ import annotations

import io
import re
import secrets
import time
from typing import Any, Dict, List

from flask import abort, flash, g, redirect, render_template, request, send_file, url_for

from ..access import Access, role
from ..app import MIN_PASSWORD, USERNAME_RULE, username_problem
from ..auth import admin_required, manager_required
from ..bulk_users import new_password, passwords_workbook, people_workbook, read_people, template_bytes


def register(app, ctx) -> None:
    """Add the people from a file routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- people from a file (Phase AR)
    BULK_MINUTES = 30  # how long a checked file waits to be added, and the passwords to be downloaded

    def _bulk_held() -> Dict[str, Dict[str, Any]]:
        """Checked files and password sheets waiting for their owner, in memory only (a restart drops them)."""
        held = app.extensions.setdefault("bulk_users", {})
        now = time.time()
        for key in [k for k, v in held.items() if v["expires"] < now]:
            held.pop(key, None)
        return held

    def _bulk_plan(rows: List[Dict[str, Any]], access: Access) -> List[Dict[str, Any]]:
        """Each row of an uploaded people sheet with what would be added and, when it cannot be, the reasons. The same
        rules as Add a person: a supervisor adds planners, associates and team managers of their own programs only."""
        store, admin, tree = app.extensions["store"], bool(g.user["is_admin"]), access.book.tree()
        by_name = {" ".join(p["name"].split()).casefold(): p["id"] for p in access.grantable()}
        taken = {u["username"] for u in store.list_users()}
        in_file = {r["username"].strip().lower() for r in rows}
        planned: List[Dict[str, Any]] = []
        seen: set = set()
        for r in rows:
            username = r["username"].strip().lower()
            problems: List[str] = []
            kind = " ".join(r["role"].lower().replace("_", " ").split()).replace(" ", "_") or "planner"
            everything = False
            programs: List[int] = []
            for name in [x for x in re.split(r"[;,]", r["programs"]) if x.strip()]:
                key = " ".join(name.split()).casefold()
                if key == "all" and admin:
                    everything = True
                elif key in by_name:
                    programs.append(by_name[key])
                else:
                    problems.append(f"{name.strip()} is not one of your programs.")
            programs = sorted(set(programs))
            roster = r["roster_name"].strip()
            if username_problem(username):
                problems.append(USERNAME_RULE)
            elif username in taken:
                problems.append(f"{username} already exists.")
            elif username in seen:
                problems.append(f"{username} is in the file twice.")
            seen.add(username)
            if kind not in ctx.ROLES:
                problems.append("Pick a role.")
            elif kind not in ctx.STAFF_ADDS and not admin:
                problems.append("Only an admin adds supervisors and admins.")
            elif everything and kind == "associate":
                problems.append("An associate has named programs, not all of them.")
            elif not everything and not programs and not problems:
                problems.append("Give them at least one of your programs.")
            if kind == "associate" and programs and not problems:
                found = ctx._roster_problem(roster, programs, tree)
                if found:
                    problems.append(found)
                else:
                    roster = ctx._roster_canonical(roster, programs, tree) or roster
            elif kind != "associate":
                roster = ""
            if r["password"] and len(r["password"]) < MIN_PASSWORD:
                problems.append(f"A password of at least {MIN_PASSWORD} characters, or leave it blank to make one.")
            planned.append({**r, "typed": r["username"].strip(), "username": username, "kind": kind, "programs_ids": programs, "everything": everything,
                            "roster": roster, "problems": problems, "has_password": bool(r["password"])})
        for p in planned:  # the team manager: someone already here, or a team manager added by this same file
            wanted = p["team_manager"].strip().lower()
            if not wanted or p["problems"]:
                continue
            found = next((u for u in store.list_users() if u["username"] == wanted and u["is_team_manager"] and u["active"]
                          and (u["all_programs"] or set(p["programs_ids"]) & set(store.user_program_ids(u["id"])))), None)
            mate = next((q for q in planned if q["username"] == wanted and q["kind"] == "team_manager" and not q["problems"]
                         and (q["everything"] or set(p["programs_ids"]) & set(q["programs_ids"]))), None)
            if p["kind"] != "associate":
                p["problems"].append("Only an associate has a team manager.")
            elif found is None and mate is None:
                p["problems"].append(f"{wanted} is not a team manager of their programs.")
        return planned

    @app.route("/admin/users/bulk", methods=["GET", "POST"])
    @manager_required
    def admin_users_bulk():  # type: ignore[no-untyped-def]
        """Add many people from one sheet: check it first (every row with its reason), then add the good rows."""
        access, error, plan, token = Access(app.extensions["store"], g.user), "", None, ""
        if request.method == "POST":
            upload = request.files.get("people")
            try:
                if upload is None or not upload.filename:
                    raise ValueError("Pick the people sheet to upload.")
                plan = _bulk_plan(read_people(upload.read(), upload.filename), access)
                token = secrets.token_urlsafe(16)
                _bulk_held()[token] = {"user": g.user["id"], "rows": [{k: p[k] for k in ("n", *[
                    "username", "display_name", "role", "programs", "roster_name", "team_manager", "password"])}
                    for p in plan], "expires": time.time() + 60 * BULK_MINUTES}
            except ValueError as exc:
                error = str(exc)
        return render_template("admin_users_bulk.html", error=error, plan=plan, token=token, roles=ctx.ROLES,
                               good=sum(1 for p in plan or [] if not p["problems"]), minutes=BULK_MINUTES)

    @app.route("/admin/users/bulk/template.xlsx")
    @manager_required
    def admin_users_bulk_template():  # type: ignore[no-untyped-def]
        return send_file(io.BytesIO(template_bytes()), as_attachment=True, download_name="People_template.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/admin/users/bulk/add", methods=["POST"])
    @manager_required
    def admin_users_bulk_add():  # type: ignore[no-untyped-def]
        """Add the rows of a checked file that can be added. The checks run again first: nothing is trusted from the
        earlier answer but the rows the person uploaded."""
        held = _bulk_held().get(request.form.get("token", ""))
        if held is None or held["user"] != g.user["id"]:
            abort(404)
        _bulk_held().pop(request.form["token"], None)
        store, access = app.extensions["store"], Access(app.extensions["store"], g.user)
        plan = _bulk_plan(held["rows"], access)
        order = sorted((p for p in plan if not p["problems"]), key=lambda p: p["kind"] == "associate")  # team managers first
        made, shown = {}, []
        for p in order:
            password = p["password"] or new_password()
            uid = store.add_user(p["username"], p["display_name"], password, is_admin=p["kind"] == "admin",
                                 must_change=True)
            store.update_user(uid, is_supervisor=int(p["kind"] == "supervisor"), all_programs=int(p["everything"]),
                              is_associate=int(p["kind"] == "associate"),
                              roster_name=p["roster"] if p["kind"] == "associate" else "",
                              is_team_manager=int(p["kind"] == "team_manager"))
            store.set_user_programs(uid, p["programs_ids"])
            made[p["username"]] = uid
            shown.append({"username": p["username"], "display_name": p["display_name"] or p["username"],
                          "role": ctx.ROLES[p["kind"]], "password": "" if p["password"] else password,
                          "given": bool(p["password"])})
        for p in order:  # their team managers, now that everyone is here
            wanted = p["team_manager"].strip().lower()
            if p["kind"] == "associate" and wanted:
                chosen = made.get(wanted) or next((u["id"] for u in store.list_users() if u["username"] == wanted), None)
                if chosen is not None:
                    store.update_user(made[p["username"]], team_manager_id=chosen)
        ctx._record("users_bulk_added", detail=f"{len(shown)} added, {len(plan) - len(shown)} left out")  # never the passwords
        sheet_token = secrets.token_urlsafe(16)
        _bulk_held()[sheet_token] = {"user": g.user["id"], "expires": time.time() + 60 * BULK_MINUTES,
                                     "sheet": passwords_workbook([s for s in shown if not s["given"]])}
        return render_template("admin_users_bulk.html", error="", plan=None, token="", roles=ctx.ROLES, good=0,
                               minutes=BULK_MINUTES, added=shown, skipped=[p for p in plan if p["problems"]],
                               sheet_token=sheet_token)

    @app.route("/admin/users/bulk/<sheet_token>/passwords.xlsx")
    @manager_required
    def admin_users_bulk_passwords(sheet_token: str):  # type: ignore[no-untyped-def]
        """The temporary passwords made up for a file's people: once, for the person who added them."""
        held = _bulk_held().get(sheet_token)
        if held is None or held["user"] != g.user["id"] or "sheet" not in held:
            abort(404)
        _bulk_held().pop(sheet_token, None)
        return send_file(io.BytesIO(held["sheet"]), as_attachment=True, download_name="Temporary_passwords.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/admin/signins/release", methods=["POST"])
    @admin_required
    def admin_signins_release():  # type: ignore[no-untyped-def]
        """Phase AU: an admin lifts the hold on an address (a whole office behind one address, a tester)."""
        address = (request.form.get("address") or "").strip()
        app.extensions["throttle"].release(address)
        ctx._record("sign_in_released", subject=address)
        flash(f"{address} may sign in again.")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/export.xlsx")
    @manager_required
    def admin_users_export():  # type: ignore[no-untyped-def]
        """Phase AU: the people this person manages, as a sheet in the bulk upload's columns."""
        store, access = app.extensions["store"], Access(app.extensions["store"], g.user)
        admin = bool(g.user["is_admin"])
        tree = access.book.tree()
        names = {u["id"]: u["username"] for u in store.list_users()}
        rows = []
        for u in store.list_users():
            if not (admin or access.can_manage(u)):
                continue
            ids = store.user_program_ids(u["id"])
            rows.append({"username": u["username"], "display_name": u["display_name"],
                         "role": role(u).lower().replace(" ", "_"),
                         "programs": "ALL" if u["all_programs"] else "; ".join(
                             {p["id"]: p["name"] for p in tree}.get(i, "?") for i in ids),
                         "roster_name": u["roster_name"], "team_manager": names.get(u["team_manager_id"], ""),
                         "active": u["active"]})
        ctx._record("users_exported", detail=f"{len(rows)} people")
        return send_file(io.BytesIO(people_workbook(rows)), as_attachment=True, download_name="People.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/admin/users/switch", methods=["POST"])
    @manager_required
    def admin_users_switch():  # type: ignore[no-untyped-def]
        """Phase AU: switch several people off or on at once; the same walls as one at a time (only people this person
        manages, never themselves)."""
        store, access = app.extensions["store"], Access(app.extensions["store"], g.user)
        ids = [int(x) for x in request.form.getlist("who") if x.isdigit()]
        on = request.form.get("decision") == "on"
        if not ids:
            flash("Tick the people first.")
            return redirect(url_for("admin_users"))
        done, skipped = [], []
        for uid in ids:
            target = store.get_user(uid)
            if target is None or target["id"] == g.user["id"] or not access.can_manage(target):
                skipped.append(uid)
                continue
            store.set_active(uid, on)
            ctx._record("user_enabled" if on else "user_disabled", subject=target["username"])
            done.append(uid)
        said = f"{len(done)} {'person' if len(done) == 1 else 'people'} switched {'on' if on else 'off'}."
        if skipped:
            said += f" {len(skipped)} left as they were: not yours to change, or your own account."
        flash(said)
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
    @manager_required
    def admin_user_action(user_id: int, action: str):  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        access = Access(store, g.user)
        target = store.get_user(user_id)
        if target is None:
            abort(404)
        if target["id"] == g.user["id"]:
            flash("Change your own account from Settings; you cannot switch it off.")
            return redirect(url_for("admin_users"))
        if not access.can_manage(target):
            abort(403)
        if action == "disable":
            store.set_active(user_id, False)
            ctx._record("user_disabled", subject=target["username"])
            flash(f"{target['username']} is switched off.")
        elif action == "enable":
            store.set_active(user_id, True)
            ctx._record("user_enabled", subject=target["username"])
            flash(f"{target['username']} is switched on.")
        elif action == "delete":  # Phase AR: the account goes; the name stays in the history of what they did
            if request.form.get("confirm") != "1":
                flash(f"Tick the box to confirm, then press Delete person for {target['username']}.")
                return redirect(url_for("admin_users"))
            if target["is_admin"] and sum(1 for u in store.list_users() if u["is_admin"] and u["active"]) <= 1:
                flash("That is the last admin. Make another admin before deleting this one.")
                return redirect(url_for("admin_users"))
            store.delete_user(user_id)
            ctx._record("user_deleted", subject=target["username"], detail=role(target))
            flash(f"{target['username']} is deleted: they cannot sign in and the username is free again. "
                  "Their name stays in the history of what they did.")
        elif action == "reset":
            temporary = secrets.token_urlsafe(9)
            store.set_password(user_id, temporary, must_change=True)
            ctx._record("password_reset", subject=target["username"])  # never the password itself
            flash(f"Temporary password for {target['username']}: {temporary} "
                  "(shown once; they choose their own at next sign-in).")
        elif action == "team":  # Phase AK
            try:
                flash(ctx._set_team_manager(access, target, request.form.get("team_manager", "")))
            except PermissionError:
                abort(403)
            except ValueError as exc:
                flash(str(exc))
        elif action == "programs":
            admin = bool(g.user["is_admin"])
            kind = request.form.get("role", "")
            current = role(target).lower().replace(" ", "_")
            if kind and kind != current and not admin:
                abort(403)
            try:
                programs = ctx._chosen_programs(access, request.form.getlist("programs"),
                                            keep=store.user_program_ids(user_id))
            except PermissionError:
                abort(403)
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for("admin_users"))
            changes: Dict[str, Any] = {}
            kind = kind if admin and kind in ctx.ROLES else current
            if kind == "associate":  # Phase AG: still linked to a name on the schedule of the programs kept
                roster = request.form.get("roster_name", "").strip() or target["roster_name"]
                problem = ctx._roster_problem(roster, programs, access.book.tree(), user_id)
                if problem:
                    flash(f"{target['username']}: {problem}")
                    return redirect(url_for("admin_users"))
                changes = {"is_associate": 1,
                           "roster_name": ctx._roster_canonical(roster, programs, access.book.tree()) or roster}
            if admin:
                changes.update({"is_admin": int(kind == "admin"), "is_supervisor": int(kind == "supervisor"),
                                "is_team_manager": int(kind == "team_manager"),
                                "all_programs": int(request.form.get("all_programs") == "1" and kind != "associate"),
                                "is_associate": int(kind == "associate"),
                                "roster_name": changes.get("roster_name", "")})
            if changes:
                store.update_user(user_id, **changes)
            store.set_user_programs(user_id, programs)
            tree = access.book.tree()
            said = ("all programs" if changes.get("all_programs") else ctx._program_names(programs, tree) or "no programs")
            ctx._record("user_programs_changed", subject=target["username"],
                    detail=f"{ctx.ROLES[kind]}; {said}")
            flash(f"{target['username']}: {said}.")
        else:
            abort(404)
        return redirect(url_for("admin_users"))

