"""Rebuild an input workbook into the friendly production template.

    python3 tools/build_input_template.py OLD_WORKBOOK.xlsx NEW_WORKBOOK.xlsx

Sheet names stay the ones the engine resolves ('Instructions', 'Engine
Defaults', 'Schedule', ...); only their content and presentation change.

  Start Here      -> new first tab: the weekly checklist with links, live quick
                     checks while you type, and a colour legend.
  Instructions    -> the decisions a scheduler makes per schedule, grouped, one
                     plain-language line of help per row, and EVERY value cell
                     restricted to what the engine accepts (dropdown, number
                     range or text length). Rarely changed sections fold away.
  Engine Defaults -> engine tuning rows, defaults intact, restricted the same
                     way, hidden (right-click a tab > Unhide to see it).
  Data sheets     -> roster, preference, fixed, previous-week, language and
                     coverage-split cells get dropdowns tied to the roster and
                     the Shift Library; demand and shrinkage get number limits.
  Reference tabs  -> the old release notes, start-here and list tabs, and the
                     demand/shrinkage tabs for the interval sizes not in use,
                     are hidden, not deleted.

Nothing is invented: every value is carried across from the source workbook.
A row the engine reads under another name (an alias such as "Leave" for
"Leave Enabled") is carried into its row here. A labelled row this template
does not lay out is kept, under "Other settings carried from your workbook".

The builder then proves it changed nothing the engine reads: it parses the
source and the rebuilt workbook with the engine and compares every parsed
field and the input-contract verdict. Any difference deletes the output and
exits 2, naming the fields.
"""
import re
import shutil
import sys
from copy import copy
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.utils import get_column_letter


def F(**kw):
    """Font with an explicit face: a font with none renders in a serif fallback outside Excel."""
    kw.setdefault("name", "Calibri")
    return Font(**kw)

