# Phase C result: graceful degradation and schedule quality

Started from commit `407a725` (engine sha256 `38f494d9…`). Engine after Phase C: sha256 `a2d4e7a1…` (commit `f326be4`).

Every rule was written and pushed before its code or its runs:

| Rule | Commit | What it decides |
|---|---|---|
| `C1_RULE.txt` | `85d4e0b` | Shortfall schedule (F-06) and the next-Sunday floor (F-07): R1–R7 |
| `F33_RULE.txt` | `e6ee6b1` | Whether the Stage-2 expression fix ships for normal runs |
| `C3_RULE.txt`, `C4_RULE.txt` | `c5bc453` | The AE_IT Stage-1 shape test; the volume-weighting switch |

Changes made after a rule was pushed are recorded in `C1_AMENDMENTS.txt` and `C4_AMENDMENTS.txt`. None of them changes a measurement or a pass rule.

Every fix was written test-first:
- `C1_TESTS_BEFORE_FIX.txt`: the 8 C1 tests, all failing on the Phase B engine.
- `C2_C4_TESTS_BEFORE_FIX.txt`: 14 of the 15 C2/C4 tests failing on the engine without C2/C4. The one that passes checks that the default (Interval Count) still covers the long window, which is correct before and after.
- `F33_F34_TESTS_BEFORE_FIX.txt`: the 4 F-33/F-34 tests, failing on the Phase B engine.
- `C2_BREAK_CAPACITY_TEST_BEFORE_FIX.txt`: one test added after the scenario runs found a C2 regression (below); it fails on the engine that had it.

## What changed

| Step | Finding | Change | Where |
|---|---|---|---|
| C1 | F-06 | When no schedule meets every hard rule, the run now also produces a **shortfall schedule**. This applies on three exits:<br>• the contract's capacity proofs fail;<br>• the hard probe is INFEASIBLE or UNKNOWN;<br>• no break-feasible candidate exists.<br>An elastic pass gives every coverage minimum a reported slack: nobody on the floor, language, opening, Coverage Split, hard floor, and the next-Sunday minimums. Every person rule stays hard: rest, OFF days, leave, hard OFF, fixed requests, nesting, shift variety, language hours, blank-hours ban, breaks, exception cap.<br>The schedule is exported as `HARD_RULE_SHORTFALL_SCHEDULE`, with a first sheet **Shortfalls** (day, time, rule, required, short by). It is never releasable, and the runner always exits non-zero.<br>The runner checks it independently: the validator must find exactly the listed misses and nothing else (`SHORTFALLS_CONFIRMED`), and the clean-room checker runs on it.<br>Input errors (duplicates, unreadable values, request conflicts) still get no schedule. | `run_shortfall_pass`, `build_skeleton(elastic)`, `solve_breaks(elastic)`, `build_business_outcome`, runner `validate_shortfall_schedule` |
| C1 | F-07 | The next-Sunday floor is measured as coverage quality (`NEXT_SUNDAY_FLOOR_GAPS` under the coverage gate), as the current week's floor is. Zero staffing, language and opening on next Sunday stay hard.<br>The normal model still holds the next-Sunday floor as a constraint, so the search of every week that is feasible today is unchanged. | `week_boundary_hard_failure_count`, `production_quality_gate`, validator `NEXT_SUNDAY_CARRY_OUT` |
| – | F-33 (new) | OR-Tools 9.15 corrupts Stage 2's shared balance expressions (below). The shortfall pass builds fresh ones. Normal runs keep the legacy terms: the pre-registered A/B did not pass. | `after_break_raw_expression` |
| – | F-34 (new) | The Stage-1 window is sized from the configured `Stage 1 Minimum Slice Seconds`, not the 45 s constant. Identical at the default. | `stage1_minimum_budget_seconds` |
| C2 | F-20 | Optional rows `Break Set For Shifts Of N Hours Or More` = e.g. `15, 30, 15, 15`. The largest threshold a shift reaches wins; 30 minutes or more is a lunch. Read by the engine (patterns, Stage-1 productive time, contract checks, seeds, capacity diagnostics, workbook), the independent validator and the clean-room checker. | `_parse_break_sets_by_shift_length`, `break_segments_for`, validator, `clean_room_check.break_lengths_for` |
| C4 | F-28 | Optional row `Coverage Objective Weighting` = `Interval Count` (default) or `Volume Weighted`.<br>Volume Weighted weighs each interval's miss by requirement ÷ mean active requirement in both stages, and the selector ranks first by `after_target_volume_fte`. The default does not change. | `volume_weight`, `calculate_metrics`, `_candidate_quality_tuple` |

