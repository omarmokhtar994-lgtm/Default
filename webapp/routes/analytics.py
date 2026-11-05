# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: analytics."""
from __future__ import annotations

import copy
import io
import json
import re
import time
import zipfile
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import abort, flash, g, redirect, render_template, request, send_file, url_for
from openpyxl.utils.exceptions import InvalidFileException

from .. import needed
from ..analytics import program_weeks
from ..app import clean_program, kept_figures, start_date
from ..attendance import pick_version
from ..auth import login_required, manager_required
from ..channel_hours import combine, week_hours
from ..clock import EGYPT, HOME, ZONES, pick_zone, zone_label
from ..day import read_inputs
from ..merge import merge_intervals
from ..permissions import allowed
from ..program_page import build, overview, weeks_to_show
from ..programs import ProgramBook
from ..results import recolour
from ..run_admin import unit_keys
from ..runs import READY
from ..shrinkage import mapping_from_form
from ..versions import shift_span
from ..week import in_zone, view as week_view
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the analytics routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- analytics
    def _all_runs() -> list:
        """Every run this person may see (all of them for admins and people with every program)."""
        return ctx._visible(app.extensions["store"].list_runs(limit=100000))

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
            uploaded = [r for r in ctx._visible(app.extensions["store"].list_runs())
                        if r.get("program") == name and r["mode"] == READY and r["status"] == "DONE"]
            return render_template("program_empty.html", name=name, uploaded=uploaded)  # no engine week yet
        n = weeks_to_show(request.args.get("weeks", "12"))
        shown = history if n is None else history[-n:]
        groups = [{**p, "choices": [(k, t) for k, t in p["choices"] if k != name]}
                  for p in ctx._unit_choices(ProgramBook(app.extensions["store"]).tree())]
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
        run = ctx._run_or_404(run_id)
        side = "before" if request.args.get("side") == "before" else "after"
        return _week_page(run, side, run.get("program") or "", run.get("week_start") or "",
                          program_weeks(_all_runs(), app.extensions['store'].in_use_runs()))

    def _version_weeks(program: str) -> List[str]:
        """The weeks with a kept schedule for ``program`` (uploaded ones included), as the person may see."""
        return sorted({w for p, w in app.extensions["store"].schedule_weeks() if p == program}) \
            if program and ctx._access().can_open(program) else []

    def _week_choices(program: str, history: Dict[str, list]) -> Tuple[List[str], List[str]]:
        """The Week page's program and week lists: runs that count and kept schedules (Phase W)."""
        kept = {p for p, _ in app.extensions["store"].schedule_weeks()}
        programs = sorted(set(history) | {p for p in kept if ctx._access().can_open(p)}, key=str.lower)
        weeks = sorted({w["week"] for w in history.get(program, [])} | set(_version_weeks(program)), reverse=True)
        return programs, weeks

    def _week_target(program: str, week_start: str, run_id: Optional[str]) -> float:
        """The interval target that colours a week (Phase AH): the one set for the program and week, else the
        workbook's own, else 90%."""
        kept = app.extensions["store"].get_interval_target(program, week_start) if program and week_start else None
        if kept:
            return kept["target"] / 100
        default = app.extensions["store"].rta_default(program, "target") if program else None  # Phase AU
        if default:
            return int(default) / 100
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
        source = ctx._book().input_path(row["run_id"])
        return round(100 * read_inputs(source)["target"]) if source.is_file() else 90

    def _target_panel(program: str, week_start: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """The Week page's interval target (Phase W): the choice and each day's intervals at it, as the RTA counts."""
        kept = app.extensions["store"].get_interval_target(program, week_start)
        own = _own_target(row)
        default = app.extensions["store"].rta_default(program, "target")  # Phase AU: the program's default target
        base = int(default) if default else own
        days = []
        first = date.fromisoformat(week_start)
        for i in range(7):
            on = first + timedelta(days=i)
            try:
                page = ctx._days().page(program, on)
            except ValueError:  # the workbook is missing: said on the day page
                page = None
            days.append({"date": on, "label": f"{on:%a %d}", "t": page["target"] if page else None})
        return {"current": kept["target"] if kept else base, "own": own, "base": base, "from_program": bool(default),
                "kept": kept, "days": days, "choices": sorted({100, 95, 90, 85, 80, own, base}, reverse=True),
                "may_set": allowed(app.extensions["store"], g.user, "setup")}

    @app.route("/day/shrinkage", methods=["POST"])
    @manager_required
    def day_shrinkage_map():  # type: ignore[no-untyped-def]
        """Save what counts as shrinkage in and out of office for a program (Phase AF, E1; admins and supervisors)."""
        program = clean_program(request.form.get("program", ""))
        on = ctx._date(request.form.get("date", ""))
        if not program or on is None:
            abort(400)
        if not ctx._access().can_open(program):
            abort(403)
        app.extensions["store"].set_shrinkage_map(program, mapping_from_form(request.form), g.user["id"])
        ctx._record("shrinkage_mapped", program=program, subject=program, detail="Saved what counts as shrinkage.")
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
        if not ctx._access().can_open(program):
            abort(403)
        store = app.extensions["store"]
        row, _ = pick_version(store.list_schedules(program=program, week_start=week))
        if row is None:
            abort(404)
        try:
            target = int(request.form.get("target", ""))
        except ValueError:
            target = -1
        base = app.extensions["store"].rta_default(program, "target")
        if target not in {100, 95, 90, 85, 80, _own_target(row), int(base) if base else -1}:
            abort(400)
        store.set_interval_target(program, week, target, g.user["id"])
        ctx._record("interval_target_changed", program=program, week_start=week, subject=f"{target}%",
                detail=f"interval target for the week of {week}")
        flash(f"The interval target for the week of {date.fromisoformat(week):%a %d %b} is now {target}%: the RTA "
              "counts each day's intervals against it.")
        return redirect(url_for("week_page", program=program, week=week) + "#target", code=303)

    def _outlook(program: str, week_start: str) -> Optional[List[Dict[str, Any]]]:
        """The rest of the week on the Week page (Phase AF, F4); None for a week that is over."""
        today = A.datetime.now(EGYPT).date()
        first = date.fromisoformat(week_start)
        if first + timedelta(days=6) <= today:
            return None
        try:
            return ctx._days().outlook(program, first, today)
        except ValueError:  # a workbook that cannot be read: said on the day page
            return None

    def _hours_needed(program: str, week_start: str, basis: str, aim: str, show: str,
                      version_id: Optional[int] = None) -> Dict[str, Any]:
        """The Weeks page's Hours needed table (Phase AH): each day of the week from the DayBook (as recorded on the
        RTA, or as planned), and for today and the days to come what to do (days off to cancel, then overtime)."""
        days, rows = ctx._days(), []
        clock = A.datetime.now(EGYPT)
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
        if not ctx._access().can_open(program):
            abort(403)
        basis, aim, show = _needed_choices()
        found = _hours_needed(program, week, basis, aim, show, _week_version(program, week))
        table = found["table"]
        reach = "100%" if aim == "full" else f"the target ({round(100 * table['target'])}%) with 10 minutes over it"
        title = (f"{ctx._unit_filter(program)}, week of {date.fromisoformat(week):%a %d %b %Y}. "
                 f"{'As recorded on the RTA' if basis == 'recorded' else 'As planned'}. Hours needed to reach {reach}.")
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{program}_{week}_hours_needed").strip("_") + ".xlsx"
        return send_file(io.BytesIO(needed.workbook(table, title)), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def _recorded_week(program: str, week_start: str) -> Optional[Dict[str, Any]]:
        """The week as the RTA records it, for the Schedules page (Phase AH): intervals at the target, tight ones."""
        days, found = ctx._days(), {"now": 0, "intervals": 0, "tight": 0, "target": None}
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
        days, views = ctx._days(), []
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
        units = sorted(u for u in found["program"]["units"] if ctx._access().can_open(u))
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
        info = {"name": _merged_name(program, units), "units": units, "all": len(units) == len(_merge_units(program)),
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
        listed = ctx._book().week_list(row["program"], row["week_start"])  # Phase AA: switch between the week's schedules
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
                               may_set_in_use=ctx._may_set_in_use(row), target_panel=target, elsewhere=elsewhere,
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
        merge = ctx._merge_choice(program) if program and ctx._access().can_open(program) else None
        ctx._merge_pick_for(program, units, merge)
        if merge:
            found = _merged_week(program, merge, week, side)
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
                                  f"{A.datetime.fromtimestamp(marks[-1]['at'], EGYPT):%a %d %b}")
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

    ctx._all_runs = _all_runs
    ctx._channel_hours_for = _channel_hours_for
    ctx._channel_hours_week = _channel_hours_week
    ctx._lob_names = _lob_names
    ctx._merge_units = _merge_units
    ctx._merged_name = _merged_name
    ctx._outlook = _outlook
    ctx._recorded_week = _recorded_week
    ctx._version_week = _version_week
    ctx._walled = _walled
    ctx._week_target = _week_target
