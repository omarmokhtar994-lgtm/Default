# Phase H: one output look, 11H/3OFF associate limit, simpler Colab Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every schedule workbook the user opens has the agreed layout and honest labels; a workbook can cap how many associates work the 11H/3OFF pattern; both Colab notebooks run in three steps with no typed paths.

**Architecture:** Task 1 changes the output polisher (before-breaks role) and the production runner (top-level copies = the validated polished files, raw engine copies kept under `debug/raw_engine_output/`). Task 2 adds one instruction, parsed into `ParsedInput`, enforced in both CP-SAT models that create `long_mode`, checked before solving, checked independently by the validator, and reported in Production Summary. Task 3 rewrites the two notebooks into Setup / Your workbook / Run cells, keeping every safeguard the existing tests pin.

**Tech Stack:** Python 3.11, OR-Tools CP-SAT 9.15, openpyxl, unittest, Jupyter nbformat 4 JSON.

**Spec:** Owner, 2026-10-07 chat: "refine now colab runner make it easier for me as a user to use it without efforts"; "make sure all output sheets are using the same agreed visuals as before break and after break i think still using the old visuals"; "add an option to use 11/3 shift but with a count like 1 slot only or 2". Answers: 11/3 = an 11-hour shift (the engine's existing 11H/3OFF pattern); count = "Max total slots per week ... if i ask for 2 i expected 2 associates only with full shift 11 hours"; both notebooks; results download keeps everything, as today.

## Global Constraints

- `CLAUDE.md`: failing test first; no test weakened; a re-pin only with the reason in the test; protected workbooks and `engine/regression_assets` byte-identical; default behaviour unchanged (the new instruction is blank = no limit); designated branch; Egypt time.
- Gate `run_tests.sh` + `GATE_MINIMUMS.json` (raise `min_tests`); after the engine change `tools/refresh_engine_identity.py --previous <old sha>`; package rebuilt with `tools/build_production_package.py`.
- Notebook safeguards stay (pinned by tests): `rc922_runner.py`, `start_new_session`, `KeyboardInterrupt`, `--resume`, `--overwrite`, `SEEDS`, `RESUME = True`, the solver pins, the COVERAGE_MEASURE param line and `cmd += ["--coverage-objective-weighting", COVERAGE_MEASURE]`, `/content/drive/MyDrive/RC922_RC5` (B), `RC9_2_2_FIX_VALIDATION_RC5.zip` (A).

## Review Focus

- A run whose independent validation FAILED must not put a file at the top level that looks approved: the top-level copy is the polished file whose Read Me already states the status (Task 1 test `test_failed_validation_still_publishes_the_polished_file_with_its_status`).
- 11H limit with a workbook whose library has only 11-hour shifts (every associate is forced long): a limit below the working roster is a named pre-solver conflict, not a silent infeasible solve (Task 2 test `test_limit_below_forced_long_associates_is_named`).
- 11H limit typed as "2.0", " 2 ", or "two": the first two read as 2; "two" is a named input error (Task 2 test `test_limit_values`).
- 11H limit set while "Use 11H/3OFF" is No: no effect; Production Summary says so; not an error (Task 2 test `test_limit_without_11h_mode_is_inert`).
- A notebook cell with a Python syntax error is only found on Colab: every code cell must compile locally (Task 3 test `test_every_code_cell_compiles`).

---

### Task 1: one output look

**Files:**
- Modify: `engine/production/production_output_polisher.py` (`_build_dashboard`, `_arrange_tabs`/`_apply_output_theme` for role `BEST_BEFORE_BREAKS_SCHEDULE`)
- Modify: `engine/RUN_UNIVERSAL_PRODUCTION.py` (new `publish_top_level_copies`, called after packaging)
- Test: `tests_staged/test_rc9_2_53_one_output_look.py`

**Interfaces:**
- Produces: `publish_top_level_copies(case_root: Path) -> list[str]`: for each of `*_BEST_BEFORE_BREAKS_SCHEDULE.xlsx` and `*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx` that has a `production/` counterpart, move the raw top-level file to `debug/raw_engine_output/` and copy the production file to the top level (byte-identical); returns the names replaced. Missing production copy: leave the top-level file untouched.
- Before-breaks role: dashboard cards "Before Target" / "Before Floor" from "Before Target Hits" / "Before Floor Hits"; sheet "FT Wise After Breaks" renamed "FT Wise Before Breaks"; the empty "Break Schedule" sheet removed; Read Me instruction lines name the sheets that exist.

- [ ] Step 1: failing tests:
  - `test_before_breaks_dashboard_says_before`: polish a before-breaks fixture (`fixtures/real_runs/before_break/`); Read Me cards read "Before Target"/"Before Floor"; no "After Target" text on Read Me.
  - `test_before_breaks_has_no_after_or_empty_break_sheets`: sheet names include "FT Wise Before Breaks"; exclude "FT Wise After Breaks" and "Break Schedule".
  - `test_after_breaks_unchanged`: after-breaks role keeps its sheet list and "After Target".
  - `test_top_level_copies_are_the_validated_production_files`: temp case root with raw + production files; after the call, top-level bytes == production bytes and the raw files are under `debug/raw_engine_output/`.
  - `test_failed_validation_still_publishes_the_polished_file_with_its_status` (Review Focus).
  - `test_no_production_copy_leaves_the_top_level_file`.
- [ ] Step 2: run, confirm failures; save `evidence/phase_h/H1_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: implement; grep every reader of "FT Wise After Breaks" and "Break Schedule" and of top-level BEST files (validator, release gate, portfolio, resume, packager) and keep each working; ledger what was checked.
- [ ] Step 4: tests + the output/polisher/runner suites pass; commit.

### Task 2: Max 11H/3OFF associates per week

**Files:**
- Modify: `engine/_tools/l632_universal_scheduler.py` (parse, `ParsedInput`, contract payload, `validate_input_contract`, `build_skeleton` long-mode block ~7553, `solve_joint_shift_off_language_break_refinement` ~16467, Production Summary rows)
- Modify: `engine/tools/independent_validator.py` (count check + raw cross-check)
- Modify: `tools/build_input_template.py` ("Shift & OFF" row, alias, help)
- Test: `tests_staged/test_rc9_2_54_11h_associate_limit.py`

**Interfaces:**
- Instruction "Max 11H/3OFF Associates" (aliases "Maximum 11H/3OFF Associates", "Max 11H 3OFF Associates"); whole number >= 1; blank = no limit.
- `ParsedInput.max_11h_associates: Optional[int] = None`; contract key `max_11h_associates` only when set.
- Invalid value -> parser warning `HARD_INVALID_11H_ASSOCIATE_LIMIT` (run refused, named).
- Models: when set and `use_11h_3off`, `sum(long_mode[a]) <= max_11h_associates` in both models.
- Pre-solver: associates forced long (fixed long-shift requests, or a long-only library) above the limit -> `validate_input_contract` failure `11H_ASSOCIATE_LIMIT_BELOW_FORCED`, naming them.
- Validator: associates whose week has a shift >= `LONG_SHIFT_MIN_DURATION_MIN` above the limit -> hard failure `11H_ASSOCIATE_LIMIT_EXCEEDED`; raw instruction cell cross-checked against the parse.
- Production Summary (only when Use 11H/3OFF is Yes): "Max 11H/3OFF Associates" (number or "No limit") and "11H/3OFF Associates Used".

- [ ] Step 1: load `cpsat-engine-modeling`; failing tests:
  - `test_default_is_no_limit_and_contract_unchanged`
  - `test_limit_values` ("2"->2, "2.0"->2, " 2 "->2, "two"/"0"/"-1" -> HARD warning)
  - `test_limit_caps_the_long_pattern`: 9h + 11h library, Use 11H/3OFF Yes, demand that favours 11h; without the limit more than 1 associate is long; with limit 1 exactly <= 1 is long (solved, elastic HardConfig like test_rc9_2_48).
  - `test_limit_without_11h_mode_is_inert`
  - `test_limit_below_forced_long_associates_is_named`
  - `test_validator_fails_a_week_over_the_limit` (inject a second long associate)
  - `test_summary_rows`
- [ ] Step 2: run, confirm failures; save `evidence/phase_h/H2_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: implement; refresh engine identity.
- [ ] Step 4: tests + 11H-related existing suites pass; commit.

### Task 3: three-step Colab notebooks

**Files:**
- Modify: `packages/rc9_2_2_production/runners/RC922_Colab_A_NO_DRIVE.ipynb`, `RC922_Colab_B_WITH_DRIVE.ipynb`
- Modify (re-pin, reason in test): `tests_staged/test_rc9_2_35_phase_c_coverage_measure_choice.py` (Run cell found by its runner call instead of the title "5. Run")
- Test: `tests_staged/test_rc9_2_55_colab_three_steps.py`

**Layout (both):** markdown intro (3 steps, what you get), then code cells "#@title 1. Setup", "#@title 2. Your workbook", "#@title 3. Run".
- Setup: pins; A uploads the package ZIP with a button (skips if already extracted); B mounts Drive and finds the ZIP (existing shallow search), results on Drive.
- Your workbook: an upload button (`files.upload()`) saving to `/content/inputs/`; B also accepts a Drive path; each workbook checked at once with `tools/check_input_workbook.py`, ACCEPTED/REJECTED printed.
- Run: MODE (default QUICK), SEEDS = 0, COVERAGE_MEASURE, RESUME = True; runs every uploaded workbook with today's command and safeguards, then `release_gate_report.py`, prints one verdict line per workbook, then A zips and downloads RESULTS_ROOT, B writes the zip next to the Drive results.

- [ ] Step 1: failing tests: `test_three_code_steps` (exactly 3 code cells titled as above), `test_workbook_is_uploaded_with_a_button`, `test_run_checks_runs_scores_and_delivers` (order: check_input_workbook.py < rc922_runner.py < release_gate_report.py < download/zip), `test_every_code_cell_compiles` (strip `!`/`%` lines, `compile()`), plus all safeguard needles listed in Global Constraints.
- [ ] Step 2: run, confirm failures; save `evidence/phase_h/H3_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: rewrite both notebooks; re-pin the coverage-choice test's cell lookup with its reason.
- [ ] Step 4: notebook suites pass; commit.

### Finish

- [ ] Full gate; raise `min_tests`; push; rebuild package (gate inside); update `PRODUCTION_RUN_GUIDE.md` steps; render the new before/after Read Me pages and the notebook cells for the owner.