**Not changed:**
- The search, objective and selection of any workbook without the new rows.
- The demand or roster of any workbook.
- Any baseline workbook.

## Proof that normal runs are unchanged (C1 rule R1, C4 rule V1)

| Check | Result | File |
|---|---|---|
| All 111 repository workbooks, Phase B engine vs Phase C engine:<br>• contract result, hard warnings, parsed facts;<br>• language rules in force per quarter;<br>• the new optional rows and the break set each shift length gets. | **0 of 111 changed** | `WORKBOOK_PARSE_SNAPSHOT_BEFORE.json` / `_AFTER.json` |
| Stage-1 models (the hard probe and two search profiles) of every packaged and real-run workbook, compared constraint by constraint and on the objective | **45 builds, 0 differing constraints, objectives identical** | `STAGE1_MODEL_IDENTITY.json` |
| Stage-2 models rebuilt on the 40 saved final schedules | **40 models, 0 differing constraints** | `STAGE2_MODEL_IDENTITY.json` |
| Golden replay of the release checks on the 40 saved schedules | **Identical to Phase B, row for row.** The only parity differences are the three `*_all_staffed_quarters` fields that pre-Phase-A audits lack. The one clean-room FAIL is still the correct S14 duplicate-row case. | `GOLDEN_REPLAY_GATES.json` |
| Next-Sunday floor gaps on the 40 saved schedules | **0 on every one** (validator recomputation and engine audit). So F-07 leaves every published schedule's hard-failure count unchanged. | `R1_BOUNDARY_FLOOR.json` |
| Real Voice run (below) | 248 / 264 after-break target and 253 floor, the same as Phase B | `real_run_voice_language_hours/` |

The three engine edits made after the model-identity runs do not touch `build_skeleton` or `solve_breaks`:
- the break-capacity diagnostic;
- the shortfall probe's status names;
- one full stop in an outcome text.

At the default break set, the diagnostic is again the Phase B code.

**Contract fingerprint.** It now records the two optional rows, so every workbook's hash moves although no workbook changed. For the three RC9.1 baseline-protected workbooks, `BASELINE_CONTRACT_WIDENING.json` proves four things:
- the file bytes equal the pinned `file_sha256`;
- the Phase B hash equals the recorded one;
- every previously recorded field has the same value;
- two fields were added (`break_sets_by_shift_length`, `coverage_objective_weighting`) and none removed.

`evidence/RC9_1_BASELINE.json` gained one history entry per scenario. The scored RC9.1 metrics are untouched.

## C1: the shortfall schedule on the scenarios (`scenario_results/`, `C1_SCENARIO_SCORE.json`)

Production runner, QUICK 300 s, 2 workers, seed 9000, engine `a2d4e7a1…`. Scored by `c1_score.py`.

| Scenario | Before Phase C | After Phase C |
|---|---|---|
| S04 one unreachable quarter | refused, no schedule | **Shortfall schedule.** Short only Sun 03:00–03:45 (4 quarters, nobody on the floor). Validator: `ZERO_STAFF_ACTIVE` ×4, as listed. Clean-room: 0 violations. Exit 2. |
| S05 Spanish shortage | INFEASIBLE, no schedule | **Shortfall schedule.** 64 Spanish quarters short (16 on each of Tue, Thu, Fri and Sat), all listed and confirmed. Clean-room: 0 violations. Exit 2. |
| S09 lone night cover with breaks | no schedule (exception gap 6) | **Shortfall schedule.** 9 quarters with nobody on the floor (Sun 22:00 and 22:15, Mon 00:30, and 06:45 and 21:00 on Wed, Thu and Fri), all listed and confirmed. Exit 2. |
| S11 overnight Mon–Fri Spanish | no schedule (lone Spanish cover, break) | **Shortfall schedule.** One Spanish quarter short: Mon 23:00. Confirmed. Exit 2. |
| S13 24/7 understaffed | no schedule | **Shortfall schedule.** 4 quarters with nobody on the floor, all on Sunday, confirmed. Exit 2. |
| S10 fixed shift vs blank rule | refused in 1 s | refused in 1 s, **no shortfall schedule** (input error) |
| S14 duplicate Preference row | refused in 1 s | refused in 1 s, **no shortfall schedule** (input error) |

