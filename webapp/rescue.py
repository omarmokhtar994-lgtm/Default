# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AD: Rescue the day (owner, 2026-10-11: "group breaks and fail one interval down to 50% if that will rescue
other intervals ... maximum for 3 intervals not more ... in order to save other intervals but that doesn't mean that
all breaks should be only for those 3 intervals but mainly to bulk in them and rest to be distributed to achieve our
goal ... interval wise only not weighted volume"; answer 3: the 3 count the whole day, intervals already lost before
the press included; sample 02).

A CP-SAT model re-places the breaks that have not started, for people on shift and present, to get as many
intervals as it can to the week's interval target, every interval counted the same (interval compliance). It may
give up at most ``may_give_up`` intervals: a given-up interval falls below the target but never below 50% of its
demand (or below where it is now, if it is lower already); every other interval stays at the target or no worse than
now. Each break stays inside its shift, on a 5-minute step, clear of the person's away time and activities, in its
order, within the program's gaps (a gap already outside them may stay as it is; none is held across a cancelled
break), and no language or channel falls below its need (or below where it is now). In order, each keeping the
one before: the most intervals at the target, then the fewest given up, then the fewest breaks moved (and,
among those, the least moving): one solve, with weights that keep that order exactly.

The model counts on the floor in the page's own way (5-minute ticks; an interval is at the target when the page's
rounded figure is), but the figures the page shows come from the page itself (``DayBook.rescue_plan``)."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from .day import ABSENT, AUX, EXTRA_BREAKS, STEP, _across_cancel, _norm

LIMIT = 3  # intervals a day may give up, the ones already lost before the press included (owner, answer 3)
FLOOR = 0.5  # never below 50% of demand
SECONDS = 12.0  # one solve (RESCUE_ONESOLVE_AB.txt): days of up to 60 people finished proven best in 1.4 to 3.8 s
SEED, WORKERS = 9000, 4
PROBING: Optional[int] = 0  # cp_model_probing_level, by a pre-registered A/B (evidence/phase_ad/RESCUE_PROBING_AB.txt)


def least(per: int, ratio: float, required: float) -> int:
    """The fewest person-ticks in an interval of ``per`` ticks for the page to count ``ratio`` x ``required`` on the
    floor (the page compares its figure rounded to one decimal)."""
    goal = ratio * required - 1e-9
    f = max(0, int((goal - 0.2) * per))
    while round(f / per, 1) < goal:
        f += 1
    return f


def lost_so_far(cells: List[Dict[str, Any]], now: int, step: int) -> List[Dict[str, Any]]:
    """The intervals with demand already over at ``now`` (minutes) that missed the target (``at_target`` cells)."""
    return [c for c in cells if c["ok"] is False and c["t"] + step <= now]


def allowance(lost: List[Dict[str, Any]]) -> int:
    return max(0, LIMIT - len(lost))


