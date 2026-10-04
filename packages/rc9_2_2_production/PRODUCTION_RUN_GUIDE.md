# Production run guide — RC9.2.2 RC6

Release `L6.3.2.8-RC9.2.2-PRODUCTION-HARDENED-RC6`. This guide covers how to
prepare a weekly input workbook, run it on Google Colab, and know which file to
publish.

---

## 1. What "safe to run" means for this package

**What the package guarantees on every run:**
- **Engine and tests are checked first.** Before any solving, the runner
  verifies the engine's sha256, the pinned runtime (OR-Tools 9.15.6755, scipy),
  and runs the full offline test gate (1349 tests). If anything fails, it
  **refuses to run**.
- **Bad inputs are refused.** A workbook that breaks the input contract is
  refused with a message naming the cell or person. Examples: an unknown
  associate on the previous-week sheet, a yes/no cell holding "Yes." or
  "Enable", or a Preference value the engine cannot classify.
- **Nothing is published unchecked.** A schedule is published only if the
  independent validator passes it with **0 hard failures** and metric parity.
  The validator re-checks leave, OFF, rest gaps, break rules, language minima
  and next-Sunday carry-over from the output cells.
- **The exit code tells you.** Exit 0 means an approved schedule. Anything else
  means **not approved: do not publish**.

**What is not proven yet:**
- The head-to-head comparison against RC5 on the same workbooks and seeds is
  still running. Results are expected around 3 Oct.
- On the cases measured so far, this engine places breaks much better:
  after-breaks target intervals went Chat 155 → 179 and Voice 227 → 246.
- Until the comparison finishes, "at least as good as RC5 on every workbook"
  is expected but not proven.

**Interim recommendation for critical schedules:**
- If you still have the RC5 package and the time, run the same workbook on
  both.
- Publish the one with the higher **after-breaks target** that is also
  validator-approved. Compare the *Production Summary* sheet of each output.
- For routine schedules, this package alone is fine.

**Do not use yet, for production:**
| Setting | Why |
|---|---|
| `SINGLE_LONG_RUN = True` | The one-long-run DEEP/OVERNIGHT path works end to end (F-16: Chat and H1 completed and passed the validator). It is not better: on Chat one 4 h run scored 166 after-break target, against 169-184 for single 1 h QUICK runs. Use `MODE = DEEP` with seeds instead (the default). |
| `SKIP_GUARDS = True` | It turns off the checks that make the output safe. |
| `--enable-dnbs`, `--enable-joint-refinement`, `--enable-break-load-feedback` | Measured and not shown to help. They are off by default; leave them off. |

---

## 2. What you need

- A Google account with Colab (the free tier works; High-RAM is nicer).
- `RC9_2_2_PRODUCTION_PACKAGE.zip` (this package).
- Your week's input workbook (`.xlsx`) in the updated format (section 3).
- For the recommended Drive notebook: put both files in your Google Drive, for
  example in a folder `MyDrive/schedules/`.

---

## 3. Preparing the input workbook

### 3.1 Start from the updated format

**Option A (simplest):** copy the shipped workbook for the same program from
the package's `inputs/` folder. Replace the roster, demand, shrinkage,
preferences and previous-week data with this week's.

| Program | Shipped workbook |
|---|---|
| Cricut Chat | `Cricut_Chat_RC9_1_READY_SKELETON.xlsx` |
| Cricut Voice | `Cricut_Voice_RC9_1_READY_SKELETON.xlsx` |
| NMG Spanish | `NMG_SP_RC9_1_READY_FIXED.xlsx` |
| NMG English | `NMG_EN_FIXED_NESTING_REST_SAFE_REGRESSION_CLEAN.xlsx` |
| NMG English + Spanish | `NMG_EN_AND_SP.xlsx` |
| GDI 28 HC 24/7 | `GDI_REAL28_RC9_1_24_7_FINAL_READY.xlsx` |
| AE Arabic B2B | `AE_AR_B2B.xlsx` |

