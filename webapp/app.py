# © 2026 Omar Mokhtar. All rights reserved.
"""The team scheduler website: Flask application factory and routes."""
from __future__ import annotations

import os
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from .analytics import program_weeks, team
from .eta import queue_plan
from .auth import admin_required, check_csrf, csrf_token, load_user, login_required
from .program_page import build, overview, weeks_to_show
from .runs import MODES, OPTION_LABELS, RESUMABLE, RunQueue, parse_options, run_options
from .store import Store

COPYRIGHT = "© 2026 Omar Mokhtar. All rights reserved."
MIN_PASSWORD = 10
RUN_ID = re.compile(r"^[0-9a-f]{12}$")
STATUS_WORDS = {"CHECKING": "Checking", "REJECTED": "Rejected", "QUEUED": "Queued", "GATE": "Safety gate",
                "RUNNING": "Running", "SCORING": "Scoring", "DONE": "Approved", "REVIEW": "Needs review",
                "FAILED": "Not approved",
                "STOPPED": "Stopped", "INTERRUPTED": "Interrupted", "EXPIRED": "Expired"}
STAGES = ("Check", "Safety gate", "Schedule", "Scoring", "Result")
IN_FLIGHT = ("CHECKING", "QUEUED", "GATE", "RUNNING", "SCORING")


def label(run: Dict[str, Any]) -> str:
    """The word shown for a run's state (a passed readiness check built no schedule)."""
    if run["status"] == "DONE" and run.get("mode") == "SMOKE":
        return "Ready"
    return STATUS_WORDS.get(run["status"], run["status"])


def stages(run: Dict[str, Any]) -> list:
    """(label, state) for the five stage-bar segments; state is one of
    done | active | waiting | failed | halted | ok | '' (not reached)."""
    status = run["status"]
    if status in ("DONE", "REVIEW", "EXPIRED"):
        last = {"DONE": "ok", "REVIEW": "waiting", "EXPIRED": "done"}[status]
        return [(name, "done") for name in STAGES[:-1]] + [(label(run), last)]
    at, state = {"CHECKING": (0, "active"), "REJECTED": (0, "failed"), "QUEUED": (1, "waiting"),
                 "GATE": (1, "active"), "RUNNING": (2, "active"), "SCORING": (3, "active"),
                 "STOPPED": (2, "halted"), "INTERRUPTED": (2, "halted")}.get(status, (None, ""))
    if status == "FAILED":
        # No runner exit code: it never started (safety gate or website error).
        at, state = (1, "failed") if run.get("exit_code") is None else (4, "failed")
    if at is None:
        return [(name, "") for name in STAGES]
    labels = list(STAGES)
    if status == "QUEUED":
        labels[1] = "Queued"
    elif state == "halted":
        labels[2] = STATUS_WORDS[status]
    elif status == "FAILED" and at == 4:
        labels[4] = "Not approved"
    elif status == "REJECTED":
        labels[0] = "Rejected"
    return [(labels[i], "done" if i < at else state if i == at else "") for i in range(len(STAGES))]


def _secret_key(data_dir: Path) -> str:
    path = data_dir / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        os.chmod(path, 0o600)
    return path.read_text(encoding="utf-8").strip()


EGYPT = timezone(timedelta(hours=3))  # owner's rule: times in Egypt time (UTC+3)


def _when(epoch: Optional[float]) -> str:
    if not epoch:
        return ""
    return datetime.fromtimestamp(epoch, EGYPT).strftime("%a %d %b, %H:%M")


def duration(minutes: float) -> str:
    minutes = max(0, int(round(minutes)))
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h" + (f" {rest:02d} min" if rest else "")


def _clock(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, EGYPT).strftime("%H:%M")


def eta_text(eta: Optional[dict]) -> str:
    """One plain sentence about a run's place in line (empty for the running one)."""
    if not eta or eta["position"] == 0:
        return ""
    ahead = eta["ahead"]
    lead = "Next in line" if ahead == 0 else f"{ahead} run{'s' if ahead != 1 else ''} ahead of you"
    if eta["starts_in_min"] <= 0:
        return f"{lead}. Starts now."
    return (f"{lead}. Starts in about {duration(eta['starts_in_min'])} "
            f"(around {_clock(eta['starts_at'])} Egypt time), {eta['basis']}.")


