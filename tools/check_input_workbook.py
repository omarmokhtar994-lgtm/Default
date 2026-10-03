#!/usr/bin/env python3
"""Check an input workbook in seconds, before spending an hour solving it.

Runs exactly the checks the production run starts with, and nothing else:
  1. the engine's input contract (the run refuses a workbook that fails it);
  2. the independent validator's raw-workbook cross-check (roster, demand,
     leave/OFF cells re-read without engine code);
  3. whether every dropdown rejects typed values (a typed "Yes." or "Enable"
     in a yes/no cell fails the contract; an enforced dropdown prevents it).

    python3 tools/check_input_workbook.py WORKBOOK.xlsx [--acknowledge-departed "Name A; Name B"]

Exit 0: the workbook will be accepted. Exit 1: it will be refused; the
messages say which cell to fix. Nothing is written to the workbook.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
sys.path.insert(0, str(ROOT / "engine" / "tools"))
sys.path.insert(0, str(ROOT / "tools"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("workbook", type=Path)
    ap.add_argument("--acknowledge-departed", default="",
                    help="semicolon-separated names; prefer the workbook's 'Known Departed Associates' row")
    args = ap.parse_args()
    import l632_universal_scheduler as E
    import independent_validator as V
    from enforce_workbook_validations import unenforced_count

    book = args.workbook
    if not book.is_file():
        print(f"no such file: {book}")
        return 1
    print(f"workbook : {book.name}")
    print(f"engine   : {E.VERSION}")
    override = [n.strip() for n in args.acknowledge_departed.split(";") if n.strip()] or None
    try:
        parsed = E.parse_input(book, acknowledged_departed_override=override)
    except Exception as exc:  # the run would stop here too; say why in plain words
        print(f"\nREFUSED - the workbook could not be read: {type(exc).__name__}: {exc}")
        return 1

    day_hours = [round(sum(float(x or 0) for x in day) * parsed.interval_minutes / 60.0, 1)
                 for day in parsed.requirements]
    print(f"program  : {parsed.program_name}")
    print(f"roster   : {len(parsed.associates)} associates; interval {parsed.interval_minutes} min")
    print(f"demand   : FTE-hours Sun..Sat {day_hours}")
    print(f"requests : preferences {'on' if parsed.use_preferences else 'off'}, "
          f"fixed requests {'on' if parsed.fixed_enabled else 'off'}, "
          f"leave {'on' if parsed.leave_enabled else 'off'}")
    notes = [w for w in parsed.parser_warnings if not str(w).startswith("HARD_")]
    for w in notes[:15]:
        print(f"note     : {w}")

    failed = False
    contract = E.validate_input_contract(parsed)
    problems = contract.get("failures", [])
    print(f"\n1. input contract          : {'PASS' if not problems else 'FAIL'}")
    for f in problems:
        failed = True
        print(f"   - {f.get('detail') or f.get('code')}")

    cross = V.independent_input_crosscheck(book, parsed)
    print(f"2. independent cross-check : "
          f"{'FAIL' if cross['mismatches'] else 'PASS'}  {cross['checks']}")
    for m in cross["mismatches"]:
        failed = True
        print(f"   - {m}")
    for n in cross["not_checked"]:
        print(f"   - not checked: {n['check']} ({n['reason']})")

    total, open_ = unenforced_count(book)
    print(f"3. dropdowns               : {total} validations, {open_} accept typed values")
    if open_:
        print("   Typed values outside a list are not blocked in this workbook. Fix with:\n"
              f"   python3 tools/enforce_workbook_validations.py \"{book}\"   (cell values stay unchanged)")

    lines, conflicts = language_hours_report(E, parsed)
    for line in lines:
        print(line)
    failed = failed or conflicts

    print("\nRESULT:", "REFUSED - fix the items above" if failed else "ACCEPTED - ready to run")
    return 1 if failed else 0


def language_hours_report(E, parsed) -> list:
    """Say whether Language Setup's Coverage Start/End limit who works when.

    They do only when the Instructions row "Language Working Window" is set:
    with it OFF (the default) an English associate can be scheduled in the
    International hours and the other way round, and nothing in the run looks
    wrong. MINIMUM_ROWS enforces only rows whose Minimum Per Interval is above
    0. This changes no result; it makes the setting visible before the run.
    """
    mode = getattr(parsed, "language_working_window_mode", "OFF")
    windows = getattr(parsed, "language_windows", {}) or {}
    lines = [f"4. language hours          : Language Working Window = {mode}"]
    if not windows:
        lines.append("   no Language Setup row limits working hours")
        return lines, False
    by_language: dict = {}
    for key, value in windows.items():
        language, _, day = key.partition("@@")
        for start, end, has_minimum in E._coerce_language_window_entries(value):
            days = [int(day)] if day else list(range(7))
            for d in days:
                by_language.setdefault(language, {}).setdefault(d, []).append((start, end, has_minimum))
    unenforced_rows = 0
    for language in sorted(by_language):
        per_day = by_language[language]
        parts = []
        for d in range(7):
            entries = per_day.get(d)
            if not entries:
                parts.append(f"{E.DAY_NAMES[d]} none")
                continue
            parts.append(E.DAY_NAMES[d] + " " + "+".join(f"{E.hhmm(s)}-{E.hhmm(e)}" for s, e, _m in entries))
            if mode == "MINIMUM_ROWS":
                unenforced_rows += sum(1 for _s, _e, m in entries if not m)
        lines.append(f"   {language}: " + ", ".join(parts))
        missing = [E.DAY_NAMES[d] for d in range(7) if d not in per_day]
        if missing and mode != "OFF":
            lines.append(f"   note: {language} has no row for {', '.join(missing)}; on those days its "
                         "associates may start at any hour")
    if mode == "OFF":
        lines.append("   WARNING: these hours do NOT limit when each language's associates work "
                     "(they only set the minimum-per-interval hours). To keep each language inside its "
                     "hours set Instructions > Language Working Window = ALL_ROWS.")
    elif unenforced_rows:
        lines.append(f"   WARNING: MINIMUM_ROWS enforces only rows with Minimum Per Interval above 0; "
                     f"{unenforced_rows} language-day window(s) above have minimum 0 and are not enforced. "
                     "Use ALL_ROWS to enforce every row.")
    lines.append("   A shift is inside a window when it STARTS inside it (it may run past the window's end).")
    # A fixed request is a hard rule and so is an enforced window: one that
    # starts outside its associate's window makes the run infeasible, and the
    # engine only says "no schedule satisfies all hard rules". Name each one.
    check_mode = mode if mode != "OFF" else "ALL_ROWS"
    conflicts = fixed_requests_outside_language_hours(E, parsed, check_mode)
    if conflicts and mode != "OFF":
        lines.append(f"   FAIL: {len(conflicts)} fixed request(s) start outside the associate's language hours; "
                     "the run cannot satisfy both. Change the request, the associate's Language, or the window:")
    elif conflicts:
        lines.append(f"   note: if you set ALL_ROWS, {len(conflicts)} fixed request(s) would start outside the "
                     "associate's language hours and the run would be refused. Fix these first:")
    for name, language, day, shift, allowed in conflicts[:20]:
        lines.append(f"     - {name} ({language}) {day}: fixed {shift}, {language} hours {allowed}")
    if len(conflicts) > 20:
        lines.append(f"     ... and {len(conflicts) - 20} more")
    return lines, bool(conflicts) and mode != "OFF"


def fixed_requests_outside_language_hours(E, parsed, mode: str) -> list:
    """Fixed shift requests that start outside the associate's language window
    under `mode`. The engine's own function, so the run names the same ones."""
    import copy
    probe = copy.copy(parsed)
    probe.language_working_window_mode = mode
    return [(r["associate"], r["language"], r["day"], r["shift"], r["window"])
            for r in E.fixed_requests_outside_language_windows(probe)]

if __name__ == "__main__":
    raise SystemExit(main())