The shipped workbooks keep their original layout byte for byte (they are the
baselines the release is measured against). That layout has **no
`Language Working Window` row and no `Coverage Days` column**, so a copy of one
cannot limit when each language works, or set different language hours per day.
To get those controls, convert the copy with Option B, then follow 3.7.

**Option B:** convert your existing (older-layout) workbook. This carries every
value across unchanged, adds the new rows at their defaults, and makes every
dropdown reject typed values. Keep your original as a backup.

```
python3 tools/build_input_template.py OLD_WORKBOOK.xlsx NEW_WORKBOOK.xlsx
```

In Colab, add a cell after step 3 of the notebook:

```
!python3 {PACKAGE_ROOT}/tools/build_input_template.py "/content/drive/MyDrive/schedules/old.xlsx" "/content/drive/MyDrive/schedules/new.xlsx"
```

### 3.2 The sheets, and what to update each week

| Sheet | What it holds | Weekly update |
|---|---|---|
| **Instructions** | The decisions for this schedule: program, headcount, interval size, target, shift lengths, OFF rules, requests on/off, breaks, language window, **Known Departed Associates**. | Check `Count of Associates`. Set `Known Departed Associates` if needed (3.4). Leave the rest unless the policy changed. |
| **Engine Defaults** | Engine tuning, marked do-not-touch. | **Do not change.** |
| **Schedule** | The roster: Slot, Emp ID, Email, **SF Name**, TL, Language (one row per associate). | Yes: this week's roster. Names must match the other sheets exactly (case and extra spaces are ignored). |
| **Preference** | Per associate and day (Sun–Sat): `OFF`, `Leave`, a shift such as `09:00 - 18:00`, or blank. | Yes. |
| **Fixed Request** | Fixed shifts (only when `Fixed Request Use = Yes`). | If used. |
| **Previous week scheduled** | Last Saturday's shift per person (for rest and carry-over). | Yes. |
| **FT Wise 15 / 30 / 60 Min** | Demand: required FTE per interval, Sun–Sat. The one named in `Requirements Source` is used. | Yes: fill the sheet that matches `Interval Minutes`. |
| **Shrinkage 15 / 30 / 60 Min** | Shrinkage ratio per interval (0.08 = 8%). | Yes, the matching one. |
| **Shift Library / Shift Catalog** | Allowed shifts and statuses. | Only if the shift policy changed. |
| **Language Setup** | One row per language and set of days: coverage start/end, minimum per interval, `Coverage Days`. Whether the hours also limit who may work when is set by `Language Working Window` (3.7). | Only if coverage rules changed. |
| **Validation Lists**, **00 START HERE**, **Input Checks**, release-notes sheets | Lists behind the dropdowns, and notes. | Do not edit. |

### 3.3 Preference and Fixed cells: accepted values

**Accepted as is:**
- **Leave:** `Leave`, `Annual Leave`, `AL`, `A/L`, `Sick`, `Sick Leave`, `SL`,
  `Holiday`, `Public Holiday`, `PH`, `BH`, `Casual Leave`, `CL`,
  `Medical Leave`, `ML`, `Maternity`, `Paternity`, `Bereavement`, `Vacation`,
  `Unpaid Leave`, `LOA`, `PTO`, `Leave (approved)`.
- **OFF:** `OFF`, `Day Off`, `Off Day`, `Rest Day`, `RD`, `R/D`, `D/O`, `WO`,
  `Week Off`, `Comp Off`, `OFF (approved)`, `Requested Off`, `X`.
- **Shift:** `HH:MM - HH:MM`, for example `09:00 - 18:00` or `22:00 - 07:00`.
- **Blank:** empty, `N/A`, `NA`, `-`, `TBD`, `TBA`.

