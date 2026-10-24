# © 2026 Omar Mokhtar. All rights reserved.
"""The team scheduler website: the Flask application factory. ``create_app`` sets up the stores, the request hooks and
the helpers the areas share; the routes live in ``webapp/routes``, one module per area."""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    abort,
    flash,
    g,
    has_request_context,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.sessions import SecureCookieSessionInterface

from .attendance import DayBook, operating_span, with_text  # noqa: F401  operating_span: read by webapp/routes through this module (tests replace it)
from .channel_page import NAMES as CHANNEL_NAMES
from .channel_plan import plan_day  # noqa: F401  read by webapp/routes through this module (tests replace it)
from .clock import EGYPT, HOME, SHOWN, ZONES, moved_text
from .permissions import ENDPOINTS as PERMISSION_ENDPOINTS, allowed, matrix
from .day import channel_letters
from .leave import LeaveBook
from .swaps import SwapBook
from .insights_page import dur as insights_dur
from .outcome import cannot_schedule
from .access import Access, role
from .notify import Notifier, post_json
from .programs import ProgramBook
from .auth import associate_allowed, check_csrf, csrf_token, load_user
from .schedules import ScheduleBook, group_changes
from .versions import zoned_label
from .paging import page_of
from .runs import MODES, OPTION_LABELS, RunQueue, run_options
from .store import Store
from .throttle import SignInThrottle
from werkzeug.datastructures import ImmutableMultiDict
from .change_requests import ChangeBook
from .merged_day import lob_of

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
    ctx = SimpleNamespace()  # what the route areas share (see webapp/routes)
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
        try:  # Phase AY (owner, 2026-10-23): VTO is gone; every VTO already recorded becomes an Early leave, back dated
            found = app.extensions["days"].convert_vto_to_early_leave()
            if found["converted"] or found["skipped"]:
                logging.getLogger(__name__).info("VTO converted to Early leave: %s done, %s skipped %s", found["converted"],
                                                 len(found["skipped"]), found["skipped"])
        except Exception:  # noqa: BLE001 (a failed conversion never stops the site; the VTO records stay as they are)
            logging.getLogger(__name__).exception("VTO conversion failed")
        app.extensions["leave"] = LeaveBook(app.extensions["store"], app.extensions["days"])  # Phase AG
        app.extensions["leave"].recover()  # Phase AI: an approval a stopped server left half done goes back to the RTA
        # Phase AO: leave approved while a week had no schedule is applied once that week's schedule is kept
        queue.on_kept = lambda run_id: app.extensions["leave"].apply_waiting(app.extensions["store"].get_run(run_id))
        app.extensions["swaps"] = SwapBook(app.extensions["store"], app.extensions["days"])
        app.extensions["days"].measure_of = lambda unit: ProgramBook(app.extensions["store"]).day_measure(unit)  # Phase AU
        app.extensions["changes"] = ChangeBook(app.extensions["store"], app.extensions["days"],
                                               lambda unit: ProgramBook(app.extensions["store"]).day_measure(unit),  # Phase AS
                                               lambda unit: ProgramBook(app.extensions["store"]).request_settings_for_unit(unit))
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
        # Phase AF (D5): the page asks for a zone; Phase AY (owner, 2026-10-23: "everything by default should match the pc timezone unless it
        # has been changed manually"): without one, the zone of the person's computer, else Egypt
        g.zone = request.args["tz"] if request.args.get("tz") in dict(ZONES) else (ctx._pc_zone() or HOME)
        if g.get("user") and request.method == "POST" and request.endpoint in ctx.DAY_WRITES:
            try:
                ctx._still_editable(ctx._date(request.form.get("date", "")), ctx._date(request.form.get("first", "")))
            except ValueError as exc:
                if "application/json" in request.headers.get("Accept", ""):
                    return jsonify(error=str(exc)), 400
                flash(str(exc))
                return ctx._back_to_day(clean_program(request.form.get("program", "")), ctx._date(request.form.get("date", "")),
                                    request.form.get("view", ""))
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
            on = ctx._date(request.form.get("date", ""))
            zone = request.form.get("tz", "")
            if program and on and zone in dict(ZONES) and ctx._window_moved(program, on, zone) is None:
                message = "Clocks change in this RTA window. Reopen the day in the schedule's own time zone before editing."
                if request.accept_mimetypes.best == "application/json":
                    return jsonify(error=message), 400
                flash(message)
                return redirect(url_for("day_page", program=program, date=on.isoformat(),
                                        tz=ctx._own_zone(program, on)), code=303)

    def _route_to_lob() -> None:
        """Phase AP (owner, 2026-10-21: edits go through to each person's own LOB): a form from the merged RTA page
        names the page's program; swap it for the LOB that lists the person, so every route works as before on that
        LOB, in that LOB's own time."""
        program, on = clean_program(request.form.get("program", "")), ctx._date(request.form.get("date", ""))
        units = ctx._merge_units(program) if program else []
        if len(units) < 2 or on is None:
            return
        own = lob_of(ctx._days(), units, on, request.form.get("associate", "").strip())
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
        # Phase AY (owner, 2026-10-23: split view): only the embedded day page may be framed, and only by this site
        framed = request.endpoint == "day_page" and request.args.get("embed") == "1"
        ancestors = "'self'" if framed else "'none'"
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN" if framed else "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; "
            f"frame-ancestors {ancestors}; base-uri 'self'; form-action 'self'; object-src 'none'")  # Phase AG: fonts and icons are served by the site itself; Phase AT: no base tag, forms post here only
        # Phase AT: a signed-in page is never kept by the browser or a proxy (the back button after sign-out shows nothing)
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    app.add_template_filter(insights_dur, "dur")

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
        if who and who["is_associate"]:
            news_n += len(ctx._day_changes(who))
            found = app.extensions["store"].unseen_leave_swap(who["id"])
            news_weeks = len(found["leave"]) + len(found["swaps"])
        else:
            news_weeks = 0
        return {"csrf_token": csrf_token, "copyright": COPYRIGHT, "user": g.get("user"), "news_n": news_n,
                "news_weeks": news_weeks, "zone_words": ctx._zone_words,
                "theme": theme if theme in THEMES else "", "back": back,
                "status_words": STATUS_WORDS, "label": label, "modes": MODES, "stages": stages, "in_flight": IN_FLIGHT,
                "when": _when, "run_options": run_options, "option_labels": OPTION_LABELS,
                "eta_text": eta_text, "duration": duration, "clock": _clock, "with_text": with_text,
                "group_changes": group_changes, "zones": ZONES, "home_zone": HOME, "channel_letters": channel_letters,
                "can": _can, "embed": request.endpoint == "day_page" and request.values.get("embed") == "1"}

    NAV_ACTIVE = {"home": "home", "overview_page": "overview", "day_page": "day", "week_page": "week",
                  "run_week": "week", "run_schedules": "schedules", "program": "analysis", "programs": "programs",
                  "exports_page": "exports", "incidents_page": "incidents", "shrinkage_page": "shrinkage", "team_page": "team", "admin_users": "people", "program_setup": "setup",
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
        day = ctx._date(request.args.get("date", ""))  # Overview and RTA keep the day being looked at
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
            app.extensions["changes"].expire_overdue(key, ctx._local_now(key))  # Phase AU
            found += app.extensions["changes"].count(key)
        return found

    ctx.__dict__.update({k: v for k, v in locals().items() if k in ['_access', '_can_see_run', '_left_menu', '_my_programs', '_paged', '_requests_waiting', '_unit_choices', '_unit_filter', '_visible', 'config']})
    from .routes import register_all  # here, not at the top: the routes import names from this module
    register_all(app, ctx)

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
