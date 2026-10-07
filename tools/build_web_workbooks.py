#!/usr/bin/env python3
# © 2026 Omar Mokhtar. All rights reserved.
"""Build the two clean input workbooks the website offers on its home page.

    python3 tools/build_web_workbooks.py [OUT_DIR]      (default webapp/workbooks)

Example: the synthetic SYNTH_M2 workbook (made-up "Synth Agent" names, a
roster that schedules) rebuilt by tools/build_input_template.py, whose own
check proves the engine reads it exactly as it reads the source; nothing is
written if it would not.

Blank: the example with people, demand, shrinkage, preferences, fixed
requests, last week's shifts and languages cleared, the program name and
headcount emptied, and the 30-minute demand tabs selected (the interval the
team's programs use). Every tab, dropdown, the Start Here checklist and the
Shift Library stay.
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_input_template as B  # noqa: E402

SOURCE = "fixtures/synthetic_suite/SYNTH_M2_MULTI_START_WITH_BREAKS.xlsx"
EXAMPLE_NAME = "Scheduler_Input_Example.xlsx"
BLANK_NAME = "Scheduler_Input_Blank.xlsx"
# sheet: (first data row, first data column); everything from there on is cleared
CLEARED = {
    "Schedule": (3, 1), "Previous week scheduled": (3, 1), "Preference": (3, 1), "Fixed Request": (3, 1),
    "Language Setup": (3, 1), "Coverage Split": (6, 1),
    "FT Wise 15 Min": (3, 2), "FT Wise 30 Min": (3, 2), "FT Wise 60 Min": (3, 2),
    "Shrinkage 15 Min": (3, 2), "Shrinkage 30 Min": (3, 2), "Shrinkage 60 Min": (3, 2),
}
# the header the clearing relies on: (row, column, text)
HEADERS = {
    "Schedule": (2, 1, "Slot"), "Previous week scheduled": (2, 1, "Slot"), "Preference": (2, 1, "Associate Name"),
    "Fixed Request": (2, 1, "Active?"), "Language Setup": (2, 1, "Language"), "Coverage Split": (4, 1, "Coverage Group"),
    **{f"{kind} {n} Min": (2, 1, "Interval") for kind in ("FT Wise", "Shrinkage") for n in (15, 30, 60)},
}
BLANK_SETTINGS = {"Program Name": None, "Count of Associates": None, "Interval Minutes": "30",
                  "Requirements Source": "FT Wise 30 Min", "Shrinkage Source": "Shrinkage 30 Min"}


def blank_from(example: Path, blank: Path) -> None:
    wb = load_workbook(example)
    for sheet, (row, col, text) in HEADERS.items():
        found = wb[sheet].cell(row, col).value
        if found != text:
            raise SystemExit(f"{sheet}: expected the header {text!r} at row {row}, found {found!r}; nothing written")
    for sheet, (first_row, first_col) in CLEARED.items():
        for cells in wb[sheet].iter_rows(min_row=first_row, min_col=first_col):
            for cell in cells:
                if cell.value is not None and not str(cell.value).startswith("="):
                    cell.value = None
    settings = wb["Instructions"]
    seen = set()
    for cells in settings.iter_rows():
        name = cells[1].value
        if name in BLANK_SETTINGS:
            old = cells[2].value
            new = BLANK_SETTINGS[name]
            cells[2].value = int(new) if isinstance(old, int) and new is not None else new
            seen.add(name)
    missing = set(BLANK_SETTINGS) - seen
    if missing:
        raise SystemExit(f"Instructions rows not found: {sorted(missing)}; nothing written")
    wb.save(blank)


def main(argv: list) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "webapp" / "workbooks"
    out.mkdir(parents=True, exist_ok=True)
    example = out / EXAMPLE_NAME
    if B.main(["build", str(ROOT / SOURCE), str(example)]) != 0:
        return 2
    blank_from(example, out / BLANK_NAME)
    print(f"{BLANK_NAME}: every tab and dropdown, no people or demand, 30-minute tabs selected")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
