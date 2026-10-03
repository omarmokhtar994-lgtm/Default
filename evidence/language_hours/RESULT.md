# Language hours on Cricut Voice (2026-10-03)

## What was reported

On a real Voice run, English (domestic) associates were scheduled in
International hours and the other way round. The input's per-day language hours
(for example Spanish 18:00-05:00 Mon-Fri, 19:00-06:00 Sat-Sun) could not be found.

## Findings

1. **Language hours are not enforced unless `Language Working Window` is set.**
   - Language Setup's Coverage Start/End limit when a language's associates may
     start work only when Instructions -> `Language Working Window` is
     `MINIMUM_ROWS`, `ALL_ROWS` or `REQUIRED_LANGUAGE_ONLY`.
   - The default is `OFF`. RC5 and FINAL behave identically here: the language
     parsing and window functions are the same code. The only difference is that
     FINAL also accepts the spellings "All Days", "Every Day" and "7 Days".
   - `MINIMUM_ROWS` enforces only rows with Minimum Per Interval > 0, and both
     Voice rows have minimum 0, so it would enforce nothing. `ALL_ROWS` is the
     setting that keeps each team inside its hours.
   - Measured on the 12 Voice runs of the F-03 experiment (mode OFF):
     - FINAL put 22 to 24 of 159 shifts outside their language's hours;
     - RC5 put 23 to 30 outside;
     - examples: English 09:00-18:00 and 05:00-14:00 against English hours of
       16:00-03:00.
2. **The shipped Voice workbook's layout has no control for this.**
   - `inputs/Cricut_Voice_RC9_1_READY_SKELETON.xlsx` is baseline-protected and keeps its bytes.
   - It has no `Language Working Window` row and no `Coverage Days` column.
   - Its International row is 00:00-23:00, which restricts nothing.
   - `tools/build_input_template.py` adds both controls (and a Coverage Split
     sheet). The per-day hours were always supported through one Language Setup
     row per set of days in `Coverage Days`, in RC5 as in FINAL.
3. **The roster labels do not match the hours.**
   - Four associates labelled English have fixed requests starting at 03:00-05:00,
     which are International hours: Jhonny Mascarenhas, Meraj Shaikh, Jojie Lovino
     and Sharmaine Magtoto.
   - With the window on, those 20 fixed requests contradict it. The run is then
     refused as "no schedule satisfies all hard rules", and the message does not
     say why.

## Changes

- `tools/check_input_workbook.py` adds section **4. language hours**:
  - shows the mode and each language's hours per day;
  - warns when hours are authored but not enforced (OFF), or not enforced
    because of MINIMUM_ROWS with minimum 0;
  - lists by name and day every fixed request that starts outside its person's
    hours. With the window on, this refuses the workbook (exit 1); with it OFF,
    it is a note.
  - Tests: `tests_staged/test_rc9_2_25_input_vocabulary.py::ThePreCheckShowsTheLanguageHours`.
  - The engine is unchanged (sha256 `251cf35a...`).
- `PRODUCTION_RUN_GUIDE.md` adds section 3.7 (language hours, the modes, per-day
  rows, start-only rule, overnight rows, roster labels, fixed-request conflicts)
  and a troubleshooting row.
- **`Cricut_Voice_LANGUAGE_HOURS.xlsx`** is a new input sheet. The shipped workbook
  is not modified. This copy is converted with `build_input_template.py`, then:
  - `Language Working Window = ALL_ROWS`;
  - International hours set to 00:00-16:00, the earliest International fixed
    request starts at 00:00;
  - English hours left at 16:00-03:00;
  - `Coverage Days = All` on both rows;
  - the four associates above relabelled `International` on the Schedule sheet.
    This is a roster change made on request, and it should be confirmed against
    the real team list.

## Runs

Both runs were QUICK, 900 s, 4 workers, seed 9000, with the engine at commit d06427f.

| run | input | mode | result | validator | after_target | shifts outside hours |
|---|---|---|---|---|---|---|
| first try | Voice + Intl 03:00-16:00, ALL_ROWS | ALL_ROWS | refused: hard rules infeasible (fixed requests outside hours) | not run | - | - |
| VOICE_ALLROWS2 | test copy: per-day English rows (Mon-Fri 16-03, Sat-Sun 17-04), Intl 00-16, 4 relabelled | ALL_ROWS (CLI) | PASS_WITH_QUALITY_WARNINGS, exit 0 | PASS, 0 hard | 245 / 254 floor | 0 of 159 |
| VOICE_FINAL_SHEET | `Cricut_Voice_LANGUAGE_HOURS.xlsx` | ALL_ROWS (workbook) | PASS_WITH_QUALITY_WARNINGS, exit 0 | PASS, 0 hard | 247 / 252 floor | 0 of 159 |

**Independent check of VOICE_FINAL_SHEET.** The 159 shift cells were read from
the output workbook's Schedule sheet, not from the engine's report. All of them
start inside their language's hours:

- English starts: 16:00-22:00 and 00:00;
- International starts: 00:00-05:00, 10:00, 11:00 and 14:00.

**Coverage.** With mode OFF, 1 h runs of the same engine scored after_target
245-248 (F-03). Enforcing the hours here cost no measurable coverage, on a
15-minute run.

## Follow-up: the failure message and the validator (2026-10-03)

**Engine message.** A hard-rule contradiction used to print each
constraint-isolation row as a raw solver dump under "Main blockers". The wrapper
then replaced the engine's diagnosis in `BUSINESS_OUTCOME.txt` with "the engine
output problem", so the reason never reached the results folder. Now:

- `build_business_outcome` names the conflicting rule families in plain words:
  the refined core when it was computed, otherwise each family whose relaxation
  alone makes a schedule possible.
- It lists every fixed request that starts outside its associate's enforced
  language window, using `fixed_requests_outside_language_windows`. The
  pre-check calls the same function.
- `RUN_UNIVERSAL_PRODUCTION.py` keeps the engine's diagnosis for
  FAIL_HARD_CONTRACT_INFEASIBLE and FAIL_HARD_CONTRACT_UNKNOWN. It also writes the
  findings, the named requests and the actions into `BUSINESS_OUTCOME.txt`.

These are reporting changes only; no solve path changed. The engine sha256 is
now `d449b6f2...`; it was `251cf35a...`. End to end on the same input as the
first refused run, the result is in `VOICE_CONFLICT_MSG2/BUSINESS_OUTCOME.txt`:

    Outcome: No schedule satisfies all hard rules together
    ... The rules that conflict: language rules (...); fixed requests (Fixed Request sheet).
    Main blockers:
    - fixed requests (Fixed Request sheet): relaxing this rule alone makes a schedule possible
    Affected examples:
    - Jhonny Mascarenhas (English) | Mon | fixed 05:00 - 14:00 | language hours 16:00-03:00

**Validator.** `independent_validator.py` checked shift starts against language
hours only under ALL_ROWS and MINIMUM_ROWS. Its REQUIRED_LANGUAGE_ONLY check sat
inside that branch and could never run. The engine enforces the hours in all
three modes, so a REQUIRED_LANGUAGE_ONLY schedule was not independently checked
at all.

- Both checks now run in every enforced mode.
- The tests use the enforced Voice run as a fixture. Two of the three fail on the
  old validator.
- No shipped or fixture workbook uses REQUIRED_LANGUAGE_ONLY (59 OFF, 2
  ALL_ROWS), so no existing result changes.