YES_NO = '"Yes,No"'
# Restored from RC5's template (audit F-17): the language working window and the
# per-language coverage days were settable from RC5's template, not from this one.
LANGUAGE_WINDOW_CHOICES = '"OFF,MINIMUM_ROWS,ALL_ROWS,REQUIRED_LANGUAGE_ONLY"'
LANGUAGE_DAYS_CHOICES = '"All,Weekdays,Weekends,Sun-Thu,Mon-Fri,Sun,Mon,Tue,Wed,Thu,Fri,Sat"'
# The two texts the engine's blank-interval rule tells apart (blank_requirement_mode).
BLANK_RULE_CHOICES = '"No new staffing in blank intervals,Allow staffing in blank intervals"'
# BREAK_DURATION_CHOICES in the engine; any other duration is refused there.
BREAK_MINUTES = '"15,30,45,60"'
# Allowed Shift Durations Hours: kept on the hidden Validation Lists tab so a
# program that needs another mix can add one line there. Every entry must give
# durations between 4 and 16 h (the engine's own bounds); 10.5 h or more also
# needs Use 11H/3OFF = Yes, which the engine checks and names.
DURATION_LIST = "DURATIONS"
DURATION_CHOICES = ["8", "9", "10", "11", "12", "8, 9", "9, 10", "9, 11", "10, 11", "8, 9, 10", "9, 10, 11"]
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
        ("Blank Interval Staffing Rule", BLANK_RULE_CHOICES),
        # What "better coverage" means for this program (audit F-28): Interval
        # Count = the share of intervals at target (interval compliance);
        # Volume Weighted = the requirement covered, so busy intervals weigh
        # more (service level). The Colab runner can override it per run.
        ("Coverage Objective Weighting", '"Interval Count,Volume Weighted"'),
    ]),
    ("Shift & OFF", [
        ("Allowed Shift Durations Hours", DURATION_LIST),
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
        ("Short Break Count", '"0,1,2,3,4"'),
        ("Short Break Duration Minutes", BREAK_MINUTES),
        ("Lunch Count", '"0,1,2"'),
        ("Lunch Duration Minutes", BREAK_MINUTES),
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
# Sections folded away on the Instructions tab (one click on + opens them).
FOLDED_SECTIONS = {"Opening Guard", "Release Quality"}
DEAD_ROWS = {"rc9.1deepdefaultseconds", "rc9.1fulldefaultseconds",
             "rc9.1stage2searchorder", "rc9.1jointbudgetpolicy"}
# Rows the planner was asked to drive from the sheet. Leaving them blank is
# honest but useless: a dropdown you have to discover is not a choice you were
# offered. These rows are seeded with the exact value the engine falls back to
# when the cell is empty, so pre-filling them changes no behaviour - it only
# makes the setting visible. Nothing else is seeded, because pre-filling a row
# whose default the engine may revise would freeze that default into the
# contract without anyone deciding to.
SEEDED_DEFAULTS = {"runstage": "Full Schedule", "rundepth": "Quick",  # the engine's own fallback depth is QUICK
                   # An empty cell means Interval Count, so seeding it changes no contract.
                   "coverageobjectiveweighting": "Interval Count"}

# Every name the engine reads each row under, in the engine's own order (the
# first one present wins there, so it wins here). Taken from the engine's
# _instruction_get / _parse_break_segments / break-window lookups.
ENGINE_NAMES = {
    "Program Name": ["Program Name", "Account Name", "Client Name", "Client / Case Name", "Business Name"],
    "Count of Associates": ["Count of Associates", "Roster Count", "Headcount"],
    "Allow Headcount Mismatch": ["Allow Headcount Mismatch", "Headcount Mismatch Override", "Roster Count Mismatch Allowed"],
    "Interval Minutes": ["Interval Granularity Minutes", "Interval Minutes", "Interval"],
    "Requirements Source": ["Requirements Source", "Requirement Source", "Active Requirements Used"],
    "Shrinkage Source": ["Shrinkage Source", "Shrinkage Sheet"],
    "Run Stage": ["Run Stage", "Schedule Stage", "Run Type"],
    "Run Depth": ["Run Depth", "Run Length", "Search Depth"],
    "Shift Consistency Polish": ["Shift Consistency Polish", "Consistency Polish"],
    "Target": ["Target", "Coverage Target", "Interval Target"],
    "Target Priority Confirmed": ["Target Priority Confirmed", "Coverage Target Confirmed", "Target Confirmed"],
    "Minimum Per Interval": ["Minimum Per Interval", "Coverage Floor", "Minimum Coverage Percentage"],
    "Hard Floor Solver Constraint Enabled": ["Hard Floor Solver Constraint Enabled", "Minimum Floor Enforcement Hard",
                                             "Coverage Floor Hard Constraint"],
    "Blank Interval Staffing Rule": ["Blank Interval Staffing Rule", "Blank Requirement Rule", "Blank Interval Rule",
                                     "Blank Demand Rule"],
    "Coverage Objective Weighting": ["Coverage Objective Weighting", "Coverage Weighting"],
    "Allowed Shift Durations Hours": ["Allowed Shift Durations Hours", "Allowed Shift Duration Hours", "Shift Duration"],
    "Use 11H/3OFF": ["Use 11H/3OFF", "Use 11H 3OFF", "11H/3OFF"],
    "Strict OFF Count": ["Strict 2 OFF", "Strict Two OFF", "Strict OFF Count"],
    "Separate OFF Days": ["Separate OFF Days", "Separate Off Days", "Allow Separate OFF Days"],
    "Rest Gap Hours": ["Difference Between Shifts", "Rest Gap Hours", "Minimum Rest Gap"],
    "Count of Different Shifts Per week": ["Count of Different Shifts Per week", "Max Different Shifts per Week"],
    "Fixed Request Use": ["Fixed Request Use", "Use Fixed Requests", "Fixed/Nesting Enabled", "Use Fixed/Nesting"],
    "Hard OFF Preferences": ["Hard OFF Preferences", "Hard OFF", "OFF Preferences Hard"],
    "Leave Enabled": ["Leave", "Leave Days", "Leave Enabled"],
    "Use Preferences": ["Use Preferences", "Preferences"],
    "Known Departed Associates": ["Known Departed Associates", "Departed Associates", "Former Associates"],
    "Opening Minimum FTE": ["Opening Minimum FTE", "Opening Minimum HC"],
    "Short Break Count": ["Short Break Count", "Count of Short Breaks", "Number of Short Breaks"],
    "Short Break Duration Minutes": ["Short Break Duration Minutes", "Short Break Duration", "Break Duration Minutes"],
    "Lunch Count": ["Lunch Count", "Meal Count", "Count of Lunch Breaks"],
    "Lunch Duration Minutes": ["Lunch Duration Minutes", "Lunch Duration", "Meal Duration Minutes"],
    "Break Preferred Gap Minutes": ["Break Preferred Gap Minutes", "Preferred Gap Between Breaks Minutes",
                                    "Preferred Break Separation Minutes", "Minimum Gap Between Breaks Minutes",
                                    "Break Minimum Gap Minutes", "Minimum Break Separation Minutes"],
    "Break Absolute Minimum Gap Minutes": ["Break Absolute Minimum Gap Minutes",
                                           "Absolute Minimum Gap Between Breaks Minutes",
                                           "Break Hard Minimum Gap Minutes", "Minimum Legal Break Separation Minutes"],
    "Break Normal Maximum Gap Minutes": ["Break Normal Maximum Gap Minutes", "Break Flexible Maximum Gap Minutes",
                                         "Preferred Maximum Gap Between Breaks Minutes"],
    "Allow Back-to-Back Breaks": ["Allow Back-to-Back Breaks", "Back-to-Back Breaks Allowed"],
    "Language Working Window": ["Language Working Window", "Language Working Hours", "Language Window Enforcement"],
    "Critical Coverage No-Break Exception Enabled": ["Critical Coverage No-Break Exception Enabled",
                                                     "No-Break Exception Enabled"],
    "Critical Coverage No-Break Max Associate-Days": ["Critical Coverage No-Break Max Associate-Days",
                                                      "No-Break Max Associate-Days"],
    "Production Quality Gate Mode": ["Production Quality Gate Mode", "Coverage Quality Gate Mode"],
    "Minimum After Break Target Ratio": ["Minimum After Break Target Ratio", "Minimum After Break Target Percentage",
                                         "After Break Target Minimum"],
    "Protected Before80 Minimum Intervals": ["Protected Before80 Minimum Intervals",
                                             "Protected Before 80 Minimum Intervals", "Protected Tier Before80 Minimum"],
    "Protected After80 Minimum Intervals": ["Protected After80 Minimum Intervals",
                                            "Protected After 80 Minimum Intervals", "Protected Tier After80 Minimum"],
    "Demand Fit Guard Enabled": ["Demand Fit Guard Enabled", "Blank Bridge Guard Enabled"],
    "Demand Fit Minimum Active Minutes": ["Demand Fit Minimum Active Minutes", "Minimum Active Minutes"],
    "Demand Fit Minimum Active Ratio": ["Demand Fit Minimum Active Ratio", "Minimum Active Ratio"],
    "Demand Fit Maximum Blank Span Minutes": ["Demand Fit Maximum Blank Span Minutes", "Maximum Blank Span Minutes"],
    "Overage Control Enabled": ["Overage Control Enabled", "Coverage Overage Control Enabled"],
    "Overage Soft Cap": ["Overage Soft Cap", "Coverage Overage Soft Cap"],
    "Overage Severe Cap": ["Overage Severe Cap", "Coverage Overage Severe Cap"],
    "Overage Extreme Cap": ["Overage Extreme Cap", "Coverage Overage Extreme Cap"],
    "Overage Penalty Weight": ["Overage Penalty Weight", "Coverage Overage Penalty Weight"],
    "Maximum Concurrent Break Ratio": ["Maximum Concurrent Break Ratio", "Break Maximum Concurrent Ratio"],
    "Maximum Concurrent Breaks": ["Maximum Concurrent Breaks", "Break Maximum Concurrent Count"],
    "Break Concurrency Gate Mode": ["Break Concurrency Gate Mode", "Concurrent Break Gate Mode"],
    "Next Sunday Balance Enabled": ["Next Sunday Balance Enabled", "Week Boundary Balance Enabled"],
    "Next Sunday Overage Cap": ["Next Sunday Overage Cap", "Week Boundary Overage Cap"],
    "Next Sunday Maximum Adjacent Raw Change": ["Next Sunday Maximum Adjacent Raw Change",
                                                "Week Boundary Maximum Adjacent Raw Change"],
    "Next Sunday Balance Gate Mode": ["Next Sunday Balance Gate Mode", "Week Boundary Balance Gate Mode"],
    "Language Operational Reserve Enabled": ["Language Operational Reserve Enabled", "Required Language Reserve Enabled",
                                             "Skill Operational Reserve Enabled"],
    "Language Operational Reserve Extra FTE": ["Language Operational Reserve Extra FTE",
                                               "Required Language Reserve Extra FTE", "Skill Reserve Extra FTE"],
    "Language Reserve Gate Mode": ["Language Reserve Gate Mode", "Required Language Reserve Gate Mode",
                                   "Skill Reserve Gate Mode"],
    "Qualified Language Break Certificate Enabled": ["Qualified Language Break Certificate Enabled",
                                                     "Language Break Feasibility Certificate Enabled",
                                                     "Skill Break Feasibility Certificate Enabled"],
    "Whole Week Balance Enabled": ["Whole Week Balance Enabled", "Weekly Coverage Balance Enabled"],
    "Whole Week Overage Cap": ["Whole Week Overage Cap", "Weekly Overage Cap"],
    "Quality Benchmark Tolerance Intervals": ["Quality Benchmark Tolerance Intervals", "Benchmark Tolerance Intervals"],
}

# Restriction for every value cell that is not a dropdown, inside the range the
# engine accepts: (kind, minimum, maximum, number format). Ratios are entered
# as ratios (0.9) or percentages (90%), which Excel stores as the same 0.9.
NUMBER_RULES = {
    "Program Name": ("textLength", None, 80, None),
    "Count of Associates": ("whole", 1, 5000, "0"),
    "Target": ("decimal", 0, 1, "0%"),
    "Minimum Per Interval": ("decimal", 0, 1, "0%"),
    "Rest Gap Hours": ("decimal", 0, 24, "0.##"),
    "Count of Different Shifts Per week": ("whole", 1, 7, "0"),
    "Known Departed Associates": ("textLength", None, 2000, None),
    "Opening Minimum FTE": ("whole", 0, 500, "0"),
    "Opening Guard Intervals": ("whole", 0, 96, "0"),
    "Break Preferred Gap Minutes": ("whole", 0, 720, "0"),
    "Break Absolute Minimum Gap Minutes": ("whole", 0, 720, "0"),
    "Break Normal Maximum Gap Minutes": ("whole", 0, 720, "0"),
    "Critical Coverage No-Break Max Associate-Days": ("whole", 0, 5000, "0"),
    "Minimum After Break Target Ratio": ("decimal", 0, 1, "0%"),
    "Protected Before80 Minimum Intervals": ("whole", 0, 672, "0"),
    "Protected After80 Minimum Intervals": ("whole", 0, 672, "0"),
    "Demand Fit Minimum Active Minutes": ("whole", 0, 1440, "0"),
    "Demand Fit Minimum Active Ratio": ("decimal", 0, 1, "0%"),
    "Demand Fit Maximum Blank Span Minutes": ("whole", 0, 1440, "0"),
    "Overage Soft Cap": ("decimal", 1, 5, "0%"),
    "Overage Severe Cap": ("decimal", 1, 5, "0%"),
    "Overage Extreme Cap": ("decimal", 1, 5, "0%"),
    "Overage Penalty Weight": ("whole", 0, 100000000, "0"),
    "Maximum Concurrent Break Ratio": ("decimal", 0, 1, "0%"),
    "Maximum Concurrent Breaks": ("whole", 1, 5000, "0"),
    "Next Sunday Overage Cap": ("decimal", 1, 5, "0%"),
    "Next Sunday Maximum Adjacent Raw Change": ("whole", 1, 1000, "0"),
    "Language Operational Reserve Extra FTE": ("whole", 0, 500, "0"),
    "Whole Week Overage Cap": ("decimal", 1, 5, "0%"),
    "Quality Benchmark Tolerance Intervals": ("whole", 0, 672, "0"),
}

# One line of plain help per row, shown beside the value and when the cell is selected.
HELP = {
    "Program Name": "Name printed on every output. Any text.",
    "Count of Associates": "People on the Schedule tab. Start Here checks that the roster matches.",
    "Allow Headcount Mismatch": "Yes only if the roster may differ from the count above on purpose.",
    "Interval Minutes": "Size of one demand row: 15, 30 or 60 minutes.",
    "Requirements Source": "The demand tab to use. Must match Interval Minutes.",
    "Shrinkage Source": "The shrinkage tab to use. Must match Interval Minutes.",
    "Run Stage": "Full Schedule = shifts and breaks. Before Breaks Only = shifts only, for a quick review.",
    "Run Depth": "Quick is fastest. Deep and Overnight search longer for a better week.",
    "Shift Consistency Polish": "Yes = also write a 'more consistent' copy of the week when it keeps coverage. No = skip it.",
    "Target": "Coverage goal for every interval. Type 0.9 or 90%.",
    "Target Priority Confirmed": "Set Yes when a 100% target is intended.",
    "Minimum Per Interval": "Lowest acceptable coverage in any interval (the floor). Type 0.8 or 80%.",
    "Hard Floor Solver Constraint Enabled": "Yes = never below the floor (the week may become unsolvable). No = protect it as a priority.",
    "Blank Interval Staffing Rule": "What to do in intervals that have no demand.",
    "Coverage Objective Weighting": "Interval Count = most intervals at target. Volume Weighted = busy intervals count more (service level).",
    "Allowed Shift Durations Hours": "Shift lengths allowed. 10.5 h or more needs Use 11H/3OFF = Yes.",
    "Use 11H/3OFF": "Yes = long-shift week with three OFF days.",
    "Strict OFF Count": "Yes = exactly two OFF days (three with 11H/3OFF) per person.",
    "Separate OFF Days": "Yes = a person's OFF days may be apart. No = they must be together.",
    "Rest Gap Hours": "Minimum hours between the end of one shift and the start of the next.",
    "Count of Different Shifts Per week": "Most different shifts one person may get in a week (1 to 7).",
    "Fixed Request Use": "Yes = apply the Fixed Request tab.",
    "Hard OFF Preferences": "Yes = OFF requests on the Preference tab are always granted.",
    "Leave Enabled": "Yes = Leave on the Preference tab is honoured.",
    "Use Preferences": "Yes = try to give people their preferred shifts.",
    "Known Departed Associates": "Names on last week's tab who have left, separated by ; (Start Here lists any missing).",
    "Opening Guard Enabled": "Yes = keep enough people on at the start of each day.",
    "Opening Minimum FTE": "People needed at opening (whole number).",
    "Opening Guard Intervals": "How many opening intervals the guard covers.",
    "Short Break Count": "Short breaks per shift.",
    "Short Break Duration Minutes": "Length of each short break.",
    "Lunch Count": "Lunches per shift.",
    "Lunch Duration Minutes": "Length of each lunch.",
    "Break Preferred Gap Minutes": "Ideal minutes between two breaks.",
    "Break Absolute Minimum Gap Minutes": "Two breaks are never closer than this.",
    "Break Normal Maximum Gap Minutes": "Two breaks are normally no further apart than this.",
    "Allow Back-to-Back Breaks": "Yes = a break may directly follow another.",
    "Language Working Window": "OFF = language hours set minimums only. The other choices also limit when each language may work (guide 3.7).",
    "Critical Coverage No-Break Exception Enabled": "Yes = a person may skip a break when coverage is critical (set a limit below).",
    "Critical Coverage No-Break Max Associate-Days": "Most person-days that may skip a break. Above 0 when enabled.",
    "Production Quality Gate Mode": "Warn = report quality issues. Fail = block release. Off = ignore.",
    "Minimum After Break Target Ratio": "Optional. Lowest share of intervals at target after breaks.",
    "Protected Before80 Minimum Intervals": "Optional. Intervals that must reach 80% before breaks.",
    "Protected After80 Minimum Intervals": "Optional. Intervals that must reach 80% after breaks.",
}

NAVY = "1F3864"
HDR = PatternFill("solid", fgColor=NAVY)
SECTION = PatternFill("solid", fgColor="D9E2F3")
WARN = PatternFill("solid", fgColor="FFF2CC")
INPUT = PatternFill("solid", fgColor="FFF8E1")
FOLD = PatternFill("solid", fgColor="EDEDED")
THIN = Border(*[Side(style="thin", color="BFBFBF")] * 4)
HELP_FONT = F(color="595959", size=10)
TAB_START, TAB_SETTINGS, TAB_WEEKLY, TAB_POLICY, TAB_HIDDEN = "2E7D32", NAVY, "ED7D31", "7F7F7F", "BFBFBF"


def enforced_list_validation(choices, kind="list", maximum=None, operator=None, prompt=None, warn_only=False):
    """A validation that rejects anything outside what the engine accepts.

    openpyxl's DataValidation leaves showErrorMessage off, which lets Excel
    accept any typed value: "Enable" in a Yes/No row then reads as No
    (audit finding F-18). RC5's shipped workbooks enforced every list. The same
    helper builds the number-range, text-length, time and formula checks, so
    every restriction in the template is enforced the same way.

    warn_only is used for exactly two cell groups where the engine accepts more
    than a list can name: a previous-week name or shift (someone who has left,
    a shift no longer in the library). Excel then asks before accepting it.
    """
    dv = DataValidation(type=kind, formula1=choices, formula2=maximum, operator=operator, allow_blank=True)
    dv.errorStyle = "stop"
    dv.showErrorMessage = True
    dv.errorTitle = "Value not allowed"
    dv.error = "Choose a value from the list. Typed values outside the list are not accepted."
    if kind != "list":
        dv.error = "This value is outside what the scheduler accepts. " + (prompt or "")
    if warn_only:
        dv.errorStyle = "warning"
        dv.errorTitle = "Please check this value"
    if prompt:
        dv.showInputMessage = True
        dv.prompt = prompt[:250]
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
    # Every further row a planner may add gets the same dropdown.
    for r in range(ws.max_row + 1, header + 41):
        dv.add(ws.cell(r, days_col))
    return True

def norm(s): return "".join(ch for ch in str(s or "").lower() if ch.isalnum() or ch == ".")

def _two_tab_layout(ws):
    """True when the sheet already has this template's Section|Instruction|Value|Notes header."""
    for r in ws.iter_rows(min_row=1, max_row=8, values_only=True):
        labels = [norm(c) for c in r[:3]]
        if labels[1:3] == ["instruction", "value"]:
            return True
    return False


def existing_rows(wb):
    """[(sheet, label, value)] in sheet order, for every labelled value row."""
    rows = []
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
            if key and norm(key) not in DEAD_ROWS and norm(key) not in {"instruction", "section"}:
                rows.append((name, str(key).strip(), val))
    return rows


def existing_values(wb):
    values = {}
    for _sheet, key, val in existing_rows(wb):
        if val not in (None, ""):
            values.setdefault(norm(key), val)
    return values


def layout_value(key, values):
    """The value the engine reads for this row: the first of its names present."""
    for name in ENGINE_NAMES.get(key, [key]):
        if norm(name) in values:
            return values[norm(name)]
    return None


def carried_rows(wb, sheet):
    """Labelled rows of `sheet` that no template row (or alias) accounts for."""
    known = {norm(n) for names in ENGINE_NAMES.values() for n in names}
    known |= {norm(k) for _s, items in SETUP_LAYOUT + ADVANCED_LAYOUT for k, _c in items}
    out, seen = [], set()
    for name, key, val in existing_rows(wb):
        if name == sheet and val not in (None, "") and norm(key) not in known and norm(key) not in seen:
            seen.add(norm(key))
            out.append((key, val))
    return out


def as_number(value, kind):
    """'33' -> 33 for a number row, so the cell's number check and format apply.
    The engine reads both the same way; the self-check below proves it."""
    if kind not in ("whole", "decimal") or not isinstance(value, str):
        return value
    text = value.strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d*\.\d+", text):
        return float(text)
    return value


def write_sheet(wb, title, layout, values, blurb, start_note=None, carried=(), lists=None):
    if title in wb.sheetnames: del wb[title]
    ws = wb.create_sheet(title)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 44
    ws.column_dimensions["C"].width = 34
    ws.column_dimensions["D"].width = 90
    ws["A1"] = blurb
    ws["A1"].font = F(bold=True, color="FFFFFF", size=14)
    ws["A1"].fill = HDR
    ws["A1"].alignment = Alignment(vertical="center", indent=1)
    ws.merge_cells("A1:D1")
    ws.row_dimensions[1].height = 30
    if start_note:
        ws["A2"] = start_note
        ws["A2"].fill = WARN
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        ws.merge_cells("A2:D2")
        ws.row_dimensions[2].height = 34
    row = 4 if start_note else 3
    for col, head in zip("ABCD", ("", "Instruction", "Value", "Help")):
        c = ws[f"{col}{row}"]; c.value = head
        c.font = F(bold=True, color="FFFFFF"); c.fill = HDR
    header_row = row
    row += 1
    validations = {}
    written = 0
    cells = {}
    sections = [(s, [(k, ch) for k, ch in items]) for s, items in layout]
    if carried:
        sections.append(("Other settings carried from your workbook", [(k, None) for k, _v in carried]))
    carried_values = {norm(k): v for k, v in carried}
    for section, items in sections:
        folded = section in FOLDED_SECTIONS
        # Section band: label in A only, so it is never read as a setting.
        band = ws.cell(row, 1, section + ("   (click + on the left to open)" if folded else ""))
        band.font = F(bold=True, color=NAVY)
        for col in range(1, 5):
            ws.cell(row, col).fill = SECTION
        row += 1
        first_item = row
        for key, choices in items:
            v = carried_values[norm(key)] if norm(key) in carried_values else layout_value(key, values)
            if v in (None, "") and norm(key) in SEEDED_DEFAULTS:
                v = SEEDED_DEFAULTS[norm(key)]
            rule = NUMBER_RULES.get(key)
            if rule:
                v = as_number(v, rule[0])
            ws.cell(row, 2, key)
            value_cell = ws.cell(row, 3, v if v is not None else "")
            value_cell.fill = INPUT
            value_cell.alignment = Alignment(horizontal="left")
            if rule and rule[3]:
                value_cell.number_format = rule[3]
            help_text = HELP.get(key, "Carried unchanged from the source workbook." if norm(key) in carried_values else "")
            if v in (None, ""):
                help_text = ("Blank = engine default. " + help_text).strip()
            ws.cell(row, 4, help_text).font = HELP_FONT
            for col in range(2, 5): ws.cell(row, col).border = THIN
            ws.cell(row, 2).font = F(size=11)
            ws.row_dimensions[row].height = 20
            for col in range(2, 5): ws.cell(row, col).alignment = Alignment(vertical="center", horizontal="left")
            dv = None
            if choices == DURATION_LIST and lists is not None:
                dv = validations.get(choices)
                if dv is None:
                    dv = enforced_list_validation(lists[DURATION_LIST], prompt=HELP.get(key))
                    ws.add_data_validation(dv); validations[choices] = dv
            elif choices:
                dv = validations.get(choices)
                if dv is None:
                    dv = enforced_list_validation(choices)
                    ws.add_data_validation(dv); validations[choices] = dv
            elif rule:
                kind, low, high, _fmt = rule
                if kind == "textLength":
                    dv = enforced_list_validation(str(high), kind="textLength", operator="lessThanOrEqual",
                                                  prompt=f"Up to {high} characters.")
                else:
                    word = "a whole number" if kind == "whole" else "a number"
                    shown = (f"{low:.0%} to {high:.0%}" if _fmt == "0%" else f"{low} to {high}")
                    dv = enforced_list_validation(str(low), kind=kind, maximum=str(high), operator="between",
                                                  prompt=f"Enter {word} from {shown}.")
                ws.add_data_validation(dv)
            if dv is not None:
                dv.add(value_cell)
            cells[key] = value_cell.coordinate
            row += 1; written += 1
        if folded:
            for r in range(first_item, row):
                ws.row_dimensions[r].outlineLevel = 1
                ws.row_dimensions[r].hidden = True
        row += 1
    ws.sheet_properties.outlinePr.summaryBelow = False
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    return written, cells


def header_row_of(ws, needles, max_scan=12):
    for r in range(1, min(ws.max_row, max_scan) + 1):
        labels = [norm(ws.cell(r, c).value) for c in range(1, ws.max_column + 1)]
        if all(any(n in label for label in labels) for n in needles):
            return r, {label: c for c, label in enumerate(labels, start=1) if label}
    return None, {}


def col_letter(_ws, c):
    return get_column_letter(c)


def style_header(ws, header):
    if header is None:
        return
    for c in range(1, ws.max_column + 1):
        cell = ws.cell(header, c)
        if cell.value not in (None, ""):
            cell.font = F(bold=True, color="FFFFFF")
            cell.fill = HDR
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    if header > 1 and ws.cell(1, 1).value not in (None, ""):
        ws.cell(1, 1).font = F(bold=True, color=NAVY, size=13)
        ws.cell(1, 1).fill = PatternFill()
    ws.sheet_view.showGridLines = False


def fill_inputs(ws, first_row, last_row, cols):
    for r in range(first_row, last_row + 1):
        for c in cols:
            cell = ws.cell(r, c)
            cell.fill = INPUT
            cell.border = THIN


ROSTER_ROWS = 300  # rows below each header that carry the checks (a roster is far smaller)


def restrict_data_sheets(wb, refs):
    """Dropdowns and number limits on the weekly data tabs. Returns what it bound."""
    bound = {}
    days = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")

    def day_cols(headers):
        return [c for label, c in headers.items() if label[:3] in days and len(label) <= 9]

    # Schedule: unique names and IDs, language from Language Setup.
    ws = wb["Schedule"] if "Schedule" in wb.sheetnames else None
    if ws is not None:
        h, heads = header_row_of(ws, ["name", "language"])
        if h:
            name_c = next((c for label, c in heads.items() if "sfname" in label or label in {"name", "associatename", "employeename"}), None)
            lang_c = next((c for label, c in heads.items() if "language" in label or "skill" in label), None)
            id_c = next((c for label, c in heads.items() if label in {"empid", "employeeid", "id"}), None)
            last = h + ROSTER_ROWS
            if name_c:
                L = col_letter(ws, name_c)
                refs["roster"] = f"'Schedule'!${L}${h + 1}:${L}${last}"
                dv = enforced_list_validation(f"COUNTIF(${L}${h + 1}:${L}${last},{L}{h + 1})<=1", kind="custom",
                                              prompt="One row per person. Names must match the other tabs.")
                dv.error = "This name is already on the roster. One row per person."
                ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
                bound["Schedule names"] = True
            if id_c:
                L = col_letter(ws, id_c)
                dv = enforced_list_validation(f"COUNTIF(${L}${h + 1}:${L}${last},{L}{h + 1})<=1", kind="custom",
                                              prompt="Employee ID, once per person.")
                dv.error = "This employee ID is already on the roster."
                ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
            if lang_c and refs.get("languages"):
                L = col_letter(ws, lang_c)
                dv = enforced_list_validation(refs["languages"], warn_only=True,
                                              prompt="Pick the language from Language Setup.")
                dv.error = "This language is not on the Language Setup tab. Keep it only if that is intended."
                ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
            dc = day_cols(heads)
            if dc and refs.get("day_values"):
                dv = enforced_list_validation(refs["day_values"],
                                              prompt="OFF, Leave or a shift from the Shift Library.")
                ws.add_data_validation(dv)
                for c in dc:
                    dv.add(f"{col_letter(ws, c)}{h + 1}:{col_letter(ws, c)}{last}")
            style_header(ws, h)
            refs["roster_header"] = h

    def name_and_days(title, active_needed=False, warn_names=False):
        ws = wb[title] if title in wb.sheetnames else None
        if ws is None:
            return
        h, heads = header_row_of(ws, ["name"])
        if not h:
            return
        last = h + ROSTER_ROWS
        name_c = next((c for label, c in heads.items() if "name" in label), None)
        if name_c and refs.get("roster"):
            L = col_letter(ws, name_c)
            dv = enforced_list_validation(refs["roster"], warn_only=warn_names,
                                          prompt="Pick a name from this week's roster.")
            if warn_names:
                dv.error = ("This name is not on this week's roster. If the person has left, also list "
                            "them in Instructions > Known Departed Associates.")
            ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
            fill_inputs(ws, h + 1, max(ws.max_row, h + 1), [name_c])
        lang_c = next((c for label, c in heads.items() if "language" in label), None)
        if lang_c and refs.get("languages"):
            L = col_letter(ws, lang_c)
            dv = enforced_list_validation(refs["languages"], warn_only=True)
            dv.error = "This language is not on the Language Setup tab. Keep it only if that is intended."
            ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
        dc = day_cols(heads)
        if title == "Previous week scheduled":
            dc = [c for label, c in heads.items() if label.startswith("sat") or "saturday" in label or "previous" in label and "shift" in label]
        values_ref = refs.get("prev_values" if title == "Previous week scheduled" else "day_values")
        if dc and values_ref:
            dv = enforced_list_validation(values_ref, warn_only=title == "Previous week scheduled",
                                          prompt="OFF, Leave or a shift from the Shift Library.")
            if title == "Previous week scheduled":
                dv.error = "Not in this week's Shift Library. Keep it only if it really was last Saturday's shift (HH:MM - HH:MM)."
            ws.add_data_validation(dv)
            for c in dc:
                dv.add(f"{col_letter(ws, c)}{h + 1}:{col_letter(ws, c)}{last}")
            fill_inputs(ws, h + 1, max(ws.max_row, h + 1), dc)
            # OFF grey, Leave lilac: the week reads at a glance.
            rng = f"{col_letter(ws, dc[0])}{h + 1}:{col_letter(ws, dc[-1])}{last}"
            top = f"{col_letter(ws, dc[0])}{h + 1}"
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'UPPER(TRIM({top}))="OFF"'],
                                                           fill=PatternFill("solid", fgColor="D9D9D9")))
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'UPPER(TRIM({top}))="LEAVE"'],
                                                           fill=PatternFill("solid", fgColor="E4DFEC")))
        active_c = next((c for label, c in heads.items() if label.startswith("active")), None)
        if active_c:
            L = col_letter(ws, active_c)
            dv = enforced_list_validation(YES_NO, prompt="Yes = apply this row. No = ignore it.")
            ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
        group_c = next((c for label, c in heads.items() if "group" in label or "nest" in label), None)
        if group_c:
            L = col_letter(ws, group_c)
            dv = enforced_list_validation("50", kind="textLength", operator="lessThanOrEqual",
                                          prompt="Optional. People with the same group number work the same shifts.")
            ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
        style_header(ws, h)
        bound[title] = True

    name_and_days("Preference")
    name_and_days("Fixed Request", active_needed=True)
    name_and_days("Previous week scheduled", warn_names=True)

    # Demand and shrinkage: numbers only, inside the engine's ranges.
    for title in [t for t in wb.sheetnames if norm(t).startswith("ftwise") or norm(t).startswith("shrinkage")]:
        ws = wb[title]
        h, heads = header_row_of(ws, ["sun", "mon"])
        if not h:
            continue
        dc = day_cols(heads)
        if not dc:
            continue
        last = max(ws.max_row, h + 1)
        shrink = norm(title).startswith("shrinkage")
        if shrink:
            dv = enforced_list_validation("0", kind="decimal", maximum="0.9999", operator="between",
                                          prompt="Shrinkage as a ratio (0.08) or percent (8%). Below 100%.")
        else:
            dv = enforced_list_validation("0", kind="decimal", maximum="100000", operator="between",
                                          prompt="Required FTE for this interval. 0 or more; blank = no demand.")
        ws.add_data_validation(dv)
        rng = f"{col_letter(ws, dc[0])}{h + 1}:{col_letter(ws, dc[-1])}{last}"
        dv.add(rng)
        for r in range(h + 1, last + 1):
            for c in dc:
                cell = ws.cell(r, c)
                cell.number_format = "0.0%" if shrink else "0.##"
        fill_inputs(ws, h + 1, last, dc)
        style_header(ws, h)
        bound[title] = True

    # Language Setup: Yes/No, whole-number minimums, real times.
    ws = wb["Language Setup"] if "Language Setup" in wb.sheetnames else None
    if ws is not None:
        h, heads = header_row_of(ws, ["language", "minimum"])
        if h:
            last = h + 40
            for label, c in heads.items():
                L = col_letter(ws, c)
                if label.startswith("active") or "crossskilled" in label:
                    dv = enforced_list_validation(YES_NO)
                elif "minimum" in label:
                    dv = enforced_list_validation("0", kind="whole", maximum="500", operator="between",
                                                  prompt="People of this language needed at all times in the window (whole number).")
                elif "coveragestart" in label or "coverageend" in label or label in {"starttime", "endtime"}:
                    dv = enforced_list_validation("0", kind="time", maximum="0.999988426", operator="between",
                                                  prompt="A time such as 08:00. The window may cross midnight.")
                    for r in range(h + 1, last + 1):
                        ws.cell(r, c).number_format = "hh:mm"
                else:
                    continue
                ws.add_data_validation(dv); dv.add(f"{L}{h + 1}:{L}{last}")
            style_header(ws, h)
            bound["Language Setup"] = True

    # Coverage Split: group from Language Setup, real times, ratio 0-100%.
    ws = wb["Coverage Split"] if "Coverage Split" in wb.sheetnames else None
    if ws is not None and refs.get("groups"):
        dv = enforced_list_validation(refs["groups"], prompt="A Coverage Group from Language Setup.")
        ws.add_data_validation(dv); dv.add("A6:A25")
        dv = enforced_list_validation("0", kind="time", maximum="0.999988426", operator="between",
                                      prompt="A time such as 08:00.")
        ws.add_data_validation(dv); dv.add("B6:C25")
        dv = enforced_list_validation("0", kind="decimal", maximum="1", operator="between",
                                      prompt="Share of the requirement this group must cover, e.g. 100%.")
        ws.add_data_validation(dv); dv.add("D6:D25")
        for r in range(6, 26):
            ws.cell(r, 2).number_format = ws.cell(r, 3).number_format = "hh:mm"
            ws.cell(r, 4).number_format = "0%"
        bound["Coverage Split"] = True
    return bound


