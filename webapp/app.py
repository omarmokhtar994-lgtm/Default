# © 2026 Omar Mokhtar. All rights reserved.
"""The team scheduler website: Flask application factory and routes."""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from .adherence import interval_shrinkage, person_day, team as team_figures
from .analytics import program_weeks, team
from .attendance import ACTIVITY_KINDS, DayBook, hm, tomorrow_unchecked, week_start
from .day import AUX, MEASURES, STATUSES, BreakRefused, board
from .coach import actual_shrinkage, corrected_tab
from .eta import queue_plan
from .handover import note as handover_note
from .exports import KINDS as EXPORT_KINDS, build as build_export
from .outcome import cannot_schedule, read as read_outcome, view as outcome_view
from .auth import admin_required, check_csrf, csrf_token, load_user, login_required
from .program_page import build, overview, weeks_to_show
from .run_admin import apply_rename, apply_run_change, preview_rename, preview_run_change
from .schedules import ScheduleBook
from .versions import DAYS, with_notes
from .runs import MODES, OPTION_LABELS, RESUMABLE, RunQueue, parse_options, run_options
from .store import Store
from .week import view as week_view

COPYRIGHT = "© 2026 Omar Mokhtar. All rights reserved."
MIN_PASSWORD = 10
RUN_ID = re.compile(r"^[0-9a-f]{12}$")
STATUS_WORDS = {"CHECKING": "Checking", "REJECTED": "Rejected", "QUEUED": "Queued", "GATE": "Safety gate",
                "RUNNING": "Running", "SCORING": "Scoring", "DONE": "Approved", "REVIEW": "Needs review",
                "FAILED": "Not approved",
                "STOPPED": "Stopped", "INTERRUPTED": "Interrupted", "EXPIRED": "Expired"}
STAGES = ("Check", "Safety gate", "Schedule", "Scoring", "Result")
IN_FLIGHT = ("CHECKING", "QUEUED", "GATE", "RUNNING", "SCORING")


def engine_said(run: Dict[str, Any]) -> Dict[str, str]:
    """The engine's outcome kept on the run row (code, category, headline), or {}."""
    try:
        data = json.loads(run.get("engine_outcome") or "")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def kept_figures(run: Dict[str, Any]) -> Dict[str, Any]:
    """The compact figures kept on the run row, or {}."""
    try:
        data = json.loads(run.get("metrics") or "")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def label(run: Dict[str, Any]) -> str:
    """The word shown for a run's state (a passed readiness check built no schedule)."""
    if run.get("mode") == "SMOKE" and run["status"] in ("DONE", "FAILED"):
        return "Ready to run" if run["status"] == "DONE" else "Not ready"
    if run["status"] == "FAILED":
        said = engine_said(run)
        if cannot_schedule(said.get("code", ""), said.get("category", "")):
            return "Can't be scheduled"
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
        labels[4] = label(run)
    elif status == "REJECTED":
        labels[0] = "Rejected"
    return [(labels[i], "done" if i < at else state if i == at else "") for i in range(len(STAGES))]


def _secret_key(data_dir: Path) -> str:
    path = data_dir / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        os.chmod(path, 0o600)
    return path.read_text(encoding="utf-8").strip()


WORKBOOKS = ("Scheduler_Input_Blank.xlsx", "Scheduler_Input_Example.xlsx")
BACK = {"program": "programs"}  # where Back goes without browser history; every other page: home
THEMES = ("light", "dark")  # no cookie: follow the device's setting
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


