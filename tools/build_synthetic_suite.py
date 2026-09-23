#!/usr/bin/env python3
"""Build the four-tier synthetic test suite (easy / moderate / hard / extreme).

Every coverage case is PLANTED: a complete weekly schedule is written down
first -- shift per associate per day, OFF pair, and a break pattern taken from
the engine's own legal pattern set -- and the demand is then derived from that
plan's after-break coverage. So the optimum is known before the engine runs:
the planted schedule hits 100% of every active interval, and that claim is
certified by the engine's own `calculate_metrics` on the planted schedule, not
asserted. The engine is then asked to find a schedule of its own with no hint
of the plan.

Cases that are not planted have an outcome that follows from arithmetic:
  * an over-demanded roster with a hard floor (total required productive
    hours exceed total supplied productive hours, so no schedule exists);
  * a day every associate is hard-OFF on (it cannot be covered);
  * malformed contracts, which must be refused before the solver starts.

Nothing here reads or changes a shipped workbook except as a FORMAT template
(every value the engine reads is overwritten). Outputs are test inputs, named
SYNTH_*, written to --out-dir with a cases.json holding each expectation and
its certificate.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import openpyxl

DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def load_engine(path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("E", path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["E"] = E
    spec.loader.exec_module(E)
    return E


def hhmm(minute: int) -> str:
    minute %= 1440
    return "%02d:%02d" % (minute // 60, minute % 60)


# --------------------------------------------------------------------- workbook
def set_instruction(wb, label: str, value: Any, E) -> None:
    for name in ("Instructions", "Engine Defaults"):
        ws = wb[name]
        for r in range(1, ws.max_row + 1):
            if E.norm(ws.cell(r, 2).value) == E.norm(label):
                ws.cell(r, 3).value = value
                return
    # Not in the template: the engine reads Engine Defaults by label, so append it.
    ws = wb["Engine Defaults"]
    r = ws.max_row + 1
    ws.cell(r, 1).value = "Synthetic"
    ws.cell(r, 2).value = label
    ws.cell(r, 3).value = value


def clear_rows(ws, first_row: int) -> None:
    for r in range(first_row, max(ws.max_row, first_row) + 1):
        for c in range(1, ws.max_column + 1):
            ws.cell(r, c).value = None


def write_grid(ws, interval_minutes: int, grid: List[List[Optional[float]]]) -> None:
    """grid[d][i]; row 3.. holds intervals, columns B..H hold Sun..Sat."""
    per_day = 1440 // interval_minutes
    for i in range(per_day):
        ws.cell(3 + i, 1).value = hhmm(i * interval_minutes)
        for d in range(7):
            ws.cell(3 + i, 2 + d).value = grid[d][i]


def build_workbook(template: Path, out: Path, case: Dict[str, Any], E,
                   demand: List[List[Optional[float]]]) -> None:
    shutil.copy(template, out)
    wb = openpyxl.load_workbook(out)
    im = case["interval_minutes"]
    n = case["associates"]
    settings = {
        "Program Name": case["id"],
        "Count of Associates": n,
        "Allow Headcount Mismatch": "No",
        "Interval Minutes": im,
        "Requirements Source": "FT Wise %d Min" % im,
        "Shrinkage Source": "Shrinkage %d Min" % im,
        "Run Stage": "Full Schedule",
        "Run Depth": "Quick",
        "Target": 1.0,
        "Target Priority Confirmed": "Yes",
        "Minimum Per Interval": 0.8,
        "Hard Floor Solver Constraint Enabled": "No",
        "Blank Interval Staffing Rule": "No new staffing in blank intervals",
        "Allowed Shift Durations Hours": "9",
        "Use 11H/3OFF": "No",
        "Strict OFF Count": "Yes",
        "Separate OFF Days": "No",
        "Rest Gap Hours": 12,
        "Count of Different Shifts Per week": 2,
        "Fixed Request Use": "No",
        "Hard OFF Preferences": "Yes",
        "Leave Enabled": "Yes",
        "Use Preferences": "Yes",
        "Opening Guard Enabled": "No",
        "Short Break Count": 2,
        "Short Break Duration Minutes": 15,
        "Lunch Count": 1,
        "Lunch Duration Minutes": 30,
        "Critical Coverage No-Break Exception Enabled": "No",
        "Critical Coverage No-Break Max Associate-Days": 0,
    }
    settings.update(case.get("settings", {}))
    for k, v in settings.items():
        set_instruction(wb, k, v, E)

    # Roster.
    ws = wb["Schedule"]
    clear_rows(ws, 3)
    names = case["names"]
    langs = case["languages"]
    for a in range(n):
        ws.cell(3 + a, 1).value = a + 1
        ws.cell(3 + a, 2).value = 900000 + a
        ws.cell(3 + a, 3).value = names[a]
        ws.cell(3 + a, 4).value = names[a]
        ws.cell(3 + a, 5).value = "TL Synthetic"
        ws.cell(3 + a, 6).value = langs[a]

    # Preferences: only what the case asks for.
    ws = wb["Preference"]
    clear_rows(ws, 3)
    prefs = case.get("preferences", {})
    for r, (a, row) in enumerate(sorted(prefs.items())):
        ws.cell(3 + r, 1).value = names[a]
        ws.cell(3 + r, 2).value = langs[a]
        for d in range(7):
            ws.cell(3 + r, 3 + d).value = row[d]

    ws = wb["Fixed Request"]
    clear_rows(ws, 3)
    ws.cell(3, 1).value = "No"

    # Previous Saturday: OFF for everyone unless the case supplies shifts.
    ws = wb["Previous week scheduled"]
    clear_rows(ws, 3)
    prev = case.get("previous_saturday", {})
    for a in range(n):
        ws.cell(3 + a, 1).value = a + 1
        ws.cell(3 + a, 2).value = names[a]
        ws.cell(3 + a, 3).value = langs[a]
        ws.cell(3 + a, 4).value = prev.get(a, "OFF")

    # Shift library: statuses + the case's shifts.
    ws = wb["Shift Library"]
    clear_rows(ws, 3)
    rows = [("OFF", None, None, None, "Status", "Expected weekly OFF value"),
            ("Leave", None, None, None, "Status", "Hard unavailable day"),
            ("Planned", None, None, None, "Status", "Previous-Saturday only")]
    for start in case["shift_starts"]:
        end = start + case.get("shift_minutes", 540)
        rows.append(("%s - %s" % (hhmm(start), hhmm(end)), hhmm(start), hhmm(end),
                     case.get("shift_minutes", 540) / 60, "9H", "synthetic"))
    for extra in case.get("extra_shift_rows", []):
        rows.append(tuple(extra))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            ws.cell(3 + r, 1 + c).value = v

    # Language setup.
    ws = wb["Language Setup"]
    clear_rows(ws, 3)
    for r, rule in enumerate(case["language_rules"]):
        for c, v in enumerate(rule):
            ws.cell(3 + r, 1 + c).value = v

    # Demand and shrinkage: blank every grid, then fill the chosen one.
    for sheet in ("FT Wise 15 Min", "FT Wise 30 Min", "FT Wise 60 Min",
                  "Shrinkage 15 Min", "Shrinkage 30 Min", "Shrinkage 60 Min"):
        clear_rows(wb[sheet], 3)
        m = int(sheet.split()[-2])
        write_grid(wb[sheet], m, [[None] * (1440 // m) for _ in range(7)])
    write_grid(wb["FT Wise %d Min" % im], im, demand)
    shr = [[(case["shrinkage"] if demand[d][i] not in (None, 0) else None)
            for i in range(1440 // im)] for d in range(7)]
    write_grid(wb["Shrinkage %d Min" % im], im, shr)
    wb.save(out)


# ---------------------------------------------------------------------- planting
def works(a_off_start: int, d: int) -> bool:
    return d not in (a_off_start % 7, (a_off_start + 1) % 7)


def plant(case: Dict[str, Any], parsed, E) -> Tuple[Any, Dict, List]:
    """Planted skeleton + break selection built from the engine's own objects."""
    n = case["associates"]
    patterns = E.generate_break_patterns(parsed)
    by_label = {E.norm(s.label): s for s in parsed.shifts}
    assignment = [["OFF"] * 7 for _ in range(n)]
    selected_idx: List[List[Optional[int]]] = [[None] * 7 for _ in range(n)]
    for a in range(n):
        start = case["plan_start"][a]
        label = "%s - %s" % (hhmm(start), hhmm(start + case.get("shift_minutes", 540)))
        shift = by_label[E.norm(label)]
        for d in range(7):
            if works(case["plan_off"][a], d) and d not in case.get("plan_forced_off_days", ()):
                assignment[a][d] = shift.label
                selected_idx[a][d] = shift.index
    skeleton = E.SkeletonSolution("planted", "PLANTED", 0.0, 0.0, assignment, selected_idx, {})

    selected: Dict[Tuple[int, int], Optional[int]] = {}
    if patterns and parsed.break_segments_q:
        # Stagger: for each (day, shift start) group, hand out the legal
        # patterns round-robin from a spread of offsets so breaks do not stack.
        load: Dict[int, int] = {}
        cover: Dict[int, int] = {}
        for a, d, si in E.scheduled_cells(skeleton):
            st = d * 96 + parsed.shifts[si].start_min // 15
            for o in range(parsed.shifts[si].duration_q):
                cover[st + o] = cover.get(st + o, 0) + 1
        cells = sorted(E.scheduled_cells(skeleton), key=lambda t: (t[1], parsed.shifts[t[2]].start_min, t[0]))
        for a, d, si in cells:
            shift = parsed.shifts[si]
            legal = [p for p in patterns if p.duration_q == shift.duration_q]
            base = d * 96 + shift.start_min // 15

            def peak(p):
                return max((load.get(base + o, 0) for o in p.broken_offsets), default=0)

            def empties(p):
                return sum(1 for o in p.broken_offsets if load.get(base + o, 0) + 1 >= cover.get(base + o, 0))

            def ratio(p):
                return max((load.get(base + o, 0) + 1) / cover[base + o] for o in p.broken_offsets) if p.broken_offsets else 0

            def over_cap(p):
                return sum(1 for o in p.broken_offsets
                           if load.get(base + o, 0) + 1 > E.maximum_concurrent_breaks(parsed, cover.get(base + o, 0)))

            best = min(legal, key=lambda p: (empties(p), over_cap(p), ratio(p), peak(p), -p.score, p.index))
            selected[(a, d)] = best.index
            for o in best.broken_offsets:
                load[base + o] = load.get(base + o, 0) + 1
    return skeleton, selected, patterns


