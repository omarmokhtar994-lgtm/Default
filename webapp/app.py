# © 2026 Omar Mokhtar. All rights reserved.
"""The team scheduler website: Flask application factory and routes."""
from __future__ import annotations

import copy
import io
import json
import os
import re
import secrets
import shutil
import tempfile
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from flask import (Flask, abort, flash, g, has_request_context, jsonify, redirect, render_template, request, send_file,
                   session, url_for)
from flask.sessions import SecureCookieSessionInterface
from openpyxl.utils.exceptions import InvalidFileException
from werkzeug.utils import secure_filename

from .adherence import interval_shrinkage, person_day, team as team_figures
from .analytics import program_weeks, team
from .channel_hours import combine, week_hours
from .attendance import (ACTIVITY_KINDS, ADD_KINDS, COVER_ROLES, DAY_OFF, DayBook, aux_details, hm, pick_version, plain_hm, tomorrow_unchecked, week_start,
                         with_text)
from .break_plan import check_row, floor, slots_for, suggest
from .channel_fair import fairness
from .channel_page import (FULL as FULL_DAYS, NAMES as CHANNEL_NAMES, apply_edit, before as channel_before,
                           carry as channel_carry, coverage as channel_coverage, current as channel_current,
                           grid as channel_grid, people_for, planned_anything)
from .channel_people import ChannelPeople, can_work, channel_words
from .channel_plan import NoPlan, plan_day, score_day
from .channel_template import channel_workbook
from .channels import check_lines, has_channel_needs, read_channels, requirement_tab
from .clock import minute_now, EGYPT, HOME, SHOWN, ZONES, moved_text, pick_zone, rta_shift, shift as zone_shift, shown, to_schedule, zone_label
from .permissions import CATALOGUE as PERMISSIONS, ENDPOINTS as PERMISSION_ENDPOINTS, ROLE_NAMES, allowed, matrix
from .day import ABSENT as ABSENT_STATES, AUX, EXTRA_BREAKS, MEASURES, OVERTIME_MAX, STATUSES, channel_letters, BreakRefused, at_target, board, glance, hover_tips, my_day, my_items, now_panel, read_inputs, shift_groups, window_view
from .coach import actual_shrinkage, corrected_tab
from .leave import KINDS as LEAVE_KINDS, LeaveBook
from .swaps import SwapBook
from .shrinkage import ITEMS as SHRINKAGE_ITEMS, day_shrinkage, mapping_from_form, read_mapping
from .contacts import ContactBook, pick_contact
from .eta import queue_plan
from .handover import note as handover_note
from .exports import EXPORT_SECONDS, KINDS as EXPORT_KINDS, MAX_DAYS as MAX_EXPORT_DAYS, build as build_export
from .outcome import cannot_schedule, read as read_outcome, view as outcome_view
from .access import Access, role
from .notify import (DEFAULT_HOLD, DEFAULT_KINDS as NOTIFY_DEFAULT_KINDS, HOLDS, KINDS as NOTIFY_KINDS, MODE_WORDS,
                     MODES as NOTIFY_MODES, SERVICES, Notifier, Post, check_link, last_line, leave_out, link_end,
                     post_json, post_result, post_what)
from .programs import ProgramBook
from .auth import (admin_required, associate_allowed, check_csrf, csrf_token, load_user, login_required,
                   manager_required, safe_next, session_stamp)
from .program_page import build, overview, weeks_to_show
from .run_admin import PICK_UNIT, apply_rename, apply_run_change, preview_rename, preview_run_change, unit_keys
from .bulk_breaks import SHIFTS as BULK_SHIFTS, verb as bulk_verb
from .schedules import ScheduleBook, group_changes
from .versions import DAYS, shift_span, stale_blocks, with_notes, zoned_copy, zoned_label
from . import needed
from .paging import page_of
from .results import recolour, version_summary
from .runs import ACTIVE, MODES, OPTION_LABELS, READY, RESUMABLE, RunQueue, parse_options, run_options
from .store import Store
from .throttle import SignInThrottle
from werkzeug.datastructures import ImmutableMultiDict
from .change_requests import ChangeBook, level_of
from .bulk_users import people_workbook, new_password, passwords_workbook, read_people, template_bytes
from .daily_views import people_of, workbook as daily_workbook
from .merge import merge_intervals
from .merged_day import lob_of, merged_page
from .week import in_zone, view as week_view

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
    if not path.exists():  # Phase AT: created private from the start, never world-readable even for a moment
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secrets.token_urlsafe(48))
    return path.read_text(encoding="utf-8").strip()


WORKBOOKS = ("Scheduler_Input_Blank.xlsx", "Scheduler_Input_Example.xlsx")
BACK = {"program": "programs"}  # where Back goes without browser history; every other page: home
THEMES = ("light", "dark", "ocean")  # no cookie: follow the device's setting; ocean: Phase AG, the third look


def _when(epoch: Optional[float]) -> str:
    if not epoch:
        return ""
    zone = ZoneInfo(g.get("zone", HOME)) if has_request_context() else EGYPT  # Phase AF: the page's zone
    return datetime.fromtimestamp(epoch, zone).strftime("%a %d %b, %H:%M")


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


FIRST_DAY, LAST_DAY = date(2000, 1, 1), date(2099, 12, 31)  # days the site works with (Phase AC: 9999-12-31 crashed)


def in_range(day: Optional[date]) -> Optional[date]:
    """``day`` when the website can work with it (week and day arithmetic stays inside the calendar), else None."""
    return day if day is not None and FIRST_DAY <= day <= LAST_DAY else None


def start_date(text: str) -> Optional[str]:
    """A schedule's first date as given (YYYY-MM-DD, any weekday), or None if it is not a date."""
    try:
        found = in_range(datetime.strptime((text or "").strip(), "%Y-%m-%d").date())
    except ValueError:
        return None
    return found.isoformat() if found else None


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


