# RC9.2.1 Consolidated Issue Register

Every reported failure, regression and gap from the delivered evidence
(`RELEASE_GATES.csv`, `RULE_VERIFICATION_MATRIX.csv`, `MICRO_TEST_MANIFEST.json`,
`REGRESSION_SCENARIO_MANIFEST.json`, the handoff notepad, and this session's own
execution), consolidated to root causes rather than symptoms.

## Consolidation

Twelve of the recorded PENDING/NOT_RUN entries shared **one** root cause:
`"OR-Tools unavailable offline"`. That is a single environment blocker, not
twelve defects. OR-Tools 9.15.6755 is now installed and solving, so they were
executed rather than re-reported.

| # | Issue | Root cause | Status |
|---|---|---|---|
| 1 | Balance/overage unreachable when floor missed | raw floats above the balance block in a lexicographic tuple | **FIXED** |
| 2 | Deficit metrics had no before-break variant | metric asymmetry in `calculate_metrics` | **FIXED** |
| 3 | Runner stamped runs with the RC9.2 release name | hardcoded literal drifted from engine `VERSION` | **FIXED** |
| 4 | Validator long-shift threshold 660 vs engine 630 | contract constant duplicated instead of shared | **FIXED** |
| 5 | Validator understated avoidable overage | missing ceil tolerance | **FIXED** |
| 6 | All 3 NMG EN fixtures fail preflight | fixture defect, engine correct | **FIXED** (repaired fixture) |
| 7 | Folder 12 validator pair mismatched | 33-associate input vs 40-associate output | **BLOCKED** — needs the real input |
| 8 | Skeleton leaderboards could not explain selection | deficit/overage columns never populated | **FIXED** |
| 9 | Folder 15 cannot test 11H/3OFF | fixture has `use_11h_3off=False`, only 540-min shifts | **MITIGATED** (unit guards) |
| 10 | Folder 17 cannot test directional assist | single Spanish rule, no English rule or mapping | **MITIGATED** (unit guards) |
| 11 | Carry-in overage charged as avoidable | no separation of solver-uncontrollable staffing | **FIXED** |
| 12 | M06/M09/M14 negative tests never executed | OR-Tools unavailable | **EXECUTED — all pass** |

## Issue 6 — NMG EN preflight, root cause and repair

**Root cause.** Not an engine defect. The engine's diagnosis is correct in both
variants, verified by hand:

* Historical/randomized fixtures: prev-Sat `23:00 - 08:00` ends 08:00 Sunday
  against a fixed Sunday start of 14:00 — a 6h gap under a 12h rest rule (the
  second case is 9h). Genuine violations.
* Cleaned fixture: Sunday 02:00–08:00 is active with demand (8.8 FTE at 02:00)
  and an English minimum of 1, but no previous-Saturday shift reaches past
  02:00 and no shift in the library starts early enough on Sunday. Maximum
  possible coverage really is 0. Failures decompose exactly as 24
  `LANGUAGE_WINDOW_MAX_CAPACITY_BELOW_MINIMUM` (per quarter) plus 12
  `ZERO_ACTIVE_INTERVAL_PROVABLY_IMPOSSIBLE` (per interval) over that window.

The rest-safe cleanup resolved the rest conflict by replacing the overnight
carry-in rows with shifts ending at or before 02:00 — and orphaned Sunday's
small hours in the process. The two constraints were traded, not both satisfied.

**Repair** (`fixtures/NMG_EN_REST_SAFE_REGRESSION_CLEAN_SUNDAY_CARRYIN_REPAIR.xlsx`,
authorised by the project owner). Previous-Saturday `23:00 - 08:00` added to
**Associates 016–025** on the `Previous week scheduled` sheet.

Those ten were chosen deliberately: they are fixed **OFF on Sunday**, so a
carry-in ending 08:00 Sunday cannot violate the 12h rest rule. Associates
001–015 are fixed to a Sunday `14:00 - 23:00` shift and would each have gained a
6h-gap violation; the 12 flexible rows (031–042) would have had every Sunday
start before 20:00 forbidden.

Verified equivalent in every other respect — demand, shrinkage, active
intervals, fixed schedules, shift library and all 42 associates identical;
only 10 `previous_saturday` values differ.

| | source | repaired |
|---|---|---|
| sha256 | `ac24a0fe…` | `ed90d630…` |
| preflight | FAIL, 36 failures | **PASS, 0 failures** |

Resulting Sunday carry-in coverage: 97.4% at 00:00, 98.3% at 01:00, 98.9% at
02:00 — a well-formed scenario.