def after_coverage(parsed, skeleton, selected, patterns, E) -> Tuple[List[List[float]], List[List[float]]]:
    """Average before/after headcount per (day, interval), current week only."""
    breaks = E.break_qslots(parsed, skeleton, selected, patterns)
    qpi = parsed.qslots_per_interval
    per_day = parsed.intervals_per_day
    before = [[0.0] * per_day for _ in range(7)]
    after = [[0.0] * per_day for _ in range(7)]
    for d in range(7):
        for i in range(per_day):
            b = aft = 0
            for q in range(qpi):
                qslot = d * 96 + i * qpi + q
                cov = E.scheduled_covering_qslot(parsed, skeleton, qslot)
                b += len(cov)
                aft += sum(1 for a, _, _ in cov if (a, qslot) not in breaks)
            before[d][i] = b / qpi
            after[d][i] = aft / qpi
    return before, after


# ------------------------------------------------------------------------ cases
def english(n: int) -> Tuple[List[str], List[str]]:
    return ["Synth Agent %03d" % (a + 1) for a in range(n)], ["English"] * n


ENGLISH_RULE = [("English", "00:00", "00:00", "English", "Yes", "English", 0,
                 "No minimum", "No", "All")]


def spread(n: int, starts: Sequence[int]) -> Tuple[List[int], List[int]]:
    """Deterministic plan: associate a gets start starts[a % k] and OFF pair a % 7."""
    return [starts[a % len(starts)] for a in range(n)], [a % 7 for a in range(n)]


