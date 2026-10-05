# Phase C result: graceful degradation and schedule quality

Started from commit `407a725` (engine sha256 `38f494d9…`). Engine after C1–C4: sha256 `a2d4e7a1…` (commit `f326be4`). With the per-program coverage measure: `e211adeb…`. Released engine, with the F-35 fix: sha256 `34964381…`. Its default models are identical to `a2d4e7a1…`, Phase B and Phase A (below).

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
| **Since Phase A:** the same comparison against the Phase A engine (`5597971`, sha256 `e5afd99d…`) | **Stage 1: 45 builds, 0 differing constraints, objectives identical. Stage 2: 51 models, 0 differing constraints.** Default runs build exactly the models they built after Phase A, so neither Phase B nor Phase C can have lowered any of these schedules. | `STAGE1_MODEL_IDENTITY_PHASE_A.json`, `STAGE2_MODEL_IDENTITY_PHASE_A.json` |

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

## F-35 (new): the shift-consistency polish was never published

Found in the C4 impact A/B: Voice, Interval Count, seed 9000 ended with exit 4. The validator passed every hard rule, but parity failed on five overage statistics (for example extreme-overage intervals: engine 134, validator 135).

**Cause:**
- After selection, `run_case` replaced `selection["recommended"]` with the polished pair. Every audit metric, gate and outcome number was then taken from that pair.
- The workbook writer iterated `selection["exports"]`, which still held the original pair.
- The engine's own export record for the published workbook said 135, the validator's figure. Its canonical metrics said 134, the polished schedule's figure.

**Scope** (`F35_POLISH_NOT_PUBLISHED.txt`, `f35_polish_check.py`):
- On all six runs checked, the published workbook has the pre-polish start times. This includes the polish's own evidence runs (Voice, Chat, AE_IT).
- The polish's measured gains were never delivered.
- Swaps alone change no measured statistic, so parity passed. A one-hour move could change one, and then parity blocked a valid schedule.

**What it did not affect:**
- No hard rule; no wrong schedule was published.
- Every published workbook is the schedule the validator checked.

**Fix** (business decision, 2026-10-04: keep published schedules as they are):
- The polish is withheld. The audit records `WITHHELD_PENDING_VALIDATION`.
- `run_case` takes the measured pair from `recommended_export_pair(selection)`, which raises `PublishedScheduleMismatch` if the measured pair is not the published RECOMMENDED_FINAL pair.
- Published workbooks are unchanged by construction: the writer and its export list are untouched, and the polish ran only after the search had ended.
- Tests written first (`F35_TESTS_BEFORE_FIX.txt`): 5 of 6 failed before the fix. The 6th checks that the polish function is kept for its own validation.

**Follow-up the same day (business decision): publish the polish as its own workbook.**
- The selected schedule is still never rewritten.
- An applied polish is published beside it as `MORE_CONSISTENT_CANDIDATE`, written from the polished pair itself (`add_more_consistent_export`).
- The independent validator recognises the new artifact type.
- The runner approves the workbook only if its coverage, recomputed by the validator, is no worse than the selected schedule's (`more_consistent_coverage_verdict`). If it is approved, `BUSINESS_OUTCOME.txt` names the file and its start-time movement before and after.
- Tests written first (`MORE_CONSISTENT_TESTS_BEFORE_FIX.txt`): 7 of 9 failed before the change. On the real Voice fixture, the test proves the written workbook's start times are the polish record's "after" values. That is exactly the check F-35 lacked.
- Two F-35 tests were re-pinned to the lasting contract ("the polish never replaces the selected pair"), with the reason written in the test.

**Effect on the running C4 A/B:**
- Its frozen engine publishes the same workbooks as the fixed engine, so the validator-based measures of rules B and C are unaffected.
- A parity failure caused by F-35 is attributed under `C4_AB_AMENDMENTS.txt` A3. That amendment was written after the Voice and Chat seed-9000 pairs and before any other result.

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

## C4 follow-up: each program chooses its coverage measure

Programs accountable for service level and programs accountable for interval compliance need different measures. So the choice is made per program, in the same two places as the Language Working Window.

