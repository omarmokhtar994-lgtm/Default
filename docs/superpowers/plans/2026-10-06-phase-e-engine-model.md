# Phase E: engine model findings Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Act on the review's findings F-E3, F-E1 and F-E2 with measurement first and
engine changes only behind failing tests and pre-registered A/B rules.

**Architecture:** F-E3 is an offline diagnostic tool (no engine change) that scores saved
weeks with two Stage-1 break stand-ins against the engine's after-break metric. F-E1 replaces
percent-unit coverage thresholds with exact ones in four models, behind an instruction
switch, default off until its A/B passes. F-E2 is a run-parameter A/B (profile order and
slice length), no code change unless it passes.

**Tech Stack:** Python 3.11, OR-Tools CP-SAT 9.15, openpyxl, unittest (`python3 -m unittest`;
pytest is not installed).

**Spec:** `evidence/phase_e/ENGINE_MODEL_REVIEW.md` (findings F-E1 to F-E4).

## Global Constraints

- Project rules in `CLAUDE.md` outrank this plan (protected workbooks and `engine/regression_assets` byte-identical; no test weakened; no speculative behaviour change; designated branch only; Egypt time).
- Every engine change: failing test first, then the change, then `run_tests.sh` against `tests_staged/GATE_MINIMUMS.json` (min_tests 1436, max_skips 3; raise min_tests by the tests added).
- No engine edit while a measured run is in flight (packager identity check).
- Production A/B settings: production runner, QUICK 3,600 s, 2 workers, seed 9000, two runs at a time; rules written into `evidence/phase_e/E_PLAN.md` and committed before the first run.
- Load the matching skill at the start of each step (CLAUDE.md list).

## Review Focus

- Interval with shrinkage 1.0 (eff 0): exact threshold must not divide by zero; the interval stays unreachable, as in the metric.
- Interval with requirement 0 or blank: no hit variable created, as today.
- 60-minute intervals (qpi 4) and 15-minute intervals (qpi 1): thresholds exact for every qpi.
- Carry-in (previous Saturday) quarters: included with the same exact scale on both sides.
- Workbooks with the switch absent: parsed default off, input-contract fingerprint unchanged.

---

### Task 1: F-E3 offline break stand-in diagnostic

**Files:**
- Create: `tools/break_proxy_diagnostic.py`
- Test: `tests_staged/test_rc9_2_45_break_proxy_diagnostic.py`
- Output: `evidence/phase_e/E1_BREAK_PROXY_DIAGNOSTIC.json`, section in `evidence/phase_e/E_PLAN.md`

**Interfaces:**
- Produces: `presence_profile(E, p, shift) -> List[float]` (per-quarter presence of one head on `shift`; flat = (paid - break)/paid everywhere; window-aware = 1 - share of legal patterns of that duration breaking at that offset); `predicted_after_hits(E, p, skeleton, mode: str) -> int` with mode in {"flat", "window"}.

- [ ] Step 1: failing tests: `test_flat_profile_is_constant_and_matches_productive_coeff` (each quarter == (duration_q - break_quarters_for)/duration_q); `test_window_profile_is_1_outside_every_break_window_and_sums_to_the_same_paid_presence` (sum over offsets equal to flat sum within 1e-9; value 1.0 at offset 0 and at the last offset of a 9 h shift).
- [ ] Step 2: run, see both fail (module missing).
- [ ] Step 3: implement both functions and a CLI scoring every saved real-program week (engine outputs under the scratchpad and `evidence/`) with `calculate_metrics` before/after, the two predictions, and the per-week error; report mean absolute error and rank correlation per mode.
- [ ] Step 4: tests pass; run the CLI; write results.
- [ ] Step 5: decision recorded: proceed to a window-aware Stage-1 change only if window MAE is at most half of flat MAE on the real programs; otherwise close F-E3. Commit.

### Task 2: F-E1 exact coverage thresholds (switch, default off)

**Files:**
- Modify: `engine/_tools/l632_universal_scheduler.py` (Stage 1 `build_skeleton` coverage block; `solve_breaks` units; `aggregate_pattern_mix_guidance` thresholds; `run_shortfall_pass` checks; `ParsedInput` field `exact_coverage_units: bool = False`; instruction "Exact Coverage Units" Yes/No in `BOOLEAN_INSTRUCTION_ALIASES`; `input_contract_payload` adds the key only when True)
- Test: `tests_staged/test_rc9_2_46_exact_coverage_units.py`

**Interfaces:**
- Produces: `coverage_hit_units(parsed, d, i, ratio) -> Tuple[int, int]` returning (per-head-quarter coefficient, threshold) such that `coef * head_quarters >= threshold` holds exactly when the metric's `eff * head_quarters / qpi >= ratio * req - 1e-9` (exact mode), or the current percent units (legacy mode).

- [ ] Step 1: failing tests: `test_exact_units_agree_with_the_metric_threshold_for_every_real_interval` (all 7 ready-to-edit workbooks, target and floor ratios: minimum head-quarters from `coverage_hit_units` == from the metric formula); `test_legacy_units_are_unchanged_when_the_switch_is_off` (equals today's `round(eff*100)`, `ceil_units(req*ratio)*qpi`); `test_switch_default_off_and_contract_fingerprint_unchanged`; review-focus cases (eff 0, req 0, qpi 1/2/4).
- [ ] Step 2: run, confirm failures are the expected ones (missing function / field), save output to `evidence/phase_e/E2_TESTS_BEFORE_FIX.txt`.
- [ ] Step 3: implement `coverage_hit_units` and route the four models through it (exact scale = `JOINT_COVERAGE_SCALE`, coefficient = round(eff x scale), threshold = ceil(req x ratio x qpi x scale), checked against the metric in the test).
- [ ] Step 4: tests pass; full gate `run_tests.sh` green with min_tests raised; protected-baseline byte check.
- [ ] Step 5: pre-register in `E_PLAN.md`, then A/B on the 7 real programs (switch on vs off, same engine file). Rule: every run exit 0 / validator PASS / 0 hard failures; no program loses more than 1 interval at target or at floor; summed after-target >= control. Default flips to on only if it passes. Commit each step.

### Task 3: F-E2 Stage-1 portfolio order and slices (run-parameter A/B)

**Files:**
- Record: `evidence/phase_e/E_PLAN.md`, `evidence/phase_e/E3_PORTFOLIO_AB.json`

- [ ] Step 1: from the 98 saved audits, fix the treatment before running: `--skeleton-profiles` ordered by shipped-schedule yield (target90_restore_champion, target_floor_pareto_master, target90_restore_productive, floor_gate_hunter_before, then the rest in current order), same total budget. Pre-register the rule (same as Task 2 Step 5).
- [ ] Step 2: run treatment vs control on the 7 real programs, two at a time, engine untouched.
- [ ] Step 3: apply the rule; if it passes, propose the runner default change as its own task with a failing test; otherwise record and close. Commit.