def case_defs() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    def add(cid, tier, n, starts, plan_starts, plan_off, s, im=60, **kw):
        names, langs = english(n)
        c = dict(id=cid, tier=tier, associates=n, shift_starts=starts, plan_start=plan_starts,
                 plan_off=plan_off, shrinkage=s, interval_minutes=im, names=names,
                 languages=langs, language_rules=ENGLISH_RULE)
        c.update(kw)
        cases.append(c)
        return c

    # EASY ---------------------------------------------------------------
    # E1: one shift, no breaks, 7 associates with 7 distinct OFF pairs -> exactly
    # 5 on every day. Zero slack: a single misplaced OFF pair misses a day.
    add("SYNTH_E1_EXACT_FIT_NO_BREAKS", "easy", 7, [8 * 60], [8 * 60] * 7, list(range(7)), 0.0,
        settings={"Short Break Count": 0, "Lunch Count": 0},
        purpose="Exact-fit days-off: every day needs exactly 5 of 7, which only the 7 distinct OFF pairs give.")
    # E2: same shape with breaks and 14 associates, plus 20% shrinkage.
    p, o = spread(14, [8 * 60])
    add("SYNTH_E2_SINGLE_SHIFT_WITH_BREAKS", "easy", 14, [8 * 60], p, o, 0.2,
        purpose="Two per OFF pair, one shift, standard 15/30/15 breaks, 20% shrinkage.")

    # MODERATE -----------------------------------------------------------
    starts = [h * 60 for h in range(6, 16)]
    p, o = spread(20, [6 * 60, 7 * 60, 9 * 60, 10 * 60, 12 * 60, 14 * 60, 15 * 60])
    add("SYNTH_M1_MULTI_START_NO_BREAKS", "moderate", 20, starts, p, o, 0.2,
        settings={"Short Break Count": 0, "Lunch Count": 0},
        purpose="Ten legal starts, seven used, 20% shrinkage, zero slack before breaks.")
    p, o = spread(28, [6 * 60, 7 * 60, 8 * 60, 10 * 60, 11 * 60, 13 * 60, 15 * 60])
    add("SYNTH_M2_MULTI_START_WITH_BREAKS", "moderate", 28, starts, p, o, 0.15,
        purpose="Same shape with breaks: the after-break optimum is the planted plan's.")

    # HARD ---------------------------------------------------------------
    # H1: 24/7 with overnight shifts (never on Saturday night, so nothing spills
    # into next week and previous Saturday is OFF for all).
    starts24 = [h * 60 for h in range(0, 24)]
    plan_starts = [(a * 5 % 24) * 60 for a in range(42)]
    plan_off = [a % 7 for a in range(42)]
    c = add("SYNTH_H1_24x7_OVERNIGHT", "hard", 42, starts24, plan_starts, plan_off, 0.12,
            purpose="24/7 with overnight shifts across midnight, 12% shrinkage, rest 12h.")
    # Overnight starters (start >= 15:00 spills past midnight) must not work
    # Saturday, or the plan spills into next Sunday: move their OFF pair to Fri-Sat.
    for a in range(42):
        if plan_starts[a] + 540 > 1440:
            c["plan_off"][a] = 5
    # H2: over-demand with a HARD floor: demand is 2x the planted after-break
    # coverage, so the floor needs 1.6x the productive hours the roster has.
    p, o = spread(20, [6 * 60, 7 * 60, 9 * 60, 10 * 60, 12 * 60, 14 * 60, 15 * 60])
    add("SYNTH_H2_HARD_FLOOR_OVERDEMAND", "hard", 20, starts, p, o, 0.2,
        demand_multiplier=2.0,
        settings={"Hard Floor Solver Constraint Enabled": "Yes"},
        purpose="Provably infeasible hard floor: must be refused or reported, never shipped as met.")
    # H3: language minimum. 10 of 30 are Spanish; Spanish needs 1 on the floor
    # after breaks 09:00-18:00 every day. The plan puts 2+ Spanish on every day.
    n = 30
    p, o = spread(n, [7 * 60, 8 * 60, 9 * 60, 11 * 60, 13 * 60])
    c = add("SYNTH_H3_LANGUAGE_MINIMUM", "hard", n, starts, p, o, 0.1,
            purpose="Hard language minimum after breaks; coverage optimum from the plan.")
    c["languages"] = ["Spanish" if a % 3 == 0 else "English" for a in range(n)]
    for a in range(n):
        if a % 3 == 0:          # Spanish: 09:00 start so they span the window
            c["plan_start"][a] = 9 * 60
    c["language_rules"] = [
        ("English", "00:00", "00:00", "English", "Yes", "English", 0, "No minimum", "No", "All"),
        ("Spanish", "09:00", "18:00", "Spanish, English", "Yes", "Spanish", 1, "Min 1", "Yes", "All"),
    ]

    # EXTREME ------------------------------------------------------------
    # X1: 15-minute intervals, 24/7, 120 associates, 14 starts.
    n = 120
    starts15 = [h * 60 for h in range(0, 24)]
    plan_starts = [((a * 7) % 24) * 60 for a in range(n)]
    plan_off = [a % 7 for a in range(n)]
    # At ~17 on the floor per quarter a 4-break absolute cap cannot fit 4 break
    # quarters per associate-day (a real 120-seat floor would not run one); the
    # ratio cap (30%) still applies.
    c = add("SYNTH_X1_LARGE_15MIN_24x7", "extreme", n, starts15, plan_starts, plan_off, 0.1, im=15,
            settings={"Maximum Concurrent Breaks": 10},
            purpose="120 associates, 15-minute grid, 24 starts, 24/7, planted after-break optimum.")
    for a in range(n):
        if plan_starts[a] + 540 > 1440:
            c["plan_off"][a] = 5
    # X2: every associate is hard-OFF on Sunday. Sunday demand is set equal to
    # Monday's, so Sunday is provably uncoverable and everything else is planted.
    n = 21
    p, o = spread(n, [7 * 60, 9 * 60, 11 * 60])
    c = add("SYNTH_X2_ALL_HARD_OFF_SUNDAY", "extreme", n, starts, p, o, 0.1,
            purpose="All associates hard-OFF Sunday: Sunday must be 0 hit, the rest the plan's optimum.")
    c["plan_off"] = [6 if a % 2 == 0 else 0 for a in range(n)]    # Sat-Sun or Sun-Mon
    c["preferences"] = {a: ["OFF", None, None, None, None, None, None] for a in range(n)}
    c["sunday_copies_monday"] = True
    return cases


