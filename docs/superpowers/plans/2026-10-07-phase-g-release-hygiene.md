# Phase G: release hygiene (owner's "group 2") Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a package that carries its own current gate result, explain every "no schedule" verdict, measure how the new verdict reads on stored runs, settle the Colab shortfall-test failure with evidence, and close the Phase E exception-cell follow-up.

**Architecture:** Tooling changes in `tools/` (package builder, release gate report), one default-neutral engine change (exception-cell threshold through the existing helper), and two measurement tasks (stored-run replay, CPU-constrained test reproduction) that change no code.

**Tech Stack:** Python 3.11, OR-Tools CP-SAT 9.15, openpyxl, unittest.

**Spec:** Owner, 2026-10-07: "Go ahead with full group 2" (items listed in chat: refresh package evidence + clean-extract gate; Colab shortfall test; replay stored gate reports; "impossible vs ran out of time" statuses; Phase E exception-cell follow-up). Background: `evidence/external_reviews/CHATGPT_FINAL_AUDIT_2026_10_07_EVALUATION.md` (P0-02, P1-03, next steps 2-4); Phase E ledger ruling on `critical_exception_cells`.

## Global Constraints

- `CLAUDE.md`: failing test first; never edit a test to pass; protected workbooks and `engine/regression_assets` byte-identical; historical evidence files are never rewritten (new dated records only); no speculative behaviour change; designated branch; Egypt time.
- Gate `run_tests.sh` + `tests_staged/GATE_MINIMUMS.json`; raise `min_tests` by the tests added.
- After the engine change (Task 5): `tools/refresh_engine_identity.py --previous 65aae56861b9...` (full sha from SCENARIOS.json).
- No full gate or package build while Task 2 measures (CPU contention).

## Review Focus

- A gate that fails inside the staged package must still leave no package and no gate record claiming PASS (Task 1 test `test_a_failing_gate_is_recorded_as_fail`).
- A run with no BUSINESS_OUTCOME.json must keep today's verdict and say the reason is unknown, not guess (Task 4 test `test_missing_outcome_is_named_unknown`).
- With "Exact Coverage Units" off, exception cells must be identical to today (Task 5 test `test_switch_off_cells_unchanged`).
- Stored runs without a validation file are counted as NOT_RELEASABLE "validation never ran", not skipped (Task 3 report column).
- The shortfall reproduction must record every run, including passes, so a rare failure is not hidden (Task 2 log).

---

### Task 1: package carries its own gate result

**Files:**
- Modify: `tools/build_production_package.py`
- Test: `tests_staged/test_rc9_2_50_package_gate_record.py`

**Interfaces:**
- Produces: `gate_record(stdout: str, returncode: int) -> dict` with keys `status` ("PASS"|"FAIL"), `tests` (int|None), `skipped` (int|None), `result_line` (str). Parses `GATE PASS — N suite(s), T tests (S skipped)`; any non-zero returncode is FAIL regardless of text.
- `build()` writes `PACKAGE_GATE_RESULT.txt` (full gate stdout) into the package root and adds `"gate": gate_record(...)` plus `"built_utc"` to `MANIFEST.json`; it still refuses to package on FAIL.