| Rule | Result |
|---|---|
| R1 normal path unchanged | **PASS** (section above) |
| R2 a shortfall schedule where there was none (S04, S05, S09, S11, S13) | **PASS**, 5 of 5 |
| R3 honest: validator failure types are coverage minimums only; counts equal the Shortfalls sheet; no clean-room violation outside them | **PASS**, 5 of 5 (`SHORTFALLS_CONFIRMED`, 0 clean-room violations) |
| R4 S04 short only in Sun 03:00–03:59 | **PASS** |
| R5 never releasable: non-zero exit, outcome says so and lists the misses | **PASS**, 5 of 5 |
| R6 input errors still refused (S10, S14) | **PASS** |
| R7 gate | **PASS** (below) |

**Verdict: SHIP.**

**A C2 regression found here.** The first scenario round crashed on S09, S11 and S13 with `FAIL_UNEXPECTED_ENGINE_EXCEPTION`:
- **Cause:** the C2 edit of the break-capacity diagnostic left one name it had removed. That diagnostic runs on every schedule that gets past Stage 1, and no unit test reached it. The gate's undefined-name sweep would have caught it; the gate had not yet run.
- **Fix:** a workbook without per-length sets now runs the Phase B code exactly. The per-length count applies only when such rows exist.
- **Test:** `test_the_break_capacity_diagnostic_counts_each_shift_its_own_set`.
- **Rerun:** all seven scenarios were rerun on the fixed engine. Round 1 is kept in `scenario_results/round1_c2_regression/`.

## F-33 (new): Stage 2's balance terms are built from corrupted expressions

**Found while building C1.** The first elastic Stage 2 was INFEASIBLE on S04, where an elastic model cannot be infeasible.

**Cause:** OR-Tools 9.15 reduces `k - (k - S)` to the inner sum object `S` itself, and the `- allowed` that follows then modifies `S` in place. Stage 2 stores one `headcount - breaks` expression per quarter and reuses it in the whole-week and next-Sunday adjacent-balance terms.

**Measured on all 40 saved real models** (`F33_STAGE2_MODEL_DIFF.json`): 4 to 40 corrupted constraints in every model, and no other difference.

**Impact:**
- The corrupted terms are soft penalties, so no released schedule broke a hard rule. The validator, parity and the clean-room checker recompute every hard rule from the cells, and they pass.
- The break placement optimised a different objective from the one written.

**Pre-registered A/B** (`F33_RULE.txt`, `F33_AB_SCORE.json`): same skeletons, seeds and time, 50 paired Stage-2 solves.
- F1 validity: PASS.
- F2 non-inferiority: **FAIL**. On H1, after-target fell by 5.0 (2 scorable pairs). Break concurrency was worse on Voice (+1.0), Chat (+0.75) and H1 (+8.5).

**Verdict: DO_NOT_SHIP_AS_IS.** The fresh expressions are used only in the shortfall pass, where they are required for a correct model. Normal runs keep the legacy terms, proven identical above.

**F-33 stays open:** the corrected objective needs re-tuning before it can replace the old one.

## F-34 (new): Stage 1 ignored its configured slice

The budget planner sized the Stage-1 window from the 45 s constant, whatever `Stage 1 Minimum Slice Seconds` said. So the earlier AE_IT test at 240 s ran one or two profiles in FINAL's small window, and could not test what it was meant to test.

**Fix:** the window now follows `max(45 s, configured slice)` per profile, capped at 45 % of the run. It is identical for any slice of 45 s or less, including the default.

**Measured in C3:** a 240 s slice gets a 1,620 s Stage-1 window (the cap). The default gets 1,068 s.

## C2: break entitlement by shift length

The rule is the business's to state. The engine now reads it if stated.

| Check | Result |
|---|---|
| Parsing:<br>• no row, every shift keeps the global set;<br>• the largest threshold reached wins;<br>• unreadable values → `HARD_INVALID_BREAK_CONTRACT`;<br>• a set longer than its shift → `BREAKS_EXCEED_SHIFT` | tests pass |
| Pattern generation follows each shift's own set (9 h: 15/30/15; 11 h: 15/30/15/15) | test passes |
| End to end: an 11-hour schedule gets four breaks per 11-hour shift. The independent validator and the clean-room checker both read the per-length sets and find no break violation. | test passes |
| Workbooks without the row | unchanged (snapshot and model identity above) |