# Contract-refusal cases are mutations of E2's finished workbook.
REFUSALS = [
    ("SYNTH_R1_OFF_GRID_SHIFT", "extreme", "SHIFT_OFF_QUARTER_GRID",
     "extra_shift", ("08:10 - 17:10", "08:10", "17:10", 9, "9H", "off grid")),
    ("SYNTH_R2_CAP_ORDER", "extreme", "INVALID_OVERAGE_CAP_ORDER",
     "settings", {"Overage Soft Cap": 1.4, "Overage Severe Cap": 1.2}),
    ("SYNTH_R3_GATE_MODE_TYPO", "extreme", "HARD_INVALID_FLOOR_LOSS_FROM_BREAKS_GATE_MODE",
     "settings", {"Floor Loss From Breaks Gate Mode": "Maybe"}),
    ("SYNTH_R4_HEADCOUNT_MISMATCH", "extreme", "HEADCOUNT_MISMATCH",
     "settings", {"Count of Associates": 15}),
    ("SYNTH_R5_SHRINKAGE_100", "extreme", "HARD_INVALID_SHRINKAGE_VALUE",
     "shrinkage", 1.0),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--template", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    E = load_engine(a.engine)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    manifest: List[Dict[str, Any]] = []
    built: Dict[str, Tuple[Dict[str, Any], Path]] = {}

    for case in case_defs():
        im = case["interval_minutes"]
        per_day = 1440 // im
        out = a.out_dir / (case["id"] + ".xlsx")
        # Pass 1: placeholder demand wherever the plan puts anyone, so the
        # engine parses the case and hands back its own shifts and patterns.
        placeholder = [[1.0] * per_day for _ in range(7)]
        build_workbook(a.template, out, case, E, placeholder)
        parsed = E.parse_input(out)
        skeleton, selected, patterns = plant(case, parsed, E)
        before, after = after_coverage(parsed, skeleton, selected, patterns, E)
        s = case["shrinkage"]
        mult = case.get("demand_multiplier", 1.0)
        demand: List[List[Optional[float]]] = [[None] * per_day for _ in range(7)]
        for d in range(7):
            for i in range(per_day):
                if before[d][i] > 0:
                    if after[d][i] <= 0:
                        raise SystemExit("%s: planted breaks empty %s %s" % (case["id"], d, i))
                    # Round DOWN to 2 decimals: never above what the plan delivers.
                    demand[d][i] = math.floor(after[d][i] * (1 - s) * mult * 100 + 1e-9) / 100
        if case.get("sunday_copies_monday"):
            demand[0] = list(demand[1])
        build_workbook(a.template, out, case, E, demand)

        # Certificate: re-parse the final workbook and score the plan with the
        # engine's canonical metric.
        parsed = E.parse_input(out)
        contract = E.validate_input_contract(parsed)
        skeleton, selected, patterns = plant(case, parsed, E)
        m = E.calculate_metrics(parsed, skeleton, selected, patterns)
        active = sum(1 for d in range(7) for i in range(per_day) if parsed.active[d][i])
        sunday_active = sum(1 for i in range(per_day) if parsed.active[0][i])
        cert = {k: m.get(k) for k in ("active_intervals", "before_target", "after_target",
                                        "before_floor", "after_floor")}
        for k in ("break_concurrency_violation_count", "language_gap_count", "zero_staffed_active_quarters",
                  "blank_staffed_quarters", "whole_week_imbalance_violation_count"):
            cert["plan_" + k] = m.get(k)
        cert["active_intervals"] = active
        cert["sunday_active_intervals"] = sunday_active
        cert["planted_supply_productive_hours"] = round(sum(map(sum, after)) * im / 60, 2)
        cert["demand_fte_hours"] = round(sum(v or 0 for row in demand for v in row) * im / 60, 2)
        exp: Dict[str, Any] = {"contract": "PASS"}
        if case.get("demand_multiplier", 1.0) > 1.0:
            exp = {"contract": "PASS", "hard_floor_infeasible": True,
                   "acceptable_refusals": ["HARD_FLOOR_PROVABLY_IMPOSSIBLE", "AGGREGATE_HARD_FLOOR_CAPACITY_SHORTAGE"],
                   "proof": "floor needs %.2f productive FTE-hours after shrinkage; the roster supplies at most %.2f"
                            % (0.8 * cert["demand_fte_hours"], cert["planted_supply_productive_hours"] * (1 - s))}
        elif case.get("sunday_copies_monday"):
            # Two outcomes are correct: a schedule with Sunday at 0 hits and the
            # rest at the planted optimum, or a refusal proving a demanded
            # interval cannot be staffed (the engine treats "at least one on
            # the floor in every demanded interval" as a hard contract).
            exp.update(optimum_after_target=active - sunday_active, sunday_hits=0,
                       acceptable_refusals=["ZERO_ACTIVE_INTERVAL_PROVABLY_IMPOSSIBLE"])
        else:
            exp.update(optimum_after_target=active, optimum_before_target=active)
        entry = {"id": case["id"], "tier": case["tier"], "purpose": case["purpose"],
                 "workbook": out.name, "associates": case["associates"],
                 "interval_minutes": im, "shrinkage": s,
                 "contract_status": contract.get("status"),
                 "contract_failures": [f.get("code") for f in contract.get("failures", [])],
                 "certificate": cert, "expected": exp}
        manifest.append(entry)
        built[case["id"]] = (case, out)
        print("%-34s contract=%s active=%s plan before/after target=%s/%s"
              % (case["id"], contract.get("status"), active, cert["before_target"], cert["after_target"]))

    # Refusals, derived from E2.
    base_case, base_out = built["SYNTH_E2_SINGLE_SHIFT_WITH_BREAKS"]
    parsed_e2 = E.parse_input(base_out)
    for rid, tier, code, kind, payload in REFUSALS:
        c = copy.deepcopy(base_case)
        c["id"] = rid
        if kind == "extra_shift":
            c["extra_shift_rows"] = [payload]
        elif kind == "settings":
            c.setdefault("settings", {}).update(payload)
        elif kind == "shrinkage":
            c["shrinkage"] = payload
        out = a.out_dir / (rid + ".xlsx")
        demand = [[parsed_e2.requirements[d][i] if parsed_e2.active[d][i] else None
                   for i in range(parsed_e2.intervals_per_day)] for d in range(7)]
        build_workbook(a.template, out, c, E, demand)
        manifest.append({"id": rid, "tier": tier, "workbook": out.name,
                         "purpose": "Malformed contract must be refused before the solver: %s" % code,
                         "expected": {"refused_with": code}})
        print("%-34s refusal case (expects %s)" % (rid, code))

    (a.out_dir / "cases.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