def write_lists(wb, values):
    """The hidden tab behind the dropdowns that follow other tabs."""
    if "Validation Lists" in wb.sheetnames:
        del wb["Validation Lists"]
    ws = wb.create_sheet("Validation Lists")
    ws["A1"] = "Lists behind the dropdowns. Add a line to a list to offer it. Do not rename this tab."
    ws["A1"].font = F(bold=True, color=NAVY)
    heads = ["Allowed Shift Durations Hours", "Day values (OFF, Leave, shifts)", "Previous Saturday values"]
    for c, head in enumerate(heads, start=1):
        cell = ws.cell(2, c, head)
        cell.font = F(bold=True, color="FFFFFF"); cell.fill = HDR
        ws.column_dimensions[cell.column_letter].width = 34
    durations = list(DURATION_CHOICES)
    current = values.get(norm("Allowed Shift Durations Hours"))
    if current not in (None, "") and str(current).strip() not in durations:
        durations.insert(0, str(current).strip())  # the workbook's own value stays valid
    for i, d in enumerate(durations, start=3):
        ws.cell(i, 1, d)
    refs = {DURATION_LIST: f"'Validation Lists'!$A$3:$A${2 + len(durations) + 20}"}

    # Day values follow the Shift Library live: OFF and Leave, then every label row.
    lib = wb["Shift Library"] if "Shift Library" in wb.sheetnames else None
    ws.cell(3, 2, "OFF"); ws.cell(4, 2, "Leave")
    ws.cell(3, 3, "OFF"); ws.cell(4, 3, "Leave")
    r_out = 5
    if lib is not None:
        first = next((r for r in range(1, lib.max_row + 1)
                      if re.match(r"\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", str(lib.cell(r, 1).value or ""))), None)
        statuses = [str(lib.cell(r, 1).value).strip() for r in range(1, (first or 1))
                    if norm(lib.cell(r, 1).value) == "planned"]
        for s in statuses:  # "Planned" is a previous-Saturday-only status
            ws.cell(r_out, 3, s)
        r_prev = r_out + len(statuses)
        if first:
            for i, r in enumerate(range(first, max(lib.max_row, first) + 41)):
                formula = f"=IF('Shift Library'!A{r}=\"\",\"\",'Shift Library'!A{r})"
                ws.cell(r_out + i, 2, formula)
                ws.cell(r_prev + i, 3, formula)
            last = r_out + (max(lib.max_row, first) + 41 - first) - 1
            refs["day_values"] = f"'Validation Lists'!$B$3:$B${last}"
            refs["prev_values"] = f"'Validation Lists'!$C$3:$C${last + len(statuses)}"
    lang = wb["Language Setup"] if "Language Setup" in wb.sheetnames else None
    if lang is not None:
        h, heads = header_row_of(lang, ["language", "minimum"])
        if h:
            lc = next((c for label, c in heads.items() if label == "language" or label.startswith("language")), 1)
            gc = next((c for label, c in heads.items() if "group" in label), None)
            refs["languages"] = f"'Language Setup'!${col_letter(lang, lc)}${h + 1}:${col_letter(lang, lc)}${h + 40}"
            if gc:
                refs["groups"] = f"'Language Setup'!${col_letter(lang, gc)}${h + 1}:${col_letter(lang, gc)}${h + 40}"
    return refs


