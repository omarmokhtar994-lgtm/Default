# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: volumes (Phase BI; owner, 2026-11-03): actual volumes in, the forecast of a week from a typed total, the people needed with Erlang,
and how the week went. Pages: Actuals, Forecast and needs, How we did, Settings (``/volumes?tab=``). Every grid is laid out like the input sheet
(intervals down, Sun to Sat across) with a button that copies it for Excel."""
from __future__ import annotations

import io
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
from ..volumes import DEFAULTS, LABELS, VolumeBook, _today
from ..volumes_io import CHANNELS, DAY_NAMES, parse_grid, parse_long, parse_pasted, read_table

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TABS = (("actuals", "Actuals"), ("forecast", "Forecast and needs"), ("how", "How we did"), ("settings", "Settings"))
HELD_MINUTES = 20
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
        try:
            return date.fromisoformat((text or "").strip())
        except ValueError:
            return None

    def _week(key: str, text: str, default: date) -> date:
        return week_begin(_date(text) or default, _start_day(key))

    def _week_choices(key: str, centre: date, back: int, ahead: int) -> List[Dict[str, str]]:
        first = week_begin(centre, _start_day(key))
        out = []
        for k in range(-back, ahead + 1):
            d = first + timedelta(weeks=k)
            out.append({"iso": d.isoformat(), "text": f"{d:%a %d %b %Y} to {d + timedelta(days=6):%a %d %b}"})
        return out

    def _typed_days() -> Dict[int, str]:
        return {d: request.values.get(f"d{d}", "").strip() for d in range(7) if request.values.get(f"d{d}", "").strip()}

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
                                "measure": vb.measure_of(key), "day_names": DAY_NAMES, "today": today.isoformat(), "grid_error": "", **extra}
        if tab == "actuals":
            ctxt["weeks"] = _week_choices(key, today - timedelta(weeks=1), 10, 1)
        elif tab == "forecast":
            week = _week(key, request.values.get("week", ""), today + timedelta(weeks=1))
            typed_total = request.values.get("total", "").strip()
            typed_days = _typed_days()
            error = ""
            try:
                f = vb.forecast(key, channel, week, total=typed_total or None, day_totals=typed_days, today=today)
            except ValueError as exc:
                error, f = str(exc), vb.forecast(key, channel, week, today=today)
            if f["error"]:
                error = error or f["error"]
            day = DAY_NAMES.index(request.values.get("day", "Mon")) if request.values.get("day", "Mon") in DAY_NAMES else 1
            ctxt.update(week=week, week_end=week + timedelta(days=6), weeks=_week_choices(key, today + timedelta(weeks=1), 2, 6), f=f, error=error, day=day,
                        total_text=typed_total or (f"{f['total']:,}" if f.get("total") is not None else ""), typed_days=typed_days,
                        calls_grid=vb.grid(f["calls"], step) if f["calls"] else None,
                        needs_grid=vb.grid(f["needs"], step) if f.get("needs") else None,
                        saved=store.volume_forecast(key, channel, week.isoformat()))
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
            r0 = vb.report(key, channel, week, today=today)
            if on is None or not week <= on <= week + timedelta(days=6):
                idx = next((i for i, d in enumerate(r0["actual"]) if sum(d)), 0)
                on = date.fromisoformat(r0["dates"][idx])
            r = vb.report(key, channel, week, on=on, today=today)
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
        elif tab == "settings":
            ctxt.update(settings=vb.settings(key), labels=LABELS, defaults=DEFAULTS)
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
        week = _week(key, request.form.get("week", ""), _today() + timedelta(weeks=1))
        action = request.form.get("action", "preview")
        if action == "save":
            try:
                vb.save_forecast(key, channel, week, request.form.get("total", ""), _typed_days(), g.user["id"])
            except ValueError as exc:
                flash(str(exc))
                return _render("forecast")
            ctx._record("volumes_forecast_saved", program=key, week_start=week.isoformat(), subject=channel,
                        detail=f"{request.form.get('total', '').strip()} contacts")
            flash(f"Saved the {channel} forecast for the week of {week:%a %d %b}.")
            return redirect(url_for("volumes_page", tab="forecast", program=key, channel=channel, week=week.isoformat()), code=303)
        if action == "remove":
            vb.store.delete_volume_forecast(key, channel, week.isoformat())
            ctx._record("volumes_forecast_saved", program=key, week_start=week.isoformat(), subject=channel, detail="removed")
            flash("Removed that forecast.")
            return redirect(url_for("volumes_page", tab="forecast", program=key, channel=channel, week=week.isoformat()), code=303)
        return _render("forecast")

    # ------------------------------------------------------------------ actuals: check, then save
    @app.route("/volumes/actuals/check", methods=["POST"])
    @login_required
    def volumes_actuals_check():  # type: ignore[no-untyped-def]
        vb, key = _book(), _unit()
        channel = _channel(request.form.get("channel", ""))
        today = _today()
        step = vb.step(key)
        result: Dict[str, Any] = {"problems": [], "summary": None, "token": "", "mode": ""}
        try:
            upload = request.files.get("file")
            pasted = request.form.get("paste", "")
            if len(pasted) > MAX_PASTE:
                raise ValueError("That is too much to paste: upload it as a file.")
            if upload is not None and upload.filename:
                table = read_table(upload.read(), upload.filename)
            elif pasted.strip():
                table = parse_pasted(pasted)
            else:
                raise ValueError("Upload a file or paste the table.")
            aht_text = request.form.get("aht_paste", "")
            grid = any(str(row[0]).strip().lower() == "interval" and any(str(c).strip().title()[:3] in DAY_NAMES for c in row[1:])
                       for row in table[:30] if row)
            if grid:
                week = _week(key, request.form.get("week", ""), today - timedelta(weeks=1))
                parsed = parse_grid(table, week, channel, parse_pasted(aht_text) if aht_text.strip() else None, step, today)
                result["mode"] = f"the input sheet's layout for the week of {week:%a %d %b %Y}, {channel}"
            else:
                parsed = parse_long(table, channel, step, today)
                result["mode"] = "one row per date and interval"
            result.update(problems=parsed.problems, summary=parsed.summary)
            if not parsed.problems:
                token = secrets.token_urlsafe(16)
                _held()[token] = {"user": g.user["id"], "key": key, "rows": parsed.rows, "expires": time.time() + 60 * HELD_MINUTES}
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
        done = {ch: vb.store.replace_volume_rows(key, ch, rows, g.user["id"]) for ch, rows in held["rows"].items()}
        said = "; ".join(f"{ch}: {n['rows']:,} rows over {n['days']} day{'s' if n['days'] != 1 else ''}"
                         f"{', replacing ' + str(n['replaced_days']) if n['replaced_days'] else ''}" for ch, n in done.items())
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
            vb.set_settings(key, data, g.user["id"])
        except ValueError as exc:
            flash(str(exc))
            return _render("settings")
        ctx._record("volumes_settings_saved", program=key, subject="Volumes", detail="settings saved")
        flash("Saved the settings.")
        return redirect(url_for("volumes_page", tab="settings", program=key), code=303)

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
            f = vb.forecast(key, channel, week, total=request.args.get("total") or None, day_totals=_typed_days(), today=_today())
            values = f.get("calls") if what == "calls" else f.get("needs")
        elif what in ("actual", "otf"):
            r = vb.report(key, channel, week, today=_today())
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
        """FT Wise and a tab per channel (people needed on the floor) from each channel's saved forecast, else its suggestion."""
        vb, key = _book(), _unit()
        week = _week(key, request.args.get("week", ""), _today() + timedelta(weeks=1))
        found = {}
        for ch in CHANNELS:
            f = vb.forecast(key, ch, week, today=_today())
            if not f["error"] and f.get("needs"):
                found[ch] = f
        try:
            data = vb.requirement_workbook(key, week, found)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("volumes_page", tab="forecast", program=key, week=week.isoformat()), code=303)
        ctx._record("downloaded", program=key, week_start=week.isoformat(), subject="Volumes requirement", detail=", ".join(sorted(found)))
        return send_file(io.BytesIO(data), as_attachment=True, download_name=f"Requirement_from_forecast_{week.isoformat()}.xlsx", mimetype=XLSX)

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
