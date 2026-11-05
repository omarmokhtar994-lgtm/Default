# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: break changes and coaching."""
from __future__ import annotations

import json
import re
import time
from datetime import timedelta
from typing import Dict
from zoneinfo import ZoneInfo

from flask import abort, flash, g, redirect, render_template, request, url_for

from ..app import clean_program
from ..attendance import hm
from ..auth import login_required, manager_required, safe_next
from ..clock import EGYPT
from ..day import my_day
from ..permissions import allowed
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the break changes and coaching routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- break changes and coaching (Phase AS)
    def _local_now(key: str) -> A.datetime:
        """Now on the clock the program's schedule is kept in (a break time is in the schedule's own time)."""
        return A.datetime.now(ZoneInfo(ctx._own_zone(key, A.datetime.now(EGYPT).date())))

    @app.route("/me/breaks")
    @login_required
    def me_breaks():  # type: ignore[no-untyped-def]
        """An associate's breaks on the running day, and the times they may ask each to move to (Phase AS)."""
        if not g.user["is_associate"]:
            return redirect(url_for("home"))
        key, name = ctx._my_unit(), g.user["roster_name"]
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
        running = None  # Phase AX: a shift that began yesterday and is still running is what "now" is, after midnight
        if found is not None and now is not None and found["on"] < now.date():
            running = my_day(found["view"], name, found["now"])
        card = None  # Phase AU: Today carries the day's card (it was on My week)
        if key and now is not None:
            try:
                page = app.extensions["days"].page(key, now.date())
                card = my_day(page["view"], name, now.hour * 60 + now.minute) if page else None
            except ValueError:  # a day whose input workbook is not kept: the breaks say so, the card is left out
                card = None
        if key:
            book.expire_overdue(key, now)  # Phase AU
        rules = app.extensions["changes"].settings_of(key) if key else {"enabled": True}
        news = book.news(g.user["id"], read=True)  # Phase AU: the answers since they last looked, shown once
        changed = ctx._day_changes(g.user)
        app.extensions["store"].mark_day_seen(g.user["id"], time.time())
        return render_template("me_breaks.html", unit=key, card=card, running=running, news=news, changed=changed, requests_on=rules.get("enabled", True), tomorrow=tomorrow, tseg=tseg, found=found, seg=seg, options=options, problem=problem,
                               today=now.date() if now else None,
                               mine=book.mine(key, g.user["id"]) if key else [], hm=hm,
                               now_at=found["now"] if found else 0)

    @app.route("/me/breaks", methods=["POST"])
    @login_required
    def me_breaks_ask():  # type: ignore[no-untyped-def]
        """Ask the RTA to move a break; the name comes from the account, never from the form."""
        key = ctx._my_unit()
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
        key = ctx._requests_unit()
        book, leave = app.extensions["changes"], app.extensions["leave"]
        now = _local_now(key) if key else None
        names = [n for n in request.args.getlist("who") if n in (leave.names(key) if key else [])]
        on = ctx._date(request.args.get("date", "")) or (now.date() if now else A.datetime.now(EGYPT).date())
        minutes = request.args.get("minutes", 30, type=int)
        billable = request.args.get("billable") == "1"
        options, problem = None, ""
        if key and names:
            try:
                options = book.coaching_options(key, on, names, minutes, now, billable=billable)
            except ValueError as exc:
                problem = str(exc)
        if key:
            book.expire_overdue(key, now)
        news = book.news(g.user["id"], read=True)  # Phase AU
        return render_template("requests_coaching.html", unit=key, news=news, label=ctx._unit_filter(key) if key else "",
                               roster=sorted(leave.names(key)) if key else [], names=names, on=on, minutes=minutes, billable=billable,
                               options=options, problem=problem, depts=[d["name"] if isinstance(d, dict) else d
                                                                        for d in (ctx._with_lists(key) if key else [])],
                               mine=book.mine(key, g.user["id"]) if key else [], hm=hm, may_decide=allowed(
                                   app.extensions["store"], g.user, "rta_change"))

    @app.route("/requests/coaching", methods=["POST"])
    @login_required
    def requests_coaching_ask():  # type: ignore[no-untyped-def]
        if g.user["is_associate"] or not _can_ask_coaching():
            abort(403, description="Your role cannot ask for coaching here.")
        key = clean_program(request.form.get("program", ""))
        if not key or not ctx._access().can_open(key):
            abort(403, description="That is not one of your programs")
        names = request.form.getlist("who")
        on = ctx._date(request.form.get("date", ""))
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
        if not ctx._access().can_open(row["program"]):
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
        ctx._record("change_decided", subject=f"{row['kind']} for {', '.join(json.loads(row['names']))}", detail=said[:300])
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
        if not ctx._access().can_open(row["program"]):
            abort(403, description="This request is on a program that is not one of yours.")
        try:
            said = leave.decide(request_id, g.user, request.form.get("decision") == "approve",
                                request.form.get("reason", ""))
        except ValueError as exc:
            said = str(exc)
        ctx._record("leave_decided", subject=f"{row['associate']}: {row['kind']} {row['first_day']} to {row['last_day']}",
                detail=said[:300])
        flash(said)
        return redirect(url_for("requests_page", program=row["program"]))

    @app.route("/requests/balances", methods=["POST"])
    @manager_required
    def request_balances():  # type: ignore[no-untyped-def]
        """Planned leave balances for a year, one person a line: a name, then the days (pasted from a sheet)."""
        key = ctx._requests_unit()
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
            ctx._record("leave_balances", subject=key, detail=f"{count} for {year}")
            flash(f"Saved {count} balance{'s' if count != 1 else ''} for {year}.")
        return redirect(url_for("requests_page", program=key))

    ctx._can_ask_coaching = _can_ask_coaching
    ctx._local_now = _local_now
