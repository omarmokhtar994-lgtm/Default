"""Rebuild an input workbook into the two-tab production template.

Sheet names stay 'Instructions' and 'Engine Defaults' because the engine
resolves those by alias; only their content and presentation change.

  Instructions   -> the ~20 decisions a scheduler makes per schedule, grouped,
                    with dropdowns where the value is an enum.
  Engine Defaults-> the engine tuning rows, defaults intact, marked do-not-touch.

Nothing is invented: every value is carried across from the source workbook.
Rows the engine does not read are dropped; rows it reads but the workbook never
set are added at their engine default so they are visible and changeable.
"""
import shutil, sys
from copy import copy
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

YES_NO = '"Yes,No"'
# Restored from RC5's template (audit F-17): the language working window and the
# per-language coverage days were settable from RC5's template, not from this one.
LANGUAGE_WINDOW_CHOICES = '"OFF,MINIMUM_ROWS,ALL_ROWS,REQUIRED_LANGUAGE_ONLY"'
LANGUAGE_DAYS_CHOICES = '"All,Weekdays,Weekends,Sun-Thu,Mon-Fri,Sun,Mon,Tue,Wed,Thu,Fri,Sat"'
SETUP_LAYOUT = [
    ("Case Setup", [
        ("Program Name", None),
        ("Count of Associates", None),
        ("Allow Headcount Mismatch", YES_NO),
        ("Interval Minutes", '"15,30,60"'),
        ("Requirements Source", '"FT Wise 15 Min,FT Wise 30 Min,FT Wise 60 Min"'),
        ("Shrinkage Source", '"Shrinkage 15 Min,Shrinkage 30 Min,Shrinkage 60 Min"'),
    ]),
    ("How To Run", [
        ("Run Stage", '"Before Breaks Only,Full Schedule"'),
        ("Run Depth", '"Quick,Deep,Overnight"'),
        # After the schedule is chosen: re-deal same-day shifts between
        # interchangeable associates so each week is more uniform. Blank = the
        # engine default; nothing it measures may get worse.
        ("Shift Consistency Polish", YES_NO),
    ]),
    ("Coverage", [
        ("Target", None),
        ("Target Priority Confirmed", YES_NO),
        ("Minimum Per Interval", None),
        ("Hard Floor Solver Constraint Enabled", YES_NO),
        ("Blank Interval Staffing Rule", None),
    ]),
    ("Shift & OFF", [
        ("Allowed Shift Durations Hours", None),
        ("Use 11H/3OFF", YES_NO),
        ("Strict OFF Count", YES_NO),
        ("Separate OFF Days", YES_NO),
        ("Rest Gap Hours", None),
        ("Count of Different Shifts Per week", None),
    ]),
    ("Requests", [
        ("Fixed Request Use", YES_NO),
        ("Hard OFF Preferences", YES_NO),
        ("Leave Enabled", YES_NO),
        ("Use Preferences", YES_NO),
        # Names (comma or semicolon separated) of people on the previous-week
        # sheet who have left. Without it such a row fails the input contract,
        # and there was no visible place to say so. One name never silences
        # another: each must be listed.
        ("Known Departed Associates", None),
    ]),
    ("Opening Guard", [
        ("Opening Guard Enabled", YES_NO),
        ("Opening Minimum FTE", None),
        ("Opening Guard Intervals", None),
    ]),
    ("Breaks", [
        ("Short Break Count", None),
        ("Short Break Duration Minutes", None),
        ("Lunch Count", None),
        ("Lunch Duration Minutes", None),
        ("Break Preferred Gap Minutes", None),
        ("Break Absolute Minimum Gap Minutes", None),
        ("Break Normal Maximum Gap Minutes", None),
        ("Allow Back-to-Back Breaks", YES_NO),
    ]),
    ("Language / Skill", [
        ("Language Working Window", LANGUAGE_WINDOW_CHOICES),
    ]),
    ("Exception Policy", [
        ("Critical Coverage No-Break Exception Enabled", YES_NO),
        ("Critical Coverage No-Break Max Associate-Days", None),
    ]),
    ("Release Quality", [
        ("Production Quality Gate Mode", '"Warn,Fail,Off"'),
        ("Minimum After Break Target Ratio", None),
        ("Protected Before80 Minimum Intervals", None),
        ("Protected After80 Minimum Intervals", None),
    ]),
]
GATE_MODE = '"Warn,Fail,Off"'
ADVANCED_LAYOUT = [
    ("Demand Fit", [("Demand Fit Guard Enabled", '"Auto,Yes,No"'),
                    ("Demand Fit Minimum Active Minutes", None),
                    ("Demand Fit Minimum Active Ratio", None),
                    ("Demand Fit Maximum Blank Span Minutes", None)]),
    ("Overage Control", [("Overage Control Enabled", YES_NO), ("Overage Soft Cap", None),
                         ("Overage Severe Cap", None), ("Overage Extreme Cap", None),
                         ("Overage Penalty Weight", None)]),
    ("Break Concurrency", [("Maximum Concurrent Break Ratio", None),
                           ("Maximum Concurrent Breaks", None),
                           ("Break Concurrency Gate Mode", GATE_MODE)]),
    ("Week Boundary", [("Next Sunday Balance Enabled", YES_NO), ("Next Sunday Overage Cap", None),
                       ("Next Sunday Maximum Adjacent Raw Change", None),
                       ("Next Sunday Balance Gate Mode", GATE_MODE)]),
    ("Language / Skill", [("Language Operational Reserve Enabled", YES_NO),
                          ("Language Operational Reserve Extra FTE", None),
                          ("Language Reserve Gate Mode", GATE_MODE),
                          ("Qualified Language Break Certificate Enabled", YES_NO)]),
    ("Whole Week Balance", [("Whole Week Balance Enabled", YES_NO), ("Whole Week Overage Cap", None)]),
    ("Benchmarks", [("Quality Benchmark Tolerance Intervals", None)]),
]
DEAD_ROWS = {"rc9.1deepdefaultseconds", "rc9.1fulldefaultseconds",
             "rc9.1stage2searchorder", "rc9.1jointbudgetpolicy"}