**In the workbook:**
- The template builder adds a **Coverage Objective Weighting** dropdown to the Coverage section, with the choices Interval Count and Volume Weighted.
- It is seeded with Interval Count, which is what an empty cell already means. So a rebuilt workbook keeps its contract.
- The packaged workbooks were not modified: they are hash-pinned, and three of them are baseline-protected.

**Per run:**
- `--coverage-objective-weighting INTERVAL_COUNT|VOLUME_WEIGHTED` on the engine, the production runner and the Colab runner.
- A `COVERAGE_MEASURE` dropdown in both notebooks. Its default, `workbook`, uses the row.

**Precedence:** run override, then workbook, then default (Interval Count).

**Where it is recorded:**
- The override is applied before the contract is read, so the contract fingerprint records it.
- The measure used and where it came from are in the audit (`coverage_measure`), and in `BUSINESS_OUTCOME.txt`, e.g. `Coverage measure: Volume Weighted (run override)`.

| Check | Result |
|---|---|
| Tests, written first (`C4_MEASURE_CHOICE_TESTS_BEFORE_FIX.txt`) | 12 tests. Before the change, 11 failed; the 12th checks that an unknown value is refused, which argparse already did. After the change, all pass. |
| Default runs unchanged | Final engine against Phase B and against Phase A: 45 Stage-1 builds and 51 Stage-2 models, 0 differing constraints |
| First Volume Weighted run end to end (S01, QUICK 300 s, `--coverage-objective-weighting VOLUME_WEIGHTED`) | Exit 0. Validator PASS, parity PASS, clean-room PASS with 0 violations, MAX_TARGET export PASS. 84/84 intervals at target. The outcome shows `Coverage measure: Volume Weighted (run override)`. |
| Real Voice workbook with Volume Weighted (QUICK 3600 s, seed 9000) | Exit 0. Validator PASS, parity PASS, clean-room PASS with 0 violations, MAX_FLOOR and MAX_TARGET exports PASS. Against the default run of the same seed: requirement covered at target 1,590 vs 1,587 FTE (+3); intervals at target 248 vs 248; floor 252 vs 253; severe floor gaps 11 vs 10; break-concurrency violations 1 vs 0; language gaps 0. A small trade on Voice, one seed, so direction only. The A/B measures it properly. (`volume_e2e/`) |

One existing test, and its duplicate under `tests/`, was re-pinned: `test_rc9_2_1c_tooling_integrity` pins the template's seeded rows, and a third seeded row was added on purpose. The reason is written in the test.

The impact of Volume Weighted on real programs is measured by the pre-registered A/B in `C4_AB_RULE.txt` and `C4_AB_AMENDMENTS.txt`, which runs after this package ships.

## C4 impact A/B: does Volume Weighted work, and what does it cost? (`C4_AB_RULE.txt`, `C4_AB_AMENDMENTS.txt`, `c4_ab_runs/`, `C4_AB_SCORE_FINAL.json`)

