# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: a week's channels."""
from __future__ import annotations

import io
import json
import tempfile
import time
from datetime import date
from pathlib import Path

from flask import abort, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from ..app import start_date
from ..attendance import hm
from ..auth import login_required
from ..channel_fair import fairness
from ..channel_page import FULL as FULL_DAYS, NAMES as CHANNEL_NAMES, apply_edit, carry as channel_carry, coverage as channel_coverage, current as channel_current, grid as channel_grid, people_for, planned_anything
from ..channel_people import ChannelPeople
from ..channel_plan import NoPlan, score_day
from ..channels import read_channels
from ..clock import HOME, ZONES, pick_zone
from ..day import read_inputs
from ..versions import DAYS, shift_span, stale_blocks, with_notes, zoned_copy
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the a week's channels routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- a week's channels (Phase V)
    @app.route("/schedules/<int:schedule_id>/channels", methods=["GET", "POST"])
    @login_required
    def plan_channels(schedule_id: int):  # type: ignore[no-untyped-def]
        """Plan a week's channels: a grid per day, Suggest (channels, and breaks inside the break rules), a block set
        by hand, Copy to days with the same shifts; nothing is kept until Save, which makes a new version."""
        row = ctx._version_or_404(schedule_id)
        store, book = app.extensions["store"], ctx._book()
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
            if action in ("suggest", "suggest_week"):  # Phase AY: the tick on the page decides, not only the workbook
                setup = dict(setup, rules=dict(setup["rules"], consistent=request.form.get("consistent") == "1"))
            try:
                if action == "suggest":
                    found = A.plan_day(people, setup, rules, d, carry=channel_carry(week, rules, draft, d),
                                     move_breaks=request.form.get("move") == "1",
                                     before=ctx._channel_before(row, week, rules, draft, d, skills, inputs["languages"]))
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
                            found = A.plan_day(theirs, setup, rules, o, carry=channel_carry(week, rules, draft, o),
                                             move_breaks=request.form.get("move") == "1",
                                             before=ctx._channel_before(row, week, rules, draft, o, skills, inputs["languages"]))
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
                    start = ctx._clock_of(request.form.get("start", ""), span)
                    end = ctx._clock_of(request.form.get("end", ""), span)
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
                    use = request.form.get("use") == "1" and ctx._may_set_in_use(row)
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
        score = score_day(people, plan, setup, d, rules, before=ctx._channel_before(row, week, rules, draft, d, skills, inputs["languages"]))
        target = setup["email_hours"][d]["hours"] if setup["email_mode"] == "hours" else None
        run = store.get_run(row["run_id"]) or {}
        return render_template("channels.html", row=row, run=run, day=day, days=DAYS, full=FULL_DAYS, setup=setup,
                               grid=channel_grid(people, plan), people=people, score=score, target=target,
                               cover=channel_coverage(people, plan, setup, d, inputs["interval"], before=ctx._channel_before(row, week, rules, draft, d, skills, inputs["languages"])),
                               plan=plan, planned=planned_anything(plan), drafted=sorted(draft, key=DAYS.index), names=CHANNEL_NAMES,
                               stale=[] if day in draft else stale_blocks(week, d),
                               may_set_in_use=ctx._may_set_in_use(row), hm=hm,
                               fair=fairness(week, rules, draft, skills, inputs["languages"], d))

    @app.route("/schedules/<int:schedule_id>/check", methods=["POST"])
    @login_required
    def schedule_check(schedule_id: int):  # type: ignore[no-untyped-def]
        ctx._version_or_404(schedule_id)
        try:
            found = ctx._book().check(schedule_id, request.form.get("associate", ""), request.form.get("day", ""),
                                  request.form.get("value", ""))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(severity=found["severity"],
                       added=[{"severity": p["severity"], "text": p["text"]} for p in found["added"]],
                       metrics={k: found["metrics"].get(k) for k in ("active_intervals", "after_100", "before_100")})

    @app.route("/schedules/<int:schedule_id>/change", methods=["POST"])
    @login_required
    def schedule_change(schedule_id: int):  # type: ignore[no-untyped-def]
        row = ctx._version_or_404(schedule_id)
        name, day, value = (request.form.get(k, "") for k in ("associate", "day", "value"))
        reason = " ".join(request.form.get("reason", "").split())[:300]
        book = ctx._book()
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
        ctx._version_or_404(schedule_id)
        try:
            found = ctx._book().check_swap(schedule_id, request.form.get("first", ""), request.form.get("second", ""))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(severity=found["severity"],
                       added=[{"severity": p["severity"], "text": p["text"]} for p in found["added"]])

    @app.route("/schedules/<int:schedule_id>/swap", methods=["POST"])
    @login_required
    def schedule_swap(schedule_id: int):  # type: ignore[no-untyped-def]
        row = ctx._version_or_404(schedule_id)
        first, second = request.form.get("first", ""), request.form.get("second", "")
        reason = " ".join(request.form.get("reason", "").split())[:300]
        book = ctx._book()
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
        row = ctx._version_or_404(schedule_id)
        if not ctx._may_set_in_use(row):
            abort(403)
        ctx._book().set_in_use(schedule_id, g.user["id"])
        flash(f"{row['label']} is now the schedule in use.")
        return redirect(url_for("run_schedules", run_id=row["run_id"], v=schedule_id))

    @app.route("/schedules/<int:schedule_id>/download")
    @login_required
    def schedule_download(schedule_id: int):  # type: ignore[no-untyped-def]
        row = ctx._version_or_404(schedule_id)
        book = ctx._book()
        stem = secure_filename(f"{row['program'] or row['run_id']}_{row['week_start']}_{row['label']}") or "schedule"
        # Phase AM: "Times in" another zone downloads a copy in that zone's clock; the kept workbook stays as it is
        own = pick_zone((ctx._book().store.get_run(row["run_id"]) or {}).get("tz") or HOME)
        tz = request.args.get("tz", "")
        first = start_date(row["week_start"] or "")
        convert = tz in dict(ZONES) and tz != own and bool(first)
        if convert:
            stem = secure_filename(f"{stem}_{dict(ZONES)[tz].split(' (')[0]} time") or stem
        ctx._record("downloaded", program=row["program"], week_start=row["week_start"], run_id=row["run_id"],
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
        from ..channel_export import channel_plan_workbook
        row = ctx._version_or_404(schedule_id)
        store, book = app.extensions["store"], ctx._book()
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
        row = ctx._version_or_404(schedule_id)
        use = request.form.get("use") == "1" and ctx._may_set_in_use(row)
        try:
            found = ctx._book().auto_breaks(schedule_id, g.user["id"], use)
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
        row = ctx._version_or_404(schedule_id)
        elsewhere = None  # Phase Z: a version that is not in use says which schedule the week uses
        if not row["in_use"] and row["program"] and row["week_start"]:
            used = ctx._book().in_use(row["program"], row["week_start"])
            if used is not None and used["run_id"] != row["run_id"]:
                elsewhere = {"run_id": used["run_id"],
                             "workbook": (app.extensions["store"].get_run(used["run_id"]) or {}).get("workbook", "")}
        return ctx._version_week(row, "before" if request.args.get("side") == "before" else "after", elsewhere=elsewhere)

