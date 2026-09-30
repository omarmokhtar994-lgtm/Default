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

    print("\nRESULT:", "REFUSED - fix the items above" if failed else "ACCEPTED - ready to run")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
