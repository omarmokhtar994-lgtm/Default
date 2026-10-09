# © 2026 Omar Mokhtar. All rights reserved.
"""Phase V: one day's channels, and the breaks it may move, planned with CP-SAT on the website (owner, 2026-10-09:
"next to assign each associate for a while for channel based on the requirements ... it can automatically plan same
as for breaks to cover that as much as possible", "this needs to be connected somehow with breaks as well").

The schedule's shifts never change. In 15-minute slots, each person on shift is either on a break or on one channel
they can work; in all-channels times they cover every channel they can work at once. The breaks stay inside the
engine's break rules (windows, edge margin, gaps, at most N at once); the schedule's breaks move only when that
helps (each move costs), breaks typed on the page never move, and empty breaks (a ready schedule) are placed.

Costs, from the most to the least important:
  language minimums per channel                 200 per person-slot short (Strict: above every channel)
  channels in the workbook's order              Balanced 100 / 60 / 30 per person-slot short; Strict makes each
                                                channel outweigh everything the next ones down could lose that day
  a run on a channel longer than its maximum    40 per slot window over (a wish: someone who works only Phone
                                                cannot always follow it, and is then reported)
  a moved break 5, a channel change mid-stretch 2 (a change at a break is free), fair spread 1 per slot

``score_day`` recounts any plan from its blocks and breaks alone and checks every break with the break planner's
own row check: it judges the planner in the tests and gives the figures the pages show."""
from __future__ import annotations

import time
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

from .break_plan import check_row, hm
from .channels import QUARTER, blended_at, inside

LANGUAGE, BALANCED, LONG, MOVE, SWITCH, FAIR = 200, (100, 60, 30), 40, 5, 2, 1
# Two stages, measured on a 16- and a 40-person day (Phase V task 5's ledger): the breaks kept (the best plan is
# proven in 4 to 11 s), then the breaks free to move, starting from that plan, for 10 s. A deterministic search
# (interleaved, or one worker) gave the same plan twice but worse plans, or none in time once breaks may move.
KEPT = {"num_workers": 4, "max_time_in_seconds": 12.0, "random_seed": 9000}
MOVING = {"num_workers": 4, "max_time_in_seconds": 10.0, "random_seed": 9000}


class NoPlan(ValueError):
    """The day cannot be planned (no time inside the break rules for a break, or no answer in the time allowed)."""


def counts_for(language: str, setup_rows: Iterable[Dict[str, Any]]) -> Set[str]:
    """The languages a person speaking ``language`` counts for: their Language Setup row's "can cover languages"
    (which holds its own), or just their own when the language has no row."""
    me = (language or "").strip().casefold()
    row = next((r for r in setup_rows if r["name"].strip().casefold() == me), None)
    return set(row["covers"]) if row else {me}


