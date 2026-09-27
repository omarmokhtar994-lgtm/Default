# Audit brief: RC5 → final engine (everything changed since RC5 was received)

This brief is for an independent auditor who has not seen this work. It
tries to answer every question without needing anything else: what changed,
why, how each change was measured, the results, what was gained and lost, and
what is still open or weak. Every claim points to a file in this package, so
you can check it.

Times are UTC unless marked (Egypt time = UTC+3).

---

## 0. Identities

| | value |
|---|---|
| Baseline received | **RC5** (`RC9_2_2_MAX_COVERAGE_RC5_RELEASE_CANDIDATE`), received 2026-09-15 |
| Baseline engine sha256 (`engine/_tools/l632_universal_scheduler.py`) | `0e6f643552c5e59f284fefbabc74803c3450b2a1cd2de47fad44781f6408cc5c` |
| Baseline test gate | 11 suites, 453 tests |
| Final engine sha256 | `2071ae894f14f6e37131111dddfd0512ec147ab98e678cd714141a30dd3b75a4` |
| Final release identity | `engine/RELEASE_IDENTITY_RC9_2_2.json` (`release_short`: RC9.2.2-PRODUCTION-HARDENED-RC5-P1-C1; status still `RELEASE_CANDIDATE_NO_GO_PENDING_SCENARIO_AND_QUALITY_REVIEW`, not changed by me) |
| Final test gate | `./run_tests.sh`: **PASS, 30 suites, 677 tests** (431 in `tests/`, 246 in `tests_staged/`), plus 2 selfchecks, a cross-module call-signature check and an undefined-name sweep. Log: `05_TESTS/GATE_FINAL.log` |
| Production package | `01_ENGINE_PACKAGE/RC9_2_2_PRODUCTION_PACKAGE.zip`, 316 files, sha256 `77e810c63ec0c79a6292f830bca2ed76c3f10fd131a06ca7d5abea1bad25e7b7`. Its engine files are byte-identical to `04_FINAL_ENGINE/` (checked by sha256). |
| Solver | OR-Tools CP-SAT 9.15.6755 (unchanged) |
| Git | branch `claude/handoff-document-m6egz2`; 168 commits since RC5, all in `07_COMMIT_LOG_SINCE_RC5.txt` with full messages and file stats |

### Package layout

| folder | contents |
|---|---|
| `00_READ_ME_FIRST_AUDIT_BRIEF.md` | this file |
| `01_ENGINE_PACKAGE/` | the deployable package (Colab notebooks, runner, engine, scenarios) |
| `02_CODE_DIFFS/` | `RC5_to_FINAL__engine_full.diff` (whole `engine/` directory); three stage diffs (A, B, C, see §3); `FILE_CHECKSUMS_RC5_vs_FINAL.tsv` (every engine file, both sha256s, status) |
| `03_BASELINE_RC5_ENGINE/` | RC5's `engine/` exactly as received |
| `04_FINAL_ENGINE/` | the final `engine/` |
| `05_TESTS/` | `tests/`, `tests_staged/`, `run_tests.sh`, the gate tools, fixtures, final gate log |
| `06_EVIDENCE/` | every measurement, pre-registered rule, result file and write-up referenced below |
| `07_COMMIT_LOG_SINCE_RC5.txt` | every commit since RC5 |
| `08_TOOLS/` | research tools, benchmark and synthetic-suite builders, patches that were **not** shipped |

### Files changed in `engine/` (RC5 → final)

26 files unchanged, 8 changed, 1 added. Line counts are from `diff`.

| file | + | − | what |
|---|---|---|---|
| `_tools/l632_universal_scheduler.py` | 2927 | 424 | the scheduler (21,409 → 23,912 lines) |
| `RUN_UNIVERSAL_PRODUCTION.py` | 280 | 42 | production runner: flags, depth defaults, joint default |
| `RUN_PORTFOLIO.py` | 227 | 0 | **new**: seed portfolio runner |
| `tools/independent_validator.py` | 214 | 7 | validator: 7 more metrics, 2 more gates recomputed, next-Sunday fix |
| `_tools/canonical_metrics.py` | 134 | 7 | canonical metric surface: new fields, CM-1 |
| `production/phase_c_quality_report.py` | 113 | 5 | merged from the Coverage Split line |
| `_tools/phase_b_maturity.py` | 82 | 0 | budget plan: DNBS and break-load-feedback phases |
| `README.md`, `RELEASE_IDENTITY_RC9_2_2.json` | small | small | identity/docs |

---

## 1. Executive summary

**What was done.** RC5 was audited, hardened, merged with the parallel
Coverage Split line of the engine, audited again formula by formula, tested
against a new synthetic suite and two published benchmarks, and then improved
through a series of **pre-registered A/B tests**. A change shipped only if it
passed a rule written down before its runs. Changes that failed their rule
were reverted or left off behind a flag.

**The largest measured gains:**

1. **S2-PAR** (Stage-2 break solves use every worker; before this, every break
   solve silently ran on one worker). End-to-end A/B, 900 s, 6 cases: summed
   after-breaks target **827 → 913 (+86)**. Chat 155→179, Voice 227→246,
   M2 82→109, H3 76→91. No case got worse.
2. **DEEP/OVERNIGHT as seed portfolios** (best of 4 or 6 one-hour QUICK runs,
   instead of one 4 h or 6 h run). A/B: **692 vs 370**. One long DEEP run was
   killed by the kernel at 13–14 GB on 2 of 4 cases and produced no schedule;
   where it finished, it only tied.
3. **Joint-solve isolation**: long runs can no longer be OOM-killed inside
   joint refinement. When memory suffices, results are identical.
4. **F-1** (exact Stage-2 hit arithmetic): Chat 162 → 165 (deterministic A/B).
5. **DNBS v2** (per-day break re-optimisation with its own budget): 1057.5 →
   1058.0. This is marginal (+0.5), with a mixed per-case result (see §6).

**Many correctness fixes**, mostly fail-closed input contracts and more
independent validation:

- 7 more metrics independently recomputed (parity surface 41 → 48 fields);
- 2 more release gates recomputed independently;
- a validator bug fixed (next-Sunday rule);
- a floor-loss metric, cap and gate added;
- dead code and silent fallbacks removed.

**Removed:** joint refinement and the no-candidate endgame are now off by
default at every depth. Measured across 474 solver audits, they improved
nothing. They were the cause of the 13 GB OOM kills.

