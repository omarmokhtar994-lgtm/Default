#!/usr/bin/env python3
"""Public benchmark: the multi-skill shift design instances of Bonutti, Ceschia,
De Cesco, Musliu & Schaerf, "Modeling and solving a real-life multi-skill shift
design problem", Annals of Operations Research 252(2):365-382, 2017.

Source (instances, best and proven-optimal solutions, the authors' C++
validator): https://bitbucket.org/satt/shift-design (commit e3d4bf6). The two
benchmark hosts NIGHT_14 wanted (schedulingbenchmarks.org, TU Wien) are still
blocked by the network policy; this set comes from the same research group and
is the closest public match to a call-centre week: 15-minute requirements over
7 days, shift types with start/length windows, one break per shift with
placement margins, requirements counted net of breaks, cyclic week.

Three subcommands, nothing hidden:

  build  translate R-instances into engine workbooks, one per skill
  bound  independent exact upper bound in the engine's metric (CP-SAT, no
         engine code), cyclic week
  score  read the engine's published workbook, rescore it cyclically from the
         Schedule and Break Schedule sheets alone, and write the benchmark's
         own solution format so the authors' validator can score it too

Translation, stated so nothing is hidden:

  * each skill is its own engine case. In the benchmark every shift is staffed
    per skill and the requirement is per skill, so the instance separates
    exactly into one single-skill problem per skill;
  * demand = the requirement in whole people per 15-minute slot, shrinkage 0,
    Target 100%: a slot is "hit" exactly when on-floor heads >= requirement;
    a 0 requirement is left blank (not counted) and staffing there is allowed;
  * shift library = every (start, length) of the instance's shift types on a
    30-minute grid inside the type's windows. Every shift of the published
    optimum is checked to be in it. Starts at 24:00 are next-day shifts and
    are left out (the published optima never use them);
  * breaks: one 60-minute break; the type's minimum distances from shift start
    and end become Break Edge Margin / Lunch Earliest Minutes From Shift Start.
    The engine has one break rule per workbook, so only instances whose used
    shift types share one rule are translated: R1, R5, R6, R7 (morning,
    afternoon, night: 60 minutes, 120 from each edge) and R10 (long: 60
    minutes, 180 from start, 60 from end). R1/R7's short types (30-minute
    break, 60-minute margins) and R10's short type (no break) are left out:
    the published optimum uses none of them. R2, R3, R4, R8, R9 need two break
    rules at once and are not translated;
  * roster: the engine plans fixed weekly tours (5 days, 2 adjacent OFF days,
    12h rest, at most 2 different shifts). The benchmark has no tours and no
    roster: it sizes daily shift counts freely. The roster per skill is the
    smallest 5-day roster that can supply the published optimum's duties,
    ceil(duties / 5);
  * week: the benchmark's week is cyclic (Saturday's night shifts cover
    Sunday morning). The engine's week takes last Saturday's shifts as input;
    they are the published optimum's own Saturday night shifts (steady state),
    as in the Union Airways translation. Scoring is done cyclically on the
    engine's own week, exactly as the authors' validator does it.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_synthetic_suite as S  # noqa: E402

DAYS = 7
SLOTS = 96  # 15-minute slots per day
WEEK = DAYS * SLOTS
SOURCE = ("Bonutti, Ceschia, De Cesco, Musliu & Schaerf, Annals of OR 252(2):365-382 (2017); "
          "https://bitbucket.org/satt/shift-design @ e3d4bf6")

# Instance -> shift types translated (see the module docstring for why).
TRANSLATED = {"R1": ("M", "A", "N"), "R5": ("M", "A", "N"), "R6": ("M", "A", "N"),
              "R7": ("M", "A", "N"), "R10": ("L",)}
NOT_TRANSLATED = {
    "R2": "optimum uses Morning-Short (30-minute break, 60-minute margins) beside 60-minute/120 types",
    "R3": "optimum uses Afternoon-Short (30/60) beside 60/120 types",
    "R4": "optimum uses Afternoon-Short (30/60) beside 60/120 types",
    "R8": "optimum uses Afternoon-Short (30/60) beside 60/120 types",
    "R9": "optimum uses no-break Short shifts beside a 60-minute Long type with its own margins",
}


def tmin(text: str) -> int:
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def parse_instance(path: Path) -> Dict[str, Any]:
    """The authors' format, read the way sdb_validator.cc reads it."""
    lines = [ln.strip() for ln in path.read_text().splitlines()]
    gran = int(lines[0].split()[1])
    days = int(lines[1].split()[1])
    skills = int(lines[2].split()[1])
    assert gran == 15 and days == 7, (path, gran, days)
    n_types = int(next(ln for ln in lines if ln.startswith("NumberOfShiftTemplates")).split()[1])
    i = next(k for k, ln in enumerate(lines) if ln.startswith("NumberOfShiftTemplates")) + 1
    types = {}
    while len(types) < n_types:
        tok = lines[i].split()
        i += 1
        if not tok:
            continue
        t = {"short": tok[0], "name": tok[1], "min_start": tmin(tok[2]), "max_start": tmin(tok[3]),
             "min_len": int(tok[5]), "max_len": int(tok[6]), "grid": int(tok[7])}
        assert tok[4] == "*", ("max stop not supported", tok)
        if tok[8] == "Break":
            t.update(brk=int(tok[9]), brk_from=tok[10], brk_to=tok[11],
                     off_start=int(tok[12]), off_end=int(tok[13]), days=tok[14])
            assert t["brk_from"] == "*" and t["brk_to"] == "*", ("break clock window not supported", tok)
        else:
            t.update(brk=0, off_start=0, off_end=0, days=tok[9])
        assert t["days"] == "*", ("day availability not supported", tok)
        types[t["short"]] = t
    req = [[[0] * SLOTS for _ in range(DAYS)] for _ in range(skills)]
    started = False
    for ln in lines[i:]:
        if ln.startswith("Requirements"):
            started = True
            continue
        if not started or not ln:
            continue
        m = re.match(r"(\d\d:\d\d)\s*/\s*(\d\d:\d\d)\s+(.*)$", ln)
        a, b = tmin(m.group(1)) // 15, tmin(m.group(2)) // 15
        cells = m.group(3).split()
        assert len(cells) == DAYS, ln
        for d, cell in enumerate(cells):
            vals = [int(v) for v in cell.split("/")]
            assert len(vals) == skills, ln
            for sk in range(skills):
                for p in range(a, b if b > a else SLOTS):
                    req[sk][d][p] = vals[sk]
    return {"id": path.stem, "skills": skills, "types": types, "req": req}


