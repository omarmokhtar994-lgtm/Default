# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: my week."""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any, Dict, List

from flask import abort, flash, g, redirect, render_template, request, url_for

from ..attendance import hm, week_start
from ..auth import login_required
from ..clock import EGYPT, ZONES, zone_gap_words
from ..day import my_items
from ..leave import KINDS as LEAVE_KINDS, span_text
from ..versions import shift_span
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the my week routes to ``app``; ``ctx`` holds the helpers the areas share."""
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
        clock_now = A.datetime.now(EGYPT)
        today = clock_now.date()
        weeks = _my_weeks(key, today) if key else []
        swap_week = ctx._date(request.args.get("swapweek", ""))
        week_offers = swaps.week_candidates(key, swap_week, name, today) if swap_week in weeks else []
        swap_day = ctx._date(request.args.get("swap", ""))
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
            shown = ctx._date(request.args.get("week", ""))
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
        answers = _leave_swap_answers(g.user["id"])  # Phase AU: the answers since they last looked, shown once
        return render_template("me.html", unit=key, answers=answers, kinds=LEAVE_KINDS, mine=mine, swaps=my_swaps, swap_day=swap_day,
                               swap_note=swap_note, weeks=weeks, shown=shown, week_labels={w.isoformat(): f"{w:%d %b} to {(w + timedelta(days=6)):%d %b}" for w in weeks}, swap_week=swap_week, week_offers=week_offers,
                               offers=offers, today=today, week=week, hm=hm)

    def _zone_words() -> str:
        """Phase AU: "Times are in Cairo (Egypt) time." for an associate's pages, with the gap when it is another zone."""
        key = _my_unit()
        if not key:
            return ""
        today = A.datetime.now(EGYPT).date()
        zone = ctx._own_zone(key, today)
        words = f"Times are in {dict(ZONES)[zone]} time, the schedule's own."
        gap = zone_gap_words(zone, today)
        return f"{words} {gap}" if gap else words

    def _day_changes(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Phase AU: changes to this associate's breaks made by someone else since they last looked (never older than
        two days)."""
        key = _my_unit()
        if not key or not user["roster_name"]:
            return []
        since = max(user.get("day_seen_at") or 0, time.time() - 2 * 86400)
        return app.extensions["store"].break_changes_for(key, user["roster_name"], user["id"], since)

    def _leave_swap_answers(user_id: int) -> List[str]:
        """Phase AU: the final answers to this person's leave requests and swaps they have not seen, as lines; marks them seen."""
        store = app.extensions["store"]
        found = store.unseen_leave_swap(user_id)
        lines = []
        for r in found["leave"]:
            span = span_text(date.fromisoformat(r["first_day"]), date.fromisoformat(r["last_day"]))
            lines.append(f"{r['kind']}, {span}: {r['status']}" + (f". “{r['reason']}”" if r["status"] == "refused" and r["reason"] else "")
                         + (f". {r['outcome']}" if r["status"] == "approved" and r["outcome"] else ""))
        for r in found["swaps"]:
            lines.append(f"Swap with {r['other']} on {date.fromisoformat(r['day']):%a %d %b}: {r['status']}"
                         + (f". “{r['reason']}”" if r["reason"] else ""))
        store.mark_leave_swap_seen([r["id"] for r in found["leave"]], [r["id"] for r in found["swaps"]])
        return lines

    def _my_weeks(key: str, today: date) -> List[date]:
        """Phase AO: the Sundays of this week and every later week that has a schedule kept for ``key``."""
        found = []
        for w in app.extensions["schedules"].kept_weeks(key):
            first = ctx._date(w["week"])
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
        for p in ctx._access().programs():
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
        first, last = ctx._date(request.form.get("first", "")), ctx._date(request.form.get("last", "")
                                                                  or request.form.get("first", ""))
        try:
            if first is None or last is None:
                raise ValueError("Pick the first and the last day.")
            app.extensions["leave"].ask(key, g.user["roster_name"], g.user["id"], request.form.get("kind", ""),
                                        first, last, request.form.get("note", ""), A.datetime.now(EGYPT).date())
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
        on, other = ctx._date(request.form.get("day", "")), " ".join(request.form.get("other", "").split())
        week_first = ctx._date(request.form.get("week", ""))
        try:
            if week_first is not None:  # Phase AO: the whole week from today on, one request
                if not other:
                    raise ValueError("Pick a colleague.")
                today = A.datetime.now(EGYPT).date()
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
                                          request.form.get("note", ""), A.datetime.now(EGYPT).date(),
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
        if not ctx._access().can_open(row["program"]):
            abort(403, description="This request is on a program that is not one of yours.")
        try:
            said = app.extensions["swaps"].decide(swap_id, g.user, request.form.get("decision") == "approve",
                                                  request.form.get("reason", ""))
        except ValueError as exc:
            said = str(exc)
        ctx._record("swap_decided", subject=f"{row['asker']} and {row['other']}, {row['day']}", detail=said[:300])
        flash(said)
        return redirect(url_for("requests_page", program=row["program"]))

    ctx._day_changes = _day_changes
    ctx._my_unit = _my_unit
    ctx._zone_words = _zone_words