def start_date(text: str) -> Optional[str]:
    """A schedule's first date as given (YYYY-MM-DD, any weekday), or None if it is not a date."""
    try:
        return datetime.strptime((text or "").strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def start_choices(around: str = "", keep: str = "") -> List[Tuple[str, str, int]]:
    """The start dates offered in a dropdown: Sundays and Mondays from 4 weeks before ``around`` (today
    when not given) to 10 weeks after, plus ``keep``; (value, label, weekday with Sunday 0), in date order."""
    centre = date.fromisoformat(around) if start_date(around) else datetime.now(EGYPT).date()
    days = {centre + timedelta(days=n) for n in range(-28, 71)}
    picked = {d for d in days if d.weekday() in (6, 0)}
    if start_date(keep):
        picked.add(date.fromisoformat(keep))
    return [(d.isoformat(), f"{d:%a %d %b %Y}", (d.weekday() + 1) % 7) for d in sorted(picked)]


def usual_start_days(runs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Each program's usual first weekday (Sunday 0), from its latest run with a start date."""
    found: Dict[str, int] = {}
    for r in sorted(runs, key=lambda r: r["created"]):
        if r.get("program") and start_date(r.get("week_start") or ""):
            found[r["program"]] = (date.fromisoformat(r["week_start"]).weekday() + 1) % 7
    return found


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
                         gate_cmd=config.get("GATE_CMD"), keep_days=int(config.get("RUN_FILES_DAYS", 30)))
        app.extensions["runs"] = queue
        # Schedule versions are checked with the installed package's independent validator.
        book = ScheduleBook(app.extensions["store"], data_dir,
                            Path(config.get("VALIDATOR_ROOT") or config["PACKAGE_ROOT"]))
        app.extensions["schedules"] = book
        queue.schedules = book
        app.extensions["days"] = queue.days = DayBook(app.extensions["store"], book)
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

    @app.template_filter("start_day")
    def _start_day(iso: str) -> str:
        """A schedule's first date in words: Monday 12 Oct."""
        found = start_date(iso or "")
        return f"{date.fromisoformat(found):%A %d %b}" if found else (iso or "")

    @app.template_filter("day_month")
    def _day_month(iso: str) -> str:
        try:
            return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b")
        except (TypeError, ValueError):
            return iso or ""

    @app.template_filter("fromjson")
    def _fromjson(text: str) -> Any:
        try:
            return json.loads(text or "{}")
        except ValueError:
            return {}

    @app.template_filter("hmm")
    def _hmm(hours: Optional[float]) -> str:
        """Signed hours as h:mm, the way RTA sheets show buffers: +0:38, -1:12."""
        if hours is None:
            return ""
        minutes = round(abs(float(hours)) * 60)
        return f"{'+' if hours >= 0 else '−'}{minutes // 60}:{minutes % 60:02d}"

    @app.template_filter("num")
    def _num(value: float) -> str:
        value = round(float(value), 1)
        return str(int(value)) if value.is_integer() else str(value)

    @app.context_processor
    def _globals() -> Dict[str, Any]:
        theme = request.cookies.get("theme", "")
        endpoint = request.endpoint or ""
        back = None if endpoint in ("home", "login", "static") else url_for(BACK.get(endpoint, "home"))
        return {"csrf_token": csrf_token, "copyright": COPYRIGHT, "user": g.get("user"),
                "theme": theme if theme in THEMES else "", "back": back,
                "status_words": STATUS_WORDS, "label": label, "modes": MODES, "stages": stages, "in_flight": IN_FLIGHT,
                "when": _when, "run_options": run_options, "option_labels": OPTION_LABELS,
                "eta_text": eta_text, "duration": duration, "clock": _clock}

    # ------------------------------------------------------------- theme
    @app.route("/theme", methods=["POST"])
    def set_theme():  # type: ignore[no-untyped-def]
        """Light, dark, or the device's own setting ("system"); kept in a cookie
        so the page is drawn in that theme from the first byte."""
        back = request.form.get("next") or "/"
        if not back.startswith("/") or back.startswith("//"):
            back = "/"  # only ever back to this site
        response = redirect(back)
        choice = request.form.get("theme", "")
        if choice in THEMES:
            response.set_cookie("theme", choice, max_age=365 * 86400, httponly=True, samesite="Lax",
                                secure=bool(config.get("HTTPS", True)))
        else:
            response.delete_cookie("theme")
        return response

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
                _record("user_added", subject=username,
                        detail="admin" if request.form.get("is_admin") == "on" else "")  # never the password
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
            _record("user_disabled", subject=target["username"])
            flash(f"{target['username']} is switched off.")
        elif action == "enable":
            store.set_active(user_id, True)
            _record("user_enabled", subject=target["username"])
            flash(f"{target['username']} is switched on.")
        elif action == "reset":
            temporary = secrets.token_urlsafe(9)
            store.set_password(user_id, temporary, must_change=True)
            _record("password_reset", subject=target["username"])  # never the password itself
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
        prefill = start_date(request.args.get("week", "")) or next_sunday()
        return render_template("dashboard.html", runs=runs, queue=queue, plan=plan, summaries=summaries,
                               active=active, waiting=waiting, latest=latest,
                               latest_summary=summaries.get(latest["id"]) if latest else None,
                               now=time.time(), known_programs=known,
                               prefill_program=clean_program(request.args.get("program", "")),
                               prefill_week=prefill, start_options=start_choices(prefill, prefill),
                               usual_start=usual_start_days(runs))

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
        week_start = start_date(week) if week else ""
        if week_start is None:
            flash("Pick the date the schedule starts.")
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
        _record("run_uploaded", app.extensions["store"].get_run(run_id), detail=mode)
        return redirect(url_for("run_detail", run_id=run_id))

    @app.route("/runs/<run_id>")
    @login_required
    def run_detail(run_id: str):  # type: ignore[no-untyped-def]
        return _run_page(_run_or_404(run_id))

    def _run_page(run: Dict[str, Any], **extra: Any):  # type: ignore[no-untyped-def]
        """The run page; ``extra`` carries a change to check before saving (run_tag)."""
        run_id = run["id"]
        queue = _queue()
        store = app.extensions["store"]
        people = [u for u in store.list_users() if u["active"] or u["id"] == run["user_id"]] \
            if g.user["is_admin"] else []
        said = engine_said(run)
        found = read_outcome(queue.results_dir(run_id))
        fixed_input = cannot_schedule(said.get("code", ""), said.get("category", ""))
        return render_template("run.html", run=run, log=queue.log_tail(run_id),
                               has_zip=queue.zip_path(run_id).is_file(),
                               has_schedule=queue.final_schedule(run_id) is not None,
                               has_shortfall=queue.shortfall_schedule(run_id) is not None,
                               has_week=bool(kept_figures(run).get("intervals")),
                               resumable=run["status"] in RESUMABLE and not fixed_input and run["mode"] != "SMOKE",
                               summary=queue.summary(run_id), said=said,
                               why=outcome_view(found) if found else None,
                               eta=_plan(store.list_runs()).get(run_id), now=time.time(), people=people,
                               start_options=start_choices(run["week_start"], run["week_start"]),
                               known_programs=sorted({r["program"] for r in store.list_runs(limit=100000)
                                                      if r["program"]}, key=str.lower), **extra)

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
        week = request.form.get("week_start", "").strip()
        week_start = start_date(week) if week else ""
        if week_start is None:
            flash("Pick the date the schedule starts.")
            return redirect(url_for("run_detail", run_id=run_id))
        new: Dict[str, Any] = {"program": clean_program(request.form.get("program", "")), "week_start": week_start}
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
                return redirect(url_for("run_detail", run_id=run_id))
        reason = " ".join(request.form.get("reason", "").split())[:200]
        try:
            found = preview_run_change(store, run, new)
            if not found["changes"]:
                flash("Nothing changed: the details are the same.")
                return redirect(url_for("run_detail", run_id=run_id))
            confirmed = request.form.get("confirm") == "1"
            if found["needs_check"] and not (confirmed and reason):
                return _run_page(run, check=found, posted=new, reason=reason, reason_missing=confirmed)
            apply_run_change(store, run, new, g.user["id"], reason)
            flash("Details saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("run_detail", run_id=run_id))

    @app.route("/programs/rename", methods=["POST"])
    @admin_required
    def program_rename():  # type: ignore[no-untyped-def]
        """Rename a program everywhere, or merge it into another: shown first, saved with a reason."""
        store = app.extensions["store"]
        old, new = request.form.get("old", ""), clean_program(request.form.get("new", ""))
        reason = " ".join(request.form.get("reason", "").split())[:200]
        known = program_weeks(_all_runs())
        try:
            found = preview_rename(store, old, new)
            confirmed = request.form.get("confirm") == "1"
            if confirmed and reason and not found["clashes"]:
                apply_rename(store, old, new, g.user["id"], reason)
                flash(f"{'Merged' if found['merge'] else 'Renamed'} {old} {'into' if found['merge'] else 'to'} "
                      f"{found['new']}.")
                known = program_weeks(_all_runs())
                return redirect(url_for("program", name=found["new"]) if found["new"] in known else url_for("programs"))
            return render_template("program_rename.html", found=found, reason=reason,
                                   reason_missing=confirmed and not reason,
                                   back=url_for("program", name=old) if old in known else url_for("programs"))
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("program", name=old) if old in known else url_for("programs"))

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
        others = sorted({r["program"] for r in _all_runs() if r["program"] and r["program"] != name}, key=str.lower)
        return render_template("program.html", name=name, view=build(shown, history), weeks=n,
                               total=len(history), ranges=(4, 8, 12, 26, 52), others=others)

    def _week_page(run: Optional[Dict[str, Any]], side: str, program: str, week: str,
                   history: Dict[str, list]):  # type: ignore[no-untyped-def]
        figures = kept_figures(run or {})
        intervals = figures.get("intervals")
        weeks = [w["week"] for w in reversed(history.get(program, []))]
        return render_template("week.html", run=run, view=week_view(intervals, side) if intervals else None,
                               side=side, program=program, week=week, programs=sorted(history, key=str.lower),
                               weeks=weeks, figures=figures)

    @app.route("/runs/<run_id>/week")
    @login_required
    def run_week(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        side = "before" if request.args.get("side") == "before" else "after"
        return _week_page(run, side, run.get("program") or "", run.get("week_start") or "",
                          program_weeks(_all_runs()))

    @app.route("/week")
    @login_required
    def week_page():  # type: ignore[no-untyped-def]
        """A program's week: the run that counts for it (the latest finished, as on the program page)."""
        history = program_weeks(_all_runs())
        side = "before" if request.args.get("side") == "before" else "after"
        program = clean_program(request.args.get("program", ""))
        week = start_date(request.args.get("week", "")) or ""
        if not program and history:
            latest = max((w for rows in history.values() for w in rows), key=lambda w: w["finished"] or 0)
            program, week = latest["program"], latest["week"]
        rows = history.get(program, [])
        if program and not week and rows:
            week = rows[-1]["week"]
        row = next((w for w in rows if w["week"] == week), None) or next(  # else the week holding that date
            (w for w in reversed(rows) if week and start_date(w["week"]) and
             0 <= (date.fromisoformat(week) - date.fromisoformat(w["week"])).days <= 6), None)
        week = row["week"] if row else week
        run = app.extensions["store"].get_run(row["run_id"]) if row else None
        return _week_page(run, side, program, week, history)

    # ------------------------------------------------------------- schedule versions (Phase N)
    def _book() -> ScheduleBook:
        book = app.extensions.get("schedules")
        if book is None:
            abort(404)
        return book

    def _version_or_404(schedule_id: int) -> Dict[str, Any]:
        row = app.extensions["store"].get_schedule(schedule_id)
        if row is None:
            abort(404)
        return row

    def _may_set_in_use(row: Dict[str, Any]) -> bool:
        run = app.extensions["store"].get_run(row["run_id"]) or {}
        return bool(g.user["is_admin"]) or run.get("user_id") == g.user["id"]

    @app.route("/runs/<run_id>/schedules")
    @login_required
    def run_schedules(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        book, queue = _book(), _queue()
        versions = book.versions(run_id)
        if not versions and run["status"] in ("DONE", "REVIEW") and run["mode"] != "SMOKE":
            queue.keep_schedules(run_id)  # a run finished before versions existed, files still here
            versions = book.versions(run_id)
        chosen = request.args.get("v", type=int)
        current = next((v for v in versions if v["id"] == chosen), None) or next(
            (v for v in versions if v["in_use"]), None) or (versions[0] if versions else None)
        view = book.view(current["id"]) if current else None
        counts = {v["id"]: book.view(v["id"]) for v in versions} if versions else {}
        return render_template("schedules.html", run=run, versions=versions, current=current, view=view,
                               counts=counts, may_set_in_use=bool(current) and _may_set_in_use(current),
                               days=DAYS)

    @app.route("/schedules/<int:schedule_id>/check", methods=["POST"])
    @login_required
    def schedule_check(schedule_id: int):  # type: ignore[no-untyped-def]
        _version_or_404(schedule_id)
        try:
            found = _book().check(schedule_id, request.form.get("associate", ""), request.form.get("day", ""),
                                  request.form.get("value", ""))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(severity=found["severity"],
                       added=[{"severity": p["severity"], "text": p["text"]} for p in found["added"]],
                       metrics={k: found["metrics"].get(k) for k in ("active_intervals", "after_100", "before_100")})

    @app.route("/schedules/<int:schedule_id>/change", methods=["POST"])
    @login_required
    def schedule_change(schedule_id: int):  # type: ignore[no-untyped-def]
        row = _version_or_404(schedule_id)
        name, day, value = (request.form.get(k, "") for k in ("associate", "day", "value"))
        reason = " ".join(request.form.get("reason", "").split())[:300]
        book = _book()
        try:
            if not reason and book.check(schedule_id, name, day, value)["added"]:
                return jsonify(error="This change breaks a rule or adds a warning: give a reason to keep it."), 400
            saved = book.change(schedule_id, g.user["id"], name, day, value, reason)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(schedule_id=saved, url=url_for("run_schedules", run_id=row["run_id"], v=saved))

    @app.route("/schedules/<int:schedule_id>/swap-check", methods=["POST"])
    @login_required
    def schedule_swap_check(schedule_id: int):  # type: ignore[no-untyped-def]
        _version_or_404(schedule_id)
        try:
            found = _book().check_swap(schedule_id, request.form.get("first", ""), request.form.get("second", ""))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(severity=found["severity"],
                       added=[{"severity": p["severity"], "text": p["text"]} for p in found["added"]])

    @app.route("/schedules/<int:schedule_id>/swap", methods=["POST"])
    @login_required
    def schedule_swap(schedule_id: int):  # type: ignore[no-untyped-def]
        row = _version_or_404(schedule_id)
        first, second = request.form.get("first", ""), request.form.get("second", "")
        reason = " ".join(request.form.get("reason", "").split())[:300]
        book = _book()
        try:
            if not reason and book.check_swap(schedule_id, first, second)["added"]:
                return jsonify(error="This swap breaks a rule or adds a warning: give a reason to keep it."), 400
            saved = book.swap(schedule_id, g.user["id"], first, second, reason)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(schedule_id=saved, url=url_for("run_schedules", run_id=row["run_id"], v=saved))

    @app.route("/schedules/<int:schedule_id>/in-use", methods=["POST"])
    @login_required
    def schedule_in_use(schedule_id: int):  # type: ignore[no-untyped-def]
        row = _version_or_404(schedule_id)
        if not _may_set_in_use(row):
            abort(403)
        _book().set_in_use(schedule_id, g.user["id"])
        flash(f"{row['label']} is now the schedule in use.")
        return redirect(url_for("run_schedules", run_id=row["run_id"], v=schedule_id))

    @app.route("/schedules/<int:schedule_id>/download")
    @login_required
    def schedule_download(schedule_id: int):  # type: ignore[no-untyped-def]
        row = _version_or_404(schedule_id)
        book = _book()
        stem = secure_filename(f"{row['program'] or row['run_id']}_{row['week_start']}_{row['label']}") or "schedule"
        _record("downloaded", program=row["program"], week_start=row["week_start"], run_id=row["run_id"],
                schedule_id=schedule_id, subject=f"{stem}.xlsx")
        if row["kind"] != "edited":
            return send_file(book.path(schedule_id), as_attachment=True, download_name=f"{stem}.xlsx")
        return send_file(with_notes(book.path(schedule_id), book.view(schedule_id)), as_attachment=True,
                         download_name=f"{stem}.xlsx")

    @app.route("/schedules/<int:schedule_id>/week")
    @login_required
    def schedule_week(schedule_id: int):  # type: ignore[no-untyped-def]
        row = _version_or_404(schedule_id)
        intervals = json.loads(row["checks"] or "{}").get("intervals") or []
        side = "before" if request.args.get("side") == "before" else "after"
        run = app.extensions["store"].get_run(row["run_id"])
        history = program_weeks(_all_runs())
        return render_template("week.html", run=run, view=week_view(intervals, side) if intervals else None,
                               side=side, program=row["program"], week=row["week_start"],
                               programs=sorted(history, key=str.lower),
                               weeks=[w["week"] for w in reversed(history.get(row["program"], []))],
                               figures=kept_figures(run or {}), version=row)

    # ------------------------------------------------------------- the day (Phase N)
    def _days() -> DayBook:
        days = app.extensions.get("days")
        if days is None:
            abort(404)
        return days

    def _date(text: str) -> Optional[date]:
        try:
            return datetime.strptime((text or "").strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    @app.route("/day")
    @login_required
    def day_page():  # type: ignore[no-untyped-def]
        """A program's day from the schedule in use: who is on the floor, attendance, actual breaks."""
        days = _days()
        programs = days.programs()
        on = _date(request.args.get("date", "")) or datetime.now(EGYPT).date()
        program = clean_program(request.args.get("program", ""))
        if not program and programs:
            program = next((p for p in programs if days.version(p, on)[0]), programs[0])
        measure = request.args.get("measure", "")
        measure = measure if measure in MEASURES else "interval"
        tab = request.args.get("view", "")
        tab = tab if tab in ("board", "adherence", "meeting", "cover", "replan") else "timeline"
        problem = ""
        try:
            page = days.page(program, on, measure) if program else None
        except ValueError as exc:  # said on the page, not a server error
            page, problem = None, str(exc)
        people = shrink = whole = None
        finder: Dict[str, Any] = {}
        cover = None
        if page and tab == "meeting":
            finder = {"who": request.args.getlist("who"), "minutes": request.args.get("minutes", 30, type=int),
                      "from": request.args.get("from", "09:00"), "to": request.args.get("to", "18:00"),
                      "kind": request.args.get("kind", "Meeting"), "billable": request.args.get("billable") == "1"}
            if finder["who"]:
                try:
                    finder["slots"] = days.meeting_slots(program, on, finder["who"], finder["minutes"], finder["from"],
                                                         finder["to"], finder["billable"], measure)
                except ValueError as exc:
                    finder["error"] = str(exc)
        clock_now = datetime.now(EGYPT)
        from_now = clock_now.hour * 60 + clock_now.minute if clock_now.date() == on else 0
        if page and tab == "cover":
            cover = days.offers(page, from_now)
        proposal = days.replan(page, from_now) if page and tab == "replan" else None
        cover_panel = None
        if page and tab == "board" and request.args.get("cover", type=int) is not None:
            try:
                cover_panel = days.cover_offers(page, request.args.get("cover", type=int))
            except ValueError as exc:
                flash(str(exc))
        if page and tab == "adherence":
            v = page["view"]
            people = sorted((person_day(v, l["name"]) for l in v["lanes"] if any(x["offset"] == 0 for x in l["segments"])),
                            key=lambda r: (r["adherence"] is not None, r["adherence"] or 0, r["name"]))
            whole = team_figures(people)
            shrink = interval_shrinkage(v, page["inputs"], page["day"])
        return render_template("day.html", page=page, problem=problem, program=program, programs=programs, on=on,
                               people=people, whole=whole, shrink=shrink, finder=finder, cover=cover,
                               proposal=proposal, from_now=from_now, cover_panel=cover_panel,
                               tomorrow_unchecked=tomorrow_unchecked(on) if on else "",
                               activity_kinds=ACTIVITY_KINDS,
                               measure=measure,
                               measures=MEASURES, tab=tab, statuses=STATUSES, aux=sorted(AUX), hm=hm,
                               rows=board(page["view"]) if page and tab == "board" else None, week_of=week_start(on),
                               earlier=on - timedelta(days=1), later=on + timedelta(days=1))

    def _day_form():  # type: ignore[no-untyped-def]
        on = _date(request.form.get("date", ""))
        if on is None:
            raise ValueError("Pick a day.")
        return clean_program(request.form.get("program", "")), on, request.form.get("associate", "").strip()

    def _break_idx() -> int:
        try:
            return int(request.form.get("idx", ""))
        except ValueError:
            raise ValueError("Pick a break.") from None

    @app.route("/day/attendance", methods=["POST"])
    @login_required
    def day_attendance():  # type: ignore[no-untyped-def]
        try:
            program, on, name = _day_form()
            _days().set_status(program, on, name, request.form.get("status", ""), g.user["id"],
                               start=request.form.get("from", ""), end=request.form.get("to", ""),
                               billable=request.form.get("billable") == "1")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(ok=True)

    @app.route("/day/break", methods=["POST"])
    @login_required
    def day_break():  # type: ignore[no-untyped-def]
        try:
            program, on, name = _day_form()
            at = request.form.get("at", "").strip() or None
            _days().move_break(program, on, name, _break_idx(), at, g.user["id"])
        except ValueError as exc:  # BreakRefused is a ValueError
            return jsonify(error=str(exc)), 400
        return jsonify(ok=True)

    def _back_to_day(program: str, on: Optional[date], view: str, cover: str = ""):  # type: ignore[no-untyped-def]
        args = {"program": program, "date": on.isoformat() if on else None,
                "view": view if view in ("board", "adherence", "meeting", "cover", "replan") else None,
                "cover": cover if cover.isdigit() and view == "board" else None}
        if args["cover"]:
            args["_anchor"] = f"row-{args['cover']}"
        return redirect(url_for("day_page", **{k: v for k, v in args.items() if v}), code=303)

    @app.route("/day/replan/apply", methods=["POST"])
    @login_required
    def day_replan_apply():  # type: ignore[no-untyped-def]
        """Keep the autopilot's moves the user approved (each checked again)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            moves = []
            for item in request.form.getlist("move"):
                name, idx, start = item.rsplit("|", 2)
                moves.append((name, int(idx), int(start)))
            done = _days().apply_replan(program, on, moves, g.user["id"])
            flash(f"Moved {done} break{'s' if done != 1 else ''}.")
        except ValueError as exc:
            flash(f"Stopped: {exc} The moves before it were kept; open the autopilot again for a fresh proposal.")
        return _back_to_day(program, on, "")

    @app.route("/day/handover")
    @login_required
    def day_handover():  # type: ignore[no-untyped-def]
        """The shift handover note: printable, one page."""
        on = _date(request.args.get("date", "")) or datetime.now(EGYPT).date()
        program = clean_program(request.args.get("program", ""))
        measure = request.args.get("measure", "") if request.args.get("measure", "") in MEASURES else "interval"
        try:
            found = handover_note(_days(), program, on, measure) if program else None
        except ValueError as exc:
            found, problem = None, str(exc)
        else:
            problem = "" if found else f"No schedule for {program or 'this program'} on {on:%d %b}."
        return render_template("handover.html", n=found, problem=problem, program=program, on=on, hm=hm,
                               measures=MEASURES, measure=measure)

    @app.route("/day/wallboard")
    @login_required
    def day_wallboard():  # type: ignore[no-untyped-def]
        """For the floor's screen: now and the next three intervals, breaks now and next; reloads every minute."""
        clock = datetime.now(EGYPT)
        on = _date(request.args.get("date", "")) or clock.date()
        at = request.args.get("at", "")
        found = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", at)
        now = int(found.group(1)) * 60 + int(found.group(2)) if found else clock.hour * 60 + clock.minute
        days = _days()
        programs = days.programs()
        program = clean_program(request.args.get("program", "")) or (programs[0] if programs else "")
        page = days.page(program, on) if program else None
        board_now = None
        if page:
            v = page["view"]
            step = v["interval"]
            first = now - now % step
            rows = [c for c in board(v) if first <= c["t"] < first + 4 * step]
            on_break, soon = [], []
            for lane in v["lanes"]:
                for seg in lane["segments"]:
                    if seg["status"] in ("Unplanned leave", "Sick"):
                        continue
                    for b in seg["breaks"]:
                        if b["start"] <= now < b["start"] + b["minutes"]:
                            on_break.append({"name": lane["name"], "kind": b["kind"], "until": b["start"] + b["minutes"]})
                        elif now < b["start"] <= now + 30:
                            soon.append({"name": lane["name"], "kind": b["kind"], "at": b["start"]})
            langs = [{"name": lang["name"], "count": next((c["count"] for c in lang["cells"] if c["t"] == first), None),
                      "cls": next((c["cls"] for c in lang["cells"] if c["t"] == first), "none")} for lang in v["languages"]]
            board_now = {"rows": rows, "on_break": sorted(on_break, key=lambda x: x["until"]),
                         "soon": sorted(soon, key=lambda x: x["at"]), "langs": [x for x in langs if x["count"] is not None],
                         "tiles": v["tiles"]}
        return render_template("wallboard.html", w=board_now, program=program, on=on, now=now, hm=hm,
                               live=not found and on == clock.date())

    @app.route("/day/activity", methods=["POST"])
    @login_required
    def day_activity():  # type: ignore[no-untyped-def]
        """Record an activity (aux, overtime, VTO) from a form; back to the day with what happened."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            name, kind = request.form.get("associate", "").strip(), request.form.get("kind", "")
            _days().add_activity(program, on, name, kind, request.form.get("from", ""), request.form.get("to", ""),
                                 g.user["id"], billable=request.form.get("billable") == "1",
                                 note=request.form.get("note", ""))
            flash(f"Recorded: {name}, {'day off cancelled (called in)' if kind == 'Called in' else kind.lower()}.")
            if kind in ("Overtime", "Called in") and _days().next_week_unknown(program, on):
                flash(tomorrow_unchecked(on))
        except ValueError as exc:
            flash(str(exc))
        return _back_to_day(program, on, request.form.get("view", ""), request.form.get("cover", ""))

    @app.route("/day/activity/cancel", methods=["POST"])
    @login_required
    def day_activity_cancel():  # type: ignore[no-untyped-def]
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _days().cancel_activity(program, on, request.form.get("id", 0, type=int), g.user["id"])
            flash("Cancelled.")
        except ValueError as exc:
            flash(str(exc))
        return _back_to_day(program, on, request.form.get("view", ""))

    @app.route("/day/book", methods=["POST"])
    @login_required
    def day_book():  # type: ignore[no-untyped-def]
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        who = request.form.getlist("who")
        try:
            if on is None:
                raise ValueError("Pick a day.")
            start, minutes = request.form.get("start", -1, type=int), request.form.get("minutes", 0, type=int)
            kind = request.form.get("kind", "Meeting")
            _days().book_session(program, on, who, start, minutes, kind, g.user["id"],
                                 billable=request.form.get("billable") == "1")
            flash(f"Booked: {kind.lower()} {hm(start)} to {hm(start + minutes)} for {', '.join(who)}.")
        except ValueError as exc:
            flash(str(exc))
        return _back_to_day(program, on, "meeting")

    @app.route("/day/break-advice", methods=["POST"])
    @login_required
    def day_break_advice():  # type: ignore[no-untyped-def]
        measure = request.form.get("measure", "")
        try:
            program, on, name = _day_form()
            found = _days().break_advice(program, on, name, _break_idx(), request.form.get("at", ""),
                                         measure if measure in MEASURES else "interval")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(found)

    # ------------------------------------------------------------- exports (Phase O)
    def _export_args() -> Dict[str, Any]:
        today = datetime.now(EGYPT).date()
        start = _date(request.args.get("from", "")) or today.replace(day=1)
        end = _date(request.args.get("to", "")) or today
        program = clean_program(request.args.get("program", "")) or None
        return {"start": start, "end": end, "program": program, "user_id": request.args.get("user", type=int),
                "measure": request.args.get("measure", "") if request.args.get("measure", "") in MEASURES else "interval"}

    def _exports_page(error: str = "", status: int = 200):  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        a = _export_args()
        today = datetime.now(EGYPT).date()
        sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        presets = [("Today", today, today), ("This week", sunday, sunday + timedelta(days=6)),
                   ("This month", first, today), ("Last month", last_month_end.replace(day=1), last_month_end)]
        lo = datetime(a["start"].year, a["start"].month, a["start"].day, tzinfo=EGYPT).timestamp()
        hi = datetime(a["end"].year, a["end"].month, a["end"].day, tzinfo=EGYPT).timestamp() + 86400
        found = {
            "attendance": store.attendance_between(a["start"].isoformat(), a["end"].isoformat(), a["program"], a["user_id"]),
            "activity": store.day_log_between(a["start"].isoformat(), a["end"].isoformat(), a["program"], a["user_id"]),
            "changes": store.changes_between(lo, hi, a["program"], a["user_id"]),
            "versions": store.list_events(lo, hi, a["program"], a["user_id"], ["version_created", "set_in_use"]),
            "runs": store.runs_between(lo, hi, a["program"], a["user_id"]),
        }
        counts = {k: (len(rows), max(rows, key=lambda r: r.get("at") or r.get("created") or 0) if rows else None)
                  for k, rows in found.items()}
        return render_template("exports.html", kinds=EXPORT_KINDS, counts=counts, presets=presets, error=error,
                               programs=_days().programs() if app.extensions.get("days") else [],
                               users=store.list_users(), measures=MEASURES, **a), status

    def _coach_args() -> Dict[str, Any]:
        days = _days()
        programs = days.programs()
        today = datetime.now(EGYPT).date()
        program = clean_program(request.args.get("program", "")) or (programs[0] if programs else "")
        start = _date(request.args.get("from", "")) or today - timedelta(days=27)
        end = _date(request.args.get("to", "")) or today
        if end < start or (end - start).days > 400:
            start, end = end - timedelta(days=27), end
        return {"program": program, "programs": programs, "start": start, "end": end}

    @app.route("/coach")
    @login_required
    def coach_page():  # type: ignore[no-untyped-def]
        a = _coach_args()
        found = actual_shrinkage(_days(), a["program"], a["start"], a["end"]) if a["program"] else None
        return render_template("coach.html", found=found, days=DAYS, hm=hm, **a)

    @app.route("/coach/download")
    @login_required
    def coach_download():  # type: ignore[no-untyped-def]
        a = _coach_args()
        if not a["program"]:
            abort(404)
        found = actual_shrinkage(_days(), a["program"], a["start"], a["end"])
        name = secure_filename(f"Shrinkage_{found['interval']}_Min_{a['program']}_{a['start']}_to_{a['end']}.xlsx")
        _record("downloaded", program=a["program"], subject=name)
        return send_file(corrected_tab(found, a["program"]), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/exports")
    @login_required
    def exports_page():  # type: ignore[no-untyped-def]
        return _exports_page()

    @app.route("/exports/download")
    @login_required
    def exports_download():  # type: ignore[no-untyped-def]
        a = _export_args()
        kinds = request.args.getlist("kind")
        fmt = request.args.get("format", "xlsx")
        try:
            data, name, mime = build_export(app.extensions["store"], _days(), a["start"], a["end"], kinds, fmt,
                                            a["program"], a["user_id"], g.user["display_name"], a["measure"])
        except ValueError as exc:  # said on the page
            return _exports_page(str(exc), 400)
        _record("exported", subject=name, program=a["program"] or "",
                detail=f"{a['start']} to {a['end']}: {', '.join(k for k in EXPORT_KINDS if k in kinds)}")
        return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=name)

    @app.route("/team")
    @login_required
    def team_page():  # type: ignore[no-untyped-def]
        return render_template("team.html", people=team(_all_runs()))

    @app.route("/workbooks/<name>")
    @login_required
    def workbook(name: str):  # type: ignore[no-untyped-def]
        """The clean input workbooks (tools/build_web_workbooks.py); nothing else."""
        if name not in WORKBOOKS:
            abort(404)
        return send_file(Path(__file__).with_name("workbooks") / name, as_attachment=True, download_name=name)

    @app.route("/runs/<run_id>/start", methods=["POST"])
    @login_required
    def run_start(run_id: str):  # type: ignore[no-untyped-def]
        """Start a run of this run's workbook (after a readiness check: the real run)."""
        run = _run_or_404(run_id)
        mode = request.form.get("mode", "")
        if run["status"] in IN_FLIGHT or mode not in MODES:
            flash("Pick Quick, Deep or Overnight to start the run.")
            return redirect(url_for("run_detail", run_id=run_id))
        new_id = _queue().start_from(run_id, g.user["id"], mode)
        if new_id is None:
            flash(f"The workbook of this check is no longer on the server (files are kept {_queue().keep_days} days). "
                  "Upload it again.")
            return redirect(url_for("run_detail", run_id=run_id))
        _record("run_started", app.extensions["store"].get_run(new_id), detail=f"{mode}, from the check {run_id}")
        return redirect(url_for("run_detail", run_id=new_id))

    @app.route("/runs/<run_id>/stop", methods=["POST"])
    @login_required
    def run_stop(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        stopped = _queue().stop(run_id)
        if stopped:
            _record("run_stopped", run)
        flash("Stopping safely; checkpoints are kept." if stopped else "This run is not running.")
        return redirect(url_for("run_detail", run_id=run_id))

    @app.route("/runs/<run_id>/resume", methods=["POST"])
    @login_required
    def run_resume(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        resumed = _queue().resume(run_id)
        if resumed:
            _record("run_resumed", run)
        flash("Queued again; it continues from its checkpoints." if resumed else "This run cannot be resumed.")
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