**Refused** (the run stops and names the cell), because the meaning is
ambiguous: `Training`, `WFH`, `Half Day`, `Morning`, `Sick Off`, `Off Duty`,
and any other free text.

**Using your own site codes.** Add a sheet named **`Preference Code Mapping`**
with two columns, `Value` and `Meaning`. `Meaning` must be `Leave`, `OFF` or
blank:

| Value | Meaning |
|---|---|
| TRN | Leave |
| HD | OFF |

### 3.4 Someone on last week's sheet has left

If a name on **Previous week scheduled** is not in the **Schedule** roster, the
run is refused:

`HARD_PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE: 'Name' ... is not in the Schedule roster`

- **Misspelled name:** correct the spelling.
- **The person has left:** type their name in **Instructions → Known Departed
  Associates**. Separate several names with `;`.
- Each person must be listed. Acknowledging one never silences another.

### 3.5 Yes/No cells and dropdowns

A yes/no instruction must hold `Yes` or `No`. `Y`/`N`, `True`/`False`,
`1`/`0`, `On`/`Off` and `Enabled`/`Disabled` are also accepted. Anything else,
such as `Yes.`, `Enable` or `Active`, is refused
(`HARD_INVALID_INSTRUCTION_BOOLEAN`); it is never silently read as "No".

Workbooks converted with the builder, and the shipped non-baseline workbooks,
already reject typed values in every dropdown. To add that protection to
another workbook (cell values are not changed):

```
python3 tools/enforce_workbook_validations.py MY_WORKBOOK.xlsx
```

### 3.5b Layout rules the run enforces (refused, never guessed)

These used to be read by guesswork and could silently change what the run
scheduled. Each one now stops the run before solving and names the sheet, row
or person:

| Problem in the workbook | Code |
|---|---|
| The same person on two **filled** Preference rows (for example leave on one row, OFF on another). Put all of a person's requests on one row. An extra **empty** row is ignored. | `HARD_PREFERENCE_DUPLICATE_ASSOCIATE` |
| The same person on two active Fixed Request rows | `HARD_FIXED_REQUEST_DUPLICATE_ASSOCIATE` |
| Day columns on Schedule (when it carries fixed requests), Preference or Fixed Request are not labelled Sun..Sat. Real calendar dates are fine: each date is read as its weekday. | `HARD_DAY_COLUMNS_NOT_FOUND` |
| A demand time row appears twice, is missing, or sits off the interval grid (for example 10:15 on a 30-minute sheet) | `HARD_DUPLICATE_REQUIREMENT_TIME`, `HARD_MISSING_REQUIREMENT_TIME`, `HARD_OFF_GRID_REQUIREMENT_TIME` |
| A shrinkage time row appears twice | `HARD_DUPLICATE_SHRINKAGE_TIME` |
| Names below a gap of more than 20 empty rows on the Schedule sheet | `HARD_ROSTER_ROWS_AFTER_BLANK_GAP` |
| A Shift Library label with two times that cannot be read (`08:00 - 24:00`; write `16:00 - 00:00`) | `HARD_INVALID_SHIFT_LABEL` |
| A language `Minimum Per Interval` that is not a whole number of zero or more | `HARD_INVALID_LANGUAGE_MINIMUM` |
| An unreadable previous-Saturday shift (`25:00 - 06:00`) | `HARD_INVALID_PREVIOUS_SATURDAY_SHIFT` |
| One person's leave, OFF and fixed-shift requests cannot fit in one week (for example three OFF requests under Strict 2 OFF) | `ASSOCIATE_REQUESTS_EXCEED_WEEK` |

The employee ID is now read from the column headed `Emp ID` / `Employee ID`
wherever it is, not from the second column.

**Leave counts against the week.** The weekly rule is two OFF days (three in
11H/3OFF), taken from the days not already on approved leave. Someone on leave
all week owes no OFF day; someone on leave six days owes one. This used to
make the whole week unschedulable.

