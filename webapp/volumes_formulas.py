# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "I want the one equals =agents() in Excel"): a workbook whose people-needed grid is made of live formulas.

One sheet per channel with the program's own settings as inputs (handle time, interval, service level target, answer time, highest occupancy, chats at once,
shrinkage), the forecast contacts per interval and day (Sun to Sat, intervals down, like the input sheet), the people needed worked out by the one-cell
formula of ``webapp/excel_agents.py`` (it works in every Excel and in LibreOffice, with nothing to set up), and, beside it, the people the site worked out
when the file was made. A cell counts the intervals where the two differ, so the sheet shows whether it still agrees with the site (it will not once an input or
a forecast cell is changed, which is the point). The Read me sheet carries the Excel 365 ``=AGENTS(...)`` definition as text to paste into Name Manager.

Email uses the workload method (contacts x handle time over the productive time in the interval), as on the site.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import excel_agents as X
from .volumes_io import CHANNELS, DAY_NAMES

GRID_ROW = 14                      # the first row of the grids (their header is the row above, their group labels two above)
CONTACTS, LIVE, SITE = 2, 10, 18   # first column of each grid (B, J, R)
INPUT = PatternFill("solid", fgColor="EEF3FA")
LABEL = PatternFill("solid", fgColor="DDE6F2")

INPUTS = (  # (row, label, key in the settings, note by channel)
    (4, "Handle time (seconds)", "aht", {}),
    (5, "Interval (seconds)", "interval", {}),
    (6, "Service level target (%)", "sl_target", {"Email": "not used for email"}),
    (7, "Answer within (seconds)", "sl_seconds", {"Email": "not used for email"}),
    (8, "Highest occupancy (%)", "occupancy", {}),
    (9, "Chats at once per agent", "concurrency", {"Phone": "not used for phone", "Email": "not used for email"}),
    (10, "Shrinkage (%)", "shrinkage", {}),
)

LINES = (
    "What this is: the people needed on the floor per interval for one week, with the Erlang calculation as live Excel formulas. Change a blue cell (an input, or a number "
    "of contacts) and the middle grid recalculates. The right grid is what the site worked out when this file was made, and the cell beside \"Intervals that differ\" "
    "counts where the two differ, so it is 0 until you change something.",
    "The formula in the middle grid is one ordinary cell formula: it uses only POISSON, SUMPRODUCT, ROW, INDIRECT, EXP, ROUNDUP, INT and IF, so it works in every "
    "version of Excel and in LibreOffice, with no macro, no add-in and no array entry. Copy a cell of the grid and paste it into your own sheet; point its references "
    "at your contacts, handle time and settings.",
    "Excel 365 can have a function of its own, =AGENTS(calls, aht, interval_seconds, target, answer_seconds, max_occupancy). Add it once: Formulas, Name Manager, New; "
    "type the name (AGENTS); paste the definition below into Refers to; press OK. Then, for example: =AGENTS(B14, $B$4, $B$5, $B$6/100, $B$7, $B$8/100). The target and the "
    "occupancy are fractions (0.8 is 80%). SERVICELEVEL is the same for the share answered in time with a given number of agents.",
    "POISSON is the name Microsoft keeps for compatibility; it works in every version today. If a future Excel no longer has it, replace POISSON( with POISSON.DIST( in the formula "
    "(same arguments). The cell beside \"Intervals that differ\" shows at once if a different Excel calculates anything differently.",
    "Method: traffic in Erlangs is contacts x handle time / interval. The agents needed are the fewest above the traffic with the Erlang C service level at least the "
    "target and the occupancy (traffic / agents) at most the highest occupancy; comparisons are made to 12 places, as a spreadsheet does. Erlang C assumes nobody abandons, so it "
    "over-staffs where callers do. Chat divides the handle time by the chats at once. Email is the workload method. These are people on the floor; the schedule engine "
    "adds shrinkage itself.",
)