**Known property, stated explicitly:** a 23:00–08:00 shift runs on while Sunday
demand collapses to 0.9 FTE, so 05:00–07:30 sits at 345–1111% coverage. This is
inherent to the shift shape, not an artefact of the repair, but it inflates
overage metrics — which is why issue 11 was fixed alongside it. Results from
this fixture are **not** comparable to the recorded 4H evidence: that run
consumed `CLEAN2 (1).xlsx` (`fd6b0cc9…`), a different file.

## Issue 11 — carry-in overage was charged as avoidable

**Root cause.** Previous-week carry-in is fixed workbook input, not a decision
variable — the solver cannot remove those associates from an interval. But where
carry-in alone exceeds the staffing the target needs, the whole excess was
charged as *avoidable* overage.

Measured on the repaired fixture: Sunday 07:00 has 0.9 FTE of demand against 10
carry-in associates, booking **9.0 FTE of avoidable overage** in that interval
alone, flagged `severe` and `extreme`, with `indivisible_staffing_only` **False**
so nothing marked it structural. Across Sunday 05:00–07:30 that is **48 FTE**
of "avoidable" overage no schedule could have avoided.

This matters directly for the release question: an overage regression caused by
the input contract was indistinguishable from one caused by the optimizer.

**Fix.** Four additive metrics, measurement only:
`carry_in_forced_overage_fte_sum`, `carry_in_forced_overage_interval_count`,
`before_/after_solver_controllable_avoidable_overage_fte_sum`.
Defined as `max(0, carry-in effective − unavoidable at target)`.

**Ranking is deliberately unchanged.** Feeding this into the selector would be a
behaviour change requiring its own evidence; a guard asserts the new keys never
appear in `_candidate_quality_tuple`.

## Issue 12 — negative fixtures, executed

All four fail for the **correct diagnosed reason**, which is the intended result:

| Fixture | Result | Codes |
|---|---|---|
| NEG_HEADCOUNT_MISMATCH | FAIL | `HEADCOUNT_MISMATCH` ×1 |
| NEG_LANGUAGE_SHORTAGE | FAIL | `LANGUAGE_MINIMUM_EXCEEDS_ELIGIBLE_ROSTER`, `LANGUAGE_WINDOW_MAX_CAPACITY_BELOW_MINIMUM` ×252, +2 more |
| NEG_FIXED_CYCLIC_REST | FAIL | `FIXED_CYCLIC_REST_CONFLICT` ×1 |
| NEG_OPENING_GUARD_CAPACITY | FAIL | `OPENING_MINIMUM_EXCEEDS_ROSTER`, `OPENING_WINDOW_MAX_CAPACITY_BELOW_MINIMUM` ×56, +1 |

Closes M05, **M06**, **M09**, **M14**.

## Issues 9 & 10 — fixture coverage gaps

Confirmed by parsing the shipped workbooks:

* `15_11H_3OFF_SAKS`: `use_11h_3off=False`, shift durations `[540]` only. Cannot
  exercise 11H/3OFF or the 11H break pattern. It *does* exercise separate OFF
  (`separate_off_days=True`).
* `17_BILINGUAL_NMG_EN_SP`: one rule — Spanish, eligible `{spanish}`. No English
  rule and no directional mapping, so "assists English only in the configured
  direction" and "no double counting" are unobservable. GDI REAL28 *does*
  exercise eligibility inversion (`Bilingual/French` accepts both).
* No fixture anywhere in the kit has a shift ≥ 630 min, so nothing would catch a
  regression in the issue-4 threshold change.

**Mitigation.** A missing fixture is not a reason to leave semantics unpinned.
`tests/test_rc9_2_1_rule_semantics.py` exercises the engine's own predicates
directly — 26 guards covering language eligibility and direction, the long-shift
OFF boundary, rest including carry-in, half-open carry-in coverage, and the
9H/11H break patterns. Real fixtures are still required to close the matrix rows.

---

# Iteration 2 — execution results and the decisive attribution test

## Issue 6 closed: NMG EN now runs

First successful NMG EN run in the project. Both engines RC=0 on the repaired
fixture, skeleton-only, seed 9000, 900s, 2 workers.

| Metric | baseline `56ec2eef` | corrected |
|---|---|---|
| before_target / before_90 | 228 | 227 |
| before_80 / before_floor | 231 / 232 | 231 / 232 |
| before_100 | 216 | 215 |
| avoidable overage | 1154.67 | 1150.07 |