def solve(view: Dict[str, Any], inputs: Dict[str, Any], target: float, now: Optional[int], may_give_up: int,
          seconds: float = SECONDS) -> Dict[str, Any]:
    """Moves {name, idx, kind, minutes, from, to}, the intervals given up (their minutes), and a status: "rescued",
    "no gain" (nothing more reaches the target within the rules) or "not solved" (no answer in the time); with the
    solver's status in ``solver`` (OPTIMAL proves it the best; FEASIBLE is the best found in the time). ``now`` is
    minutes past midnight today, or None for another day (nothing started, nothing over)."""
    started = time.time()
    step = view["interval"]
    per = step // STEP
    cells = view["cells"]
    slots = [x for c in cells for x in c["slots"]]
    interval_mode = view["measure"] == "interval"
    lo_gap, hi_gap = inputs.get("gap_min"), inputs.get("gap_max")
    first = 0 if now is None else (now // STEP + 1) * STEP  # a break moves to a time still ahead
    over = (lambda t: False) if now is None else (lambda t: t + step <= now)

    def free(seg: Dict[str, Any], t: int) -> bool:  # on the floor at t, breaks aside (as Fix breaks reads it)
        if not seg["start"] <= t < seg["end"]:
            return False
        if not (seg["billable"] and interval_mode) and seg["away"][0] <= t < seg["away"][1]:
            return False
        return not any(a["start"] <= t < a["end"] for a in seg.get("activities", [])
                       if a["kind"] == "VTO" or a["kind"] in EXTRA_BREAKS
                       or (a["kind"] in AUX and not (a.get("billable") and interval_mode)))

    def cover(seg: Dict[str, Any], s: int, minutes: int) -> List[int]:
        return [t // STEP for t in range(max(s, 0), min(s + minutes, 1440), STEP) if free(seg, t)]

    people = [(lane, seg) for lane in view["lanes"] for seg in lane["segments"]
              if seg["offset"] == 0 and seg["status"] not in ABSENT]
    moving = []  # (lane, seg, break, positions)
    for lane, seg in people:
        for b in seg["breaks"]:
            if now is not None and b["start"] <= now:
                continue  # started
            lo, hi = max(seg["start"], first), seg["end"] - b["minutes"]
            places = [s for s in range(lo + (-lo) % STEP, hi + 1, STEP)
                      if all(free(seg, t) for t in range(s, s + b["minutes"], STEP))]
            if b["start"] not in places:
                places = sorted(places + [b["start"]])
            if len(places) > 1:
                moving.append((lane, seg, b, places))
    base = list(slots)  # on the floor with every movable break taken off the day
    for lane, seg, b, _ in moving:
        for k in cover(seg, b["start"], b["minutes"]):
            base[k] += 1

    m = cp_model.CpModel()
    x: List[Dict[int, Any]] = []
    away: Dict[int, Dict[Any, int]] = {}  # interval -> {start variable: ticks of the interval it takes off the floor}
    worst: Dict[int, int] = {}  # interval -> the most ticks the movable breaks can take off it together
    start_hint: Dict[Any, int] = {}
    for j, (lane, seg, b, places) in enumerate(moving):
        x.append({s: m.NewBoolVar(f"b{j}_{s}") for s in places})
        m.AddExactlyOne(x[j].values())
        most: Dict[int, int] = {}
        for s, v in x[j].items():
            start_hint[v] = int(s == b["start"])
            here: Dict[int, int] = {}
            for k in cover(seg, s, b["minutes"]):
                here[k // per] = here.get(k // per, 0) + 1
            for i, n in here.items():
                away.setdefault(i, {})[v] = n
                most[i] = max(most.get(i, 0), n)
        for i, n in most.items():
            worst[i] = worst.get(i, 0) + n

    # intervals: at the target, given up, never worse otherwise. One floor variable per interval (person-ticks on
    # the floor), defined once; the conditions are on it alone.
    at_vars, given, base_at, before_at = [], [], 0, 0
    flag_hint: Dict[Any, int] = {}
    for i, c in enumerate(cells):
        if c["required"] <= 0 or over(c["t"]):
            continue
        ticks = range(i * per, (i + 1) * per)
        before = sum(slots[k] for k in ticks)
        need, half = least(per, target, c["required"]), least(per, FLOOR, c["required"])
        before_at += before >= need
        row = away.get(i)
        if not row:
            base_at += before >= need
            continue
        top = sum(base[k] for k in ticks)
        f = m.NewIntVar(max(0, top - worst[i]), top, f"floor{i}")
        m.Add(f == top - cp_model.LinearExpr.WeightedSum(list(row), list(row.values())))
        flag_hint[f] = before
        m.Add(f >= min(before, half))  # never below 50% (or below where it is now, if lower)
        if min(before, need) > min(before, half):  # giving it up allows something
            gone = m.NewBoolVar(f"gone{i}")
            m.Add(f >= min(before, need)).OnlyEnforceIf(gone.Not())
            given.append((gone, c["t"]))
            flag_hint[gone] = 0
        if top >= need:  # it can reach the target
            at = m.NewBoolVar(f"at{i}")
            m.Add(f >= need).OnlyEnforceIf(at)
            at_vars.append(at)
            flag_hint[at] = int(before >= need)
    m.Add(sum(g for g, _ in given) <= max(0, may_give_up))

    # languages (as Fix breaks keeps them): per tick, eligible people on the floor never below min(now, minimum)
    lang_of = {lane["name"]: _norm(lane["language"]) for lane in view["lanes"]}
    for rule in view["languages"]:
        inside = {c["t"] for c in rule["cells"] if c["count"] is not None}
        eligible = set(rule["eligible"])
        mine = [(j, item) for j, item in enumerate(moving) if lang_of[item[0]["name"]] in eligible]
        if not mine or not inside:
            continue
        now_on = [0] * len(slots)
        for lane in view["lanes"]:
            if lang_of[lane["name"]] not in eligible:
                continue
            for seg in lane["segments"]:
                if seg["status"] in ABSENT:
                    continue
                for k in range(len(slots)):
                    t = k * STEP
                    if free(seg, t) and not any(b["start"] <= t < b["start"] + b["minutes"] for b in seg["breaks"]):
                        now_on[k] += 1
        takers: Dict[int, List[Any]] = {}
        breaks_at: Dict[int, set] = {}  # tick -> the breaks that could take an eligible person away then
        back: Dict[int, int] = {}
        for j, (lane, seg, b, places) in mine:
            for k in cover(seg, b["start"], b["minutes"]):
                back[k] = back.get(k, 0) + 1
            for s, v in x[j].items():
                for k in cover(seg, s, b["minutes"]):
                    takers.setdefault(k, []).append(v)
                    breaks_at.setdefault(k, set()).add(j)
        least_on = max(rule["minimum"], 1)
        for k, vs in takers.items():
            keep = min(now_on[k], least_on)
            if k * STEP - (k * STEP) % step in inside and now_on[k] + back.get(k, 0) - len(breaks_at[k]) < keep:
                m.Add(now_on[k] + back.get(k, 0) - sum(vs) >= keep)  # only where the breaks could breach it

    # channels (Phase V): never a channel or its language below its need, or below where it is now
    hold = (view.get("channels") or {}).get("hold")
    if hold is not None:
        counters: Dict[Tuple[Any, int], Dict[str, Any]] = {}
        known: Dict[Tuple[str, int], List[Tuple[Tuple[str, Any], float]]] = {}

        def limits(name: str, k: int):
            if (name, k) not in known:
                known[(name, k)] = hold.limits(name, k)
            return known[(name, k)]

        for j, (lane, seg, b, places) in enumerate(moving):
            name = lane["name"]
            for k in cover(seg, b["start"], b["minutes"]):
                for key, need in limits(name, k):
                    counters.setdefault((key, k), {"need": need, "back": 0, "terms": [], "who": set()})["back"] += 1
            for s, v in x[j].items():
                for k in cover(seg, s, b["minutes"]):
                    for key, need in limits(name, k):
                        c = counters.setdefault((key, k), {"need": need, "back": 0, "terms": [], "who": set()})
                        c["terms"].append(v)
                        c["who"].add(j)
        for (key, k), c in counters.items():
            now_count = hold.current(key, k)
            keep = min(now_count, c["need"])
            if c["terms"] and now_count + c["back"] - len(c["who"]) < keep - 1e-9:  # only where it could breach
                m.Add(int(round((now_count + c["back"]) * 100)) - 100 * sum(c["terms"]) >= int(round(keep * 100)))

    # gaps between a person's breaks, in the order they are in now (so none can come to overlap another)
    index = {id(item[2]): j for j, item in enumerate(moving)}

    def start_of(seg, b):
        j = index.get(id(b))
        return (sum(s * v for s, v in x[j].items()), True) if j is not None else (b["start"], False)

    for lane, seg in people:
        ordered = sorted(seg["breaks"], key=lambda b: (b["start"], b["idx"]))
        for p, q in zip(ordered, ordered[1:]):
            sp, vp = start_of(seg, p)
            sq, vq = start_of(seg, q)
            if not (vp or vq):
                continue
            gap_now = q["start"] - p["start"] - p["minutes"]
            m.Add(sq - sp - p["minutes"] >= min(lo_gap or 0, gap_now))
            if hi_gap is not None and not _across_cancel(seg, p["idx"], q["idx"]):
                m.Add(sq - sp - p["minutes"] <= max(hi_gap, gap_now))

    def hint(solver=None):
        m.ClearHints()
        for v, value in list(start_hint.items()) + list(flag_hint.items()):
            m.AddHint(v, solver.Value(v) if solver else value)

    def run(seconds: float):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = seconds
        solver.parameters.num_workers = WORKERS
        solver.parameters.random_seed = SEED
        if PROBING is not None:
            solver.parameters.cp_model_probing_level = PROBING
        status = solver.Solve(m)
        if status == cp_model.MODEL_INVALID:  # a fault in this module, never "no rescue"
            raise RuntimeError(f"The rescue model is invalid: {m.Validate()}")
        return solver, status

    out: Dict[str, Any] = {"moves": [], "given_up": [], "status": "no gain", "before_at": before_at,
                           "after_at": before_at, "moving": len(moving), "solver": ""}

    def done(**more):
        out.update(more, seconds=round(time.time() - started, 1))
        return out

    if not at_vars:
        return done()
    # the most at the target, then the fewest given up, the fewest breaks moved, and among those the least moving (in
    # 5-minute steps): each weight is larger than everything after it can add up to, so one objective keeps the order
    steps = [{s: abs(s - item[2]["start"]) // STEP for s in x[j]} for j, item in enumerate(moving)]
    per_move = 1 + sum(max(d.values()) for d in steps)
    per_given = 1 + per_move * (len(moving) + 1)
    rest = (per_given * sum(g for g, _ in given)
            + sum(per_move * (1 - x[j][item[2]["start"]]) + sum(d * x[j][s] for s, d in steps[j].items() if d)
                  for j, item in enumerate(moving)))
    hint()
    m.Minimize(rest - (1 + per_given * (len(given) + 1)) * sum(at_vars))  # the most at the target above all the rest
    solver, status = run(seconds)
    out["solver"] = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return done(status="not solved")
    if base_at + sum(solver.Value(a) for a in at_vars) <= before_at:
        return done()
    to = {}
    for j, (lane, seg, b, places) in enumerate(moving):
        to[j] = next(s for s, v in x[j].items() if solver.Value(v))
        if to[j] != b["start"]:
            out["moves"].append({"name": lane["name"], "idx": b["idx"], "kind": b["kind"], "minutes": b["minutes"],
                                 "from": b["start"], "to": to[j]})
    # what the kept answer does, counted from the starts themselves (not from the stage flags)
    final = list(base)
    for j, (lane, seg, b, places) in enumerate(moving):
        for k in cover(seg, to[j], b["minutes"]):
            final[k] -= 1
    after_at, given_up = base_at, []
    for i, c in enumerate(cells):
        if c["required"] <= 0 or over(c["t"]):
            continue
        ticks = range(i * per, (i + 1) * per)
        if i not in away:
            continue
        before = sum(slots[k] for k in ticks)
        need = least(per, target, c["required"])
        f = sum(final[k] for k in ticks)
        after_at += f >= need
        if f < min(before, need):
            given_up.append(c["t"])
    return done(status="rescued", given_up=given_up, after_at=after_at)
