# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: the day."""
from __future__ import annotations

import io
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from ..access import Access
from ..adherence import interval_shrinkage, person_day, team as team_figures
from ..app import clean_program, in_range
from ..attendance import ACTIVITY_KINDS, ADD_KINDS, COVER_ROLES, DAY_OFF, DayBook, aux_details, hm, plain_hm, tomorrow_unchecked, week_start
from ..auth import login_required, manager_required
from ..bulk_breaks import SHIFTS as BULK_SHIFTS, verb as bulk_verb
from ..channel_page import NAMES as CHANNEL_NAMES
from ..clock import EGYPT, HOME, ZONES, minute_now, moved_text, noon_gap, pick_zone, rta_window_shift, shift as zone_shift, shown, to_schedule
from ..contacts import ContactBook, pick_contact
from ..daily_views import people_of, workbook as daily_workbook
from ..day import ABSENT as ABSENT_STATES, AUX, BIO, EXTRA_BREAKS, MEASURES, OVERTIME_MAX, STATUSES, at_target, board, glance, hover_tips, now_panel, shift_groups, window_view
from ..handover import note as handover_note
from ..merged_day import merged_page
from ..notify import SERVICES, leave_out
from ..permissions import ENDPOINTS as PERMISSION_ENDPOINTS, allowed
from ..programs import ProgramBook
from ..run_admin import unit_keys
from ..shrinkage import ITEMS as SHRINKAGE_ITEMS, day_shrinkage, read_mapping
from ..versions import shift_span
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the the day routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- the day (Phase N)
    def _days() -> DayBook:
        days = app.extensions.get("days")
        if days is None:
            abort(404)
        return days

    def _date(text: str) -> Optional[date]:
        try:
            return in_range(A.datetime.strptime((text or "").strip(), "%Y-%m-%d").date())
        except ValueError:
            return None

    @app.route("/overview")
    @login_required
    def overview_page():  # type: ignore[no-untyped-def]
        """A program's day at a glance; breaks, attendance and cover are on RTA (the day page)."""
        days = _days()
        programs = ctx._my_programs(days.programs())
        today = A.datetime.now(EGYPT)
        on = _date(request.args.get("date", "")) or today.date()
        program = clean_program(request.args.get("program", "")) or (programs[0] if programs else "")
        page, problem, ahead, attention = None, "", [], {}
        if program:
            try:
                page = days.page(program, on)
            except ValueError as exc:
                problem = str(exc)
        if page:
            v = page["view"]
            cells = [c for c in v["cells"] if c["pm"] is not None]
            now = today.hour * 60 + today.minute if on == today.date() else -1
            ahead = [c for c in cells if c["t"] + v["interval"] > now][:6]
            short = [c for c in cells if c["pm"] < 0 and c["t"] + v["interval"] > now]
            attention = {
                "short": short, "worst": min(short, key=lambda c: c["pm"]) if short else None,
                "absent": [(l["name"], s["status"]) for l in v["lanes"] for s in l["segments"]
                           if s["offset"] == 0 and s["status"] in ABSENT_STATES],
                "late": [(l["name"], s["status"], s.get("to") if s["status"] == "Late" else s.get("from"))
                         for l in v["lanes"] for s in l["segments"]
                         if s["offset"] == 0 and s["status"] in ("Late", "Left early")]}
        return render_template("overview.html", page=page, problem=problem, program=program, programs=programs,
                               on=on, ahead=ahead, attention=attention, week_of=week_start(on),
                               outlook=ctx._outlook(program, week_start(on).isoformat()) if program else None,
                               label=ProgramBook(app.extensions["store"]).label(program) if program else "")

    @app.route("/schedules")
    @login_required
    def schedules_for():  # type: ignore[no-untyped-def]
        """The menu's Schedules (Phase AA, approved sample 03): the program's weeks with a kept schedule, and the
        chosen week's schedules side by side. The week shown is the one asked for, else this week when it has a
        schedule, else the newest."""
        program = clean_program(request.args.get("program", ""))
        book = ctx._book()
        weeks = book.kept_weeks(program) if program else []
        keys = [w["week"] for w in weeks]
        today = A.datetime.now(EGYPT).date()
        this_week = (today - timedelta(days=(today.weekday() + 1) % 7)).isoformat()
        week = request.args.get("week", "")
        if week not in keys:
            week = this_week if this_week in keys else (keys[-1] if keys else "")
        entries = book.week_compare(program, week) if week else []
        return render_template("schedules_week.html", program=program, weeks=weeks, week=week, this_week=this_week,
                               entries=entries,
                               may_use={e["shown"]["id"] for e in entries if ctx._may_set_in_use(e["shown"])},
                               may_delete={e["run"]["id"] for e in entries if ctx._may_delete(e["run"])})

    # Phase AI: the 24 hours from the start picked; Phase AK: Fix breaks, Rescue the day and Change several breaks too
    WINDOW_TABS = ("timeline", "board", "adherence", "replan", "rescue", "bulk")
    START = re.compile(r"^([01]\d|2[0-3]):(00|15|30|45)$")

    def _window_moved(program: str, on: date, zone: str, start: Optional[int] = None) -> Optional[int]:
        """The shift of ``zone`` from the schedule's own clock for the 24 hours the RTA shows (from ``start`` minutes of ``zone``'s clock, else
        the start kept for this program, else midnight); None when the clocks change inside them (Phase AY)."""
        own = _own_zone(program, on)
        if start is None:
            found = START.match(((session.get("rta") or {}).get(program) or {}).get("start", "")) or START.match("00:00")
            start = int(found.group(1)) * 60 + int(found.group(2))
        return rta_window_shift(on, own, zone, start - noon_gap(on, own, zone))

    def _own_zone(program: str, on: date) -> str:
        """The zone the schedule in use for ``program`` on ``on`` was made in (Egypt when none is kept)."""
        row = _days().version(program, on)[0] if program else None
        return pick_zone(((app.extensions["store"].get_run(row["run_id"]) or {}).get("tz") if row else "") or HOME)

    def _rta_choice(program: str, moved_for) -> Tuple[str, int]:
        """Phase AI: the zone and the day's start (minutes, in that zone) the RTA shows ``program`` in: as asked for,
        else as last picked for it this session; Egypt from midnight to begin with. ``window=operating`` (the program's
        operating day, kept in the schedule's time) starts it there; ``moved_for(zone, begins)`` is the zone's shift for the 24 hours from ``begins``."""
        every = dict(session.get("rta") or {})
        kept = dict(every.get(program) or {})
        if request.args.get("tz") in dict(ZONES):
            kept["tz"] = request.args["tz"]
        zone = kept["tz"] if kept.get("tz") in dict(ZONES) else (_pc_zone() or HOME)  # a zone picked here stays; else the computer's
        if START.match(request.args.get("start", "")):
            kept["start"] = request.args["start"]
        elif request.args.get("window") == "operating" and program:
            begins = app.extensions["store"].get_day_start(program)
            if begins is not None:
                kept["start"] = plain_hm(begins + moved_for(zone, begins))
        if program and kept != every.get(program):
            every[program] = kept
            session["rta"] = every
        found = START.match(kept.get("start", "")) or START.match("00:00")
        return zone, int(found.group(1)) * 60 + int(found.group(2))

    @app.url_defaults
    def _keep_embed(endpoint: str, values: Dict[str, Any]) -> None:
        """Phase AY: inside a split-view pane every link and redirect to the day stays embedded."""
        if endpoint == "day_page" and "embed" not in values and request and request.values.get("embed") == "1":
            values["embed"] = "1"

    SPLIT_MAX = 3  # panes (owner: "a max of 2 or 3")

    @app.route("/day/split")
    @login_required
    def day_split():  # type: ignore[no-untyped-def]
        """Phase AY: two or three RTA days side by side or stacked, each its own program, day, zone and tab (each pane is the ordinary day page
        embedded, so every check of that page holds in it)."""
        days = _days()
        mine = ctx._my_programs(days.programs())
        today = A.datetime.now(EGYPT).date()
        panes, missing = [], []
        for i in range(1, SPLIT_MAX + 1):
            asked = request.args.get(f"p{i}", "").strip()
            if not asked:
                continue
            program = clean_program(asked)
            on = _date(request.args.get(f"d{i}", "")) or today
            if program not in mine:
                missing.append(i)
                continue
            panes.append({"n": i, "program": program, "date": on,
                          "src": url_for("day_page", program=program, date=on.isoformat(), embed="1", view=request.args.get(f"v{i}") or None,
                                         tz=request.args.get(f"z{i}") if request.args.get(f"z{i}") in dict(ZONES) else None)})
        layout = request.args.get("layout", "")
        layout = layout if layout in ("rows", "cols") else ("cols" if len(panes) >= 3 else "rows")
        free = next((i for i in range(1, SPLIT_MAX + 1) if not request.args.get(f"p{i}", "").strip()), None)
        slots = [{"n": i, "program": request.args.get(f"p{i}", ""), "date": (_date(request.args.get(f"d{i}", "")) or today).isoformat()}
                 for i in range(1, SPLIT_MAX + 1) if request.args.get(f"p{i}", "").strip() or i == free]
        return render_template("split.html", panes=panes, missing=missing, layout=layout, programs=mine, slots=slots,
                               can_add=free is not None and len(panes) + len(missing) < SPLIT_MAX, max=SPLIT_MAX)

    @app.route("/day")
    @login_required
    def day_page():  # type: ignore[no-untyped-def]
        """A program's day from the schedule in use: who is on the floor, attendance, actual breaks. Phase AI: in the
        zone and from the start picked on the page; every time shown in that zone, and every change kept in the
        schedule's own time."""
        days = _days()
        programs = ctx._my_programs(days.programs())
        on = _date(request.args.get("date", "")) or A.datetime.now(EGYPT).date()
        program = clean_program(request.args.get("program", ""))
        if not program and programs:
            program = next((p for p in programs if days.version(p, on)[0]), programs[0])
        own_zone = _own_zone(program, on)
        g.zone, start_at = _rta_choice(program, lambda zone, begins: rta_window_shift(on, own_zone, zone, begins) or 0)  # 0 when the clocks change in that window (Phase AY)
        moved = _window_moved(program, on, g.zone, start_at)
        g.rta_clock_notice = ""
        if moved is None:
            g.zone, moved = own_zone, 0
            g.rta_clock_notice = ("Clocks change in this window. Times and edits are shown in the schedule's own "
                                  "time zone. This schedule records wall-clock times and does not distinguish "
                                  "the two occurrences of a repeated hour.")
        units = ctx._merge_units(program)  # Phase AP: a View pick when the program has two or more LOBs
        merge = _merge_choice(program)
        _merge_pick_for(program, units, merge)
        with shown(moved):
            return _day_body(days, programs, on, program, own_zone, moved, start_at, merge)

    def _merge_choice(program: str) -> Optional[List[str]]:
        """Phase AP: the LOBs the RTA page shows as one, else None. Phase AX (owner, 2026-10-22: two out of five): the
        LOBs ticked in the View pick, the one the page is opened on always among them; "merge=1" alone keeps the
        choice made, or means all. The pick is kept for the program in the session, like the zone and the start."""
        units = ctx._merge_units(program)
        if len(units) < 2:
            return None
        kept = dict(session.get("rta_merge") or {})
        pid = str(ProgramBook(app.extensions["store"]).unit(program)["program"]["id"])
        if "merge" in request.args:
            if request.args.get("merge") != "1":
                kept[pid] = ""
            elif "pick" in request.args:
                want = set(request.args.getlist("lobs"))
                chosen = [u for u in units if u == program or u in want]
                kept[pid] = "1" if len(chosen) == len(units) else (chosen if len(chosen) > 1 else "")
            elif not kept.get(pid):
                kept[pid] = "1"
            session["rta_merge"] = kept
        held = kept.get(pid)
        if isinstance(held, list):
            chosen = [u for u in units if u == program or u in held]
            return chosen if len(chosen) > 1 else None
        return units if held == "1" else None

    def _merge_pick_for(program: str, units: List[str], merge: Optional[List[str]]) -> None:
        """Phase AX: what the View pick shows: a tick box per LOB, the ones merged ticked, the open one fixed."""
        names = ctx._lob_names(units) if len(units) > 1 else {}
        g.merge_pick = f"All LOBs of {ProgramBook(app.extensions['store']).unit(program)['program']['name']}" \
            if len(units) > 1 else ""
        g.merge_lobs = [{"unit": u, "name": names[u], "home": u == program, "on": bool(merge) and u in merge}
                        for u in units] if len(units) > 1 else []
        g.merge_summary = " + ".join(names[u] for u in merge) if merge else "This LOB"

    MERGE_TABS = ("timeline", "board", "adherence", "requests")  # Phase AP: the tabs that read, and change one person at a time

    def _day_body(days, programs: List[str], on: date, program: str, own_zone: str, moved: int,
                  start_at: int, merge: Optional[List[str]] = None):  # type: ignore[no-untyped-def]
        measure = request.args.get("measure", "")
        # Phase AS: with none in the address the RTA opens on the program's own (interval compliance until it says otherwise)
        measure = measure if measure in MEASURES else (ProgramBook(app.extensions["store"]).day_measure(program)
                                                       if program else "interval")
        tab = request.args.get("view", "")
        tab = tab if tab in ("board", "adherence", "meeting", "sessions", "cover", "replan", "channels", "bulk", "rescue", "requests") else "timeline"
        if merge and tab not in MERGE_TABS:
            flash("Pick one LOB for that tab: it plans or changes one LOB's schedule.")
            return redirect(url_for("day_page", program=program, date=on.isoformat(), merge="1", tz=g.zone,
                                    start=request.args.get("start") or None), code=303)
        problem = ""
        try:
            if merge:
                page = merged_page(days, program, merge, on, measure, start_at - moved, g.zone, _own_zone) \
                    if program else None
                if page and len(merge) < len(ctx._merge_units(program)):  # Phase AX: some of the LOBs, said as such
                    page["note"] = (f"{' + '.join(ctx._lob_names(merge).values())} together. A change made here is saved "
                                    "on the person's own LOB.")
            else:
                page = days.page(program, on, measure) if program else None
        except ValueError as exc:  # said on the page, not a server error
            page, problem = None, str(exc)
        anchor, sources, start = page, {0: page}, 0
        if page and merge:  # the merged page is already the 24 hours from the start picked
            start = page["view"]["start"]
        elif page:  # Phase AI: the 24 hours from the start picked, stitched from the schedule's days
            step = page["view"]["interval"]
            start = start_at - moved
            start -= start % step
            if start and tab in WINDOW_TABS:
                for d in range(start // 1440, (start + 1439) // 1440 + 1):
                    if d:
                        try:
                            sources[d] = days.page(program, on + timedelta(days=d), measure)
                        except ValueError:  # a workbook that cannot be read: its hours stay empty
                            sources[d] = None
                found = window_view({d: (x or {}).get("view") for d, x in sources.items()}, start, on)
                begins = app.extensions["store"].get_day_start(program)  # Phase AU: the operating day runs to its last shift
                if begins is not None and start == begins - begins % step:
                    try:
                        length = A.operating_span(found)
                    except (ValueError, KeyError, TypeError, StopIteration):
                        length = 1440  # it cannot be worked out: 24 hours from the start
                    if length < 1440:
                        found = window_view({d: (x or {}).get("view") for d, x in sources.items()}, start, on, length)
                page = dict(page, view=found, target=at_target(found["cells"], page["target"]["target"]))
        window = bool(page and "start" in page["view"])
        clock_now = A.datetime.now(ZoneInfo(own_zone))
        now_at = (clock_now.date() - on).days * 1440 + clock_now.hour * 60 + clock_now.minute  # from on's midnight

        def source(t: int):  # type: ignore[no-untyped-def]
            """The schedule's day that holds minute ``t`` of the page (from ``on``'s midnight), its page and the
            minute in it."""
            d = t // 1440
            if d not in sources:
                try:
                    sources[d] = days.page(program, on + timedelta(days=d), measure)
                except ValueError:
                    sources[d] = None
            return on + timedelta(days=d), sources[d], t - 1440 * d

        people = shrink = whole = None
        finder: Dict[str, Any] = {}
        cover = None
        sessions = days.sessions(program, on) if page and tab == "sessions" else []
        if page and tab == "meeting":
            finder = {"who": request.args.getlist("who"), "minutes": request.args.get("minutes", 30, type=int),
                      "from": request.args.get("from", "09:00"), "to": request.args.get("to", "18:00"),
                      "kind": request.args.get("kind", "Meeting"), "billable": request.args.get("billable") == "1",
                      "with_whom": request.args.get("with_whom", ""), "why": request.args.get("why", ""),
                      "with_dept": request.args.get("with_dept", ""), "at": request.args.get("at", "")}
            if finder["who"]:
                try:
                    finder["slots"] = days.meeting_slots(program, on, finder["who"], finder["minutes"],
                                                         to_schedule(finder["from"], moved),
                                                         to_schedule(finder["to"], moved), finder["billable"], measure)
                except ValueError as exc:
                    finder["error"] = str(exc)
        clock_now = A.datetime.now(ZoneInfo(own_zone))
        from_now = clock_now.hour * 60 + clock_now.minute if clock_now.date() == on else 0
        shift_view: Dict[str, Any] = {"shift_groups": [], "shift": "", "shift_names": None}
        if page and tab == "timeline":  # the Timeline by shift start (Phase W)
            wanted = request.args.get("shift", "").strip()
            wanted = wanted if wanted == "earlier" or re.match(r"^([01]\d|2[0-3]):[0-5]\d$", wanted) else ""
            groups = shift_groups(page["view"], from_now if clock_now.date() == on else None)
            chosen = next((g for g in groups if g["key"] == wanted), None)
            shift_view = {"shift_groups": groups, "shift": wanted,
                          "shift_names": set(chosen["names"]) if chosen else (set() if wanted else None)}
        outside: Dict[str, Any] = {"rows": [], "prev": [], "roles": COVER_ROLES, "channels": [], "languages": []}
        if page and tab == "cover":
            cover = days.offers(page, from_now)
            ch = page["view"].get("channels")  # Phase AJ: cover from outside the roster, on a channel when there are
            outside = {"rows": days.covers(program, on),
                       "prev": [c for c in days.covers(program, on - timedelta(days=1)) if c["end_min"] > 1440],  # last night's, still on
                       "roles": COVER_ROLES,
                       "channels": [(r["letter"], r["name"]) for r in ch["rows"] if "language" not in r] if ch else [],
                       "languages": days.cover_languages(page)}
        fresh = request.args.get("how") == "fresh"  # Phase AX: "Replan the day's breaks", from scratch
        replan_now = _window_now(on, start) or 0
        passed = bool(fresh and page and minute_now(on, own_zone, A.datetime.now(EGYPT)) >= start + 1440)
        if passed:  # owner, 2026-10-22: only for what is still to come, so a day that has passed has nothing to replan
            replan_now = start + 1440
        proposal = (days.fresh_replan_window if fresh else days.replan_window)(program, on, start, replan_now) \
            if page and tab == "replan" else None
        bulk = _bulk_panel(days, page, program, on, moved, start) if page and tab == "bulk" else None  # Phase AD (sample 04)
        rescue = None  # Phase AD (sample 02): interval compliance only; the page says so for the other measure
        if page and tab == "rescue" and measure == "interval":
            try:
                rescue = days.rescue_plan(program, on, _window_now(on, start), page=None if start else page, start=start)
            except ValueError as exc:
                rescue = {"error": str(exc)}
        dayoff = days.dayoff_plan(anchor, from_now) if anchor and tab == "rescue" else None  # Phase AF (F1, F2)
        chfix = None  # Phase AM: Fix channels, shown before anything is kept
        if page and tab == "channels" and request.args.get("fix") == "1" and allowed(app.extensions["store"], g.user,
                                                                                    "rta_change"):
            try:
                chfix = days.channel_fix_plan(program, on, now=minute_now(on, own_zone, A.datetime.now(EGYPT)))
            except ValueError as exc:
                chfix = {"error": str(exc)}
        cover_panel = None
        cover_at = request.args.get("cover", type=int)
        if page and tab == "board" and cover_at is not None:
            held_on, held, at = source(cover_at)
            try:
                if held is None:
                    raise ValueError("No schedule for that hour.")
                cover_panel = {**days.cover_offers(held, at), "t": cover_at, "end": cover_at + page["view"]["interval"],
                               "date": held_on}  # Phase AI: the page's minutes, the day that holds them
            except ValueError as exc:
                flash(str(exc))
        add_panel = person_panel = None
        add_at = request.args.get("add", type=int)
        first_t = page["view"].get("start", 0) if page else 0
        held = None
        if page and add_at is not None and first_t <= add_at < first_t + 1440:  # "+ Add" on an interval (Phase R)
            held_on, held, t = source(add_at)  # Phase AI: the schedule's day that holds the interval
        if held is not None:
            step = held["view"]["interval"]
            row_at = add_at - add_at % step
            t -= t % step
            own = [(l, x) for l in held["view"]["lanes"] for x in l["segments"] if x["offset"] == 0]
            # Phase AC: someone marked sick or on leave goes last, so + Add never opens on a person it would refuse
            own.sort(key=lambda p: (p[1]["status"] in ABSENT_STATES,
                                    not (p[1]["start"] < t + step and t < p[1]["end"]), p[1]["start"], p[0]["name"]))
            # Phase AD (owner's yes, sample 06): nobody present on shift in this interval: open on Overtime for the
            # person whose shift starts right after it or ends right before it, placed and long enough to cover it
            nobody = bool(own) and not any(x["status"] not in ABSENT_STATES and x["start"] < t + step and t < x["end"]
                                           for _, x in own)
            if nobody:
                own.sort(key=lambda p: (p[1]["status"] in ABSENT_STATES,
                                        min(abs(p[1]["start"] - (t + step)), abs(t - p[1]["end"])), p[1]["start"],
                                        p[0]["name"]))
            first = own[0][1] if nobody else None
            side = "after" if first and first["start"] < t + step else "before"  # before, as always, unless it ended
            reach = (first["start"] - t if side == "before" else t + step - first["end"]) if first else 0
            minutes = min([m for m in ADD_LENGTHS if reach <= m <= OVERTIME_MAX] or [OVERTIME_MAX]) if first else None
            off = days.off_today(program, held_on)  # for "Day off cancelled" (Phase S)
            shifts = days.shift_library(program, held_on)
            add_panel = {"t": t, "end": t + step, "person": request.args.get("person", ""), "date": held_on,
                         "row": row_at,
                         "kinds": {k: v for k, v in ADD_KINDS.items() if off or DAY_OFF not in v},
                         "people": [(l["name"], x["label"], l["language"], x["start"], x["end"],
                                     x["status"].lower() if x["status"] in ABSENT_STATES else "") for l, x in own],
                         "kind_of": GROUP_KIND, "default_what": "Overtime" if nobody else "Break",
                         "default_side": side, "default_minutes": minutes,
                         "cell": next((c for c in held["view"]["cells"] if c["t"] == t), None),
                         "off": off, "shifts": shifts,
                         "shift_pick": max((x for x in shifts if x[1] <= t < x[2]), key=lambda x: x[1],
                                           default=shifts[0] if shifts else None)}  # most of it after this time
        # Find a time's and Change several breaks' "who" is their list of people, not one person's day
        who = request.args.get("who", "") if tab not in ("meeting", "bulk") else ""
        if page and who and add_panel is None:  # one person's day (Phase R)
            lane = next((l for l in page["view"]["lanes"] if l["name"] == who), None)
            if lane is not None:
                seg = next((x for x in lane["segments"] if x["offset"] == 0), lane["segments"][0])
                nowish = now_at if window else from_now
                first = seg["start"] if seg["start"] >= nowish else nowish
                person_panel = {"lane": lane, "seg": seg,
                                "date": seg.get("date") or (on if seg["offset"] == 0 else on - timedelta(days=1)),
                                "add_at": max(first_t, min(first_t + 1439, first - first % page["view"]["interval"]))}
        if page and tab == "adherence":
            v = page["view"]
            people = sorted((person_day(v, l["name"]) for l in v["lanes"] if any(x["offset"] == 0 for x in l["segments"])),
                            key=lambda r: (r["adherence"] is not None, r["adherence"] or 0, r["name"]))
            whole = team_figures(people)
            # Phase AI: each interval's planned shrinkage from the day that holds it
            planned = {t + 1440 * d: x for d, src in sources.items() if src
                       for t, x in src["inputs"].get("planned_shrinkage", {}).get(src["day"], {}).items()}
            if merge:  # Phase AP: each LOB's planned figure on the shared clock, the LOBs' mean at each interval
                found: Dict[int, List[float]] = {}
                for u, src in page["pages"].items():
                    for t, x in src["inputs"].get("planned_shrinkage", {}).get(src["day"], {}).items():
                        found.setdefault(t + page["merged"]["delta"][u], []).append(x)
                planned = {t: sum(xs) / len(xs) for t, xs in found.items()}
            shrink = interval_shrinkage(v, {"planned_shrinkage": {0: planned}}, 0)
        outside_breaks = []  # Phase AX: breaks that lie outside their shift (stale data); said, and Fix moves them inside
        for lane in (page["view"]["lanes"] if page else []):
            for seg in lane["segments"]:
                if seg["offset"] == 0:
                    outside_breaks += [(lane["name"], b["kind"], b["start"]) for b in seg["breaks"]
                                       if b["start"] < seg["start"] or b["start"] + b["minutes"] > seg["end"]]
        bar = {"undo": days.undoable(program, on, g.user["id"]) if program and page and not merge else None,  # Phase AD
               "send": _send_bar(program, on) if program and page and not merge else None,
               "resend": request.args.get("resend", 0, type=int)}
        # Phase AB: group posts (Phase AP: a merged page changes several LOBs, so it posts to no group and has no
        # Undo or Send bar: open the LOB for those)
        group = app.extensions["store"].get_notify(program) if program and not merge else None
        posting = bool(group and group["link"] and group["mode"] in ("on", "preview"))
        post_kinds = [k for k in (group or {}).get("kinds", "").split(",") if k] if posting else []
        now_of_day = now_at if window else (clock_now.hour * 60 + clock_now.minute if clock_now.date() == on
                                            else (10 ** 6 if on < clock_now.date() else -10 ** 6))
        tips = hover_tips(page["view"], now_of_day) if page else {}  # Phase AF (D2, D3)
        at_a_glance = glance(page["view"], now_of_day) if page else []  # Phase AF (D6)
        now_box = now_panel(page["view"], now_of_day) if page else None  # Phase AG (T2): today only
        shrinkage = None  # Phase AF (E1): in and out of office, side by side
        if page:
            kept = app.extensions["store"].get_shrinkage_map(program)
            mapping = read_mapping(kept["mapping"] if kept else None)
            leave_of = {n: k for u in (merge or [program]) for n, k in app.extensions["leave"].approved_on(u, on).items()}
            shrinkage = {**day_shrinkage(anchor["view"], anchor["week"], anchor["day"], mapping, anchor["inputs"],
                                         leave_of),
                         "mapping": mapping, "items": SHRINKAGE_ITEMS,
                         "may_set": allowed(app.extensions["store"], g.user, "setup")}
            if merge:  # Phase AP: the planned figure is the mean of the LOBs' own
                planned = [day_shrinkage(p["view"], p["week"], p["day"], mapping, p["inputs"])["in_office"]["planned"]
                           for p in page["pages"].values()]
                planned = [x for x in planned if x is not None]
                shrinkage["in_office"] = {**shrinkage["in_office"],
                                          "planned": sum(planned) / len(planned) if planned else None}
        return render_template("day.html", outside_breaks=outside_breaks, page=page, problem=problem, program=program, programs=programs, on=on,
                               today=clock_now.date(), tips=tips, at_a_glance=at_a_glance, shrinkage=shrinkage,
                               now_box=now_box, requests_waiting=ctx._requests_waiting(program, g.user) if now_box else 0,
                               posts=app.extensions["notifier"].statuses(program, on.isoformat())
                               if program and on else {},
                               post_to=SERVICES.get(group["service"], "") if posting else "",
                               post_mode=group["mode"] if posting else "", post_kinds=post_kinds,
                               people=people, whole=whole, shrink=shrink, finder=finder, sessions=sessions, cover=cover, outside=outside, prev_on=on - timedelta(days=1),
                               ot_page=ctx._paged(cover["overtime"] if cover else [], "ot_page", "ot-h"),
                               log_page=ctx._paged(list(reversed(page["log"])) if page else [], "log_page", "daylog-h"),
                               proposal=proposal, fresh=fresh, passed=passed, from_now=from_now, cover_panel=cover_panel,
                               tile_now=now_at if window else (from_now if clock_now.date() == on else None),
                               add_panel=add_panel, person_panel=person_panel, lengths=ADD_LENGTHS, bar=bar,
                               overtime_hours=OVERTIME_MAX // 60,
                               bulk=bulk, shifts=BULK_SHIFTS, bulk_verb=bulk_verb, rescue=rescue, dayoff=dayoff, chfix=chfix,
                               team_names=sorted({u["display_name"] for u in app.extensions["store"].list_users()
                                                  if u["active"] and not u["is_associate"] and program
                                                  and Access(app.extensions["store"], u).can_open(program)},
                                                 key=str.lower),  # "With": the program's own staff (Phase AI)
                               with_lists=_with_lists(program) if program else [],  # or from the lists (Phase U)
                               tomorrow_unchecked=tomorrow_unchecked(on) if on else "",
                               activity_kinds=ACTIVITY_KINDS,
                               chhours=ctx._channel_hours_for(merge or [program], page["week_start"])
                               if page and tab == "timeline" else None,
                               merged=bool(merge), lob_names=ctx._lob_names(merge) if merge else {},
                               lob_by_name={l["name"]: l["lob"] for l in page["view"]["lanes"]} if page and merge else {},
                               measure=measure,
                               measures=MEASURES, tab=tab, statuses=STATUSES, aux=sorted(AUX), hm=hm,
                               rows=board(page["view"], page["target"]["target"]) if page and tab == "board" else None, week_of=week_start(on),
                               **_requests_tab(program, on, tab, merge),
                               earlier=on - timedelta(days=1), later=on + timedelta(days=1), **shift_view,
                               **_window_context(program, on, own_zone, moved, start_at, page, anchor, start, tab))

    def _measure_arg(raw: str, program: Any) -> str:
        """Phase AU: the measure asked for, else the program's own (LOBs and defaults), else interval compliance."""
        if raw in MEASURES:
            return raw
        unit = program[0] if isinstance(program, (list, tuple)) and program else program
        return ProgramBook(app.extensions["store"]).day_measure(unit) if isinstance(unit, str) and unit else "interval"

    def _requests_tab(program: str, on: date, tab: str, merge: Optional[List[str]] = None) -> Dict[str, Any]:
        """Phase AU: break changes and coaching on the RTA tab itself: the count for the tab, and (on the tab) the rows.
        In the view with every LOB of a program the rows are all those LOBs', each with its LOB."""
        if not program:
            return {"changes_n": 0}
        book, units = app.extensions["changes"], (merge or [program])
        for u in units:
            book.expire_overdue(u, ctx._local_now(u))  # Phase AU
        found = {"changes_n": sum(book.count(u) for u in units)}
        if tab == "requests":
            rows = []
            for u in units:
                for r in ctx._change_rows(u):
                    r["lob"] = ((ProgramBook(app.extensions["store"]).unit(u) or {}).get("lob") or {}).get("name") or u
                    rows.append(r)
            decided = sorted((r for u in units for r in book.decided(u)), key=lambda r: -(r["decided_at"] or r["asked"]))[:20]
            found.update(changes=rows, changes_decided=decided, unit=program,
                         may_change=allowed(app.extensions["store"], g.user, "rta_change"),
                         can_ask_coaching=ctx._can_ask_coaching(),
                         back=url_for("day_page", program=program, date=on.isoformat(), view="requests", tz=g.zone,
                                      start=request.args.get("start") or None, merge="1" if merge else None))
        return found

    def _window_context(program: str, on: date, own_zone: str, moved: int, start_at: int, page, anchor, start: int,
                        tab: str) -> Dict[str, Any]:
        """Phase AI: what the page says and offers about its zone and start: the starts to pick from (each hour, and
        the program's operating day in the zone shown), where the page's 24 hours begin (``vx``, minutes from the
        day's midnight), the schedule's own zone, and the shift that turns the times shown into the schedule's."""
        begins = app.extensions["store"].get_day_start(program) if program else None
        op = plain_hm(begins + moved) if begins is not None else ""
        hours = sorted({plain_hm(m) for m in range(0, 1440, 60)} | ({op} if op else set()))
        starts = [(h, h + (", the operating day" if h == op else ", the calendar day" if h == "00:00" else ""))
                  for h in hours]
        vx = page["view"].get("start", 0) if page else 0
        return {"starts": starts, "start_at": plain_hm(start_at), "vx": vx, "moved": moved, "own_zone": own_zone,
                "own_name": dict(ZONES)[own_zone].split(" (")[0], "zone_name": dict(ZONES)[g.zone].split(" (")[0], "anchor_view": anchor["view"] if anchor else None,
                "on_anchor_day": bool(start) and tab not in WINDOW_TABS,
                "may_set_start": allowed(app.extensions["store"], g.user, "setup")}

    GOTO_PAGES = (  # (label, endpoint, what it needs: "" anyone, "unit" a program picked, "manager", "admin")
        ("Home", "home", ""), ("RTA", "day_page", "unit"), ("Overview", "overview_page", "unit"),
        ("Wallboard", "day_wallboard", "unit"), ("Weeks", "week_page", "unit"), ("Schedules", "schedules_for", "unit"),
        ("Analysis", "program", "unit"), ("Programs", "programs", ""), ("Exports", "exports_page", ""),
        ("Team", "team_page", ""), ("People", "admin_users", "manager"),
        ("Departments and people", "with_setup", "manager"), ("Associate channels", "channel_setup", "manager"),
        ("Notifications", "notifications_page", "admin"), ("LOBs and defaults", "program_setup", "admin"))
    GOTO_MAX = 8  # results per group

    @app.route("/goto")
    @login_required
    def goto():  # type: ignore[no-untyped-def]
        """Go to (Phase AG, T3): pages, programs and people matching ``q``, as JSON for the Ctrl K dialog."""
        words = request.args.get("q", "").casefold().split()
        program = clean_program(request.args.get("program", ""))
        on = _date(request.args.get("date", "")) or A.datetime.now(EGYPT).date()
        if program and not ctx._access().can_open(program):
            abort(403)

        def hit(text: str) -> bool:
            return all(w in text.casefold() for w in words)

        items: List[Dict[str, str]] = []
        manager = allowed(app.extensions["store"], g.user, "setup")
        can_rta = allowed(app.extensions["store"], g.user, "rta_view")
        for label, endpoint, needs in GOTO_PAGES:
            permission = PERMISSION_ENDPOINTS.get(endpoint)
            if permission and not allowed(app.extensions["store"], g.user, permission):
                continue
            if (needs == "unit" and not program) or (needs == "manager" and not manager) or \
                    (needs == "admin" and not g.user["is_admin"]) or not hit(label):
                continue
            args = {"name": program} if endpoint == "program" else (
                {"program": program, **({"date": on.isoformat()} if endpoint in ("day_page", "overview_page") else {})}
                if needs == "unit" else {})
            items.append({"group": "Pages", "label": label, "note": ctx._unit_name(program) if needs == "unit" else "",
                          "url": url_for(endpoint, **args)})
        units = sorted(k for k in unit_keys(app.extensions["store"]) if ctx._access().can_open(k))
        items += [{"group": "Programs", "label": ctx._unit_name(k), "note": "RTA", "url": url_for("day_page", program=k)}
                  for k in units if can_rta and words and (hit(k) or hit(ctx._unit_name(k)))][:GOTO_MAX]
        if can_rta and program and words:
            found = []
            for name, cell in _days().roster(program, on):
                if not hit(name):
                    continue
                span, word = shift_span(cell), " ".join(str(cell or "").split()).casefold()
                note = (f"{on:%a} {hm(span[0])} to {hm(span[1])}" if span else
                        f"On leave on {on:%a}" if word == "leave" else f"Off on {on:%a}")
                found.append({"group": "People", "label": name, "note": note,
                              "url": url_for("day_page", program=program, date=on.isoformat(), who=name)})
            items += sorted(found, key=lambda i: i["label"])[:GOTO_MAX]
        return jsonify(items=items)

    @app.route("/day/operating-day", methods=["POST"])
    @manager_required
    def day_operating_start():  # type: ignore[no-untyped-def]
        """When a program's operating day starts (Phase AF, A4; admins and supervisors), in the schedule's time."""
        program = clean_program(request.form.get("program", ""))
        on = _date(request.form.get("date", ""))
        if not program or on is None:
            abort(400)
        if not ctx._access().can_open(program):
            abort(403)
        typed = to_schedule(request.form.get("start", "").strip(), _shift_of(program, on))  # Phase AI: as shown
        m = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", typed)
        if not m or int(m.group(2)) % 15:
            flash("Give the start as a time on the quarter hour, like 16:00.")
        else:
            start = int(m.group(1)) * 60 + int(m.group(2))
            app.extensions["store"].set_day_start(program, start, g.user["id"])
            ctx._record("operating_day_set", program=program, subject=hm(start), detail="operating day start")
            _say(f"The operating day starts at {hm(start)}.", program, on)
        return redirect(url_for("day_page", program=program, date=on.isoformat(), window="operating"), code=303)

    ADD_LENGTHS = (5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240)  # minutes offered by "+ Add"
    # What each "+ Add" choice is to a LOB's group rule (Phase AC: the tick shows only for a change that would post)
    GROUP_KIND = {**{k: "added_break" for k in ("Break", "Lunch")}, **{k: "aux" for k in AUX},
                  **{k: "private" for k in ABSENT_STATES}, **{k: "late" for k in ("Late", "Left early")},
                  "Overtime": "overtime", "VTO": "overtime", DAY_OFF: "called_in"}

    def _shift_of(program: str, on: Optional[date]) -> int:
        """Phase AI: minutes the RTA form showed its times ahead of the schedule's own (the form's ``tz``); 0 without
        one, as before."""
        zone = request.values.get("tz", "")
        if not program or on is None or zone not in dict(ZONES):
            return 0
        return zone_shift(on, _own_zone(program, on), zone)

    def _typed(key: str, program: str, on: Optional[date]) -> str:
        """A time typed or picked on the RTA, in the schedule's own time."""
        return to_schedule(request.form.get(key, "").strip(), _shift_of(program, on))

    def _say(text: str, program: str, on: Optional[date]) -> None:
        """Flash ``text`` (made in the schedule's time) with its times as the RTA form showed them."""
        flash(moved_text(text, _shift_of(program, on)))

    def _shown_data(value: Any, minutes: int) -> Any:
        """A JSON answer with every time of day in it as the RTA shows them."""
        if isinstance(value, str):
            return moved_text(value, minutes)
        if isinstance(value, dict):
            return {k: _shown_data(v, minutes) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_shown_data(v, minutes) for v in value]
        return value

    def _refused(exc: Exception, program: str, on: Optional[date]):  # type: ignore[no-untyped-def]
        return jsonify(error=moved_text(str(exc), _shift_of(program, on))), 400

    def _left_out_asked() -> bool:
        """The RTA unticked "Post to the group" for this one change (Phase AB): the form had the tick, and it is off."""
        return request.form.get("post_asked") == "1" and request.form.get("post") != "1"

    def _day_form():  # type: ignore[no-untyped-def]
        on = _date(request.form.get("date", ""))
        if on is None:
            raise ValueError("Pick a day.")
        return clean_program(request.form.get("program", "")), on, request.form.get("associate", "").strip()

    def _posted_day() -> Tuple[str, Optional[date]]:
        """The program and the day a form named (for its answer), whatever else it got wrong."""
        return clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))

    def _break_idx() -> int:
        try:
            return int(request.form.get("idx", ""))
        except ValueError:
            raise ValueError("Pick a break.") from None

    @app.route("/day/channel", methods=["POST"])
    @login_required
    def day_channel():  # type: ignore[no-untyped-def]
        """Phase V: a channel warning's fix, from the Channels tab: a channel change for someone (swap), moving the
        aux that caused it (activity) or a break (break); or taking a channel change back (cancel)."""
        try:
            program, on, name = _day_form()
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("day_page"), code=303)
        action, days, at = request.form.get("action", ""), _days(), request.form.get("at", "")
        try:
            if action == "swap":
                letter = request.form.get("channel", "")
                days.channel_move(program, on, name, _typed("from", program, on), _typed("to", program, on), letter,
                                  g.user["id"])
                flash(f"{name}: {CHANNEL_NAMES.get(letter, letter)} from {request.form.get('from')} to "
                      f"{request.form.get('to')}.")
            elif action == "activity":
                days.move_activity(program, on, request.form.get("id", -1, type=int), _typed("at", program, on),
                                   g.user["id"])
                flash(f"{name}: moved to {at}.")
            elif action == "break":
                days.move_break(program, on, name, _break_idx(), _typed("at", program, on), g.user["id"])
                flash(f"{name}: break moved to {at}.")
            elif action == "cancel":
                days.cancel_channel_move(program, on, request.form.get("id", -1, type=int), g.user["id"])
                flash("The channel change was taken back.")
            else:
                raise ValueError("Pick what to do.")
        except ValueError as exc:  # BreakRefused is a ValueError
            _say(str(exc), program, on)
        return _back_to_day(program, on, "channels")

    def _late_answers() -> Dict[str, str]:
        """Phase AY: what the form says about a late login or early leave: from the allowance or an incident (the allowance when it says
        nothing), and the account manager's approval of an exception (counted only when ticked and commented)."""
        approved = request.form.get("am_ok") == "1"
        return {"late_kind": request.form.get("late_kind", "") or "allowance",
                "am_note": request.form.get("am_note", "").strip() if approved else ""}

    @app.route("/day/attendance-check", methods=["POST"])
    @login_required
    def day_attendance_check():  # type: ignore[no-untyped-def]
        """Phase AY: what a late login or early leave would come to against the allowance, before it is kept (JSON)."""
        try:
            program, on, name = _day_form()
            status = request.form.get("status", "")
            if status not in ("Late", "Left early"):
                raise ValueError("Only a late login or an early leave is checked against the allowance.")
            found = _days().set_status(program, on, name, status, g.user["id"], start=_typed("from", program, on),
                                       end=_typed("to", program, on), dry_run=True, **_late_answers())
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(policy=found["policy"], text=found["what"])

    @app.route("/day/attendance", methods=["POST"])
    @login_required
    def day_attendance():  # type: ignore[no-untyped-def]
        try:
            program, on, name = _day_form()
            status = request.form.get("status", "")
            with_dept, with_whom, why = _aux_answers(status, program)
            _days().set_status(program, on, name, status, g.user["id"],
                               start=_typed("from", program, on), end=_typed("to", program, on),
                               billable=request.form.get("billable") == "1", with_whom=with_whom, why=why,
                               with_dept=with_dept, **_late_answers())
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(ok=True)

    @app.route("/day/absences", methods=["POST"])
    @login_required
    def day_absences():  # type: ignore[no-untyped-def]
        """Absences already known for later days (Phase AF, F3), from the RTA: one person, a whole-shift status, from
        one day to another; the days they do not work are said, not recorded."""
        program = clean_program(request.form.get("program", ""))
        on = _date(request.form.get("date", ""))
        if not program or on is None:
            abort(400)
        if not ctx._access().can_open(program):
            abort(403)
        name, status = request.form.get("associate", "").strip(), request.form.get("status", "")
        first = _date(request.form.get("first", ""))
        last = _date(request.form.get("last", "")) or first
        try:
            if not name or first is None:
                raise ValueError("Pick who and the first day.")
            found = _days().record_absences(program, name, status, first, last, g.user["id"])
            said = []
            if found["done"]:
                said.append(f"Recorded {status.lower()} for {name} on {', '.join(f'{d:%a %d %b}' for d in found['done'])}.")
            if found["off"]:
                said.append(f"{name} is off on {', '.join(f'{d:%a %d %b}' for d in found['off'])}: nothing recorded.")
            if found["missing"]:
                said.append(f"No schedule here for {', '.join(f'{d:%a %d %b}' for d in found['missing'])}.")
            flash(" ".join(said))
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("day_page", program=program, date=on.isoformat()), code=303)

    @app.route("/day/break", methods=["POST"])
    @login_required
    def day_break():  # type: ignore[no-untyped-def]
        try:
            program, on, name = _day_form()
            at = _typed("at", program, on) or None
            with leave_out(_left_out_asked()):
                _days().move_break(program, on, name, _break_idx(), at, g.user["id"],
                                   missed=request.form.get("missed") == "1")
        except ValueError as exc:  # BreakRefused is a ValueError
            return _refused(exc, *_posted_day())
        return jsonify(ok=True)

    def _bulk_form() -> Dict[str, Any]:
        f = request.values
        return {"names": f.getlist("who"), "which": f.get("which", ""), "action": f.get("act", ""),
                "amount": f.get("amount", 0, type=int), "at": f.get("at", ""), "why": f.get("why", "")}

    def _bulk_panel(days, page: Dict[str, Any], program: str, on: date, moved: int = 0,
                    start: int = 0) -> Dict[str, Any]:
        """Change several breaks (Phase AD, sample 04): today's people by shift start with their breaks, the form as
        filled, and the effect once asked for (nothing kept)."""
        now = _window_now(on, start)
        groups: Dict[int, List[Dict[str, str]]] = {}
        kinds: List[str] = []
        for lane in page["view"]["lanes"]:
            for seg in lane["segments"]:
                if seg["offset"] != 0 or seg["status"] in ABSENT_STATES:
                    continue
                said = [f"{b['kind']} {hm(b['start'])}" + (" (started)" if now is not None and b["start"] <= now else "")
                        for b in seg["breaks"]] + [f"{b['kind']} cancelled" for b in seg.get("cancelled", [])]
                groups.setdefault(seg["start"], []).append({"name": lane["name"], "breaks": ", ".join(said)})
                kinds += [b["kind"] for b in seg["breaks"] + seg.get("cancelled", []) if b["kind"] not in kinds]
        form = _bulk_form()
        panel = {"groups": [{"label": f"{hm(t)} shift", "people": people} for t, people in sorted(groups.items())],
                 "kinds": kinds, "who": set(form["names"]), "which": form["which"] or (kinds[0] if kinds else "all"),
                 "act": form["action"] or "cancel", "amount": form["amount"] or 15, "at": form["at"],
                 "why": form["why"], "preview": None, "error": ""}
        if request.args.get("show") and form["names"]:
            try:
                panel["preview"] = days.bulk_preview(program, on, form["names"], panel["which"], panel["act"],
                                                     panel["amount"], to_schedule(form["at"], moved), form["why"], now,
                                                     start=start)
            except ValueError as exc:
                panel["error"] = str(exc)
        return panel

    @app.route("/day/bulk/apply", methods=["POST"])
    @login_required
    def day_bulk_apply():  # type: ignore[no-untyped-def]
        """Phase AD: keep a Change several breaks as one change, held from the group until Send."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        form = _bulk_form()
        try:
            if on is None:
                raise ValueError("Pick a day.")
            start = _form_start()
            done = _days().apply_bulk(program, on, form["names"], form["which"], form["action"], g.user["id"],
                                      amount=form["amount"], at=_typed("at", program, on), why=form["why"],
                                      now=_window_now(on, start), start=start,
                                      missed=request.form.get("missed") == "1")
            said = bulk_verb(form["action"], done)
            _say(said[0].upper() + said[1:] + ".", program, on)
        except ValueError as exc:
            _say(f"Stopped: {exc} Anything changed before it was kept, and Undo takes it all back.", program, on)
        return _back_to_day(program, on, "")

    def _send_bar(program: str, on: date) -> Optional[Dict[str, Any]]:
        """Phase AD (samples 05a, 05b): the newest bulk change of this LOB's day (or the undo of one) and what it
        has with the group: held for Send, posted, or a correction to send; None when nothing goes to a group."""
        store, notifier = app.extensions["store"], app.extensions["notifier"]
        for a in reversed(store.day_actions(program, on.isoformat())):
            of = store.get_day_action(a["undo_of"]) if a["kind"] == "undo" and a["undo_of"] else None
            if a["kind"] != "bulk" and not (of and of["kind"] == "bulk"):
                continue
            state = notifier.action_state(a)
            return {**state, "action": a, "of": of} if state else None
        return None

    @app.route("/day/send", methods=["POST"])
    @login_required
    def day_send():  # type: ignore[no-untyped-def]
        """Phase AD: post a bulk change (or its correction) to the LOB's group; once posted, only when asked again."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        view = request.form.get("view", "")
        action = app.extensions["store"].get_day_action(request.form.get("action_id", 0, type=int))
        if on is None or not action or action["program"] != program or action["shift_date"] != on.isoformat():
            flash("That change is not on this day: open the day again.")
            return _back_to_day(program, on, view)
        posted, said = app.extensions["notifier"].send_action(action, again=request.form.get("again") == "1")
        flash(said)
        if not posted and said.startswith("Already posted"):  # asked on the page (the script asks in a dialog)
            args = {"program": program, "date": on.isoformat(), "resend": action["id"],
                    "view": view if view in ("board", "adherence", "meeting", "sessions", "cover", "replan", "channels", "bulk", "rescue") else None}
            return redirect(url_for("day_page", **{k: v for k, v in args.items() if v}) + "#act-bar", code=303)
        return _back_to_day(program, on, view)

    @app.route("/day/undo-last", methods=["POST"])
    @login_required
    def day_undo_last():  # type: ignore[no-untyped-def]
        """Phase AD: take back your own newest change on this LOB's day (2 at most)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _say(_days().undo_last(program, on, g.user["id"]), program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, request.form.get("view", ""))

    @app.route("/day/break/cancel", methods=["POST"])
    @login_required
    def day_break_cancel():  # type: ignore[no-untyped-def]
        """Phase AD: cancel a break with a reason (sample 03); answered like a break move."""
        try:
            program, on, name = _day_form()
            with leave_out(_left_out_asked()):
                _days().cancel_break(program, on, name, _break_idx(), request.form.get("why", ""), g.user["id"],
                                     now=_minute_now(on))
        except ValueError as exc:  # BreakRefused is a ValueError
            return _refused(exc, *_posted_day())
        return jsonify(ok=True)

    def _minute_now(on: Optional[date], program=None) -> Optional[int]:
        """Now in the schedule timezone when ``on`` is today; None for another date."""
        if on is None:
            return None
        program = program or clean_program(request.values.get("program", ""))
        at = minute_now(on, _own_zone(program, on), A.datetime.now(EGYPT))
        return at if 0 <= at < 1440 else None

    MINUTE = re.compile(r"^-?\d{1,4}$")  # a minute of the page's 24 hours (Phase AI: before 0 too)

    def _window_now(on: Optional[date], start: int, program=None) -> Optional[int]:
        """Phase AK: now as a minute from ``on``'s midnight when it falls in the 24 hours from ``start``, else None
        (from 0, as ``_minute_now``)."""
        if on is None:
            return None
        program = program or clean_program(request.values.get("program", ""))
        at = minute_now(on, _own_zone(program, on), A.datetime.now(EGYPT))
        return at if start <= at < start + 1440 else None

    def _form_start() -> int:
        """The minute the page's 24 hours began at, as the form sent it (0 when it did not)."""
        value = request.form.get("start", "0")
        return int(value) if MINUTE.match(value) else 0

    def _move_item(item: str) -> Tuple[Any, ...]:
        """A move from a form: "name|idx|minute" on the page's day, or "name|idx|minute|YYYY-MM-DD" on its shift's own
        date (Phase AK)."""
        try:
            head, last = item.rsplit("|", 1)
            when = _date(last) if re.match(r"^\d{4}-\d{2}-\d{2}$", last) else None
            name, idx, minute = (head if when else item).rsplit("|", 2)
            return (name, int(idx), int(minute)) + ((when,) if when else ())
        except ValueError:
            raise ValueError("A move in the form cannot be read: open the tool again.") from None

    def _back_to_day(program: str, on: Optional[date], view: str, cover: str = ""):  # type: ignore[no-untyped-def]
        on = _date(request.form.get("anchor", "")) or on  # Phase AI: the day the page showed, not the shift's own
        args = {"program": program, "date": on.isoformat() if on else None,
                "view": view if view in ("board", "adherence", "meeting", "cover", "replan", "channels", "bulk", "rescue", "sessions") else None,
                "cover": cover if MINUTE.match(cover) and view == "board" else None}
        if args["cover"]:
            args["_anchor"] = f"row-{args['cover']}"
        return redirect(url_for("day_page", **{k: v for k, v in args.items() if v}), code=303)

    @app.route("/day/replan/apply", methods=["POST"])
    @login_required
    def day_replan_apply():  # type: ignore[no-untyped-def]
        """Keep the autopilot's moves the user approved (each checked again)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            moves = [_move_item(item) for item in request.form.getlist("move")]
            days = _days()
            with days.action(program, on, g.user["id"], bulk=True) as act:  # Phase AD: one change, held for Send
                try:
                    done = days.apply_replan(program, on, moves, g.user["id"])
                finally:
                    n = len(act.logs)
                    act.label = (f"{'Replan' if request.form.get('how') == 'fresh' else 'Fix'} breaks moved "
                                 f"{n} break{'s' if n != 1 else ''}")
            flash(f"Moved {done} break{'s' if done != 1 else ''}.")
        except ValueError as exc:
            _say(f"{exc} Undo takes back what was kept; open it again for a fresh proposal.", program, on)
        return _back_to_day(program, on, "")

    @app.route("/day/rescue/apply", methods=["POST"])
    @login_required
    def day_rescue_apply():  # type: ignore[no-untyped-def]
        """Phase AD: keep the Rescue the day moves as one change, held from the group until Send."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            moves = [_move_item(item) for item in request.form.getlist("move")]
            if not moves:
                raise ValueError("No moves to keep.")
            start = _form_start()
            done = _days().apply_rescue(program, on, moves, g.user["id"], now=_window_now(on, start), start=start)
            flash(f"Rescue the day moved {done} break{'s' if done != 1 else ''}.")
        except ValueError as exc:
            _say(f"Stopped: {exc} Anything changed before it was kept, and Undo takes it all back.", program, on)
        return _back_to_day(program, on, "")

    @app.route("/day/channels/fix", methods=["POST"])
    @login_required
    def day_channel_fix():  # type: ignore[no-untyped-def]
        """Phase AM: keep the Fix channels changes shown in the preview as one change (one step for Undo)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            changes = []
            for item in request.form.getlist("change"):
                name, lo, hi, letter = (item.split("|") + ["", "", "", ""])[:4]
                if not (lo.isdigit() and hi.isdigit()) or letter not in ("P", "C", "E"):
                    raise ValueError("A change in the list cannot be read: open Fix channels again.")
                changes.append((name, int(lo), int(hi), letter))
            if not changes:
                raise ValueError("No changes to keep.")
            done = _days().apply_channel_fix(program, on, changes, g.user["id"], now=minute_now(on, _own_zone(program, on), A.datetime.now(EGYPT)))
            flash(f"Fix channels changed {done} stretch{'es' if done != 1 else ''}. Undo takes them all back.")
        except ValueError as exc:
            _say(f"No changes were saved: {exc}", program, on)
        return _back_to_day(program, on, "channels")

    @app.route("/day/daily-views.xlsx")
    @login_required
    def day_daily_views():  # type: ignore[no-untyped-def]
        """Phase AP (sample ap01, D): a workbook with a sheet for each associate on the page the RTA shows (one LOB, or
        the merged page), after the day's changes, in the zone and from the start picked."""
        days = _days()
        program, on = clean_program(request.args.get("program", "")), _date(request.args.get("date", ""))
        if not program or on is None:
            abort(400)
        own_zone = _own_zone(program, on)
        g.zone, start_at = _rta_choice(program, lambda zone, begins: rta_window_shift(on, own_zone, zone, begins) or 0)  # 0 when the clocks change in that window (Phase AY)
        moved = _window_moved(program, on, g.zone, start_at)
        if moved is None:
            g.zone, moved = own_zone, 0
        merge = _merge_choice(program)
        try:
            if merge:
                page = merged_page(days, program, merge, on, "interval", start_at - moved, g.zone, _own_zone)
            else:
                page = days.page(program, on)
                if page is not None:
                    start = start_at - moved
                    page = days.window_page(program, on, start - start % page["view"]["interval"])
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("day_page", program=program, date=on.isoformat()), code=303)
        if page is None:
            abort(404)
        shown_at = start_at
        people = people_of(page["view"], moved, ctx._lob_names(merge) if merge else None)
        heading = (f"{on:%A %d %b %Y}, times in {dict(ZONES)[g.zone]}, the 24 hours from {plain_hm(shown_at)}. "
                   "As recorded on the RTA when this was downloaded.")
        name = secure_filename(f"Daily_views_{(ctx._merged_name(program, merge) if merge else program)}_{on}") + ".xlsx"
        ctx._record("downloaded", subject=name, program=program, detail="Daily views")
        return send_file(io.BytesIO(daily_workbook(people, heading)), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/day/handover")
    @login_required
    def day_handover():  # type: ignore[no-untyped-def]
        """The shift handover note: printable, one page."""
        on = _date(request.args.get("date", "")) or A.datetime.now(EGYPT).date()
        program = clean_program(request.args.get("program", ""))
        measure = _measure_arg(request.args.get("measure", ""), program)
        try:
            found = handover_note(_days(), program, on, measure) if program else None
        except ValueError as exc:
            found, problem = None, str(exc)
        else:
            problem = "" if found else f"No schedule for {program or 'this program'} on {on:%d %b}."
        return render_template("handover.html", n=found, problem=problem, program=program, on=on, hm=hm,
                               measures=MEASURES, measure=measure)

    @app.route("/day/wallboard")
    @login_required
    def day_wallboard():  # type: ignore[no-untyped-def]
        """For the floor's screen: now and the next three intervals, breaks now and next; reloads every minute."""
        clock = A.datetime.now(EGYPT)
        on = _date(request.args.get("date", "")) or clock.date()
        at = request.args.get("at", "")
        found = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", at)
        now = int(found.group(1)) * 60 + int(found.group(2)) if found else clock.hour * 60 + clock.minute
        days = _days()
        programs = ctx._my_programs(days.programs())
        program = clean_program(request.args.get("program", "")) or (programs[0] if programs else "")
        page = days.page(program, on) if program else None
        board_now = None
        if page:
            v = page["view"]
            step = v["interval"]
            first = now - now % step
            rows = [c for c in board(v, page["target"]["target"]) if first <= c["t"] < first + 4 * step]
            on_break, soon = [], []
            for lane in v["lanes"]:
                for seg in lane["segments"]:
                    if seg["status"] in ABSENT_STATES:
                        continue
                    added = [{"kind": a["kind"], "start": a["start"], "minutes": a["end"] - a["start"]}
                             for a in seg.get("activities", []) if a["kind"] in EXTRA_BREAKS]  # added on the day
                    for b in seg["breaks"] + added:
                        if b["start"] <= now < b["start"] + b["minutes"]:
                            on_break.append({"name": lane["name"], "kind": b["kind"], "until": b["start"] + b["minutes"]})
                        elif now < b["start"] <= now + 30:
                            soon.append({"name": lane["name"], "kind": b["kind"], "at": b["start"]})
            langs = [{"name": lang["name"], "count": next((c["count"] for c in lang["cells"] if c["t"] == first), None),
                      "cls": next((c["cls"] for c in lang["cells"] if c["t"] == first), "none")} for lang in v["languages"]]
            board_now = {"rows": rows, "on_break": sorted(on_break, key=lambda x: x["until"]),
                         "soon": sorted(soon, key=lambda x: x["at"]), "langs": [x for x in langs if x["count"] is not None],
                         "tiles": v["tiles"]}
        return render_template("wallboard.html", w=board_now, program=program, on=on, now=now, hm=hm,
                               live=not found and on == clock.date())

    def _plan_asked_breaks(program: str, on: date, name: str, kind: str) -> None:
        """Phase AY: the "Short breaks" and "Lunches" counts on the form that adds overtime or a call-in (0 and 0 by default) are placed
        at once, in the same journal entry as the record. A refusal is said, and the record stays."""
        shorts, lunches = request.form.get("shorts", 0, type=int) or 0, request.form.get("lunches", 0, type=int) or 0
        if kind not in ("Overtime", "Called in", DAY_OFF) or not (shorts or lunches):
            return
        try:
            made = _days().plan_extra_breaks(program, on, name, shorts, lunches, g.user["id"])
            _say(f"Planned {len(made)} of the {shorts + lunches} breaks asked for {name}." if len(made) < shorts + lunches
                 else f"Planned {len(made)} breaks for {name}.", program, on)
        except ValueError as exc:
            _say(f"Recorded, but the breaks were not planned: {exc}", program, on)

    @app.route("/day/activity", methods=["POST"])
    @login_required
    def day_activity():  # type: ignore[no-untyped-def]
        """Record an activity (aux, overtime) from a form; back to the day with what happened."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            name, kind = request.form.get("associate", "").strip(), request.form.get("kind", "")
            start, _, end = request.form.get("span", "").partition("|")  # a picked length ("21:00|21:45")
            if not request.form.get("span"):
                start, end = request.form.get("from", ""), request.form.get("to", "")
            start, end = (to_schedule(x.strip(), _shift_of(program, on)) for x in (start, end))
            with_dept, with_whom, why = _aux_answers(kind, program)
            warning = _days().add_activity(program, on, name, kind, start, end, g.user["id"], dry_run=True,
                                           with_whom=with_whom, why=why, with_dept=with_dept).get("warning", "") \
                if kind in ("Overtime", "Called in") else ""
            with _days().action(program, on, g.user["id"]):
                _days().add_activity(program, on, name, kind, start, end,
                                     g.user["id"], billable=request.form.get("billable") == "1",
                                     note=request.form.get("note", ""), with_whom=with_whom, why=why, with_dept=with_dept)
                _plan_asked_breaks(program, on, name, kind)
            flash(f"Recorded: {name}, {'day off cancelled (called in)' if kind == 'Called in' else kind.lower()}.")
            if warning:
                _say(f"Warning: {warning}", program, on)
            if kind in ("Overtime", "Called in") and _days().next_week_unknown(program, on):
                flash(tomorrow_unchecked(on))
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, request.form.get("view", ""), request.form.get("cover", ""))

    @app.route("/day/cover", methods=["POST"])
    @login_required
    def day_cover():  # type: ignore[no-untyped-def]
        """Phase AJ: a team manager or support member, not on the roster, logging in to cover intervals."""
        program, on = _posted_day()
        try:
            if on is None:
                raise ValueError("Pick a day.")
            with leave_out(_left_out_asked()):
                _days().add_cover(program, on, request.form.get("name", ""), request.form.get("role", ""),
                                  _typed("from", program, on), _typed("to", program, on), g.user["id"],
                                  channel=request.form.get("channel", ""), language=request.form.get("language", ""))
            flash(f"Recorded: {' '.join(request.form.get('name', '').split())} covering.")
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "cover")

    # Phase AY (owner, 2026-10-23: "make it for everything and limit it 1 day back for everyone, 7 days for supervisor, unlimited for
    # admin, also the timezone should match their own on the PC"): a change to a day (every POST of the day page) is refused for a day
    # older than yesterday, 7 days back for a supervisor, no limit for an admin. Today is the viewer's own: the zone their browser
    # reports in the ``pc_tz`` cookie (app.js), else the zone the page shows, else Egypt.
    DAY_WRITES = frozenset({
        "day_absences", "day_activity", "day_activity_cancel", "day_activity_edit", "day_add", "day_attendance", "day_book",
        "day_break", "day_break_cancel", "day_bulk_apply", "day_call_in_breaks", "day_channel", "day_channel_fix", "day_cover",
        "day_cover_cancel", "day_replan_apply", "day_rescue_apply", "day_send", "day_session_cancel", "day_session_edit",
        "day_session_move", "day_undo", "day_undo_last"})
    ZONE_NAME = re.compile(r"^[A-Za-z0-9_+\-]+(/[A-Za-z0-9_+\-]+){0,2}$")

    def _viewer_today() -> date:
        pinned = app.config.get("TODAY")  # tests
        if pinned:
            return pinned
        for name in (request.cookies.get("pc_tz", ""), pick_zone(request.values.get("tz", "")), HOME):
            try:
                if name and ZONE_NAME.match(name):
                    return A.datetime.now(ZoneInfo(name)).date()
            except (ZoneInfoNotFoundError, ValueError, OSError):
                continue
        return A.datetime.now(EGYPT).date()

    def _pc_zone() -> Optional[str]:
        """The zone this person's computer is in (``pc_tz``, kept by app.js), when it is one the pages can show times in."""
        name = request.cookies.get("pc_tz", "")
        return name if name in dict(ZONES) else None

    def _back_limit() -> Optional[int]:
        """Days back this person may change; None for no limit."""
        if g.user.get("is_admin"):
            return None
        return 7 if g.user.get("is_supervisor") else 1

    def _still_editable(*days: Optional[date]) -> None:
        limit = _back_limit()
        if limit is None:
            return
        today = _viewer_today()
        for on in days:
            if on is not None and on < today - timedelta(days=limit):
                raise ValueError(f"{on:%a %d %b} is closed to changes for your role: you can change today and {limit} "
                                 f"{'day' if limit == 1 else 'days'} back ({today:%a %d %b} is today where you are). "
                                 "Ask a supervisor or an admin for an older day.")

    @app.route("/day/cover/cancel", methods=["POST"])
    @login_required
    def day_cover_cancel():  # type: ignore[no-untyped-def]
        program, on = _posted_day()
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _days().cancel_cover(program, on, request.form.get("id", 0, type=int), g.user["id"])
            flash("Cancelled.")
        except ValueError as exc:
            _say(str(exc), program, on)
        view = request.form.get("view", "")  # Phase AY: the board's Remove button brings the person back to the board
        return _back_to_day(program, on, view if view == "board" else "cover")

    @app.route("/day/activity/cancel", methods=["POST"])
    @login_required
    def day_activity_cancel():  # type: ignore[no-untyped-def]
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _days().cancel_activity(program, on, request.form.get("id", 0, type=int), g.user["id"])
            flash("Cancelled.")
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, request.form.get("view", ""))

    def _with_lists(program: str) -> list:
        """The departments a booking picks from (Phase U): those of the program's lists with someone in them."""
        return [d for d in ContactBook(app.extensions["store"]).for_unit(program) if d["people"]]

    def _aux_answers(kind: str, program: str) -> Tuple[str, str, str]:
        """(department, with, why) for an aux, from the form: every way of booking one asks who it is with and why
        (Phase T); from the program's lists when it has them, typed when it has none (Phase U)."""
        dept, with_whom = request.form.get("with_dept", ""), request.form.get("with_whom", "")
        lists = _with_lists(program) if kind in AUX and kind != BIO else []
        if lists:
            dept, with_whom = pick_contact(lists, kind, dept, with_whom)
        with_whom, why = aux_details(kind, with_whom, request.form.get("why", ""))
        return (dept if lists else ""), with_whom, why

    def _add_fields():  # type: ignore[no-untyped-def]
        program, on, name = _day_form()
        minutes = request.form.get("minutes", "0")
        return program, on, name, request.form.get("what", ""), _typed("from", program, on), \
            int(minutes) if minutes.isdigit() else -1, request.form.get("billable") == "1"

    def _to_row(program: str, on: Optional[date], view: str, at: str):  # type: ignore[no-untyped-def]
        on = _date(request.form.get("anchor", "")) or on  # Phase AI: the day the page showed
        args = {"program": program, "date": on.isoformat() if on else None,
                "view": view if view in ("board", "cover") else None}
        if MINUTE.match(at):
            args["_anchor"] = f"row-{at}"
        return redirect(url_for("day_page", **{k: v for k, v in args.items() if v}), code=303)

    @app.route("/day/add", methods=["POST"])
    @login_required
    def day_add():  # type: ignore[no-untyped-def]
        """RTA's "+ Add": anything in an interval (a break, lunch, aux, attendance or overtime)."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            program, on, name, what, start, minutes, billable = _add_fields()
            with_dept, with_whom, why = _aux_answers(what, program)
            with leave_out(_left_out_asked()), _days().action(program, on, g.user["id"]):
                found = _days().add_item(program, on, name, what, start, minutes, g.user["id"], billable=billable,
                                         note=request.form.get("note", ""), end=_typed("to", program, on),
                                         with_whom=with_whom, why=why, with_dept=with_dept,
                                         side=request.form.get("side", ""), **_late_answers())
                _plan_asked_breaks(program, on, name, what)
            _say(f"Recorded: {name}, {found['text']}.", program, on)
            if found.get("warning"):
                _say(f"Warning: {found['warning']}", program, on)
            if what in ("Overtime", DAY_OFF) and _days().next_week_unknown(program, on):
                flash(tomorrow_unchecked(on))
        except ValueError as exc:
            _say(str(exc), program, on)
        return _to_row(program, on, request.form.get("view", "board"), request.form.get("at", ""))

    @app.route("/day/add-preview", methods=["POST"])
    @login_required
    def day_add_preview():  # type: ignore[no-untyped-def]
        measure = request.form.get("measure", "")
        try:
            program, on, name, what, start, minutes, billable = _add_fields()
            found = _days().preview_item(program, on, name, what, start, minutes, billable,
                                         _measure_arg(measure, request.form.get("program", "")),
                                         end=_typed("to", program, on),  # who and why are asked on Add
                                         side=request.form.get("side", ""))
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(_shown_data(found, _shift_of(program, on)))

    @app.route("/day/undo", methods=["POST"])
    @login_required
    def day_undo():  # type: ignore[no-untyped-def]
        """From one person's day: a status back to Present, or a moved break back to the plan."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            program, on, name = _day_form()
            if request.form.get("what") == "status":
                _days().set_status(program, on, name, "Present", g.user["id"])
                flash(f"{name} is back to present.")
            elif request.form.get("what") == "break":
                _days().move_break(program, on, name, _break_idx(), None, g.user["id"])
                flash(f"{name}'s break is back to the plan.")
            else:
                abort(400)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _to_row(program, on, request.form.get("view", ""), request.form.get("at", ""))

    @app.route("/day/book", methods=["POST"])
    @login_required
    def day_book():  # type: ignore[no-untyped-def]
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        who = request.form.getlist("who")
        try:
            if on is None:
                raise ValueError("Pick a day.")
            start, minutes = request.form.get("start", -1, type=int), request.form.get("minutes", 0, type=int)
            if request.form.get("at"):  # Phase AV: a time typed in, not one of the suggestions
                start = _days().session_start(program, on, who, _typed("at", program, on))
            kind = request.form.get("kind", "Meeting")
            with_dept, with_whom, why = _aux_answers(kind, program)
            _days().book_session(program, on, who, start, minutes, kind, g.user["id"],
                                 billable=request.form.get("billable") == "1", with_whom=with_whom, why=why,
                                 with_dept=with_dept)
            _say(f"Booked: {kind.lower()} {hm(start)} to {hm(start + minutes)} for {', '.join(who)}.", program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "sessions" if request.form.get("at") else "meeting")

    @app.route("/day/session/move", methods=["POST"])
    @login_required
    def day_session_move():  # type: ignore[no-untyped-def]
        """Phase AV: move some or all of a booked session to another time, all or none."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        who = request.form.getlist("who")
        try:
            if on is None:
                raise ValueError("Pick a day.")
            session = request.form.get("session", "")
            start = _days().session_start(program, on, who, _typed("at", program, on), session)
            _days().move_session(program, on, session, who, start, g.user["id"])
            _say(f"Moved {', '.join(who)} to {hm(start)}.", program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "sessions")

    @app.route("/day/session/edit", methods=["POST"])
    @login_required
    def day_session_edit():  # type: ignore[no-untyped-def]
        """Phase AY: give some or all of a booked session a new start and end, all or none."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        who = request.form.getlist("who")
        try:
            if on is None:
                raise ValueError("Pick a day.")
            session = request.form.get("session", "")
            days = _days()
            start = days.session_start(program, on, who, _typed("at", program, on), session)
            end = days.session_start(program, on, who, _typed("to", program, on), session)
            days.edit_session(program, on, session, who, start, end, g.user["id"])
            _say(f"Changed {', '.join(who)} to {hm(start)} to {hm(end)}.", program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "sessions")

    @app.route("/day/activity/edit", methods=["POST"])
    @login_required
    def day_activity_edit():  # type: ignore[no-untyped-def]
        """Phase AY: a booked aux (coaching, meeting, training) or an added break gets a new start and end."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _days().edit_activity(program, on, request.form.get("id", -1, type=int), _typed("at", program, on),
                                  _typed("to", program, on), g.user["id"])
            _say(f"Changed to {request.form.get('at', '')} to {request.form.get('to', '') or 'the same length'}.", program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        view = request.form.get("view", "")
        return _back_to_day(program, on, view if view in ("cover", "board", "sessions", "timeline") else "cover")

    @app.route("/day/call-in/breaks", methods=["POST"])
    @login_required
    def day_call_in_breaks():  # type: ignore[no-untyped-def]
        """Phase AY: place the breaks of a person called in for typed times, as the program's break rules place them."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        name = request.form.get("associate", "")
        try:
            if on is None:
                raise ValueError("Pick a day.")
            made = _days().plan_call_in_breaks(program, on, name, g.user["id"])
            _say(f"Planned {len(made)} breaks for {name}. Undo takes them back.", program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "cover")

    @app.route("/day/session/cancel", methods=["POST"])
    @login_required
    def day_session_cancel():  # type: ignore[no-untyped-def]
        """Phase AV: take some or all of a booked session out."""
        program, on = clean_program(request.form.get("program", "")), _date(request.form.get("date", ""))
        who = request.form.getlist("who")
        try:
            if on is None:
                raise ValueError("Pick a day.")
            _days().cancel_session(program, on, request.form.get("session", ""), who, g.user["id"])
            _say(f"Took {', '.join(who)} out of the session.", program, on)
        except ValueError as exc:
            _say(str(exc), program, on)
        return _back_to_day(program, on, "sessions")

    @app.route("/day/channel-preview", methods=["POST"])
    @login_required
    def day_channel_preview():  # type: ignore[no-untyped-def]
        """Phase AF (C3): what a channel change would cause, before it is kept (JSON)."""
        try:
            program, on, name = _day_form()
            found = _days().channel_preview(program, on, name, _typed("from", program, on),
                                            _typed("to", program, on), request.form.get("channel", ""))
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(_shown_data(found, _shift_of(program, on)))

    @app.route("/day/break-advice", methods=["POST"])
    @login_required
    def day_break_advice():  # type: ignore[no-untyped-def]
        measure = request.form.get("measure", "")
        try:
            program, on, name = _day_form()
            found = _days().break_advice(program, on, name, _break_idx(), _typed("at", program, on),
                                         _measure_arg(measure, request.form.get("program", "")))
        except ValueError as exc:
            return _refused(exc, *_posted_day())
        return jsonify(_shown_data(found, _shift_of(program, on)))

    ctx.DAY_WRITES = DAY_WRITES
    ctx._back_to_day = _back_to_day
    ctx._date = _date
    ctx._days = _days
    ctx._measure_arg = _measure_arg
    ctx._merge_choice = _merge_choice
    ctx._merge_pick_for = _merge_pick_for
    ctx._own_zone = _own_zone
    ctx._pc_zone = _pc_zone
    ctx._still_editable = _still_editable
    ctx._window_moved = _window_moved
    ctx._with_lists = _with_lists