# Rows the planner was asked to drive from the sheet. Leaving them blank is
# honest but useless: a dropdown you have to discover is not a choice you were
# offered. These two are seeded with the exact value the engine falls back to
# when the cell is empty, so pre-filling them changes no behaviour - it only
# makes the setting visible. Nothing else is seeded, because pre-filling a row
# whose default the engine may revise would freeze that default into the
# contract without anyone deciding to.
SEEDED_DEFAULTS = {"runstage": "Full Schedule", "rundepth": "Quick"}  # the engine's own fallback depth is QUICK

HDR = PatternFill("solid", fgColor="1F3864")
SECTION = PatternFill("solid", fgColor="D9E2F3")
WARN = PatternFill("solid", fgColor="FFF2CC")
THIN = Border(*[Side(style="thin", color="BFBFBF")] * 4)

def enforced_list_validation(choices):
    """A dropdown that rejects anything outside its list.

    openpyxl's DataValidation leaves showErrorMessage off, which lets Excel
    accept any typed value: "Enable" in a Yes/No row then reads as No
    (audit finding F-18). RC5's shipped workbooks enforced every list.
    """
    dv = DataValidation(type="list", formula1=choices, allow_blank=True)
    dv.errorStyle = "stop"
    dv.showErrorMessage = True
    dv.errorTitle = "Value not allowed"
    dv.error = "Choose a value from the list. Typed values outside the list are not accepted."
    return dv


def ensure_language_setup_controls(wb):
    """Add the day-scope field and enforced dropdown to an existing skill sheet (from RC5)."""
    ws = next((wb[name] for name in ("Language Setup", "Skill Setup", "Skills Setup")
               if name in wb.sheetnames), None)
    if ws is None:
        return False
    header = None
    for r in range(1, ws.max_row + 1):
        labels = {norm(ws.cell(r, c).value) for c in range(1, ws.max_column + 1)}
        if "language" in labels and any("minimum" in label for label in labels):
            header = r
            break
    if header is None:
        return False
    headers = {norm(ws.cell(header, c).value): c for c in range(1, ws.max_column + 1)}
    days_col = next((c for label, c in headers.items()
                     if "coveragedays" in label or "activedays" in label or "daysactive" in label), None)
    if days_col is None:
        days_col = ws.max_column + 1
        ws.cell(header, days_col, "Coverage Days")
        if days_col > 1:
            ws.cell(header, days_col)._style = copy(ws.cell(header, days_col - 1)._style)
    ws.column_dimensions[ws.cell(header, days_col).column_letter].width = 20
    dv = enforced_list_validation(LANGUAGE_DAYS_CHOICES)
    dv.errorTitle = "Invalid coverage days"
    dv.error = "Choose a listed day or range, or type a supported value such as Sun-Thu."
    ws.add_data_validation(dv)
    for r in range(header + 1, ws.max_row + 1):
        language = ws.cell(r, headers.get("language", 1)).value
        if language not in (None, ""):
            cell = ws.cell(r, days_col)
            if cell.value in (None, ""):
                cell.value = "All"
            dv.add(cell)
    return True