def write_start_here(wb, cells, refs, values, req_title, shr_title):
    if "Start Here" in wb.sheetnames:
        del wb["Start Here"]
    ws = wb.create_sheet("Start Here", 0)
    ws.sheet_view.showGridLines = False
    for col, width in zip("ABCDE", (3, 6, 30, 70, 52)):
        ws.column_dimensions[col].width = width
    program = values.get(norm("Program Name")) or "this program"
    ws["B1"] = f"Weekly schedule input  -  {program}"
    ws["B1"].font = F(bold=True, color="FFFFFF", size=18)
    for col in "ABCDE":
        ws[f"{col}1"].fill = HDR
    ws.row_dimensions[1].height = 40
    ws["B2"] = ("Fill the orange tabs each week, check the settings once, and watch the checks below "
                "turn green. Cells you fill are pale yellow; every one only accepts values the scheduler can use.")
    ws["B2"].alignment = Alignment(wrap_text=True, vertical="center")
    ws.merge_cells("B2:E2"); ws.row_dimensions[2].height = 36

    I = lambda key: f"Instructions!{cells[key].replace(chr(36), '')}" if key in cells else None
    roster = refs.get("roster")
    steps = [
        ("Instructions", "Check the settings (headcount, target, shift lengths, requests).", "headcount"),
        ("Schedule", "This week's roster: one row per person, with language.", "roster"),
        (req_title, "Demand: required FTE per interval, Sunday to Saturday.", "demand"),
        (shr_title, "Shrinkage per interval (0.08 = 8%).", "shrinkage"),
        ("Preference", "OFF, Leave or preferred shift per person and day.", "preference"),
        ("Fixed Request", "Fixed shifts (only used when Fixed Request Use = Yes).", "fixed"),
        ("Previous week scheduled", "Last Saturday's shift per person (for rest rules).", "previous"),
    ]
    checks = {}
    if roster:
        names = roster
        checks["roster"] = (f'=IF(COUNTA({names})=0,"! Roster is empty",IF(SUMPRODUCT(({names}<>"")*(COUNTIF({names},{names})>1))>0,'
                            f'"! "&SUMPRODUCT(({names}<>"")*(COUNTIF({names},{names})>1))&" repeated name(s)",'
                            f'"OK  "&COUNTA({names})&" people"))')
        if I("Count of Associates"):
            mismatch_ok = I("Allow Headcount Mismatch")
            ok_clause = f'OR({I("Count of Associates")}=COUNTA({names}),{mismatch_ok}="Yes")' if mismatch_ok else f'{I("Count of Associates")}=COUNTA({names})'
            checks["headcount"] = (f'=IF({ok_clause},"OK  Count of Associates matches the roster",'
                                   f'"! Count of Associates is "&{I("Count of Associates")}&" but the roster has "&COUNTA({names}))')

        def names_not_on_roster(title, extra=""):
            ws_src = wb[title] if title in wb.sheetnames else None
            if ws_src is None:
                return None
            h, heads = header_row_of(ws_src, ["name"])
            nc = next((c for label, c in heads.items() if "name" in label), None)
            if not h or not nc:
                return None
            L = col_letter(ws_src, nc)
            rng = f"'{title}'!${L}${h + 1}:${L}${h + ROSTER_ROWS}"
            return rng
        pref = names_not_on_roster("Preference")
        if pref:
            checks["preference"] = (f'=IF(SUMPRODUCT(({pref}<>"")*(COUNTIF({names},{pref})=0))=0,"OK  every name is on the roster",'
                                    f'"! "&SUMPRODUCT(({pref}<>"")*(COUNTIF({names},{pref})=0))&" name(s) not on the roster")')
        fixed = names_not_on_roster("Fixed Request")
        if fixed and I("Fixed Request Use"):
            checks["fixed"] = (f'=IF({I("Fixed Request Use")}<>"Yes","Not used (Fixed Request Use = No)",'
                               f'IF(SUMPRODUCT(({fixed}<>"")*(COUNTIF({names},{fixed})=0))=0,"OK  every name is on the roster",'
                               f'"! "&SUMPRODUCT(({fixed}<>"")*(COUNTIF({names},{fixed})=0))&" name(s) not on the roster"))')
        prev = names_not_on_roster("Previous week scheduled")
        if prev and I("Known Departed Associates"):
            kd = I("Known Departed Associates")
            missing = f'SUMPRODUCT(({prev}<>"")*(COUNTIF({names},{prev})=0)*ISERROR(SEARCH({prev},"|"&{kd}&"|")))'
            checks["previous"] = (f'=IF({missing}=0,"OK  every name is on the roster or listed as departed",'
                                  f'"! "&{missing}&" name(s) not on the roster: list them in Known Departed Associates if they left")')
    if I("Requirements Source"):
        demand = f'INDIRECT("\'"&{I("Requirements Source")}&"\'!B1:H200")'
        checks["demand"] = (f'=IF(ISERROR(COUNT({demand})),"! Requirements Source names no tab",'
                            f'IF(COUNT({demand})=0,"! No demand entered",IF(COUNTIF({demand},"<0")>0,"! Negative demand",'
                            f'"OK  "&COUNT({demand})&" demand cells")))')
    if I("Shrinkage Source"):
        shr = f'INDIRECT("\'"&{I("Shrinkage Source")}&"\'!B1:H200")'
        checks["shrinkage"] = (f'=IF(ISERROR(COUNT({shr})),"! Shrinkage Source names no tab",'
                               f'IF(COUNTIF({shr},">=1")+COUNTIF({shr},"<0")>0,"! A value is not between 0% and 99%",'
                               f'"OK  "&COUNT({shr})&" shrinkage cells"))')

    row = 4
    for col, head in zip("BCDE", ("#", "Tab", "What to do", "Quick check")):
        c = ws[f"{col}{row}"]; c.value = head
        c.font = F(bold=True, color="FFFFFF"); c.fill = HDR
    for i, (tab, what, check) in enumerate(steps, start=1):
        row += 1
        if tab not in wb.sheetnames:
            continue
        ws.cell(row, 2, i).alignment = Alignment(horizontal="center")
        link = ws.cell(row, 3, tab)
        link.hyperlink = Hyperlink(ref=link.coordinate, location=f"'{tab}'!A1", display=tab)
        link.font = F(color="0563C1", underline="single", bold=True)
        ws.cell(row, 4, what).alignment = Alignment(wrap_text=True, vertical="center")
        if check in checks:
            ws.cell(row, 5, checks[check])
        for col in range(2, 6):
            ws.cell(row, col).border = THIN
        ws.row_dimensions[row].height = 22
    last_check_row = row
    rng = f"E5:E{last_check_row}"
    ws.conditional_formatting.add(rng, FormulaRule(formula=['LEFT(E5,2)="OK"'],
                                                   fill=PatternFill("solid", fgColor="C6EFCE"), font=F(color="006100", bold=True)))
    ws.conditional_formatting.add(rng, FormulaRule(formula=['LEFT(E5,1)="!"'],
                                                   fill=PatternFill("solid", fgColor="FFC7CE"), font=F(color="9C0006", bold=True)))

    row += 2
    ws.cell(row, 2, "Colours").font = F(bold=True, color=NAVY, size=12)
    legend = [
        (INPUT, "Pale yellow cell", "You fill this. Dropdowns and limits stop values the scheduler cannot use."),
        (PatternFill("solid", fgColor=TAB_WEEKLY), "Orange tab", "Update every week."),
        (PatternFill("solid", fgColor=TAB_SETTINGS), "Blue tab", "Settings: check when the policy changes."),
        (PatternFill("solid", fgColor=TAB_POLICY), "Grey tab", "Reference: shift list, language hours, coverage split."),
    ]
    for fill, what, meaning in legend:
        row += 1
        ws.cell(row, 2).fill = fill
        ws.cell(row, 3, what).font = F(bold=True)
        ws.cell(row, 4, meaning)
    row += 2
    ws.cell(row, 2, "Good to know").font = F(bold=True, color=NAVY, size=12)
    notes = [
        "The quick checks above help while you type. The scheduler re-checks everything on every run and "
        "stops with a clear message if anything is wrong - that check is the authority.",
        "Hidden tabs (engine tuning, lists, the demand tabs for other interval sizes, old notes) are kept, "
        "not deleted: right-click any tab > Unhide.",
        "Changing Interval Minutes? Unhide the matching FT Wise and Shrinkage tabs and pick them in Instructions.",
        "Outputs: the main schedule, plus optional MAX_TARGET, MAX_FLOOR and MORE_CONSISTENT copies to choose from.",
    ]
    for note in notes:
        row += 1
        cell = ws.cell(row, 3, "•  " + note)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=5)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 32
    ws.sheet_properties.tabColor = TAB_START
    return ws