Pre-registered before the first run. Five real programs, Interval Count against Volume Weighted on one frozen engine, QUICK 3600 s, 2 workers per run, two runs at a time on their own cores. Seeds 9000 and 9001 for every program (amendment A1, at the business's request); a third seed, 9002, for every program whose two seeds disagreed on direction or price (A2: Voice, Chat, AE IT, GDI). AE IT's Interval Count arm reuses the C3 default runs (same command, models proven identical). F-35 parity failures are attributed per A3/A4 and still checked for hard failures and clean-room violations.

Verdict: **CLOSE**. Rule A failures: 0. Rule B: 5 of 5 cases cover at least as much requirement, sum of mean deltas +52.7 FTE (PASS).

| Program | Seeds | Requirement covered at target (FTE) | Intervals at target | Intervals at floor | Severe floor gaps | Break-overlap violations | Price (rule C) |
|---|---|---|---|---|---|---|---|
| Cricut Voice | 3 | +8.3 (seeds: +9, +19, -3) | +0.3 of 264 | -0.7 | +0.3 | +1.3 | MINOR |
| Cricut Chat | 3 | +20.0 (seeds: -32, +35, +57) | -5.7 of 242 | -2.3 | +1.3 | +1.3 | MINOR |
| NMG Spanish | 2 | +12.4 (seeds: +12, +12) | +3.0 of 126 | +0.0 | +0.0 | +3.0 | MINOR |
| AE IT B2B | 3 | +9.3 (seeds: -10, +9, +29) | -0.7 of 112 | -0.7 | +3.0 | +5.3 | MAJOR (break_concurrency) |
| GDI 28 HC 24/7 | 3 | +2.7 (seeds: -19, +14, +13) | +1.0 of 156 | +0.0 | +0.0 | +2.3 | MINOR |

Columns are the mean paired difference, Volume Weighted minus Interval Count, measured by the independent validator on the published workbooks. "Requirement covered at target" is the FTE of the intervals that reach target after breaks.

**What it says:**
- **No wrong schedule (rule A).** Every Volume Weighted run: exit 0 where its pair exits 0, 0 validator hard failures, 0 clean-room violations, 0 language gaps, 0 empty quarters, no crash or time-out.
- **It does what it says (rule B).** On all five programs it covers at least as much requirement at target; +52.7 FTE in total.
- **The price (rule C)** is MINOR on four programs. Chat trades about 6 of 242 intervals at target for +20 FTE of busy-interval demand covered: the intended trade. **AE IT is MAJOR**: +9.3 FTE covered, but about 5 more break-overlap violations (one seed, +18) and 3 more severe floor gaps.
- **The seed matters more than the measure** on a single run (Chat: -32 and +57 FTE on two seeds). F-36 now ranks the best-of-seeds pick by the program's own measure, so a multi-seed run keeps that benefit.

**Verdict (pre-registered): CLOSE.** Volume Weighted is validated as a per-program option. It stays opt-in (default Interval Count); the price table is in the run guide (3.5d). Three seeds show direction and size, not a confidence interval.

## F-36 (new): best-of-seeds ignored the coverage measure

**Found:** while reading the C4 A/B (the seed is the largest source of variation), the selection across seeds turned out to ignore the program's measure. `RUN_PORTFOLIO.py` (Colab QUICK = best of 2 seeds, DEEP = 4, OVERNIGHT = 6) always ranked by intervals at target.

**Fix:**
- When every seed ran Volume Weighted (read from each run's audit), seeds rank first by requirement covered at target, recomputed from the independent validator's interval rows, then in the old order.
- Interval Count ranks exactly as before.
- Seeds that disagree on the measure fall back to the old ranking and say so (`INTERVAL_COUNT_MIXED_MEASURES`).
- Eligibility is unchanged.
- `PORTFOLIO_SUMMARY.json` records `after_ranking_measure` and the ranking used.

**Tests written first** (`F36_TESTS_BEFORE_FIX.txt`): 5 of 6 failed before; the 6th checks that eligibility is unchanged. The existing portfolio suites pass unchanged.

## C3: AE_IT after-break floor, Stage-1 shape (`C3_RULE.txt`, `c3_runs/`)

**Setup:**
- Both arms ran on the frozen engine of `f326be4`: QUICK 3600 s, 2 workers, seeds 9000–9004.
- Two runs at a time, each pinned to its own core pair.
- The S240 workbook is the original plus one Engine Defaults row, `Stage 1 Minimum Slice Seconds = 240`.
- **All 10 runs are valid:** exit 0, validator PASS, parity PASS.
- **Restart:** the container was reclaimed while idle during the seed 9003 pair. That pair was rerun from scratch. The resumable driver skips only runs with a finished record, so no partial run is counted.

| Seed | DEFAULT target / floor (Stage-1 profiles) | S240 target / floor (Stage-1 profiles) | Floor Δ |
|---|---|---|---|
| 9000 | 76 / 87 (11) | 75 / 88 (4) | +1 |
| 9001 | 74 / 86 (10) | 73 / 88 (3) | +2 |
| 9002 | 70 / 86 (11) | 73 / 90 (3) | +4 |
| 9003 | 73 / 88 (10) | 75 / 87 (3) | −1 |
| 9004 | 66 / 87 (10) | 73 / 88 (4) | +1 |
| **Mean** | **71.8 / 86.8** | **73.8 / 88.2** | **+1.4** |

Other means, DEFAULT → S240:
- before-break floor 90 → 91;
- severe floor gaps 20.2 → 19.4;
- break-concurrency violations 1.0 → 2.4.

For reference, RC5's 6-seed means were 68.2 target / 91.5 floor.

**Read (pre-registered): UNRESOLVED.**
- **Why not CAUSE:** that needed an S240 floor of at least 90 and at least +2 over DEFAULT. S240 reached 88.2 and +1.4.
- **Why not NOT THE CAUSE:** that needed +1 or less.

**What the numbers do say, short of the rule's bar:**
- The deeper Stage-1 slice moves AE_IT in the right direction on both measures: +1.4 floor and +2.0 target on average.
- It is steadier: target ranges 73–75 against 66–76.
- Before breaks it reaches RC5's floor level (91). About 3 floor intervals are still lost when breaks are placed.
- So Stage-1 shape explains part of the gap to RC5, not all of it. The rest is in break placement, which is where F-33's corrupted balance terms act.

**Decision, as pre-registered:**
- No default changes.
- `Stage 1 Minimum Slice Seconds = 240` is documented as an AE_IT option, with its measured effect: +1.4 floor, +2.0 target, +1.4 concurrency violations.
- Choosing it is a business decision.
- F-21 stays open. The remaining candidate is break placement (F-33).

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

## Final end to end: friendly input, release engine, new output layout (`e2e_friendly_voice/`)

The Voice language-hours workbook, converted by the new template builder (`VERIFIED`: the engine reads the same contract), run through the production runner on the release engine `9f91e56c…`: QUICK 3600 s, 4 workers, seed 9000.

| Check | Result |
|---|---|
| Runner exit code | **0**, `PASS_WITH_QUALITY_WARNINGS`, production eligible |
| Independent validator (published schedule) | **PASS**, 0 hard failures, parity **PASS**; 245 / 264 intervals at target, 254 at floor |
| Clean-room checker | **PASS**, 0 violations, 0 disagreements with the engine |
| MORE_CONSISTENT_CANDIDATE | Written, validator **PASS**, coverage no worse on every measure, **approved**; named in `BUSINESS_OUTCOME.txt`: start-time movement 66 h -> 53 h, distinct start times 60 -> 59. The selected schedule is unchanged. |
| MAX_TARGET, MAX_FLOOR | Validator **PASS**, 0 hard failures |
| Output layout | Published schedule and all three alternatives: 8 visible tabs (Read Me First, Schedule, Break Plan, Break Schedule, FT Wise After Breaks, Coverage Before Breaks, Production Summary, Validation Log), every other tab kept hidden (57 in total). The before-breaks review workbook shows 7 (no Break Plan: it has no breaks). Presentation `APPLIED` on every alternative, before its validation. |
| Coverage measure line | `Coverage measure: Interval Count (workbook)` |

## Gate (`GATE_RUN.txt`)

**Final gate (`GATE_RUN_FINAL.txt`), after F-35's published polish, F-36 and the friendly workbooks:** `./run_tests.sh` on engine `9f91e56c…`: **GATE PASS, 60 suites, 1,432 tests (2 skipped)**. The floor in `GATE_MINIMUMS.json` was raised from 1,395 to 1,432 (+9 more-consistent workbook, +6 F-36, +14 friendly input, +8 friendly output); max_skips 2 -> 3 because the Start Here live-check test skips on a machine without LibreOffice (written reason in the file).


`./run_tests.sh` on the released engine `34964381…` (F-35 fix included): **GATE PASS: 56 suites, 1,395 tests (2 skipped)**. The floor in `GATE_MINIMUMS.json` was raised from 1,349 to 1,395: 28 tests for C1, C2 and C4, 12 for the per-program coverage measure, and 6 for F-35.

Five existing tests were re-pinned. Three check the engine's **source text** for a hard-minimum constraint; two check the order in which the chosen schedule is bound. Each reason is written in the test.

The text changed: every coverage minimum now goes through `at_least()`. That is `model.Add(expr >= required)` in a normal run, and gets a reported slack only in the shortfall pass. The constraint itself did not change: both model-identity checks above show it, constraint by constraint.

| Test | Change |
|---|---|
| `test_rc9_2_1_rule_semantics` (coverage split in Stage 1 and Stage 2) | Pins the `at_least(...)` calls, plus `at_least`'s hard branch in both stages |
| `test_rc9_2_13_f1_exact_stage2_hits` (hard floor is exact) | Pins `at_least(after_exact, hard_floor_exact, …)` and the hard branch |
| `test_rc9_2_22_stage1_profile_rotation` (hard floor precedes the break load) | Pins `at_least(eff, hard_floor_units, …)` |
| `test_rc9_2_1_selector_integrity` and its `tests_staged` copy (the final break-capacity measurement follows the selection) | Pins the binding `chosen_skeleton, chosen_breaks = recommended_export_pair(selection)` (F-35); the ordering it protects is unchanged |

One engine change was made for a test rather than re-pinning it:
- **The test:** `test_rc9_2_14_probe_retry` checks that the hard-probe retry comes before the first `if probe.cp_status not in {"OPTIMAL", "FEASIBLE"}:` in the file.
- **The conflict:** the shortfall pass, earlier in the file, used the same line.
- **The change:** the shortfall pass now tests INFEASIBLE (`NO_SCHEDULE_MEETS_THE_PERSON_RULES`) separately from a timeout (`NO_SHORTFALL_SCHEDULE_FOUND_IN_TIME`). Its earlier single status misreported a timeout as a person-rule infeasibility.

## Package

**Final package (2026-10-05):** `dist/RC9_2_2_PRODUCTION_PACKAGE.zip`, 1,858 files, 16.19 MB, sha256 `8c58c392f5de839833317a9a47bbb7f85a3bb39fea70de7ac24d6e15707db367`, engine `9f91e56c…`. The builder's own gate on the staged copy: **PASS, 60 suites, 1,432 tests (2 skipped)**. `./run_tests.sh` from a clean extract of the zip: **GATE PASS, 60 suites, 1,432 tests (2 skipped)** (`CLEAN_EXTRACT_GATE_FINAL.txt`). Ships the ready-to-edit weekly workbooks in `inputs/ready_to_edit/`; the seven shipped workbooks are byte-for-byte unchanged (manifest hashes checked by the gate).


`dist/RC9_2_2_PRODUCTION_PACKAGE.zip`, sha256 `50919d4758bb82a7d9ba574cc6723a425dab89963cdad94d0d0d389d82d2711f`, 1,733 files (rebuilt with the F-35 fix; the first Phase C package was `750cb6ca…`), built by `tools/build_production_package.py` from commit-ready sources. The checks run on it:
- the builder's own gate on the staged copy: PASS;
- `./run_tests.sh` from a clean extract of the zip: **GATE PASS, 56 suites, 1,395 tests** (2 skipped);
- the clean-room checker ships at `tools/clean_room_check.py`, where the runner looks for it.

The first build was refused by that gate. The new coverage-measure test read the runners from the repository layout (`packages/rc9_2_2_production/runners`), which the package does not have (it ships them at `runners/`). The test now resolves either layout, as the other runner tests do. No shipped code changed.

## Release status

`engine/RELEASE_IDENTITY_RC9_2_2.json` -> `status`: **PILOT_APPROVED_PARALLEL_RUN**, approved by **Omar Mokhtar**, 2026-10-05 05:45 Egypt time (was `RELEASE_CANDIDATE_NO_GO_PENDING_SCENARIO_AND_QUALITY_REVIEW`; history kept in `status_history`). Scope: the parallel-run week, where the engine's schedules are compared with the manually produced ones on the same inputs. `PRODUCTION_APPROVED` follows a successful parallel week. The status is a recorded decision; no code reads it, and the engine file (`9f91e56c…`) is unchanged. Package rebuilt with this status: `RC9_2_2_PRODUCTION_PACKAGE.zip`, 1,864 files, 16.22 MB, sha256 `a3fc3ab2b60b5f89b1acb33f5c628deba2ef42062896b14482f22a7e2b75d2de`; gate PASS staged and from a clean extract, 1,432 tests (2 skipped) (`CLEAN_EXTRACT_GATE_PILOT.txt`). This supersedes the `8c58c392…` package.

## Still open after Phase C

- **F-33** for normal runs: the corrected Stage-2 objective needs re-tuning and a new A/B before it ships.
- **C4:** closed as a per-program option (A/B verdict CLOSE). Making it the default for everyone is not proposed: AE IT pays a MAJOR break-overlap price, and C4_RULE.txt's ten-seed rule would still apply.
- **C2:** the business must state the break rule for long shifts. Until then, every shift gets the global set.
- **From Phase B:** the F-11 range clamps and the joint model's split constraint (that model is off in production).
- P3 items.