## C4: optional volume weighting (`C4_RULE.txt`)

| Rule | Result |
|---|---|
| V1 default unchanged: with the row absent, models identical and all workbooks parse identically | **PASS** (section above) |
| V2 the switch does what it says, on the constructed two-window case: Interval Count covers the 9 thin intervals, Volume Weighted the 6 thick ones | **PASS** |
| V3 gate | **PASS** |

The case's thick window is 0.85 FTE, not the rule's 1.0 FTE. At 1.0 FTE one 9-hour shift less its breaks (0.89 FTE productive) cannot reach the 90 % target in any interval, so neither weighting has a reason to choose it. The reason and the full calculation are in `C4_AMENDMENTS.txt`.

Volume Weighted is **not** the default. Making it the default needs two things (`C4_RULE.txt`):
- the end-to-end A/B on five real cases;
- a business decision, because the two measures trade against each other by construction.

## C3: AE_IT after-break floor, Stage-1 shape (`C3_RULE.txt`, `c3_runs/`)

**In progress.** The ten runs (5 seeds × 2 arms, QUICK 3600 s) are running on the frozen engine of `f326be4`. This section is filled in when they finish.

## Real workbook end to end (`real_run_voice_language_hours/`)

- **Workbook:** `fixtures/real_runs/language_hours/Cricut_Voice_LANGUAGE_HOURS.xlsx`.
- **Run:** production runner, QUICK 3600 s, 4 workers, seed 9000, engine `a2d4e7a1…`. Same settings as the Phase A and Phase B real runs.

| Check | Result |
|---|---|
| Runner exit code | **0** |
| Shortfall pass | did not run (the week is feasible) |
| Independent validator | **PASS**; parity **PASS** |
| Clean-room gate | **PASS**, 0 violations |
| Alternative exports | MAX_FLOOR **PASS**, MAX_TARGET **PASS** |
| After-break target / floor | **248 / 264, 253**: identical to Phase B |
| Next-Sunday floor gaps | 0 |
| Engine elapsed | 3,448 s of 3,600 |
| Outcome text | "Hard-valid final schedule generated with declared operational warnings", with the same four warnings as Phase B |

## Gate (`GATE_RUN.txt`)

`./run_tests.sh` on engine `a2d4e7a1…`: **GATE PASS: 54 suites, 1,377 tests (2 skipped)**. The floor in `GATE_MINIMUMS.json` was raised from 1,349 to 1,377.

Three existing tests were re-pinned. Each checks the engine's **source text** for a hard-minimum constraint, and each reason is written in the test.

The text changed: every coverage minimum now goes through `at_least()`. That is `model.Add(expr >= required)` in a normal run, and gets a reported slack only in the shortfall pass. The constraint itself did not change: both model-identity checks above show it, constraint by constraint.

| Test | Change |
|---|---|
| `test_rc9_2_1_rule_semantics` (coverage split in Stage 1 and Stage 2) | Pins the `at_least(...)` calls, plus `at_least`'s hard branch in both stages |
| `test_rc9_2_13_f1_exact_stage2_hits` (hard floor is exact) | Pins `at_least(after_exact, hard_floor_exact, …)` and the hard branch |
| `test_rc9_2_22_stage1_profile_rotation` (hard floor precedes the break load) | Pins `at_least(eff, hard_floor_units, …)` |

One engine change was made for a test rather than re-pinning it:
- **The test:** `test_rc9_2_14_probe_retry` checks that the hard-probe retry comes before the first `if probe.cp_status not in {"OPTIMAL", "FEASIBLE"}:` in the file.
- **The conflict:** the shortfall pass, earlier in the file, used the same line.
- **The change:** the shortfall pass now tests INFEASIBLE (`NO_SCHEDULE_MEETS_THE_PERSON_RULES`) separately from a timeout (`NO_SHORTFALL_SCHEDULE_FOUND_IN_TIME`). Its earlier single status misreported a timeout as a person-rule infeasibility.

## Still open after Phase C

- **F-33** for normal runs: the corrected Stage-2 objective needs re-tuning and a new A/B before it ships.
- **C4:** Volume Weighted as the default needs the five-case A/B and a business decision.
- **C2:** the business must state the break rule for long shifts. Until then, every shift gets the global set.
- **From Phase B:** the F-11 range clamps and the joint model's split constraint (that model is off in production).
- P3 items.