def organize_tabs(wb, values, req_title, shr_title):
    weekly = ["Schedule", req_title, shr_title, "Preference", "Fixed Request", "Previous week scheduled"]
    policy = ["Language Setup", "Coverage Split", "Shift Library"]
    order = ["Start Here", "Instructions"] + [t for t in weekly + policy if t and t in wb.sheetnames]
    rest = [s for s in wb.sheetnames if s not in order]
    wb._sheets = [wb[s] for s in order + rest]
    for name in rest:
        wb[name].sheet_state = "hidden"
        wb[name].sheet_properties.tabColor = TAB_HIDDEN
    wb["Instructions"].sheet_properties.tabColor = TAB_SETTINGS
    for t in weekly:
        if t and t in wb.sheetnames:
            wb[t].sheet_properties.tabColor = TAB_WEEKLY
    for t in policy:
        if t in wb.sheetnames:
            wb[t].sheet_properties.tabColor = TAB_POLICY
    for ws in wb.worksheets:
        ws.sheet_view.tabSelected = False
        # Printing a tab gives one page wide, landscape.
        ws.page_setup.orientation = "landscape"
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
    wb.active = 0
    wb["Start Here"].sheet_view.tabSelected = True
    return rest


PROVENANCE_ONLY = {"coverage_objective_weighting_source": "coverage_objective_weighting",
                   "coverage_split_source": "coverage_split_rules"}


