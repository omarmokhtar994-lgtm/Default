# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: home."""
from __future__ import annotations

import os
import time
from typing import Dict, Optional, Tuple

from flask import render_template, request

from ..app import clean_program, next_sunday, start_choices, start_date, usual_start_days
from ..auth import login_required
from ..eta import queue_plan
from ..programs import ProgramBook


def register(app, ctx) -> None:
    """Add the home routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- home
    def _plan(runs: list) -> Dict[str, dict]:
        queue = app.extensions.get("runs")
        if queue is None:
            return {}
        return queue_plan(runs, time.time(), os.cpu_count() or 1, queue.gate_pending())

    @app.route("/")
    @login_required
    def home():  # type: ignore[no-untyped-def]
        queue = app.extensions.get("runs")
        everyone = app.extensions["store"].list_runs()
        plan = _plan(everyone)  # the queue is shared: waiting times count every run
        runs = ctx._visible(everyone)
        summaries = {r["id"]: ctx._run_figures(r) for r in runs} if queue else {}
        # Phase AI: the queue is everyone's; another program's runs show only as running or waiting, with the wait
        seen = {r["id"] for r in runs}
        active = sorted((r for r in everyone if r["status"] in ("GATE", "RUNNING", "SCORING")),
                        key=lambda r: r["id"] not in seen)
        waiting = sorted((r for r in everyone if r["status"] == "QUEUED"), key=lambda r: r["created"])
        wait_min = max((e["finishes_in_min"] for e in plan.values()), default=0)
        latest = next((r for r in runs if r["status"] in ("DONE", "REVIEW") and summaries.get(r["id"])), None)
        known = sorted({r["program"] for r in runs if r.get("program")}, key=str.lower)
        prefill = start_date(request.args.get("week", "")) or next_sunday()
        upload_programs, upload_keys = _upload_choices(everyone)
        picked = None if request.args.get("all") == "1" else (ctx._left_menu().get("nav_unit") or None)
        unfiled = [r for r in runs if not r.get("program") and r["mode"] != "SMOKE"
                   and r["status"] not in ("REJECTED", "EXPIRED", "CANCELLED")]  # uploaded without a program
        # Phase Z: which run counts for its week, and Home's panel follows the program picked on the left
        in_use_map = app.extensions["store"].in_use_runs()
        in_use_ids = set(in_use_map.values())
        not_in_use_ids = {r["id"] for r in runs if (r.get("program"), r.get("week_start")) in in_use_map
                          and in_use_map[(r["program"], r["week_start"])] != r["id"]}
        latest_week = ""
        if picked:
            mine = [r for r in runs if r.get("program") == picked and r["status"] in ("DONE", "REVIEW")
                    and summaries.get(r["id"])]
            weeks = sorted({r["week_start"] for r in mine if r.get("week_start")})
            used = in_use_map.get((picked, weeks[-1])) if weeks else None
            latest = next((r for r in mine if r["id"] == used), None) or (mine[0] if mine else latest)
            latest_week = weeks[-1] if latest is not None and latest["id"] == used else ""
        cards = _program_cards(runs, picked)
        everything = _program_cards(runs)
        others = [{"name": c["name"], "key": c["units"][0]["key"]} for c in everything
                  if not any(c["name"] == x["name"] for x in cards)] if picked else []
        return render_template("dashboard.html", upload_programs=upload_programs, upload_keys=upload_keys,
                               program_cards=cards, other_programs=others, picked=picked, unfiled=unfiled,
                               unfiled_starts={r["id"]: start_choices(r["week_start"] or prefill, r["week_start"])
                                               for r in unfiled},
                               runs=runs, runs_page=ctx._paged(runs, "runs_page", "runs-h"), queue=queue, plan=plan,
                               summaries=summaries,
                               active=active, waiting=waiting, seen=seen, wait_min=wait_min,
                               latest=latest, latest_week=latest_week,
                               in_use_ids=in_use_ids, not_in_use_ids=not_in_use_ids,
                               latest_summary=ctx._walled(latest, summaries.get(latest["id"])) if latest else None,
                               now=time.time(), known_programs=known,
                               prefill_program=clean_program(request.args.get("program", ""))
                               or (picked if picked in upload_keys else ""),  # the unit picked on the left
                               prefill_week=prefill, start_options=start_choices(prefill, prefill),
                               usual_start=usual_start_days(runs))

    WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

    def _program_cards(runs: list, only: Optional[str] = None) -> list:
        """Home: this person's programs (only the one holding unit ``only`` when given), each LOB with its
        latest schedule week."""
        latest = app.extensions["store"].latest_weeks()
        usual = usual_start_days(runs)
        cards = []
        for p in ctx._access().programs():
            units = [{"key": key, "text": next((l["name"] for l in p["lobs"] if l["key"] == key), p["name"]),
                      "latest": latest.get(key)} for key in p["units"]]
            if not units:
                continue
            if only is not None and only not in p["units"]:
                continue
            day = p["start_day"] if p["saved"] else usual.get(units[0]["key"], 0)
            cards.append({"name": p["name"], "units": units, "starts": WEEKDAYS[day]})
        return cards

    def _upload_choices(runs: list) -> Tuple[list, set]:
        """New schedule is open to everyone, for the programs they have (Phase AR; admins have all): each program with
        its LOBs, and the defaults it starts from (a program's saved defaults, else the weekday its schedules usually start on)."""
        book = ProgramBook(app.extensions["store"])
        book.sync()
        usual = usual_start_days(runs)
        out, keys = [], set()
        for p in book.tree():
            choices = [(l["key"], f"{p['name']}, {l['name']}") for l in p["lobs"]]
            if p["key"] in p["units"]:
                choices.append((p["key"], p["name"] if not p["lobs"] else f"{p['name']} (whole program)"))
            choices = [(k, t) for k, t in choices if ctx._access().can_open(k)]  # Phase AR: only the programs a person has
            if not choices:
                continue
            keys |= {k for k, _ in choices}
            defaults = ({"start_day": p["start_day"], "run_mode": p["run_mode"], "options": p["options"]}
                        if p["saved"] else ({"start_day": usual[p["key"]]} if p["key"] in usual else {}))
            if p.get("measure"):  # Phase AU: how the program counts is also how a new run is built, unless it says otherwise
                options = dict(defaults.get("options") or {})
                options.setdefault("coverage_measure", "INTERVAL_COUNT" if p["measure"] == "interval" else "VOLUME_WEIGHTED")
                defaults = {**defaults, "options": options}
            out.append({"name": p["name"], "choices": choices, "defaults": defaults})
        return out, keys

    ctx._plan = _plan
