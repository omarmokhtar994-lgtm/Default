# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: exports."""
from __future__ import annotations

import io
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import abort, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from .. import shrink_view as _sv
from ..access import role
from ..analytics import team
from ..app import IN_FLIGHT, WORKBOOKS, clean_program
from ..attendance import hm
from ..auth import login_required
from ..clock import EGYPT
from ..coach import actual_shrinkage, corrected_tab
from ..day import MEASURES
from ..exports import EXPORT_SECONDS, KINDS as EXPORT_KINDS, MAX_DAYS as MAX_EXPORT_DAYS, _Days as ExportDays, build as build_export
from ..insights import ABSENT_CHOICES, ABSENT_VIEWS, absent_kinds, collect as collect_insights
from ..insights_page import LEVELS as INSIGHT_LEVELS, build as insights_view
from ..permissions import allowed
from ..runs import MODES
from ..shrink_page import build as shrink_page
from ..versions import DAYS
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the exports routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- exports (Phase O)
    def _export_args() -> Dict[str, Any]:
        today = A.datetime.now(EGYPT).date()
        start = ctx._date(request.args.get("from", "")) or today.replace(day=1)
        end = ctx._date(request.args.get("to", ""))
        pick = request.args.get("pick", "")
        kind, _, value = pick.partition(":")
        program = clean_program(value if kind == "key" else request.args.get("program", "")) or None
        if program is not None and not ctx._access().can_open(program):
            abort(403)
        wanted = request.args.get("user", type=int)
        if wanted is not None:  # Phase AT: filtering by a person is only for a person this user may see
            person = app.extensions["store"].get_user(wanted)
            if person is None or not ctx._access().sees(person):
                abort(403)
        if kind == "group":  # a whole program: all of its LOBs
            found = next((p for p in ctx._access().programs() if str(p["id"]) == value), None)
            if found is None:
                abort(403)
            program = sorted(found["units"])
        elif program is None and ctx._access().keys() is not None:
            program = sorted(ctx._access().keys())  # "all programs" means all of this person's programs
        if end is None:  # to the latest day anything was recorded for, when that is after today (owner, 2026-10-09:
            # changes made for a schedule that starts next week did not show in the default period)
            latest = ctx._date(app.extensions["store"].latest_record_date(program) or "")
            end = min(max(today, latest or today), start + timedelta(days=MAX_EXPORT_DAYS - 1))
        return {"start": start, "end": end, "program": program, "pick": pick,
                "user_id": request.args.get("user", type=int),
                "measure": ctx._measure_arg(request.args.get("measure", ""), program)}

    def _exports_page(error: str = "", status: int = 200):  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        a = _export_args()
        today = A.datetime.now(EGYPT).date()
        sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        presets = [("Today", today, today), ("This week", sunday, sunday + timedelta(days=6)),
                   ("Next week", sunday + timedelta(days=7), sunday + timedelta(days=13)),
                   ("This month", first, today), ("Last month", last_month_end.replace(day=1), last_month_end)]
        lo = A.datetime(a["start"].year, a["start"].month, a["start"].day, tzinfo=EGYPT).timestamp()
        hi = A.datetime(a["end"].year, a["end"].month, a["end"].day, tzinfo=EGYPT).timestamp() + 86400
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
                               programs=ctx._my_programs(ctx._days().programs()) if app.extensions.get("days") else [],
                               pick_tree=ctx._access().programs(), everything=ctx._access().everything(),
                               users=[u for u in store.list_users() if ctx._access().sees(u)],  # Phase AR: this program's people
                               measures=MEASURES, **a), status

    def _coach_args() -> Dict[str, Any]:
        days = ctx._days()
        programs = ctx._my_programs(days.programs())
        today = A.datetime.now(EGYPT).date()
        program = clean_program(request.args.get("program", "")) or (programs[0] if programs else "")
        start = ctx._date(request.args.get("from", "")) or today - timedelta(days=27)
        end = ctx._date(request.args.get("to", "")) or today
        if end < start or (end - start).days > 400:
            start, end = end - timedelta(days=27), end
        return {"program": program, "programs": programs, "start": start, "end": end}

    @app.route("/coach")
    @login_required
    def coach_page():  # type: ignore[no-untyped-def]
        a = _coach_args()
        found = actual_shrinkage(ctx._days(), a["program"], a["start"], a["end"]) if a["program"] else None
        return render_template("coach.html", found=found, days=DAYS, hm=hm, **a)

    @app.route("/coach/download")
    @login_required
    def coach_download():  # type: ignore[no-untyped-def]
        a = _coach_args()
        if not a["program"]:
            abort(404)
        found = actual_shrinkage(ctx._days(), a["program"], a["start"], a["end"])
        name = secure_filename(f"Shrinkage_{found['interval']}_Min_{a['program']}_{a['start']}_to_{a['end']}.xlsx")
        ctx._record("downloaded", program=a["program"], subject=name)
        return send_file(corrected_tab(found, a["program"]), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/exports")
    @login_required
    def exports_page():  # type: ignore[no-untyped-def]
        return _exports_page()

    SHRINK_SHOW, SHRINK_BY, SHRINK_STEPS, SHRINK_DAYS = _sv.SHOW, _sv.BY, _sv.STEPS, ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
    SHRINK_OUT, SHRINK_IN, SHRINK_LABEL, SHRINK_PRESETS = _sv.OUT_ITEMS, _sv.IN_ITEMS, _sv.LABEL, _sv.PRESETS
    shrink_ticks, shrink_mapping, shrink_intervals = _sv.ticks_from, _sv.mapping_of, _sv.collect_intervals
    HEAVY_WEEKS_DEFAULT, HEAVY_WEEKS_RECOMMENDED = 13, 6

    def _heavy_limit() -> Tuple[int, bool]:
        """Phase AV: (the most days of a period this person may ask of the Incidents, Shrinkage and Exports pages, whether
        they are exempt). Admins, supervisors and RTAs (who may change the day) have no limit but the 13 months kept;
        everyone else gets the weeks an admin set under LOBs and defaults."""
        user = g.user
        if user.get("is_admin") or user.get("is_supervisor") or allowed(app.extensions["store"], user, "rta_change"):
            return MAX_EXPORT_DAYS, True
        weeks = app.extensions["store"].get_app_setting("heavy_weeks", str(HEAVY_WEEKS_DEFAULT))
        return 7 * (int(weeks) if weeks.isdigit() and int(weeks) > 0 else HEAVY_WEEKS_DEFAULT), False

    def _too_long(start: date, end: date) -> str:
        limit, exempt = _heavy_limit()
        if exempt or (end - start).days + 1 <= limit:
            return ""
        return (f"Your account can look at up to {limit // 7} weeks at a time. Pick a shorter period, or ask an admin, "
                "a supervisor or the RTA for a longer look.")


    @app.route("/incidents")
    @login_required
    def incidents_page():  # type: ignore[no-untyped-def]
        """Phase AV: incidents, absenteeism and shrinkage per associate, LOB and program for any period."""
        a = _export_args()
        today = A.datetime.now(EGYPT).date()
        if not request.args.get("to"):
            a["end"] = min(a["end"], today) if a["start"] <= today else a["end"]
        error = ""
        limit, exempt = _heavy_limit()
        if (a["end"] - a["start"]).days + 1 > limit:
            a["start"] = a["end"] - timedelta(days=limit - 1)
            error = (f"Your account can look at up to {limit // 7} weeks at a time; showing the last {limit // 7} weeks of the period."
                     if not exempt else f"Records are kept 13 months; showing the last {limit} days of the period.")
        book = ctx._access().book
        keys = ([a["program"]] if isinstance(a["program"], str) else list(a["program"] or [])
                or [k for p in ctx._access().programs() for k in p["units"]])
        units = {}
        for k in keys:
            found = book.unit(k)
            if found and ctx._access().can_open(k):
                units[k] = (found["program"]["name"], (found["lob"] or {}).get("name") or found["program"]["name"])
        level = request.args.get("view", "")
        if level not in ("overview", "lobs", "associates"):
            level = "associates" if role(g.user) == "Team manager" else "overview"
        who = request.args.get("who", "")
        deadline = time.monotonic() + EXPORT_SECONDS
        wrapped = ExportDays(ctx._days(), deadline)

        def check() -> None:
            if time.monotonic() > deadline:
                raise ValueError("This took too long: pick a shorter period or one program.")
        try:
            facts = collect_insights(wrapped, app.extensions["store"], app.extensions.get("leave"), units,
                                     a["start"], a["end"], a["measure"], check)
        except ValueError as exc:
            facts, error = [], str(exc)
        counts = absent_kinds(request.args.getlist("abs"))
        before = []
        if facts and level == "overview" and not who:  # the same number of days just before, for "up or down on"
            length = (a["end"] - a["start"]).days + 1
            try:
                before = collect_insights(wrapped, app.extensions["store"], app.extensions.get("leave"), units,
                                          a["start"] - timedelta(days=length), a["start"] - timedelta(days=1),
                                          a["measure"], check)
            except ValueError:
                before = []
        sunday = _sv.week_begin(today, next(iter([(book.unit(k) or {}).get("program", {}).get("start_day", 0) or 0 for k in units]), 0))  # the program's week start
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        presets = [("This week", sunday, today), ("Last week", sunday - timedelta(days=7), sunday - timedelta(days=1)),
                   ("This month", first, today), ("Last month", last_month_end.replace(day=1), last_month_end),
                   ("Last 30 days", today - timedelta(days=29), today)]
        return render_template("insights.html", view=insights_view(facts, level, who, a["start"], a["end"], counts, before),
                               presets=presets, error=error, pick_tree=ctx._access().programs(),
                               everything=ctx._access().everything(), measures=MEASURES, level=level, who=who,
                               levels=INSIGHT_LEVELS, units=len(units), counts=counts, absent_choices=ABSENT_CHOICES,
                               absent_views=ABSENT_VIEWS, **a)

    @app.route("/shrinkage")
    @login_required
    def shrinkage_page():  # type: ignore[no-untyped-def]
        """Phase AV: shrinkage out of office, in office or both, day over day, week over week or per interval."""
        a = _export_args()
        today = A.datetime.now(EGYPT).date()
        if not request.args.get("to") and a["start"] <= today:
            a["end"] = min(a["end"], today)
        error = ""
        limit, exempt = _heavy_limit()
        if (a["end"] - a["start"]).days + 1 > limit:
            a["start"] = a["end"] - timedelta(days=limit - 1)
            error = (f"Your account can look at up to {limit // 7} weeks at a time; showing the last {limit // 7} weeks of the period."
                     if not exempt else f"Records are kept 13 months; showing the last {limit} days of the period.")
        book = ctx._access().book
        keys = ([a["program"]] if isinstance(a["program"], str) else list(a["program"] or [])
                or [k for p in ctx._access().programs() for k in p["units"]])
        units = {}
        for k in keys:
            found = book.unit(k)
            if found and ctx._access().can_open(k):
                units[k] = (found["program"]["name"], (found["lob"] or {}).get("name") or found["program"]["name"])
        show = request.args.get("show", "both")
        show = show if show in dict(SHRINK_SHOW) else "both"
        by = request.args.get("by", "day")
        by = by if by in dict(SHRINK_BY) else "day"
        step = request.args.get("step", 30, type=int)
        step = step if step in SHRINK_STEPS else 30
        first = request.args.get("first", 0, type=int) or 0
        last = request.args.get("last", 24, type=int) or 24
        first, last = (max(0, min(first, 23)) * 60, max(1, min(last, 24)) * 60)
        if last <= first:
            first, last = 0, 1440
        focus = request.args.get("focus", "inn")
        focus = focus if focus in ("inn", "out") else "inn"
        dows = {d for d in request.args.getlist("dow") if d in SHRINK_DAYS}
        first_unit = next(iter(units), "")
        kept = app.extensions["store"].get_shrinkage_map(first_unit) if first_unit else None
        out_ticks, in_ticks = shrink_ticks(kept, request.args.getlist("out"), request.args.getlist("inn"))
        deadline = time.monotonic() + EXPORT_SECONDS
        wrapped = ExportDays(ctx._days(), deadline)

        def check() -> None:
            if time.monotonic() > deadline:
                raise ValueError("This took too long: pick a shorter period or one program.")
        facts, per_day = [], {}
        try:
            facts = collect_insights(wrapped, app.extensions["store"], app.extensions.get("leave"), units, a["start"],
                                     a["end"], a["measure"], check, mapping_override=shrink_mapping(out_ticks, in_ticks))
            if dows:
                facts = [r for r in facts if SHRINK_DAYS[(date.fromisoformat(r["date"]).weekday() + 1) % 7] in dows]
            if by == "interval":
                per_day = shrink_intervals(wrapped, units, a["start"], a["end"], a["measure"], out_ticks, in_ticks, step, check)
                if dows:
                    per_day = {d: v for d, v in per_day.items()
                               if SHRINK_DAYS[(date.fromisoformat(d).weekday() + 1) % 7] in dows}
        except ValueError as exc:
            error = str(exc)
        sunday = _sv.week_begin(today, next(iter([(book.unit(k) or {}).get("program", {}).get("start_day", 0) or 0 for k in units]), 0))  # the program's week start
        first_of = today.replace(day=1)
        last_month_end = first_of - timedelta(days=1)
        presets = [("This week", sunday, today), ("Last week", sunday - timedelta(days=7), sunday - timedelta(days=1)),
                   ("This month", first_of, today), ("Last month", last_month_end.replace(day=1), last_month_end),
                   ("Last 30 days", today - timedelta(days=29), today)]
        start_days = {k: (book.unit(k) or {}).get("program", {}).get("start_day", 0) or 0 for k in units}
        week_days = sorted({start_days[k] for k in units})
        view = shrink_page(facts, per_day, show, by, out_ticks, in_ticks, step, first, last, focus, start_days,
                           week_days[0] if week_days else 0)
        return render_template("shrinkage.html", view=view, presets=presets, error=error, pick_tree=ctx._access().programs(),
                               everything=ctx._access().everything(), measures=MEASURES, units=len(units), show=show, by=by,
                               step=step, first_h=first // 60, last_h=last // 60, focus=focus, dows=dows,
                               out_ticks=out_ticks, in_ticks=in_ticks, show_choices=SHRINK_SHOW, by_choices=SHRINK_BY,
                               steps=SHRINK_STEPS, out_items=SHRINK_OUT, in_items=SHRINK_IN, item_label=SHRINK_LABEL,
                               presets_out=SHRINK_PRESETS, day_names=SHRINK_DAYS,
                               week_starts=[("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")[d] for d in week_days], **a)

    @app.route("/exports/download")
    @login_required
    def exports_download():  # type: ignore[no-untyped-def]
        a = _export_args()
        kinds = request.args.getlist("kind")
        fmt = request.args.get("format", "xlsx")
        try:
            too_long = _too_long(a["start"], a["end"])  # Phase AV: the weeks an admin allows this account
            if too_long:
                raise ValueError(too_long)
            data, name, mime = build_export(app.extensions["store"], ctx._days(), a["start"], a["end"], kinds, fmt,
                                            a["program"], a["user_id"], g.user["display_name"], a["measure"],
                                            deadline=time.monotonic() + EXPORT_SECONDS)
        except ValueError as exc:  # said on the page (in JSON when the page's script asked: Phase W)
            if request.headers.get("X-Requested-With") == "fetch":
                return jsonify(error=str(exc)), 400
            return _exports_page(str(exc), 400)
        ctx._record("exported", subject=name, program=a["program"] if isinstance(a["program"], str) else "",
                detail=f"{a['start']} to {a['end']}: {', '.join(k for k in EXPORT_KINDS if k in kinds)}")
        return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=name)

    @app.route("/team")
    @login_required
    def team_page():  # type: ignore[no-untyped-def]
        return render_template("team.html", people=team(ctx._all_runs()))

    @app.route("/workbooks/<name>")
    @login_required
    def workbook(name: str):  # type: ignore[no-untyped-def]
        """The clean input workbooks (tools/build_web_workbooks.py); nothing else."""
        if name not in WORKBOOKS:
            abort(404)
        return send_file(Path(A.__file__).with_name("workbooks") / name, as_attachment=True, download_name=name)

    @app.route("/runs/<run_id>/start", methods=["POST"])
    @login_required
    def run_start(run_id: str):  # type: ignore[no-untyped-def]
        """Start a run of this run's workbook (after a readiness check: the real run)."""
        run = ctx._run_or_404(run_id)
        mode = request.form.get("mode", "")
        if run["status"] in IN_FLIGHT or mode not in MODES:
            flash("Pick Quick, Deep or Overnight to start the run.")
            return redirect(url_for("run_detail", run_id=run_id))
        new_id = ctx._queue().start_from(run_id, g.user["id"], mode)
        if new_id is None:
            flash(f"The workbook of this check is no longer on the server (files are kept {ctx._queue().keep_days} days). "
                  "Upload it again.")
            return redirect(url_for("run_detail", run_id=run_id))
        ctx._record("run_started", app.extensions["store"].get_run(new_id), detail=f"{mode}, from the check {run_id}")
        return redirect(url_for("run_detail", run_id=new_id))

    ctx.HEAVY_WEEKS_DEFAULT = HEAVY_WEEKS_DEFAULT
    ctx.HEAVY_WEEKS_RECOMMENDED = HEAVY_WEEKS_RECOMMENDED
