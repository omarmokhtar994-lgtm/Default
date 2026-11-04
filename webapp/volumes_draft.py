# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "entry is manual on site per interval or excel sheet to be uploaded and make a draft of sheet can be filled").

The draft workbook: a "Read me" sheet and one sheet per channel in the input sheet's layout (intervals down, Sun to Sat across). The contacts offered go in
the left block and, optionally, the handle time in seconds in the right block. Cell B2 holds the date the week starts, so a filled sheet can be reused for
another week by changing it. Excel itself refuses text, negative numbers and out-of-range numbers in the blocks (data validation).

``parse_draft`` reads a filled draft back through the same ``parse_grid`` the pasted grids use, so a draft is checked exactly like a paste: one bad cell
and nothing from any channel is taken, each reason names its sheet and row (never the text typed in it), a coarser interval than the program's is refused.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from typing import Any, List

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.datavalidation import DataValidation

from .upload_guard import look_rows
from .volumes_io import CHANNELS, DAY_NAMES, FIRST_DAY, MAX_AHT, MAX_VOLUME, STEPS, ParsedVolumes, _norm, date_of, parse_grid
from .zipcheck import zip_problem

READ_ME = "Read me"
HEAD_ROW = 5                    # the "Interval" header row of a draft this module wrote; a filled one is searched for it
SLOTS_MAX = 288                 # a 5-minute day
MAX_SHEET_ROWS = HEAD_ROW + SLOTS_MAX + 10
NOT_A_DRAFT = "That is not a draft workbook. Download the draft, fill it in and upload it as .xlsx."
TOO_LONG = "A sheet has more rows than a day has intervals. Use the draft as downloaded and do not add rows."

INPUT = PatternFill("solid", fgColor="EEF3FA")
LABEL = PatternFill("solid", fgColor="DDE6F2")

LINES = (
    "Fill in the sheet of each channel you have numbers for. Leave the others empty; they are skipped.",
    "B2 is the date the week starts. Change it to use the sheet for another week; the dates under it follow.",
    "Contacts offered go in the left block: one whole number per interval and day. Leave a day with no data empty; inside a day, an empty cell counts as zero.",
    "The handle time in seconds is optional and goes in the right block, in the same place as its contacts.",
    "Do not add, move, rename or delete sheets, rows or columns. Do not paste formulas.",
    "On the Actuals tab, upload the file and check it. Nothing is kept until you press Save; one wrong cell and nothing is taken.",
)


def draft_workbook(week_start: date, step: int) -> bytes:
    """A draft for the week starting ``week_start`` with intervals of ``step`` minutes (see the module note for its layout)."""
    if step not in STEPS:
        raise ValueError("The interval is 5, 10, 15, 20, 30 or 60 minutes.")
    wb = Workbook()
    info = wb.active
    info.title = READ_ME
    info["A1"] = "Volumes draft"
    info["A1"].font = Font(bold=True, size=14)
    for i, line in enumerate(LINES, start=3):
        info.cell(i, 1).value = line
    info.column_dimensions["A"].width = 120
    slots = 1440 // step
    first, last = HEAD_ROW + 1, HEAD_ROW + slots
    for channel in CHANNELS:
        ws = wb.create_sheet(channel)
        ws["A1"] = f"{channel}: contacts offered per interval"
        ws["A1"].font = Font(bold=True, size=13)
        ws["A2"] = "Week starts on"
        ws["B2"] = week_start
        ws["B2"].number_format = "yyyy-mm-dd"
        ws["B2"].fill = INPUT
        ws["B2"].font = Font(bold=True)
        ws["C2"] = "Change this date to use the sheet for another week."
        ws["B3"] = "Contacts offered (whole numbers)"
        ws["J3"] = "Handle time in seconds (optional)"
        ws["A4"] = "Date"
        ws.cell(HEAD_ROW, 1).value = "Interval"
        for block in (2, 10):
            for k, name in enumerate(DAY_NAMES):
                col = block + k
                ws.cell(HEAD_ROW, col).value = name
                # the date of that weekday in the week B2 starts: counted from B2's own weekday, so a Monday-start week puts Sunday last
                ws.cell(4, col).value = f"=$B$2+MOD({k}-(WEEKDAY($B$2)-1),7)"
                ws.cell(4, col).number_format = "dd mmm"
                ws.cell(HEAD_ROW, col).fill = LABEL
                ws.cell(HEAD_ROW, col).font = Font(bold=True)
                ws.cell(HEAD_ROW, col).alignment = Alignment(horizontal="center")
                for row in range(first, last + 1):
                    ws.cell(row, col).fill = INPUT
        ws.cell(HEAD_ROW, 1).fill = LABEL
        ws.cell(HEAD_ROW, 1).font = Font(bold=True)
        for i in range(slots):
            minute = i * step
            ws.cell(first + i, 1).value = f"{minute // 60:02d}:{minute % 60:02d}"
        whole = DataValidation(type="whole", operator="between", formula1="0", formula2=str(MAX_VOLUME), allow_blank=True, showErrorMessage=True,
                               errorTitle="Contacts offered", error=f"A whole number from 0 to {MAX_VOLUME:,}.")
        secs = DataValidation(type="decimal", operator="between", formula1="1", formula2=str(int(MAX_AHT)), allow_blank=True, showErrorMessage=True,
                              errorTitle="Handle time", error=f"Seconds, from 1 to {int(MAX_AHT):,}.")
        ws.add_data_validation(whole)
        ws.add_data_validation(secs)
        whole.add(f"B{first}:H{last}")
        secs.add(f"J{first}:P{last}")
        ws.column_dimensions["A"].width = 16
        for col in range(2, 17):
            ws.column_dimensions[ws.cell(1, col).column_letter].width = 9 if col != 9 else 3
        ws.freeze_panes = ws.cell(first, 2)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _sheets(data: bytes, formulas: bool) -> List[tuple]:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=not formulas)
        out = []
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True, max_col=17, max_row=MAX_SHEET_ROWS + 50)]
            if any(any(c is not None and str(c).strip() != "" for c in r) for r in rows[MAX_SHEET_ROWS:]):
                raise ValueError(TOO_LONG)
            out.append((ws.title, [r + [None] * (17 - len(r)) for r in rows]))
        return out
    except (zipfile.BadZipFile, InvalidFileException, KeyError, IndexError, OSError, ValueError, TypeError) as exc:
        if isinstance(exc, ValueError) and str(exc) == TOO_LONG:
            raise
        raise ValueError(NOT_A_DRAFT) from exc