SEEDED_FALLBACK = {"run_stage": "'FULL_SCHEDULE'", "run_depth": "'QUICK'"}


def engine_reading(path):
    """Everything the engine parses from a workbook, for the self-check."""
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "engine" / "_tools"))
    import l632_universal_scheduler as E
    parsed = E.parse_input(Path(path))
    fields = {k: repr(v) for k, v in vars(parsed).items() if k not in {"path", "instructions"}}
    fields["input_contract"] = repr(sorted((f.get("code"), str(f.get("detail", f.get("message", ""))))
                                           for f in E.validate_input_contract(parsed).get("failures", [])))
    return fields


def build(src, dst):
    shutil.copy(src, dst)
    wb = load_workbook(dst)
    values = existing_values(wb)
    carried_instr = carried_rows(wb, "Instructions")
    carried_defaults = carried_rows(wb, "Engine Defaults")
    req_title = next((t for t in wb.sheetnames if norm(t) == norm(layout_value("Requirements Source", values))), None)
    shr_title = next((t for t in wb.sheetnames if norm(t) == norm(layout_value("Shrinkage Source", values))), None)
    refs = write_lists(wb, values)
    n1, cells = write_sheet(wb, "Instructions", SETUP_LAYOUT, values,
                            "Settings for this schedule",
                            "Fill the yellow Value cells. Every cell only accepts what the scheduler can use "
                            "(pick from the list, or a number inside the allowed range). Blank = engine default.",
                            carried=carried_instr, lists=refs)
    n2, _ = write_sheet(wb, "Engine Defaults", ADVANCED_LAYOUT, values,
                        "ADVANCED - engine tuning. Defaults are production-tested.",
                        "Change these only with a specific reason. They are not per-schedule business "
                        "settings; the values here are the ones every released result was measured with.",
                        carried=carried_defaults, lists=refs)
    ensure_language_setup_controls(wb)
    # Input Checks was a static snapshot that said PASS no matter what the roster held.
    if "Input Checks" in wb.sheetnames:
        del wb["Input Checks"]
        ws = wb.create_sheet("Input Checks")
        ws["A1"] = "Input Checks are performed by the engine, not by this sheet."
        ws["A1"].font = F(bold=True, color="FFFFFF"); ws["A1"].fill = HDR
        ws.merge_cells("A1:F1"); ws.column_dimensions["A"].width = 110
        ws["A3"] = ("The previous version of this tab held hardcoded PASS/WARN text. It reported "
                    "PASS regardless of what the roster, demand or language setup actually "
                    "contained, so it could not catch the errors it appeared to check for.")
        ws["A4"] = ("The engine runs the real pre-solver contract validation on every run and writes "
                    "the result to the audit JSON as pre_solver_contract_validation, with a specific "
                    "code, day and time for each failure. That is the authoritative check. The Start "
                    "Here tab carries live quick checks while you type.")
        for r in (3, 4):
            ws[f"A{r}"].alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[r].height = 45
    # Coverage Split: which group STAFFS which window, as opposed to Language
    # Setup's weaker "at least N of them are present". Written empty on purpose -
    # rows here change the contract, so a workbook that never asked for the feature
    # must not acquire it just by being rebuilt through the template. Rows a
    # workbook already holds are carried across.
    kept_split = []
    if "Coverage Split" in wb.sheetnames:
        old = wb["Coverage Split"]
        oh, _ = header_row_of(old, ["coveragegroup", "start"])
        if oh:
            for r in range(oh + 1, old.max_row + 1):
                row_values = [old.cell(r, c).value for c in range(1, 8)]
                if row_values[0] not in (None, "") and norm(row_values[0]) != norm("Name from Language Setup's Coverage Group column."):
                    kept_split.append(row_values)
        del wb["Coverage Split"]
    ws = wb.create_sheet("Coverage Split")
    ws["A1"] = "Coverage Split - which coverage group is responsible for staffing which hours"
    ws["A1"].font = F(bold=True, color="FFFFFF"); ws["A1"].fill = HDR
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
        c.font = F(bold=True, color="FFFFFF"); c.fill = HDR; c.border = THIN
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
        c.font = F(italic=True, color="808080", size=9)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[5].height = 40
    for col, width in zip("ABCDEFG", (22, 12, 12, 16, 13, 11, 46)):
        ws.column_dimensions[col].width = width
    dv_yesno = enforced_list_validation(YES_NO)
    ws.add_data_validation(dv_yesno)
    for row in range(6, 26):
        for col in range(1, 8):
            ws.cell(row, col).border = THIN
            if col <= 6:
                ws.cell(row, col).fill = INPUT
        dv_yesno.add(ws.cell(row, 5))
        dv_yesno.add(ws.cell(row, 6))
    for i, row_values in enumerate(kept_split):
        for col, value in enumerate(row_values, start=1):
            ws.cell(6 + i, col, value)
    ws.freeze_panes = ws["A6"]
    ws.sheet_view.showGridLines = False

    bound = restrict_data_sheets(wb, refs)
    write_start_here(wb, cells, refs, values, req_title, shr_title)
    hidden = organize_tabs(wb, values, req_title, shr_title)
    wb.save(dst)
    return n1, n2, bound, hidden