def need_at(setup: Dict[str, Any], channel: str, day: int, t: int) -> float:
    """People needed on ``channel`` at minute ``t`` of ``day`` (past 1440: the next day's grid)."""
    d, m = (day + t // 1440) % 7, t % 1440
    return float(setup["need"].get(channel, {}).get(d, {}).get(m - m % setup["step"], 0.0) or 0.0)


def in_play(setup: Dict[str, Any]) -> List[str]:
    return [c for c in "PCE" if c in setup["need"] or (c == "E" and setup["email_mode"] == "hours")]


def allowed(setup: Dict[str, Any], day: int, person: Dict[str, Any], t: int) -> List[str]:
    """The channels ``person`` may be on at ``t``: those they work that the day needs; Email Hours only inside the
    day's window (unless Email is all they work)."""
    playing = in_play(setup)
    mine = [c for c in "PCE" if c in person["skills"] and c in playing] or [c for c in "PCE" if c in person["skills"]]
    if setup["email_mode"] == "hours" and "E" in mine and len(mine) > 1:
        window = setup["email_hours"][day]
        if not (t < 1440 and window["start"] <= t < window["end"]):
            mine.remove("E")
    return mine


def _candidates(rules: Dict[str, Any], person: Dict[str, Any], kind: str, minutes: int) -> List[int]:
    """Break starts inside the rules for this kind (window, edge margin), on quarter hours."""
    lo, hi = person["start"], person["end"]
    margin = rules.get("edge_margin") or 0
    first, last = lo + margin, hi - margin - minutes
    window = (rules.get("windows") or {}).get(kind.casefold()) or {}
    if window.get("earliest") is not None:
        first = max(first, lo + window["earliest"])
    if window.get("latest") is not None:
        last = min(last, lo + window["latest"])
    first += -first % QUARTER
    return list(range(first, last + 1, QUARTER))


def plan_day(people: List[Dict[str, Any]], setup: Dict[str, Any], rules: Dict[str, Any], day: int,
             carry: Optional[Dict[str, Dict[str, int]]] = None, move_breaks: bool = True,
             locked: FrozenSet[Tuple[str, int]] = frozenset(),
             before: Optional[Dict[str, Dict[int, int]]] = None) -> Dict[str, Any]:
    """The day's plan: ``blocks`` (name -> [(start, end, letter)], A in all-channels times), ``breaks`` (name ->
    starts, in the people's break order), ``moved`` ([(name, kind, old, new)]), ``status`` and ``metrics`` (the
    model's own shortfall in hours). ``people``: name, language, start, end (minutes; past 1440 for a shift
    crossing midnight), breaks [(kind, start or None, minutes)], skills (letters), counts_for (languages).
    ``carry``: minutes per channel each person had earlier this week (fair spread). ``locked``: (name, break index)
    typed on the page. ``before``: people per channel and slot from the previous day's overnight shifts."""
    started = time.time()
    first = _solve(people, setup, rules, day, carry or {}, False, locked, before or {}, solver_settings=KEPT)
    first["note"] = ""
    movable = any(start is not None and (p["name"], k) not in locked
                  for p in people for k, (_, start, _) in enumerate(p["breaks"]))
    if not move_breaks or not movable:
        return first
    try:
        second = _solve(people, setup, rules, day, carry or {}, True, locked, before or {}, hint=first,
                        solver_settings=MOVING)
    except NoPlan as exc:
        first["note"] = f"Breaks were kept as they are. {exc}"
        first["seconds"] = round(time.time() - started, 1)
        return first
    second["note"] = ""
    second["seconds"] = round(time.time() - started, 1)
    return second


def _solve(people, setup, rules, day, carry, move_breaks, locked, before, hint=None,
           solver_settings=None) -> Dict[str, Any]:
    started = time.time()
    m = cp_model.CpModel()
    order = list(setup["rules"]["order"])
    strict = setup["rules"]["strict"]
    block = max(1, setup["rules"]["min_block"] // QUARTER)
    cost: List[Any] = []
    x: Dict[Tuple[str, int, str], Any] = {}
    off: Dict[Tuple[str, int], Any] = {}  # on a break in that slot
    picks: Dict[Tuple[str, int], Dict[int, Any]] = {}
    fixed_at: Dict[int, int] = {}
    slots: Dict[str, List[int]] = {}
    for p in people:
        name, lo, hi = p["name"], p["start"], p["end"]
        if lo % QUARTER or hi % QUARTER:
            raise NoPlan(f"{name}'s shift ({hm(lo)} to {hm(hi)}) does not start and end on quarter hours; channels "
                         "are planned in 15-minute steps.")
        slots[name] = list(range(lo, hi, QUARTER))
        starts = []
        for k, (kind, start, minutes) in enumerate(p["breaks"]):
            fixed = start is not None and (not move_breaks or (name, k) in locked)
            cands = [start] if fixed else sorted(set(_candidates(rules, p, kind, minutes)) | ({start} - {None}))
            if not cands:
                raise NoPlan(f"{name}'s {kind} has no time inside the break rules.")
            picks[name, k] = {c: m.NewBoolVar(f"b{name}{k}{c}") for c in cands}
            m.AddExactlyOne(picks[name, k].values())
            if start is not None and not fixed:
                cost.append(MOVE * (1 - picks[name, k][start]))
                m.AddHint(picks[name, k][start], 1)
            if fixed:
                for t in range(start - start % QUARTER, start + minutes, QUARTER):
                    fixed_at[t] = fixed_at.get(t, 0) + 1
            s = m.NewIntVar(min(cands), max(cands), "")
            m.Add(s == sum(c * v for c, v in picks[name, k].items()))
            starts.append((s, minutes, fixed))
        for (s1, m1, f1), (s2, _, f2) in zip(starts, starts[1:]):
            if f1 and f2:
                continue  # both as they are: the row check reports them
            m.Add(s2 - (s1 + m1) >= (rules.get("min_gap") or 0))
            if rules.get("max_gap"):
                m.Add(s2 - (s1 + m1) <= rules["max_gap"])
        for t in slots[name]:
            cover = [v for k, (kind, _, minutes) in enumerate(p["breaks"]) for c, v in picks[name, k].items()
                     if c < t + QUARTER and t < c + minutes]
            if cover:
                off[name, t] = cover[0] if len(cover) == 1 else m.NewBoolVar("")
                if len(cover) > 1:
                    m.AddMaxEquality(off[name, t], cover)
            if blended_at(setup, day, t):
                continue
            chans = allowed(setup, day, p, t)
            for c in chans:
                x[name, t, c] = m.NewBoolVar(f"x{name}{t}{c}")
            m.Add(sum(x[name, t, c] for c in chans) + (off[name, t] if (name, t) in off else 0) == 1)
    cap = rules.get("max_concurrent") or 0
    every = sorted({t for ts in slots.values() for t in ts})
    if cap:
        for t in every:
            here = [off[n, t] for n in slots if (n, t) in off]
            if len(here) > cap:
                m.Add(sum(here) <= max(cap, fixed_at.get(t, 0)))
    # the blocks: no block shorter than the minimum unless a break, the shift end, all-channels time or the email
    # window cuts it; a long run is a wish; a change of channel mid-stretch costs, at a break it is free
    longs: Dict[str, List[Any]] = {}
    for p in people:
        name, ts = p["name"], slots[p["name"]]
        for c in "PCE":
            if not any((name, t, c) in x for t in ts):
                continue
            for i in range(len(ts)):
                for length in range(1, block):
                    run, j = ts[i:i + length], i + length
                    if len(run) < length or j >= len(ts) or any((name, t, c) not in x for t in run):
                        break
                    nxt = ts[j]
                    if (name, nxt, c) not in x:
                        break  # cut: a break-free stretch cannot go on with this channel here
                    lits = [x[name, ts[i - 1], c]] if i > 0 and (name, ts[i - 1], c) in x else []
                    lits += [x[name, t, c].Not() for t in run] + [x[name, nxt, c]]
                    if (name, nxt) in off:
                        lits.append(off[name, nxt])
                    m.AddBoolOr(lits)
            most = (setup["rules"]["max_run"].get(c) or 0) // QUARTER
            if most:
                for i in range(len(ts) - most):
                    window = ts[i:i + most + 1]
                    if all((name, t, c) in x for t in window):
                        over = m.NewBoolVar("")
                        m.Add(sum(x[name, t, c] for t in window) <= most + over)
                        cost.append(LONG * over)
                        longs.setdefault(name, []).append(over)
        for prev, t in zip(ts, ts[1:]):
            for c in "PCE":
                if (name, t, c) in x:
                    change = m.NewBoolVar("")
                    m.Add(change >= x[name, t, c] - (x[name, prev, c] if (name, prev, c) in x else 0)
                          - (off[name, prev] if (name, prev) in off else 0)
                          - (1 if blended_at(setup, day, prev) else 0))
                    cost.append(SWITCH * change)
        if setup["rules"].get("fair") and carry.get(name):
            ranks = {c: r for r, c in enumerate(sorted("PCE", key=lambda c: (carry[name].get(c, 0), c)))}
            cost += [FAIR * ranks[c] * x[name, t, c] for t in ts for c in "PCE" if (name, t, c) in x and ranks[c]]
    # coverage
    def cover(c: str, t: int, who: Optional[Set[str]] = None) -> List[Any]:
        found = []
        for p in people:
            if t not in slots[p["name"]] or (who is not None and not (p["counts_for"] & who)):
                continue
            if (p["name"], t, c) in x:
                found.append(x[p["name"], t, c])
            elif blended_at(setup, day, t) and c in p["skills"]:
                found.append(1 - off[p["name"], t] if (p["name"], t) in off else 1)
        return found

    shorts: Dict[str, List[Any]] = {c: [] for c in setup["need"]}
    worst: Dict[str, int] = {}
    for c in setup["need"]:
        for t in every:
            need = int(round(need_at(setup, c, day, t)))
            if need <= 0:
                continue
            short = m.NewIntVar(0, need, "")
            m.AddMaxEquality(short, [need - sum(cover(c, t)) - (before.get(c, {}).get(t, 0)), 0])
            shorts[c].append(short)
            worst[c] = worst.get(c, 0) + need
    email: List[Any] = []
    if setup["email_mode"] == "hours":
        target = setup["email_hours"][day]
        lo, hi = target["start"], min(target["end"], 1440)
        placed = [x[n, t, "E"] for n in slots for t in slots[n] if lo <= t < hi and (n, t, "E") in x]
        for lang, hours in [(None, target["hours"])] + list(target["languages"].items()):
            want = int(round(hours * 60 / QUARTER))
            if want <= 0:
                continue
            mine = placed if lang is None else [x[p["name"], t, "E"] for p in people if lang.casefold() in p["counts_for"]
                                                for t in slots[p["name"]] if lo <= t < hi and (p["name"], t, "E") in x]
            short = m.NewIntVar(0, want, "")
            m.AddMaxEquality(short, [want - sum(mine), 0])
            email.append(short)
            worst["E"] = worst.get("E", 0) + want
    lang_short: List[Any] = []
    for rule in setup["languages"]:
        if not rule["active"] or rule["minimum"] <= 0:
            continue
        for t in every:
            if inside(rule["days"], rule["start"], rule["end"], (day + t // 1440) % 7, t % 1440):
                short = m.NewIntVar(0, rule["minimum"], "")
                m.AddMaxEquality(short, [rule["minimum"] - sum(cover(rule["channel"], t, {rule["language"].casefold()})),
                                         0])
                lang_short.append(short)
    weight = _weights(order, strict, worst)
    for c, items in shorts.items():
        cost += [weight[c] * s for s in items]
    cost += [weight["E"] * s for s in email]
    language = (sum(weight[c] * worst.get(c, 0) for c in "PCE") + 1) if strict else LANGUAGE
    cost += [language * s for s in lang_short]
    if hint:  # a whole earlier plan as the starting point (in place of the kept breaks' hints)
        m.ClearHints()
        for (name, k), choices in picks.items():
            for c, v in choices.items():
                m.AddHint(v, int(hint["breaks"].get(name, [None] * (k + 1))[k] == c))
        given = {(n, t): letter for n, runs in hint["blocks"].items() for a, b, letter in runs
                 for t in range(a, b, QUARTER)}
        for (name, t, c), v in x.items():
            m.AddHint(v, int(given.get((name, t)) == c))
    m.Minimize(sum(cost))
    solver = cp_model.CpSolver()
    for key, value in (solver_settings or MOVING).items():
        setattr(solver.parameters, key, value)
    status = solver.Solve(m)
    if status == cp_model.MODEL_INVALID:  # a fault in this module, never "no plan"
        raise RuntimeError(f"The channel plan model is invalid: {m.Validate()}")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if status == cp_model.INFEASIBLE:
            raise NoPlan("The breaks cannot all fit their rules on this day with channels planned around them.")
        raise NoPlan("No plan was found in the time allowed. Try again, or keep the breaks as they are.")
    out = {"blocks": {}, "breaks": {}, "moved": [], "status": solver.StatusName(status),
           "seconds": round(time.time() - started, 1)}
    for p in people:
        name = p["name"]
        chosen = [next(c for c, v in picks[name, k].items() if solver.Value(v)) for k in range(len(p["breaks"]))]
        out["breaks"][name] = chosen
        out["moved"] += [(name, kind, old, new) for (kind, old, _), new in zip(p["breaks"], chosen)
                         if old is not None and old != new]
        runs: List[Tuple[int, int, str]] = []
        for t in slots[name]:
            if (name, t) in off and solver.Value(off[name, t]):
                continue
            letter = "A" if blended_at(setup, day, t) else next(c for c in "PCE" if (name, t, c) in x
                                                                and solver.Value(x[name, t, c]))
            if runs and runs[-1][1] == t and runs[-1][2] == letter:
                runs[-1] = (runs[-1][0], t + QUARTER, letter)
            else:
                runs.append((t, t + QUARTER, letter))
        out["blocks"][name] = runs
    out["metrics"] = {"short": {c: sum(solver.Value(s) for s in items) * QUARTER / 60 for c, items in shorts.items()},
                      "language_short": sum(solver.Value(s) for s in lang_short) * QUARTER / 60,
                      "long": {n: sum(solver.Value(v) for v in vs) for n, vs in longs.items()
                               if any(solver.Value(v) for v in vs)}}
    return out


def _weights(order: List[str], strict: bool, worst: Dict[str, int]) -> Dict[str, int]:
    """Per person-slot short: Balanced 100 / 60 / 30 in the workbook's order; Strict makes each channel outweigh the
    most the channels after it could lose that day."""
    if not strict:
        return {c: w for c, w in zip(order, BALANCED)}
    weight: Dict[str, int] = {}
    below = 0
    for c in reversed(order):
        weight[c] = max(BALANCED[-1], below + 1)
        below += weight[c] * worst.get(c, 0)
    return weight


def score_day(people: List[Dict[str, Any]], plan: Dict[str, Any], setup: Dict[str, Any], day: int,
              rules: Dict[str, Any]) -> Dict[str, Any]:
    """A plan recounted from its blocks and breaks alone: hours short per channel and per language minimum, email
    hours placed, channel changes mid-stretch, runs longer than a channel's maximum (per person), and every rule it
    breaks in plain words (``problems``)."""
    problems: List[str] = []
    at: Dict[Tuple[str, int], str] = {}
    block = max(1, setup["rules"]["min_block"] // QUARTER)
    for p in people:
        name, lo, hi = p["name"], p["start"], p["end"]
        starts = plan["breaks"].get(name, [])
        if p["breaks"]:
            level, text = check_row(rules, f"{hm(lo)} - {hm(hi)}", starts)
            if level != "ok":
                problems.append(f"{name}: {text}")
        for (kind, _, minutes), s in zip(p["breaks"], starts):
            for t in range(s - s % QUARTER, s + minutes, QUARTER):
                at[name, t] = "B"
        for start, end, letter in plan["blocks"].get(name, []):
            for t in range(start, end, QUARTER):
                if (name, t) in at:
                    problems.append(f"{name}: two things at {hm(t)}.")
                elif not lo <= t < hi:
                    problems.append(f"{name}: {letter} at {hm(t)} is outside the shift.")
                elif (letter == "A") != blended_at(setup, day, t):
                    problems.append(f"{name}: {letter} at {hm(t)} does not match the all-channels times.")
                elif letter != "A" and letter not in allowed(setup, day, p, t):
                    problems.append(f"{name}: {letter} at {hm(t)} is not a channel they may work then.")
                at[name, t] = letter
        for t in range(lo, hi, QUARTER):
            if (name, t) not in at:
                problems.append(f"{name}: nothing planned at {hm(t)}.")
    cap = rules.get("max_concurrent") or 0
    every = sorted({t for p in people for t in range(p["start"], p["end"], QUARTER)})
    for t in every:
        resting = sum(1 for p in people if at.get((p["name"], t)) == "B")
        if cap and resting > cap:
            problems.append(f"{resting} people on a break at {hm(t)}; at most {cap}.")
    switches, long_runs = 0, {}
    for p in people:
        name, ts = p["name"], list(range(p["start"], p["end"], QUARTER))
        runs: List[Tuple[str, int, int]] = []
        for i, t in enumerate(ts):
            letter = at.get((name, t))
            if runs and runs[-1][0] == letter and runs[-1][2] == i:
                runs[-1] = (letter, runs[-1][1], i + 1)
            else:
                runs.append((letter, i, i + 1))
        for (a, _, _), (b, _, _) in zip(runs, runs[1:]):
            switches += int(a not in ("A", "B") and b not in ("A", "B"))
        for k, (letter, i, j) in enumerate(runs):
            if letter in ("A", "B", None):
                continue
            nxt = ts[j] if j < len(ts) else None
            cut = nxt is None or at.get((name, nxt)) in ("A", "B") or letter not in allowed(setup, day, p, nxt)
            if j - i < block and not cut:
                problems.append(f"{name}: {letter} from {hm(ts[i])} lasts {(j - i) * QUARTER} minutes, under the "
                                f"{block * QUARTER}-minute minimum.")
            most = (setup["rules"]["max_run"].get(letter) or 0) // QUARTER
            if most and j - i > most:
                long_runs[name] = long_runs.get(name, 0) + 1
    short = {c: 0.0 for c in setup["need"]}
    for c in setup["need"]:
        for t in every:
            have = sum(1 for p in people if at.get((p["name"], t)) == c
                       or (at.get((p["name"], t)) == "A" and c in p["skills"]))
            short[c] += max(0.0, round(need_at(setup, c, day, t)) - have) * QUARTER / 60
    language_short = 0.0
    for rule in setup["languages"]:
        if not rule["active"]:
            continue
        for t in every:
            if inside(rule["days"], rule["start"], rule["end"], (day + t // 1440) % 7, t % 1440):
                have = sum(1 for p in people if rule["language"].casefold() in p["counts_for"]
                           and (at.get((p["name"], t)) == rule["channel"]
                                or (at.get((p["name"], t)) == "A" and rule["channel"] in p["skills"])))
                language_short += max(0, rule["minimum"] - have) * QUARTER / 60
    if setup["email_mode"] == "hours":
        target = setup["email_hours"][day]
        email = sum(1 for p in people for t in every if at.get((p["name"], t)) == "E"
                    and target["start"] <= t < min(target["end"], 1440)) * QUARTER / 60
    else:
        email = sum(1 for p in people for t in every if at.get((p["name"], t)) == "E") * QUARTER / 60
    return {"short": short, "language_short": language_short, "email": email, "switches": switches,
            "long": long_runs, "problems": problems}
