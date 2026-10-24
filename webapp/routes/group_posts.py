# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: group posts."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Tuple

from flask import abort, flash, g, redirect, render_template, request, url_for

from ..analytics import program_weeks
from ..app import clean_program
from ..attendance import hm
from ..auth import admin_required
from ..notify import DEFAULT_HOLD, DEFAULT_KINDS as NOTIFY_DEFAULT_KINDS, HOLDS, KINDS as NOTIFY_KINDS, MODES as NOTIFY_MODES, MODE_WORDS, SERVICES, check_link, last_line, link_end, post_from_body, post_result, post_what
from ..permissions import CATALOGUE as PERMISSIONS, ROLE_NAMES, matrix
from ..programs import ProgramBook
from ..run_admin import PICK_UNIT, apply_rename, preview_rename, unit_keys
from ..runs import MODES
from ..shrinkage import ITEMS as SHRINKAGE_ITEMS, mapping_from_form, read_mapping


def register(app, ctx) -> None:
    """Add the group posts routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ---------------------------------------------------------------- group posts (Phase AB)
    def _notify_units() -> List[Tuple[str, str]]:
        """Every LOB (and program without LOBs) as (key, "Program, LOB"), in the left menu's order."""
        return [pair for p in ctx._unit_choices(ProgramBook(app.extensions["store"]).tree()) for pair in p["choices"]]

    def _notify_fields(saved: Dict[str, Any]) -> Dict[str, Any]:
        """The Notifications form, checked: a pasted link replaces the saved one, an empty field keeps it."""
        link, service = request.form.get("link", "").strip(), saved.get("service", "")
        if link:
            service = check_link(link)
        else:
            link = saved.get("link", "")
        mode = request.form.get("mode", "off")
        mode = mode if mode in NOTIFY_MODES else "off"
        if mode != "off" and not link:
            raise ValueError("Paste the group link first, or leave posting Off.")
        hold = request.form.get("hold", type=int)
        morning = request.form.get("morning", "").strip()
        if morning and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", morning):
            raise ValueError("Pick a time like 07:30, or leave it empty.")
        return {"link": link, "service": service, "mode": mode,
                "kinds": ",".join(k for k in NOTIFY_KINDS if k in request.form.getlist("kinds")),
                "hold": hold if hold in HOLDS else DEFAULT_HOLD, "morning": morning,
                "morning_day": "before" if request.form.get("morning_day") == "before" else "same"}

    def _notify_unit() -> Tuple[str, str]:
        key, labels = request.values.get("unit", ""), dict(_notify_units())
        if key not in labels:
            abort(404, description="There is no such LOB. Pick one from the list on the Notifications page.")
        return key, labels[key]

    @app.route("/admin/roles", methods=["GET", "POST"])
    @admin_required
    def roles_page():  # type: ignore[no-untyped-def]
        """Phase AK: what Planner, Team manager and Supervisor may see and do (only the listed roles and keys are
        read from the form; everything not ticked is off)."""
        store = app.extensions["store"]
        if request.method == "POST":
            if request.form.get("reset") == "1" and request.form.get("confirm") != "1":
                flash("Tick the box to put every role back to the defaults.")
            elif request.form.get("reset") == "1":
                store.set_role_permissions({})
                ctx._record("roles_changed", subject="Roles", detail="back to the defaults")
                flash("Roles are back to the defaults.")
            else:
                ticked = set(request.form.getlist("allow"))
                rows = {(r, k): f"{r}|{k}" in ticked for r in ROLE_NAMES for k in PERMISSIONS}
                store.set_role_permissions(rows)
                ctx._record("roles_changed", subject="Roles", detail="; ".join(
                    f"{r}: {sum(1 for k in PERMISSIONS if rows[(r, k)])} of {len(PERMISSIONS)}" for r in ROLE_NAMES))
                flash("Roles saved.")
            return redirect(url_for("roles_page"))
        return render_template("roles.html", catalogue=PERMISSIONS, role_names=ROLE_NAMES, grid=matrix(store))

    @app.route("/notifications", methods=["GET", "POST"])
    @admin_required
    def notifications_page():  # type: ignore[no-untyped-def]
        """Teams and Slack group posts (Phase AB, approved sample 02): each LOB's group link, kept on this server and
        never shown again in full; what posts; how long changes wait; the last posts and their result."""
        store, units = app.extensions["store"], _notify_units()
        if not units:
            flash("There is no LOB to post for yet. Add one under LOBs and defaults.")
            return redirect(url_for("home"))
        if request.method == "POST":
            key, label_ = _notify_unit()
            try:
                fields = _notify_fields(store.get_notify(key) or {})
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for("notifications_page", unit=key), code=303)
            store.set_notify(key, **fields, site=request.host_url, saved_by=g.user["id"], saved_at=time.time())
            said = f"Posting {MODE_WORDS[fields['mode']].lower()}; " + (
                f"{SERVICES[fields['service']]} link ending {link_end(fields['link'])}" if fields["link"] else
                "no group link")
            ctx._record("notify_saved", program=key, subject=label_, detail=said)
            flash(f"Notifications saved for {label_}.")
            return redirect(url_for("notifications_page", unit=key), code=303)
        key = request.args.get("unit", "")
        key = key if key in dict(units) else units[0][0]
        saved = store.get_notify(key) or {}
        rows = []
        every, newest = store.notify_overview()  # Phase AC: two queries for every LOB, not two per LOB
        for k, text in units:
            s = every.get(k, {})
            rows.append({"key": k, "label": text, "mode": MODE_WORDS[s.get("mode") or "off"],
                         "service": SERVICES.get(s.get("service", ""), "–") if s.get("link") else "–",
                         "last": last_line(newest[k]) if k in newest else
                         ("No posts yet" if s.get("link") else "No group link yet")})
        posts = store.notify_posts(unit=key)
        shown = next((p for p in posts if p["what"] != "test" and p["status"] in ("sent", "preview")), None)
        by = store.get_user(saved["saved_by"]) if saved.get("saved_by") else None
        return render_template("notifications.html", unit=key, unit_label=dict(units)[key], rows=rows, saved=saved,
                               mode=saved.get("mode") or "off", kinds=NOTIFY_KINDS, holds=HOLDS,
                               ticked=(saved["kinds"].split(",") if saved else NOTIFY_DEFAULT_KINDS),
                               hold=int(saved.get("hold") or DEFAULT_HOLD), end=link_end(saved.get("link", "")),
                               service_name=SERVICES.get(saved.get("service", ""), ""),
                               saved_by=by["display_name"] if by else "",
                               last_post=post_from_body(shown["body"]) if shown else None,
                               recent=ctx._paged([(p, post_what(p), *post_result(p)) for p in posts], "posts_page",
                                             "nf-rec-h"))

    @app.route("/notifications/test", methods=["POST"])
    @admin_required
    def notifications_test():  # type: ignore[no-untyped-def]
        key, label_ = _notify_unit()
        ok, said = app.extensions["notifier"].send_test(key, g.user["display_name"])
        if (app.extensions["store"].get_notify(key) or {}).get("link"):
            ctx._record("notify_tested", program=key, subject=label_, detail=said)
        flash(said)
        return redirect(url_for("notifications_page", unit=key), code=303)

    @app.route("/notifications/remove", methods=["POST"])
    @admin_required
    def notifications_remove():  # type: ignore[no-untyped-def]
        key, label_ = _notify_unit()
        app.extensions["store"].set_notify(key, link="", service="", mode="off", saved_by=g.user["id"],
                                           saved_at=time.time())
        ctx._record("notify_removed", program=key, subject=label_, detail="Posting off")
        flash(f"Group link removed for {label_}; posting is off.")
        return redirect(url_for("notifications_page", unit=key), code=303)

    @app.route("/setup/programs", methods=["GET", "POST"])
    @admin_required
    def program_setup():  # type: ignore[no-untyped-def]
        """Programs and LOBs: add them, put an existing name in a program as a LOB, and set the defaults a
        new schedule starts from. Keys never change, so nothing stored is rewritten."""
        store = app.extensions["store"]
        book = ProgramBook(store)
        book.sync()
        if request.method == "POST":
            action, name = request.form.get("action", ""), request.form.get("name", "")
            pid = request.form.get("program_id", type=int)
            try:
                if action == "add_program":
                    book.add_program(name)
                    said = f"Added program {' '.join(name.split())}."
                elif action == "add_lob":
                    said = f"Added LOB {book.add_lob(pid, name)}."
                elif action == "adopt":
                    key = request.form.get("key", "")
                    book.adopt(key, pid, name)
                    said = f"{key} is now {book.label(key)}."
                elif action == "heavy_pages":  # Phase AV: how many weeks the heavy pages allow most people
                    weeks = request.form.get("weeks", type=int)
                    if weeks is None or not 1 <= weeks <= 52:
                        raise ValueError("Give a whole number of weeks from 1 to 52.")
                    store.set_app_setting("heavy_weeks", str(weeks))
                    ctx._record("heavy_weeks_set", detail=f"{weeks} weeks")
                    said = f"People other than admins, supervisors and RTAs can now look at up to {weeks} weeks at a time."
                elif action == "defaults":
                    options = {k: request.form.get(k) for k, plain in ctx.ADVANCED_DEFAULTS.items()
                               if request.form.get(k) and request.form.get(k) != plain}
                    book.set_defaults(pid, request.form.get("start_day", type=int, default=-1),
                                      request.form.get("run_mode", ""), options)
                    said = f"Saved the defaults for {book.program(pid)['name']}."
                elif action == "measure":  # Phase AS
                    book.set_measure(pid, request.form.get("coverage_measure", ""))
                    said = f"{book.program(pid)['name']} now counts billable time as {book.MEASURES[book.measure_setting(pid)].lower()}."
                elif action == "rta_defaults":  # Phase AU: the program's default target and operating day
                    target_text, start_text = request.form.get("target", "").strip(), request.form.get("day_start", "").strip()
                    if target_text and not target_text.isdigit():
                        raise ValueError("The default target is 1 to 100 percent.")
                    m = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", start_text) if start_text else None
                    if start_text and not m:
                        raise ValueError("Give the operating day start as a time on the quarter hour, like 16:00.")
                    kept = book.rta_defaults(pid)
                    book.set_rta_defaults(pid, int(target_text) if target_text else None,
                                          int(m.group(1)) * 60 + int(m.group(2)) if m else None, kept["shrinkage"])
                    said = f"Saved the target and operating day defaults for {book.program(pid)['name']}."
                elif action == "shrinkage":  # Phase AU: what counts as shrinkage, for the program's LOBs
                    kept = book.rta_defaults(pid)
                    book.set_rta_defaults(pid, kept["target"], kept["day_start"], mapping_from_form(request.form))
                    said = f"Saved what counts as shrinkage for {book.program(pid)['name']}."
                elif action == "shrinkage_standard":
                    kept = book.rta_defaults(pid)
                    book.set_rta_defaults(pid, kept["target"], kept["day_start"], None)
                    said = f"{book.program(pid)['name']} counts shrinkage the standard way again."
                elif action == "reset_unit":  # a LOB's own operating day or shrinkage goes back to the program's
                    unit, field = request.form.get("unit", ""), request.form.get("field", "")
                    if not ctx._access().can_open(unit) or field not in ("day_start", "shrinkage"):
                        abort(400)
                    (app.extensions["store"].clear_day_start if field == "day_start"
                     else app.extensions["store"].clear_shrinkage_map)(unit)
                    said = f"{book.label(unit)} uses the program's {'operating day' if field == 'day_start' else 'shrinkage'} again."
                elif action == "requests":  # Phase AU: associate break change requests for this program
                    book.set_request_settings(pid, request.form.get("enabled") == "1",
                                              request.form.get("lead", type=int, default=0),
                                              request.form.get("limit", type=int, default=0))
                    said = f"Saved the break change request rules for {book.program(pid)['name']}."
                elif action == "rename_program":
                    book.rename(pid, None, name)
                    said = f"Renamed to {book.program(pid)['name']}."
                elif action == "rename_lob":
                    book.rename(None, request.form.get("lob_id", type=int), name)
                    said = "Renamed the LOB."
                elif action == "delete_program":
                    gone = book.delete_program(pid)
                    said = f"Deleted program {gone}."
                    ctx._record("program_deleted", subject=gone, detail=said)
                    flash(said)
                    return redirect(url_for("program_setup"))
                elif action == "delete_lob":
                    lob_id = request.form.get("lob_id", type=int)
                    owner = next((l["program_id"] for l in store.list_lobs() if l["id"] == lob_id), None)
                    gone = book.delete_lob(lob_id)
                    said = f"Deleted LOB {gone}" + (f" of {book.program(owner)['name']}." if owner else ".")
                    ctx._record("lob_deleted", subject=gone, detail=said)
                    flash(said)
                    return redirect(url_for("program_setup"))
                else:
                    abort(400)
                ctx._record("program_set_up", subject=request.form.get("key") or name, detail=said)
                flash(said)
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("program_setup"))
        tree = book.tree()
        people = {p["id"]: [] for p in tree}
        for u in store.list_users():
            for pid in store.user_program_ids(u["id"]):
                people.setdefault(pid, []).append(u["display_name"] + (" (supervisor)" if u["is_supervisor"] else ""))
        loose = [p for p in tree if not p["lobs"]]  # names that can be put in a program as a LOB
        blockers = {k: book.blocker(n, k) for p in tree for n, k in [(p["name"], p["key"])] +
                    [(l["name"], l["key"]) for l in p["lobs"]]}
        for p in tree:
            p["measure_value"] = p.get("measure") or "interval"
        return render_template("program_setup.html", heavy_weeks=int(store.get_app_setting("heavy_weeks", str(ctx.HEAVY_WEEKS_DEFAULT))),
                               heavy_recommended=ctx.HEAVY_WEEKS_RECOMMENDED, programs=tree, people=people, loose=loose, modes=MODES,
                               measures=ProgramBook.MEASURES, request_rules={p["id"]: book.request_settings(p["id"]) for p in tree},
                               hm=hm, rta_def={p["id"]: book.rta_defaults(p["id"]) for p in tree},
                               shrink_items=SHRINKAGE_ITEMS,
                               shrink_now={p["id"]: read_mapping(json.dumps(book.rta_defaults(p["id"])["shrinkage"])
                                                                 if book.rta_defaults(p["id"])["shrinkage"] else None)
                                           for p in tree},
                               own_units=_own_unit_settings(tree),
                               blockers=blockers, unit_groups=ctx._unit_choices(tree),
                               look_alike={p["key"]: book.look_alike(p["id"]) for p in tree if not p["lobs"]},
                               days=["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])

    def _own_unit_settings(tree: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """Phase AU: the LOBs (and a program without LOBs) that have their own operating day or shrinkage mapping, which
        win over the program's defaults until they are reset."""
        store, found = app.extensions["store"], {}
        for p in tree:
            rows = []
            for key in p["units"]:
                own_start, own_map = store._day_start_own(key), store.get_shrinkage_map(key)
                inherited = not (own_map and own_map["at"])
                if own_start is not None or not inherited:
                    rows.append({"key": key, "label": ProgramBook(store).label(key),
                                 "day_start": None if own_start is None else hm(own_start), "shrinkage": not inherited})
            found[p["id"]] = rows
        return found

    @app.route("/programs/rename", methods=["POST"])
    @admin_required
    def program_rename():  # type: ignore[no-untyped-def]
        """Rename a program everywhere, or merge it into another: shown first, saved with a reason."""
        store = app.extensions["store"]
        old, new = request.form.get("old", ""), clean_program(request.form.get("new", ""))
        reason = " ".join(request.form.get("reason", "").split())[:200]
        known = program_weeks(ctx._all_runs(), app.extensions['store'].in_use_runs())
        try:
            if new not in unit_keys(store):
                raise ValueError(PICK_UNIT)  # moved into a program or LOB that is set up, never a typed name
            found = preview_rename(store, old, new)
            confirmed = request.form.get("confirm") == "1"
            if confirmed and reason and not found["clashes"]:
                apply_rename(store, old, new, g.user["id"], reason)
                book = ProgramBook(store)
                flash(f"Moved {book.label(old)} into {book.label(found['new'])}.")
                known = program_weeks(ctx._all_runs(), app.extensions['store'].in_use_runs())
                return redirect(url_for("program", name=found["new"]) if found["new"] in known else url_for("programs"))
            return render_template("program_rename.html", found=found, reason=reason,
                                   reason_missing=confirmed and not reason,
                                   back=url_for("program", name=old) if old in known else url_for("programs"))
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("program", name=old) if old in known else url_for("programs"))