def norm(s): return "".join(ch for ch in str(s or "").lower() if ch.isalnum() or ch == ".")

def _two_tab_layout(ws):
    """True when the sheet already has this template's Section|Instruction|Value|Notes header."""
    for r in ws.iter_rows(min_row=1, max_row=8, values_only=True):
        labels = [norm(c) for c in r[:3]]
        if labels[1:3] == ["instruction", "value"]:
            return True
    return False


def existing_values(wb):
    values = {}
    for name in ("Instructions", "Engine Defaults"):
        if name not in wb.sheetnames: continue
        # A workbook already rebuilt by this template has Section|Instruction|
        # Value|Notes on BOTH tabs. Reading its Engine Defaults as the legacy
        # Key|Value layout dropped every set value on a second rebuild (e.g.
        # "Demand Fit Guard Enabled = Auto" came back blank, i.e. No).
        two_tab = name == "Instructions" or _two_tab_layout(wb[name])
        for r in wb[name].iter_rows(values_only=True):
            if two_tab:
                key, val = (r[1] if len(r) > 1 else None, r[2] if len(r) > 2 else None)
            else:
                key, val = (r[0], r[1] if len(r) > 1 else None)
            if key and norm(key) not in DEAD_ROWS:
                values.setdefault(norm(key), val)
    return values

def write_sheet(wb, title, layout, values, blurb, start_note=None):
    if title in wb.sheetnames: del wb[title]
    ws = wb.create_sheet(title)
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 48
    ws.column_dimensions["C"].width = 30
    ws.column_dimensions["D"].width = 62
    ws["A1"] = blurb
    ws["A1"].font = Font(bold=True, color="FFFFFF", size=12)
    ws["A1"].fill = HDR
    ws.merge_cells("A1:D1")
    if start_note:
        ws["A2"] = start_note
        ws["A2"].fill = WARN
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="center")
        ws.merge_cells("A2:D2")
        ws.row_dimensions[2].height = 30
    row = 4 if start_note else 3
    for col, head in zip("ABCD", ("Section", "Instruction", "Value", "Notes")):
        c = ws[f"{col}{row}"]; c.value = head
        c.font = Font(bold=True, color="FFFFFF"); c.fill = HDR
    row += 1
    validations = {}
    written = 0
    for section, items in layout:
        first = True
        for key, choices in items:
            v = values.get(norm(key))
            if v in (None, "") and norm(key) in SEEDED_DEFAULTS:
                v = SEEDED_DEFAULTS[norm(key)]
            ws.cell(row, 1, section if first else "").fill = SECTION if first else PatternFill()
            if first: ws.cell(row, 1).font = Font(bold=True)
            ws.cell(row, 2, key)
            ws.cell(row, 3, v if v is not None else "")
            for col in range(1, 5): ws.cell(row, col).border = THIN
            if choices:
                dv = validations.get(choices)
                if dv is None:
                    dv = enforced_list_validation(choices)
                    ws.add_data_validation(dv); validations[choices] = dv
                dv.add(ws.cell(row, 3))
            if v is None:
                ws.cell(row, 4, "not set - engine default applies")
                ws.cell(row, 4).font = Font(italic=True, color="808080")
            first = False
            row += 1; written += 1
        row += 1
    ws.freeze_panes = ws.cell(row=(5 if start_note else 4), column=1)
    return written

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
shutil.copy(src, dst)
wb = load_workbook(dst)
values = existing_values(wb)
n1 = write_sheet(wb, "Instructions", SETUP_LAYOUT, values,
                 "SETUP - the decisions you make for this schedule",
                 "Fill the Value column. Cells with a dropdown accept only the listed options. "
                 "Anything left blank uses the engine default and is marked in Notes.")
