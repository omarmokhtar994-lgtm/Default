# Phase F: release verdict, optional half-hour starts Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every run state plainly whether its schedule is releasable, and add an optional, marked :30-start fallback.

**Architecture:** F1 adds one verdict function to the release gate report and writes it to a status file and the exit code. No schedule changes. F2 adds an input switch, default No, that widens the shift library with :30 variants carried at a Stage-1 penalty and marks them in the output. F3 and F4 are measurement tasks with no engine change.

**Tech Stack:** Python 3.11, OR-Tools CP-SAT 9.15, openpyxl, unittest (`python3 -m unittest`).

**Spec:** Owner decisions of 2026-10-07 in chat (recorded in `evidence/external_reviews/CHATGPT_FINAL_AUDIT_2026_10_07_EVALUATION.md`, "Decisions that need Omar", answered):
- floor vs target follows each program's coverage measure (already implemented, F-36; no change);
- :30 starts optional in the input sheet;
- release checks: owner deferred ("ignore if not important"). Claude's safe default below: never hides or blocks a schedule; only hard-rule failure is not releasable.

## Global Constraints

- `CLAUDE.md` rules: failing test first; no test weakened or edited to pass; protected workbooks and `engine/regression_assets` byte-identical; no speculative behaviour change (F2 default No, measured before any default change); designated branch only; Egypt time.
- Release gate `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`; raise `min_tests` by the tests added.
- After any engine change, run `tools/refresh_engine_identity.py --previous <old sha>`.

## Review Focus

- A workbook with no protected minimum configured (every ready-to-edit program today) must not become REVIEW_REQUIRED for that reason alone; the check is listed as not evaluated.
- An independent validation that was never run must not read as releasable.
- Several cases in one results folder: the run verdict is the worst case verdict.
- The Colab notebook must keep its artifacts and finish normally for REVIEW_REQUIRED.
- F2 with the switch absent: parsed default No, contract fingerprint unchanged, shift library unchanged.

---

### Task 1: (F1) release verdict

**Files:**
- Modify: `tools/release_gate_report.py` (new `release_verdict`, `main()` writes `RELEASE_VERDICT.json` and returns the exit code)
- Test: `tests_staged/test_rc9_2_47_release_verdict.py`

**Interfaces:**
- Produces: `release_verdict(row: dict) -> dict` with keys `verdict` ("RELEASABLE" | "REVIEW_REQUIRED" | "NOT_RELEASABLE"), `failed` (list of str), `not_evaluated` (list of str), `notes` (list of str).
- Policy (from the spec's safe default):
  - NOT_RELEASABLE when gate 8 is FAIL or NO_EVIDENCE.
  - REVIEW_REQUIRED when gate 4 or gate 5 is FAIL.
  - `not_evaluated` lists gate 4 PASS_PROTECTED_NOT_EVALUATED and gate 5 UNKNOWN attribution / PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD; these never change the verdict alone.
  - RELEASABLE otherwise.
- Run verdict = worst case. `main()` returns 3 when any case is NOT_RELEASABLE, else 0. The runner already returns this code as `gate_rc`.

- [ ] Step 1: failing tests (literal expectations):
  - `test_all_gates_pass_is_releasable`
  - `test_gate5_fail_is_review_required_and_named`
  - `test_unconfigured_protected_tier_alone_stays_releasable_but_is_listed_not_evaluated`
  - `test_validator_fail_is_not_releasable`
  - `test_validator_never_run_is_not_releasable`
  - `test_main_writes_the_verdict_file_and_exits_3_only_for_not_releasable`, using the `_case` fixture pattern from `test_rc9_2_1c_tooling_integrity.py`
- [ ] Step 2: run, confirm failures (function missing), save to `evidence/phase_f/F1_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: implement; print a one-line banner per case and overall.
- [ ] Step 4: tests pass; full gate green; commit.

### Task 2: (F2) optional half-hour starts (detailed in its own brief when F1 is done)

Decisions fixed now:
- Instruction "Allow Half-Hour Starts" (Yes/No, default No; in `BOOLEAN_INSTRUCTION_ALIASES`; contract key only when on).
- When on, each library shift without a :30 twin gets one starting 30 minutes later, same length, flagged `half_hour_fallback`.
- Stage 1 charges a per-use penalty below every coverage term, so a :30 start is chosen only when it adds coverage.
- The output marks each :30 assignment, with a count in Production Summary.
- Tests:
  - switch default off: library and contract unchanged;
  - on: twins exist and are flagged;
  - on, with a demand that :00 starts can cover: no :30 used;
  - on, with a demand only :30 covers: :30 used and marked;
  - validator accepts the flagged shifts.
- Measurement after merge: 3 programs, off vs on, production runner. The rule is written before the runs.

### Task 3: (F3) shortfall test reproduction (no engine change)

- [ ] Run `tests_staged/test_rc9_2_32_phase_c_shortfall.py` repeatedly under Colab-like CPU (2 cores pinned with `taskset`, competing load) and record which shortfall days appear. The report decides: engine regression, or an over-specific test (time-limited search outcome). The test is not edited unless the evidence shows its contract was wrong, and then only with a written reason.

### Task 4: (F4) Stage-1 probe with production-like start (no engine change)

- [ ] Give `tools/stage1_ab_probe.py` the production warm start: each arm first runs the hard-feasibility probe, and the measured profile is hinted with it. Drop programs where the probe is infeasible under production hard rules (record them). Re-register Task 3's rule before any run, then run it.

### Order change (owner, 2026-10-07 ~06:40 Egypt)

Do Task 2 (:30 starts) next, then Task 5 (break-rule what-if); Tasks 3 and 4 are
deferred (cleanup / small expected value).

### Task 5: (F5) break-rule what-if (measurement only, no engine change)

- [ ] For Cricut Chat and AE IT B2B, copy the workbook and change one break rule
  at a time (concurrent-break ratio 0.3 -> 0.4; widen break windows by one
  quarter each side), run the production runner (QUICK 3,600 s, 2 workers,
  seed 9000), and report intervals at target and floor after breaks versus
  the unchanged control. The owner decides any rule change; nothing is
  changed in the real workbooks.