SOL_RE = re.compile(r"^(\S+)\s*\(\s*(\S+)\s*\)\s*(\d\d:\d\d)-(\d\d:\d\d)\*?\s+(\d+)\s+"
                    r"\((?:break at (\d+:\d\d)--(\d+:\d\d)|no break)\)\s+(.*)\[.*\]\s*$")


def parse_solution(path: Path, skills: int) -> List[Dict[str, Any]]:
    out = []
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = SOL_RE.match(ln)
        assert m, ln
        counts = [[int(x) for x in c.strip().split("/")] for c in m.group(8).strip().rstrip(",").split(",")]
        assert len(counts) == DAYS and all(len(c) == skills for c in counts), ln
        out.append({"type_name": m.group(2), "start": tmin(m.group(3)), "len": int(m.group(5)),
                    "brk_at": tmin(m.group(6)) if m.group(6) else None, "counts": counts})
    return out


def shift_library(inst: Dict[str, Any], keep: Tuple[str, ...]) -> List[Dict[str, Any]]:
    lib = []
    for short in keep:
        t = inst["types"][short]
        for start in range(t["min_start"], t["max_start"] + 1, 30):
            if start >= 1440:
                continue
            for length in range(t["min_len"], t["max_len"] + 1, 30 if t["grid"] <= 30 else t["grid"]):
                lib.append({"type": short, "name": t["name"], "start": start, "len": length, "brk": t["brk"],
                            "off_start": t["off_start"], "off_end": t["off_end"]})
    return lib