**The one-interval target drop is search divergence, not a selector regression.**
`before_target` is tuple position 0, so the selector cannot prefer a lower-target
candidate. Confirmed from the pools: the corrected run's leaderboard tops out at
**227**, the baseline's contains a **228** — the corrected search never found one.
The cause is that `select_stage1_hint_skeleton` ranks with the same tuple, so
changing the ordering changes the solver's starting hint and therefore its
trajectory. The correction is not purely post-hoc, and every A/B of it is
confounded for that reason.

## The decisive test — one pool, two orderings, no solver

Run once on the corrected engine so the leaderboard carries deficits and overage
(the issue-8 fix), then re-rank that single pool both ways offline:

```
candidates in pool : 12     contract: target 90%, floor 75%, 252 active
pre-fix champion   : target_locked_residual_balance_polish  227/232  overage 1153.05
post-fix champion  : target_locked_residual_balance_polish  227/232  overage 1153.05
VERDICT: champion UNCHANGED
```

## Honest conclusion on the deficit-masking correction

**The defect is real and provable; it does not bite on any real pool examined.**

| Pool | Source | Champion changed? |
|---|---|---|
| Cricut candidate pool (7) | RC9.1 checkpoint `da21c3ba` | No |
| Cricut skeletons (10) | RC9.1 checkpoint | No |
| **NMG EN (12)** | **fresh run, isolated re-rank** | **No** |
| GDI REAL28 (10) | fresh A/B | Changed — but pools differed, confounded |

The reason is visible in the NMG EN leaderboard: floor deficits span 4.39 → 8.84
and adjacent candidates differ by ~0.20 — **twenty quanta**. Real candidates are
nowhere near floor-equivalent, so the comparison legitimately resolves on floor
long before the balance block. The synthetic 78% figure in Correction Pass 01
described a floor-equivalent regime that does not occur in this corpus.

The correction remains **correct and safe** — it removes a genuine pathology in
which an 8th-decimal difference outranks 141 FTE — but its practical benefit is
**not demonstrated on real data**, and the single GDI observation is more likely
search divergence than selector effect.

## Overage sum vs peak ordering — deliberately NOT changed

Round 1 on GDI traded overage sum down 13.32 FTE for peak up 1.68. The question
was whether the tuple should rank peak or spread above sum.

**No change made, on evidence.** The overage block is rarely reached at all on
real pools, so reordering within it would be speculative — and within NMG EN's
top group the entire overage spread is 1152.53 → 1153.05, i.e. **0.52 FTE**.
Changing priority order on that basis would be exactly the stacked speculative
patch the handoff forbids. Revisit only if a pool is found where the block
actually decides.

## Issue 11 validated end-to-end on a real run

| | FTE |
|---|---|
| total avoidable overage | 1153.05 |
| **carry-in forced** (solver cannot avoid) | **61.59** across 15 intervals |
| solver-controllable | 1091.07 |

5.3% of the headline number is structurally forced by fixed previous-week input.
Part of that is introduced by the repair itself (10 added carry-in rows), but the
mechanism is general and applies to any scenario with overnight carry-in.

## M15 resume identity — PASSES

Resuming the RC9.1 checkpoint (`run_id fd33cad8…`) with the folder-13 workbook
raises:

> `Resume refused: input/contract/engine/seed/parameters hash differs from the existing run identity`

The gate is sound rather than nominal: `run_id = canonical_hash(run_identity)[:24]`
over version, input, contract, engine, seed and parameter hashes, so run_id
equality implies full identity equality. The message also correctly separates
technical failure from staffing infeasibility. Four guards added.

An initial attempt appeared to show only silent non-resume; that was a test
error — the guard reads `work_dir/RUN_IDENTITY.json` (`<case>/debug`) and the
checkpoint had been placed in the case root. Corrected, and the refusal fires.

## Final verification

| Check | Result |
|---|---|
| `py_compile` — engine, production, tools, tests | PASS |
| `tests/test_rc9_2_1_rule_semantics.py` | **30/30** |
| `tests/test_rc9_2_1_selector_integrity.py` | **28/28** |
| `tests/test_rc9_2_1_validator_parity.py` | **16/16** |
| engine selfcheck | PASS, **byte-identical to the pre-change baseline** |
| wrapper selfcheck | PASS |

Engine SHA after all corrections: `9febb23f0cc75cbbc493c072696b01c7db6cb303a691102f551c7b3b5b4f644f`

**Release recommendation unchanged: NO-GO. RC9.1 remains the production engine.**
Break-stage regression, deep regression and Gate 8 remain unevidenced.
