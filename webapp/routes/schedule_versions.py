# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: schedule versions."""
from __future__ import annotations

import zipfile
from datetime import date, timedelta
from typing import Any, Dict

from flask import abort, g, render_template, request, url_for
from openpyxl.utils.exceptions import InvalidFileException

from ..app import start_date
from ..auth import login_required
from ..channel_hours import combine
from ..clock import EGYPT, HOME, ZONES, pick_zone
from ..day import read_inputs
from ..runs import ACTIVE
from ..schedules import ScheduleBook
from ..versions import DAYS
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the schedule versions routes to ``app``; ``ctx`` holds the helpers the areas share."""
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
        if not ctx._can_see_run(run):
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
        run = ctx._run_or_404(run_id)
        book, queue = _book(), ctx._queue()
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
        g.zone = request.args["tz"] if request.args.get("tz") in dict(ZONES) else (ctx._pc_zone() or own)  # Phase AY: the computer's zone, else the schedule's own
        first = date.fromisoformat(run["week_start"]) if start_date(run.get("week_start") or "") else A.datetime.now(EGYPT).date()
        moved = own != g.zone
        together = None  # Phase AP: every LOB of the program as one, when it has two or more
        units = ctx._merge_units(run["program"]) if run.get("program") and start_date(run.get("week_start") or "") else []
        if len(units) > 1:
            weeks_of = [w for w in (ctx._channel_hours_week(u, run["week_start"]) for u in units) if w]
            together = {"name": ctx._merged_name(run["program"], units), "of": len(units),
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
                               days=DAYS, channel_lines=None if input_problem else ctx._channel_lines(run_id),
                               chhours=ctx._channel_hours_week(run["program"], run["week_start"])
                               if current and run.get("program") and start_date(run.get("week_start") or "") else None,
                               channel_added=added, step=step, input_problem=input_problem,
                               week_list=week_list if len(week_list) > 1 else [],
                               may_use={e["shown"]["id"] for e in week_list if _may_set_in_use(e["shown"])},
                               may_delete=_may_delete(run), running=run["status"] in ACTIVE + ("QUEUED",),
                               recorded=ctx._recorded_week(run["program"], run["week_start"])
                               if current and current["in_use"] and run.get("program") and start_date(
                                   run.get("week_start") or "") else None)

    ctx._book = _book
    ctx._may_delete = _may_delete
    ctx._may_set_in_use = _may_set_in_use
    ctx._version_or_404 = _version_or_404