def formulas_workbook(week_start: date, step: int, forecasts: Dict[str, Dict[str, Any]], settings: Dict[str, Dict[str, Any]]) -> bytes:
    """The workbook for the channels in ``forecasts`` (the dicts ``VolumeBook.forecast`` gives, with their grids of calls and people needed); ValueError when none
    has a grid of people needed."""
    chosen = [ch for ch in CHANNELS if ch in forecasts and forecasts[ch].get("calls") and forecasts[ch].get("needs")]
    if not chosen:
        raise ValueError("There is no grid of people needed to put in a workbook.")
    wb = Workbook()
    info = wb.active
    info.title = "Read me"
    info["A1"] = f"Volumes with live formulas, week of {week_start:%a %d %b %Y}"
    info["A1"].font = Font(bold=True, size=14)
    row = 3
    for line in LINES:
        info.cell(row, 1).value = line
        info.cell(row, 1).alignment = Alignment(wrap_text=True, vertical="top")
        row += 2
    for definition in X.lambda_definitions().strip().split("\n\n"):
        name, text = definition.split("\n", 1)
        info.cell(row, 1).value = name
        info.cell(row, 1).font = Font(bold=True)
        cell = info.cell(row + 1, 1)
        cell.value = text.strip()
        cell.data_type = "s"                                   # it starts with "=": it is text to paste, not a formula to run
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 3
    info.column_dimensions["A"].width = 130
    for ch in chosen:
        f, s = forecasts[ch], settings[ch]
        slots = len(f["calls"][0])
        last = GRID_ROW + slots - 1
        ws = wb.create_sheet(ch)
        ws["A1"] = f"{ch}: people needed on the floor, with live formulas"
        ws["A1"].font = Font(bold=True, size=13)
        ws["A2"] = "Week starting"
        ws["B2"] = week_start
        ws["B2"].number_format = "yyyy-mm-dd"
        values = {"aht": f["aht"], "interval": step * 60, "sl_target": s["sl_target"], "sl_seconds": s["sl_seconds"], "occupancy": s["occupancy"],
                  "concurrency": s["concurrency"] if ch == "Chat" else 1, "shrinkage": s["shrinkage"]}
        for r, label, key, notes in INPUTS:
            ws.cell(r, 1).value = label
            ws.cell(r, 2).value = values[key]
            ws.cell(r, 2).fill = INPUT
            if ch in notes:
                ws.cell(r, 3).value = notes[ch]
        aht = "($B$4/$B$9)" if ch == "Chat" else "$B$4"
        live_range = f"{get_column_letter(LIVE)}{GRID_ROW}:{get_column_letter(LIVE + 6)}{last}"
        site_range = f"{get_column_letter(SITE)}{GRID_ROW}:{get_column_letter(SITE + 6)}{last}"
        ws["D4"], ws["F4"] = "Hours needed on the floor", f"=SUM({live_range})*$B$5/3600"
        ws["D5"], ws["F5"] = "People at the busiest interval", f"=MAX({live_range})"
        ws["D6"], ws["F6"] = "People to schedule at the peak, with shrinkage", "=F5/(1-$B$10/100)"
        ws["D7"], ws["F7"] = "Intervals that differ from the site", f"=SUMPRODUCT(--(ROUND({live_range},2)<>ROUND({site_range},2)))"
        ws["F8"] = '=IF(F7=0,"Every interval matches the site\'s figures.","Some intervals differ from the site\'s figures because an input or a number of contacts was changed.")'
        ws["F4"].number_format, ws["F6"].number_format = "#,##0.0", "0.0"
        for start, label in ((CONTACTS, "Contacts forecast (change a blue cell to try another)"), (LIVE, "People needed on the floor (live formulas)"),
                             (SITE, "People needed, as the site worked them out")):
            ws.cell(GRID_ROW - 2, start).value = label
            ws.cell(GRID_ROW - 2, start).font = Font(bold=True)
            for d, name in enumerate(DAY_NAMES):
                head = ws.cell(GRID_ROW - 1, start + d)
                head.value = name
                head.fill = LABEL
                head.font = Font(bold=True)
                head.alignment = Alignment(horizontal="center")
        ws.cell(GRID_ROW - 1, 1).value = "Interval"
        ws.cell(GRID_ROW - 1, 1).fill = LABEL
        ws.cell(GRID_ROW - 1, 1).font = Font(bold=True)
        for i in range(slots):
            r = GRID_ROW + i
            minute = i * step
            ws.cell(r, 1).value = f"{minute // 60:02d}:{minute % 60:02d}"
            for d in range(7):
                calls_ref = f"{get_column_letter(CONTACTS + d)}{r}"
                ws.cell(r, CONTACTS + d).value = int(f["calls"][d][i])
                ws.cell(r, CONTACTS + d).fill = INPUT
                if ch == "Email":
                    formula = f"=IF({calls_ref}<=0,0,ROUND({calls_ref}*$B$4/($B$5*($B$8/100)),2))"
                else:
                    formula = "=" + X.agents_formula(calls_ref, aht, "$B$5", "($B$6/100)", "$B$7", "($B$8/100)")
                ws.cell(r, LIVE + d).value = formula
                ws.cell(r, SITE + d).value = f["needs"][d][i]
                if ch == "Email":
                    ws.cell(r, LIVE + d).number_format = ws.cell(r, SITE + d).number_format = "0.00"
        ws.column_dimensions["A"].width = 38
        for col in range(2, SITE + 7):
            ws.column_dimensions[get_column_letter(col)].width = 9 if col not in (9, 17) else 3
        ws.freeze_panes = ws.cell(GRID_ROW, 2)
    wb.calculation.fullCalcOnLoad = True
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