def label(start: int, length: int) -> str:
    return "%s - %s" % (S.hhmm(start), S.hhmm(start + length))


def break_offsets(sh: Dict[str, Any]) -> List[int]:
    """Legal break starts (minutes from shift start) under the instance's rule."""
    if not sh["brk"]:
        return [None]
    return list(range(sh["off_start"], sh["len"] - sh["off_end"] - sh["brk"] + 1, 15))


def cases_for(inst_dir: Path, sol_dir: Path, iid: str, rosters: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    inst = parse_instance(inst_dir / (iid + ".txt"))
    opt = parse_solution(sol_dir / (iid + "-opt.txt"), inst["skills"])
    keep = TRANSLATED[iid]
    lib = shift_library(inst, keep)
    in_lib = {(s["start"], s["len"]) for s in lib}
    for s in opt:
        assert (s["start"], s["len"]) in in_lib, ("published optimum shift not in library", iid, s)
    t0 = inst["types"][keep[0]]
    assert all(inst["types"][k]["brk"] == t0["brk"] and inst["types"][k]["off_start"] == t0["off_start"]
               and inst["types"][k]["off_end"] == t0["off_end"] for k in keep), iid
    lengths = sorted({s["len"] for s in lib})
    settings = {
        "Interval Minutes": 15,
        "Allowed Shift Durations Hours": ",".join("%g" % (m / 60) for m in lengths),
        "Short Break Count": 0, "Lunch Count": 1, "Lunch Duration Minutes": t0["brk"],
        "Break Edge Margin Minutes": t0["off_end"],
        "Lunch Earliest Minutes From Shift Start": t0["off_start"],
        "Maximum Concurrent Break Ratio": 0.75, "Maximum Concurrent Breaks": 999,
        "Blank Interval Staffing Rule": "Allow staffing in blank intervals",
    }
    cases = []
    for sk in range(inst["skills"]):
        duties = sum(s["counts"][d][sk] for s in opt for d in range(DAYS))
        n = math.ceil(duties / 5)
        cid = "PUB_SDB_%s_SKILL%d" % (iid, sk + 1)
        if rosters and cid in rosters:
            n = rosters[cid]
        names, langs = S.english(n)
        prev, k = {}, 0
        for s in opt:  # last Saturday = the published optimum's Saturday night shifts
            if s["start"] + s["len"] > 1440:
                for _ in range(s["counts"][6][sk]):
                    prev[k] = label(s["start"], s["len"])
                    k += 1
        assert k <= n, (iid, sk, k, n)
        demand = [[(inst["req"][sk][d][p] or None) for p in range(SLOTS)] for d in range(DAYS)]
        cases.append({
            "id": cid, "instance": iid, "skill": sk, "tier": "benchmark",
            "associates": n, "duties_in_published_optimum": duties, "names": names, "languages": langs,
            "language_rules": S.ENGLISH_RULE, "interval_minutes": 15, "shrinkage": 0.0,
            "shift_starts": [], "previous_saturday": prev, "settings": settings,
            "extra_shift_rows": [(label(s["start"], s["len"]), S.hhmm(s["start"]), S.hhmm(s["start"] + s["len"]),
                                  s["len"] / 60, "%gH" % (s["len"] / 60), "%s (%s)" % (s["name"], iid))
                                 for s in lib],
            "library": lib, "demand": demand, "req": inst["req"][sk],
            "purpose": "Bonutti et al. %s, skill %d, as a %d-person weekly roster" % (iid, sk + 1, n),
        })
    return cases


# --------------------------------------------------------------------------- build
def cmd_build(a) -> int:
    E = S.load_engine(a.engine)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    ref = json.loads(a.reference.read_text())
    rosters = {k: v["min_roster"] for k, v in ref.items() if v.get("min_roster")}
    for iid in TRANSLATED:
        for c in cases_for(a.instances, a.solutions, iid, rosters):
            if c["id"] not in rosters:
                print("%-24s skipped: no proven full-cover roster" % c["id"])
                continue
            out = a.out_dir / (c["id"] + ".xlsx")
            S.build_workbook(a.template, out, c, E, c["demand"])
            parsed = E.parse_input(out)
            contract = E.validate_input_contract(parsed)
            active = sum(1 for d in range(DAYS) for p in range(SLOTS) if c["req"][d][p] > 0)
            manifest.append({k: c[k] for k in ("id", "instance", "skill", "tier", "associates",
                                               "duties_in_published_optimum", "purpose")}
                            | {"workbook": out.name, "source": SOURCE, "shifts_in_library": len(c["library"]),
                               "active_slots": active, "contract_status": contract.get("status"),
                               "contract_failures": [f.get("code") for f in contract.get("failures", [])],
                               "parsed_shifts": len(parsed.shifts),
                               "parsed_break_sets": [list(map(list, parsed.break_segments_q))]})
            print("%-24s N=%-3d shifts=%-4d active=%-4d contract=%s" % (
                c["id"], c["associates"], len(c["library"]), active, contract.get("status")))
    (a.out_dir / "cases.json").write_text(json.dumps(
        {"source": SOURCE, "not_translated": NOT_TRANSLATED, "cases": manifest}, indent=2))
    return 0


# --------------------------------------------------------------------------- bound
def cmd_bound(a) -> int:
    """Max slots hit, cyclic week, N workers on 5-day tours with 2 adjacent OFF days.

    Relaxation of the engine's rules: no 12h rest, no limit on different shifts,
    no carry-in; breaks anywhere the instance allows (the engine's legal set is
    the same set). Any engine schedule, scored cyclically, is at most this.
    The engine's concurrent-break cap (<= 75% of on-shift heads and at least one
    left working) is added in the "with_cap" variant only.
    """
    from ortools.sat.python import cp_model
    results = {}
    for iid in TRANSLATED:
        if a.only and iid not in a.only.split(","):
            continue
        for c in cases_for(a.instances, a.solutions, iid):
            req = c["req"]
            active = [(d, p) for d in range(DAYS) for p in range(SLOTS) if req[d][p] > 0]
            row = {"associates": c["associates"], "active_slots": len(active)}
            for variant in ("no_cap", "with_cap"):
                m = cp_model.CpModel()
                n = c["associates"]
                off = [m.NewIntVar(0, n, "off%d" % k) for k in range(DAYS)]  # OFF pair (k, k+1)
                m.Add(sum(off) == n)
                on_cov = [[] for _ in range(WEEK)]
                brk_cov = [[] for _ in range(WEEK)]
                for d in range(DAYS):
                    ys = []
                    for si, sh in enumerate(c["library"]):
                        for b in break_offsets(sh):
                            y = m.NewIntVar(0, n, "y%d_%d_%s" % (d, si, b))
                            ys.append(y)
                            base = d * SLOTS + sh["start"] // 15
                            for o in range(sh["len"] // 15):
                                t = (base + o) % WEEK
                                if b is not None and b // 15 <= o < (b + sh["brk"]) // 15:
                                    brk_cov[t].append(y)
                                else:
                                    on_cov[t].append(y)
                    m.Add(sum(ys) == n - off[d] - off[(d - 1) % DAYS])
                hits = []
                for d, p in active:
                    t = d * SLOTS + p
                    h = m.NewBoolVar("h%d" % t)
                    m.Add(sum(on_cov[t]) >= req[d][p]).OnlyEnforceIf(h)
                    hits.append(h)
                if variant == "with_cap":
                    for t in range(WEEK):
                        if brk_cov[t]:
                            m.Add(4 * sum(brk_cov[t]) <= 3 * (sum(brk_cov[t]) + sum(on_cov[t])))
                            m.Add(sum(on_cov[t]) >= 1)
                m.Maximize(sum(hits))
                sv = cp_model.CpSolver()
                sv.parameters.max_time_in_seconds = a.time_limit
                sv.parameters.num_workers = a.workers
                sv.parameters.random_seed = 1
                st = sv.Solve(m)
                row[variant] = {"status": sv.StatusName(st), "best": int(sv.ObjectiveValue()) if st in (
                    cp_model.OPTIMAL, cp_model.FEASIBLE) else None, "bound": int(math.floor(sv.BestObjectiveBound() + 1e-6)),
                    "seconds": round(sv.WallTime(), 1)}
            results[c["id"]] = row
            print(c["id"], json.dumps(row))
            a.out.write_text(json.dumps(results, indent=2))
    return 0


# ----------------------------------------------------------------------- reference
def cmd_reference(a) -> int:
    """Does a schedule hitting EVERY active slot exist under the engine's own rules?

    Exact CP-SAT feasibility, no engine code, cyclic week, N workers. Each worker:
    5 working days with the 2 OFF days adjacent; 12h rest between consecutive
    working days (Saturday -> Sunday included); at most 2 different shifts in
    the week. Shifts: those the published optimum uses (start, length). Break:
    any legal start under the instance's rule (= the engine's parsed rule). On
    every slot: on-floor heads >= requirement; with the engine's concurrent-break
    cap (breaks <= 75% of on-shift heads, at least one working while anyone is
    on break). FEASIBLE is a constructive proof that 100% of active slots is
    reachable within the engine's rules, so it is the optimum of the engine's
    metric.
    """
    from ortools.sat.python import cp_model
    relax = set(filter(None, a.relax.split(",")))
    results = json.loads(a.out.read_text()) if a.out.exists() else {}
    for iid in TRANSLATED:
        if a.only and iid not in a.only.split(","):
            continue
        inst = parse_instance(a.instances / (iid + ".txt"))
        opt = parse_solution(a.solutions / (iid + "-opt.txt"), inst["skills"])
        for c in cases_for(a.instances, a.solutions, iid):
            if c["id"] in results and results[c["id"]].get("min_roster"):
                continue
            row = {"relaxed": sorted(relax), "ceil_duties_over_5": c["associates"], "tries": {}}
            for n in range(c["associates"], c["associates"] + a.max_extra + 1):
                status, secs = _full_cover_feasible(cp_model, c, opt, n, relax, a)
                row["tries"][str(n)] = {"status": status, "seconds": secs}
                print(c["id"], n, status, secs, flush=True)
                if status in ("FEASIBLE", "OPTIMAL"):
                    row["min_roster"] = n
                    break
                if status != "INFEASIBLE":
                    break  # unknown: stop, never guess
            row["active_slots"] = sum(1 for d in range(DAYS) for p in range(SLOTS) if c["req"][d][p] > 0)
            row["shifts_allowed"] = [label(s, l) for s, l in sorted({(s["start"], s["len"]) for s in opt})]
            results[c["id"]] = row
            a.out.write_text(json.dumps(results, indent=2))
    return 0


def tour_patterns(shifts: List[Tuple[int, int]], relax: set) -> List[Tuple[int, Tuple[Optional[int], ...]]]:
    """Every legal weekly tour: (OFF pair k = days k and k+1, shift index per day or None).

    5 working days, the 2 OFF days adjacent (cyclic); at most 2 different shifts
    unless relaxed; 12h rest between consecutive working days (Saturday ->
    Sunday too) unless relaxed.
    """
    import itertools
    out = []
    for k in range(DAYS):
        work_days = [d for d in range(DAYS) if d not in (k, (k + 1) % DAYS)]
        for combo in itertools.product(range(len(shifts)), repeat=len(work_days)):
            if "variety" not in relax and len(set(combo)) > 2:
                continue
            row: List[Optional[int]] = [None] * DAYS
            for d, j in zip(work_days, combo):
                row[d] = j
            ok = True
            if "rest" not in relax:
                for d in range(DAYS):
                    j1, j2 = row[d], row[(d + 1) % DAYS]
                    if j1 is not None and j2 is not None:
                        s1, l1 = shifts[j1]
                        if 1440 + shifts[j2][0] - (s1 + l1) < 720:
                            ok = False
                            break
            if ok:
                out.append((k, tuple(row)))
    return out


def _full_cover_feasible(cp_model, c, opt, n, relax, a):
    """One exact feasibility solve of the full-cover model for a roster of n (see cmd_reference).

    Aggregated, so identical workers create no symmetry: an integer count per
    legal tour pattern, and per (day, shift) an integer count per break start.
    Exact, because no engine rule links one person's breaks across days.
    """
    libsh = {(s["start"], s["len"]): s for s in c["library"]}
    shifts = sorted({(s["start"], s["len"]) for s in opt})
    req = c["req"]
    tours = tour_patterns(shifts, relax)
    m = cp_model.CpModel()
    tv = [m.NewIntVar(0, n, "t%d" % i) for i in range(len(tours))]
    m.Add(sum(tv) == n)
    on_cov = [[] for _ in range(WEEK)]
    brk_cov = [[] for _ in range(WEEK)]
    for d in range(DAYS):
        for j, key in enumerate(shifts):
            users = [tv[i] for i, (_, row) in enumerate(tours) if row[d] == j]
            sh = libsh[key]
            zs = []
            for b in break_offsets(sh):
                z = m.NewIntVar(0, n, "z%d_%d_%s" % (d, j, b))
                zs.append(z)
                base = d * SLOTS + sh["start"] // 15
                for o in range(sh["len"] // 15):
                    t = (base + o) % WEEK
                    if b is not None and b // 15 <= o < (b + sh["brk"]) // 15:
                        brk_cov[t].append(z)
                    else:
                        on_cov[t].append(z)
            m.Add(sum(zs) == sum(users))
    for d in range(DAYS):
        for p in range(SLOTS):
            t = d * SLOTS + p
            if req[d][p] > 0:
                m.Add(sum(on_cov[t]) >= req[d][p])
            if brk_cov[t] and "cap" not in relax:
                m.Add(4 * sum(brk_cov[t]) <= 3 * (sum(brk_cov[t]) + sum(on_cov[t])))
                anyb = m.NewBoolVar("ab%d" % t)
                m.Add(sum(brk_cov[t]) == 0).OnlyEnforceIf(anyb.Not())
                m.Add(sum(on_cov[t]) >= 1).OnlyEnforceIf(anyb)
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = a.time_limit
    sv.parameters.num_workers = a.workers
    sv.parameters.random_seed = 1
    st = sv.Solve(m)
    return sv.StatusName(st), round(sv.WallTime(), 1)


# --------------------------------------------------------------------------- score
def read_engine_week(xlsx: Path):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    rows = list(wb["Schedule"].iter_rows(values_only=True))
    hdr = next(i for i, r in enumerate(rows) if r and "Sun" in r)
    cols = [rows[hdr].index(dn) for dn in day_names]
    name_col = rows[hdr].index("SF Name")
    shifts = {}
    for r in rows[hdr + 1:]:
        if not r or not r[name_col]:
            continue
        for d, ci in enumerate(cols):
            v = str(r[ci] or "").strip()
            m = re.match(r"^(\d\d:\d\d)\s*-\s*(\d\d:\d\d)$", v)
            if m:
                st, en = tmin(m.group(1)), tmin(m.group(2))
                shifts[(r[name_col], d)] = (st, (en - st) % 1440 or 1440)
    breaks = {}
    for r in list(wb["Break Schedule"].iter_rows(values_only=True))[1:]:
        if not r or not r[0] or str(r[6]).strip().lower() != "scheduled":
            continue
        d = day_names.index(r[1])
        st = r[4] if isinstance(r[4], str) else r[4].strftime("%H:%M")
        breaks.setdefault((r[0], d), []).append((tmin(st), int(r[5])))
    return shifts, breaks


def cyclic_score(req, shifts, breaks) -> Dict[str, Any]:
    cov = [0] * WEEK
    for (who, d), (st, ln) in shifts.items():
        rel = []
        for bst, bl in breaks.get((who, d), []):
            off = (bst - st) % 1440
            rel.append((off, off + bl))
        for o in range(0, ln, 15):
            if any(a <= o < b for a, b in rel):
                continue
            cov[(d * SLOTS + st // 15 + o // 15) % WEEK] += 1
    hit = under = over = active = 0
    for d in range(DAYS):
        for p in range(SLOTS):
            r, c = req[d][p], cov[d * SLOTS + p]
            if r > 0:
                active += 1
                hit += c >= r
            under += max(0, r - c)
            over += max(0, c - r)
    return {"active": active, "hit": hit, "under_slots": under, "over_slots": over}


def cmd_score(a) -> int:
    runs = Path(a.runs)
    table = {}
    for iid in TRANSLATED:
        inst = parse_instance(a.instances / (iid + ".txt"))
        merged: Dict[Tuple[int, int, Optional[int]], List[List[int]]] = {}
        complete = True
        for c in cases_for(a.instances, a.solutions, iid):
            found = sorted(runs.glob("%s*/**/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx" % c["id"]))
            if not found:
                table[c["id"]] = {"status": "NO_PUBLISHED_SCHEDULE"}
                complete = False
                continue
            shifts, breaks = read_engine_week(found[-1])
            row = cyclic_score(c["req"], shifts, breaks)
            row["workbook"] = str(found[-1].relative_to(runs))
            table[c["id"]] = row
            for (who, d), (st, ln) in shifts.items():
                b = breaks.get((who, d), [])
                key = (st, ln, (b[0][0] - st) % 1440 if b else None)
                merged.setdefault(key, [[0] * inst["skills"] for _ in range(DAYS)])[d][c["skill"]] += 1
        if complete:
            lines = []
            for j, ((st, ln, boff), counts) in enumerate(sorted(merged.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or 0))):
                tname = next(t["name"] for t in inst["types"].values()
                             if t["min_start"] <= st <= t["max_start"] and t["min_len"] <= ln <= t["max_len"]
                             and t["short"] in TRANSLATED[iid])
                end = st + ln
                endtxt = S.hhmm(end) + ("*" if end > 1440 else "")
                if boff is None:
                    btxt = "(no break)"
                else:
                    bs = st + boff
                    btxt = "(break at %d:%02d--%d:%02d)" % (bs // 60, bs % 60, (bs + 60) // 60, (bs + 60) % 60)
                cnt = " ".join("/".join(str(x) for x in counts[d]) + "," for d in range(DAYS))
                tot = "/".join(str(sum(counts[d][sk] for d in range(DAYS))) for sk in range(inst["skills"]))
                lines.append("E%d ( %s ) %s-%s %d %s %s [%s]" % (j + 1, tname, S.hhmm(st), endtxt, ln, btxt, cnt, tot))
            (a.out_dir / ("%s-engine.txt" % iid)).write_text("\n".join(lines) + "\n")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "engine_cyclic_scores.json").write_text(json.dumps(table, indent=2))
    for k, v in table.items():
        print(k, v)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "bound", "reference", "score"):
        p = sub.add_parser(name)
        p.add_argument("--instances", type=Path, required=True)
        p.add_argument("--solutions", type=Path, required=True)
        if name == "build":
            p.add_argument("--engine", type=Path, required=True)
            p.add_argument("--template", type=Path, required=True)
            p.add_argument("--out-dir", type=Path, required=True)
            p.add_argument("--reference", type=Path, required=True,
                           help="reference JSON: each case is built at its smallest proven full-cover roster")
        if name in ("bound", "reference"):
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--time-limit", type=float, default=300)
            p.add_argument("--workers", type=int, default=4)
            p.add_argument("--only", default="")
            p.add_argument("--relax", default="", help="reference only: any of cap,rest,variety")
            p.add_argument("--max-extra", type=int, default=12, help="reference only: roster sizes tried above ceil(duties/5)")
        if name == "score":
            p.add_argument("--runs", type=Path, required=True)
            p.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    return {"build": cmd_build, "bound": cmd_bound, "reference": cmd_reference, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
