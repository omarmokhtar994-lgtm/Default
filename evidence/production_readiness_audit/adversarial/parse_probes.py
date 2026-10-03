#!/usr/bin/env python3
"""Parser / contract probes: does a bad or unusual input get refused, warned,
normalised safely, or silently turned into a different contract?

Each probe builds a workbook with make_case.build, runs the engine's own
parse_input + capacity_diagnostics + validate_input_contract (exactly what a
production run does before CP-SAT), and records what the engine believed the
workbook said next to what the workbook actually said.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import make_case  # noqa: E402
import l632_universal_scheduler as E  # noqa: E402

NAMES = [f"Agent {c}" for c in "ABCDEFGHIJ"]


def base(**over):
    spec = {
        "roster": [(n, "English") for n in NAMES],
        "demand": lambda d, m: 3 if 8 * 60 <= m < 20 * 60 else None,
    }
    spec.update(over)
    return spec


def run(spec):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.xlsx"
        make_case.build(spec, path)
        try:
            parsed = E.parse_input(path)
        except Exception as exc:
            return {"outcome": "REFUSED_AT_PARSE", "error": f"{type(exc).__name__}: {exc}"}, None
        cap = E.capacity_diagnostics(parsed)
        contract = E.validate_input_contract(parsed, cap)
        codes = sorted({f.get("code") for f in contract["failures"]})
        outcome = "REFUSED" if contract["failures"] else ("WARNED" if contract["warnings"] else "ACCEPTED")
        return {"outcome": outcome, "failure_codes": codes,
                "warning_codes": sorted({w.get("code") for w in contract["warnings"]}),
                "parser_notes": [w for w in parsed.parser_warnings if not w.startswith("Break placement")][:6]}, parsed


def demand_total(p):
    return round(sum(v or 0 for day in p.requirements for v in day) * p.interval_minutes / 60, 2)


PROBES = []


def probe(pid, title, expectation):
    def wrap(fn):
        PROBES.append((pid, title, expectation, fn))
        return fn
    return wrap


@probe("P01", "baseline small workbook", "ACCEPTED")
def p01():
    r, p = run(base())
    r["seen"] = {"associates": len(p.associates), "demand_fte_hours": demand_total(p)} if p else None
    return r


@probe("P02", "Schedule columns re-ordered: Emp ID moved to column 4, TL in column 2",
       "names/languages still bound by header; employee IDs read correctly")
def p02():
    header = ["Slot", "TL", "Email", "Emp ID", "SF Name", "Language"] + make_case.DAYS
    rows = [[i + 1, "Same TL", f"a{i}@x", 5000 + i, n, "English"] + [None] * 7 for i, n in enumerate(NAMES)]
    r, p = run(base(roster_rows=rows, schedule_header=header))
    if p:
        r["seen"] = {"emp_ids_read": [a.emp_id for a in p.associates][:3], "names": [a.name for a in p.associates][:3]}
    return r


@probe("P03", "Schedule day headers are real dates (not Sun..Sat) and carry fixed requests; no Fixed Request sheet",
       "day columns found or refused; never a positional guess")
def p03():
    header = ["Slot", "Emp ID", "Email", "SF Name", "TL", "Language", "Notes A", "Notes B"] + \
             [dt.datetime(2026, 10, 4) + dt.timedelta(days=i) for i in range(7)]
    rows = [[i + 1, 9000 + i, "e", n, "TL", "English", "x", "y"] + ["08:00 - 17:00"] * 5 + ["OFF", "OFF"]
            for i, n in enumerate(NAMES)]
    r, p = run(base(roster_rows=rows, schedule_header=header,
                    instructions={"Fixed Request Use": "Yes"}))
    if p:
        r["seen"] = {"fixed_schedule_of_first": p.associates[0].fixed_schedule}
    return r


@probe("P04", "Preference sheet lists the same associate twice: Leave on Monday, then a blank row",
       "duplicate refused (as Previous-Saturday duplicates are) or Leave kept")
def p04():
    rows = [("Agent A", [None, "Leave", None, None, None, None, None]),
            ("Agent A", [None] * 7)]
    r, p = run(base(preference_rows=rows))
    if p:
        r["seen"] = {"agent_a_preferences": p.associates[0].preferences}
    return r


@probe("P05", "Fixed Request sheet with date headers instead of Sun..Sat (Fixed Request Use = Yes)",
       "fixed requests read, or refused; never silently dropped")
def p05():
    header = ["Active?", "Associate Name", "Nesting Group"] + \
             [dt.datetime(2026, 10, 4) + dt.timedelta(days=i) for i in range(7)]
    rows = [["Yes", "Agent A", None, "08:00 - 17:00", "08:00 - 17:00", "08:00 - 17:00",
             "08:00 - 17:00", "08:00 - 17:00", "OFF", "OFF"]]
    r, p = run(base(fixed_rows=rows, fixed_header=header, instructions={"Fixed Request Use": "Yes"}))
    if p:
        r["seen"] = {"agent_a_fixed": p.associates[0].fixed_schedule}
    return r


@probe("P06", "11-hour shifts requested while Use 11H/3OFF = No",
       "refused with a contradiction message; never a silent switch to 9-hour shifts")
def p06():
    shifts = [f"{h:02d}:00 - {(h + 11) % 24:02d}:00" for h in range(24)] + ["08:00 - 17:00"]
    r, p = run(base(instructions={"Allowed Shift Durations Hours": 11, "Use 11H/3OFF": "No"}, shifts=shifts))
    if p:
        r["seen"] = {"allowed_durations_min": sorted(p.allowed_shift_durations),
                     "shift_labels": [s.label for s in p.shifts]}
    return r


@probe("P07", "Interval Minutes = 30 but the demand sheet is 15-minute",
       "refused or demand preserved; never silently drop half the rows")
def p07():
    rows = [(make_case.hhmm(m), [2 if 8 * 60 <= m < 20 * 60 else None] * 7) for m in range(0, 1440, 15)]
    spec = base(step=30, demand_rows=rows)
    r, p = run(spec)
    if p:
        r["seen"] = {"interval": p.interval_minutes, "demand_fte_hours": demand_total(p),
                     "workbook_demand_fte_hours": 2 * 12 * 7}
    return r


@probe("P08", "Demand sheet repeats the 10:00 row; the repeat is blank",
       "duplicate time refused; never silently erase demand")
def p08():
    rows = []
    for m in range(0, 1440, 60):
        v = [3 if 8 * 60 <= m < 20 * 60 else None] * 7
        rows.append((make_case.hhmm(m), v))
        if m == 600:
            rows.append(("10:00", [None] * 7))
    r, p = run(base(demand_rows=rows))
    if p:
        r["seen"] = {"demand_10_00": [p.requirements[d][10] for d in range(7)],
                     "demand_fte_hours": demand_total(p), "workbook_demand_fte_hours": 3 * 12 * 7}
    return r


@probe("P09", "Demand sheet is missing the 12:00 row entirely",
       "warned or refused; never silently read as 'no demand'")
def p09():
    rows = [(make_case.hhmm(m), [3 if 8 * 60 <= m < 20 * 60 else None] * 7) for m in range(0, 1440, 60) if m != 720]
    r, p = run(base(demand_rows=rows))
    if p:
        r["seen"] = {"demand_12_00": [p.requirements[d][12] for d in range(7)], "active_12_00": p.active[1][12]}
    return r


@probe("P10", "No-break exceptions enabled with Max Associate-Days = 0",
       "0 honoured, or refused as contradictory")
def p10():
    r, p = run(base(instructions={"Critical Coverage No-Break Exception Enabled": "Yes",
                                  "Critical Coverage No-Break Max Associate-Days": 0}))
    if p:
        r["seen"] = {"allow": p.allow_no_break_exceptions, "max_no_break_exceptions": p.max_no_break_exceptions}
    return r


@probe("P11", "'Count of Different Shifts Per week' = 'three'; and = 0",
       "refused as non-numeric / out of range")
def p11():
    out = {}
    for value in ("three", 0):
        r, p = run(base(instructions={"Count of Different Shifts Per week": value}))
        r["seen"] = {"max_different_shifts": p.max_different_shifts} if p else None
        out[str(value)] = r
    return {"outcome": "SEE_CASES", "cases": out}


@probe("P12", "Coverage Split row with Start = '9am'",
       "refused; never silently drop a hard staffing rule")
def p12():
    r, p = run(base(language_setup=[{"Language": "English", "Coverage Start": "00:00", "Coverage End": "00:00",
                                     "Active?": "Yes", "Coverage Group": "English", "Minimum Per Interval": 0}],
                    coverage_split=[{"Coverage Group": "English", "Start": "9am", "End": "17:00",
                                     "Coverage Ratio": 1.0, "Exclusive?": "No", "Active?": "Yes"}]))
    if p:
        r["seen"] = {"coverage_split_rules": len(p.coverage_split_rules), "source": p.coverage_split_source}
    return r


@probe("P13", "Language minimum 0.5 and -1",
       "refused (minimum must be a whole number >= 0)")
def p13():
    out = {}
    for value in (0.5, -1):
        r, p = run(base(roster=[(n, "Spanish" if i < 3 else "English") for i, n in enumerate(NAMES)],
                        language_setup=[{"Language": "Spanish", "Coverage Start": "09:00", "Coverage End": "17:00",
                                         "Active?": "Yes", "Coverage Group": "Spanish",
                                         "Minimum Per Interval": value}]))
        r["seen"] = {"language_rules": [(x.group, x.minimum) for x in p.language_rules]} if p else None
        out[str(value)] = r
    return {"outcome": "SEE_CASES", "cases": out}


@probe("P14", "One associate on Leave all 7 days (Strict OFF = Yes)",
       "accepted; that associate simply does not work")
def p14():
    r, p = run(base(preferences={"Agent A": ["Leave"] * 7}))
    return r


@probe("P15", "Shift Library with malformed labels ('9-18', '08:00 - 24:00') beside valid ones",
       "malformed labels reported")
def p15():
    shifts = ["9-18", "08:00 - 24:00"] + [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
    r, p = run(base(shifts=shifts))
    if p:
        r["seen"] = {"shifts_parsed": [s.label for s in p.shifts]}
    return r


@probe("P16", "Demand cell 'abc'", "REFUSED")
def p16():
    rows = [(make_case.hhmm(m), ["abc" if m == 600 and d == 1 else (3 if 8 * 60 <= m < 20 * 60 else None)
                                 for d in range(7)]) for m in range(0, 1440, 60)]
    r, _ = run(base(demand_rows=rows))
    return r


@probe("P17", "Roster has 25 blank rows between associates 5 and 6; Count of Associates left blank",
       "all 10 associates read, or refused")
def p17():
    header = ["Slot", "Emp ID", "Email", "SF Name", "TL", "Language"] + make_case.DAYS
    rows = [[i + 1, 7000 + i, "e", n, "TL", "English"] + [None] * 7 for i, n in enumerate(NAMES[:5])]
    rows += [[None] * 13 for _ in range(25)]
    rows += [[i + 6, 7100 + i, "e", n, "TL", "English"] + [None] * 7 for i, n in enumerate(NAMES[5:])]
    r, p = run(base(roster_rows=rows, schedule_header=header, instructions={"Count of Associates": None}))
    if p:
        r["seen"] = {"associates_read": len(p.associates)}
    return r


@probe("P18", "Previous-Saturday shift '25:00 - 06:00' (invalid hour)", "refused")
def p18():
    r, p = run(base(previous_saturday={"Agent A": "25:00 - 06:00"}))
    if p:
        r["seen"] = {"agent_a_previous_saturday": p.associates[0].previous_saturday}
    return r


@probe("P19", "Instructions list 'Target' twice: 0.9 then 0.5", "refused as contradictory, or warned")
def p19():
    spec = base()
    r = None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.xlsx"
        make_case.build(spec, path)
        from openpyxl import load_workbook
        wb = load_workbook(path)
        wb["Instructions"].append(["Case", "Target", 0.5, None])
        wb.save(path)
        p = E.parse_input(path)
        contract = E.validate_input_contract(p, E.capacity_diagnostics(p))
        r = {"outcome": "REFUSED" if contract["failures"] else ("WARNED" if contract["warnings"] else "ACCEPTED"),
             "failure_codes": sorted({f.get("code") for f in contract["failures"]}),
             "seen": {"target_ratio_used": p.target_ratio}}
    return r


@probe("P20", "Language Working Window = 'Enforce' (not a listed value)", "REFUSED")
def p20():
    r, _ = run(base(instructions={"Language Working Window": "Enforce"}))
    return r


@probe("P21", "Overnight day-specific language minimum Mon-Fri 18:00-05:00 (Spanish, min 1)",
       "minimum applies Mon 18:00..Tue 05:00 ... Fri 18:00..Sat 05:00; NOT Mon 00:00-05:00")
def p21():
    r, p = run(base(roster=[(n, "Spanish" if i < 4 else "English") for i, n in enumerate(NAMES)],
                    demand=lambda d, m: 2,
                    language_setup=[{"Language": "Spanish", "Coverage Start": "18:00", "Coverage End": "05:00",
                                     "Active?": "Yes", "Coverage Group": "Spanish",
                                     "Minimum Per Interval": 1, "Coverage Days": "Mon-Fri"}]))
    if p:
        r["seen"] = {d: [E.hhmm(m) for m in range(0, 1440, 60) if E.language_rules_at(p, m, 15, day=di)]
                     for di, d in enumerate(E.DAY_NAMES)}
    return r


def main():
    out = []
    for pid, title, expectation, fn in PROBES:
        try:
            result = fn()
        except Exception as exc:
            result = {"outcome": "PROBE_ERROR", "error": f"{type(exc).__name__}: {exc}"}
        out.append({"id": pid, "probe": title, "expected": expectation, **result})
        print(json.dumps(out[-1], default=str)[:900], flush=True)
    (HERE / "PARSE_PROBES_RESULT.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
