# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: a week's breaks."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

from flask import flash, g, redirect, render_template, request, url_for

from ..app import start_date
from ..attendance import hm
from ..auth import login_required
from ..break_plan import check_row, floor, slots_for, suggest
from ..channel_page import before as channel_before
from ..day import read_inputs
from ..versions import DAYS, shift_span


def register(app, ctx) -> None:
    """Add the a week's breaks routes to ``app``; ``ctx`` holds the helpers the areas share."""
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
            prior, _ = ctx._days().version(row["program"], prior_on)
            previous = json.loads(prior["week"] or "{}") if prior else None
        return channel_before(week, rules, draft, d, skills, language_rows, previous_week=previous)

    @app.route("/schedules/<int:schedule_id>/breaks", methods=["GET", "POST"])
    @login_required
    def plan_breaks(schedule_id: int):  # type: ignore[no-untyped-def]
        """Plan a week's breaks: a grid per day, Suggest for the empty ones, saved as a new version."""
        row = ctx._version_or_404(schedule_id)
        store, book = app.extensions["store"], ctx._book()
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
                use = request.form.get("use") == "1" and ctx._may_set_in_use(row)
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
                                                                                  ctx._week_target(row["program"], row["week_start"], row["run_id"])),
                               interval=inputs["interval"], drafted=sorted(draft, key=DAYS.index),
                               may_set_in_use=ctx._may_set_in_use(row), hm=hm)

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

    ctx._channel_before = _channel_before
    ctx._clock_of = _clock_of