**Instruction values and contradictions (also refused before solving).** Each
of these used to be replaced by a default without a word:

| Problem in the workbook | Code |
|---|---|
| A number row the engine reads holds text or a formula (`three`, `=A1`) | `HARD_INVALID_INSTRUCTION_NUMBER` |
| The same instruction label twice on one sheet with different values (the last row used to win) | `HARD_DUPLICATE_INSTRUCTION` |
| `Count of Different Shifts Per week` is 0 | `INVALID_MAX_SHIFT_VARIETY` |
| No-break exceptions enabled with a maximum of 0 (it used to become 8). Enabled with no maximum stated still uses 8 and says so. | `HARD_CONTRADICTORY_NO_BREAK_LIMIT` |
| `Allowed Shift Durations` lists 10.5 h or more while `Use 11H/3OFF` is No (they used to become 9 h) | `HARD_LONG_DURATION_WITHOUT_11H_MODE` |
| `Allowed Shift Durations` has no readable duration between 4 and 16 hours | `HARD_INVALID_SHIFT_DURATIONS` |
| A Coverage Split row with an unreadable time, ratio, `Exclusive?` or `Active?`, or a blank `Active?` (write Yes or No) | `HARD_INVALID_COVERAGE_SPLIT_ROW` |
| A fixed shift in hours the Blank Interval Staffing Rule forbids | `FIXED_REQUEST_IN_BLANK_HOURS` |
| A fixed shift the Language Working Window does not allow for that person | `FIXED_REQUEST_OUTSIDE_LANGUAGE_HOURS` |

**Overnight language rules with Coverage Days** open on each listed day: a
Mon-Fri 18:00-05:00 rule runs from Monday 18:00 to Saturday 05:00. Monday
00:00-05:00 belongs to Sunday night and is not covered by it.

**Coverage Split Gate Mode** now decides what a Coverage Split shortfall
after breaks does: `Fail` blocks release, `Warn` reports it.

**Release checks after the schedule is built.** On top of the independent
validator and the metric parity check, the run now:

- runs the clean-room checker (`tools/clean_room_check.py`, no engine code).
  A rule violation, or a coverage figure that differs from the engine's,
  blocks release (`FAIL_CLEAN_ROOM`). A layout it cannot read is recorded as
  `NOT_CHECKED` in `CLEAN_ROOM_CHECK.json` and does not block.
- validates every alternative export (`MAX_TARGET`, `MAX_FLOOR`, `BALANCED`).
  Each verdict is in `INDEPENDENT_VALIDATION_<ROLE>.json` and in
  `UNIVERSAL_RUN_STATUS.json`. These do not affect the main schedule's release.

`BUSINESS_OUTCOME.txt` now lists **Why it is blocked** for a blocked schedule,
keeps the engine's own explanation when no schedule was produced, and reports a
diagnostics-only (SMOKE) run as diagnostics rather than as a final schedule.

### 3.5c When no schedule meets every hard rule: the shortfall schedule

Some weeks have no schedule that meets every hard rule: a quarter no legal
shift can reach, too few language agents, a lone night cover who must take a
break. Such a run used to end with no schedule at all. It now also produces
`<id>_L6_3_2_3_HARD_RULE_SHORTFALL_SCHEDULE.xlsx`:

- it meets every **person** rule: rest, OFF days, leave, hard OFF, fixed
  requests, nesting, shift variety, language working hours, blank-hours ban,
  breaks and the no-break exception limit;
- it misses only **coverage minimums** (nobody on the floor, language
  minimum, opening minimum, Coverage Split, hard floor, next-Sunday
  minimums), as few as the solver could find;
- its first sheet, **Shortfalls**, lists every missed quarter with the day,
  time, rule, what was required and how far short it is;
- the run still ends with a blocking code and `BUSINESS_OUTCOME.txt` says
  "No schedule meets every hard rule; a shortfall schedule is attached for
  review". The independent validator checks it and must find exactly the
  listed shortfalls and nothing else (`SHORTFALL_SCHEDULE_VALIDATION.json`).