- [ ] Step 1: failing tests: `test_pass_line_is_parsed` (1483 tests, 2 skipped, PASS), `test_a_failing_gate_is_recorded_as_fail` (returncode 1 with a PASS-looking line -> FAIL), `test_builder_writes_the_record_into_the_package` (source names `PACKAGE_GATE_RESULT.txt` and `"gate"` in the manifest, same pattern as `test_package_builder_excludes_legacy_colab_notebooks`).
- [ ] Step 2: run, confirm failures; save to `evidence/phase_g/G1_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: implement.
- [ ] Step 4: tests pass; commit.
- [ ] Step 5 (after Tasks 4-5 land): `python3 tools/build_production_package.py`; record zip sha256, file count, gate line in `evidence/phase_g/G1_PACKAGE_BUILD.md`. The old `CLEAN_EXTRACT_GATE_PILOT.txt` stays as history.

### Task 2: shortfall test at Colab-like CPU (measurement, no code change)

- [ ] Run `tests_staged/test_rc9_2_32_phase_c_shortfall.py::C1ShortfallPass::test_the_pass_exports_a_listed_non_releasable_schedule` 10 times pinned to 2 cores (`taskset -c 0,1`) with 2 competing busy processes on the same cores, then 5 times unloaded on 2 cores. Log every run (pass/fail, wall time, assertion message listing the shortfall days) to `evidence/phase_g/G2_SHORTFALL_REPRO.md`.
- Reading (written before the runs): a failure is a regression only if the extra shortfalls also appear unloaded or the model proves them avoidable; if they appear only under load, the test encodes a time-limited search outcome. Either way the test is not edited here; a test change, if any, is proposed to the owner with the evidence.

### Task 3: replay stored gate reports (measurement, no code change)

- [ ] Run `tools/release_gate_report.py` on each stored run family under `evidence/raw_runs/*` and the Phase F runs; tabulate per program: RELEASABLE / REVIEW_REQUIRED / NOT_RELEASABLE and the failing gates. Write `evidence/phase_g/G3_VERDICT_REPLAY.md` (+ JSON). Runs on engines older than the verdict code are replayed as stored; the table says which engine each family ran on.

### Task 4: release verdict names why there is no schedule

**Files:**
- Modify: `tools/release_gate_report.py`
- Test: `tests_staged/test_rc9_2_51_verdict_no_schedule_reason.py`

**Interfaces:**
- Consumes: `release_verdict(row) -> dict` (Phase F).
- Produces: the report row gains `outcome_category` and `outcome_code` read from the case's `BUSINESS_OUTCOME.json` (missing file -> both ""). When gate 8 is NO_EVIDENCE, `release_verdict` adds one note: SEARCH_INCOMPLETE -> "no schedule: the search ran out of time; this is not proof the week is impossible"; outcome_code HARD_RULE_COMBINATION_INFEASIBLE -> "no schedule: the hard rules contradict each other (proven)"; any other or missing -> "no schedule: reason not recorded (see BUSINESS_OUTCOME / audit)". Verdict values unchanged.

- [ ] Step 1: failing tests `test_search_ran_out_is_named`, `test_proven_contradiction_is_named`, `test_missing_outcome_is_named_unknown`, `test_verdict_value_unchanged` (all three stay NOT_RELEASABLE).
- [ ] Step 2: run, confirm failures; save `evidence/phase_g/G4_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: implement; banner prints the note.
- [ ] Step 4: pass; commit.

### Task 5: exception cells use the coverage threshold helper

**Files:**
- Modify: `engine/_tools/l632_universal_scheduler.py` (`critical_exception_cells`, hard-floor branch)
- Test: `tests_staged/test_rc9_2_52_exception_cells_threshold.py`

**Interfaces:**
- Consumes: `coverage_hit_threshold_units(parsed, day, interval, ratio) -> int` (Phase E).
- Change: replace `ceil_units(req * hard_floor_ratio) * qpi` with `coverage_hit_threshold_units(parsed, d, i, hard_floor_ratio)`; legacy path returns the same expression, so default output is unchanged.

- [ ] Step 1: failing test `test_switch_on_uses_exact_threshold`: a hard-floor workbook (Exact Coverage Units = Yes) where legacy and exact thresholds differ; a cell the metric says still hits after removing one head is not marked critical. Plus `test_switch_off_cells_unchanged` (same cells as a recomputation with the legacy expression).
- [ ] Step 2: run, confirm the first fails; save `evidence/phase_g/G5_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: implement; `refresh_engine_identity.py --previous <old>`.
- [ ] Step 4: tests pass; full gate; raise `min_tests`; commit; push.

Order: 4, 5, 1 (steps 1-4), full gate, 1 step 5 (package build runs the gate inside), 3, 2 (alone on the machine).