**Not shipped** (measured, failed their rule):
- F-6
- LP-visible hit links
- the unconditional joint floor bound (#48)
- B-13 bound
- Stage-1 profile rotation
- break-load feedback
- DNBS v1 (at 900 s)

The last two of these are kept as opt-in flags.

**Most important caveat.** There is **no single direct A/B of RC5 against
the final engine**. The gain comes from a chain of A/Bs, each comparing one
change against the engine just before it. The chain is in §6.7. A direct
RC5-vs-final run on the same cases, seeds and budget is the obvious
confirmation, and was not done.

---

## 2. Method and rules followed throughout

- **Pre-registered A/B.** Before any run of a behavioural change, a file
  `PREREGISTERED_RULE.txt` fixed the following:
  - cases, seeds, budget and workers;
  - the metric;
  - the ship conditions.

  It was committed before the runs. The same scorer script was used for both
  arms. Results are in `RESULT.txt` next to the rule (`06_EVIDENCE/*/`).
- **Score.** `after_target` is the number of demanded intervals meeting the
  target *after* breaks are placed. It counts only when all three hold:
  - the independent validator returns PASS;
  - there are 0 hard failures;
  - engine/validator metric parity is PASS.

  A run that dies or fails validation scores 0. `before_target` (the
  before-breaks sheet) is checked separately so that a change cannot buy
  after-breaks coverage with a worse skeleton.
- **Typical ship rule:**
  - (1) all NEW runs are clean;
  - (2) the summed after_target of NEW is ≥ CURRENT (two-seed means where
    two seeds were run);
  - (3) no real workbook is worse by more than 2 or 3;
  - (4) no schedule is lost;
  - (5) the mechanism actually executed.
- **Cases.** Real workbooks:
  - Cricut Chat
  - Cricut Voice
  - AE_AR_B2B
  - NMG_SP

  Synthetic cases with a known optimum:
  - SYNTH_M2 (optimum 117)
  - SYNTH_H3 (optimum 105)
  - SYNTH_H1, 24x7 overnight (skeleton 168)

  Plus X1, and the Winston and Union Airways benchmarks.
- **Noise.** Multi-worker CP-SAT is nondeterministic. Run-to-run spread is
  about ±1 on the real workbooks and much larger on H1 (125–151 across seeds).
  Where a clean attribution was needed, deterministic single-worker A/Bs
  were used.
- **Standing rules:**
  - no baseline was regenerated or fabricated;
  - no validation was weakened;
  - no test was deleted or weakened to pass;
  - pins were moved only when the measured contract changed, with the
    reason recorded;
  - infrastructure kills were rerun with the same seed and not scored;
  - every behavioural fix was mutation-checked where a test was added. The
    test must fail on the old code, and the source was restored
    byte-identical afterwards.

---

## 3. Change catalogue

The work falls into three stages. The stage diffs are in `02_CODE_DIFFS/`.
Scheduler line counts per stage:

| stage | from → to | scheduler lines |
|---|---|---|
| A | RC5 → hardened RC5 (`candidates/RC9_2_2_HARDENED_RC5`, scheduler `d3e3160d…`) | +1148 −338 |
| B | hardened → merged with the Coverage Split line (commits 4ef05e8, 6938b55) | +441 −14 |
| C | merged → final | +1164 −57 |

Each entry below gives:
- **what** changed;
- **type**: *inert* (parsing, reporting or validation; cannot change a
  schedule, proven by gate and corpus) or *behavioural* (can change a
  schedule, needs an A/B);
- **evidence** and **tests**.

### Stage A: hardening RC5 (2026-09-15 → 09-20)

| id | what | type | evidence / tests |
|---|---|---|---|
| **P-1** | `shift_day_demand_fit` memoised on the parsed contract. It was called 632,649 times per run for 168 distinct answers. The original body is kept as `_shift_day_demand_fit_uncached`. | speed only; output identical | `06_EVIDENCE/PATCH_P1_AND_C1.md` |
| **A-1** | `_parse_break_segments`: a contract stating zero breaks silently got 15/30/15. Out-of-set durations were coerced to 15; negative counts were swallowed. Now zero means zero, and invalid values raise `HARD_INVALID_BREAK_CONTRACT`. | fail-closed contract | c0f7d3c; canonical contract hash identical on all packaged workbooks |
| **A-2** | `_detect_interval_minutes`: an interval outside {15, 30, 60} was replaced by inference. Now raises `HARD_INVALID_INTERVAL_MINUTES`. Absent still infers. | fail-closed | c0f7d3c |
| **A-3** | Language day aliases ("All Days", "Every Day", "7 Days") never matched because of inner spaces. Fixed with an `_alias_key()` helper. | contract fix | c0f7d3c |
| **A-7** | `language_rules_at` with a day outside 0..6 silently returned no rules. Day 7 (next Sunday) now maps to Sunday; out-of-range values raise. | fail-closed | c0f7d3c |
| **Capacity-benchmark gate** (test tooling, not engine) | Classifies each case's roster capacity (ample / tight / short) so that comparisons against a baseline do not count capacity-forced losses as regressions. 10 guards. | tests only | dc0e667; `AE_RESULTS_ROOT_CAUSE_FOUND.md`; C1 capacity-gate patch (`08_TOOLS/patches`) |
| **B-1/B-2** | Release gates became stage-aware. A skeleton-only (before-breaks) run no longer fails parity with 41 phantom mismatches. | inert (gates) | 8ac7281; 8 recorded audits replay identically |
| **B-3** | The Stage-1 portfolio's per-profile slice floor was measured on cold solves (240 s) but applied to warm-started solves. At 900 s it attempted 0 of 15 profiles. Changed to **45 s**, the warm knee of the curve (`B3_STAGE1_WARM_SLICE_CURVE.json`), with portfolio sizing to the budget. | **behavioural** | 8b4a781, a33f419; `B3_STAGE1_PORTFOLIO_FLOOR.md` |
| **B-7** | 43 behavioural parameters that existed only as CLI flags can now be set from the workbook. Precedence: explicit CLI > workbook > engine default. The runner no longer silently overrides workbook values. | behavioural only if a workbook sets them (none of the corpus does) | 15d6304; 34 tests |
| **B-8** | The validator checked a weaker next-Sunday adjacency rule (interval maxima) than the engine enforces (quarter slots). The validator is now stricter and matches. | validator | d49fc4f |
| **S11-1 / W1** | `floor_losses_from_breaks` had no metric, cap or gate. Added all three: cap `max(3, ceil(3% of active intervals))`, gate mode default `warn`. It found real unmeasured losses, up to 7 intervals on AE_IT_Choice. | reporting gate (warn) | 3da4902, 09e0c35, 965826b |
| **B-11** | Name-matched sheets (leave, OFF, preferences) failed open. A misspelled name silently deleted approved leave or hard OFF. Now fail closed. The only escape is a named list of departed associates. | fail-closed | cee6e36; a true positive on real data (`SAKS_NEW`, Associate 051) |
| **B-12** | A single-term header lookup could match a prose banner. It is now anchored. | inert | 0 of 15 contract hashes changed |
| **C-3** | The preference vocabulary accepted only two exact words, so "Annual Leave", "A/L", "Sick" and similar did not block scheduling. It now fails closed on unknown values. | fail-closed | 31a5993; 0 false positives across 15 workbooks |
| **B-9 / W7a** | The validator independently recomputes 7 previously engine-only metrics: `target_losses_from_breaks`, `floor_losses_from_breaks`, `before_severe_floor_gap_count`, `hard_floor_gap_count`, `week_boundary_hard_failure_count`, `week_boundary_max_adjacent_raw_change`, `week_boundary_max_coverage_ratio`. Parity 41 → 48. | validator | 6cf3b63, a195530, 09e0c35; parity 48/48 on all six real workbooks |
| **RC-B** | 49 of 81 `getattr(parsed, f, shadow)` defaults were looser than the declared policy (e.g. 999999 vs 3, `off` vs `fail`, 2.0 vs 1.35). They were aligned to the declared defaults; the defensive reads were kept because duck-typed callers use them. | inert (corpus) | c8d2877 |
| **RC-A** | 18 silent cross-metric fallbacks (e.g. `after_floor` falling back to `after_80`) are now named failures. Instrumented runs showed they never fire today. | inert | 91ef41e |
| **CM-1** | One canonical metric field was missing from its own alias list. Fixed. | inert | 91ef41e |
| **S6-1/S6-2** | A nesting group whose members have different approved leave made the model infeasible (`1 == 0`) with no named cause. It now fails the contract with `CONFLICTING_LEAVE_OR_OFF_IN_NESTING_GROUP`. | fail-closed | a279f7e |
| **S13-2** | 213 lines of dead code deleted (6 functions). Each was proven unreachable by AST, string-literal and textual search. | inert | bb72508 |
| **Telemetry** | CP-SAT's `best_objective_bound` on UNKNOWN results and `deterministic_time` are now recorded under `solver_telemetry`. Observation only. | inert | 63dc2f0; 5 tests |
| **Solver limits** | `max_memory_in_mb = 6000` (normal peak ~820 MB never binds; the ~8.2 GB joint-refinement peak does). The gap limit is deliberately left off: the objective spans 4e8:1, so a relative gap does not bound coverage. | behavioural only near the memory limit | 8182b74; `BUDGET_SWEEP_AND_OOM.md`, `MEMORY_GROWTH_LOCALISED.md` |
| **Joint refinement off at SMOKE/QUICK** | 69 attempts on 7 workbooks gave 0 improvements, while the phase was ~90% of peak RAM. Peak 8197 → 798 MB; coverage identical. | behavioural (memory) | c044149, 405ff7e |
| **employee_quality validator** | Third ungated release gate, now recomputed independently from the output workbook (warn mode, like the engine). | validator | b903d91; 9 tests |

**Reverted or retracted in Stage A:**
- **#48**: the unconditional joint floor bound. Nine paired runs showed it
  *damaged* the floor (AE_IT_B2B before_floor pinned at 91 vs 91/98/97). The
  model constraint was reverted; W1's metric and gate were kept.
  Evidence: 87379e9.
- **B-13**: the joint bounds were "gameable" (the variable-vs-variable bound
  is equivalent to no bound). The constant-bound fix was applied, measured,
  showed no benefit, and was reverted. The finding is kept as the guard test
  `test_rc9_2_5_joint_bound_shape.py`. Evidence: 13b2cbb.
- **B-10** retracted: the 180 s break-slice floor is correctly a floor
  (90–150 s → 160; 180 s → 162).
- **S9-2** retracted: the Pareto frontier overriding the order is by design.
- **S15-3** retracted: under-funded phases are not truncated, by documented
  design.

**Deterministic measurement of the Stage-A stack** (c566351). One worker,
seed 9000, AE_AR_B2B and AE_IT_B2B, original engine vs the nine-fix tree:
- all 46 pre-existing canonical metrics identical;
- every scheduling sheet byte-identical.

So the Stage-A hardening **changed no schedule** on those cases. An earlier
"+0.15%" claim came from multi-worker noise and was retracted.

### Stage B: merge with the Coverage Split line (2026-09-23)

- Two engine lineages had diverged:
  - L6.3.2.6 Coverage Split, the repo line (Language Setup coverage groups
    with owned windows and pooling of overlapping windows, A50–A54);
  - L6.3.2.7 RC5 hardening (Stage A).
- They were merged with a real 3-way merge against the common ancestor
  `93ab7f8`. There were 6 conflicts in the scheduler, resolved by hand.
  Conflict 2 was the same function written twice; the two versions were
  checked over 23,887,872 input combinations with 0 disagreements.
- The first merge pass missed 5 files. A real 1800 s run then died with
  `build_global_budget_plan() got an unexpected keyword 'diagnostics'`.
  Those 5 files were merged in 6938b55. A new static gate
  (`tools/check_cross_module_calls.py`) now catches this class of defect.
- The hardened Phase C packaging chain was merged in. It refuses to package
  unless the manifest is sealed, validation is PASS and the hashes match.
- **Verification:** AE_AR_B2B at 1800 s, one worker, seed 9000. Pre-merge
  and merged engines gave **166/165/168/167, identical** (9877d41).
- Coverage Split end-to-end: `06_EVIDENCE/COVERAGE_SPLIT_VERIFICATION.md`.

### Stage C: formula audit, suites, performance and robustness (2026-09-23 → 09-27)

| id | what | type | evidence / tests |
|---|---|---|---|
| **Anchor cap** | The Stage-2 anchor could spend the last fundable break-search attempt. On Chat, 0 of 168 planned attempts ran; across 22 runs at 1800 s, 15 never ran the break search. The anchor now leaves 180 s plus a **30 s hand-off margin** (the worst measured hand-off was 9.82 s). | behavioural | 9b17dde, de36c3a; bit-identical to the uncapped engine in every single-worker pair where it does not bind |
| **language_reserve validator** | Second ungated release gate now recomputed independently, reusing the engine's own tier helpers. 10 tests, mutation-checked twice. | validator | 258efc4 |
| **Target-lock arithmetic** | Checked on all 242 Chat intervals: the model threshold is stricter than the metric on 242 of them and looser on 0, so `min_target_hits = N` does force after_target ≥ N. Pinned by a test. | verification | 258efc4 |
| **Formula audit** | Every formula statement (1,102) was inventoried and verified. | audit | `06_EVIDENCE/formula_audit/` |
| **F-1** | Stage-2 coverage hits and the hard floor now use the exact ×1e6 threshold that the joint model and the metric use. Deterministic A/B: **Chat 162 → 165 of 214**; AE_AR unchanged. | **behavioural, A/B** | de36c3a; `test_rc9_2_13_f1_exact_stage2_hits.py` |
| **F-2** | Off-grid shift starts are refused. | fail-closed (inert on corpus) | de36c3a; synthetic R1 |
| **F-3** | Overage caps were divided by 100 when below 10, and their order check could never fire. Both fixed. | contract (inert on corpus) | de36c3a |
| **F-4** | Break headcount now divides a weekly deficit by a weekly contribution. | advisory arithmetic | de36c3a |
| **F-5** | A mistyped floor gate mode now names itself. | fail-closed | de36c3a |
| **Probe retry** | The hard-feasibility probe gave up on UNKNOWN after 30 s with 94% of the budget unspent (X1, Union N=246/247). It now retries on half the Stage-1 window, capped at 600 s. | behavioural (only when the probe returns UNKNOWN) | d99a641; `test_rc9_2_14_probe_retry.py` |
| **Starved Stage-1** | If the portfolio cannot fund any profile, the first before-basis profile runs on the leftover time. E2 at 300 s: 45 → 63/63. Inert whenever any profile ran. | behavioural (starved runs only) | d99a641 |
| **Capacity advisory** | The advisory counted room per quarter against ceil(requirement) and falsely said "hire 1 more" on a 63/63 roster. It now uses the metric's interval averaging. Identical at 15 min. | advisory | d99a641 |
| **Joint memory guard** | Joint loops check available memory ≥ max(2 GB, 15%) before building a model (X1 was SIGKILLed at 13.9 GB). | robustness | d99a641; `test_rc9_2_15` |
| **Blank staffing** | `blank_staffed_quarters` counted last Saturday's carry-in as staffing. Engine/validator parity on NMG SP was 16 vs 0; this defect was already present in RC5. It now counts current-week staffing only. | metric fix (parity) | 3bfda69 |
| **S2-PAR** | With the break-infeasibility core on (the default), every Stage-2 solve carried assumption literals and so ran on **one worker**, whatever `--num-workers` said. It now solves a clone on all workers and re-solves with assumptions (one worker, ≤ 60 s) only on INFEASIBLE, to name the core. The one-worker path is unchanged. | **behavioural, A/B: SHIP** | 37288d0; `06_EVIDENCE/s2par_e2e/`; `test_rc9_2_16` |
| **DNBS v2** | Day-neighbourhood break search: after break search, re-optimise breaks one day at a time on the fixed skeleton. A candidate is kept only if it dominates its anchor and passes the release validator. It has its own budget phase: 8% of the total, floor 60 s, cap 420 s, taken from break search only if ≥ 180 s remain (288 s at 3600 s). | **behavioural, A/B: SHIP** | 50f6a82; `06_EVIDENCE/dnbs_e2e_3600b/`; `test_rc9_2_17` (16) |
| **Seed portfolio runner** | `engine/RUN_PORTFOLIO.py` runs K complete, untouched seeds. It keeps the best *validated* after-breaks run and, separately, the best before-breaks sheet. | new runner | 0762e0f; `test_rc9_2_18` (8) |
| **Joint-solve isolation** | Each joint-refinement CP-SAT solve runs in a forked child: same model, parameters and seed. The response comes back as protobuf text and is set on the parent solver, so `Value`, `ObjectiveValue` and `StatusName` are unchanged. The child runs at `oom_score_adj` 1000 with `PR_SET_PDEATHSIG`. A watchdog kills the child below max(256 MB, 2% RAM) free; that solve then reports UNKNOWN and no further joint model starts. Non-memory child errors (exit 72) are re-raised. It falls back to in-process without fork or with callbacks. Recorded in the run audit as `joint_solve_isolation`. | robustness; registered 5-check rule: SHIP | 2f2a9ce, 9473e99, 8506631; `06_EVIDENCE/joint_solve_isolation/`; `test_rc9_2_19` (16) |
| **DEEP/OVERNIGHT presets** | DEEP = best of 4 × 3600 s QUICK seeds; OVERNIGHT = best of 6. Available as `RUN_PORTFOLIO.py --preset` and as the Colab runner's `--mode`. `--seeds` and `--time-limit` override the preset; `--single-run` restores one long run. QUICK and SMOKE are unchanged. Notebooks: `SEEDS=0` means automatic (QUICK 2, DEEP 4, OVERNIGHT 6). | **behavioural (mode semantics), A/B: adopt** | 850b129; `06_EVIDENCE/seed_portfolio_ab/`; `test_rc9_2_20` (10) |
| **Joint refinement + endgame removed from defaults** | Runner: `joint_enabled: False` at SMOKE, QUICK, DEEP and OVERNIGHT. Engine: `FINAL_RECOVERY_ENDGAME_ENABLED = False`, so a run with no release candidate records `DISABLED_NO_MEASURED_VALUE` and finalizes. `--enable-joint-refinement` and `--enable-final-recovery-endgame` restore them. The code is kept. | behavioural (only for `--single-run` DEEP/OVERNIGHT and no-candidate runs) | 97955f2; `06_EVIDENCE/JOINT_REFINEMENT_REMOVED.md`; `test_rc9_2_21` (5); `test_rc9_2_8_joint_default.py` re-pinned (see §5) |
| **Stage-1 profile rotation (opt-in)** | `--stage1-profile-rotation i/n` keeps the first 5 profiles and rotates the rest per seed. `RUN_PORTFOLIO.py --diversify-profiles` passes it through. **Default off** (its A/B failed). | opt-in | 215d7e8; `test_rc9_2_22` (8) |
| **`build_skeleton(break_load_units=…)`** | Optional input that raises Stage-1 hit thresholds by the observed break load. It affects the objective only; hard constraints are unchanged. `None` means unchanged. | inert by default | 215d7e8 |
| **Break-load feedback (opt-in)** | `run_break_load_feedback` takes coordinated repair's slot when enabled. It feeds break load on under-target intervals back to Stage 1, does an anchored re-solve (24 or 12 changes), then Stage 2 + DNBS. A result is kept only if compliant and dominating. Budget: coordinated repair's slot plus 8% (floor 120 s, cap 900 s; 540 s at 3600 s). **Default off** (its A/B failed). | opt-in | 7e765db; `test_rc9_2_23` (7) |

---

## 4. Code-level detail of the Stage-C engine additions

These are in `l632_universal_scheduler.py` unless noted. Read them in
`02_CODE_DIFFS/STAGE_C__merged_to_FINAL.diff`.

**Joint-solve isolation**
- Constants: `JOINT_SOLVE_ISOLATION_ENABLED = True`,
  `JOINT_SOLVE_KILL_BELOW_FREE_MB = 256`,
  `JOINT_SOLVE_KILL_BELOW_FREE_SHARE = 0.02`, `JOINT_SOLVE_POLL_SEC = 0.2`.
- State: `_JOINT_SOLVE_MEMORY_STOPS`, `_JOINT_SOLVE_ISOLATION_LOG`.
- Functions:
  - `_cgroup_memory_headroom_mb()` and `machine_free_memory_mb()` (the
    tighter of cgroup and MemAvailable);
  - `joint_solve_kill_threshold_mb()`;
  - `_child_prepare_for_isolated_solve()` (oom_score_adj, PDEATHSIG);
  - `isolated_cp_solve(solver, model, in_process_solve, response_type, solution_callback=None)`;
  - `isolated_cp_solver(cp_model)`, a CpSolver subclass overriding
    `solve`/`Solve`;
  - `joint_solve_isolation_audit()`.
- Wiring:
  - `configured_solver` for the joint phase uses `isolated_cp_solver`;
  - per-solve rows go through `record_diagnostic`;
  - `audit["joint_solve_isolation"]` is set on both return paths;
  - `joint_memory_headroom()` returns not-ok after any memory stop.

**Endgame gate.** `FINAL_RECOVERY_ENDGAME_ENABLED = False` guards the
no-candidate endgame loop. Its audit status is `DISABLED_NO_MEASURED_VALUE`.
CLI: `--enable-final-recovery-endgame`.

**Profile rotation.** `STAGE1_ROTATION_ANCHORS = 5`,
`STAGE1_PROFILE_ROTATION = (0, 1)` and
`rotate_stage1_profiles(names, seed_index, seed_count)`. It is applied after
the skeleton profile names are resolved and recorded in the audit
(`run_parameters.stage1_profile_rotation`). CLI:
`--stage1-profile-rotation i/n`. `main()` declares the three module flags
global before setting them.

**Break-load feedback.**
- `BREAK_LOAD_FEEDBACK_ENABLED = False` and `FBL_VARIANT_CHANGES = (24, 12)`.
- `break_load_by_interval(parsed, metrics, damaged_only=True)`.
- `run_break_load_feedback(parsed, candidates, hard, pattern_width, deadline, workers, log, random_seed=0)`.
- In `build_skeleton`, `break_load_units` raises the floor, target, full and
  tier *objective* thresholds after the hard-floor constraint is posted.
- CLI: `--enable-break-load-feedback`.

**`phase_b_maturity.py`.**
- DNBS constants: 0.08, 60, 420 and 180.
- FBL constants: 0.08, 120, 900 and 180.
- `PHASE_MINIMUM_VIABLE_SECONDS` gains DNBS 21 and FBL 120.
- New kwargs `day_neighbourhood_break_search` and `break_load_feedback`.
- New plan keys for both phases.

**`RUN_UNIVERSAL_PRODUCTION.py`.**
- Joint refinement is off at every depth.
- The rotation, break-load-feedback and endgame flags are passed through.
- Earlier changes also live here:
  - B-7 workbook routes;
  - `--disable-joint-refinement` is emitted because a reserve of 0 does
    *not* disable the phase (measured).

**`RUN_PORTFOLIO.py`** (new).
- `PRESET_SEEDS = {"DEEP": 4, "OVERNIGHT": 6}`.
- `PRESET_SEED_ARGS = ["--mode", "QUICK", "--time-limit", "3600"]`.
- Seeds start at 9000.
- `--preset`, `--seeds`, `--diversify-profiles`.
- A preset refuses a conflicting `--mode` or `--time-limit`.

**Colab package** (`01_ENGINE_PACKAGE`).
- `runners/rc921_runner.py`:
  - `depth_plan(args, row)`;
  - `PORTFOLIO_DEPTH_SEEDS`;
  - `--single-run`;
  - `run_portfolio(..., seeds)`.
- Notebooks A and B: `SEEDS = 0` means automatic, plus a `SINGLE_LONG_RUN`
  switch; Notebook B gains `MODE`.
- `SCENARIOS.json` carries the new engine sha.

---

## 5. Tests

| | RC5 | final |
|---|---|---|
| suites run by `run_tests.sh` | 11 | **30** |
| tests | 453 | **677** (tests/ 431 + tests_staged/ 246) |
| extra static checks | selfchecks | 2 selfchecks + cross-module call signatures + undefined-name sweep |

The final gate result is `GATE PASS — 30 suite(s) + 2 selfchecks + …`
(`05_TESTS/GATE_FINAL.log`).

**A gate defect found and fixed.** `run_tests.sh` globbed one filename
pattern, so 7 suites were never executed. Wiring them in exposed 2 stale pins
that asserted already-fixed defects were still present (7fcc425).

**New suites** (`tests_staged/`):

| suite | tests |
|---|---|
| `test_engine_logic_checks.py` | 41 fast logic checks; 8 of 8 mutations caught |
| `test_rc9_2_4_b9_metric_coverage.py` | 10 (2 skipped in this environment) |
| `test_rc9_2_5_joint_bound_shape.py` | 3 |
| `test_rc9_2_6_solver_telemetry.py` | 5 |
| `test_rc9_2_7_solver_limits.py` | 6 |
| `test_rc9_2_8_joint_default.py` | 5 |
| `test_rc9_2_9_employee_quality_validation.py` | 9 |
| `test_rc9_2_10_language_reserve_validation.py` | 10 |
| `test_rc9_2_11_time_arithmetic.py` | |
| `test_rc9_2_12_formula_audit_fixes.py` | |
| `test_rc9_2_13_f1_exact_stage2_hits.py` | |
| `test_rc9_2_14_probe_retry.py` | 10 |
| `test_rc9_2_15_capacity_and_starved_stage1.py` | 13; 8 fail on the previous engine |
| `test_rc9_2_16_stage2_parallel.py` | 4; 2 fail on the previous engine |
| `test_rc9_2_17_day_neighbourhood_break_search.py` | 16 |
| `test_rc9_2_18_seed_portfolio.py` | 8 |
| `test_rc9_2_19_joint_solve_isolation.py` | 16; includes a bit-identical check against in-process solving |
| `test_rc9_2_20_depth_presets.py` | 10 |
| `test_rc9_2_21_joint_refinement_removed.py` | 5 |
| `test_rc9_2_22_stage1_profile_rotation.py` | 8 |
| `test_rc9_2_23_break_load_feedback.py` | 7; uses a real M2 candidate fixture with its source recorded; ~126 s |

**Tests changed rather than added.** Each was re-pinned because the measured
contract changed. None was weakened, and a negative test was added alongside
where one applied.

- **Merge (4ef05e8):** 10 pins on the older engine were updated.
  - `STAGE1_MIN_MEANINGFUL_SLICE_SEC` 240 → 45 is B-3, re-pinned with both
    bounds asserted.
  - `gate_results` gained `floor_loss`.
  - `_contract_run_settings` returns a 3-tuple.
  - The validator returns 2 on a hard failure and 3 on a crash.
- **6938b55:** the Phase A packager is now DISABLED. The old test asserted
  that it packaged; the new one asserts the deprecation is enforced and
  nothing is written. The Phase C fixture was rebuilt with real sha256
  values, and 2 negative tests were added (unsealed → refused; tampered →
  refused).
- **`test_rc9_2_8_joint_default.py`:** previously pinned joint refinement ON
  at DEEP/OVERNIGHT. The premise changed with DEEP_MODE_OOM plus 474 audits
  with 0 improvements, so it now pins OFF. The reason is documented in the
  test's docstring.
- **F-1 structure test:** now scoped per block. The next-Sunday block's two
  exact hits are asserted to stay exact.

---

## 6. Every A/B and measurement, with results

`at` = after_target, `af` = after_floor, `bt` = before_target. Every run
listed passed the validator with 0 hard failures and parity PASS, unless
stated otherwise.

### 6.1 S2-PAR end-to-end (900 s, 2 workers, seed 9000): **SHIP**

| case | CURRENT at/af/bt | NEW at/af/bt |
|---|---|---|
| Cricut Chat | 155 / 228 / 163 | **179** / 224 / 196 |
| Cricut Voice | 227 / 244 / 245 | **246** / 251 / 250 |
| AE_AR_B2B | 166 / 168 / 168 | 167 / 168 / 168 |
| NMG_SP | 121 / 126 / 126 | 121 / 126 / 126 |
| SYNTH_M2 (opt 117) | 82 / 98 / 83 | **109** / 117 / 117 |
| SYNTH_H3 (opt 105) | 76 / 95 / 86 | **91** / 105 / 105 |
| **sum at** | **827** | **913** |

Note that Chat's after_floor went down by 4 (228 → 224) while target went up
24. Floor is the lower threshold.

An earlier component A/B (120 s, 4 workers) held S2-PAR back because M2 went
100 → 96, which broke a "no case worse than 2" rule. The end-to-end A/B above
was then registered and passed. See 3bfda69 and 37288d0.

### 6.2 F-1 (deterministic, 1 worker, 1800 s, seed 9000): **SHIP**

- Chat: 162 → 165 of 214.
- AE_AR: 166/165/168/167 unchanged.

**F-6** (next-Sunday deficit weight): Chat 165 → 161, **not shipped**.

### 6.3 DNBS

**v1 at 900 s: NOT SHIPPED.**
- Sum 1003 vs 1019. DNBS had effectively no window (8–49 s) and did not
  execute on 6 of 7 cases, so the difference was noise. The rule failed and
  was applied as written.
- One Voice run gained 241 → 242.

**v1 at 3600 s: VOID.**
- The container restarted after 12 of 28 runs.
- Design defect found: DNBS only got break-search leftovers. v2 was given
  its own phase.

**v2 at 3600 s, two seeds: SHIP.**

| case | CUR mean | NEW mean | Δ |
|---|---|---|---|
| Chat | 174.5 | 177.0 | +2.5 |
| Voice | 246.5 | 246.5 | 0 |
| AE_AR | 168.0 | 168.0 | 0 |
| NMG_SP | 121.0 | 121.0 | 0 |
| M2 | 110.5 | 107.5 | **−3.0** |
| H3 | 95.0 | 92.0 | **−3.0** |
| H1 | 142.0 | 146.0 | +4.0 |
| **sum** | **1057.5** | **1058.0** | +0.5 |

- DNBS executed in 14 of 14 NEW runs.
- Before-breaks sheets: Chat 191.0 → 193.5; the rest equal.
- **Honest reading:** +0.5 is inside noise. The −3 on M2 and H3 is most
  likely the 288 s that DNBS takes from break search, since DNBS accepted
  nothing on M2.

### 6.4 Seed portfolio: seeds vs time (pre-registered, commit 5c8f6aa)

**QUICK** (2 workers). A = one 3600 s run, two-seed mean; B = best of
2 × 1800 s; C = best of 4 × 900 s; D = best of 2 × 3600 s.

| case | A | B | C | D |
|---|---|---|---|---|
| Chat | 174.5 / 191 | 180 / 198 | 178 / 195 | 178 / 191 |
| Voice | 246.5 / 248.5 | 247 / 249 | 247 / 250 | 247 / 249 |
| AE_AR | 168 | 168 | 168 | 168 |
| NMG_SP | 121 / 126 | 121 / 126 | 122 / 126 | 121 / 126 |
| M2 | 110.5 | 113 | 110 | 111 |
| H3 | 95 | 90 | 93 | 98 |
| H1 | 142 | **111** | **123** | 143 |
| **sum after** | 1057.5 | 1030 | 1041 | **1066** |

Verdict: **QUICK stays one 3600 s run.** Splitting the hour costs H1 −31 and
−19; the rule allows no case worse by more than 3. Real workbooks alone
favour splitting slightly (710 → 716). D (2 hours) is best overall, so the
notebooks default to 2 QUICK seeds.

**DEEP.** E = best of 4 × 3600 s seeds; F = one 14,400 s DEEP run with the
frozen engine.

| case | E | F |
|---|---|---|
| Chat | **179** (171, 178, 179, 179) | killed at 13.0 GB, no schedule |
| Voice | 248 | 248 |
| NMG_SP | 122 | 122 |
| H1 | **143** | killed at 13.9 GB, no schedule |
| **sum** | **692** | **370** |

Verdict: **DEEP = best of 4 × 1 h; OVERNIGHT = best of 6.** Where F finished
it tied and never beat E, and no before-breaks sheet was worse under E. The
VOICE_DEEP run was first killed while my verification jobs shared the
machine, so it was rerun alone with the same seed and that rerun was scored.

**Seeds curve** (expected best-of-N from 4 observed runs per case, Chat,
Voice, NMG_SP and H1):

| step | gain |
|---|---|
| 1 → 2 seeds | +7.58 |
| 2 → 3 | +1.17 |
| 3 → 4 | +0.50 |

### 6.5 Joint-solve isolation: registered 5-check rule, **SHIP**

1. Toy deterministic solves, isolated vs in-process: identical status,
   objective, bound, every variable, branches, conflicts and deterministic
   time.
2. Real models, isolation off vs on:
   - M2: 3 solves identical, 2 of which searched (1,156 and 16,482 branches,
     same bound 117).
   - Chat: identical but trivial (INFEASIBLE in presolve).
   - H1: the in-process arm could not run at all (OOM-killed at 13 GB twice).
3. Survival on an emulated 7 GB machine:
   - Chat: the child was stopped at 233 MB free and the parent returned
     normally.
   - H1: the model build took 4.5 GB in the parent; the child was stopped at
     251 MB free and the parent returned normally.
4. End to end, M2, DEEP, 3600 s, 1 worker: validator PASS, 0 hard, parity
   PASS, audit shows ISOLATED with child exit 0.
5. Gate PASS.

**Limitation:** the Python-side model *build* runs in the parent and is not
isolated (Chat 3.8 GB, H1 4.5 GB). The only guard there is the pre-build
headroom check (2 GB or 15% free).

### 6.6 Joint refinement: measured, then removed from defaults

| evidence | result |
|---|---|
| Solver audits | 474 audits: `improved = 0` in every one |
| The 28 audits with `accepted = 1` | all anchor replays of the starting schedule |
| DEEP (NMG_SP, Voice, M2) | 36 attempts: 34 UNKNOWN, 2 INFEASIBLE, 0 improved |
| DEEP Chat and H1 | killed at 13.0 / 13.9 GB inside the phase (`DEEP_MODE_OOM.md`) |
| No-candidate endgame | 9 runs, EXHAUSTED every time, 0 candidates added |

### 6.7 Cumulative chain RC5 → final (no single direct A/B exists)

| step | measured effect | how |
|---|---|---|
| Stage-A hardening stack | **0 schedule change** (46/46 metrics, all scheduling sheets byte-identical) on AE_AR_B2B and AE_IT_B2B | deterministic, 1 worker |
| Stage-A behavioural items (B-3 slice floor, joint off at QUICK) | B-3: a 900 s run went from 0 of 15 Stage-1 profiles attempted to a funded portfolio. Joint off: 8197 → 798 MB, coverage identical | targeted measurements |
| Merge with Coverage Split | 166/165/168/167 identical | deterministic |
| F-1 | Chat +3 | deterministic |
| Anchor cap + margin | bit-identical where it does not bind | deterministic pairs |
| S2-PAR | +86 over 6 cases (900 s) | pre-registered A/B |
| DNBS v2 | +0.5 over 7 cases (3600 s, two seeds); M2/H3 −3 each | pre-registered A/B |
| Isolation, joint removal | no change at QUICK (the phase never ran at QUICK) | by construction + tests |
| DEEP/OVERNIGHT portfolio | +322 over 4 cases vs one DEEP run (mostly by not being OOM-killed) | pre-registered A/B |

Numbers at different budgets are **not additive** (900 s vs 3600 s,
different seeds). The chain shows the direction and approximate size, not a
single RC5-vs-final figure.

### 6.8 Measured and not shipped (default engine unchanged)

| change | result | status |
|---|---|---|
| Profile diversity (rotation per seed) | 1065 vs 1067; H1 −8 | opt-in flag |
| Break-load feedback in the engine (540 s at 3600 s) | 1056.5 vs 1058.0; 26 attempts, 0 accepted | opt-in flag |
| 40-min break-load feedback probe ("long-run polish") | H1 142 → 150; Chat, Voice, NMG_SP, M2 and H3 +0 | not built |
| LP-visible hit links | no gain, H1 worse | patch only |
| Skeleton ranking by quick after-break estimate | estimate unreliable | not built |
| F-6 | Chat 165 → 161 | not shipped |
| #48 unconditional joint floor bound | damaged the floor | reverted |
| B-13 constant bound | no benefit | reverted; kept as a guard test |
| Relative gap limit | not applied: the objective spans 4e8:1, so a gap does not bound coverage | off |

### 6.9 Benchmarks and synthetic suite (production budget: QUICK 3600 s, 2 workers)

| case | before the Stage-C fixes (1 worker, ≤ 1800 s) | final | proven optimum |
|---|---|---|---|
| Winston N=23 / N=22 | 56/56, 48/56 | same | 56 / 48 (OPTIMAL) |
| Union Airways N=247 | stopped at 61 s (probe) | **168** | 168 |
| Union Airways N=246 | stopped at 61 s | **168** (= upper bound) | 166–168 |
| SYNTH_M2 | 82 | 104–113 across runs and seeds | 117 |
| SYNTH_H3 | 76–77 | 90–98 across runs and seeds | 105 |
| SYNTH_H1 (24x7) | 114 | 125–151 across runs and seeds | 168 (skeleton) |
| SYNTH_X1 (120 agents, 15 min) | crash, then refusal | **500** valid | 672 |
| E1 / M1 / E2 | 63/63, 116/118, 45/63 | E2 63/63 | |
| H2, X2, R1–R5 (should refuse) | refused with the right code | same | |

Both published optima (Winston: 23 employees; Union Airways: $30,610) were
re-derived with an independent exact model before comparison
(`tools/benchmark_exact.py`).

Every published schedule validated clean, and every refusal named the right
reason (`06_EVIDENCE/NIGHT_14_TEST_SUITES_AND_BENCHMARKS.md`).

### 6.10 Headroom research (Chat)

Upper-bound relaxations using the engine's exact coverage formulas reproduce
the engine's schedules exactly:
- M2 111 = 111
- Chat 178 = 178
- Voice 246 = 246

Once the weekly rules are dropped, relaxed Chat schedules reach 218. The
proven bound is only the trivial 242, so the 179 → 218 gap is created by the
rules that were dropped:
- consecutive OFF days;
- rest gaps;
- the shift-variety limit;
- fixed assignments;
- language rules;
- break concurrency caps.

Certifying real headroom needs the full joint model, which the user excluded
from scope. See `06_EVIDENCE/upper_bound/CHAT_BOUND.md`.

---

## 7. Gains vs losses ledger

### Gained

- **Coverage:**
  - Chat about 155 → 179, Voice 227 → 248, M2 82 → 111, H3 76 → 98,
    H1 114 → 151 (best seeds);
  - Union benchmarks now optimal;
  - X1 produces a valid schedule.
- **Reliability:**
  - DEEP/OVERNIGHT no longer die at 13–14 GB;
  - QUICK peak memory 8.2 GB → ~0.8 GB;
  - the X1 crash became a result;
  - the probe no longer gives up with 94% of the budget unspent.
- **Correctness and safety:**
  - fail-closed contracts: A-1, A-2, A-7, B-11, C-3, F-2, F-5, S6-1;
  - floor-loss metric, cap and gate;
  - independent checks for 7 more metrics and 2 more gates;
  - validator next-Sunday fix;
  - blank-staffing parity fix;
  - no silent fallbacks (RC-A, RC-B).
- **Engineering:**
  - gate 11 → 30 suites (453 → 677 tests);
  - static cross-module signature check;
  - CP-SAT telemetry;
  - 213 dead lines removed;
  - Stage-1 speed-up (P-1).

### Lost, traded off, or changed in meaning

1. **DNBS costs M2 and H3 about −3 each** (two-seed means). Shipped because
   the registered rule passed on the sum (+0.5), which is inside noise.
2. **Chat after_floor −4 in the S2-PAR A/B** (228 → 224), while its target
   rose 24.
3. **Stricter inputs can refuse workbooks RC5 accepted.** These are:
   - a misspelled roster name on a leave/OFF sheet (B-11);
   - unknown preference words (C-3);
   - an invalid break contract or interval (A-1, A-2);
   - off-grid shift starts (F-2);
   - a mistyped gate mode (F-5);
   - conflicting leave inside a nesting group (S6-1).

   This is intended, but a user will see new refusals. 0 false positives
   were found on the 15-workbook corpus, and one true positive (SAKS_NEW).
4. **DEEP and OVERNIGHT mean something different now:** 4 or 6 independent
   1-hour runs, not one long run. The same wall time requires 4 or 6 × 3600 s
   of sequential compute unless seeds run in parallel. `--single-run` gives
   the old behaviour.
5. **No joint refinement and no no-candidate endgame by default.** A workbook
   where either would have helped loses it. No such workbook was found in
   474 audits and 9 endgame runs. The flags restore both.
6. **The single-run DEEP/OVERNIGHT path was not A/B-tested** after joint
   removal. Its joint reserve now goes to Stage 1 and break search.
7. **Fork overhead** on each joint solve (only when joint is enabled).
   Isolation also needs `os.fork`; it falls back in-process where fork is
   unavailable.
8. **The time spent inside Stage 2 has changed.**
   - DNBS takes 288 s of break search at 3600 s.
   - The anchor cap shortens the anchor when it binds.
9. **Validator strictness went up** (B-8, B-9 and others), so a schedule that
   RC5's validator passed could now get a warning or a parity finding.

---

## 8. Known limitations, open items, risks

- **No direct RC5-vs-final A/B.** Recommended confirmation: both engines on
  the same 7 cases, 2 seeds, 3600 s, 2 workers, same scorer (the rule format
  in `06_EVIDENCE/*/PREREGISTERED_RULE.txt`).
- **Noise versus effect size.** Two seeds per arm was the standard. H1 varies
  125–151 across seeds, so single-case differences under ~5 on H1 and under
  ~2 on the real workbooks are not significant.
- **The model build in the parent is not isolated.** A workbook whose build
  alone exceeds RAM is still exposed. That only applies with joint refinement
  enabled, which is off by default.
- **Items still open from the defect register** (`06_EVIDENCE/DEFECT_REGISTER.md`):
  - B-9b: `skill_allocation` has no independent check; 0 corpus workbooks
    use it.
  - C-2: instruction booleans have no "unrecognised" state; not reachable
    through the Excel dropdowns.
  - S9-1: the before-break ranking uses after-break terms; this is
    behavioural and was left.
  - S6-3: the fixed/nesting subsystem is unexercised by the corpus.
  - Minor items: `minute_of_day` ambiguity, `to_float` vs `strict_float`.
- **The corpus is small.** 4 real workbooks plus synthetics were used for
  A/Bs. 15 workbooks were used for contract smoke tests.
- **The release status file** still says NO_GO pending scenario and quality
  review. I did not change it.
- **Measurement environment:** a 15 GB container shared between runs.
  Contaminated runs are recorded as such and were rerun, never scored.
- **Corrections to my own earlier claims** are recorded in:
  - `06_EVIDENCE/FINAL_STATE_2026_09_23.md`;
  - `06_EVIDENCE/DEFECT_REGISTER.md` (corrections sections);
  - the commit log (the "Correct…" and "Retract…" commits).

---

## 9. How to reproduce

```bash
# gate
./run_tests.sh                       # needs ortools==9.15.6755, openpyxl, pandas, numpy, scipy

# one production run
python engine/RUN_UNIVERSAL_PRODUCTION.py --input <workbook.xlsx> --mode QUICK --time-limit 3600 \
       --num-workers 2 --solver-random-seed 9000 --output-root out/

# DEEP as shipped (best of 4 x 1 h)
# --schedule-id is required; seeds are 9000, 9001, ...; other flags pass through to the runner
python engine/RUN_PORTFOLIO.py --preset DEEP --input <workbook.xlsx> --output-root out/ --schedule-id CASE

# old behaviour
python engine/RUN_UNIVERSAL_PRODUCTION.py ... --mode DEEP --enable-joint-refinement --enable-final-recovery-endgame

# opt-in experiments
... --stage1-profile-rotation 1/4     # or RUN_PORTFOLIO.py --diversify-profiles
... --enable-break-load-feedback
```

Each A/B folder in `06_EVIDENCE` has its rule, a scorer script (`score*.py`)
and its result.

Colab: open the notebooks in `01_ENGINE_PACKAGE`. `SEEDS=0` means automatic
(QUICK 2, DEEP 4, OVERNIGHT 6).

---

## 10. Suggested audit checklist for the reviewer

1. Check that `02_CODE_DIFFS/RC5_to_FINAL__engine_full.diff` contains nothing
   not described in §3–4.
2. Check that the default path has joint refinement off (`RUN_UNIVERSAL_PRODUCTION.py`
   `all_mode_defaults`) and the endgame off (`FINAL_RECOVERY_ENDGAME_ENABLED`).
3. Review `isolated_cp_solve` for correctness:
   - response round-trip;
   - child exit handling;
   - zombie/orphan handling;
   - the watchdog threshold;
   - the fallback path.
4. Review S2-PAR:
   - Is the clone-with-literals-fixed solve equivalent to the assumption
     solve on feasible models?
   - Is the INFEASIBLE core re-solve bounded?
5. Review DNBS acceptance: dominance over the anchor plus the release
   validator; confirm it cannot accept a worse schedule.
6. Check that each re-pinned test (§5) re-pins a changed contract, not a
   weakened one.
7. Review the pre-registered rules against their results, for example whether
   DNBS's +0.5 should have shipped given M2/H3 −3.
8. Run the direct RC5-vs-final A/B (§8).