It is not releasable. Use it only after the business has accepted each listed
shortfall, or add staff and rerun. Input errors (duplicate rows, unreadable
values, contradictory requests) never get a shortfall schedule: fix the
workbook. The shortfall pass uses the run's remaining time; if it finds no
schedule in that time, `BUSINESS_OUTCOME.json` records why under
`shortfall_schedule` and the run ends as before.

The next-Sunday floor (Saturday-night carry-out) is now treated like the
current week's floor: a coverage-quality finding under the coverage gate
(`NEXT_SUNDAY_FLOOR_GAPS`), not a hard failure. Zero staffing, language and
opening minimums on next Sunday stay hard.

### 3.5d Optional rows added in Phase C

| Row (Instructions or Engine Defaults) | Effect | Default |
|---|---|---|
| `Break Set For Shifts Of N Hours Or More` = `15, 30, 15, 15` | Shifts of N hours or more get these breaks, in this order (30 minutes or more is a lunch). Several rows may be given; the largest threshold a shift reaches wins. The validator and the clean-room checker read the same rows. | Absent: every shift gets the global break set |
| `Coverage Objective Weighting` = `Interval Count` or `Volume Weighted` (a dropdown in the Coverage section of a template-built workbook) | What "better coverage" means for this program. **Interval Count**: the share of intervals at target; choose it for a program accountable for interval compliance. **Volume Weighted**: each interval's miss weighs by its requirement, and schedules are ranked first by the requirement covered at target; choose it for a program accountable for service level (busy intervals matter more). The two trade against each other: Volume Weighted can give up quiet intervals to cover a peak. The Colab run cell can override it per run (`COVERAGE_MEASURE`). With several seeds (QUICK keeps the best of 2), the best seed is picked by the same measure: by requirement covered at target, recomputed by the independent validator, for Volume Weighted, and by intervals at target as before for Interval Count (`PORTFOLIO_SUMMARY.json` → `after_ranking_measure`). The first lines of `BUSINESS_OUTCOME.txt` say which measure was used and where it came from (workbook, run override, or default). | `Interval Count` |
| `Stage 1 Minimum Slice Seconds` (Engine Defaults) | The Stage-1 search time per profile. The planner now funds the Stage-1 window for this slice (up to 45 % of the run); it used to size the window for 45 s whatever was set. Measured on AE_IT_B2B (5 paired seeds, QUICK): `240` gave +1.4 after-break floor and +2.0 target intervals, with 1.4 more break-concurrency violations; a per-workbook option, not a default. | 45 |

### 3.6 Check the workbook before running (seconds)

Use notebook step **4b** (set `WORKBOOK_TO_CHECK`), or run:

```
python3 tools/check_input_workbook.py MY_WORKBOOK.xlsx
```

`RESULT: ACCEPTED - ready to run` means the run will accept it. `REFUSED` lists
each problem with the sheet and name to fix. Fix it, then check again. This
saves waiting through the 15–30 minute safety gate only to be refused.

### 3.7 Language hours: who may work when

`Coverage Start` / `Coverage End` on **Language Setup** do two different jobs:

1. **Minimum coverage.** If `Minimum Per Interval` is above 0, at least that many
   people who can cover the language must be on duty inside those hours.
2. **Working hours.** Whether that language's associates may only **start**
   their shifts inside those hours. This happens **only** when
   **Instructions → `Language Working Window`** is set. It is `OFF` by default,
   and with `OFF` an English associate can be scheduled in International hours
   and the other way round.