def _has_content(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def parse_draft(data: bytes, filename: str, step: int, today: date) -> ParsedVolumes:
    """The volumes in a filled draft (see the module note). ValueError, in words, for a file that is not a draft workbook; every cell-level reason is in
    ``problems`` of the result, and then no channel's rows are returned."""
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("Upload the draft as an .xlsx file.")
    if not data:
        raise ValueError(NOT_A_DRAFT)
    too_big = zip_problem(data)
    if too_big:
        raise ValueError(too_big)
    sheets = _sheets(data, formulas=False)
    for title, rows in sheets + _sheets(data, formulas=True):
        refused = look_rows(rows, "the draft")
        if refused:
            raise ValueError(refused)
    out = ParsedVolumes()
    for title, rows in sheets:
        if title.strip().lower() == READ_ME.lower():
            continue
        channel = next((c for c in CHANNELS if c.lower() == title.strip().lower()), None)
        if channel is None:
            out.problems.append("A sheet other than Read me, Phone, Chat or Email is in the file; remove it or rename it.")
            continue
        head = next((i for i, r in enumerate(rows[:12]) if _norm(r[0]) == "interval"), None)
        if head is None:
            out.problems.append(f"{channel}: the sheet needs the Interval header row of the downloaded draft.")
            continue
        body = [r for r in rows[head + 1:]]
        if not any(_has_content(c) for r in body for c in r[1:8]):
            out.notes.append(f"{channel}: no numbers, so it was skipped.")
            continue
        week = date_of(rows[1][1])
        if week is None:
            out.problems.append(f"{channel}: cell B2 must be the date the week starts.")
            continue
        if not FIRST_DAY <= week <= today:
            out.problems.append(f"{channel}: cell B2 is outside the range (after 2015 and not in the future).")
            continue
        offered = [[r[0], *r[1:8]] for r in rows]
        aht = [[r[0], *r[9:16]] for r in rows]
        try:
            got = parse_grid(offered, week, channel, aht, step, today)
        except ValueError as exc:
            out.problems.append(f"{channel}: {exc}")
            continue
        for problem in got.problems:
            text = problem if problem.startswith(f"{channel}:") else f"{channel}: {problem}"
            if text not in out.problems:
                out.problems.append(text)
        if not got.problems:
            out.rows.update(got.rows)
            out.summary.update(got.summary)
            out.notes.append(f"{channel}: read the week of {week:%a %d %b %Y}.")
    if not out.problems and not out.rows:
        out.problems.append("The draft has no numbers in it.")
    if out.problems:
        out.rows, out.summary = {}, {}
    return out


def is_draft(data: bytes, filename: str) -> bool:
    """Whether an upload is a draft workbook (an .xlsx with a Read me sheet and a sheet for a channel); anything else is left to the other readers."""
    if not filename.lower().endswith(".xlsx") or zip_problem(data):
        return False
    try:
        names = {n.strip().lower() for n in load_workbook(io.BytesIO(data), read_only=True).sheetnames}
    except (zipfile.BadZipFile, InvalidFileException, KeyError, IndexError, OSError, ValueError, TypeError):
        return False
    return READ_ME.lower() in names and any(c.lower() in names for c in CHANNELS)