n2 = write_sheet(wb, "Engine Defaults", ADVANCED_LAYOUT, values,
                 "ADVANCED - engine tuning. Defaults are production-tested.",
                 "Change these only with a specific reason. They are not per-schedule business "
                 "settings; the values here are the ones every released result was measured with.")
ensure_language_setup_controls(wb)
# Input Checks was a static snapshot that said PASS no matter what the roster held.
if "Input Checks" in wb.sheetnames:
    del wb["Input Checks"]
    ws = wb.create_sheet("Input Checks")
    ws["A1"] = "Input Checks are performed by the engine, not by this sheet."
    ws["A1"].font = Font(bold=True, color="FFFFFF"); ws["A1"].fill = HDR
    ws.merge_cells("A1:F1"); ws.column_dimensions["A"].width = 110
    ws["A3"] = ("The previous version of this tab held hardcoded PASS/WARN text. It reported "
                "PASS regardless of what the roster, demand or language setup actually "
                "contained, so it could not catch the errors it appeared to check for.")
    ws["A4"] = ("The engine runs the real pre-solver contract validation on every run and writes "
                "the result to the audit JSON as pre_solver_contract_validation, with a specific "
                "code, day and time for each failure. That is the authoritative check.")
    for r in (3, 4):
        ws[f"A{r}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 45
# Coverage Split: which group STAFFS which window, as opposed to Language
# Setup's weaker "at least N of them are present". Written empty on purpose -
# rows here change the contract, so a workbook that never asked for the feature
# must not acquire it just by being rebuilt through the template.
if "Coverage Split" in wb.sheetnames:
    del wb["Coverage Split"]
ws = wb.create_sheet("Coverage Split")
ws["A1"] = "Coverage Split - which coverage group is responsible for staffing which hours"
ws["A1"].font = Font(bold=True, color="FFFFFF"); ws["A1"].fill = HDR
ws.merge_cells("A1:G1")
ws["A2"] = ("Optional. Leave empty and nothing changes. Add a row and that group must field the "
            "WHOLE requirement in its window - not the 'Minimum Per Interval' floor from Language "
            "Setup, which only guarantees one qualified person is present. Coverage Group must "
            "match the Coverage Group column in Language Setup. If two windows overlap, the "
            "groups cover those hours TOGETHER against one requirement - their people pool and "
            "the higher Coverage Ratio applies; the requirement is never charged twice.")
ws["A2"].fill = WARN
ws["A2"].alignment = Alignment(wrap_text=True, vertical="center")
ws.merge_cells("A2:G2"); ws.row_dimensions[2].height = 46
heads = ["Coverage Group", "Start", "End", "Coverage Ratio", "Exclusive?", "Active?", "Notes"]
for col, head in enumerate(heads, start=1):
    c = ws.cell(4, col, head)
    c.font = Font(bold=True, color="FFFFFF"); c.fill = HDR; c.border = THIN
notes = [
    "Name from Language Setup's Coverage Group column.",
    "Window opens (e.g. 03:00).",
    "Window closes; may cross midnight (e.g. 16:00).",
    "Blank = the workbook's Minimum Per Interval. 1.0 = full requirement.",
    "Yes = only this group may work these hours at all.",
    "No or blank = row ignored.",
    "",
]
for col, note in enumerate(notes, start=1):
    c = ws.cell(5, col, note)
    c.font = Font(italic=True, color="808080", size=9)
    c.alignment = Alignment(wrap_text=True, vertical="top")
ws.row_dimensions[5].height = 40
for col, width in zip("ABCDEFG", (22, 12, 12, 16, 13, 11, 46)):
    ws.column_dimensions[col].width = width
dv_yesno = enforced_list_validation(YES_NO)
ws.add_data_validation(dv_yesno)
for row in range(6, 26):
    for col in range(1, 8):
        ws.cell(row, col).border = THIN
    dv_yesno.add(ws.cell(row, 5))
    dv_yesno.add(ws.cell(row, 6))
ws.freeze_panes = ws["A6"]

order = ["Instructions", "Engine Defaults"] + [s for s in wb.sheetnames if s not in ("Instructions", "Engine Defaults")]
wb._sheets = [wb[s] for s in order]
wb.save(dst)
print(f"{dst.name}: Setup {n1} rows, Advanced {n2} rows")