| `Language Working Window` | What it does |
|---|---|
| `OFF` (default) | Hours set only the minimum coverage. They do not limit who works when. |
| `MINIMUM_ROWS` | Limits working hours only for rows whose `Minimum Per Interval` is above 0. A row with minimum 0 limits nothing. |
| `ALL_ROWS` | **Every active row limits its language's working hours.** Use this to keep each team inside its hours. |
| `REQUIRED_LANGUAGE_ONLY` | Also blocks anyone who cannot cover a required language from working during that language's required hours. |

**Different hours on different days.** Add one row per set of days and fill
`Coverage Days` (`All`, `Weekdays`, `Weekends`, `Mon-Fri`, `Sun-Thu`, `Sat,Sun`,
or day names separated by commas). Example:

| Language | Coverage Start | Coverage End | Coverage Days |
|---|---|---|---|
| Spanish | 18:00 | 05:00 | Mon-Fri |
| Spanish | 19:00 | 06:00 | Sat,Sun |

Rules worth knowing:
- A shift is inside a window when it **starts** inside it. A shift starting at
  02:00 in an 18:00–05:00 window may end at 11:00.
- Each day uses its own rows. If two rows cover the same day, a start inside
  either one is allowed.
- On a day with no row for a language, that language's associates may start at
  any hour. Add a row for every day they work.
- An overnight row is read **within each listed calendar day**. `18:00–05:00`
  on `Mon-Fri` allows starts on Monday 00:00–04:45 and Monday 18:00–23:45, and the
  same on each day to Friday. The after-midnight part of **Friday night** is a
  **Saturday** start, so the `Sat,Sun` row decides it. Write each day's rows for
  the starts that fall on that calendar day.
- The roster's `Language` column decides each person's hours. Someone who works
  International hours but is labelled `English` is held to English hours.
- A **fixed request** outside its person's hours cannot be met together with an
  enforced window. The run then stops with "No schedule satisfies all hard
  rules". The pre-check (3.6) lists every such request by name and day, so fix
  those first.

The pre-check prints, under **4. language hours**, the mode and each language's
hours per day. It warns when the hours are authored but not enforced.

### 3.8 More consistent weeks: the shift consistency polish

> **Published as its own workbook since 2026-10-04 (audit F-35).** Until then the
> polish never reached a published workbook: the engine measured the polished
> schedule but wrote the original one. Now the selected schedule is never changed.
> When the polish improves the week, it is written beside it as
> `<id>_L6_3_2_3_MORE_CONSISTENT_CANDIDATE.xlsx`. The independent validator checks
> it, and the runner approves it only if its coverage (target, floor, tiers,
> severe floor gaps, language, empty quarters, Coverage Split, break concurrency),
> recomputed by the validator, is no worse than the selected schedule's. When
> approved, `BUSINESS_OUTCOME.txt` names the file and its start-time movement
> before and after. Use either workbook.

Once the schedule is chosen, the polish makes each associate's week more uniform.

1. **Swaps.** Two associates with the same language and shift length exchange a
   day's shift, breaks included. Every interval is covered exactly as before.
2. **One-hour moves.** A shift starts one hour earlier or later. This is kept only
   when nothing the engine measures gets worse: target, floor, every tier, gaps,
   breaks, overage, language and week boundary.

Every move keeps every hard rule:

- rest, including from last Saturday and across the week;
- OFF days and leave;
- the maximum number of different shifts;
- language hours;
- shift length (11h/3-OFF mode).

Fixed requests and nesting groups are never moved. Preference matches and the
fairness spreads (late, overnight, weekend shifts, start swings) may not get worse.