USERNAME_RULE = "Usernames use letters, numbers, dots, dashes or underscores, with no spaces."


def username_problem(username: str) -> str:
    plain = username.replace(".", "").replace("_", "").replace("-", "")
    return "" if username and plain.isalnum() and plain.isascii() else USERNAME_RULE


def week_sunday(text: str) -> Optional[str]:
    """The Sunday that starts the week of a YYYY-MM-DD date, or None if it is not a date."""
    try:
        day = datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    return (day - timedelta(days=(day.weekday() + 1) % 7)).isoformat()


def next_sunday(today: Optional[date] = None) -> str:
    """The Sunday after today (Egypt time): the week a schedule is usually built for."""
    today = today or datetime.now(EGYPT).date()
    return (today + timedelta(days=(6 - today.weekday()) % 7 or 7)).isoformat()


def clean_program(text: str) -> str:
    return " ".join((text or "").split())[:80]


def password_problem(new: str, confirm: str, username: str) -> str:
    if len(new) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if new != confirm:
        return "The two new passwords are different."
    if username.lower() in new.lower():
        return "Do not put your username in your password."
    return ""


def create_app(config: Dict[str, Any]) -> Flask:
    app = Flask(__name__)
    data_dir = Path(config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=config.get("SECRET_KEY") or _secret_key(data_dir),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(config.get("HTTPS", True)),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    app.config.update({k: v for k, v in config.items() if k not in {"SECRET_KEY"}})
    app.extensions["store"] = Store(data_dir / "scheduler.db")
    if config.get("PACKAGE_ROOT"):
        queue = RunQueue(app.extensions["store"], Path(config["PACKAGE_ROOT"]),
                         Path(config.get("RUNS_DIR") or data_dir / "runs"),
                         runner_cmd=config.get("RUNNER_CMD"), parallel=int(config.get("PARALLEL", 1)),
                         check_cmd=config.get("CHECK_CMD"), score_cmd=config.get("SCORE_CMD"),
                         gate_cmd=config.get("GATE_CMD"))
        app.extensions["runs"] = queue
        if config.get("START_WORKER", True):
            queue.start()

    @app.before_request
    def _before() -> None:
        check_csrf()
        load_user()

    @app.after_request
    def _headers(response):  # type: ignore[no-untyped-def]
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'")
        return response

    @app.template_filter("num")
    def _num(value: float) -> str:
        value = round(float(value), 1)
        return str(int(value)) if value.is_integer() else str(value)

    @app.context_processor
    def _globals() -> Dict[str, Any]:
        return {"csrf_token": csrf_token, "copyright": COPYRIGHT, "user": g.get("user"),
                "status_words": STATUS_WORDS, "label": label, "modes": MODES, "stages": stages, "in_flight": IN_FLIGHT,
                "when": _when, "run_options": run_options, "option_labels": OPTION_LABELS,
                "eta_text": eta_text, "duration": duration, "clock": _clock}

    # ------------------------------------------------------------- sign in/out
    @app.route("/login", methods=["GET", "POST"])
    def login():  # type: ignore[no-untyped-def]
        error = ""
        if request.method == "POST":
            user, reason = app.extensions["store"].authenticate(request.form.get("username", ""),
                                                                request.form.get("password", ""))
            if user is not None:
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                csrf_token()
                target = request.args.get("next", "")
                return redirect(target if target.startswith("/") and not target.startswith("//") else url_for("home"))
            error = {"locked": "Too many wrong passwords: this account is locked for 15 minutes.",
                     "disabled": "This account is switched off. Ask your admin."}.get(
                         reason, "Wrong username or password.")
        return render_template("login.html", error=error)

    @app.route("/logout", methods=["POST"])
    def logout():  # type: ignore[no-untyped-def]
        session.clear()
        return redirect(url_for("login"))

    @app.route("/account/password", methods=["GET", "POST"])
    @login_required
    def change_password():  # type: ignore[no-untyped-def]
        error = ""
        if request.method == "POST":
            store = app.extensions["store"]
            if store.check_password(g.user["username"], request.form.get("current", "")) is None:
                error = "Your current password is not right."
            else:
                error = password_problem(request.form.get("new", ""), request.form.get("confirm", ""),
                                         g.user["username"])
            if not error:
                store.set_password(g.user["id"], request.form["new"], must_change=False)
                flash("Password changed.")
                return redirect(url_for("home"))
        return render_template("password.html", error=error, forced=bool(g.user["must_change"]))

    # ------------------------------------------------------------- admin
    @app.route("/admin/users", methods=["GET", "POST"])
    @admin_required
    def admin_users():  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        error = ""
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            if username_problem(username):
                error = USERNAME_RULE
            elif any(u["username"] == username for u in store.list_users()):
                error = f"{username} already exists."
            elif len(password) < MIN_PASSWORD:
                error = f"Give a temporary password of at least {MIN_PASSWORD} characters."
            else:
                store.add_user(username, request.form.get("display_name", ""), password,
                               is_admin=request.form.get("is_admin") == "on", must_change=True)
                flash(f"Added {username}. They choose their own password at first sign-in.")
                return redirect(url_for("admin_users"))
        return render_template("admin_users.html", users=store.list_users(), error=error)

    @app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
    @admin_required
    def admin_user_action(user_id: int, action: str):  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        target = store.get_user(user_id)
        if target is None:
            abort(404)
        if target["id"] == g.user["id"] and action == "disable":
            flash("You cannot switch off your own account.")
        elif action == "disable":
            store.set_active(user_id, False)
            flash(f"{target['username']} is switched off.")
        elif action == "enable":
            store.set_active(user_id, True)
            flash(f"{target['username']} is switched on.")
        elif action == "reset":
            temporary = secrets.token_urlsafe(9)
            store.set_password(user_id, temporary, must_change=True)
            flash(f"Temporary password for {target['username']}: {temporary} "
                  "(shown once; they choose their own at next sign-in).")
        else:
            abort(404)
        return redirect(url_for("admin_users"))

    # ------------------------------------------------------------- home
    def _plan(runs: list) -> Dict[str, dict]:
        queue = app.extensions.get("runs")
        if queue is None:
            return {}
        return queue_plan(runs, time.time(), os.cpu_count() or 1, queue.gate_pending())

    @app.route("/")
    @login_required
    def home():  # type: ignore[no-untyped-def]
        queue = app.extensions.get("runs")
        runs = app.extensions["store"].list_runs()
        plan = _plan(runs)
        summaries = {r["id"]: queue.summary(r["id"]) for r in runs} if queue else {}
        active = [r for r in runs if r["status"] in ("GATE", "RUNNING", "SCORING")]
        waiting = sorted((r for r in runs if r["status"] == "QUEUED"), key=lambda r: r["created"])
        latest = next((r for r in runs if r["status"] in ("DONE", "REVIEW") and summaries.get(r["id"])), None)
        known = sorted({r["program"] for r in runs if r.get("program")}, key=str.lower)
        return render_template("dashboard.html", runs=runs, queue=queue, plan=plan, summaries=summaries,
                               active=active, waiting=waiting, latest=latest,
                               latest_summary=summaries.get(latest["id"]) if latest else None,
                               now=time.time(), known_programs=known, next_sunday=next_sunday())

    # ------------------------------------------------------------- runs
    def _queue() -> RunQueue:
        queue = app.extensions.get("runs")
        if queue is None:
            abort(404)
        return queue

    def _run_or_404(run_id: str) -> Dict[str, Any]:
        run = app.extensions["store"].get_run(run_id) if RUN_ID.match(run_id) else None
        if run is None:
            abort(404)
        return run

    @app.route("/runs", methods=["POST"])
    @login_required
    def submit_run():  # type: ignore[no-untyped-def]
        queue = _queue()
        upload = request.files.get("workbook")
        mode = request.form.get("mode", "QUICK")
        name = os.path.basename((upload.filename or "") if upload else "")
        if not name.lower().endswith(".xlsx") or mode not in MODES:
            flash("Upload an Excel workbook (.xlsx) and pick a mode.")
            return redirect(url_for("home"))
        options, problem = parse_options(request.form)
        if problem:
            flash(problem)
            return redirect(url_for("home"))
        program = clean_program(request.form.get("program", ""))
        week = request.form.get("week_start", "").strip()
        week_start = week_sunday(week) if week else ""
        if week_start is None:
            flash("Give the schedule week as a date (the Sunday it starts).")
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
        run_id = queue.submit(g.user["id"], path, mode, name, options, program=program, week_start=week_start)
        return redirect(url_for("run_detail", run_id=run_id))

    @app.route("/runs/<run_id>")
    @login_required
    def run_detail(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        queue = _queue()
        return render_template("run.html", run=run, log=queue.log_tail(run_id),
                               has_zip=queue.zip_path(run_id).is_file(),
                               has_schedule=queue.final_schedule(run_id) is not None,
                               resumable=run["status"] in RESUMABLE, summary=queue.summary(run_id),
                               eta=_plan(app.extensions["store"].list_runs()).get(run_id), now=time.time())

    @app.route("/runs/<run_id>/status.json")
    @login_required
    def run_status(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        eta = _plan(app.extensions["store"].list_runs()).get(run_id)
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
        return send_file(path, as_attachment=True, download_name=f"{stem}_results_{run_id}.zip")

    @app.route("/runs/<run_id>/schedule")
    @login_required
    def run_schedule(run_id: str):  # type: ignore[no-untyped-def]
        _run_or_404(run_id)
        path = _queue().final_schedule(run_id)
        if path is None:
            abort(404)
        return send_file(path, as_attachment=True, download_name=path.name)

    @app.route("/runs/<run_id>/tag", methods=["POST"])
    @login_required
    def run_tag(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        if run["user_id"] != g.user["id"] and not g.user["is_admin"]:
            abort(403)
        week = request.form.get("week_start", "").strip()
        week_start = week_sunday(week) if week else ""
        if week_start is None:
            flash("Give the schedule week as a date (the Sunday it starts).")
        else:
            app.extensions["store"].update_run(run_id, program=clean_program(request.form.get("program", "")),
                                               week_start=week_start)
            flash("Program and week saved.")
        return redirect(url_for("run_detail", run_id=run_id))

    # ------------------------------------------------------------- analytics
    def _all_runs() -> list:
        return app.extensions["store"].list_runs(limit=100000)

    @app.route("/programs")
    @login_required
    def programs():  # type: ignore[no-untyped-def]
        return render_template("programs.html", rows=overview(program_weeks(_all_runs())))

    @app.route("/programs/<path:name>")
    @login_required
    def program(name: str):  # type: ignore[no-untyped-def]
        history = program_weeks(_all_runs()).get(name)
        if not history:
            abort(404)
        n = weeks_to_show(request.args.get("weeks", "12"))
        shown = history if n is None else history[-n:]
        return render_template("program.html", name=name, view=build(shown, history), weeks=n,
                               total=len(history), ranges=(4, 8, 12, 26, 52))

    @app.route("/team")
    @login_required
    def team_page():  # type: ignore[no-untyped-def]
        return render_template("team.html", people=team(_all_runs()))

    @app.route("/runs/<run_id>/stop", methods=["POST"])
    @login_required
    def run_stop(run_id: str):  # type: ignore[no-untyped-def]
        _run_or_404(run_id)
        flash("Stopping safely; checkpoints are kept." if _queue().stop(run_id) else "This run is not running.")
        return redirect(url_for("run_detail", run_id=run_id))

    @app.route("/runs/<run_id>/resume", methods=["POST"])
    @login_required
    def run_resume(run_id: str):  # type: ignore[no-untyped-def]
        _run_or_404(run_id)
        flash("Queued again; it continues from its checkpoints." if _queue().resume(run_id)
              else "This run cannot be resumed.")
        return redirect(url_for("run_detail", run_id=run_id))

    @app.errorhandler(500)
    def _server_error(err):  # type: ignore[no-untyped-def]
        return render_template("error.html", code=500,
                               message="Something went wrong on our side. Your runs are safe. Tell your admin."), 500

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def _error(err):  # type: ignore[no-untyped-def]
        messages = {403: "This page is for admins.", 404: "There is nothing here.",
                    413: "That file is larger than 25 MB."}
        text = messages.get(err.code) or getattr(err, "description", "") or "Something went wrong."
        return render_template("error.html", code=err.code, message=text), err.code

    return app