class QuietSessions(SecureCookieSessionInterface):
    """The session cookie goes out on page loads and whenever the session changes, but not on a page's own
    background requests (previews, status polls). Phase XY: a preview started before a save and answered after it
    re-sent the session from before the save, and the save's message was lost. Page loads keep a signed-in person's
    12 hours running as before; browsers say which requests are page loads (Sec-Fetch-Mode: navigate), and a
    request that does not say is treated as one."""

    def should_set_cookie(self, app: Flask, session: Any) -> bool:
        if not session.modified and request.headers.get("Sec-Fetch-Mode", "navigate") != "navigate":
            return False
        return super().should_set_cookie(app, session)


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
    app.session_interface = QuietSessions()
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
    app.extensions["throttle"] = SignInThrottle()  # Phase AT: one address, many usernames
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
        app.extensions["leave"] = LeaveBook(app.extensions["store"], app.extensions["days"])  # Phase AG
        app.extensions["leave"].recover()  # Phase AI: an approval a stopped server left half done goes back to the RTA
        # Phase AO: leave approved while a week had no schedule is applied once that week's schedule is kept
        queue.on_kept = lambda run_id: app.extensions["leave"].apply_waiting(app.extensions["store"].get_run(run_id))
        app.extensions["swaps"] = SwapBook(app.extensions["store"], app.extensions["days"])
        app.extensions["changes"] = ChangeBook(app.extensions["store"], app.extensions["days"],
                                               lambda unit: ProgramBook(app.extensions["store"]).day_measure(unit))  # Phase AS
        # Phase AB: RTA changes posted to each LOB's Teams or Slack group, on the notifier's own thread.
        notifier = Notifier(app.extensions["store"], transport=config.get("NOTIFY_TRANSPORT") or post_json,
                            label=ProgramBook(app.extensions["store"]).label, days=app.extensions["days"])
        app.extensions["notifier"] = app.extensions["days"].notifier = notifier
        if config.get("START_WORKER", True):
            queue.start()
        if config.get("NOTIFY_THREAD", config.get("START_WORKER", True)):
            notifier.start()

    OPEN_TO_ALL = {"static", "login", "logout", "set_theme", "change_password", "home", "submit_run", "run_tag",
                   "program_rename", "program_setup", "workbook"}

    @app.before_request
    def _before() -> Any:
        check_csrf()
        load_user()
        # Phase AG: an associate's account opens their own pages only (My week); a page sends them there and a
        # form is refused, whatever address they type.
        if g.get("user") and g.user["is_associate"] and not associate_allowed(request.endpoint):
            if request.method in ("GET", "HEAD"):
                return redirect(url_for("me_breaks"))  # Phase AU: an associate opens on Today
            abort(403, description="Your account opens My day and My weeks only.")
        # Phase AK: what this person's role may open or do, as the admin set it on Roles (checked here, not only hidden)
        if g.get("user") and not g.user["is_associate"] and request.endpoint in PERMISSION_ENDPOINTS and \
                not _can(PERMISSION_ENDPOINTS[request.endpoint]):
            g.error_hint = "An admin sets what each role may open on Roles."
            abort(403, description="Your role cannot open this page or do this")
        g.zone = pick_zone(request.args.get("tz", ""))  # Phase AF (D5): Egypt unless the page asks for another
        # Phase Q: a program page opens only for people with that program (New schedule is open to everyone).
        if g.get("user") and request.endpoint not in OPEN_TO_ALL:
            key = (request.view_args or {}).get("name") if request.endpoint == "program" else \
                clean_program(request.values.get("program", ""))
            if key and not _access().can_open(key):
                g.error_hint = "Your account opens only the programs given to you. Ask an admin to add this one to your programs."
                # Phase AR (owner, 2026-10-21: nothing of another program is visible): the refusal never says whether the
                # program exists or what it is called; words from a link are never repeated back either.
                abort(403, description="This program is not one of your programs")
        # Phase AP: a change posted from a merged RTA page is saved on the LOB the person belongs to.
        if g.get("user") and request.method == "POST" and request.path.startswith("/day/") \
                and request.form.get("merge") == "1" and request.form.get("associate"):
            _route_to_lob()
        # AN: an old cross-zone RTA form must not save through a clock change.
        # Authentication, role/program permission and CSRF checks remain first.
        if g.get("user") and request.method == "POST" and request.path.startswith("/day/"):
            program = clean_program(request.form.get("program", ""))
            on = _date(request.form.get("date", ""))
            zone = request.form.get("tz", "")
            if program and on and zone in dict(ZONES) and rta_shift(on, _own_zone(program, on), zone) is None:
                message = "Clocks change in this RTA window. Reopen the day in the schedule's own time zone before editing."
                if request.accept_mimetypes.best == "application/json":
                    return jsonify(error=message), 400
                flash(message)
                return redirect(url_for("day_page", program=program, date=on.isoformat(),
                                        tz=_own_zone(program, on)), code=303)

    def _route_to_lob() -> None:
        """Phase AP (owner, 2026-10-21: edits go through to each person's own LOB): a form from the merged RTA page
        names the page's program; swap it for the LOB that lists the person, so every route works as before on that
        LOB, in that LOB's own time."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        units = _merge_units(program) if program else []
        if len(units) < 2 or on is None:
            return
        own = lob_of(_days(), units, on, request.form.get("associate", "").strip())
        if own and own != program:
            fields = request.form.to_dict(flat=False)
            fields["program"] = [own]
            request.__dict__["form"] = ImmutableMultiDict(fields)  # the cached form, as the routes will read it

    def _can(key: str) -> bool:
        """Phase AK: whether the person signed in may do ``key`` (Roles), read once per request."""
        if "role_grid" not in g:
            g.role_grid = matrix(app.extensions["store"])
        return allowed(app.extensions["store"], g.get("user"), key, g.role_grid)

    def _access() -> Access:
        if "access" not in g:
            g.access = Access(app.extensions["store"], g.user)
        return g.access

    def _can_see_run(run: Dict[str, Any]) -> bool:
        if run.get("user_id") == g.user["id"]:
            return True
        return _access().can_open(run["program"]) if run.get("program") else _access().everything()

    def _visible(rows: list, key: str = "program") -> list:
        """Rows (runs, versions, ...) of the programs this person may open."""
        keys = _access().keys()
        return rows if keys is None else [r for r in rows if r.get(key) in keys or r.get("user_id") == g.user["id"]]

    def _paged(rows: list, arg: str, anchor: str) -> Tuple[list, Optional[Dict[str, Any]]]:
        """Phase AI: a long list 20 at a time; ``?<arg>=N`` opens page N, and each link comes back to ``#anchor``."""
        shown, info = page_of(rows, request.args.get(arg, 1, type=int) or 1)
        if info:
            args = {**(request.view_args or {}), **request.args.to_dict()}

            def link(n: int) -> str:
                return url_for(request.endpoint, **{**args, arg: n}) + f"#{anchor}"
            info.update(links=[(n, link(n) if n else "") for n in info["numbers"]],
                        prev=link(info["page"] - 1) if info["page"] > 1 else "",
                        next=link(info["page"] + 1) if info["page"] < info["pages"] else "")
        return shown, info

    def _my_programs(names: list) -> list:
        keys = _access().keys()
        return names if keys is None else [n for n in names if n in keys]

    @app.after_request
    def _headers(response):  # type: ignore[no-untyped-def]
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")  # Phase AG: fonts and icons are served by the site itself; Phase AT: no base tag, forms post here only
        # Phase AT: a signed-in page is never kept by the browser or a proxy (the back button after sign-out shows nothing)
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    @app.template_filter("unit")
    def _unit_filter(key: Any) -> Any:
        """A program key as people know it: "AE, AR B2B" for a LOB, the program's name otherwise."""
        if not isinstance(key, str) or not key:
            return key
        if "unit_labels" not in g:
            names = {}
            for p in ProgramBook(app.extensions["store"]).tree():
                names[p["key"]] = p["name"]
                names.update({l["key"]: f"{p['name']}, {l['name']}" for l in p["lobs"]})
            g.unit_labels = names
        return g.unit_labels.get(key, key)

    @app.template_filter("records_text")
    def _records_text(counts: Dict[str, int]) -> str:
        """Day record counts in words, leaving out what is none: 1 attendance, 2 break moves."""
        words = (("attendance", "attendance", "attendance"), ("breaks", "break move", "break moves"),
                 ("activities", "activity", "activities"), ("log", "day-log line", "day-log lines"),
                 ("channels", "channel change", "channel changes"))
        parts = [f"{counts[k]} {one if counts[k] == 1 else many}" for k, one, many in words if (counts or {}).get(k)]
        return ", ".join(parts) or "no day records"

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

    @app.template_filter("in_zone")
    def _in_zone(text: str) -> str:
        """Phase AI: a text kept in the schedule's time (a shift, a change) with its times as the RTA shows them."""
        return moved_text(text or "", SHOWN.get())

    @app.template_filter("zone_cell")
    def _zone_cell(value: str, moved: int, on=None, from_zone=None, to_zone=None) -> str:
        """Phase AK: a schedule cell ("08:00 - 17:00") read ``moved`` minutes later, said when it then starts the day
        before or the next day; OFF, Leave and the like as they are."""
        try:
            return zoned_label(value, moved, on=on, from_zone=from_zone, to_zone=to_zone)
        except ValueError as exc:
            return f"{value} (invalid source clock time: {exc})"

    @app.template_filter("num")
    def _num(value: float) -> str:
        value = round(float(value), 1)
        return str(int(value)) if value.is_integer() else str(value)

    @app.template_filter("channel_name")
    def _channel_name(letter: str) -> str:
        return CHANNEL_NAMES.get(letter, letter)

    def _parent_url(endpoint: str, args: Optional[Dict[str, Any]]) -> str:
        """Where Back goes when this browser has no earlier page here (Phase W): one level up. A version's pages
        go to that version on its run's schedules page, a run's pages to the run, the rest as BACK says."""
        args = args or {}
        if "schedule_id" in args:
            row = app.extensions["store"].get_schedule(args["schedule_id"])
            if row is not None:
                return url_for("run_schedules", run_id=row["run_id"], v=row["id"])
        if "run_id" in args and endpoint != "run_detail":
            return url_for("run_detail", run_id=args["run_id"])
        return url_for(BACK.get(endpoint, "home"))

    @app.context_processor
    def _globals() -> Dict[str, Any]:
        theme = request.cookies.get("theme", "")
        endpoint = request.endpoint or ""
        back = None if endpoint in ("home", "login", "static") else _parent_url(endpoint, request.view_args)
        who = g.get("user")
        news_n = app.extensions["changes"].news_count(who["id"]) if who and app.extensions.get("changes") else 0
        return {"csrf_token": csrf_token, "copyright": COPYRIGHT, "user": g.get("user"), "news_n": news_n,
                "theme": theme if theme in THEMES else "", "back": back,
                "status_words": STATUS_WORDS, "label": label, "modes": MODES, "stages": stages, "in_flight": IN_FLIGHT,
                "when": _when, "run_options": run_options, "option_labels": OPTION_LABELS,
                "eta_text": eta_text, "duration": duration, "clock": _clock, "with_text": with_text,
                "group_changes": group_changes, "zones": ZONES, "home_zone": HOME, "channel_letters": channel_letters,
                "can": _can}

    NAV_ACTIVE = {"home": "home", "overview_page": "overview", "day_page": "day", "week_page": "week",
                  "run_week": "week", "run_schedules": "schedules", "program": "analysis", "programs": "programs",
                  "exports_page": "exports", "team_page": "team", "admin_users": "people", "program_setup": "setup",
                  "with_setup": "with", "channel_setup": "channels", "notifications_page": "notify", "roles_page": "roles",
                  "day_wallboard": "wallboard", "me": "me", "me_breaks": "me_day", "requests_page": "requests"}
    PROGRAM_PAGES = {"overview": "/overview?program={key}", "day": "/day?program={key}", "week": "/week?program={key}",
                     "schedules": "/schedules?program={key}", "analysis": "/programs/{key}",
                     "home": "/?program={key}",  # Home shows the program picked (owner, 2026-10-08)
                     "with": "/setup/with?program={key}", "channels": "/setup/channels?program={key}"}

    def _unit_choices(programs: list) -> list:
        """Each program with its LOBs as (key, name) pairs, for the left menu's picker."""
        out = []
        for p in programs:
            choices = [(l["key"], f"{p['name']}, {l['name']}") for l in p["lobs"]]
            if p["key"] in p["units"]:
                choices.append((p["key"], p["name"] if not p["lobs"] else f"{p['name']} (whole program)"))
            if choices:
                out.append({"name": p["name"], "choices": choices})
        return out

    @app.context_processor
    def _left_menu() -> Dict[str, Any]:
        """The left menu: the program (and LOB) open, its pages, and what this person may manage. The program
        last opened is remembered, so the menu keeps it on pages that are not about one program."""
        user = g.get("user")
        if not user or request.endpoint in ("login", "static"):
            return {}
        access = _access()
        args = request.view_args or {}
        if request.endpoint == "program":
            key = args.get("name", "")
        elif "schedule_id" in args or "run_id" in args:  # a run's or version's own pages follow its program
            found = (app.extensions["store"].get_schedule(args["schedule_id"]) if "schedule_id" in args
                     else app.extensions["store"].get_run(args["run_id"]))
            key = (found or {}).get("program") or ""
        else:
            key = clean_program(request.args.get("program", ""))
        if key and access.can_open(key) and access.book.unit(key):
            session["unit"] = key
        else:
            key = session.get("unit", "")
            if not key or not access.can_open(key) or not access.book.unit(key):
                units = [k for p in access.programs() for k in p["units"]]
                key = units[0] if units else ""
        active = NAV_ACTIVE.get(request.endpoint or "", "")
        target = PROGRAM_PAGES.get(active, PROGRAM_PAGES["overview"])
        day = _date(request.args.get("date", ""))  # Overview and RTA keep the day being looked at
        return {"nav_units": _unit_choices(access.programs()), "nav_unit": key,
                "nav_date": day.isoformat() if day else None,
                "nav_label": access.book.label(key) if key else "", "nav_active": active, "nav_target": target,
                "user_role": role(user), "nav_requests": _requests_waiting(key, user)}

    def _requests_waiting(key: str, user: Dict[str, Any]) -> int:
        """Phase AG: leave and swap requests on the program open that this person may decide now."""
        book, swaps = app.extensions.get("leave"), app.extensions.get("swaps")
        if not (book and key) or user["is_associate"]:
            return 0
        found = book.count_for(key, user) + swaps.count_for(key, user)
        if allowed(app.extensions["store"], user, "rta_change"):  # Phase AS: break changes and coaching for the RTA
            found += app.extensions["changes"].count(key)
        return found

    # ------------------------------------------------------------- theme
    @app.route("/theme", methods=["POST"])
    def set_theme():  # type: ignore[no-untyped-def]
        """Light, dark, or the device's own setting ("system"); kept in a cookie
        so the page is drawn in that theme from the first byte."""
        response = redirect(safe_next(request.form.get("next", "")) or "/")  # only ever back to this site
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
            throttle, address = app.extensions["throttle"], request.remote_addr or ""
            typed = (request.form.get("username", "") or "").strip().lower()
            account = app.extensions["store"].get_user_by_name(typed) if typed else None
            # the typed name is kept only when it is an account: a wrong box may hold a password
            who = {"subject": account["username"] if account else "(no such username)",
                   "user_id": account["id"] if account else None}
            if throttle.held(address):  # Phase AT: too many wrong sign-ins from this address; not even a right password
                app.extensions["store"].add_event(kind="sign_in_held", detail=f"from {address}", **who)
                return render_template("login.html", error="Too many sign-in attempts from this device. Wait 15 "
                                                           "minutes and try again."), 429
            user, reason = app.extensions["store"].authenticate(request.form.get("username", ""),
                                                                request.form.get("password", ""))
            if user is None and reason != "disabled":
                throttle.failed(address)
            if user is None:
                app.extensions["store"].add_event(kind="sign_in_failed", detail=f"from {address}: {reason}", **who)
            else:
                app.extensions["store"].add_event(kind="signed_in", detail=f"from {address}", **who)
            if user is not None:
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                session["pw"] = session_stamp(user)
                session["at"] = time.time()  # Phase AU: when this session began (see end_other_sessions)
                csrf_token()
                return redirect(safe_next(request.args.get("next", "")) or url_for("home"))
            error = {"locked": "Too many wrong passwords: this account is locked for 15 minutes.",
                     "disabled": "This account is switched off. Ask your admin."}.get(
                         reason, "Wrong username or password.")
        return render_template("login.html", error=error)

    @app.route("/account/sessions/end", methods=["POST"])
    @login_required
    def end_other_sessions():  # type: ignore[no-untyped-def]
        """Phase AU: every other device is signed out (a lost phone); this one stays."""
        now = time.time()
        app.extensions["store"].end_other_sessions(g.user["id"], now)
        session["at"] = now + 0.001  # after the mark, so this device is the one that stays
        _record("sessions_ended", subject=g.user["username"])
        flash("Every other device is signed out.")
        return redirect(url_for("change_password"))

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
                session["pw"] = session_stamp(store.get_user(g.user["id"]))  # this device stays; others sign in again
                flash("Password changed.")
                return redirect(url_for("home"))
        return render_template("password.html", error=error, forced=bool(g.user["must_change"]))

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
                _record("user_added", subject=username,  # never the password
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
        return render_template("admin_users.html", users=people, error=error, made=made, grantable=access.grantable(),
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
            _record("team_manager_set", subject=target["username"], detail="none")
            return f"{target['roster_name'] or target['display_name']} has no team manager."
        chosen = store.get_user(int(value)) if value.strip().isdigit() else None
        if chosen is None or not chosen["is_team_manager"] or not chosen["active"]:
            raise ValueError("Pick a team manager.")
        if chosen["id"] not in {u["id"] for u in access.team_managers_for(target)}:
            raise ValueError(f"{chosen['display_name']} has none of {target['roster_name'] or target['display_name']}'s "
                             "programs.")
        store.update_user(target["id"], team_manager_id=chosen["id"])
        _record("team_manager_set", subject=target["username"], detail=chosen["display_name"])
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
            if kind not in ROLES:
                problems.append("Pick a role.")
            elif kind not in STAFF_ADDS and not admin:
                problems.append("Only an admin adds supervisors and admins.")
            elif everything and kind == "associate":
                problems.append("An associate has named programs, not all of them.")
            elif not everything and not programs and not problems:
                problems.append("Give them at least one of your programs.")
            if kind == "associate" and programs and not problems:
                found = _roster_problem(roster, programs, tree)
                if found:
                    problems.append(found)
                else:
                    roster = _roster_canonical(roster, programs, tree) or roster
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
        return render_template("admin_users_bulk.html", error=error, plan=plan, token=token, roles=ROLES,
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
                          "role": ROLES[p["kind"]], "password": "" if p["password"] else password,
                          "given": bool(p["password"])})
        for p in order:  # their team managers, now that everyone is here
            wanted = p["team_manager"].strip().lower()
            if p["kind"] == "associate" and wanted:
                chosen = made.get(wanted) or next((u["id"] for u in store.list_users() if u["username"] == wanted), None)
                if chosen is not None:
                    store.update_user(made[p["username"]], team_manager_id=chosen)
        _record("users_bulk_added", detail=f"{len(shown)} added, {len(plan) - len(shown)} left out")  # never the passwords
        sheet_token = secrets.token_urlsafe(16)
        _bulk_held()[sheet_token] = {"user": g.user["id"], "expires": time.time() + 60 * BULK_MINUTES,
                                     "sheet": passwords_workbook([s for s in shown if not s["given"]])}
        return render_template("admin_users_bulk.html", error="", plan=None, token="", roles=ROLES, good=0,
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
        _record("sign_in_released", subject=address)
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
        _record("users_exported", detail=f"{len(rows)} people")
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
            _record("user_enabled" if on else "user_disabled", subject=target["username"])
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
            _record("user_disabled", subject=target["username"])
            flash(f"{target['username']} is switched off.")
        elif action == "enable":
            store.set_active(user_id, True)
            _record("user_enabled", subject=target["username"])
            flash(f"{target['username']} is switched on.")
        elif action == "delete":  # Phase AR: the account goes; the name stays in the history of what they did
            if request.form.get("confirm") != "1":
                flash(f"Tick the box to confirm, then press Delete person for {target['username']}.")
                return redirect(url_for("admin_users"))
            if target["is_admin"] and sum(1 for u in store.list_users() if u["is_admin"] and u["active"]) <= 1:
                flash("That is the last admin. Make another admin before deleting this one.")
                return redirect(url_for("admin_users"))
            store.delete_user(user_id)
            _record("user_deleted", subject=target["username"], detail=role(target))
            flash(f"{target['username']} is deleted: they cannot sign in and the username is free again. "
                  "Their name stays in the history of what they did.")
        elif action == "reset":
            temporary = secrets.token_urlsafe(9)
            store.set_password(user_id, temporary, must_change=True)
            _record("password_reset", subject=target["username"])  # never the password itself
            flash(f"Temporary password for {target['username']}: {temporary} "
                  "(shown once; they choose their own at next sign-in).")
        elif action == "team":  # Phase AK
            try:
                flash(_set_team_manager(access, target, request.form.get("team_manager", "")))
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
                programs = _chosen_programs(access, request.form.getlist("programs"),
                                            keep=store.user_program_ids(user_id))
            except PermissionError:
                abort(403)
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for("admin_users"))
            changes: Dict[str, Any] = {}
            kind = kind if admin and kind in ROLES else current
            if kind == "associate":  # Phase AG: still linked to a name on the schedule of the programs kept
                roster = request.form.get("roster_name", "").strip() or target["roster_name"]
                problem = _roster_problem(roster, programs, access.book.tree(), user_id)
                if problem:
                    flash(f"{target['username']}: {problem}")
                    return redirect(url_for("admin_users"))
                changes = {"is_associate": 1,
                           "roster_name": _roster_canonical(roster, programs, access.book.tree()) or roster}
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
            said = ("all programs" if changes.get("all_programs") else _program_names(programs, tree) or "no programs")
            _record("user_programs_changed", subject=target["username"],
                    detail=f"{ROLES[kind]}; {said}")
            flash(f"{target['username']}: {said}.")
        else:
            abort(404)
        return redirect(url_for("admin_users"))

    # ------------------------------------------------------------- my week (Phase AG)
    @app.route("/me")
    @login_required
    def me():  # type: ignore[no-untyped-def]
        """An associate's own week; staff have the whole site instead."""
        if not g.user["is_associate"]:
            return redirect(url_for("home"))
        key = _my_unit()
        leave, swaps = app.extensions.get("leave"), app.extensions.get("swaps")
        name = g.user["roster_name"]
        clock_now = datetime.now(EGYPT)
        today = clock_now.date()
        weeks = _my_weeks(key, today) if key else []
        swap_week = _date(request.args.get("swapweek", ""))
        week_offers = swaps.week_candidates(key, swap_week, name, today) if swap_week in weeks else []
        swap_day = _date(request.args.get("swap", ""))
        offers, swap_note = [], ""
        if key and swap_day:
            offers = swaps.candidates(key, swap_day, name)  # Phase AO: every colleague on another shift, with its warnings
            # Phase AI: when nobody is listed because there is nothing to swap, say why
            if any(r["first_day"] <= swap_day.isoformat() <= r["last_day"] for r in app.extensions["store"].list_leave(
                    program=key, associate=name, statuses=["waiting_tm", "waiting_rta", "applying", "approved"])):
                swap_note = f"You asked for leave on {swap_day:%a %d %b}, so there is no shift to swap."
                offers = []  # Phase AO: the list shows every colleague now, so a day you asked leave for shows none
            elif not shift_span(dict(app.extensions["days"].roster(key, swap_day)).get(name, "")):
                swap_note = f"You do not work on {swap_day:%a %d %b}."
        week = []
        mine = leave.mine(key, name) if leave and key else []
        my_swaps = swaps.mine(key, name) if swaps and key else []
        shown = None
        if key:
            days = app.extensions["days"]
            shown = _date(request.args.get("week", ""))
            if shown not in weeks:  # Phase AO: this week, else the first later one with a schedule
                shown = week_start(today) if week_start(today) in weeks else (weeks[0] if weeks else None)
            version = days.version(key, today)[0]
            first = shown or (date.fromisoformat(version["week_start"]) if version and version["week_start"]
                              else week_start(today))
            for i in range(7):
                on = first + timedelta(days=i)
                notes = [f"{r['kind']}: {MY_STATUS.get(r['status'], r['status'])}" for r in mine
                         if r["status"] != "cancelled" and r["first_day"] <= on.isoformat() <= r["last_day"]]
                notes += [f"Swap with {w['other'] if w['asker'] == name else w['asker']}: {w['status_words']}"
                          for w in my_swaps if (w["day"] == on.isoformat() or (w.get("scope") == "week" and any(
                              d["date"] == on.isoformat() for d in json.loads(w.get("detail") or "{}").get("days", []))))
                          and w["status"] != "cancelled"]
                cell = dict(days.roster(key, on)).get(name, "")
                items = []
                if shift_span(cell):
                    try:
                        found = days.page(key, on)
                        items = [f"{x['what']} {hm(x['lo'])} to {hm(x['hi'])}" for x in my_items(found["view"], name)] if found else []
                    except ValueError:  # a week whose input workbook is not kept: its shifts show, its breaks do not
                        items = []
                week.append({"date": on, "cell": cell, "notes": notes, "items": items, "today": on == today})
        return render_template("me.html", unit=key, kinds=LEAVE_KINDS, mine=mine, swaps=my_swaps, swap_day=swap_day,
                               swap_note=swap_note, weeks=weeks, shown=shown, week_labels={w.isoformat(): f"{w:%d %b} to {(w + timedelta(days=6)):%d %b}" for w in weeks}, swap_week=swap_week, week_offers=week_offers,
                               offers=offers, today=today, week=week, hm=hm)

    def _my_weeks(key: str, today: date) -> List[date]:
        """Phase AO: the Sundays of this week and every later week that has a schedule kept for ``key``."""
        found = []
        for w in app.extensions["schedules"].kept_weeks(key):
            first = _date(w["week"])
            if first and first + timedelta(days=6) >= today:
                found.append(first)
        return found

    MY_STATUS = {"waiting_tm": "waiting for your TM", "waiting_rta": "approved by your TM, waiting for the RTA",
                 "applying": "being approved", "approved": "approved", "refused": "refused"}

    def _my_unit() -> str:
        """The LOB whose schedule has this associate's name ("" when none does yet)."""
        leave = app.extensions.get("leave")
        if leave is None:
            return ""
        for p in _access().programs():
            for key in p["units"]:
                if g.user["roster_name"] in leave.names(key):
                    return key
        return ""

    @app.route("/me/leave", methods=["POST"])
    @login_required
    def me_leave():  # type: ignore[no-untyped-def]
        """An associate asks for leave for themselves (the name comes from their account, never the form)."""
        key = _my_unit()
        if not g.user["is_associate"] or not key:
            abort(403, description="Only an associate on a schedule asks for leave here.")
        first, last = _date(request.form.get("first", "")), _date(request.form.get("last", "")
                                                                  or request.form.get("first", ""))
        try:
            if first is None or last is None:
                raise ValueError("Pick the first and the last day.")
            app.extensions["leave"].ask(key, g.user["roster_name"], g.user["id"], request.form.get("kind", ""),
                                        first, last, request.form.get("note", ""), datetime.now(EGYPT).date())
        except ValueError as exc:
            flash(str(exc))
        else:
            flash("Sent. Your TM decides first, then the RTA.")
        return redirect(url_for("me"))

    @app.route("/me/leave/<int:request_id>/cancel", methods=["POST"])
    @login_required
    def me_leave_cancel(request_id: int):  # type: ignore[no-untyped-def]
        try:
            app.extensions["leave"].cancel(request_id, g.user["id"])
        except KeyError:
            abort(404)
        except ValueError as exc:
            flash(str(exc))
        else:
            flash("Cancelled.")
        return redirect(url_for("me"))

    @app.route("/me/swap", methods=["POST"])
    @login_required
    def me_swap():  # type: ignore[no-untyped-def]
        """An associate offers a colleague a swap of one day's shifts (their own name comes from their account)."""
        key = _my_unit()
        if not g.user["is_associate"] or not key:
            abort(403, description="Only an associate on a schedule offers swaps here.")
        on, other = _date(request.form.get("day", "")), " ".join(request.form.get("other", "").split())
        week_first = _date(request.form.get("week", ""))
        try:
            if week_first is not None:  # Phase AO: the whole week from today on, one request
                if not other:
                    raise ValueError("Pick a colleague.")
                today = datetime.now(EGYPT).date()
                if week_first not in _my_weeks(key, today):
                    raise ValueError("Pick this week or a later week that has a schedule.")
                app.extensions["swaps"].offer_week(key, week_first, g.user["roster_name"], g.user["id"], other,
                                                   request.form.get("note", ""), today,
                                                   allow_warnings=request.form.get("anyway") == "1")
                flash(f"Sent to {other}: the week from {week_first:%a %d %b}. Once they accept, your TM decides.")
                return redirect(url_for("me"))
            if on is None or not other:
                raise ValueError("Pick a day and a colleague.")
            app.extensions["swaps"].offer(key, on, g.user["roster_name"], g.user["id"], other,
                                          request.form.get("note", ""), datetime.now(EGYPT).date(),
                                          allow_warnings=request.form.get("anyway") == "1")
        except ValueError as exc:
            flash(str(exc))
        else:
            flash(f"Sent to {other}. Once they accept, your TM decides.")
        return redirect(url_for("me"))

    @app.route("/me/swap/<int:swap_id>/<action>", methods=["POST"])
    @login_required
    def me_swap_answer(swap_id: int, action: str):  # type: ignore[no-untyped-def]
        swaps = app.extensions["swaps"]
        try:
            if action == "answer":
                flash(swaps.answer(swap_id, g.user, request.form.get("decision") == "accept"))
            elif action == "cancel":
                swaps.cancel(swap_id, g.user["id"])
                flash("Cancelled.")
            else:
                abort(404)
        except KeyError:
            abort(404)
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("me"))

    @app.route("/requests/swap/<int:swap_id>", methods=["POST"])
    @login_required
    def request_swap_decide(swap_id: int):  # type: ignore[no-untyped-def]
        row = app.extensions["store"].get_swap(swap_id)
        if row is None:
            abort(404)
        if not _access().can_open(row["program"]):
            abort(403, description="This request is on a program that is not one of yours.")
        try:
            said = app.extensions["swaps"].decide(swap_id, g.user, request.form.get("decision") == "approve",
                                                  request.form.get("reason", ""))
        except ValueError as exc:
            said = str(exc)
        _record("swap_decided", subject=f"{row['asker']} and {row['other']}, {row['day']}", detail=said[:300])
        flash(said)
        return redirect(url_for("requests_page", program=row["program"]))

    # ------------------------------------------------------------- requests (Phase AG)
    def _requests_unit() -> str:
        key = clean_program(request.values.get("program", ""))
        if key and _access().can_open(key):
            return key
        units = [k for p in _access().programs() for k in p["units"]]
        remembered = session.get("unit", "")
        return remembered if remembered in units else (units[0] if units else "")

    def _change_rows(key: str) -> List[Dict[str, Any]]:
        """Phase AS: the waiting break changes and coaching, each with the intervals it touches (before, after, buffer)."""
        book, rows, now = app.extensions["changes"], [], _local_now(key)
        for r in book.waiting(key):
            try:
                r["impact"], r["impact_note"] = book.impact(r), ""
                r["alternatives"] = book.alternatives(r, now)  # the nearest times, from what the RTA holds now
                if r["kind"] == "coaching":  # the other answer to "billable?", so the RTA sees what correcting it does
                    r["other_impact"] = book.impact(r, billable=not r["d"].get("billable"))
            except (ValueError, KeyError, StopIteration) as exc:  # a day that cannot be worked out is said, not hidden
                r["impact"], r["impact_note"], r["alternatives"] = [], f"The impact cannot be worked out: {exc}", []
            rows.append(r)
        return rows

    @app.route("/requests")
    @login_required
    def requests_page():  # type: ignore[no-untyped-def]
        """Leave waiting for a decision, each day with what it costs; what was decided lately; balances."""
        key = _requests_unit()
        leave = app.extensions.get("leave")
        waiting = leave.waiting(key) if leave and key else []
        for r in waiting:
            r["mine"] = leave.may_decide(r, g.user)
        swaps = app.extensions.get("swaps")
        swap_rows = swaps.waiting(key) if swaps and key else []
        for w in swap_rows:  # Phase AK: their team managers, or a backup
            w["mine"] = swaps.may_decide(w, g.user)
        return render_template("requests.html", unit=key, label=_unit_filter(key) if key else "", waiting=waiting,
                               decided=_paged(leave.decided(key, limit=None) if leave and key else [], "done_page",
                                              "done-h"),
                               swaps=swap_rows, changes=_change_rows(key) if key else [],
                               changes_decided=app.extensions["changes"].decided(key) if key else [],
                               may_change=allowed(app.extensions["store"], g.user, "rta_change"), hm=hm,
                               can_ask_coaching=_can_ask_coaching(),
                               swaps_decided=_paged(swaps.decided(key, limit=None) if swaps and key else [],
                                                    "swaps_done_page", "done-h"),
                               manager=allowed(app.extensions["store"], g.user, "setup"),
                               year=datetime.now(EGYPT).year)

    # ------------------------------------------------------------- break changes and coaching (Phase AS)
    def _local_now(key: str) -> datetime:
        """Now on the clock the program's schedule is kept in (a break time is in the schedule's own time)."""
        return datetime.now(ZoneInfo(_own_zone(key, datetime.now(EGYPT).date())))

    @app.route("/me/breaks")
    @login_required
    def me_breaks():  # type: ignore[no-untyped-def]
        """An associate's breaks on the running day, and the times they may ask each to move to (Phase AS)."""
        if not g.user["is_associate"]:
            return redirect(url_for("home"))
        key, name = _my_unit(), g.user["roster_name"]
        book = app.extensions["changes"]
        now, found, options, problem, tomorrow = _local_now(key) if key else None, None, None, "", None
        if key:
            try:
                found = book.running_shift(key, name, now)
                tomorrow = book.tomorrow_shift(key, name, now)  # Phase AU: today and tomorrow, no later
                picked = request.args.get("change", type=int)
                next_day = request.args.get("day") == "tomorrow"
                if picked is not None and next_day and tomorrow is not None:
                    options = book.break_options(key, name, picked, now, tomorrow["on"])
                    options["picked"], options["day"] = picked, "tomorrow"
                elif found is not None and picked is not None:
                    options = book.break_options(key, name, picked, now)
                    options["picked"] = picked
            except ValueError as exc:
                problem = str(exc)
        seg = None
        if found is not None:
            seg = next(s for lane in found["view"]["lanes"] if lane["name"] == name for s in lane["segments"]
                       if s["offset"] == 0)
        tseg = None
        if tomorrow is not None:
            tseg = next(s for lane in tomorrow["view"]["lanes"] if lane["name"] == name for s in lane["segments"]
                        if s["offset"] == 0)
        card = None  # Phase AU: Today carries the day's card (it was on My week)
        if key and now is not None:
            try:
                page = app.extensions["days"].page(key, now.date())
                card = my_day(page["view"], name, now.hour * 60 + now.minute) if page else None
            except ValueError:  # a day whose input workbook is not kept: the breaks say so, the card is left out
                card = None
        news = book.news(g.user["id"], read=True)  # Phase AU: the answers since they last looked, shown once
        return render_template("me_breaks.html", unit=key, card=card, news=news, tomorrow=tomorrow, tseg=tseg, found=found, seg=seg, options=options, problem=problem,
                               today=now.date() if now else None,
                               mine=book.mine(key, g.user["id"]) if key else [], hm=hm,
                               now_at=found["now"] if found else 0)

    @app.route("/me/breaks", methods=["POST"])
    @login_required
    def me_breaks_ask():  # type: ignore[no-untyped-def]
        """Ask the RTA to move a break; the name comes from the account, never from the form."""
        key = _my_unit()
        if not g.user["is_associate"] or not key:
            abort(403, description="Only an associate on a schedule asks to move a break here.")
        try:
            now = _local_now(key)
            book = app.extensions["changes"]
            on = (now.date() + timedelta(days=1)) if request.form.get("day") == "tomorrow" else None
            book.ask_break(key, g.user["roster_name"], g.user, request.form.get("idx", type=int, default=-1),
                           request.form.get("to", ""), request.form.get("why", ""), now, on)
            flash("Sent to the RTA. You can cancel it until it is decided.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("me_breaks"), code=303)

    @app.route("/me/breaks/<int:request_id>/cancel", methods=["POST"])
    @login_required
    def me_breaks_cancel(request_id: int):  # type: ignore[no-untyped-def]
        try:
            app.extensions["changes"].cancel(request_id, g.user)
            flash("Cancelled.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("me_breaks"), code=303)

    @app.route("/requests/coaching/<int:request_id>/cancel", methods=["POST"])
    @login_required
    def requests_coaching_cancel(request_id: int):  # type: ignore[no-untyped-def]
        """Phase AU: the one who asked for coaching takes the request back until the RTA has decided it."""
        if g.user["is_associate"] or not _can_ask_coaching():
            abort(403, description="Your role cannot ask for coaching here.")
        row = app.extensions["store"].get_change_request(request_id)
        try:
            app.extensions["changes"].cancel(request_id, g.user)
            flash("Cancelled.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("requests_coaching", program=row["program"] if row else None), code=303)

    def _can_ask_coaching() -> bool:
        store = app.extensions["store"]
        return allowed(store, g.user, "approve_tm") or allowed(store, g.user, "rta_change")

    @app.route("/requests/coaching")
    @login_required
    def requests_coaching():  # type: ignore[no-untyped-def]
        """A team manager asks for coaching for one or more associates; the times show the buffer for them together."""
        if g.user["is_associate"] or not _can_ask_coaching():
            abort(403, description="Your role cannot ask for coaching here.")
        key = _requests_unit()
        book, leave = app.extensions["changes"], app.extensions["leave"]
        now = _local_now(key) if key else None
        names = [n for n in request.args.getlist("who") if n in (leave.names(key) if key else [])]
        on = _date(request.args.get("date", "")) or (now.date() if now else datetime.now(EGYPT).date())
        minutes = request.args.get("minutes", 30, type=int)
        billable = request.args.get("billable") == "1"
        options, problem = None, ""
        if key and names:
            try:
                options = book.coaching_options(key, on, names, minutes, now, billable=billable)
            except ValueError as exc:
                problem = str(exc)
        news = book.news(g.user["id"], read=True)  # Phase AU
        return render_template("requests_coaching.html", unit=key, news=news, label=_unit_filter(key) if key else "",
                               roster=sorted(leave.names(key)) if key else [], names=names, on=on, minutes=minutes, billable=billable,
                               options=options, problem=problem, depts=[d["name"] if isinstance(d, dict) else d
                                                                        for d in (_with_lists(key) if key else [])],
                               mine=book.mine(key, g.user["id"]) if key else [], hm=hm, may_decide=allowed(
                                   app.extensions["store"], g.user, "rta_change"))

    @app.route("/requests/coaching", methods=["POST"])
    @login_required
    def requests_coaching_ask():  # type: ignore[no-untyped-def]
        if g.user["is_associate"] or not _can_ask_coaching():
            abort(403, description="Your role cannot ask for coaching here.")
        key = clean_program(request.form.get("program", ""))
        if not key or not _access().can_open(key):
            abort(403, description="That is not one of your programs")
        names = request.form.getlist("who")
        on = _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick the day.")
            app.extensions["changes"].ask_coaching(key, names, g.user, on, request.form.get("start", ""),
                                                   request.form.get("minutes", 30, type=int), request.form.get("dept", ""),
                                                   request.form.get("why", ""), _local_now(key),
                                                   billable=request.form.get("billable") == "1")
            flash("Sent to the RTA.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("requests_coaching", program=key), code=303)

    @app.route("/requests/change/<int:request_id>", methods=["POST"])
    @login_required
    def request_change_decide(request_id: int):  # type: ignore[no-untyped-def]
        """The RTA's answer to a break change or a coaching request (changes the day when approved)."""
        row = app.extensions["store"].get_change_request(request_id)
        if row is None:
            abort(404)
        if g.user["is_associate"] or not allowed(app.extensions["store"], g.user, "rta_change"):
            abort(403, description="Your role cannot change the RTA's day.")
        if not _access().can_open(row["program"]):
            abort(403, description="This request is on a program that is not one of yours.")
        try:
            moved = request.form.get("change_at", type=int)  # "Approve at 13:45 instead": a nearest time, in minutes
            billable = {"1": True, "0": False}.get(request.form.get("billable", ""))
            said = app.extensions["changes"].decide(request_id, g.user,
                                                    request.form.get("decision") == "approve" or moved is not None,
                                                    request.form.get("reason", ""), _local_now(row["program"]),
                                                    at=moved, billable=billable)
        except ValueError as exc:
            said = str(exc)
        _record("change_decided", subject=f"{row['kind']} for {', '.join(json.loads(row['names']))}", detail=said[:300])
        flash(said)
        back = safe_next(request.form.get("back", ""))  # Phase AU: decided on the RTA tab, back to the tab
        return redirect(back or url_for("requests_page", program=row["program"]), code=303)

    @app.route("/requests/leave/<int:request_id>", methods=["POST"])
    @login_required
    def request_leave_decide(request_id: int):  # type: ignore[no-untyped-def]
        leave = app.extensions["leave"]
        row = app.extensions["store"].get_leave(request_id)
        if row is None:
            abort(404)
        if not _access().can_open(row["program"]):
            abort(403, description="This request is on a program that is not one of yours.")
        try:
            said = leave.decide(request_id, g.user, request.form.get("decision") == "approve",
                                request.form.get("reason", ""))
        except ValueError as exc:
            said = str(exc)
        _record("leave_decided", subject=f"{row['associate']}: {row['kind']} {row['first_day']} to {row['last_day']}",
                detail=said[:300])
        flash(said)
        return redirect(url_for("requests_page", program=row["program"]))

    @app.route("/requests/balances", methods=["POST"])
    @manager_required
    def request_balances():  # type: ignore[no-untyped-def]
        """Planned leave balances for a year, one person a line: a name, then the days (pasted from a sheet)."""
        key = _requests_unit()
        rows: Dict[str, float] = {}
        try:
            year = int(request.form.get("year", "0"))
            for line in request.form.get("rows", "").splitlines():
                if not line.strip():
                    continue
                parts = re.split(r"[\t,;]", line) if re.search(r"[\t,;]", line) else line.rsplit(" ", 1)
                if len(parts) < 2:
                    raise ValueError(f"Give a name and a number of days on each line: {line.strip()[:60]}")
                try:
                    rows[" ".join(parts[0].split())] = float(parts[-1].strip())
                except ValueError:
                    raise ValueError(f"Give a number of days on each line: {line.strip()[:60]}") from None
            if not rows:
                raise ValueError("Paste at least one line: a name, then the days.")
            count = app.extensions["leave"].set_balances(key, year, rows, g.user["id"])
        except ValueError as exc:
            flash(str(exc))
        else:
            _record("leave_balances", subject=key, detail=f"{count} for {year}")
            flash(f"Saved {count} balance{'s' if count != 1 else ''} for {year}.")
        return redirect(url_for("requests_page", program=key))

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
        everyone = app.extensions["store"].list_runs()
        plan = _plan(everyone)  # the queue is shared: waiting times count every run
        runs = _visible(everyone)
        summaries = {r["id"]: _run_figures(r) for r in runs} if queue else {}
        # Phase AI: the queue is everyone's; another program's runs show only as running or waiting, with the wait
        seen = {r["id"] for r in runs}
        active = sorted((r for r in everyone if r["status"] in ("GATE", "RUNNING", "SCORING")),
                        key=lambda r: r["id"] not in seen)
        waiting = sorted((r for r in everyone if r["status"] == "QUEUED"), key=lambda r: r["created"])
        wait_min = max((e["finishes_in_min"] for e in plan.values()), default=0)
        latest = next((r for r in runs if r["status"] in ("DONE", "REVIEW") and summaries.get(r["id"])), None)
        known = sorted({r["program"] for r in runs if r.get("program")}, key=str.lower)
        prefill = start_date(request.args.get("week", "")) or next_sunday()
        upload_programs, upload_keys = _upload_choices(everyone)
        picked = None if request.args.get("all") == "1" else (_left_menu().get("nav_unit") or None)
        unfiled = [r for r in runs if not r.get("program") and r["mode"] != "SMOKE"
                   and r["status"] not in ("REJECTED", "EXPIRED", "CANCELLED")]  # uploaded without a program
        # Phase Z: which run counts for its week, and Home's panel follows the program picked on the left
        in_use_map = app.extensions["store"].in_use_runs()
        in_use_ids = set(in_use_map.values())
        not_in_use_ids = {r["id"] for r in runs if (r.get("program"), r.get("week_start")) in in_use_map
                          and in_use_map[(r["program"], r["week_start"])] != r["id"]}
        latest_week = ""
        if picked:
            mine = [r for r in runs if r.get("program") == picked and r["status"] in ("DONE", "REVIEW")
                    and summaries.get(r["id"])]
            weeks = sorted({r["week_start"] for r in mine if r.get("week_start")})
            used = in_use_map.get((picked, weeks[-1])) if weeks else None
            latest = next((r for r in mine if r["id"] == used), None) or (mine[0] if mine else latest)
            latest_week = weeks[-1] if latest is not None and latest["id"] == used else ""
        cards = _program_cards(runs, picked)
        everything = _program_cards(runs)
        others = [{"name": c["name"], "key": c["units"][0]["key"]} for c in everything
                  if not any(c["name"] == x["name"] for x in cards)] if picked else []
        return render_template("dashboard.html", upload_programs=upload_programs, upload_keys=upload_keys,
                               program_cards=cards, other_programs=others, picked=picked, unfiled=unfiled,
                               unfiled_starts={r["id"]: start_choices(r["week_start"] or prefill, r["week_start"])
                                               for r in unfiled},
                               runs=runs, runs_page=_paged(runs, "runs_page", "runs-h"), queue=queue, plan=plan,
                               summaries=summaries,
                               active=active, waiting=waiting, seen=seen, wait_min=wait_min,
                               latest=latest, latest_week=latest_week,
                               in_use_ids=in_use_ids, not_in_use_ids=not_in_use_ids,
                               latest_summary=_walled(latest, summaries.get(latest["id"])) if latest else None,
                               now=time.time(), known_programs=known,
                               prefill_program=clean_program(request.args.get("program", ""))
                               or (picked if picked in upload_keys else ""),  # the unit picked on the left
                               prefill_week=prefill, start_options=start_choices(prefill, prefill),
                               usual_start=usual_start_days(runs))

    WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

    def _program_cards(runs: list, only: Optional[str] = None) -> list:
        """Home: this person's programs (only the one holding unit ``only`` when given), each LOB with its
        latest schedule week."""
        latest = app.extensions["store"].latest_weeks()
        usual = usual_start_days(runs)
        cards = []
        for p in _access().programs():
            units = [{"key": key, "text": next((l["name"] for l in p["lobs"] if l["key"] == key), p["name"]),
                      "latest": latest.get(key)} for key in p["units"]]
            if not units:
                continue
            if only is not None and only not in p["units"]:
                continue
            day = p["start_day"] if p["saved"] else usual.get(units[0]["key"], 0)
            cards.append({"name": p["name"], "units": units, "starts": WEEKDAYS[day]})
        return cards

    def _upload_choices(runs: list) -> Tuple[list, set]:
        """New schedule is open to everyone, for the programs they have (Phase AR; admins have all): each program with
        its LOBs, and the defaults it starts from (a program's saved defaults, else the weekday its schedules usually start on)."""
        book = ProgramBook(app.extensions["store"])
        book.sync()
        usual = usual_start_days(runs)
        out, keys = [], set()
        for p in book.tree():
            choices = [(l["key"], f"{p['name']}, {l['name']}") for l in p["lobs"]]
            if p["key"] in p["units"]:
                choices.append((p["key"], p["name"] if not p["lobs"] else f"{p['name']} (whole program)"))
            choices = [(k, t) for k, t in choices if _access().can_open(k)]  # Phase AR: only the programs a person has
            if not choices:
                continue
            keys |= {k for k, _ in choices}
            defaults = ({"start_day": p["start_day"], "run_mode": p["run_mode"], "options": p["options"]}
                        if p["saved"] else ({"start_day": usual[p["key"]]} if p["key"] in usual else {}))
            out.append({"name": p["name"], "choices": choices, "defaults": defaults})
        return out, keys

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
        if not _can_see_run(run):
            abort(403)
        return run

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
        book = _book()
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
        if program and not _access().can_open(program):  # Phase AR: a program is uploaded to only by those who have it
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
        refusal, warnings = _channel_upload_check(path)
        if refusal:
            path.unlink()
            flash(refusal)
            return redirect(url_for("home"))
        if warnings is not None:
            flash(f"Channel tabs: {warnings} warning{'s' if warnings != 1 else ''}. They are listed on the schedules "
                  "page and never change the schedule." if warnings else "Channel tabs: checked, no warnings.")
        already = _book().week_note(program, week_start, _unit_name(program))["text"] if program and week_start else ""
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
        return str(_unit_filter(key))

    @app.route("/runs/week-check")
    @login_required
    def week_check():  # type: ignore[no-untyped-def]
        """For the upload form (Phase W): what the picked program and week already have, in a sentence."""
        program = clean_program(request.args.get("program", ""))
        week = start_date(request.args.get("week", "")) or ""
        if not program or not week:
            return jsonify(count=0, text="")
        if not _access().can_open(program):
            abort(403)
        found = _book().week_note(program, week, _unit_name(program))
        return jsonify(count=found["count"], text=found["text"])

    @app.route("/runs/<run_id>")
    @login_required
    def run_detail(run_id: str):  # type: ignore[no-untyped-def]
        return _run_page(_run_or_404(run_id))

    def _ready_figures(run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """A ready schedule's coverage (Phase S): the validator's figures for its version in use, else its newest,
        with which version that is and whether its breaks are planned yet; None when no version is kept."""
        versions = _book().versions(run["id"])
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
        versions = _book().versions(run["id"]) if app.extensions.get("schedules") else []
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
        versions = _book().versions(run_id)
        week_state = None  # Phase Z: whether this run is the one its week uses
        if run.get("program") and run.get("week_start"):
            used = _book().in_use(run["program"], run["week_start"])
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
                               summary=_walled(run, _run_figures(run)),
                               said=said,
                               why=outcome_view(found) if found else None,
                               eta=_plan(store.list_runs()).get(run_id), now=time.time(), people=people,
                               start_options=start_choices(run["week_start"], run["week_start"]),
                               unit_label=ProgramBook(store).label(run["program"]) if run["program"] else "",
                               unit_groups=_unit_choices(ProgramBook(store).tree()),
                               ready_version=(_book().versions(run_id) or [None])[0] if run["mode"] == "READY" else None,
                               edit_open=request.args.get("edit") == "1", **extra)

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
        back = url_for("home") if request.form.get("back") == "home" else url_for("run_detail", run_id=run_id)
        week = request.form.get("week_start", "").strip()
        week_start = start_date(week) if week else ""
        if week_start is None:
            flash("Pick the date the schedule starts.")
            return redirect(back)
        new: Dict[str, Any] = {"program": clean_program(request.form.get("program", "")), "week_start": week_start}
        if new["program"] and new["program"] != run["program"] and not _access().can_open(new["program"]):
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
        access = _access()
        key = clean_program(request.values.get("program", "")) or _left_menu().get("nav_unit", "")
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
        access = _access()
        key = clean_program(request.values.get("program", "")) or _left_menu().get("nav_unit", "")
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

    # ---------------------------------------------------------------- group posts (Phase AB)
    def _notify_units() -> List[Tuple[str, str]]:
        """Every LOB (and program without LOBs) as (key, "Program, LOB"), in the left menu's order."""
        return [pair for p in _unit_choices(ProgramBook(app.extensions["store"]).tree()) for pair in p["choices"]]

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
                _record("roles_changed", subject="Roles", detail="back to the defaults")
                flash("Roles are back to the defaults.")
            else:
                ticked = set(request.form.getlist("allow"))
                rows = {(r, k): f"{r}|{k}" in ticked for r in ROLE_NAMES for k in PERMISSIONS}
                store.set_role_permissions(rows)
                _record("roles_changed", subject="Roles", detail="; ".join(
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
            _record("notify_saved", program=key, subject=label_, detail=said)
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
                               last_post=Post(**json.loads(shown["body"])) if shown else None,
                               recent=_paged([(p, post_what(p), *post_result(p)) for p in posts], "posts_page",
                                             "nf-rec-h"))

    @app.route("/notifications/test", methods=["POST"])
    @admin_required
    def notifications_test():  # type: ignore[no-untyped-def]
        key, label_ = _notify_unit()
        ok, said = app.extensions["notifier"].send_test(key, g.user["display_name"])
        if (app.extensions["store"].get_notify(key) or {}).get("link"):
            _record("notify_tested", program=key, subject=label_, detail=said)
        flash(said)
        return redirect(url_for("notifications_page", unit=key), code=303)

    @app.route("/notifications/remove", methods=["POST"])
    @admin_required
    def notifications_remove():  # type: ignore[no-untyped-def]
        key, label_ = _notify_unit()
        app.extensions["store"].set_notify(key, link="", service="", mode="off", saved_by=g.user["id"],
                                           saved_at=time.time())
        _record("notify_removed", program=key, subject=label_, detail="Posting off")
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
                elif action == "defaults":
                    options = {k: request.form.get(k) for k, plain in ADVANCED_DEFAULTS.items()
                               if request.form.get(k) and request.form.get(k) != plain}
                    book.set_defaults(pid, request.form.get("start_day", type=int, default=-1),
                                      request.form.get("run_mode", ""), options)
                    said = f"Saved the defaults for {book.program(pid)['name']}."
                elif action == "measure":  # Phase AS
                    book.set_measure(pid, request.form.get("coverage_measure", ""))
                    said = f"{book.program(pid)['name']} now counts billable time as {book.MEASURES[book.measure_setting(pid)].lower()}."
                elif action == "rename_program":
                    book.rename(pid, None, name)
                    said = f"Renamed to {book.program(pid)['name']}."
                elif action == "rename_lob":
                    book.rename(None, request.form.get("lob_id", type=int), name)
                    said = "Renamed the LOB."
                elif action == "delete_program":
                    gone = book.delete_program(pid)
                    said = f"Deleted program {gone}."
                    _record("program_deleted", subject=gone, detail=said)
                    flash(said)
                    return redirect(url_for("program_setup"))
                elif action == "delete_lob":
                    lob_id = request.form.get("lob_id", type=int)
                    owner = next((l["program_id"] for l in store.list_lobs() if l["id"] == lob_id), None)
                    gone = book.delete_lob(lob_id)
                    said = f"Deleted LOB {gone}" + (f" of {book.program(owner)['name']}." if owner else ".")
                    _record("lob_deleted", subject=gone, detail=said)
                    flash(said)
                    return redirect(url_for("program_setup"))
                else:
                    abort(400)
                _record("program_set_up", subject=request.form.get("key") or name, detail=said)
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
        return render_template("program_setup.html", programs=tree, people=people, loose=loose, modes=MODES,
                               measures=ProgramBook.MEASURES,
                               blockers=blockers, unit_groups=_unit_choices(tree),
                               look_alike={p["key"]: book.look_alike(p["id"]) for p in tree if not p["lobs"]},
                               days=["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])

    @app.route("/programs/rename", methods=["POST"])
    @admin_required
    def program_rename():  # type: ignore[no-untyped-def]
        """Rename a program everywhere, or merge it into another: shown first, saved with a reason."""
        store = app.extensions["store"]
        old, new = request.form.get("old", ""), clean_program(request.form.get("new", ""))
        reason = " ".join(request.form.get("reason", "").split())[:200]
        known = program_weeks(_all_runs(), app.extensions['store'].in_use_runs())
        try:
            if new not in unit_keys(store):
                raise ValueError(PICK_UNIT)  # moved into a program or LOB that is set up, never a typed name
            found = preview_rename(store, old, new)
            confirmed = request.form.get("confirm") == "1"
            if confirmed and reason and not found["clashes"]:
                apply_rename(store, old, new, g.user["id"], reason)
                book = ProgramBook(store)
                flash(f"Moved {book.label(old)} into {book.label(found['new'])}.")
                known = program_weeks(_all_runs(), app.extensions['store'].in_use_runs())
                return redirect(url_for("program", name=found["new"]) if found["new"] in known else url_for("programs"))
            return render_template("program_rename.html", found=found, reason=reason,
                                   reason_missing=confirmed and not reason,
                                   back=url_for("program", name=old) if old in known else url_for("programs"))
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("program", name=old) if old in known else url_for("programs"))

    # ------------------------------------------------------------- analytics
    def _all_runs() -> list:
        """Every run this person may see (all of them for admins and people with every program)."""
        return _visible(app.extensions["store"].list_runs(limit=100000))

    @app.route("/programs")
    @login_required
    def programs():  # type: ignore[no-untyped-def]
        group = {k: p["name"] for p in ProgramBook(app.extensions["store"]).tree() for k in p["units"]}
        rows = overview(program_weeks(_all_runs(), app.extensions['store'].in_use_runs()))
        for r in rows:  # each LOB under its program
            r["group"] = group.get(r["name"], r["name"])
        rows.sort(key=lambda r: (r["group"].casefold(), r["name"].casefold()))
        return render_template("programs.html", rows=rows)

    @app.route("/programs/<path:name>")
    @login_required
    def program(name: str):  # type: ignore[no-untyped-def]
        history = program_weeks(_all_runs(), app.extensions['store'].in_use_runs()).get(name)
        if not history:
            if name not in unit_keys(app.extensions["store"]):
                abort(404)
            uploaded = [r for r in _visible(app.extensions["store"].list_runs())
                        if r.get("program") == name and r["mode"] == READY and r["status"] == "DONE"]
            return render_template("program_empty.html", name=name, uploaded=uploaded)  # no engine week yet
        n = weeks_to_show(request.args.get("weeks", "12"))
        shown = history if n is None else history[-n:]
        groups = [{**p, "choices": [(k, t) for k, t in p["choices"] if k != name]}
                  for p in _unit_choices(ProgramBook(app.extensions["store"]).tree())]
        return render_template("program.html", name=name, view=build(shown, history), weeks=n,
                               total=len(history), ranges=(4, 8, 12, 26, 52),
                               unit_groups=[p for p in groups if p["choices"]])

    def _week_zone(intervals: Optional[list], run: Optional[Dict[str, Any]], week: str) -> Tuple[Optional[list], str]:
        """The week's rows in the page's zone (Phase AF, D5) and a sentence saying so (empty in the schedule's own)."""
        own = pick_zone((run or {}).get("tz") or HOME)
        first = start_date(week) if week else None
        if not intervals or not first or own == g.zone:
            return intervals, ""
        on = date.fromisoformat(first)
        return (in_zone(intervals, on, own, g.zone),
                f"Times in {zone_label(g.zone, on)}: the schedule's times are in {dict(ZONES)[own]}. Each day is "
                f"{dict(ZONES)[g.zone].split(' (')[0]}'s day; hours that fall in the week before or after are left out.")

    def _week_page(run: Optional[Dict[str, Any]], side: str, program: str, week: str,
                   history: Dict[str, list]):  # type: ignore[no-untyped-def]
        figures = kept_figures(run or {})
        intervals, zone_note = _week_zone(figures.get("intervals"), run, week)
        weeks = [w["week"] for w in reversed(history.get(program, []))]
        target = _week_target(program, week, (run or {}).get("id"))
        return render_template("week.html", run=run, view=week_view(intervals, side, target) if intervals else None,
                               side=side, program=program, week=week, programs=sorted(history, key=str.lower),
                               weeks=weeks, figures=figures, zone_note=zone_note)

    @app.route("/runs/<run_id>/week")
    @login_required
    def run_week(run_id: str):  # type: ignore[no-untyped-def]
        run = _run_or_404(run_id)
        side = "before" if request.args.get("side") == "before" else "after"
        return _week_page(run, side, run.get("program") or "", run.get("week_start") or "",
                          program_weeks(_all_runs(), app.extensions['store'].in_use_runs()))

    def _version_weeks(program: str) -> List[str]:
        """The weeks with a kept schedule for ``program`` (uploaded ones included), as the person may see."""
        return sorted({w for p, w in app.extensions["store"].schedule_weeks() if p == program}) \
            if program and _access().can_open(program) else []

    def _week_choices(program: str, history: Dict[str, list]) -> Tuple[List[str], List[str]]:
        """The Week page's program and week lists: runs that count and kept schedules (Phase W)."""
        kept = {p for p, _ in app.extensions["store"].schedule_weeks()}
        programs = sorted(set(history) | {p for p in kept if _access().can_open(p)}, key=str.lower)
        weeks = sorted({w["week"] for w in history.get(program, [])} | set(_version_weeks(program)), reverse=True)
        return programs, weeks

    def _week_target(program: str, week_start: str, run_id: Optional[str]) -> float:
        """The interval target that colours a week (Phase AH): the one set for the program and week, else the
        workbook's own, else 90%."""
        kept = app.extensions["store"].get_interval_target(program, week_start) if program and week_start else None
        if kept:
            return kept["target"] / 100
        book = app.extensions.get("schedules")
        source = book.input_path(run_id) if book is not None and run_id else None
        try:
            return float(read_inputs(source)["target"]) if source is not None and source.is_file() else 0.9
        except Exception:  # a workbook that cannot be read is said where it is used; the colours keep 90%
            return 0.9

    def _walled(run: Dict[str, Any], summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """A run's wall coloured by its week's target (Phase AH); the kept summary itself is left as it is."""
        if not summary:
            return summary
        return recolour(copy.deepcopy(summary), _week_target(run.get("program") or "", run.get("week_start") or "",
                                                             run.get("id")))

    def _own_target(row: Dict[str, Any]) -> int:
        """The workbook's own interval target for a version, a whole percent (90 when it cannot be read)."""
        source = _book().input_path(row["run_id"])
        return round(100 * read_inputs(source)["target"]) if source.is_file() else 90

    def _target_panel(program: str, week_start: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """The Week page's interval target (Phase W): the choice and each day's intervals at it, as the RTA counts."""
        kept = app.extensions["store"].get_interval_target(program, week_start)
        own = _own_target(row)
        days = []
        first = date.fromisoformat(week_start)
        for i in range(7):
            on = first + timedelta(days=i)
            try:
                page = _days().page(program, on)
            except ValueError:  # the workbook is missing: said on the day page
                page = None
            days.append({"date": on, "label": f"{on:%a %d}", "t": page["target"] if page else None})
        return {"current": kept["target"] if kept else own, "own": own, "kept": kept, "days": days,
                "choices": sorted({100, 95, 90, 85, 80, own}, reverse=True),
                "may_set": allowed(app.extensions["store"], g.user, "setup")}

    @app.route("/day/shrinkage", methods=["POST"])
    @manager_required
    def day_shrinkage_map():  # type: ignore[no-untyped-def]
        """Save what counts as shrinkage in and out of office for a program (Phase AF, E1; admins and supervisors)."""
        program = clean_program(request.form.get("program", ""))
        on = _date(request.form.get("date", ""))
        if not program or on is None:
            abort(400)
        if not _access().can_open(program):
            abort(403)
        app.extensions["store"].set_shrinkage_map(program, mapping_from_form(request.form), g.user["id"])
        _record("shrinkage_mapped", program=program, subject=program, detail="Saved what counts as shrinkage.")
        flash("Saved what counts as shrinkage.")
        return redirect(url_for("day_page", program=program, date=on.isoformat()), code=303)

    @app.route("/week/target", methods=["POST"])
    @manager_required
    def week_target():  # type: ignore[no-untyped-def]
        """Set the interval target for a program's week (Phase W; admins and supervisors)."""
        program = clean_program(request.form.get("program", ""))
        week = start_date(request.form.get("week", "")) or ""
        if not program or not week:
            abort(400)
        if not _access().can_open(program):
            abort(403)
        store = app.extensions["store"]
        row, _ = pick_version(store.list_schedules(program=program, week_start=week))
        if row is None:
            abort(404)
        try:
            target = int(request.form.get("target", ""))
        except ValueError:
            target = -1
        if target not in {100, 95, 90, 85, 80, _own_target(row)}:
            abort(400)
        store.set_interval_target(program, week, target, g.user["id"])
        _record("interval_target_changed", program=program, week_start=week, subject=f"{target}%",
                detail=f"interval target for the week of {week}")
        flash(f"The interval target for the week of {date.fromisoformat(week):%a %d %b} is now {target}%: the RTA "
              "counts each day's intervals against it.")
        return redirect(url_for("week_page", program=program, week=week) + "#target", code=303)

    def _outlook(program: str, week_start: str) -> Optional[List[Dict[str, Any]]]:
        """The rest of the week on the Week page (Phase AF, F4); None for a week that is over."""
        today = datetime.now(EGYPT).date()
        first = date.fromisoformat(week_start)
        if first + timedelta(days=6) <= today:
            return None
        try:
            return _days().outlook(program, first, today)
        except ValueError:  # a workbook that cannot be read: said on the day page
            return None

    def _hours_needed(program: str, week_start: str, basis: str, aim: str, show: str,
                      version_id: Optional[int] = None) -> Dict[str, Any]:
        """The Weeks page's Hours needed table (Phase AH): each day of the week from the DayBook (as recorded on the
        RTA, or as planned), and for today and the days to come what to do (days off to cancel, then overtime)."""
        days, rows = _days(), []
        clock = datetime.now(EGYPT)
        first = date.fromisoformat(week_start)
        for i in range(7):
            on = first + timedelta(days=i)
            page, why, plan = None, "", None
            try:
                page = days.page(program, on, recorded=basis == "recorded",
                                 version_id=version_id if basis != "recorded" else None)
            except ValueError as exc:  # the workbook cannot be read: said in the column
                why = str(exc)
            if page is None and not why:
                why = "No schedule for this day."
            if page is not None and on >= clock.date():
                after = clock.hour * 60 + clock.minute if on == clock.date() else 0
                plan = days.dayoff_plan(page, after, page["target"]["target"] if aim == "target" else None)
            rows.append({"date": on, "page": page, "plan": plan, "why": why})
        return {"table": needed.week_table(rows, aim, show), "basis": basis}

    def _week_version(program: str, week_start: str) -> Optional[int]:
        """Phase AM: the version picked on the Weeks page (``v``): one of that program's week, else 404; None when
        none is picked (the one in use)."""
        picked = request.args.get("v", type=int)
        if picked is None:
            return None
        if not any(v["id"] == picked for v in app.extensions["store"].list_schedules(program=program,
                                                                                     week_start=week_start)):
            abort(404)
        return picked

    def _version_pick(versions: List[Dict[str, Any]], picked: Optional[int]) -> Dict[str, Any]:
        """The Weeks page's Version pick: the week's versions, the one in use first, each with its run and whether
        its breaks are planned."""
        store = app.extensions["store"]
        runs = {v["run_id"]: (store.get_run(v["run_id"]) or {}).get("workbook") or v["run_id"] for v in versions}
        rows = [{"id": v["id"], "in_use": bool(v["in_use"]),
                 "text": f"{runs[v['run_id']]}: {v['label']}, "
                         + ("breaks planned" if json.loads(v["week"] or "{}").get("breaks") else "before breaks")
                         + (" (in use)" if v["in_use"] else "")}
                for v in sorted(versions, key=lambda v: (not v["in_use"], -(v["created"] or 0), -v["id"]))]
        return {"rows": rows if len(rows) > 1 else [], "picked": picked}

    def _needed_choices() -> Tuple[str, str, str]:
        return (needed.pick(request.args.get("basis"), needed.BASES), needed.pick(request.args.get("aim"), needed.AIMS),
                needed.pick(request.args.get("show"), needed.SHOWS))

    @app.route("/week/hours-needed.xlsx")
    @login_required
    def week_hours_needed():  # type: ignore[no-untyped-def]
        """The Hours needed table in Excel, as the Weeks page shows it (Phase AH)."""
        program = clean_program(request.args.get("program", ""))
        week = start_date(request.args.get("week", ""))
        if not program or not week:
            abort(400)
        if not _access().can_open(program):
            abort(403)
        basis, aim, show = _needed_choices()
        found = _hours_needed(program, week, basis, aim, show, _week_version(program, week))
        table = found["table"]
        reach = "100%" if aim == "full" else f"the target ({round(100 * table['target'])}%) with 10 minutes over it"
        title = (f"{_unit_filter(program)}, week of {date.fromisoformat(week):%a %d %b %Y}. "
                 f"{'As recorded on the RTA' if basis == 'recorded' else 'As planned'}. Hours needed to reach {reach}.")
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{program}_{week}_hours_needed").strip("_") + ".xlsx"
        return send_file(io.BytesIO(needed.workbook(table, title)), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def _recorded_week(program: str, week_start: str) -> Optional[Dict[str, Any]]:
        """The week as the RTA records it, for the Schedules page (Phase AH): intervals at the target, tight ones."""
        days, found = _days(), {"now": 0, "intervals": 0, "tight": 0, "target": None}
        first = date.fromisoformat(week_start)
        for i in range(7):
            try:
                page = days.page(program, first + timedelta(days=i))
            except ValueError:
                continue
            if page is None:
                continue
            t = page["target"]
            found.update(now=found["now"] + t["now"], intervals=found["intervals"] + t["intervals"],
                         tight=found["tight"] + t["tight"], target=t["target"])
        return found if found["intervals"] else None

    def _channel_hours_for(units: List[str], week_start: str) -> Optional[Dict[str, Any]]:
        """Phase AP: the week's hours per channel of one LOB, or of several added up (a merged page)."""
        found = [w for w in (_channel_hours_week(u, week_start) for u in units) if w]
        if len(found) < 2:
            return found[0] if found else None
        table = combine(found)
        return {**table, "labels": found[0]["labels"], "unplanned_labels": [found[0]["labels"][i] for i in table["unplanned"]]}

    def _channel_hours_week(program: str, week_start: str) -> Optional[Dict[str, Any]]:
        """Phase AP (sample ap01, C): the week's scheduled hours per channel for ``program`` (None when the week has
        no schedule in use at all), with the day labels and the days that have no channel plan."""
        days, views = _days(), []
        first = date.fromisoformat(week_start)
        for i in range(7):
            try:
                page = days.page(program, first + timedelta(days=i))
            except (ValueError, KeyError, StopIteration, OSError, zipfile.BadZipFile, InvalidFileException):
                page = None  # a kept input that cannot be read: the page says so elsewhere
            views.append(page["view"] if page else None)
        if not any(views):
            return None
        table = week_hours(views)
        labels = [f"{first + timedelta(days=i):%a %d}" for i in range(7)]
        return {**table, "labels": labels, "unplanned_labels": [labels[i] for i in table["unplanned"]]}

    def _merge_units(program: str) -> List[str]:
        """Phase AP (sample ap01; owner: only LOBs of one program): the units a merged view of ``program`` holds, its
        program's LOBs, when there are two or more; else just ``program``. A person is given a whole program, so
        every unit listed is one they may open."""
        found = ProgramBook(app.extensions["store"]).unit(program) if program else None
        if found is None:
            return [program]
        units = sorted(u for u in found["program"]["units"] if _access().can_open(u))
        return units if len(units) > 1 and program in units else [program]

    def _merged_name(program: str, units: List[str]) -> str:
        """"ZED, One + Two": the program and its LOBs' own names."""
        book = ProgramBook(app.extensions["store"])
        found = book.unit(program)
        names = [(book.unit(u) or {}).get("lob") or {} for u in units]
        return f"{found['program']['name']}, " + " + ".join(n.get("name") or u for n, u in zip(names, units))

    def _lob_names(units: List[str]) -> Dict[str, str]:
        """Phase AP: the short name of each unit ("Tier 2"), for the chip on each person of a merged page."""
        book = ProgramBook(app.extensions["store"])
        return {u: ((book.unit(u) or {}).get("lob") or {}).get("name") or u for u in units}

    def _merged_week(program: str, units: List[str], week: str, side: str):  # type: ignore[no-untyped-def]
        """Phase AP: the Week page of every LOB of ``program`` as one grid, in the zone picked, with one target (the
        LOBs' targets weighted by what each LOB needs). None when none of the LOBs has a schedule for the week."""
        store = app.extensions["store"]
        kept = sorted({w for u in units for w in _version_weeks(u)})
        holding = next((w for w in reversed(kept) if week and 0 <= (date.fromisoformat(week)
                                                                    - date.fromisoformat(w)).days <= 6), None)
        if holding is None and not week and kept:
            holding = kept[-1]
        if holding is None:
            return None
        rows, targets, notes, missing = {}, [], [], []
        for u in units:
            chosen, _ = pick_version(store.list_schedules(program=u, week_start=holding))
            if chosen is None:
                missing.append(u)
                continue
            intervals, note = _week_zone(json.loads(chosen["checks"] or "{}").get("intervals") or [],
                                         store.get_run(chosen["run_id"]), holding)
            rows[u] = intervals
            targets.append((_week_target(u, holding, chosen["run_id"]), sum(r[2] for r in intervals)))
            if note and note not in notes:
                notes.append(note)
        weight = sum(w for _, w in targets)
        target = sum(t * w for t, w in targets) / weight if weight else 0.9
        merged = merge_intervals(rows)
        programs, weeks = _week_choices(program, program_weeks(_all_runs(), store.in_use_runs()))
        info = {"name": _merged_name(program, units), "units": units,
                "missing": [(ProgramBook(store).label(u)) for u in missing],
                "target": int(round(100 * target)), "differs": len({round(t, 4) for t, _ in targets}) > 1}
        return render_template("week.html", run=None, view=week_view(merged, side, target) if merged else None,
                               side=side, program=program, week=holding, programs=programs, weeks=weeks, figures={},
                               zone_note=" ".join(notes), merged=info)

    def _version_week(row: Dict[str, Any], side: str, note: Optional[Dict[str, Any]] = None,
                      target: Optional[Dict[str, Any]] = None,
                      elsewhere: Optional[Dict[str, Any]] = None,
                      outlook: Optional[List[Dict[str, Any]]] = None,
                      hours: Optional[Dict[str, Any]] = None,
                      pick: Optional[Dict[str, Any]] = None):  # type: ignore[no-untyped-def]
        """A version's week view; ``note`` (the Week page): why this version, and what else the week has."""
        run = app.extensions["store"].get_run(row["run_id"])
        intervals, zone_note = _week_zone(json.loads(row["checks"] or "{}").get("intervals") or [], run,
                                          row["week_start"])
        programs, weeks = _week_choices(row["program"], program_weeks(_all_runs(), app.extensions['store'].in_use_runs()))
        listed = _book().week_list(row["program"], row["week_start"])  # Phase AA: switch between the week's schedules
        switch = [{"workbook": e["run"].get("workbook") or e["run"]["id"], "in_use": e["in_use"],
                   "here": e["run"]["id"] == row["run_id"],
                   "url": url_for("week_page", program=row["program"], week=row["week_start"]) if e["in_use"]
                   else url_for("schedule_week", schedule_id=e["shown"]["id"])}
                  for e in listed] if len(listed) > 1 else []
        figures = kept_figures(run or {})
        if figures.get("associates") is None:  # Phase AC: an uploaded schedule keeps no count; its week has the people
            people = (json.loads(row["week"] or "{}") or {}).get("associates") or []
            figures["associates"] = sum(1 for a in people if any(shift_span(d) for d in a.get("days", []))) or None
            figures["associates_from"] = "with a shift this week" if figures["associates"] else ""
        ratio = _week_target(row["program"], row["week_start"], row["run_id"])
        return render_template("week.html", run=run, view=week_view(intervals, side, ratio) if intervals else None,
                               side=side, program=row["program"], week=row["week_start"], programs=programs,
                               weeks=weeks, figures=figures, version=row, week_note=note,
                               may_set_in_use=_may_set_in_use(row), target_panel=target, elsewhere=elsewhere,
                               switch=switch, outlook=outlook, zone_note=zone_note, needed=hours,
                               pick=pick or {"rows": [], "picked": None})

    @app.route("/week")
    @login_required
    def week_page():  # type: ignore[no-untyped-def]
        """A program's week: the schedule in use (Phase W; else the newest kept, said so), else the run that counts
        for it (the latest finished, as on the program page)."""
        store = app.extensions["store"]
        history = program_weeks(_all_runs(), store.in_use_runs())
        side = "before" if request.args.get("side") == "before" else "after"
        program = clean_program(request.args.get("program", ""))
        week = start_date(request.args.get("week", "")) or ""
        if not program and history:
            latest = max((w for rows in history.values() for w in rows), key=lambda w: w["finished"] or 0)
            program, week = latest["program"], latest["week"]
        units = _merge_units(program)  # Phase AP: a View pick when the program has two or more LOBs
        g.merge_pick = f"All LOBs of {ProgramBook(store).unit(program)['program']['name']}" if len(units) > 1 else ""
        if request.args.get("merge") == "1" and len(units) > 1:
            if not _access().can_open(program):
                abort(403)
            found = _merged_week(program, units, week, side)
            if found is not None:
                return found
        kept = _version_weeks(program)
        holding = next((w for w in reversed(kept) if week and 0 <= (date.fromisoformat(week)
                                                                    - date.fromisoformat(w)).days <= 6), None)
        if program and not week and kept:
            holding = kept[-1]
        if holding:
            versions = store.list_schedules(program=program, week_start=holding)
            chosen, said = pick_version(versions)
            picked = _week_version(program, holding)
            if picked is not None:  # Phase AM: the Version pick
                chosen, said = next(v for v in versions if v["id"] == picked), ""
            if chosen is not None:
                runs = {v["run_id"]: (store.get_run(v["run_id"]) or {}).get("workbook", "") for v in versions}
                others = [{"run_id": rid, "workbook": wb} for rid, wb in runs.items() if rid != chosen["run_id"]]
                set_by = ""
                if chosen["in_use"]:
                    marks = [e for e in store.list_events(0, time.time() + 60, program, None, ["set_in_use"])
                             if e.get("schedule_id") == chosen["id"]]
                    if marks:
                        set_by = (f"set in use by {marks[-1].get('by_name') or 'someone'} on "
                                  f"{datetime.fromtimestamp(marks[-1]['at'], EGYPT):%a %d %b}")
                return _version_week(chosen, side, {"said": said, "workbook": runs.get(chosen["run_id"], ""),
                                                    "others": others, "set_by": set_by},
                                     _target_panel(program, holding, chosen),
                                     outlook=_outlook(program, holding),
                                     hours=_hours_needed(program, holding, *_needed_choices(), picked),
                                     pick=_version_pick(versions, picked))
        rows = history.get(program, [])
        if program and not week and rows:
            week = rows[-1]["week"]
        row = next((w for w in rows if w["week"] == week), None) or next(  # else the week holding that date
            (w for w in reversed(rows) if week and start_date(w["week"]) and
             0 <= (date.fromisoformat(week) - date.fromisoformat(w["week"])).days <= 6), None)
        week = row["week"] if row else week
        run = store.get_run(row["run_id"]) if row else None
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
        run = app.extensions["store"].get_run(row["run_id"]) or {"program": row["program"]}
        if not _can_see_run(run):
            abort(403)
        return row

    def _may_delete(run: Dict[str, Any]) -> bool:
        """Who may delete a schedule (owner, 2026-10-10: "Uploader or admin"): admins, and the person who uploaded
        or ran it."""
        return bool(g.user["is_admin"]) or run.get("user_id") == g.user["id"]

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
        week_list = book.week_list(run.get("program") or "", run.get("week_start") or "")
        needs = book.channel_path(run_id)
        added = needs.stat().st_mtime if needs is not None and needs.name == "channels.xlsx" else None
        step, input_problem = None, ""
        if versions and book.input_path(run_id).is_file():
            try:
                step = read_inputs(book.input_path(run_id))["interval"]
            except (ValueError, KeyError, StopIteration, OSError, zipfile.BadZipFile, InvalidFileException):
                # Phase AC: a damaged kept input says so here instead of turning the whole page into an error
                input_problem = ("The input workbook kept with this schedule cannot be read, so its channels cannot "
                                 "be checked here. Upload the schedule again to replace it.")
        own = pick_zone(run.get("tz") or HOME)  # Phase AK: shown in the zone picked, the schedule's own to begin with
        g.zone = request.args["tz"] if request.args.get("tz") in dict(ZONES) else own
        first = date.fromisoformat(run["week_start"]) if start_date(run.get("week_start") or "") else datetime.now(EGYPT).date()
        moved = own != g.zone
        together = None  # Phase AP: every LOB of the program as one, when it has two or more
        units = _merge_units(run["program"]) if run.get("program") and start_date(run.get("week_start") or "") else []
        if len(units) > 1:
            weeks_of = [w for w in (_channel_hours_week(u, run["week_start"]) for u in units) if w]
            together = {"name": _merged_name(run["program"], units), "of": len(units),
                        "have": sum(1 for u in units if app.extensions["store"].list_schedules(
                            program=u, week_start=run["week_start"])),
                        "url": url_for("week_page", program=run["program"], week=run["week_start"], merge="1",
                                       tz=g.zone if moved else None),
                        "hours": {**combine(weeks_of), "labels": weeks_of[0]["labels"],
                                  "unplanned_labels": [weeks_of[0]["labels"][i] for i in combine(weeks_of)["unplanned"]]}
                        if weeks_of else None}
        zone_dates = {d: first + timedelta(days=((i + 6) % 7 - first.weekday()) % 7) for i, d in enumerate(DAYS)}
        return render_template("schedules.html", run=run, versions=versions, current=current, view=view,
                               leave_after=app.extensions["leave"].last_applied(run_id), moved=moved, together=together, zone_dates=zone_dates, own_zone=own, own_name=dict(ZONES)[own],
                               counts=counts, may_set_in_use=bool(current) and _may_set_in_use(current),
                               days=DAYS, channel_lines=None if input_problem else _channel_lines(run_id),
                               chhours=_channel_hours_week(run["program"], run["week_start"])
                               if current and run.get("program") and start_date(run.get("week_start") or "") else None,
                               channel_added=added, step=step, input_problem=input_problem,
                               week_list=week_list if len(week_list) > 1 else [],
                               may_use={e["shown"]["id"] for e in week_list if _may_set_in_use(e["shown"])},
                               may_delete=_may_delete(run), running=run["status"] in ACTIVE + ("QUEUED",),
                               recorded=_recorded_week(run["program"], run["week_start"])
                               if current and current["in_use"] and run.get("program") and start_date(
                                   run.get("week_start") or "") else None)

    # ------------------------------------------------------------- delete a schedule (Phase AA)
    @app.route("/runs/<run_id>/delete", methods=["POST"])
    @login_required
    def run_delete(run_id: str):  # type: ignore[no-untyped-def]
        """Delete a schedule that is not needed (owner, 2026-10-10: "Uploader or admin"): admins and the person who
        uploaded or ran it, any schedule not in use and not running. The days' records stay; the log keeps it."""
        run = _run_or_404(run_id)
        if not _may_delete(run):
            abort(403)
        program, week = run.get("program") or "", run.get("week_start") or ""
        back = redirect(url_for("schedules_for", program=program, week=week) if program else url_for("home"))
        if request.form.get("confirm") != "1":
            flash("Tick the box to confirm, then press Delete schedule.")
            return redirect(url_for("run_schedules", run_id=run_id) + "#delete")
        if run["status"] in ACTIVE + ("QUEUED",):
            flash(f"{run['workbook']} is still running: stop it first, then delete it.")
            return redirect(url_for("run_schedules", run_id=run_id) + "#delete")
        try:
            count = _book().delete_run(run_id)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("run_schedules", run_id=run_id) + "#delete")
        shutil.rmtree(_queue().run_dir(run_id), ignore_errors=True)
        _record("run_deleted", run, detail=f"{count} version{'s' if count != 1 else ''}")
        flash(f"Deleted {run['workbook']}." if not count else
              f"Deleted {run['workbook']} and its {count} version{'s' if count != 1 else ''}.")
        return back

    # ------------------------------------------------------------- channel needs for a schedule (Phase Z)
    @app.route("/runs/<run_id>/channel-needs.xlsx")
    @login_required
    def channel_needs_download(run_id: str):  # type: ignore[no-untyped-def]
        """The channel needs workbook made for this run's week: the needs added to it when there are some (to
        change them), else the empty tabs at the run's interval."""
        run = _run_or_404(run_id)
        book = _book()
        source = book.input_path(run_id)
        if not source.is_file():
            abort(404)
        name = secure_filename(f"Channel_needs_{run.get('program') or run_id}_{run.get('week_start') or ''}"
                               ).rstrip("_") + ".xlsx"
        added_needs = book.root / run_id / "channels.xlsx"
        if added_needs.is_file():
            return send_file(added_needs, as_attachment=True, download_name=name)
        inputs = read_inputs(source)
        with tempfile.TemporaryDirectory() as folder:
            made = channel_workbook(Path(folder) / name, inputs["interval"],
                                    [lang["name"] for lang in inputs["languages"]])
            data = io.BytesIO(made.read_bytes())
        return send_file(data, as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/runs/<run_id>/channel-needs", methods=["POST"])
    @login_required
    def channel_needs_add(run_id: str):  # type: ignore[no-untyped-def]
        """Add channel needs to this schedule (anyone who can edit its versions): kept with the run, no new run."""
        run = _run_or_404(run_id)
        back = redirect(url_for("run_schedules", run_id=run_id) + "#channels")
        upload = request.files.get("workbook")
        if upload is None or not os.path.basename(upload.filename or "").lower().endswith(".xlsx"):
            flash("Pick the channel needs workbook (.xlsx) to add.")
            return back
        incoming = _queue().runs_root / "_incoming"
        incoming.mkdir(exist_ok=True)
        path = incoming / f"{secrets.token_hex(8)}.upload"
        upload.save(path)
        try:
            lines = _book().attach_channels(run_id, path)
        except ValueError as exc:
            flash(f"These channel needs were not added: {exc}")
            return back
        finally:
            path.unlink(missing_ok=True)
        warnings = sum(1 for level, _ in lines if level == "warn")
        _record("channel_needs_added", run, detail=f"{warnings} warning{'s' if warnings != 1 else ''}")
        flash(f"Channel needs added to {run['workbook']}: " + (
            f"{warnings} warning{'s' if warnings != 1 else ''}, listed under Channels. They never change the schedule."
            if warnings else "checked, no warnings.") + " Plan channels is ready.")
        return back

    # ------------------------------------------------------------- a week's breaks (Phase R)
    def _clock_of(text: str, span: Tuple[int, int]) -> Optional[int]:
        found = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", (text or "").strip())
        if not found:
            return None
        m = int(found.group(1)) * 60 + int(found.group(2))
        return m + 1440 if m < span[0] and span[1] > 1440 else m  # after midnight: the overnight shift's

    def _typed_breaks(week: Dict[str, Any], d: int, rules: Dict[str, Any]) -> Optional[Dict[str, list]]:
        """The grid's times for one day, or None when the form carried no grid."""
        if "rows" not in request.form:
            return None
        shifts = {a["name"]: a["days"][d] for a in week.get("associates", [])}
        typed: Dict[str, list] = {}
        for i in range(min(request.form.get("rows", 0, type=int), 2000)):
            name = request.form.get(f"who-{i}", "")
            span = shift_span(shifts.get(name, ""))
            if not span:
                continue
            typed[name] = [_clock_of(request.form.get(f"at-{i}-{k}", ""), span)
                           for k in range(len(slots_for(rules, span[1] - span[0])))]
        return typed


    def _channel_before(row, week, rules, draft, d, skills, language_rows):
        previous = None
        if d == 0 and start_date(row.get("week_start") or ""):
            prior_on = date.fromisoformat(start_date(row["week_start"])) - timedelta(days=1)
            prior, _ = _days().version(row["program"], prior_on)
            previous = json.loads(prior["week"] or "{}") if prior else None
        return channel_before(week, rules, draft, d, skills, language_rows, previous_week=previous)

    @app.route("/schedules/<int:schedule_id>/breaks", methods=["GET", "POST"])
    @login_required
    def plan_breaks(schedule_id: int):  # type: ignore[no-untyped-def]
        """Plan a week's breaks: a grid per day, Suggest for the empty ones, saved as a new version."""
        row = _version_or_404(schedule_id)
        store, book = app.extensions["store"], _book()
        day = request.values.get("day", "")
        week = json.loads(row["week"] or "{}")
        if day not in DAYS:
            day = next((DAYS[i] for i in range(7) if any(shift_span(a["days"][i]) for a in week.get("associates", []))),
                       DAYS[0])
        d = DAYS.index(day)
        try:
            rules = book.break_rules(schedule_id)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("run_schedules", run_id=row["run_id"], v=schedule_id))
        inputs = read_inputs(book.input_path(row["run_id"]))
        if request.method == "POST":
            action = request.form.get("action", "keep")
            typed = _typed_breaks(week, d, rules)
            draft = store.get_break_draft(schedule_id)
            if typed is not None and typed != (draft.get(day) or _version_breaks(week, d, rules)):
                store.set_break_draft(schedule_id, day, typed, g.user["id"])  # only what was changed is kept
                draft = store.get_break_draft(schedule_id)
            current = draft.get(day) or _version_breaks(week, d, rules)
            go = request.form.get("go", "") if request.form.get("go", "") in DAYS else day
            if action == "suggest":
                store.set_break_draft(schedule_id, day, suggest(week, inputs, rules, d, current), g.user["id"])
                flash(f"Suggested times for the empty breaks on {day}. Nothing is kept until you save.")
            elif action == "copy":
                shifts = {a["name"]: a["days"] for a in week.get("associates", [])}
                copied = 0
                for other in DAYS:
                    if other == day:
                        continue
                    before = draft.get(other) or _version_breaks(week, DAYS.index(other), rules)
                    rows = dict(before)
                    for name, starts in current.items():
                        label = shifts.get(name, [""] * 7)[d]
                        if shifts.get(name) and shifts[name][DAYS.index(other)] == label and shift_span(label):
                            rows[name] = list(starts)
                    if rows != before:  # only a day it changes is marked unsaved
                        store.set_break_draft(schedule_id, other, rows, g.user["id"])
                        copied += 1
                flash(f"Copied {day}'s times to {copied} other day{'s' if copied != 1 else ''} with the same shift. "
                      "Nothing is kept until you save." if copied else
                      f"Nothing to copy: no other day changes with {day}'s times.")
            elif action == "discard":
                store.clear_break_draft(schedule_id)
                flash("Your unsaved times were dropped.")
            elif action == "save":
                reason = " ".join(request.form.get("reason", "").split())[:200] or "Breaks planned"
                use = request.form.get("use") == "1" and _may_set_in_use(row)
                try:
                    saved, left_out = book.save_breaks(schedule_id, g.user["id"], draft, reason, use=use)
                except ValueError as exc:
                    flash(str(exc))
                    return redirect(url_for("plan_breaks", schedule_id=schedule_id, day=day), code=303)
                store.clear_break_draft(schedule_id)
                made = book.lineage(saved)[0]
                flash("Nothing changed." if saved == schedule_id else
                      f"Saved as {made['label']}{' and in use for this week' if use else ''}.")
                for line in left_out:
                    flash(line)
                return redirect(url_for("plan_breaks", schedule_id=saved, day=day), code=303)
            return redirect(url_for("plan_breaks", schedule_id=schedule_id, day=go), code=303)
        draft = store.get_break_draft(schedule_id)
        current = draft.get(day) or _version_breaks(week, d, rules)
        people = []
        for a in sorted(week.get("associates", []), key=lambda a: ((shift_span(a["days"][d]) or (0, 0))[0], a["name"])):
            span = shift_span(a["days"][d])
            if not span:
                continue
            slots = slots_for(rules, span[1] - span[0])
            starts = (list(current.get(a["name"]) or []) + [None] * len(slots))[:len(slots)]
            level, text = check_row(rules, a["days"][d], starts)
            people.append({"name": a["name"], "label": a["days"][d], "slots": list(zip(slots, starts)),
                           "level": level, "text": text})
        columns = max((p["slots"] for p in people), key=len, default=[])
        run = store.get_run(row["run_id"]) or {}
        return render_template("breaks.html", row=row, run=run, day=day, days=DAYS, people=people, rules=rules,
                               columns=[(k, m) for (k, m), _ in columns], strip=floor(week, inputs, d, current, rules,
                                                                                  _week_target(row["program"], row["week_start"], row["run_id"])),
                               interval=inputs["interval"], drafted=sorted(draft, key=DAYS.index),
                               may_set_in_use=_may_set_in_use(row), hm=hm)

    def _version_breaks(week: Dict[str, Any], d: int, rules: Dict[str, Any]) -> Dict[str, list]:
        """The breaks a version already has on day ``d``, as the grid's starts per person."""
        out: Dict[str, list] = {}
        for a in week.get("associates", []):
            span = shift_span(a["days"][d])
            if not span:
                continue
            slots = slots_for(rules, span[1] - span[0])
            mine = {b["kind"]: b for b in week.get("breaks", []) if b["associate"] == a["name"] and b["day"] == DAYS[d]}
            starts = []
            for kind, _ in slots:
                b = mine.get(kind)
                m = _clock_of(b["start"], span) if b else None
                starts.append(m)
            out[a["name"]] = starts
        return out

    # ------------------------------------------------------------- a week's channels (Phase V)
    @app.route("/schedules/<int:schedule_id>/channels", methods=["GET", "POST"])
    @login_required
    def plan_channels(schedule_id: int):  # type: ignore[no-untyped-def]
        """Plan a week's channels: a grid per day, Suggest (channels, and breaks inside the break rules), a block set
        by hand, Copy to days with the same shifts; nothing is kept until Save, which makes a new version."""
        row = _version_or_404(schedule_id)
        store, book = app.extensions["store"], _book()
        needs = book.channel_path(row["run_id"])
        setup = None
        if needs is not None:
            try:
                inputs = read_inputs(book.input_path(row["run_id"]))
                setup = read_channels(needs, inputs["interval"])
            except (ValueError, KeyError, StopIteration) as exc:
                return render_template("error.html", code=400, message=f"The channel tabs cannot be read: {exc}"), 400
        if setup is None:
            return render_template("error.html", code=404, message="This schedule's input workbook has no channel "
                                   "tabs (Chat, Phone or Email per interval, Email Hours, Channel Setup), so there are "
                                   "no channels to plan. Add channel needs on its Schedules page, under Channels."), 404
        week = json.loads(row["week"] or "{}")
        day = request.values.get("day", "")
        if day not in DAYS:
            day = next((DAYS[i] for i in range(7) if any(shift_span(a["days"][i]) for a in week.get("associates", []))),
                       DAYS[0])
        d = DAYS.index(day)
        try:
            rules = book.break_rules(schedule_id)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("run_schedules", run_id=row["run_id"], v=schedule_id))
        skills = ChannelPeople(store).skills_for_unit(row["program"])
        draft = store.get_channel_draft(schedule_id)
        plan = channel_current(week, d, rules, draft)
        people = people_for(week, d, rules, plan, skills, inputs["languages"])
        if request.method == "POST":
            action = request.form.get("action", "")
            try:
                if action == "suggest":
                    found = plan_day(people, setup, rules, d, carry=channel_carry(week, rules, draft, d),
                                     move_breaks=request.form.get("move") == "1",
                                     before=_channel_before(row, week, rules, draft, d, skills, inputs["languages"]))
                    store.set_channel_draft(schedule_id, day, {"blocks": found["blocks"], "breaks": found["breaks"],
                                                               "moved": found["moved"], "note": found["note"]},
                                            g.user["id"])
                    moved = len(found["moved"])
                    flash(f"Suggested channels for {FULL_DAYS[day]} in {found['seconds']:g} seconds"
                          + (f"; {moved} break{'s' if moved != 1 else ''} moved inside the break rules" if moved else "")
                          + ". Nothing is kept until you save.")
                    if found["note"]:
                        flash(found["note"])
                elif action == "suggest_week":  # Phase AF (B1): every working day, one after another
                    began, planned, refused = time.time(), 0, []
                    for o, other in enumerate(DAYS):
                        if not any(shift_span(a["days"][o]) for a in week.get("associates", [])):
                            continue
                        draft = store.get_channel_draft(schedule_id)  # each day's fair spread counts the days before
                        theirs = people_for(week, o, rules, channel_current(week, o, rules, draft), skills,
                                            inputs["languages"])
                        try:
                            found = plan_day(theirs, setup, rules, o, carry=channel_carry(week, rules, draft, o),
                                             move_breaks=request.form.get("move") == "1",
                                             before=_channel_before(row, week, rules, draft, o, skills, inputs["languages"]))
                        except NoPlan as exc:
                            refused.append(f"{FULL_DAYS[other]}: {exc}")
                            continue
                        store.set_channel_draft(schedule_id, other, {"blocks": found["blocks"],
                                                                     "breaks": found["breaks"],
                                                                     "moved": found["moved"], "note": found["note"]},
                                                g.user["id"])
                        planned += 1
                    flash(f"Suggested channels for {planned} day{'s' if planned != 1 else ''} in "
                          f"{round(time.time() - began, 1):g} seconds. Nothing is kept until you save.")
                    for line in refused:
                        flash(f"Not planned: {line}")
                elif action == "edit":
                    name = request.form.get("who", "")
                    person = next((p for p in people if p["name"] == name), None)
                    if person is None:
                        raise ValueError(f"{name or 'Nobody'} works on {FULL_DAYS[day]} in this schedule.")
                    span = (person["start"], person["end"])
                    start = _clock_of(request.form.get("start", ""), span)
                    end = _clock_of(request.form.get("end", ""), span)
                    if start is None or end is None:
                        raise ValueError("Give the start and the end, like 10:00 and 11:00.")
                    if end <= start:
                        end += 1440
                    letter = request.form.get("channel", "")
                    changed = apply_edit(plan, person, start, end, letter, setup, d)
                    store.set_channel_draft(schedule_id, day, changed, g.user["id"])
                    flash(f"{name}: {CHANNEL_NAMES[letter]} from {hm(start)} to {hm(end)}. Nothing is kept until "
                          "you save.")
                elif action == "copy":
                    shifts = {a["name"]: a["days"] for a in week.get("associates", [])}
                    copied = 0
                    for other in DAYS:
                        if other == day:
                            continue
                        o = DAYS.index(other)
                        theirs = channel_current(week, o, rules, draft)
                        changed = False
                        for name, days_of in shifts.items():
                            if days_of[o] == days_of[d] and shift_span(days_of[d]) and name in plan["blocks"]:
                                if (theirs["blocks"].get(name), theirs["breaks"].get(name)) != \
                                        (plan["blocks"][name], plan["breaks"].get(name)):
                                    theirs["blocks"][name] = plan["blocks"][name]
                                    theirs["breaks"][name] = plan["breaks"].get(name)
                                    changed = True
                        if changed:
                            theirs["moved"], theirs["note"] = [], ""
                            store.set_channel_draft(schedule_id, other, theirs, g.user["id"])
                            copied += 1
                    flash(f"Copied {FULL_DAYS[day]}'s channels to {copied} other day{'s' if copied != 1 else ''} with "
                          "the same shifts. Nothing is kept until you save." if copied else
                          f"Nothing to copy: no other day changes with {FULL_DAYS[day]}'s channels.")
                elif action == "discard":
                    store.clear_channel_draft(schedule_id)
                    flash("Your unsaved channels were dropped.")
                elif action == "save":
                    reason = " ".join(request.form.get("reason", "").split())[:200] or "Channels planned"
                    use = request.form.get("use") == "1" and _may_set_in_use(row)
                    saved, left_out = book.save_channels(schedule_id, g.user["id"], draft, reason, use=use)
                    store.clear_channel_draft(schedule_id)
                    made = book.lineage(saved)[0]
                    flash("Nothing changed." if saved == schedule_id else
                          f"Saved as {made['label']}{' and in use for this week' if use else ''}.")
                    for line in left_out:
                        flash(line)
                    return redirect(url_for("plan_channels", schedule_id=saved, day=day), code=303)
                else:
                    raise ValueError("Pick what to do.")
            except ValueError as exc:  # NoPlan is a ValueError
                flash(str(exc))
            return redirect(url_for("plan_channels", schedule_id=schedule_id, day=day), code=303)
        score = score_day(people, plan, setup, d, rules, before=_channel_before(row, week, rules, draft, d, skills, inputs["languages"]))
        target = setup["email_hours"][d]["hours"] if setup["email_mode"] == "hours" else None
        run = store.get_run(row["run_id"]) or {}
        return render_template("channels.html", row=row, run=run, day=day, days=DAYS, full=FULL_DAYS, setup=setup,
                               grid=channel_grid(people, plan), people=people, score=score, target=target,
                               cover=channel_coverage(people, plan, setup, d, inputs["interval"], before=_channel_before(row, week, rules, draft, d, skills, inputs["languages"])),
                               plan=plan, planned=planned_anything(plan), drafted=sorted(draft, key=DAYS.index), names=CHANNEL_NAMES,
                               stale=[] if day in draft else stale_blocks(week, d),
                               may_set_in_use=_may_set_in_use(row), hm=hm,
                               fair=fairness(week, rules, draft, skills, inputs["languages"], d))

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
        # Phase AM: "Times in" another zone downloads a copy in that zone's clock; the kept workbook stays as it is
        own = pick_zone((_book().store.get_run(row["run_id"]) or {}).get("tz") or HOME)
        tz = request.args.get("tz", "")
        first = start_date(row["week_start"] or "")
        convert = tz in dict(ZONES) and tz != own and bool(first)
        if convert:
            stem = secure_filename(f"{stem}_{dict(ZONES)[tz].split(' (')[0]} time") or stem
        _record("downloaded", program=row["program"], week_start=row["week_start"], run_id=row["run_id"],
                schedule_id=schedule_id, subject=f"{stem}.xlsx")
        if convert:
            source = book.path(schedule_id) if row["kind"] != "edited" else with_notes(book.path(schedule_id),
                                                                                       book.view(schedule_id))
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "zoned.xlsx"
                    zoned_copy(source, out, 0, on=date.fromisoformat(first), from_zone=own, to_zone=tz)
                    data = out.read_bytes()
            except ValueError as exc:
                return render_template("error.html", code=400, message=str(exc)), 400
            return send_file(io.BytesIO(data), as_attachment=True, download_name=f"{stem}.xlsx",
                             mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if row["kind"] != "edited":
            return send_file(book.path(schedule_id), as_attachment=True, download_name=f"{stem}.xlsx")
        return send_file(with_notes(book.path(schedule_id), book.view(schedule_id)), as_attachment=True,
                         download_name=f"{stem}.xlsx")

    @app.route("/schedules/<int:schedule_id>/channels.xlsx")
    @login_required
    def channel_plan_download(schedule_id: int):  # type: ignore[no-untyped-def]
        """Phase AF (C4): the week's channel plan as on Plan channels (unsaved suggestions included), in two views."""
        from .channel_export import channel_plan_workbook
        row = _version_or_404(schedule_id)
        store, book = app.extensions["store"], _book()
        if book.channel_path(row["run_id"]) is None:
            abort(404)
        inputs = read_inputs(book.input_path(row["run_id"]))
        try:
            rules = book.break_rules(schedule_id)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("plan_channels", schedule_id=schedule_id))
        week = json.loads(row["week"] or "{}")
        skills = ChannelPeople(store).skills_for_unit(row["program"])
        draft = store.get_channel_draft(schedule_id)
        days = []
        for d, day in enumerate(DAYS):
            if any(shift_span(a["days"][d]) for a in week.get("associates", [])):
                plan = channel_current(week, d, rules, draft)
                days.append((day, channel_grid(people_for(week, d, rules, plan, skills, inputs["languages"]), plan)))
        data = channel_plan_workbook(f"{row['program']}, {row['label']}", days)
        name = f"channel_plan_{secure_filename(row['program'] or 'schedule')}_{schedule_id}.xlsx"
        return send_file(io.BytesIO(data), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/schedules/<int:schedule_id>/auto-breaks", methods=["POST"])
    @login_required
    def auto_breaks(schedule_id: int):  # type: ignore[no-untyped-def]
        """Plan breaks automatically (Phase W): every break of the week, saved as a new version."""
        row = _version_or_404(schedule_id)
        use = request.form.get("use") == "1" and _may_set_in_use(row)
        try:
            found = _book().auto_breaks(schedule_id, g.user["id"], use)
        except ValueError as exc:  # the break rules could not be read, or an edit was refused: said, nothing saved
            flash(f"Breaks were not planned: {exc}")
            return redirect(url_for("run_schedules", run_id=row["run_id"], v=schedule_id))
        flash(found["said"])
        if request.form.get("back") == "week":
            return redirect(url_for("week_page", program=row["program"], week=row["week_start"]))
        return redirect(url_for("run_schedules", run_id=row["run_id"], v=found["id"]))

    @app.route("/schedules/<int:schedule_id>/week")
    @login_required
    def schedule_week(schedule_id: int):  # type: ignore[no-untyped-def]
        row = _version_or_404(schedule_id)
        elsewhere = None  # Phase Z: a version that is not in use says which schedule the week uses
        if not row["in_use"] and row["program"] and row["week_start"]:
            used = _book().in_use(row["program"], row["week_start"])
            if used is not None and used["run_id"] != row["run_id"]:
                elsewhere = {"run_id": used["run_id"],
                             "workbook": (app.extensions["store"].get_run(used["run_id"]) or {}).get("workbook", "")}
        return _version_week(row, "before" if request.args.get("side") == "before" else "after", elsewhere=elsewhere)

    # ------------------------------------------------------------- the day (Phase N)
    def _days() -> DayBook:
        days = app.extensions.get("days")
        if days is None:
            abort(404)
        return days

    def _date(text: str) -> Optional[date]:
        try:
            return in_range(datetime.strptime((text or "").strip(), "%Y-%m-%d").date())
        except ValueError:
            return None

    @app.route("/overview")
    @login_required
    def overview_page():  # type: ignore[no-untyped-def]
        """A program's day at a glance; breaks, attendance and cover are on RTA (the day page)."""
        days = _days()
        programs = _my_programs(days.programs())
        today = datetime.now(EGYPT)
        on = _date(request.args.get("date", "")) or today.date()
        program = clean_program(request.args.get("program", "")) or (programs[0] if programs else "")
        page, problem, ahead, attention = None, "", [], {}
        if program:
            try:
                page = days.page(program, on)
            except ValueError as exc:
                problem = str(exc)
        if page:
            v = page["view"]
            cells = [c for c in v["cells"] if c["pm"] is not None]
            now = today.hour * 60 + today.minute if on == today.date() else -1
            ahead = [c for c in cells if c["t"] + v["interval"] > now][:6]
            short = [c for c in cells if c["pm"] < 0 and c["t"] + v["interval"] > now]
            attention = {
                "short": short, "worst": min(short, key=lambda c: c["pm"]) if short else None,
                "absent": [(l["name"], s["status"]) for l in v["lanes"] for s in l["segments"]
                           if s["offset"] == 0 and s["status"] in ABSENT_STATES],
                "late": [(l["name"], s["status"], s.get("to") if s["status"] == "Late" else s.get("from"))
                         for l in v["lanes"] for s in l["segments"]
                         if s["offset"] == 0 and s["status"] in ("Late", "Left early")]}
        return render_template("overview.html", page=page, problem=problem, program=program, programs=programs,
                               on=on, ahead=ahead, attention=attention, week_of=week_start(on),
                               outlook=_outlook(program, week_start(on).isoformat()) if program else None,
                               label=ProgramBook(app.extensions["store"]).label(program) if program else "")

    @app.route("/schedules")
    @login_required
    def schedules_for():  # type: ignore[no-untyped-def]
        """The menu's Schedules (Phase AA, approved sample 03): the program's weeks with a kept schedule, and the
        chosen week's schedules side by side. The week shown is the one asked for, else this week when it has a
        schedule, else the newest."""
        program = clean_program(request.args.get("program", ""))
        book = _book()
        weeks = book.kept_weeks(program) if program else []
        keys = [w["week"] for w in weeks]
        today = datetime.now(EGYPT).date()
        this_week = (today - timedelta(days=(today.weekday() + 1) % 7)).isoformat()
        week = request.args.get("week", "")
        if week not in keys:
            week = this_week if this_week in keys else (keys[-1] if keys else "")
        entries = book.week_compare(program, week) if week else []
        return render_template("schedules_week.html", program=program, weeks=weeks, week=week, this_week=this_week,
                               entries=entries,
                               may_use={e["shown"]["id"] for e in entries if _may_set_in_use(e["shown"])},
                               may_delete={e["run"]["id"] for e in entries if _may_delete(e["run"])})

    # Phase AI: the 24 hours from the start picked; Phase AK: Fix breaks, Rescue the day and Change several breaks too
    WINDOW_TABS = ("timeline", "board", "adherence", "replan", "rescue", "bulk")
    START = re.compile(r"^([01]\d|2[0-3]):(00|15|30|45)$")

    def _own_zone(program: str, on: date) -> str:
        """The zone the schedule in use for ``program`` on ``on`` was made in (Egypt when none is kept)."""
        row = _days().version(program, on)[0] if program else None
        return pick_zone(((app.extensions["store"].get_run(row["run_id"]) or {}).get("tz") if row else "") or HOME)

    def _rta_choice(program: str, moved_for) -> Tuple[str, int]:
        """Phase AI: the zone and the day's start (minutes, in that zone) the RTA shows ``program`` in: as asked for,
        else as last picked for it this session; Egypt from midnight to begin with. ``window=operating`` (the program's
        operating day, kept in the schedule's time) starts it there; ``moved_for(zone)`` is the zone's shift."""
        every = dict(session.get("rta") or {})
        kept = dict(every.get(program) or {})
        if request.args.get("tz") in dict(ZONES):
            kept["tz"] = request.args["tz"]
        zone = pick_zone(kept.get("tz", ""))
        if START.match(request.args.get("start", "")):
            kept["start"] = request.args["start"]
        elif request.args.get("window") == "operating" and program:
            begins = app.extensions["store"].get_day_start(program)
            if begins is not None:
                kept["start"] = plain_hm(begins + moved_for(zone))
        if program and kept != every.get(program):
            every[program] = kept
            session["rta"] = every
        found = START.match(kept.get("start", "")) or START.match("00:00")
        return zone, int(found.group(1)) * 60 + int(found.group(2))

    @app.route("/day")
    @login_required
    def day_page():  # type: ignore[no-untyped-def]
        """A program's day from the schedule in use: who is on the floor, attendance, actual breaks. Phase AI: in the
        zone and from the start picked on the page; every time shown in that zone, and every change kept in the
        schedule's own time."""
        days = _days()
        programs = _my_programs(days.programs())
        on = _date(request.args.get("date", "")) or datetime.now(EGYPT).date()
        program = clean_program(request.args.get("program", ""))
        if not program and programs:
            program = next((p for p in programs if days.version(p, on)[0]), programs[0])
        own_zone = _own_zone(program, on)
        g.zone, start_at = _rta_choice(program, lambda zone: rta_shift(on, own_zone, zone) or 0)
        moved = rta_shift(on, own_zone, g.zone)
        g.rta_clock_notice = ""
        if moved is None:
            g.zone, moved = own_zone, 0
            g.rta_clock_notice = ("Clocks change in this window. Times and edits are shown in the schedule's own "
                                  "time zone. This schedule records wall-clock times and does not distinguish "
                                  "the two occurrences of a repeated hour.")
        units = _merge_units(program)  # Phase AP: a View pick when the program has two or more LOBs
        g.merge_pick = f"All LOBs of {ProgramBook(app.extensions['store']).unit(program)['program']['name']}" \
            if len(units) > 1 else ""
        merge = _merge_choice(program)
        with shown(moved):
            return _day_body(days, programs, on, program, own_zone, moved, start_at, merge)

    def _merge_choice(program: str) -> Optional[List[str]]:
        """Phase AP: the LOBs the RTA page shows as one (the program's LOBs) when "All LOBs" is picked, else None.
        The pick is kept for the program in the session, like the zone and the start."""
        units = _merge_units(program)
        if len(units) < 2:
            return None
        kept = dict(session.get("rta_merge") or {})
        pid = str(ProgramBook(app.extensions["store"]).unit(program)["program"]["id"])
        if "merge" in request.args:
            kept[pid] = "1" if request.args.get("merge") == "1" else ""
            session["rta_merge"] = kept
        return units if kept.get(pid) == "1" else None

    MERGE_TABS = ("timeline", "board", "adherence", "requests")  # Phase AP: the tabs that read, and change one person at a time

    def _day_body(days, programs: List[str], on: date, program: str, own_zone: str, moved: int,
                  start_at: int, merge: Optional[List[str]] = None):  # type: ignore[no-untyped-def]
        measure = request.args.get("measure", "")
        # Phase AS: with none in the address the RTA opens on the program's own (interval compliance until it says otherwise)
        measure = measure if measure in MEASURES else (ProgramBook(app.extensions["store"]).day_measure(program)
                                                       if program else "interval")
        tab = request.args.get("view", "")
        tab = tab if tab in ("board", "adherence", "meeting", "cover", "replan", "channels", "bulk", "rescue", "requests") else "timeline"
        if merge and tab not in MERGE_TABS:
            flash("Pick one LOB for that tab: it plans or changes one LOB's schedule.")
            return redirect(url_for("day_page", program=program, date=on.isoformat(), merge="1", tz=g.zone,
                                    start=request.args.get("start") or None), code=303)
        problem = ""
        try:
            if merge:
                page = merged_page(days, program, merge, on, measure, start_at - moved, g.zone, _own_zone) \
                    if program else None
            else:
                page = days.page(program, on, measure) if program else None
        except ValueError as exc:  # said on the page, not a server error
            page, problem = None, str(exc)
        anchor, sources, start = page, {0: page}, 0
        if page and merge:  # the merged page is already the 24 hours from the start picked
            start = page["view"]["start"]
        elif page:  # Phase AI: the 24 hours from the start picked, stitched from the schedule's days
            step = page["view"]["interval"]
            start = start_at - moved
            start -= start % step
            if start and tab in WINDOW_TABS:
                for d in range(start // 1440, (start + 1439) // 1440 + 1):
                    if d:
                        try:
                            sources[d] = days.page(program, on + timedelta(days=d), measure)
                        except ValueError:  # a workbook that cannot be read: its hours stay empty
                            sources[d] = None
                found = window_view({d: (x or {}).get("view") for d, x in sources.items()}, start, on)
                page = dict(page, view=found, target=at_target(found["cells"], page["target"]["target"]))
        window = bool(page and "start" in page["view"])
        clock_now = datetime.now(ZoneInfo(own_zone))
        now_at = (clock_now.date() - on).days * 1440 + clock_now.hour * 60 + clock_now.minute  # from on's midnight

        def source(t: int):  # type: ignore[no-untyped-def]
            """The schedule's day that holds minute ``t`` of the page (from ``on``'s midnight), its page and the
            minute in it."""
            d = t // 1440
            if d not in sources:
                try:
                    sources[d] = days.page(program, on + timedelta(days=d), measure)
                except ValueError:
                    sources[d] = None
            return on + timedelta(days=d), sources[d], t - 1440 * d

        people = shrink = whole = None
        finder: Dict[str, Any] = {}
        cover = None
        if page and tab == "meeting":
            finder = {"who": request.args.getlist("who"), "minutes": request.args.get("minutes", 30, type=int),
                      "from": request.args.get("from", "09:00"), "to": request.args.get("to", "18:00"),
                      "kind": request.args.get("kind", "Meeting"), "billable": request.args.get("billable") == "1",
                      "with_whom": request.args.get("with_whom", ""), "why": request.args.get("why", ""),
                      "with_dept": request.args.get("with_dept", "")}
            if finder["who"]:
                try:
                    finder["slots"] = days.meeting_slots(program, on, finder["who"], finder["minutes"],
                                                         to_schedule(finder["from"], moved),
                                                         to_schedule(finder["to"], moved), finder["billable"], measure)
                except ValueError as exc:
                    finder["error"] = str(exc)
        clock_now = datetime.now(ZoneInfo(own_zone))
        from_now = clock_now.hour * 60 + clock_now.minute if clock_now.date() == on else 0
        shift_view: Dict[str, Any] = {"shift_groups": [], "shift": "", "shift_names": None}
        if page and tab == "timeline":  # the Timeline by shift start (Phase W)
            wanted = request.args.get("shift", "").strip()
            wanted = wanted if wanted == "earlier" or re.match(r"^([01]\d|2[0-3]):[0-5]\d$", wanted) else ""
            groups = shift_groups(page["view"], from_now if clock_now.date() == on else None)
            chosen = next((g for g in groups if g["key"] == wanted), None)
            shift_view = {"shift_groups": groups, "shift": wanted,
                          "shift_names": set(chosen["names"]) if chosen else (set() if wanted else None)}
        outside: Dict[str, Any] = {"rows": [], "roles": COVER_ROLES, "channels": [], "languages": []}
        if page and tab == "cover":
            cover = days.offers(page, from_now)
            ch = page["view"].get("channels")  # Phase AJ: cover from outside the roster, on a channel when there are
            outside = {"rows": days.covers(program, on), "roles": COVER_ROLES,
                       "channels": [(r["letter"], r["name"]) for r in ch["rows"] if "language" not in r] if ch else [],
                       "languages": days.cover_languages(page)}
        proposal = days.replan_window(program, on, start, _window_now(on, start) or 0) if page and tab == "replan" else None
        bulk = _bulk_panel(days, page, program, on, moved, start) if page and tab == "bulk" else None  # Phase AD (sample 04)
        rescue = None  # Phase AD (sample 02): interval compliance only; the page says so for the other measure
        if page and tab == "rescue" and measure == "interval":
            try:
                rescue = days.rescue_plan(program, on, _window_now(on, start), page=None if start else page, start=start)
            except ValueError as exc:
                rescue = {"error": str(exc)}
        dayoff = days.dayoff_plan(anchor, from_now) if anchor and tab == "rescue" else None  # Phase AF (F1, F2)
        chfix = None  # Phase AM: Fix channels, shown before anything is kept
        if page and tab == "channels" and request.args.get("fix") == "1" and allowed(app.extensions["store"], g.user,
                                                                                    "rta_change"):
            try:
                chfix = days.channel_fix_plan(program, on, now=minute_now(on, own_zone, datetime.now(EGYPT)))
            except ValueError as exc:
                chfix = {"error": str(exc)}
        cover_panel = None
        cover_at = request.args.get("cover", type=int)
        if page and tab == "board" and cover_at is not None:
            held_on, held, at = source(cover_at)
            try:
                if held is None:
                    raise ValueError("No schedule for that hour.")
                cover_panel = {**days.cover_offers(held, at), "t": cover_at, "end": cover_at + page["view"]["interval"],
                               "date": held_on}  # Phase AI: the page's minutes, the day that holds them
            except ValueError as exc:
                flash(str(exc))
        add_panel = person_panel = None
        add_at = request.args.get("add", type=int)
        first_t = page["view"].get("start", 0) if page else 0
        held = None
        if page and add_at is not None and first_t <= add_at < first_t + 1440:  # "+ Add" on an interval (Phase R)
            held_on, held, t = source(add_at)  # Phase AI: the schedule's day that holds the interval
        if held is not None:
            step = held["view"]["interval"]
            row_at = add_at - add_at % step
            t -= t % step
            own = [(l, x) for l in held["view"]["lanes"] for x in l["segments"] if x["offset"] == 0]
            # Phase AC: someone marked sick or on leave goes last, so + Add never opens on a person it would refuse
            own.sort(key=lambda p: (p[1]["status"] in ABSENT_STATES,
                                    not (p[1]["start"] < t + step and t < p[1]["end"]), p[1]["start"], p[0]["name"]))
            # Phase AD (owner's yes, sample 06): nobody present on shift in this interval: open on Overtime for the
            # person whose shift starts right after it or ends right before it, placed and long enough to cover it
            nobody = bool(own) and not any(x["status"] not in ABSENT_STATES and x["start"] < t + step and t < x["end"]
                                           for _, x in own)
            if nobody:
                own.sort(key=lambda p: (p[1]["status"] in ABSENT_STATES,
                                        min(abs(p[1]["start"] - (t + step)), abs(t - p[1]["end"])), p[1]["start"],
                                        p[0]["name"]))
            first = own[0][1] if nobody else None
            side = "after" if first and first["start"] < t + step else "before"  # before, as always, unless it ended
            reach = (first["start"] - t if side == "before" else t + step - first["end"]) if first else 0
            minutes = min([m for m in ADD_LENGTHS if reach <= m <= OVERTIME_MAX] or [OVERTIME_MAX]) if first else None
            off = days.off_today(program, held_on)  # for "Day off cancelled" (Phase S)
            shifts = days.shift_library(program, held_on)
            add_panel = {"t": t, "end": t + step, "person": request.args.get("person", ""), "date": held_on,
                         "row": row_at,
                         "kinds": {k: v for k, v in ADD_KINDS.items() if off or DAY_OFF not in v},
                         "people": [(l["name"], x["label"], l["language"], x["start"], x["end"],
                                     x["status"].lower() if x["status"] in ABSENT_STATES else "") for l, x in own],
                         "kind_of": GROUP_KIND, "default_what": "Overtime" if nobody else "Break",
                         "default_side": side, "default_minutes": minutes,
                         "cell": next((c for c in held["view"]["cells"] if c["t"] == t), None),
                         "off": off, "shifts": shifts,
                         "shift_pick": max((x for x in shifts if x[1] <= t < x[2]), key=lambda x: x[1],
                                           default=shifts[0] if shifts else None)}  # most of it after this time
        # Find a time's and Change several breaks' "who" is their list of people, not one person's day
        who = request.args.get("who", "") if tab not in ("meeting", "bulk") else ""
        if page and who and add_panel is None:  # one person's day (Phase R)
            lane = next((l for l in page["view"]["lanes"] if l["name"] == who), None)
            if lane is not None:
                seg = next((x for x in lane["segments"] if x["offset"] == 0), lane["segments"][0])
                nowish = now_at if window else from_now
                first = seg["start"] if seg["start"] >= nowish else nowish
                person_panel = {"lane": lane, "seg": seg,
                                "date": seg.get("date") or (on if seg["offset"] == 0 else on - timedelta(days=1)),
                                "add_at": max(first_t, min(first_t + 1439, first - first % page["view"]["interval"]))}
        if page and tab == "adherence":
            v = page["view"]
            people = sorted((person_day(v, l["name"]) for l in v["lanes"] if any(x["offset"] == 0 for x in l["segments"])),
                            key=lambda r: (r["adherence"] is not None, r["adherence"] or 0, r["name"]))
            whole = team_figures(people)
            # Phase AI: each interval's planned shrinkage from the day that holds it
            planned = {t + 1440 * d: x for d, src in sources.items() if src
                       for t, x in src["inputs"].get("planned_shrinkage", {}).get(src["day"], {}).items()}
            if merge:  # Phase AP: each LOB's planned figure on the shared clock, the LOBs' mean at each interval
                found: Dict[int, List[float]] = {}
                for u, src in page["pages"].items():
                    for t, x in src["inputs"].get("planned_shrinkage", {}).get(src["day"], {}).items():
                        found.setdefault(t + page["merged"]["delta"][u], []).append(x)
                planned = {t: sum(xs) / len(xs) for t, xs in found.items()}
            shrink = interval_shrinkage(v, {"planned_shrinkage": {0: planned}}, 0)
        bar = {"undo": days.undoable(program, on, g.user["id"]) if program and page and not merge else None,  # Phase AD
               "send": _send_bar(program, on) if program and page and not merge else None,
               "resend": request.args.get("resend", 0, type=int)}
        # Phase AB: group posts (Phase AP: a merged page changes several LOBs, so it posts to no group and has no
        # Undo or Send bar: open the LOB for those)
        group = app.extensions["store"].get_notify(program) if program and not merge else None
        posting = bool(group and group["link"] and group["mode"] in ("on", "preview"))
        post_kinds = [k for k in (group or {}).get("kinds", "").split(",") if k] if posting else []
        now_of_day = now_at if window else (clock_now.hour * 60 + clock_now.minute if clock_now.date() == on
                                            else (10 ** 6 if on < clock_now.date() else -10 ** 6))
        tips = hover_tips(page["view"], now_of_day) if page else {}  # Phase AF (D2, D3)
        at_a_glance = glance(page["view"], now_of_day) if page else []  # Phase AF (D6)
        now_box = now_panel(page["view"], now_of_day) if page else None  # Phase AG (T2): today only
        shrinkage = None  # Phase AF (E1): in and out of office, side by side
        if page:
            kept = app.extensions["store"].get_shrinkage_map(program)
            mapping = read_mapping(kept["mapping"] if kept else None)
            leave_of = {n: k for u in (merge or [program]) for n, k in app.extensions["leave"].approved_on(u, on).items()}
            shrinkage = {**day_shrinkage(anchor["view"], anchor["week"], anchor["day"], mapping, anchor["inputs"],
                                         leave_of),
                         "mapping": mapping, "items": SHRINKAGE_ITEMS,
                         "may_set": allowed(app.extensions["store"], g.user, "setup")}
            if merge:  # Phase AP: the planned figure is the mean of the LOBs' own
                planned = [day_shrinkage(p["view"], p["week"], p["day"], mapping, p["inputs"])["in_office"]["planned"]
                           for p in page["pages"].values()]
                planned = [x for x in planned if x is not None]
                shrinkage["in_office"] = {**shrinkage["in_office"],
                                          "planned": sum(planned) / len(planned) if planned else None}
        return render_template("day.html", page=page, problem=problem, program=program, programs=programs, on=on,
                               today=clock_now.date(), tips=tips, at_a_glance=at_a_glance, shrinkage=shrinkage,
                               now_box=now_box, requests_waiting=_requests_waiting(program, g.user) if now_box else 0,
                               posts=app.extensions["notifier"].statuses(program, on.isoformat())
                               if program and on else {},
                               post_to=SERVICES.get(group["service"], "") if posting else "",
                               post_mode=group["mode"] if posting else "", post_kinds=post_kinds,
                               people=people, whole=whole, shrink=shrink, finder=finder, cover=cover, outside=outside,
                               ot_page=_paged(cover["overtime"] if cover else [], "ot_page", "ot-h"),
                               vto_page=_paged(cover["vto"] if cover else [], "vto_page", "vto-h"),
                               log_page=_paged(list(reversed(page["log"])) if page else [], "log_page", "daylog-h"),
                               proposal=proposal, from_now=from_now, cover_panel=cover_panel,
                               tile_now=now_at if window else (from_now if clock_now.date() == on else None),
                               add_panel=add_panel, person_panel=person_panel, lengths=ADD_LENGTHS, bar=bar,
                               overtime_hours=OVERTIME_MAX // 60,
                               bulk=bulk, shifts=BULK_SHIFTS, bulk_verb=bulk_verb, rescue=rescue, dayoff=dayoff, chfix=chfix,
                               team_names=sorted({u["display_name"] for u in app.extensions["store"].list_users()
                                                  if u["active"] and not u["is_associate"] and program
                                                  and Access(app.extensions["store"], u).can_open(program)},
                                                 key=str.lower),  # "With": the program's own staff (Phase AI)
                               with_lists=_with_lists(program) if program else [],  # or from the lists (Phase U)
                               tomorrow_unchecked=tomorrow_unchecked(on) if on else "",
                               activity_kinds=ACTIVITY_KINDS,
                               chhours=_channel_hours_for(merge or [program], page["week_start"])
                               if page and tab == "timeline" else None,
                               merged=bool(merge), lob_names=_lob_names(merge) if merge else {},
                               lob_by_name={l["name"]: l["lob"] for l in page["view"]["lanes"]} if page and merge else {},
                               measure=measure,
                               measures=MEASURES, tab=tab, statuses=STATUSES, aux=sorted(AUX), hm=hm,
                               rows=board(page["view"], page["target"]["target"]) if page and tab == "board" else None, week_of=week_start(on),
                               **_requests_tab(program, on, tab, merge),
                               earlier=on - timedelta(days=1), later=on + timedelta(days=1), **shift_view,
                               **_window_context(program, on, own_zone, moved, start_at, page, anchor, start, tab))

    def _requests_tab(program: str, on: date, tab: str, merge: Optional[List[str]] = None) -> Dict[str, Any]:
        """Phase AU: break changes and coaching on the RTA tab itself: the count for the tab, and (on the tab) the rows.
        In the view with every LOB of a program the rows are all those LOBs', each with its LOB."""
        if not program:
            return {"changes_n": 0}
        book, units = app.extensions["changes"], (merge or [program])
        found = {"changes_n": sum(book.count(u) for u in units)}
        if tab == "requests":
            rows = []
            for u in units:
                for r in _change_rows(u):
                    r["lob"] = ((ProgramBook(app.extensions["store"]).unit(u) or {}).get("lob") or {}).get("name") or u
                    rows.append(r)
            decided = sorted((r for u in units for r in book.decided(u)), key=lambda r: -(r["decided_at"] or r["asked"]))[:20]
            found.update(changes=rows, changes_decided=decided, unit=program,
                         may_change=allowed(app.extensions["store"], g.user, "rta_change"),
                         can_ask_coaching=_can_ask_coaching(),
                         back=url_for("day_page", program=program, date=on.isoformat(), view="requests", tz=g.zone,
                                      start=request.args.get("start") or None, merge="1" if merge else None))
        return found

    def _window_context(program: str, on: date, own_zone: str, moved: int, start_at: int, page, anchor, start: int,
                        tab: str) -> Dict[str, Any]:
        """Phase AI: what the page says and offers about its zone and start: the starts to pick from (each hour, and
        the program's operating day in the zone shown), where the page's 24 hours begin (``vx``, minutes from the
        day's midnight), the schedule's own zone, and the shift that turns the times shown into the schedule's."""
        begins = app.extensions["store"].get_day_start(program) if program else None
        op = plain_hm(begins + moved) if begins is not None else ""
        hours = sorted({plain_hm(m) for m in range(0, 1440, 60)} | ({op} if op else set()))
        starts = [(h, h + (", the operating day" if h == op else ", the calendar day" if h == "00:00" else ""))
                  for h in hours]
        vx = page["view"].get("start", 0) if page else 0
        return {"starts": starts, "start_at": plain_hm(start_at), "vx": vx, "moved": moved, "own_zone": own_zone,
                "own_name": dict(ZONES)[own_zone].split(" (")[0], "zone_name": dict(ZONES)[g.zone].split(" (")[0], "anchor_view": anchor["view"] if anchor else None,
                "on_anchor_day": bool(start) and tab not in WINDOW_TABS,
                "may_set_start": allowed(app.extensions["store"], g.user, "setup")}

    GOTO_PAGES = (  # (label, endpoint, what it needs: "" anyone, "unit" a program picked, "manager", "admin")
        ("Home", "home", ""), ("RTA", "day_page", "unit"), ("Overview", "overview_page", "unit"),
        ("Wallboard", "day_wallboard", "unit"), ("Weeks", "week_page", "unit"), ("Schedules", "schedules_for", "unit"),
        ("Analysis", "program", "unit"), ("Programs", "programs", ""), ("Exports", "exports_page", ""),
        ("Team", "team_page", ""), ("People", "admin_users", "manager"),
        ("Departments and people", "with_setup", "manager"), ("Associate channels", "channel_setup", "manager"),
        ("Notifications", "notifications_page", "admin"), ("LOBs and defaults", "program_setup", "admin"))
    GOTO_MAX = 8  # results per group

    @app.route("/goto")
    @login_required
    def goto():  # type: ignore[no-untyped-def]
        """Go to (Phase AG, T3): pages, programs and people matching ``q``, as JSON for the Ctrl K dialog."""
        words = request.args.get("q", "").casefold().split()
        program = clean_program(request.args.get("program", ""))
        on = _date(request.args.get("date", "")) or datetime.now(EGYPT).date()
        if program and not _access().can_open(program):
            abort(403)

        def hit(text: str) -> bool:
            return all(w in text.casefold() for w in words)

        items: List[Dict[str, str]] = []
        manager = allowed(app.extensions["store"], g.user, "setup")
        can_rta = allowed(app.extensions["store"], g.user, "rta_view")
        for label, endpoint, needs in GOTO_PAGES:
            permission = PERMISSION_ENDPOINTS.get(endpoint)
            if permission and not allowed(app.extensions["store"], g.user, permission):
                continue
            if (needs == "unit" and not program) or (needs == "manager" and not manager) or \
                    (needs == "admin" and not g.user["is_admin"]) or not hit(label):
                continue
            args = {"name": program} if endpoint == "program" else (
                {"program": program, **({"date": on.isoformat()} if endpoint in ("day_page", "overview_page") else {})}
                if needs == "unit" else {})
            items.append({"group": "Pages", "label": label, "note": _unit_name(program) if needs == "unit" else "",
                          "url": url_for(endpoint, **args)})
        units = sorted(k for k in unit_keys(app.extensions["store"]) if _access().can_open(k))
        items += [{"group": "Programs", "label": _unit_name(k), "note": "RTA", "url": url_for("day_page", program=k)}
                  for k in units if can_rta and words and (hit(k) or hit(_unit_name(k)))][:GOTO_MAX]
        if can_rta and program and words:
            found = []
            for name, cell in _days().roster(program, on):
                if not hit(name):
                    continue
                span, word = shift_span(cell), " ".join(str(cell or "").split()).casefold()
                note = (f"{on:%a} {hm(span[0])} to {hm(span[1])}" if span else
                        f"On leave on {on:%a}" if word == "leave" else f"Off on {on:%a}")
                found.append({"group": "People", "label": name, "note": note,
                              "url": url_for("day_page", program=program, date=on.isoformat(), who=name)})
            items += sorted(found, key=lambda i: i["label"])[:GOTO_MAX]
        return jsonify(items=items)

    @app.route("/day/operating-day", methods=["POST"])
    @manager_required
    def day_operating_start():  # type: ignore[no-untyped-def]
        """When a program's operating day starts (Phase AF, A4; admins and supervisors), in the schedule's time."""
        program = clean_program(request.form.get("program", ""))
        on = _date(request.form.get("date", ""))
        if not program or on is None:
            abort(400)
        if not _access().can_open(program):
            abort(403)
        typed = to_schedule(request.form.get("start", "").strip(), _shift_of(program, on))  # Phase AI: as shown
        m = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", typed)
        if not m or int(m.group(2)) % 15:
            flash("Give the start as a time on the quarter hour, like 16:00.")
        else:
            start = int(m.group(1)) * 60 + int(m.group(2))
            app.extensions["store"].set_day_start(program, start, g.user["id"])
            _record("operating_day_set", program=program, subject=hm(start), detail="operating day start")
            _say(f"The operating day starts at {hm(start)}.", program, on)
        return redirect(url_for("day_page", program=program, date=on.isoformat(), window="operating"), code=303)

    ADD_LENGTHS = (5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240)  # minutes offered by "+ Add"
    # What each "+ Add" choice is to a LOB's group rule (Phase AC: the tick shows only for a change that would post)
    GROUP_KIND = {**{k: "added_break" for k in ("Break", "Lunch")}, **{k: "aux" for k in AUX},
                  **{k: "private" for k in ABSENT_STATES}, **{k: "late" for k in ("Late", "Left early")},
                  "Overtime": "overtime", "VTO": "overtime", DAY_OFF: "called_in"}

    def _shift_of(program: str, on: Optional[date]) -> int:
        """Phase AI: minutes the RTA form showed its times ahead of the schedule's own (the form's ``tz``); 0 without
        one, as before."""
        zone = request.values.get("tz", "")
        if not program or on is None or zone not in dict(ZONES):
            return 0
        return zone_shift(on, _own_zone(program, on), zone)

    def _typed(key: str, program: str, on: Optional[date]) -> str:
        """A time typed or picked on the RTA, in the schedule's own time."""
        return to_schedule(request.form.get(key, "").strip(), _shift_of(program, on))

    def _say(text: str, program: str, on: Optional[date]) -> None:
        """Flash ``text`` (made in the schedule's time) with its times as the RTA form showed them."""
        flash(moved_text(text, _shift_of(program, on)))

    def _shown_data(value: Any, minutes: int) -> Any:
        """A JSON answer with every time of day in it as the RTA shows them."""
        if isinstance(value, str):
            return moved_text(value, minutes)
        if isinstance(value, dict):
            return {k: _shown_data(v, minutes) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_shown_data(v, minutes) for v in value]
        return value

    def _refused(exc: Exception, program: str, on: Optional[date]):  # type: ignore[no-untyped-def]
        return jsonify(error=moved_text(str(exc), _shift_of(program, on))), 400

    def _left_out_asked() -> bool:
        """The RTA unticked "Post to the group" for this one change (Phase AB): the form had the tick, and it is off."""
        return request.form.get("post_asked") == "1" and request.form.get("post") != "1"

    def _day_form():  # type: ignore[no-untyped-def]
        on = _date(request.form.get("date", ""))
        if on is None:
            raise ValueError("Pick a day.")
        return clean_program(request.form.get("program", "")), on, request.form.get("associate", "").strip()

    def _posted_day() -> Tuple[str, Optional[date]]:
        """The program and the day a form named (for its answer), whatever else it got wrong."""
        return clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))

    def _break_idx() -> int:
        try:
            return int(request.form.get("idx", ""))
        except ValueError:
            raise ValueError("Pick a break.") from None

    @app.route("/day/channel", methods=["POST"])
    @login_required
    def day_channel():  # type: ignore[no-untyped-def]
        """Phase V: a channel warning's fix, from the Channels tab: a channel change for someone (swap), moving the
        aux that caused it (activity) or a break (break); or taking a channel change back (cancel)."""
        try:
            program, on, name = _day_form()
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("day_page"), code=303)
        action, days, at = request.form.get("action", ""), _days(), request.form.get("at", "")
        try:
            if action == "swap":
                letter = request.form.get("channel", "")
                days.channel_move(program, on, name, _typed("from", program, on), _typed("to", program, on), letter,
                                  g.user["id"])
                flash(f"{name}: {CHANNEL_NAMES.get(letter, letter)} from {request.form.get('from')} to "
                      f"{request.form.get('to')}.")
            elif action == "activity":
                days.move_activity(program, on, request.form.get("id", -1, type=int), _typed("at", program, on),
                                   g.user["id"])
                flash(f"{name}: moved to {at}.")
            elif action == "break":
                days.move_break(program, on, name, _break_idx(), _typed("at", program, on), g.user["id"])
                flash(f"{name}: break moved to {at}.")
            elif action == "cancel":
                days.cancel_channel_move(program, on, request.form.get("id", -1, type=int), g.user["id"])
                flash("The channel change was taken back.")
            else:
                raise ValueError("Pick what to do.")
        except ValueError as exc:  # BreakRefused is a ValueError
            _say(str(exc), program, on)
        return _back_to_day(program, on, "channels")

    @app.route("/day/attendance", methods=["POST"])
    @login_required
    def day_attendance():  # type: ignore[no-untyped-def]
        try:
            program, on, name = _day_form()
            status = request.form.get("status", "")
            with_dept, with_whom, why = _aux_answers(status, program)
            _days().set_status(program, on, name, status, g.user["id"],
                               start=_typed("from", program, on), end=_typed("to", program, on),
                               billable=request.form.get("billable") == "1", with_whom=with_whom, why=why,
                               with_dept=with_dept)
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(ok=True)

    @app.route("/day/absences", methods=["POST"])
    @login_required
    def day_absences():  # type: ignore[no-untyped-def]
        """Absences already known for later days (Phase AF, F3), from the RTA: one person, a whole-shift status, from
        one day to another; the days they do not work are said, not recorded."""
        program = clean_program(request.form.get("program", ""))
        on = _date(request.form.get("date", ""))
        if not program or on is None:
            abort(400)
        if not _access().can_open(program):
            abort(403)
        name, status = request.form.get("associate", "").strip(), request.form.get("status", "")
        first = _date(request.form.get("first", ""))
        last = _date(request.form.get("last", "")) or first
        try:
            if not name or first is None:
                raise ValueError("Pick who and the first day.")
            found = _days().record_absences(program, name, status, first, last, g.user["id"])
            said = []
            if found["done"]:
                said.append(f"Recorded {status.lower()} for {name} on {', '.join(f'{d:%a %d %b}' for d in found['done'])}.")
            if found["off"]:
                said.append(f"{name} is off on {', '.join(f'{d:%a %d %b}' for d in found['off'])}: nothing recorded.")
            if found["missing"]:
                said.append(f"No schedule here for {', '.join(f'{d:%a %d %b}' for d in found['missing'])}.")
            flash(" ".join(said))
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("day_page", program=program, date=on.isoformat()), code=303)

    @app.route("/day/break", methods=["POST"])
    @login_required
    def day_break():  # type: ignore[no-untyped-def]
        try:
            program, on, name = _day_form()
            at = _typed("at", program, on) or None
            with leave_out(_left_out_asked()):
                _days().move_break(program, on, name, _break_idx(), at, g.user["id"])
        except ValueError as exc:  # BreakRefused is a ValueError
            return _refused(exc, *_posted_day())
        return jsonify(ok=True)

    def _bulk_form() -> Dict[str, Any]:
        f = request.values
        return {"names": f.getlist("who"), "which": f.get("which", ""), "action": f.get("act", ""),
                "amount": f.get("amount", 0, type=int), "at": f.get("at", ""), "why": f.get("why", "")}

    def _bulk_panel(days, page: Dict[str, Any], program: str, on: date, moved: int = 0,
                    start: int = 0) -> Dict[str, Any]:
        """Change several breaks (Phase AD, sample 04): today's people by shift start with their breaks, the form as
        filled, and the effect once asked for (nothing kept)."""
        now = _window_now(on, start)
        groups: Dict[int, List[Dict[str, str]]] = {}
        kinds: List[str] = []
        for lane in page["view"]["lanes"]:
            for seg in lane["segments"]:
                if seg["offset"] != 0 or seg["status"] in ABSENT_STATES:
                    continue
                said = [f"{b['kind']} {hm(b['start'])}" + (" (started)" if now is not None and b["start"] <= now else "")
                        for b in seg["breaks"]] + [f"{b['kind']} cancelled" for b in seg.get("cancelled", [])]
                groups.setdefault(seg["start"], []).append({"name": lane["name"], "breaks": ", ".join(said)})
                kinds += [b["kind"] for b in seg["breaks"] + seg.get("cancelled", []) if b["kind"] not in kinds]
        form = _bulk_form()
        panel = {"groups": [{"label": f"{hm(t)} shift", "people": people} for t, people in sorted(groups.items())],
                 "kinds": kinds, "who": set(form["names"]), "which": form["which"] or (kinds[0] if kinds else "all"),
                 "act": form["action"] or "cancel", "amount": form["amount"] or 15, "at": form["at"],
                 "why": form["why"], "preview": None, "error": ""}
        if request.args.get("show") and form["names"]:
            try:
                panel["preview"] = days.bulk_preview(program, on, form["names"], panel["which"], panel["act"],
                                                     panel["amount"], to_schedule(form["at"], moved), form["why"], now,
                                                     start=start)
            except ValueError as exc:
                panel["error"] = str(exc)
        return panel

    @app.route("/day/bulk/apply", methods=["POST"])
    @login_required
    def day_bulk_apply():  # type: ignore[no-untyped-def]
        """Phase AD: keep a Change several breaks as one change, held from the group until Send."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        form = _bulk_form()
        try:
            if on is None:
                raise ValueError("Pick a day.")
            start = _form_start()
            done = _days().apply_bulk(program, on, form["names"], form["which"], form["action"], g.user["id"],
                                      amount=form["amount"], at=_typed("at", program, on), why=form["why"],
                                      now=_window_now(on, start), start=start)
            said = bulk_verb(form["action"], done)
            _say(said[0].upper() + said[1:] + ".", program, on)
        except ValueError as exc:
            _say(f"Stopped: {exc} Anything changed before it was kept, and Undo takes it all back.", program, on)
        return _back_to_day(program, on, "")

    def _send_bar(program: str, on: date) -> Optional[Dict[str, Any]]:
        """Phase AD (samples 05a, 05b): the newest bulk change of this LOB's day (or the undo of one) and what it
        has with the group: held for Send, posted, or a correction to send; None when nothing goes to a group."""
        store, notifier = app.extensions["store"], app.extensions["notifier"]
        for a in reversed(store.day_actions(program, on.isoformat())):
            of = store.get_day_action(a["undo_of"]) if a["kind"] == "undo" and a["undo_of"] else None
            if a["kind"] != "bulk" and not (of and of["kind"] == "bulk"):
                continue
            state = notifier.action_state(a)
            return {**state, "action": a, "of": of} if state else None
        return None

    @app.route("/day/send", methods=["POST"])
    @login_required
    def day_send():  # type: ignore[no-untyped-def]
        """Phase AD: post a bulk change (or its correction) to the LOB's group; once posted, only when asked again."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        view = request.form.get("view", "")
        action = app.extensions["store"].get_day_action(request.form.get("action_id", 0, type=int))
        if on is None or not action or action["program"] != program or action["shift_date"] != on.isoformat():
            flash("That change is not on this day: open the day again.")
            return _back_to_day(program, on, view)
        posted, said = app.extensions["notifier"].send_action(action, again=request.form.get("again") == "1")
        flash(said)
        if not posted and said.startswith("Already posted"):  # asked on the page (the script asks in a dialog)
            args = {"program": program, "date": on.isoformat(), "resend": action["id"],
                    "view": view if view in ("board", "adherence", "meeting", "cover", "replan", "channels", "bulk", "rescue") else None}
            return redirect(url_for("day_page", **{k: v for k, v in args.items() if v}) + "#act-bar", code=303)
        return _back_to_day(program, on, view)

    @app.route("/day/undo-last", methods=["POST"])
    @login_required
    def day_undo_last():  # type: ignore[no-untyped-def]
        """Phase AD: take back your own newest change on this LOB's day (2 at most)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _say(_days().undo_last(program, on, g.user["id"]), program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, request.form.get("view", ""))

    @app.route("/day/break/cancel", methods=["POST"])
    @login_required
    def day_break_cancel():  # type: ignore[no-untyped-def]
        """Phase AD: cancel a break with a reason (sample 03); answered like a break move."""
        try:
            program, on, name = _day_form()
            with leave_out(_left_out_asked()):
                _days().cancel_break(program, on, name, _break_idx(), request.form.get("why", ""), g.user["id"],
                                     now=_minute_now(on))
        except ValueError as exc:  # BreakRefused is a ValueError
            return _refused(exc, *_posted_day())
        return jsonify(ok=True)

    def _minute_now(on: Optional[date], program=None) -> Optional[int]:
        """Now in the schedule timezone when ``on`` is today; None for another date."""
        if on is None:
            return None
        program = program or clean_program(request.values.get("program", ""))
        at = minute_now(on, _own_zone(program, on), datetime.now(EGYPT))
        return at if 0 <= at < 1440 else None

    MINUTE = re.compile(r"^-?\d{1,4}$")  # a minute of the page's 24 hours (Phase AI: before 0 too)

    def _window_now(on: Optional[date], start: int, program=None) -> Optional[int]:
        """Phase AK: now as a minute from ``on``'s midnight when it falls in the 24 hours from ``start``, else None
        (from 0, as ``_minute_now``)."""
        if on is None:
            return None
        program = program or clean_program(request.values.get("program", ""))
        at = minute_now(on, _own_zone(program, on), datetime.now(EGYPT))
        return at if start <= at < start + 1440 else None

    def _form_start() -> int:
        """The minute the page's 24 hours began at, as the form sent it (0 when it did not)."""
        value = request.form.get("start", "0")
        return int(value) if MINUTE.match(value) else 0

    def _move_item(item: str) -> Tuple[Any, ...]:
        """A move from a form: "name|idx|minute" on the page's day, or "name|idx|minute|YYYY-MM-DD" on its shift's own
        date (Phase AK)."""
        try:
            head, last = item.rsplit("|", 1)
            when = _date(last) if re.match(r"^\d{4}-\d{2}-\d{2}$", last) else None
            name, idx, minute = (head if when else item).rsplit("|", 2)
            return (name, int(idx), int(minute)) + ((when,) if when else ())
        except ValueError:
            raise ValueError("A move in the form cannot be read: open the tool again.") from None

    def _back_to_day(program: str, on: Optional[date], view: str, cover: str = ""):  # type: ignore[no-untyped-def]
        on = _date(request.form.get("anchor", "")) or on  # Phase AI: the day the page showed, not the shift's own
        args = {"program": program, "date": on.isoformat() if on else None,
                "view": view if view in ("board", "adherence", "meeting", "cover", "replan", "channels", "bulk", "rescue") else None,
                "cover": cover if MINUTE.match(cover) and view == "board" else None}
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
            moves = [_move_item(item) for item in request.form.getlist("move")]
            days = _days()
            with days.action(program, on, g.user["id"], bulk=True) as act:  # Phase AD: one change, held for Send
                try:
                    done = days.apply_replan(program, on, moves, g.user["id"])
                finally:
                    n = len(act.logs)
                    act.label = f"Fix breaks moved {n} break{'s' if n != 1 else ''}"
            flash(f"Moved {done} break{'s' if done != 1 else ''}.")
        except ValueError as exc:
            _say(f"Stopped: {exc} The moves before it were kept; open the autopilot again for a fresh proposal.", program,
                 on)
        return _back_to_day(program, on, "")

    @app.route("/day/rescue/apply", methods=["POST"])
    @login_required
    def day_rescue_apply():  # type: ignore[no-untyped-def]
        """Phase AD: keep the Rescue the day moves as one change, held from the group until Send."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            moves = [_move_item(item) for item in request.form.getlist("move")]
            if not moves:
                raise ValueError("No moves to keep.")
            start = _form_start()
            done = _days().apply_rescue(program, on, moves, g.user["id"], now=_window_now(on, start), start=start)
            flash(f"Rescue the day moved {done} break{'s' if done != 1 else ''}.")
        except ValueError as exc:
            _say(f"Stopped: {exc} Anything changed before it was kept, and Undo takes it all back.", program, on)
        return _back_to_day(program, on, "")

    @app.route("/day/channels/fix", methods=["POST"])
    @login_required
    def day_channel_fix():  # type: ignore[no-untyped-def]
        """Phase AM: keep the Fix channels changes shown in the preview as one change (one step for Undo)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            changes = []
            for item in request.form.getlist("change"):
                name, lo, hi, letter = (item.split("|") + ["", "", "", ""])[:4]
                if not (lo.isdigit() and hi.isdigit()) or letter not in ("P", "C", "E"):
                    raise ValueError("A change in the list cannot be read: open Fix channels again.")
                changes.append((name, int(lo), int(hi), letter))
            if not changes:
                raise ValueError("No changes to keep.")
            done = _days().apply_channel_fix(program, on, changes, g.user["id"], now=minute_now(on, _own_zone(program, on), datetime.now(EGYPT)))
            flash(f"Fix channels changed {done} stretch{'es' if done != 1 else ''}. Undo takes them all back.")
        except ValueError as exc:
            _say(f"No changes were saved: {exc}", program, on)
        return _back_to_day(program, on, "channels")

    @app.route("/day/daily-views.xlsx")
    @login_required
    def day_daily_views():  # type: ignore[no-untyped-def]
        """Phase AP (sample ap01, D): a workbook with a sheet for each associate on the page the RTA shows (one LOB, or
        the merged page), after the day's changes, in the zone and from the start picked."""
        days = _days()
        program, on = clean_program(request.args.get("program", "")), _date(request.args.get("date", ""))
        if not program or on is None:
            abort(400)
        own_zone = _own_zone(program, on)
        g.zone, start_at = _rta_choice(program, lambda zone: rta_shift(on, own_zone, zone) or 0)
        moved = rta_shift(on, own_zone, g.zone)
        if moved is None:
            g.zone, moved = own_zone, 0
        merge = _merge_choice(program)
        try:
            if merge:
                page = merged_page(days, program, merge, on, "interval", start_at - moved, g.zone, _own_zone)
            else:
                page = days.page(program, on)
                if page is not None:
                    start = start_at - moved
                    page = days.window_page(program, on, start - start % page["view"]["interval"])
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("day_page", program=program, date=on.isoformat()), code=303)
        if page is None:
            abort(404)
        shown_at = start_at
        people = people_of(page["view"], moved, _lob_names(merge) if merge else None)
        heading = (f"{on:%A %d %b %Y}, times in {dict(ZONES)[g.zone]}, the 24 hours from {plain_hm(shown_at)}. "
                   "As recorded on the RTA when this was downloaded.")
        name = secure_filename(f"Daily_views_{(_merged_name(program, merge) if merge else program)}_{on}") + ".xlsx"
        _record("downloaded", subject=name, program=program, detail="Daily views")
        return send_file(io.BytesIO(daily_workbook(people, heading)), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
        programs = _my_programs(days.programs())
        program = clean_program(request.args.get("program", "")) or (programs[0] if programs else "")
        page = days.page(program, on) if program else None
        board_now = None
        if page:
            v = page["view"]
            step = v["interval"]
            first = now - now % step
            rows = [c for c in board(v, page["target"]["target"]) if first <= c["t"] < first + 4 * step]
            on_break, soon = [], []
            for lane in v["lanes"]:
                for seg in lane["segments"]:
                    if seg["status"] in ABSENT_STATES:
                        continue
                    added = [{"kind": a["kind"], "start": a["start"], "minutes": a["end"] - a["start"]}
                             for a in seg.get("activities", []) if a["kind"] in EXTRA_BREAKS]  # added on the day
                    for b in seg["breaks"] + added:
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
            start, _, end = request.form.get("span", "").partition("|")  # a picked length ("21:00|21:45")
            if not request.form.get("span"):
                start, end = request.form.get("from", ""), request.form.get("to", "")
            start, end = (to_schedule(x.strip(), _shift_of(program, on)) for x in (start, end))
            with_dept, with_whom, why = _aux_answers(kind, program)
            warning = _days().add_activity(program, on, name, kind, start, end, g.user["id"], dry_run=True,
                                           with_whom=with_whom, why=why, with_dept=with_dept).get("warning", "") \
                if kind == "Overtime" else ""
            _days().add_activity(program, on, name, kind, start, end,
                                 g.user["id"], billable=request.form.get("billable") == "1",
                                 note=request.form.get("note", ""), with_whom=with_whom, why=why, with_dept=with_dept)
            flash(f"Recorded: {name}, {'day off cancelled (called in)' if kind == 'Called in' else kind.lower()}.")
            if warning:
                _say(f"Warning: {warning}", program, on)
            if kind in ("Overtime", "Called in") and _days().next_week_unknown(program, on):
                flash(tomorrow_unchecked(on))
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, request.form.get("view", ""), request.form.get("cover", ""))

    @app.route("/day/cover", methods=["POST"])
    @login_required
    def day_cover():  # type: ignore[no-untyped-def]
        """Phase AJ: a team manager or support member, not on the roster, logging in to cover intervals."""
        program, on = _posted_day()
        try:
            if on is None:
                raise ValueError("Pick a day.")
            with leave_out(_left_out_asked()):
                _days().add_cover(program, on, request.form.get("name", ""), request.form.get("role", ""),
                                  _typed("from", program, on), _typed("to", program, on), g.user["id"],
                                  channel=request.form.get("channel", ""), language=request.form.get("language", ""))
            flash(f"Recorded: {' '.join(request.form.get('name', '').split())} covering.")
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "cover")

    @app.route("/day/cover/cancel", methods=["POST"])
    @login_required
    def day_cover_cancel():  # type: ignore[no-untyped-def]
        program, on = _posted_day()
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _days().cancel_cover(program, on, request.form.get("id", 0, type=int), g.user["id"])
            flash("Cancelled.")
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "cover")

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
            _say(str(exc), program, on)
        return _back_to_day(program, on, request.form.get("view", ""))

    def _with_lists(program: str) -> list:
        """The departments a booking picks from (Phase U): those of the program's lists with someone in them."""
        return [d for d in ContactBook(app.extensions["store"]).for_unit(program) if d["people"]]

    def _aux_answers(kind: str, program: str) -> Tuple[str, str, str]:
        """(department, with, why) for an aux, from the form: every way of booking one asks who it is with and why
        (Phase T); from the program's lists when it has them, typed when it has none (Phase U)."""
        dept, with_whom = request.form.get("with_dept", ""), request.form.get("with_whom", "")
        lists = _with_lists(program) if kind in AUX else []
        if lists:
            dept, with_whom = pick_contact(lists, kind, dept, with_whom)
        with_whom, why = aux_details(kind, with_whom, request.form.get("why", ""))
        return (dept if lists else ""), with_whom, why

    def _add_fields():  # type: ignore[no-untyped-def]
        program, on, name = _day_form()
        minutes = request.form.get("minutes", "0")
        return program, on, name, request.form.get("what", ""), _typed("from", program, on), \
            int(minutes) if minutes.isdigit() else -1, request.form.get("billable") == "1"

    def _to_row(program: str, on: Optional[date], view: str, at: str):  # type: ignore[no-untyped-def]
        on = _date(request.form.get("anchor", "")) or on  # Phase AI: the day the page showed
        args = {"program": program, "date": on.isoformat() if on else None,
                "view": view if view in ("board", "cover") else None}
        if MINUTE.match(at):
            args["_anchor"] = f"row-{at}"
        return redirect(url_for("day_page", **{k: v for k, v in args.items() if v}), code=303)

    @app.route("/day/add", methods=["POST"])
    @login_required
    def day_add():  # type: ignore[no-untyped-def]
        """RTA's "+ Add": anything in an interval (a break, lunch, aux, attendance, overtime or VTO)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            program, on, name, what, start, minutes, billable = _add_fields()
            with_dept, with_whom, why = _aux_answers(what, program)
            with leave_out(_left_out_asked()):
                found = _days().add_item(program, on, name, what, start, minutes, g.user["id"], billable=billable,
                                         note=request.form.get("note", ""), end=_typed("to", program, on),
                                         with_whom=with_whom, why=why, with_dept=with_dept,
                                         side=request.form.get("side", ""))
            _say(f"Recorded: {name}, {found['text']}.", program, on)
            if found.get("warning"):
                _say(f"Warning: {found['warning']}", program, on)
            if what in ("Overtime", DAY_OFF) and _days().next_week_unknown(program, on):
                flash(tomorrow_unchecked(on))
        except ValueError as exc:
            _say(str(exc), program, on)
        return _to_row(program, on, request.form.get("view", "board"), request.form.get("at", ""))

    @app.route("/day/add-preview", methods=["POST"])
    @login_required
    def day_add_preview():  # type: ignore[no-untyped-def]
        measure = request.form.get("measure", "")
        try:
            program, on, name, what, start, minutes, billable = _add_fields()
            found = _days().preview_item(program, on, name, what, start, minutes, billable,
                                         measure if measure in MEASURES else "interval",
                                         end=_typed("to", program, on),  # who and why are asked on Add
                                         side=request.form.get("side", ""))
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(_shown_data(found, _shift_of(program, on)))

    @app.route("/day/undo", methods=["POST"])
    @login_required
    def day_undo():  # type: ignore[no-untyped-def]
        """From one person's day: a status back to Present, or a moved break back to the plan."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            program, on, name = _day_form()
            if request.form.get("what") == "status":
                _days().set_status(program, on, name, "Present", g.user["id"])
                flash(f"{name} is back to present.")
            elif request.form.get("what") == "break":
                _days().move_break(program, on, name, _break_idx(), None, g.user["id"])
                flash(f"{name}'s break is back to the plan.")
            else:
                abort(400)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _to_row(program, on, request.form.get("view", ""), request.form.get("at", ""))

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
            with_dept, with_whom, why = _aux_answers(kind, program)
            _days().book_session(program, on, who, start, minutes, kind, g.user["id"],
                                 billable=request.form.get("billable") == "1", with_whom=with_whom, why=why,
                                 with_dept=with_dept)
            _say(f"Booked: {kind.lower()} {hm(start)} to {hm(start + minutes)} for {', '.join(who)}.", program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "meeting")

    @app.route("/day/channel-preview", methods=["POST"])
    @login_required
    def day_channel_preview():  # type: ignore[no-untyped-def]
        """Phase AF (C3): what a channel change would cause, before it is kept (JSON)."""
        try:
            program, on, name = _day_form()
            found = _days().channel_preview(program, on, name, _typed("from", program, on),
                                            _typed("to", program, on), request.form.get("channel", ""))
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(_shown_data(found, _shift_of(program, on)))

    @app.route("/day/break-advice", methods=["POST"])
    @login_required
    def day_break_advice():  # type: ignore[no-untyped-def]
        measure = request.form.get("measure", "")
        try:
            program, on, name = _day_form()
            found = _days().break_advice(program, on, name, _break_idx(), _typed("at", program, on),
                                         measure if measure in MEASURES else "interval")
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(_shown_data(found, _shift_of(program, on)))

    # ------------------------------------------------------------- exports (Phase O)
    def _export_args() -> Dict[str, Any]:
        today = datetime.now(EGYPT).date()
        start = _date(request.args.get("from", "")) or today.replace(day=1)
        end = _date(request.args.get("to", ""))
        pick = request.args.get("pick", "")
        kind, _, value = pick.partition(":")
        program = clean_program(value if kind == "key" else request.args.get("program", "")) or None
        if program is not None and not _access().can_open(program):
            abort(403)
        wanted = request.args.get("user", type=int)
        if wanted is not None:  # Phase AT: filtering by a person is only for a person this user may see
            person = app.extensions["store"].get_user(wanted)
            if person is None or not _access().sees(person):
                abort(403)
        if kind == "group":  # a whole program: all of its LOBs
            found = next((p for p in _access().programs() if str(p["id"]) == value), None)
            if found is None:
                abort(403)
            program = sorted(found["units"])
        elif program is None and _access().keys() is not None:
            program = sorted(_access().keys())  # "all programs" means all of this person's programs
        if end is None:  # to the latest day anything was recorded for, when that is after today (owner, 2026-10-09:
            # changes made for a schedule that starts next week did not show in the default period)
            latest = _date(app.extensions["store"].latest_record_date(program) or "")
            end = min(max(today, latest or today), start + timedelta(days=MAX_EXPORT_DAYS - 1))
        return {"start": start, "end": end, "program": program, "pick": pick,
                "user_id": request.args.get("user", type=int),
                "measure": request.args.get("measure", "") if request.args.get("measure", "") in MEASURES else "interval"}

    def _exports_page(error: str = "", status: int = 200):  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        a = _export_args()
        today = datetime.now(EGYPT).date()
        sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        presets = [("Today", today, today), ("This week", sunday, sunday + timedelta(days=6)),
                   ("Next week", sunday + timedelta(days=7), sunday + timedelta(days=13)),
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
                               programs=_my_programs(_days().programs()) if app.extensions.get("days") else [],
                               pick_tree=_access().programs(), everything=_access().everything(),
                               users=[u for u in store.list_users() if _access().sees(u)],  # Phase AR: this program's people
                               measures=MEASURES, **a), status

    def _coach_args() -> Dict[str, Any]:
        days = _days()
        programs = _my_programs(days.programs())
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
                                            a["program"], a["user_id"], g.user["display_name"], a["measure"],
                                            deadline=time.monotonic() + EXPORT_SECONDS)
        except ValueError as exc:  # said on the page (in JSON when the page's script asked: Phase W)
            if request.headers.get("X-Requested-With") == "fetch":
                return jsonify(error=str(exc)), 400
            return _exports_page(str(exc), 400)
        _record("exported", subject=name, program=a["program"] if isinstance(a["program"], str) else "",
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
        if not _can_resume(run):  # Phase AC: the page offers it only then; a direct request gets the same answer
            flash("This run cannot be resumed: " + ("a readiness check builds no schedule. Start the run instead."
                                                    if run["mode"] == "SMOKE" else
                                                    "the engine found the workbook needs a change before it can be "
                                                    "scheduled. Fix the workbook and run it again."
                                                    if run["status"] in RESUMABLE else
                                                    f"it is {label(run).lower()}."))
            return redirect(url_for("run_detail", run_id=run_id))
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
    @app.errorhandler(405)
    @app.errorhandler(413)
    def _error(err):  # type: ignore[no-untyped-def]
        """What went wrong and what to do (Phase XY): a reason given where the error was raised wins over the
        default words for its code. Phase AC: a wrong-method request (a reload of a form's address) too."""
        messages = {403: "Your account cannot do this.", 404: "This page does not exist.",
                    405: "This address opens only from its form.", 413: "That file is larger than 25 MB."}
        hints = {403: "Ask an admin if you need it.", 404: "The link may be old, or the page moved.",
                 405: "Go back, then send the form again.", 413: "Pick a smaller workbook."}
        said = getattr(err, "description", "") or ""
        own = bool(said) and said != type(err).description  # words given where it was raised
        text = said if own else messages.get(err.code, said or "Something went wrong.")
        hint = g.get("error_hint") or ("" if own else hints.get(err.code, ""))
        return render_template("error.html", code=err.code, message=text, hint=hint), err.code

    return app