def main(argv):
    if len(argv) != 3:
        print(__doc__.split("\n\n")[1])
        return 1
    src, dst = Path(argv[1]), Path(argv[2])
    n1, n2, bound, hidden = build(src, dst)
    try:
        before = engine_reading(src)
    except Exception as exc:  # the source itself cannot be read: say so, keep the output
        print(f"{dst.name}: Setup {n1} rows, Advanced {n2} rows")
        print(f"NOT VERIFIED: the engine cannot parse the source workbook ({type(exc).__name__}: {exc}).")
        return 3
    after = engine_reading(dst)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    # Provenance labels the template changes by design while the setting itself
    # is identical: the seeded Coverage Objective Weighting row (source "default"
    # becomes "workbook", value unchanged) and the Coverage Split tab it always
    # writes (source "ABSENT" becomes the empty tab, rules unchanged).
    provenance = {k: PROVENANCE_ONLY[k] for k in changed
                  if k in PROVENANCE_ONLY and before.get(PROVENANCE_ONLY[k]) == after.get(PROVENANCE_ONLY[k])}
    # Run Stage / Run Depth left blank are seeded with the runner's own fallback
    # (SEEDED_DEFAULTS): blank -> the same stage and depth, now visible.
    seeded = {k for k in changed if k in SEEDED_FALLBACK and before.get(k) == "None"
              and after.get(k) == SEEDED_FALLBACK[k]}
    changed = [k for k in changed if k not in provenance and k not in seeded]
    if changed:
        dst.unlink()
        print(f"REFUSED: the rebuilt workbook would change what the engine reads: {', '.join(changed)}. "
              "Nothing was written.")
        return 2
    print(f"{dst.name}: Setup {n1} rows, Advanced {n2} rows; dropdowns on {', '.join(bound) or 'no data tabs'}; "
          f"{len(hidden)} reference tabs hidden")
    print(f"VERIFIED: the engine reads the same contract from both workbooks ({len(before)} fields compared"
          + (f"; provenance label only: {', '.join(sorted(provenance))}" if provenance else "")
          + (f"; blank row seeded with the runner's fallback: {', '.join(sorted(seeded))}" if seeded else "") + ").")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
