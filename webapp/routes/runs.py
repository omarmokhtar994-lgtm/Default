# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: runs."""
from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import abort, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from ..app import IN_FLIGHT, RUN_ID, clean_program, engine_said, eta_text, kept_figures, label, stages, start_choices, start_date
from ..auth import login_required, manager_required
from ..channel_people import ChannelPeople, can_work, channel_words
from ..channels import check_lines, has_channel_needs, read_channels, requirement_tab
from ..clock import HOME, ZONES
from ..contacts import ContactBook
from ..day import read_inputs
from ..outcome import cannot_schedule, read as read_outcome, view as outcome_view
from ..programs import ProgramBook
from ..results import version_summary
from ..run_admin import PICK_UNIT, apply_run_change, preview_run_change, unit_keys
from ..runs import MODES, READY, RESUMABLE, RunQueue, parse_options
from ..upload_guard import look as upload_look
from ..zipcheck import zip_problem


def register(app, ctx) -> None:
    """Add the runs routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- runs
    def _queue() -> RunQueue:
        queue = app.extensions.get("runs")
        if queue is None:
            abort(404)
        return queue

    def _record(kind: str, run: Optional[Dict[str, Any]] = None, **fields: Any) -> None:
        """Keep who did what and when (listed by Exports); a run fills in its program, week and workbook."""
        if run is not None:
            fields = {"run_id": run["id"], "program": run.get("program") or "", "week_start": run.get("week_start") or "",
                      "subject": run.get("workbook") or "", **fields}
        user = g.get("user")
        app.extensions["store"].add_event(kind=kind, user_id=user["id"] if user else None, **fields)

    def _run_or_404(run_id: str) -> Dict[str, Any]:
        run = app.extensions["store"].get_run(run_id) if RUN_ID.match(run_id) else None
        if run is None:
            abort(404)
        if not ctx._can_see_run(run):
            abort(403)
        return run

    def _upload_refused(path: Path, name: str, structure: bool = True) -> str:
        """Phase AV: "" when the uploaded workbook may be kept; else the file is deleted at once and the reason (by kind
        and tab, never the values found) is returned to say and is recorded."""
        found = upload_look(path, structure=structure)
        if not found:
            return ""
        path.unlink(missing_ok=True)
        _record("upload_refused", subject=os.path.basename(name)[:120], detail=f"{found[0]}: file deleted")
        return found[1]

    def _channel_upload_check(path: Path) -> Tuple[Optional[str], Optional[int]]:
        """Phase V: (refusal, warnings) for an uploaded workbook; (None, None) when it has no channel tabs. Refused
        when the channel tabs cannot be used, or when the requirement tab is not named (the engine could then read
        a channel tab as its requirement). Warnings never block the upload."""
        trial = path.with_suffix(".xlsx")  # openpyxl opens .xlsx names only
        shutil.copyfile(path, trial)
        try:
            if not has_channel_needs(trial):  # Phase Z: empty tabs (the Blank's) ask for nobody: as before Phase V
                return None, None
            try:
                inputs = read_inputs(trial)
                setup = read_channels(trial, inputs["interval"])
            except (ValueError, KeyError, StopIteration) as exc:
                return f"The channel tabs need fixing before this upload: {exc}", None
            if requirement_tab(trial) is None:
                step = inputs["interval"]
                return ("This workbook has channel tabs but does not name its requirement tab, so the engine could "
                        "read a channel tab as the requirement. Add Requirements Source on the Instructions tab "
                        f"(for example FT Wise {step} Min), or name the tab FT Wise {step} Min."), None
            return None, sum(1 for level, _ in check_lines(setup, inputs, trial) if level == "warn")
        finally:
            trial.unlink(missing_ok=True)

    def _channel_lines(run_id: str) -> Optional[List[Tuple[str, str]]]:
        """The channel check of a run's channel needs (Phase Z: the ones added to it, else its input workbook's
        channel tabs) against its requirement tab, or None when it has none."""
        book = ctx._book()
        needs, src = book.channel_path(run_id), book.input_path(run_id)
        if needs is None:
            return None
        try:
            inputs = read_inputs(src)
            return check_lines(read_channels(needs, inputs["interval"]), inputs, src)
        except (ValueError, KeyError, StopIteration) as exc:
            return [("warn", f"The channel tabs cannot be read: {exc}")]

    @app.route("/runs", methods=["POST"])
    @login_required
    def submit_run():  # type: ignore[no-untyped-def]
        queue = _queue()
        upload = request.files.get("workbook")
        ready = request.form.get("kind") == "ready"  # a ready schedule: no engine run (Phase R)
        mode = "QUICK" if ready else request.form.get("mode", "QUICK")
        name = os.path.basename((upload.filename or "") if upload else "")
        if not name.lower().endswith(".xlsx") or mode not in MODES:
            flash("Upload an Excel workbook (.xlsx) and pick a mode.")
            return redirect(url_for("home"))
        options, problem = parse_options(request.form) if not ready else ({}, "")
        if problem:
            flash(problem)
            return redirect(url_for("home"))
        program = clean_program(request.form.get("program", ""))
        if program and not ctx._access().can_open(program):  # Phase AR: a program is uploaded to only by those who have it
            g.error_hint = "Your account opens only the programs given to you. Ask an admin to add this one to your programs."
            abort(403, description="That is not one of your programs")
        week = request.form.get("week_start", "").strip()
        week_start = start_date(week) if week else ""
        if week_start is None:
            flash("Pick the date the schedule starts.")
            return redirect(url_for("home"))
        zone = request.form.get("tz", HOME)  # Phase AF (A5): the zone the schedule's times are in
        if zone not in dict(ZONES):
            flash("Pick the schedule's time zone from the list.")
            return redirect(url_for("home"))
        incoming = queue.runs_root / "_incoming"
        incoming.mkdir(exist_ok=True)
        path = incoming / f"{secrets.token_hex(8)}.upload"
        upload.save(path)
        with path.open("rb") as handle:
            is_zip = handle.read(4) == b"PK\x03\x04"  # every .xlsx is a zip file
        if not is_zip:
            path.unlink()
            flash("Upload an Excel workbook (.xlsx): that file is not one.")
            return redirect(url_for("home"))
        too_big = zip_problem(path)  # Phase AU: before any workbook library opens it
        if too_big:
            path.unlink()
            flash(too_big)
            return redirect(url_for("home"))
        refused = _upload_refused(path, name)  # Phase AV: other tabs, card numbers, addresses, macros: deleted
        if refused:
            flash(refused)
            return redirect(url_for("home"))
        refusal, warnings = _channel_upload_check(path)
        if refusal:
            path.unlink()
            flash(refusal)
            return redirect(url_for("home"))
        if warnings is not None:
            flash(f"Channel tabs: {warnings} warning{'s' if warnings != 1 else ''}. They are listed on the schedules "
                  "page and never change the schedule." if warnings else "Channel tabs: checked, no warnings.")
        already = ctx._book().week_note(program, week_start, _unit_name(program))["text"] if program and week_start else ""
        if already:
            flash(already)
        if ready:
            run_id = queue.submit_ready(g.user["id"], path, name, program=program, week_start=week_start)
            app.extensions["store"].update_run(run_id, tz=zone)
            _record("run_uploaded", app.extensions["store"].get_run(run_id), detail="ready schedule")
            return redirect(url_for("run_detail", run_id=run_id))
        run_id = queue.submit(g.user["id"], path, mode, name, options, program=program, week_start=week_start)
        app.extensions["store"].update_run(run_id, tz=zone)
        _record("run_uploaded", app.extensions["store"].get_run(run_id), detail=mode)
        return redirect(url_for("run_detail", run_id=run_id))

    @app.route("/runs/<run_id>/zone", methods=["POST"])
    @login_required
    def run_zone(run_id: str):  # type: ignore[no-untyped-def]
        """Change the zone a schedule's times are in (Phase AF, A5): the uploader or an admin."""
        run = _run_or_404(run_id)
        if not (g.user["is_admin"] or run.get("user_id") == g.user["id"]):
            abort(403)
        zone = request.form.get("tz", "")
        if zone not in dict(ZONES):
            flash("Pick the schedule's time zone from the list.")
        else:
            app.extensions["store"].update_run(run_id, tz=zone)
            _record("run_details_changed", app.extensions["store"].get_run(run_id),
                    detail=f"times are in {dict(ZONES)[zone]}")
            flash(f"The schedule's times are in {dict(ZONES)[zone]}.")
        return redirect(url_for("run_detail", run_id=run_id), code=303)

    def _unit_name(key: str) -> str:
        return str(ctx._unit_filter(key))

    @app.route("/runs/week-check")
    @login_required
    def week_check():  # type: ignore[no-untyped-def]
        """For the upload form (Phase W): what the picked program and week already have, in a sentence."""
        program = clean_program(request.args.get("program", ""))
        week = start_date(request.args.get("week", "")) or ""
        if not program or not week:
            return jsonify(count=0, text="")
        if not ctx._access().can_open(program):
            abort(403)
        found = ctx._book().week_note(program, week, _unit_name(program))
        return jsonify(count=found["count"], text=found["text"])

    @app.route("/runs/<run_id>")
    @login_required
    def run_detail(run_id: str):  # type: ignore[no-untyped-def]
        return _run_page(_run_or_404(run_id))

    def _ready_figures(run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """A ready schedule's coverage (Phase S): the validator's figures for its version in use, else its newest,
        with which version that is and whether its breaks are planned yet; None when no version is kept."""
        versions = ctx._book().versions(run["id"])
        row = next((v for v in versions if v["in_use"]), None) or (versions[-1] if versions else None)
        found = version_summary(json.loads(row["checks"] or "{}")) if row else None
        if found:
            found.update(version_label=row["label"], breaks_planned=bool(json.loads(row["week"] or "{}").get("breaks")))
        return found

    def _run_figures(run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Phase AM (owner: "it should show the percentage ... after breaks or as per my in use selection"): a run's
        coverage on Home and its page. A ready schedule as before (Phase S). An engine run: the version in use; else
        the engine's own figures, as before; else, when the engine has none (a "Before breaks only" run), the version
        its week shows. A version's figures say which version and whether its breaks are planned."""
        if run["mode"] == READY:
            return _ready_figures(run)
        queue = app.extensions.get("runs")
        versions = ctx._book().versions(run["id"]) if app.extensions.get("schedules") else []
        row = next((v for v in versions if v["in_use"]), None)
        if row is None:
            found = queue.summary(run["id"]) if queue else None
            if found or not versions:
                return found
            row = max(versions, key=lambda v: (v["kind"] not in ("tool_before", "tool_consistent"), v["created"], v["id"]))
        found = version_summary(json.loads(row["checks"] or "{}"))
        if found:
            found.update(version_label=row["label"], breaks_planned=bool(json.loads(row["week"] or "{}").get("breaks")))
        return found

    def _can_resume(run: Dict[str, Any]) -> bool:
        """A stopped, interrupted or failed engine run that can continue from its checkpoints: never a readiness
        check, never a run the engine said cannot be scheduled from that workbook (Phase AC: one rule for the page
        and the route)."""
        said = engine_said(run)
        return (run["status"] in RESUMABLE and run["mode"] != "SMOKE"
                and not cannot_schedule(said.get("code", ""), said.get("category", "")))

    def _run_page(run: Dict[str, Any], **extra: Any):  # type: ignore[no-untyped-def]
        """The run page; ``extra`` carries a change to check before saving (run_tag)."""
        run_id = run["id"]
        queue = _queue()
        store = app.extensions["store"]
        people = [u for u in store.list_users() if u["active"] or u["id"] == run["user_id"]] \
            if g.user["is_admin"] else []
        said = engine_said(run)
        found = read_outcome(queue.results_dir(run_id))
        versions = ctx._book().versions(run_id)
        week_state = None  # Phase Z: whether this run is the one its week uses
        if run.get("program") and run.get("week_start"):
            used = ctx._book().in_use(run["program"], run["week_start"])
            if used is not None:
                week_state = {"mine": used["run_id"] == run_id, "week": run["week_start"],
                              "workbook": (store.get_run(used["run_id"]) or {}).get("workbook", "")}
        with_breaks = [v for v in versions if json.loads(v["week"] or "{}").get("breaks")]
        breaks_version = next((v for v in with_breaks if v["in_use"]), with_breaks[-1] if with_breaks else None)
        return render_template("run.html", run=run, log=queue.log_tail(run_id), week_state=week_state,
                               breaks_version=breaks_version,
                               has_zip=queue.zip_path(run_id).is_file(),
                               has_schedule=queue.final_schedule(run_id) is not None,
                               has_shortfall=queue.shortfall_schedule(run_id) is not None,
                               has_week=bool(kept_figures(run).get("intervals")),
                               resumable=_can_resume(run),
                               summary=ctx._walled(run, _run_figures(run)),
                               said=said,
                               why=outcome_view(found) if found else None,
                               eta=ctx._plan(store.list_runs()).get(run_id), now=time.time(), people=people,
                               start_options=start_choices(run["week_start"], run["week_start"]),
                               unit_label=ProgramBook(store).label(run["program"]) if run["program"] else "",
                               unit_groups=ctx._unit_choices(ProgramBook(store).tree()),
                               ready_version=(ctx._book().versions(run_id) or [None])[0] if run["mode"] == "READY" else None,
                               edit_open=request.args.get("edit") == "1", **extra)

    @app.route("/runs/<run_id>/status.json")
    @login_required
    def run_status(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        eta = ctx._plan(app.extensions["store"].list_runs()).get(run_id)
        return jsonify(status=run["status"], label=label(run),
                       message=run["message"], verdict=run["verdict"], exit_code=run["exit_code"],
                       stages=[{"label": name, "state": state} for name, state in stages(run)],
                       final=run["status"] not in IN_FLIGHT, log=_queue().log_tail(run_id, 80),
                       eta=eta, eta_text=eta_text(eta) if eta else "", started=run["started"],
                       server_time=time.time())

    @app.route("/runs/<run_id>/download")
    @login_required
    def run_download(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        path = _queue().zip_path(run_id)
        if not path.is_file():
            abort(404)
        stem = os.path.splitext(secure_filename(run["workbook"]))[0] or "results"
        _record("downloaded", run, subject=f"{stem}_results_{run_id}.zip")
        return send_file(path, as_attachment=True, download_name=f"{stem}_results_{run_id}.zip")

    @app.route("/runs/<run_id>/schedule")
    @login_required
    def run_schedule(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        path = _queue().final_schedule(run_id)
        if path is None:
            abort(404)
        _record("downloaded", run, subject=path.name)
        return send_file(path, as_attachment=True, download_name=path.name)

    @app.route("/runs/<run_id>/shortfall")
    @login_required
    def run_shortfall(run_id: str):  # type: ignore[no-untyped-def]
        """The engine's shortfall schedule, for review only (it misses listed minimums)."""
        run = _run_or_404(run_id)
        path = _queue().shortfall_schedule(run_id)
        if path is None:
            abort(404)
        _record("downloaded", run, subject=path.name)
        return send_file(path, as_attachment=True, download_name=path.name)

    @app.route("/runs/<run_id>/tag", methods=["POST"])
    @login_required
    def run_tag(run_id: str):  # type: ignore[no-untyped-def]
        """Change a run's details: its submitter the program and week, an admin everything (who submitted
        it, the workbook name too). Versions move with the run; consequences are shown before saving."""
        run = _run_or_404(run_id)
        admin = bool(g.user["is_admin"])
        if run["user_id"] != g.user["id"] and not admin:
            abort(403)
        store = app.extensions["store"]
        back = url_for("home") if request.form.get("back") == "home" else url_for("run_detail", run_id=run_id)
        week = request.form.get("week_start", "").strip()
        week_start = start_date(week) if week else ""
        if week_start is None:
            flash("Pick the date the schedule starts.")
            return redirect(back)
        new: Dict[str, Any] = {"program": clean_program(request.form.get("program", "")), "week_start": week_start}
        if new["program"] and new["program"] != run["program"] and not ctx._access().can_open(new["program"]):
            abort(403, description="That is not one of your programs")  # Phase AR
        if new["program"] and new["program"] != run["program"] and new["program"] not in unit_keys(store):
            flash(PICK_UNIT)  # picked from the list; a typed name would start a stray program
            return redirect(back)
        if "user_id" in request.form:
            new["user_id"] = request.form.get("user_id", type=int)
        if "workbook" in request.form:
            new["workbook"] = " ".join(request.form.get("workbook", "").split())
        for key in ("user_id", "workbook"):
            if key in new and new[key] != run[key] and not admin:
                abort(403)  # only an admin changes who submitted a run, or its name
        if new.get("user_id", run["user_id"]) != run["user_id"]:
            person = store.get_user(new["user_id"]) if new["user_id"] is not None else None
            if person is None or not person["active"]:
                flash("Pick someone on the team who is switched on.")
                return redirect(back)
        reason = " ".join(request.form.get("reason", "").split())[:200]
        try:
            found = preview_run_change(store, run, new)
            if not found["changes"]:
                flash("Nothing changed: the details are the same.")
                return redirect(back)
            confirmed = request.form.get("confirm") == "1"
            if found["needs_check"] and not (confirmed and reason):
                return _run_page(run, check=found, posted=new, reason=reason, reason_missing=confirmed)
            apply_run_change(store, run, new, g.user["id"], reason)
            flash("Details saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(back)

    ADVANCED_DEFAULTS = {"language_window": "workbook", "coverage_measure": "workbook", "stage": "FULL_SCHEDULE"}

    @app.route("/setup/with", methods=["GET", "POST"])
    @manager_required
    def with_setup():  # type: ignore[no-untyped-def]
        """Who an aux can be with, per program (Phase U): its departments and the people in each. Admins keep
        every program's; a supervisor their own programs' (the program check runs before every request)."""
        access = ctx._access()
        key = clean_program(request.values.get("program", "")) or ctx._left_menu().get("nav_unit", "")
        unit = access.book.unit(key) if key else None
        mine = [p for p in access.programs() if p["units"]]
        if unit is None or not access.can_open(key):
            if not mine:
                flash("There is no program to keep departments and people for yet.")
                return redirect(url_for("home"))
            return redirect(url_for("with_setup", program=mine[0]["units"][0]))
        program, book = unit["program"], ContactBook(app.extensions["store"])
        if request.method == "POST":
            action, pid, uid = request.form.get("action", ""), program["id"], g.user["id"]
            try:
                if action == "add":
                    dept, name = book.add(pid, request.form.get("department", ""), request.form.get("name", ""), uid)
                    said = f"Added {name} to {dept}." if name else f"Added the department {dept}."
                elif action == "paste":
                    depts, people = book.add_many(pid, request.form.get("lines", ""), uid)
                    said = (f"Added {depts} department{'s' if depts != 1 else ''} and {people} "
                            f"{'person' if people == 1 else 'people'}.")
                elif action == "remove_person":
                    dept, name = book.remove_person(pid, request.form.get("id", -1, type=int), uid)
                    said = f"Removed {name} from {dept}."
                elif action == "remove_department":
                    dept_id = request.form.get("id", -1, type=int)
                    if request.form.get("confirm") != "yes":  # Phase XY: the department and its people go only after a check
                        return redirect(url_for("with_setup", program=key, remove=dept_id) + f"#remove-{dept_id}", code=303)
                    dept = book.remove_department(pid, dept_id, uid)
                    said = f"Removed the department {dept} and its people."
                else:
                    raise ValueError("Pick what to do.")
                _record("with_list_changed", subject=program["name"], detail=said)
                flash(said)
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("with_setup", program=key), code=303)
        return render_template("with_setup.html", program=program, key=key, lists=book.lists(program["id"]),
                               choices=[(p["name"], p["units"][0]) for p in mine],
                               removing=request.args.get("remove", type=int))

    @app.route("/setup/channels", methods=["GET", "POST"])
    @manager_required
    def channel_setup():  # type: ignore[no-untyped-def]
        """Which channels each associate can work, per program (Phase V). Admins keep every program's; a supervisor
        their own programs' (the program check runs before every request)."""
        access = ctx._access()
        key = clean_program(request.values.get("program", "")) or ctx._left_menu().get("nav_unit", "")
        unit = access.book.unit(key) if key else None
        mine = [p for p in access.programs() if p["units"]]
        if unit is None or not access.can_open(key):
            if not mine:
                flash("There is no program to set channels for yet.")
                return redirect(url_for("home"))
            return redirect(url_for("channel_setup", program=mine[0]["units"][0]))
        program, people = unit["program"], ChannelPeople(app.extensions["store"])
        if request.method == "POST":
            action, pid = request.form.get("action", ""), program["id"]
            try:
                if action == "save":
                    rows = {}
                    for i in range(min(request.form.get("rows", 0, type=int), 3000)):
                        name = request.form.get(f"who-{i}", "")
                        if name:
                            rows[name] = "".join(c for c in "PCE" if request.form.get(f"{c}-{i}"))
                    changes = people.plan_changes(pid, rows)
                elif action == "paste":
                    changes = people.plan_changes(pid, people.read_paste(pid, request.form.get("lines", "")))
                else:
                    raise ValueError("Pick what to do.")
                count = people.apply(pid, changes, g.user["id"])
                if count:
                    said = f"Saved {count} change{'s' if count != 1 else ''}"
                    _record("channels_changed", subject=program["name"], detail=f"{said}: {people.describe(changes)}.")
                    flash(said + ".")
                else:
                    flash("Nothing changed.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("channel_setup", program=key), code=303)
        skills = people.skills(program["id"])
        rows = [{"name": n, "language": lang, "letters": can_work(skills, n)}
                for n, lang in people.roster(program["id"])]
        return render_template("channel_setup.html", program=program, key=key, rows=rows, words=channel_words,
                               choices=[(p["name"], p["units"][0]) for p in mine])

    @app.route("/runs/<run_id>/stop", methods=["POST"])
    @login_required
    def run_stop(run_id: str):  # type: ignore[no-untyped-def]
        run = ctx._run_or_404(run_id)
        stopped = ctx._queue().stop(run_id)
        if stopped:
            ctx._record("run_stopped", run)
        flash("Stopping safely; checkpoints are kept." if stopped else "This run is not running.")
        return redirect(url_for("run_detail", run_id=run_id))

    @app.route("/runs/<run_id>/resume", methods=["POST"])
    @login_required
    def run_resume(run_id: str):  # type: ignore[no-untyped-def]
        run = ctx._run_or_404(run_id)
        if not ctx._can_resume(run):  # Phase AC: the page offers it only then; a direct request gets the same answer
            flash("This run cannot be resumed: " + ("a readiness check builds no schedule. Start the run instead."
                                                    if run["mode"] == "SMOKE" else
                                                    "the engine found the workbook needs a change before it can be "
                                                    "scheduled. Fix the workbook and run it again."
                                                    if run["status"] in RESUMABLE else
                                                    f"it is {label(run).lower()}."))
            return redirect(url_for("run_detail", run_id=run_id))
        resumed = ctx._queue().resume(run_id)
        if resumed:
            ctx._record("run_resumed", run)
        flash("Queued again; it continues from its checkpoints." if resumed else "This run cannot be resumed.")
        return redirect(url_for("run_detail", run_id=run_id))

    ctx.ADVANCED_DEFAULTS = ADVANCED_DEFAULTS
    ctx._can_resume = _can_resume
    ctx._channel_lines = _channel_lines
    ctx._queue = _queue
    ctx._record = _record
    ctx._run_figures = _run_figures
    ctx._run_or_404 = _run_or_404
    ctx._unit_name = _unit_name
    ctx._upload_refused = _upload_refused