The polish uses spare time at the end of the run and never extends it. Measured on 14 schedules (on the
engine's own record, before F-35 was found): start-time movement fell by up to 70% (AE_IT 47 h -> 14 h), with
coverage and compliance unchanged (`evidence/shift_consistency/RESULT.md`). The audit
records what it did, and the log prints
`SHIFT_CONSISTENCY_POLISH APPLIED: start movement 154.0 h -> 119.0 h, distinct starts 68 -> 66`.

| Setting | Effect |
|---|---|
| Instructions → `Shift Consistency Polish` = `Yes` / `No` | On or off for this workbook. Blank means **on** (the default since 2026-10-03). |
| `--shift-consistency-polish` / `--no-shift-consistency-polish` | Command-line override. |

---

## 4. Running on Colab, step by step

Use **`runners/RC922_Colab_B_WITH_DRIVE.ipynb`**. Results go straight to Drive,
so a disconnect does not lose a finished schedule. Use
`RC922_Colab_A_NO_DRIVE.ipynb` only for short runs; it asks you to upload the
ZIP and download the results.

1. Open the notebook in Colab (File → Upload notebook).
   *Runtime → Change runtime type: CPU*, and High-RAM if offered.
2. **Step 1 (Environment):** run it. It installs the pinned solver, scipy and ruff,
   and prints the versions.
3. **Step 2 (Drive):** run it and allow access. It finds
   `RC9_2_2_PRODUCTION_PACKAGE.zip` in MyDrive, `Colab Notebooks`, `Downloads`
   or one folder down. Otherwise, set `ZIP_PATH` to its full path.
4. **Step 3 (Extract):** run it. Set `DRIVE_RESULTS` to where the results
   should go (default `MyDrive/RC922_RC5/RESULTS`).
5. **Step 4 (Verify):** run it. It prints the engine release and sha256.
6. **Step 4b (Check your workbook):** set `WORKBOOK_TO_CHECK`, for example
   `/content/drive/MyDrive/schedules/week42.xlsx`, and run. Continue only on
   `ACCEPTED`.
7. **Step 5 (Run):** set:
   - `MY_WORKBOOK` = the same path as in 4b;
   - `MODE = QUICK` (recommended) or `DEEP`;
   - leave `SEEDS = 0` (automatic: 2 seeds for QUICK, 4 for DEEP), `SINGLE_LONG_RUN = False`, `SKIP_GUARDS = False`;
   - leave `LANGUAGE_WORKING_WINDOW = workbook` (it uses your Instructions sheet);
   - leave `COVERAGE_MEASURE = workbook` to use the workbook's Coverage Objective
     Weighting, or pick `INTERVAL_COUNT` (interval-compliance programs) or
     `VOLUME_WEIGHTED` (service-level programs) for this run (3.5d).

   Run it and keep the tab open. It prints the safety-gate result, then the
   run's progress, then `exit code: 0` for an approved schedule.
8. **Step 6 (Gates):** optional. For your own workbook, gates 2 and 9 say
   `NOT_COMPARABLE`. That is expected: there is no RC9.1 baseline for your
   data, and it does not affect approval.

**How long it takes** (plus the 15–30 min safety gate at the start):

| MODE | What it does | 2 CPUs (free Colab) | 4+ CPUs |
|---|---|---|---|
| QUICK (recommended) | best of 2 × 1-hour seeds | ~2 h | ~1 h |
| DEEP | best of 4 × 1-hour seeds | ~4 h | ~2 h |
| OVERNIGHT | best of 6 × 1-hour seeds | ~6 h | ~3 h |

On free Colab, keep the tab visible; idle sessions disconnect.

**If Colab disconnects:**
- Re-open the notebook and run steps 1–4 again.
- Run step 5 with `RESUME` ticked.
- A schedule already published to Drive is kept. The runner will not overwrite
  it unless you tick `OVERWRITE`.

---

## 5. What to publish

Results are in `DRIVE_RESULTS/<YOUR WORKBOOK NAME>/`.

| File | Use |
|---|---|
| `BUSINESS_OUTCOME.txt` | **Read first.** It must say `Independent validation: PASS` and `Production eligible: True`. |
| `production/*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx` | **The schedule to publish:** shifts and breaks. It opens with *Read Me First*; the *Production Summary* sheet gives target and floor coverage. |
| `production/*_BEST_BEFORE_BREAKS_SCHEDULE.xlsx` | For review only (coverage before breaks). Not for publishing. |
| `packages/*_01_PRODUCTION_ONLY.zip` | The schedule, its validation and the input snapshot in one file, for sending on. |
| `INDEPENDENT_VALIDATION.json` / `.csv` | The validator's full report. |
| `PORTFOLIO/PORTFOLIO_SUMMARY.csv` | Every seed, its exit code and scores. The published run is the best validated seed. |

**Status meanings:**
- `PASS_WITH_QUALITY_WARNINGS` is normal. Every hard rule passed; coverage
  shortfalls are reported as warnings, not hidden. Read them in the *Production
  Summary* and *Validation Log* sheets.
- **Do not publish** if:
  - the notebook's `exit code` is not 0;
  - `BUSINESS_OUTCOME.txt` does not say validation PASS;
  - or there is no `BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx`.

---

## 6. Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| `GUARD SUITE FAILED - refusing to run scenarios` | The package's own tests failed, so the engine is not trusted. | Re-extract the original ZIP; do not edit package files. If it persists, send the notebook output. |
| `ENGINE VERIFICATION FAILED` | The engine file is not the one this package was built with. | Re-extract the original ZIP; never edit or replace package files. |
| `RUNTIME CHECK FAILED` / `RUNTIME DEPENDENCY MISSING` | The wrong solver version, or scipy is missing. | Re-run step 1. Do not install other OR-Tools versions. |
| `HARD_PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE` | A name on last week's sheet is not on the roster. | Section 3.4. |
| `UNRECOGNISED_PREFERENCE_VALUE` | A Preference/Fixed cell holds text the engine cannot classify. | Use a value from 3.3, or add a `Preference Code Mapping` sheet. |
| `HARD_INVALID_INSTRUCTION_BOOLEAN` | A yes/no cell holds something other than `Yes`/`No`. | Section 3.5. |
| `HARD_INVALID_PREFERENCE_MAPPING` | A mapping row's Meaning is not Leave/OFF/blank. | Fix that row. |
| `INPUT_CROSSCHECK_MISMATCH` | The validator's own reading of the workbook disagrees with the engine's (roster, demand or a leave/OFF cell). | Do not publish. Send the workbook and `INDEPENDENT_VALIDATION.json`. |
| `Case is already running` / portfolio `DONE ... exit=1 wall=0.4s ... winner seed=None` | Older packages: a run lock left on Drive by an interrupted run was read as a live run in the new Colab VM, so every seed refused at once. Fixed: a lock now counts only while its run is alive on the same machine, or its heartbeat is under 5 minutes old. | Use this package. With an older one, delete the `RUN_LOCK.json` files under `RESULTS_ROOT/_seeds/<WORKBOOK>/seeds/`. |
| `REFUSED ... exists; pass --overwrite` | Results for this workbook already exist. | Tick `OVERWRITE`, or set a new `DRIVE_RESULTS`. |
| `HARD_RULE_COMBINATION_INFEASIBLE` / "No schedule satisfies all hard rules" | The hard rules contradict each other. With a language window on, the usual cause is a fixed request outside its person's language hours. | Run the pre-check (3.6). It names each conflicting request. See 3.7. |
| Exit code 2, no schedule | The run failed or was refused; the log says why. | Fix the cause and re-run. Never publish from a failed run. |

---

## 7. Running without Colab (optional)

On any Linux or macOS machine with Python 3.11 (4+ CPUs and 8 GB+ RAM
recommended):

```
pip install "ortools==9.15.6755" "openpyxl>=3.1" "scipy>=1.11" "ruff==0.15.8"
cd RC9_2_2_PRODUCTION_PACKAGE
python3 tools/check_input_workbook.py /path/week42.xlsx
python3 runners/rc922_runner.py --input /path/week42.xlsx --mode QUICK --seeds 2 --results-root results_week42
echo $?     # 0 = approved schedule
```
