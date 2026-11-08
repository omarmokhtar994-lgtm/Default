# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: volumes (Phase BI; owner, 2026-11-03): actual volumes in, the forecast of a week from a typed total, the people needed with Erlang,
and how the week went. Pages: Actuals, Forecast and needs, How we did, Settings (``/volumes?tab=``). Every grid is laid out like the input sheet
(intervals down, Sun to Sat across) with a button that copies it for Excel."""
from __future__ import annotations

import calendar
import io
import re
import secrets
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import abort, flash, g, redirect, render_template, request, send_file, session, url_for
from openpyxl import Workbook
from openpyxl.styles import Font

from .. import charts
from ..app import clean_program
from ..auth import login_required
from ..programs import ProgramBook
from ..shrink_view import week_begin
from .. import drivers as drivers_mod
from .. import open_hours as open_hours_mod, sites as sites_mod
from ..volumes import DEFAULTS, LABELS, LAST_WEEK, VolumeBook, _today
from ..excel_agents import lambda_definitions
from ..volumes_zone import ZONES
from ..volumes_draft import draft_workbook, is_draft, parse_draft
from ..volumes_formulas import formulas_workbook
from ..volumes_io import CHANNELS, DAY_NAMES, FIRST_DAY, ParsedVolumes, parse_grid, parse_long, parse_pasted, read_table

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TABS = (("actuals", "Actuals"), ("forecast", "Forecast and needs"), ("outlook", "Months ahead"), ("how", "How we did"), ("settings", "Settings"))
HELD_MINUTES = 20
BASIS_WORDS = {"learned": "learned from the history", "unseen": "no seasonal pattern yet", "typed": "your typed index", "trend": "trend only"}
MAX_PASTE = 400_000


def register(app, ctx) -> None:
    """Add the volumes routes to ``app``; ``ctx`` holds the helpers the areas share."""

    def _book() -> VolumeBook:
        return app.extensions["volumes"]

    def _held() -> Dict[str, Dict[str, Any]]:
        """Checked tables waiting for their owner to press Save, in memory only (a restart drops them)."""
        held = app.extensions.setdefault("volumes_held", {})
        now = time.time()
        for token in [k for k, v in held.items() if v["expires"] < now]:
            held.pop(token, None)
        return held

    def _unit(required: bool = True) -> str:
        """The program (and LOB) key from the request, checked against what this person may open."""
        access = ctx._access()
        key = clean_program(request.values.get("program", ""))
        if key:
            if not access.can_open(key) or not access.book.unit(key):
                abort(403 if not access.can_open(key) else 404)
            return key
        key = session.get("unit", "")
        if key and access.can_open(key) and access.book.unit(key):
            return key
        units = [k for p in access.programs() for k in p["units"]]
        if not units and required:
            abort(404)
        return units[0] if units else ""

    def _start_day(key: str) -> int:
        found = ProgramBook(app.extensions["store"]).unit(key)
        return int((found or {}).get("program", {}).get("start_day") or 0)

    def _channel(value: str) -> str:
        return value if value in CHANNELS else "Phone"

    def _date(text: str) -> Optional[date]:
        """A date typed or sent, or None when it is not one or lies outside 2015 to 2100 (so calendar arithmetic on it cannot run off Python's dates)."""
        try:
            found = date.fromisoformat((text or "").strip())
        except ValueError:
            return None
        return found if FIRST_DAY <= found < LAST_WEEK else None

    def _week(key: str, text: str, default: date) -> date:
        return week_begin(_date(text) or default, _start_day(key))

    def _bad_week() -> bool:
        """Whether a form named a week that is not a date between 2015 and 2100. Pages fall back to the default week; anything that writes refuses instead."""
        raw = request.form.get("week", "").strip()
        return bool(raw) and _date(raw) is None

    def _week_choices(key: str, centre: date, back: int, ahead: int) -> List[Dict[str, str]]:
        first = week_begin(centre, _start_day(key))
        out = []
        for k in range(-back, ahead + 1):
            d = first + timedelta(weeks=k)
            out.append({"iso": d.isoformat(), "text": f"{d:%a %d %b %Y} to {d + timedelta(days=6):%a %d %b}"})
        return out

    def _typed_days() -> Dict[int, str]:
        return {d: request.values.get(f"d{d}", "").strip() for d in range(7) if request.values.get(f"d{d}", "").strip()}

    def _hist_weeks() -> Optional[str]:
        """The weeks of history the person asked for on this request, as typed (None: the channel's setting)."""
        return request.values.get("hist_weeks", "").strip() or None

    def _skips() -> Optional[List[str]]:
        """The weeks the person left out on this request, or None when the form was not sent (then the stored ones apply)."""
        return request.values.getlist("skip")[:80] if "skip_sent" in request.values else None

    def _show_zone(vb: VolumeBook, key: str) -> str:
        """The zone the person asked to see times in; the program's own when none, or one that is not in the list."""
        asked = request.values.get("show_tz", "")
        return asked if asked in dict(ZONES) else vb.zone(key)

    def _base() -> str:
        return "last_year" if request.values.get("base") == "last_year" else "history"

    def _carry() -> Dict[str, Any]:
        """What a page asks for, kept when a form on it sends the person back to it."""
        out: Dict[str, Any] = {k: request.form[k] for k in ("total", "hist_weeks", "base", "day", "show_tz", "site") if request.form.get(k)}
        if "skip_sent" in request.form:
            out["skip_sent"] = "1"
            out["skip"] = request.form.getlist("skip")[:80]
        return out

    def _plan(vb: VolumeBook, key: str, channel: str, week: date, **more: Any) -> Dict[str, Any]:
        """A forecast as the page asked for it; a bad request is a 400 in words, never a crash."""
        try:
            return vb.forecast(key, channel, week, weeks=_hist_weeks(), skip_weeks=_skips(), base=_base(), **more)
        except ValueError as exc:
            abort(400, description=str(exc))

    def _week_rows(f: Dict[str, Any]) -> List[Dict[str, Any]]:
        """The weeks behind a forecast, newest first: used with their totals, or left out with the reason."""
        totals = dict((f.get("suggestion") or {}).get("weeks", []))
        rows = [{"iso": d, "used": True, "total": totals.get(d), "reason": "", "can_leave": True} for d in (f.get("weeks") or {}).get("used", [])]
        rows += [{"iso": d, "used": False, "total": None, "reason": why, "can_leave": why == "left out by you"}
                 for d, why in (f.get("weeks") or {}).get("skipped", [])]
        return sorted(rows, key=lambda r: r["iso"], reverse=True)

    # ------------------------------------------------------------------ the page
    def _chart_day(f: Dict[str, Any], d: int):
        labels = [f"{i * f['step'] // 60:02d}:{i * f['step'] % 60:02d}" for i in range(len(f["calls"][d]))]
        open_ = [i for i, v in enumerate(f["calls"][d]) if v or (f["needs"] and f["needs"][d][i])]
        lo, hi = (min(open_), max(open_) + 1) if open_ else (0, len(labels))
        calls = charts.lines(labels[lo:hi], [("Forecast contacts", charts.BLUE, f["calls"][d][lo:hi])],
                             y_max=max(f["calls"][d][lo:hi] + [1]) * 1.2, unit="", label=f"Forecast contacts, {DAY_NAMES[d]}")
        people = ""
        if f["needs"]:
            people = charts.lines(labels[lo:hi], [("Needed on the floor", charts.ORANGE, f["needs"][d][lo:hi])],
                                  y_max=max(f["needs"][d][lo:hi] + [1]) * 1.2, unit="", label=f"People needed on the floor, {DAY_NAMES[d]}")
        return calls, people

    def _how_charts(r: Dict[str, Any], d: int):
        step = r["step"]
        labels = [f"{i * step // 60:02d}:{i * step % 60:02d}" for i in range(len(r["actual"][d]))]
        series_calls = [("Offered", charts.ORANGE, r["actual"][d])]
        if r["forecast"]:
            series_calls.insert(0, ("Forecast", charts.BLUE, r["forecast"][d]))
        busy = [i for i, v in enumerate(r["actual"][d]) if v] or [0]
        lo, hi = min(busy), max(busy) + 1
        top = max([v for _, _, vals in series_calls for v in vals[lo:hi]] + [1]) * 1.2
        calls = charts.lines(labels[lo:hi], [(n, c, v[lo:hi]) for n, c, v in series_calls], y_max=top, unit="",
                             label=f"Contacts, forecast and offered, {DAY_NAMES[d]}")
        people, sl = "", ""
        s = r["staffing"]
        if s and s["required"] is not None:
            lines = [("Needed in the system", charts.BLUE, s["required"]), ("On shift", charts.YELLOW, s["planned"]),
                     ("On the floor", charts.ORANGE, s["floor"])]
            if s["at_actual"]:
                lines.insert(1, ("Needed at actual calls", charts.AQUA, s["at_actual"]))
            top = max([v for _, _, vals in lines for v in vals[lo:hi] if v is not None] + [1]) * 1.2
            people = charts.lines(labels[lo:hi], [(n, c, v[lo:hi]) for n, c, v in lines], y_max=top, unit="",
                                  label=f"People needed, on shift and on the floor, {DAY_NAMES[d]}")
            if s["modelled_sl"]:
                target = r["settings"]["sl_target"]
                sl = charts.lines(labels[lo:hi], [("Service level the staffing gave (modelled)", charts.AQUA, s["modelled_sl"][lo:hi]),
                                                  (f"Target {target}%", charts.BLUE, [target] * (hi - lo))],
                                  y_max=100, unit="%", label=f"Modelled service level, {DAY_NAMES[d]}")
        return calls, people, sl

    def _drivers_view(vb: VolumeBook, key: str, week: date) -> Dict[str, Any]:
        """The events, AI periods, growth and last-year figures for the page; rows that touch this week come first in the person's eye."""
        try:
            doc = vb.drivers(key)
        except ValueError:
            return {"events": [], "ai": [], "growth": {"yoy": {}, "method": "measured"}, "last_year": {}, "skip_weeks": [], "damaged": True}
        end = week + timedelta(days=6)
        for e in doc["events"]:
            last = date.fromisoformat(e["end"]) + timedelta(days=e["after_days"])
            e["this_week"] = date.fromisoformat(e["start"]) <= end and week <= last
        for r in doc["ai"]:
            r["this_week"] = date.fromisoformat(r["start"]) <= end and week <= date.fromisoformat(r["end"])
        doc["damaged"] = False
        return doc

    def _clock(minutes: int) -> str:
        return "24:00" if minutes == 1440 else f"{(minutes % 1440) // 60:02d}:{minutes % 60:02d}"

    def _hours_view(hours: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Each channel's hours as the Settings form shows them: a row per weekday with the opening and closing time as typed."""
        out: Dict[str, Dict[str, Any]] = {}
        for ch, h in hours.items():
            rows = []
            for d in range(7):
                window = h["days"].get(str(d), "unset")
                rows.append({"i": d, "name": DAY_NAMES[d], "closed": window is None,
                             "from": _clock(window[0]) if isinstance(window, list) else "", "to": _clock(window[1]) if isinstance(window, list) else ""})
            out[ch] = {"min_cover": h["min_cover"], "rows": rows}
        return out

    def _site_gaps(doc: Dict[str, Any]) -> List[str]:
        """Where the time no rule covers goes, in words, one line per channel and run of weekdays that share the same gaps."""
        lines: List[str] = []
        first = doc["sites"][0]["name"] if doc["sites"] else ""
        for ch in CHANNELS:
            by_day = sites_mod.gaps(doc, ch)
            groups: Dict[Tuple[Tuple[int, int], ...], List[int]] = {}
            for d, runs in by_day.items():
                groups.setdefault(tuple(runs), []).append(d)
            for runs, days in groups.items():
                times = ", ".join(f"{_clock(a)} to {_clock(b)}" for a, b in runs)
                lines.append(f"{ch}, {', '.join(DAY_NAMES[d] for d in sorted(days))}: {times} has no rule, so it goes to {first}.")
        return lines

    def _render(tab: str, **extra: Any):
        vb, key = _book(), _unit()
        store = app.extensions["store"]
        channel = _channel(request.values.get("channel", ""))
        today = _today()
        coverage = {ch: vb.coverage(key, ch) for ch in CHANNELS}
        if tab not in dict(TABS):
            tab = "forecast" if coverage[channel]["days"] else "actuals"
        step = vb.step(key)
        ctxt: Dict[str, Any] = {"tab": tab, "tabs": TABS, "key": key, "label": ProgramBook(store).label(key), "channel": channel,
                                "channels": CHANNELS, "coverage": coverage, "step": step, "erlang": vb.uses_erlang(key),
                                "measure": vb.measure_of(key), "day_names": DAY_NAMES, "today": today.isoformat(), "grid_error": "", "draft": {}, "kinds": drivers_mod.KINDS, "lambda_text": lambda_definitions(), "zones": ZONES,
                                "zone": vb.zone(key), "zone_name": dict(ZONES)[vb.zone(key)].split(" (")[0], "clock": _clock, **extra}
        if tab == "actuals":
            ctxt["weeks"] = _week_choices(key, today - timedelta(weeks=1), 10, 1)
        elif tab == "forecast":
            week = _week(key, request.values.get("week", ""), today + timedelta(weeks=1))
            typed_total = request.values.get("total", "").strip()
            typed_days = _typed_days()
            hist, skips, base = _hist_weeks(), _skips(), _base()
            error = ""
            try:
                f = vb.forecast(key, channel, week, total=typed_total or None, day_totals=typed_days, weeks=hist, skip_weeks=skips, base=base)
            except ValueError as exc:
                error, f = str(exc), vb.forecast(key, channel, week)
            if f["error"]:
                error = error or f["error"]
            site_names = [x["name"] for x in vb.sites(key)["sites"]]
            site = request.values.get("site", "") if request.values.get("site", "") in site_names else ""
            whole_total = f.get("total")                                # the number typed is the whole program's, whichever site is shown
            f = vb.for_site(key, f, site or None)
            show_zone = _show_zone(vb, key)
            f = vb.view_in(key, f, week, show_zone)                    # the grids read in the zone asked for (the program's own unless the person picked another)
            day = DAY_NAMES.index(request.values.get("day", "Mon")) if request.values.get("day", "Mon") in DAY_NAMES else 1
            ctxt.update(week=week, week_end=week + timedelta(days=6), weeks=_week_choices(key, today + timedelta(weeks=1), 2, 6), f=f, error=error, day=day,
                        total_text=typed_total or (f"{whole_total:,}" if whole_total is not None else ""), site=site, site_names=site_names, typed_days=typed_days,
                        calls_grid=vb.grid(f["calls"], step) if f["calls"] else None,
                        needs_grid=vb.grid(f["needs"], step) if f.get("needs") else None,
                        saved=store.volume_forecast(key, channel, week.isoformat()), show_zone=show_zone, show_name=dict(ZONES)[show_zone].split(" (")[0], hist_weeks=hist if hist is not None else (f.get("weeks") or {}).get("wanted") or
                        vb.settings(key)[channel]["forecast_weeks"], base=base, skip=f.get("skip_weeks", []), week_rows=_week_rows(f), drivers=_drivers_view(vb, key, week))
            if f["calls"]:
                ctxt["chart_calls"], ctxt["chart_people"] = _chart_day(f, day)
                busiest = max(((i, d) for d in range(7) for i in range(len(f["calls"][d]))), key=lambda t: f["calls"][t[1]][t[0]])
                ctxt["busiest"] = (DAY_NAMES[busiest[1]], busiest[0] * step, f["calls"][busiest[1]][busiest[0]])
                if f.get("needs"):
                    ctxt["peak_needed"] = max(max(row) for row in f["needs"])
                    ctxt["hours_needed"] = round(sum(sum(row) for row in f["needs"]) * step / 60, 1)
        elif tab == "how":
            week = _week(key, request.values.get("week", ""), today - timedelta(weeks=1))
            on = _date(request.values.get("on", ""))
            r0 = vb.report(key, channel, week)
            if on is None or not week <= on <= week + timedelta(days=6):
                idx = next((i for i, d in enumerate(r0["actual"]) if sum(d)), 0)
                on = date.fromisoformat(r0["dates"][idx])
            r = vb.report(key, channel, week, on=on)
            day = r["dates"].index(on.isoformat()) if on.isoformat() in r["dates"] else 0
            ctxt.update(week=week, weeks=_week_choices(key, today - timedelta(weeks=1), 11, 0), r=r, on=on, day=day,
                        actual_grid=vb.grid(r["actual"], step), otf_grid=vb.grid(r["otf"], step) if r["otf"] else None,
                        forecast_grid=vb.grid(r["forecast"], step) if r["forecast"] else None)
            ctxt["band_grid"] = r["band"]
            if sum(r["actual"][day]):
                ctxt["chart_calls"], ctxt["chart_people"], ctxt["chart_sl"] = _how_charts(r, day)
            if len(r["trend"]) >= 1:
                ctxt["chart_otf"] = charts.columns([w["week"][5:] for w in r["trend"]], [round(w["otf"], 1) if w["otf"] is not None else None
                                                                                     for w in r["trend"]], unit="%",
                                                   label="Offered over forecast by week", y_max=max(120, max(w["otf"] or 0 for w in r["trend"]) * 1.1))
        elif tab == "outlook":
            names = [x["name"] for x in vb.sites(key)["sites"]]
            site = request.values.get("site", "") if request.values.get("site", "") in names else ""
            level = request.values.get("level", "year") if request.values.get("level", "year") in ("year", "week", "day") else "year"
            months_text = request.values.get("months", "6").strip() or "6"
            outlook, o_error = None, ""
            try:
                outlook = vb.outlook(key, channel, months=months_text, site=site or None)
            except ValueError as exc:
                o_error = str(exc)
            picked = None
            if outlook:
                want = request.values.get("owk", "")
                picked = next((w for w in outlook["weeks"] if w["week"] == want), outlook["weeks"][0] if outlook["weeks"] else None)
            ctxt.update(o=outlook, o_error=o_error, level=level, months_text=months_text, site=site, site_names=names, owk=picked,
                        index=vb.outlook_index(key, channel), basis_words=BASIS_WORDS, month_names=[calendar.month_name[m] for m in range(1, 13)])
        elif tab == "settings":
            ctxt.update(settings=vb.settings(key), labels=LABELS, defaults=DEFAULTS, hours_view=_hours_view(vb.open_hours(key)), sites_doc=vb.sites(key), site_gaps=_site_gaps(vb.sites(key)))
        return render_template("volumes.html", **ctxt)

    @app.route("/volumes")
    @login_required
    def volumes_page():  # type: ignore[no-untyped-def]
        return _render(request.args.get("tab", ""))

    # ------------------------------------------------------------------ the forecast: work it out or save it
    @app.route("/volumes/forecast", methods=["POST"])
    @login_required
    def volumes_forecast():  # type: ignore[no-untyped-def]
        vb, key = _book(), _unit()
        channel = _channel(request.form.get("channel", ""))
        if _bad_week():
            flash("That week is not a date between 2015 and 2100. Pick a week from the list.")
            return _render("forecast")
        week = _week(key, request.form.get("week", ""), _today() + timedelta(weeks=1))
        action = request.form.get("action", "preview")
        if action == "save":
            try:
                vb.save_forecast(key, channel, week, request.form.get("total", ""), _typed_days(), g.user["id"], weeks=_hist_weeks(), skip_weeks=_skips())
            except ValueError as exc:
                flash(str(exc))
                return _render("forecast")
            ctx._record("volumes_forecast_saved", program=key, week_start=week.isoformat(), subject=channel,
                        detail=f"{request.form.get('total', '').strip()} contacts")
            flash(f"Saved the {channel} forecast for the week of {week:%a %d %b}.")
            return redirect(url_for("volumes_page", tab="forecast", program=key, channel=channel, week=week.isoformat()), code=303)
        if action == "remember_weeks":
            try:
                vb.set_skip_weeks(key, _skips() or [], g.user["id"])
            except ValueError as exc:
                flash(str(exc))
                return _render("forecast")
            ctx._record("volumes_drivers_saved", program=key, week_start=week.isoformat(), subject="Weeks left out", detail=f"{len(_skips() or [])} weeks")
            flash("Remembered the weeks you left out. They stay out of every forecast until you change them.")
            return redirect(url_for("volumes_page", tab="forecast", program=key, channel=channel, week=week.isoformat(), **_carry()), code=303)
        if action == "remove":
            vb.store.delete_volume_forecast(key, channel, week.isoformat())
            ctx._record("volumes_forecast_saved", program=key, week_start=week.isoformat(), subject=channel, detail="removed")
            flash("Removed that forecast.")
            return redirect(url_for("volumes_page", tab="forecast", program=key, channel=channel, week=week.isoformat()), code=303)
        return _render("forecast")

    # ------------------------------------------------------------------ what else is known about the week
    @app.route("/volumes/drivers", methods=["POST"])
    @login_required
    def volumes_drivers():  # type: ignore[no-untyped-def]
        """Events and promotions, AI periods, year-over-year growth, last year's totals: each one checked whole, and refused in words with nothing kept."""
        vb, key = _book(), _unit()
        channel = _channel(request.form.get("channel", ""))
        if _bad_week():
            flash("That week is not a date between 2015 and 2100. Pick a week from the list.")
            return _render("forecast")
        week = _week(key, request.form.get("week", ""), _today() + timedelta(weeks=1))
        action = request.form.get("action", "")
        form = request.form
        uid = g.user["id"]
        try:
            if action == "add_event":
                row = {"kind": form.get("kind", ""), "name": form.get("name", ""), "channels": form.getlist("channels"), "start": form.get("start", ""),
                       "end": form.get("end", ""), "change": form.get("change", ""), "after_days": form.get("after_days", ""),
                       "after_change": form.get("after_change", ""), "hours": form.get("hours", ""), "open_from": form.get("open_from", ""),
                       "open_to": form.get("open_to", "")}
                vb.add_driver(key, "events", row, uid)
                said = f"Added the {row['kind'].lower()} {' '.join(row['name'].split())[:60]}."
            elif action == "add_ai":
                row = {"channel": form.get("ai_channel", ""), "start": form.get("start", ""), "end": form.get("end", ""), "change": form.get("change", ""),
                       "move_to": form.get("move_to", ""), "move_share": form.get("move_share", "")}
                vb.add_driver(key, "ai", row, uid)
                said = f"Added the AI period for {row['channel']}."
            elif action == "remove":
                which = form.get("list", "")
                if which not in ("events", "ai"):
                    raise ValueError("Events and AI periods are the two lists.")
                gone = next((r for r in vb.drivers(key)[which] if r["id"] == form.get("id", "")), None)
                vb.remove_driver(key, which, form.get("id", ""), uid)
                said = (f"Removed {gone['name']}." if which == "events" else f"Removed the {gone['channel']} AI period from {gone['start']}.") if gone else "That one was already removed."
            elif action == "growth":
                vb.set_growth(key, {ch: form.get(f"yoy.{ch}", "") for ch in CHANNELS}, form.get("method", "measured"), uid)
                said = "Saved the year-over-year rates."
            elif action == "last_year":
                vb.set_last_year(key, week, {ch: form.get(f"ly.{ch}", "") for ch in CHANNELS}, uid)
                said = "Saved last year's totals."
            else:
                raise ValueError("Choose what to change.")
        except ValueError as exc:
            flash(str(exc))
            return _render("forecast", draft=form)
        ctx._record("volumes_drivers_saved", program=key, week_start=week.isoformat(), subject=action.replace("_", " "), detail=said)
        flash(said)
        return redirect(url_for("volumes_page", tab="forecast", program=key, channel=channel, week=week.isoformat(), **_carry()), code=303)

    # ------------------------------------------------------------------ actuals: check, then save
    @app.route("/volumes/actuals/check", methods=["POST"])
    @login_required
    def volumes_actuals_check():  # type: ignore[no-untyped-def]
        vb, key = _book(), _unit()
        channel = _channel(request.form.get("channel", ""))
        today = _today()
        step = vb.step(key)
        result: Dict[str, Any] = {"problems": [], "summary": None, "token": "", "mode": "", "notes": []}
        try:
            upload = request.files.get("file")
            pasted = request.form.get("paste", "")
            if len(pasted) > MAX_PASTE:
                raise ValueError("That is too much to paste: upload it as a file.")
            data = upload.read() if upload is not None and upload.filename else b""
            if data and is_draft(data, upload.filename):
                parsed = parse_draft(data, upload.filename, step, today)
                result["mode"] = "the draft workbook"
            else:
                if upload is not None and upload.filename:
                    table = read_table(data, upload.filename)
                elif pasted.strip():
                    table = parse_pasted(pasted)
                else:
                    raise ValueError("Upload a file or paste the table.")
                aht_text = request.form.get("aht_paste", "")
                grid = any(str(row[0]).strip().lower() == "interval" and any(str(c).strip().title()[:3] in DAY_NAMES for c in row[1:])
                           for row in table[:30] if row)
                if grid:
                    if _bad_week():
                        raise ValueError("The week is not a date between 2015 and 2100. Pick a week from the list.")
                    week = _week(key, request.form.get("week", ""), today - timedelta(weeks=1))
                    parsed = parse_grid(table, week, channel, parse_pasted(aht_text) if aht_text.strip() else None, step, today)
                    result["mode"] = f"the input sheet's layout for the week of {week:%a %d %b %Y}, {channel}"
                else:
                    parsed = parse_long(table, channel, step, today)
                    result["mode"] = "one row per date and interval"
            source = request.form.get("source_tz", "").strip() or vb.zone(key)
            if source not in dict(ZONES):
                raise ValueError("The time zone the file is in is one of the zones in the list.")
            cells = source != vb.zone(key)                             # rows moved from another zone replace only their own intervals
            parsed = vb.convert_actuals(key, parsed, source)
            result.update(problems=parsed.problems, summary=parsed.summary, notes=parsed.notes, cells=cells)
            if not parsed.problems:
                token = secrets.token_urlsafe(16)
                _held()[token] = {"user": g.user["id"], "key": key, "rows": parsed.rows, "cells": cells, "expires": time.time() + 60 * HELD_MINUTES}
                result["token"] = token
                existing = {ch: set(vb.store.volume_days(key, ch)) for ch in parsed.rows}
                result["replaces"] = {ch: sum(1 for d in {r[0] for r in rows} if d in existing[ch]) for ch, rows in parsed.rows.items()}
        except ValueError as exc:
            result["problems"] = [str(exc)]
        return _render("actuals", check=result)

    @app.route("/volumes/actuals/save", methods=["POST"])
    @login_required
    def volumes_actuals_save():  # type: ignore[no-untyped-def]
        vb, key = _book(), _unit()
        token = request.form.get("token", "")
        held = _held().get(token)
        if held is None or held["user"] != g.user["id"] or held["key"] != key:  # someone else's check is left as it was
            flash("That check has expired. Upload or paste the table again.")
            return redirect(url_for("volumes_page", tab="actuals", program=key), code=303)
        _held().pop(token, None)
        cells = bool(held.get("cells"))
        done = vb.save_actuals(key, ParsedVolumes(rows=held["rows"]), g.user["id"], cells=cells)
        verb = "updating" if cells else "replacing"
        said = "; ".join(f"{ch}: {n['rows']:,} rows over {n['days']} day{'s' if n['days'] != 1 else ''}"
                         f"{', ' + verb + ' ' + str(n['replaced_days']) if n['replaced_days'] else ''}" for ch, n in done.items())
        ctx._record("volumes_uploaded", program=key, subject=", ".join(done), detail=said)
        flash("Saved. " + said + ".")
        return redirect(url_for("volumes_page", tab="actuals", program=key, channel=next(iter(done), "Phone")), code=303)

    @app.route("/volumes/actuals/delete", methods=["POST"])
    @login_required
    def volumes_actuals_delete():  # type: ignore[no-untyped-def]
        vb, key = _book(), _unit()
        channel = _channel(request.form.get("channel", ""))
        first, last = _date(request.form.get("first", "")), _date(request.form.get("last", ""))
        if request.form.get("confirm") != "1" or not first or not last or first > last:
            flash("Pick the first and last day and tick the box to confirm.")
        else:
            n = vb.store.delete_volume_days(key, channel, first.isoformat(), last.isoformat())
            ctx._record("volumes_deleted", program=key, subject=channel, detail=f"{first.isoformat()} to {last.isoformat()}: {n} rows")
            flash(f"Deleted {n:,} {channel} rows from {first:%d %b %Y} to {last:%d %b %Y}.")
        return redirect(url_for("volumes_page", tab="actuals", program=key, channel=channel), code=303)

    # ------------------------------------------------------------------ settings
    @app.route("/volumes/settings", methods=["POST"])
    @login_required
    def volumes_settings():  # type: ignore[no-untyped-def]
        vb, key = _book(), _unit()
        data = {ch: {name: request.form.get(f"{ch}.{name}", "") for name in DEFAULTS[ch] if f"{ch}.{name}" in request.form} for ch in CHANNELS}
        try:
            hours = {ch: open_hours_mod.from_form({k[len(f"hours.{ch}."):]: v for k, v in request.form.items() if k.startswith(f"hours.{ch}.")}, ch)
                     for ch in CHANNELS if any(k.startswith(f"hours.{ch}.") for k in request.form)}   # Phase BL: checked before anything is kept
            if "zone" in request.form and request.form["zone"] != vb.zone(key):
                vb.set_zone(key, request.form["zone"], g.user["id"])
            vb.set_settings(key, data, g.user["id"])
            if hours:
                vb.set_open_hours(key, hours, g.user["id"])
        except ValueError as exc:
            flash(str(exc))
            return _render("settings")
        ctx._record("volumes_settings_saved", program=key, subject="Volumes", detail="settings saved")
        flash("Saved the settings.")
        return redirect(url_for("volumes_page", tab="settings", program=key), code=303)

    @app.route("/volumes/sites", methods=["POST"])
    @login_required
    def volumes_sites():  # type: ignore[no-untyped-def]
        """Sites and who takes which contacts: add or remove a site, add or remove a rule. The whole document is checked before anything is kept."""
        vb, key = _book(), _unit()
        form = request.form
        doc = vb.sites(key)
        action = form.get("action", "")
        try:
            if action == "add_site":
                doc["sites"].append({"name": form.get("name", ""), "lob": form.get("lob", "")})
                said = f"Added the site {' '.join(form.get('name', '').split())[:40]}."
            elif action == "remove_site":
                name = form.get("name", "")
                if any(r["shares"].get(name, 0) > 0 for r in doc["rules"]):
                    raise ValueError(f"Remove the rules that give {name} a share first.")
                doc["sites"] = [x for x in doc["sites"] if x["name"] != name]
                for r in doc["rules"]:
                    r["shares"].pop(name, None)
                said = f"Removed the site {name}."
            elif action == "add_rule":
                channel = form.get("channel", "")
                start = open_hours_mod.clock_minutes(form.get("start", ""), f"{channel}, the start")
                end = open_hours_mod.clock_minutes(form.get("end", ""), f"{channel}, the end")
                if start < end <= start + 1440 or end == start:
                    pass
                elif end < start:
                    end += 1440
                doc["rules"].append({"channel": channel, "days": [int(d) for d in form.getlist("days") if d.isdigit()], "from": start, "to": end,
                                     "shares": {x["name"]: form.get(f"share.{x['name']}", "0") for x in doc["sites"]}})
                said = "Added the rule."
            elif action == "remove_rule":
                index = int(form.get("index", "-1")) if form.get("index", "").isdigit() else -1
                if not 0 <= index < len(doc["rules"]):
                    raise ValueError("That rule was already removed.")
                doc["rules"].pop(index)
                said = "Removed the rule."
            else:
                raise ValueError("Choose what to change.")
            vb.set_sites(key, doc, g.user["id"])
        except ValueError as exc:
            flash(str(exc))
            return _render("settings")
        ctx._record("volumes_sites_saved", program=key, subject="Volumes", detail=said)
        flash(said)
        return redirect(url_for("volumes_page", tab="settings", program=key), code=303)

    @app.route("/volumes/outlook-index", methods=["POST"])
    @login_required
    def volumes_outlook_index():  # type: ignore[no-untyped-def]
        """The seasonal index (percent of the trend) typed for the months of a channel the history has not seen; all checked before any is kept."""
        vb, key = _book(), _unit()
        channel = _channel(request.form.get("channel", ""))
        try:
            vb.set_outlook_index(key, channel, {m: request.form.get(f"idx.{m}", "") for m in range(1, 13) if f"idx.{m}" in request.form}, g.user["id"])
        except ValueError as exc:
            flash(str(exc))
            return _render("outlook")
        ctx._record("volumes_outlook_saved", program=key, subject=channel, detail="seasonal index for the months ahead")
        flash("Saved the seasonal index.")
        return redirect(url_for("volumes_page", tab="outlook", program=key, channel=channel), code=303)

    @app.route("/volumes/outlook.xlsx")
    @login_required
    def volumes_outlook_xlsx():  # type: ignore[no-untyped-def]
        """The months, weeks and days ahead for a channel (and a site), one sheet each, with the range and how each figure was worked out."""
        vb, key = _book(), _unit()
        channel = _channel(request.args.get("channel", ""))
        site = request.args.get("site", "")
        try:
            o = vb.outlook(key, channel, months=request.args.get("months", "6"), site=site or None)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("volumes_page", tab="outlook", program=key, channel=channel), code=303)
        wb = Workbook()
        wb.active.title = "Months"
        months, weeks, days = wb.active, wb.create_sheet("Weeks"), wb.create_sheet("Days")
        months.append(["Month", "Days counted", "Expected", "Low", "High", "How it was worked out"])
        for m in o["months"]:
            months.append([m["label"], m["days"], m["expected"], m["low"], m["high"], ", ".join(f"{BASIS_WORDS[b]} ({n})" for b, n in m["bases"].items())])
        weeks.append(["Week starting", "Basis", "Expected", "Low", "High"])
        days.append(["Date", "Day", "Expected", "Low", "High", "Change from events", "Events"])
        for w in o["weeks"]:
            weeks.append([w["week"], BASIS_WORDS[w["basis"]], w["expected"], w["low"], w["high"]])
            for d in w["days"]:
                days.append([d["date"], d["weekday"], d["expected"], d["low"], d["high"], round((d["factor"] - 1) * 100, 1), ", ".join(d["events"])])
        for ws in (months, weeks, days):
            for cell in ws[1]:
                cell.font = Font(bold=True)
        for note in o["notes"]:
            months.append([])
            months.append([note])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        tag = ("_" + re.sub(r"[^A-Za-z0-9]+", "_", site).strip("_")) if site else ""
        ctx._record("downloaded", program=key, subject="Volumes months ahead", detail=f"{channel}{' ' + site if site else ''}")
        return send_file(out, as_attachment=True, download_name=f"Months_ahead_{channel}{tag}_{o['start']}.xlsx", mimetype=XLSX)

    # ------------------------------------------------------------------ downloads
    def _sheet(rows: List[List[Any]], title: str) -> io.BytesIO:
        wb = Workbook()
        ws = wb.active
        ws.title = title[:31]
        for r in rows:
            ws.append([None if v == "" else v for v in r])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.column_dimensions["A"].width = 11
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return out

    @app.route("/volumes/table.xlsx")
    @login_required
    def volumes_table():  # type: ignore[no-untyped-def]
        """One grid of a page as an Excel sheet in the input sheet's layout: calls or people needed (the forecast), or offered or OTF (the week)."""
        vb, key = _book(), _unit()
        channel = _channel(request.args.get("channel", ""))
        week = _week(key, request.args.get("week", ""), _today())
        what = request.args.get("what", "calls")
        if what in ("calls", "needs"):
            f = vb.view_in(key, _plan(vb, key, channel, week, total=request.args.get("total") or None, day_totals=_typed_days()), week, _show_zone(vb, key))
            values = f.get("calls") if what == "calls" else f.get("needs")
        elif what in ("actual", "otf"):
            r = vb.report(key, channel, week)
            values = r["actual"] if what == "actual" else (r["otf"] and [[None if v is None else round(v, 1) for v in row] for row in r["otf"]])
        else:
            abort(404)
        if not values:
            abort(404)
        name = f"Volumes_{channel}_{what}_{week.isoformat()}.xlsx"
        return send_file(_sheet(vb.grid(values, vb.step(key)), f"{channel} {what}"), as_attachment=True, download_name=name, mimetype=XLSX)

    @app.route("/volumes/requirements.xlsx")
    @login_required
    def volumes_requirements():  # type: ignore[no-untyped-def]
        """FT Wise and a tab per channel (people needed on the floor) from each channel's saved forecast (the total is the planner's, so nothing is made up)."""
        vb, key = _book(), _unit()
        week = _week(key, request.args.get("week", ""), _today() + timedelta(weeks=1))
        site = request.args.get("site", "")
        found = {}
        for ch in CHANNELS:
            f = vb.forecast(key, ch, week)
            if not f["error"] and f.get("needs"):
                found[ch] = f
        try:
            if site and site not in [x["name"] for x in vb.sites(key)["sites"]]:
                raise ValueError("That site does not exist.")
            data = vb.requirement_workbook(key, week, found, site=site or None)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("volumes_page", tab="forecast", program=key, week=week.isoformat()), code=303)
        tag = re.sub(r"[^A-Za-z0-9]+", "_", site).strip("_") + "_" if site else ""
        ctx._record("downloaded", program=key, week_start=week.isoformat(), subject="Volumes requirement", detail=", ".join(sorted(found)) + (f" for {site}" if site else ""))
        return send_file(io.BytesIO(data), as_attachment=True, download_name=f"Requirement_from_forecast_{tag}{week.isoformat()}.xlsx", mimetype=XLSX)

    @app.route("/volumes/formulas.xlsx")
    @login_required
    def volumes_formulas():  # type: ignore[no-untyped-def]
        """The channel as the page shows it, with the people needed as live Excel formulas beside the site's own figures."""
        vb, key = _book(), _unit()
        channel = _channel(request.args.get("channel", ""))
        week = _week(key, request.args.get("week", ""), _today() + timedelta(weeks=1))
        f = vb.view_in(key, _plan(vb, key, channel, week, total=request.args.get("total") or None, day_totals=_typed_days()), week, _show_zone(vb, key))
        if f["error"] or not f.get("needs"):
            abort(404)
        ctx._record("downloaded", program=key, week_start=week.isoformat(), subject="Volumes formulas", detail=channel)
        data = formulas_workbook(week, vb.step(key), {channel: f}, vb.settings(key))
        return send_file(io.BytesIO(data), as_attachment=True, download_name=f"Volumes_{channel}_formulas_{week.isoformat()}.xlsx", mimetype=XLSX)

    @app.route("/volumes/draft.xlsx")
    @login_required
    def volumes_draft():  # type: ignore[no-untyped-def]
        """A draft to fill in Excel and upload: a sheet per channel in the input sheet's layout, at the program's interval."""
        vb, key = _book(), _unit()
        week = _week(key, request.args.get("week", ""), _today() - timedelta(weeks=1))
        step = vb.step(key)
        ctx._record("downloaded", program=key, week_start=week.isoformat(), subject="Volumes draft", detail=f"{step}-minute intervals")
        return send_file(io.BytesIO(draft_workbook(week, step)), as_attachment=True, download_name=f"Volumes_draft_{week.isoformat()}.xlsx", mimetype=XLSX)

    @app.route("/volumes/template.xlsx")
    @login_required
    def volumes_template():  # type: ignore[no-untyped-def]
        """The two layouts an upload can use, with made-up rows."""
        wb = Workbook()
        long = wb.active
        long.title = "One row per interval"
        long.append(["Date", "Interval", "Channel", "Offered", "AHT"])
        for h in (9, 10):
            long.append([date(2026, 10, 26), f"{h:02d}:00", "Phone", 40 + h, 300])
        grid = wb.create_sheet("Input sheet layout")
        grid.append(["Interval", *DAY_NAMES])
        for h in (9, 10):
            grid.append([f"{h:02d}:00", 20, 40 + h, 41 + h, 39 + h, 38 + h, 36 + h, 22])
        for ws in (long, grid):
            for cell in ws[1]:
                cell.font = Font(bold=True)
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, as_attachment=True, download_name="Volumes_Actuals_Template.xlsx", mimetype=XLSX)
