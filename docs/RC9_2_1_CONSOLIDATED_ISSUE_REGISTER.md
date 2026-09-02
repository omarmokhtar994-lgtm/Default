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

---

# Iteration 3 — corrected fixtures, and two validator defects they exposed

## A hypothesis raised and disproved: no instruction-parser defect

The SAKS workbook's "SAKS New Test Setup" sheet declares
`11H / 3OFF Allowed = Yes`, and its Shift Library already contains 660-minute
shifts, yet the engine parsed `use_11h_3off = False`. That looked like a parser
defect — `norm()` collapses whitespace rather than removing it, so
`'11h / 3off allowed'` never matches the alias `'11h/3off'` — and a tolerant
lookup was written and tested.

**It was wrong, and the change was reverted.** `parse_input` deliberately reads
instructions only from **Engine Defaults** and **Instructions**, and those are
unambiguous:

| Sheet | Key | Value |
|---|---|---|
| Instructions | `use 11h/3off` | **No** |
| Instructions | `allowed shift durations hours` | **9** |
| Engine Defaults | `use 11h 3 off pattern` | **No** |

The setup sheet is case-notes — it sits alongside `estimated 11h/3off net
capacity` and `100% diagnostic deficit vs all-11h`. `use_11h_3off = False` was
**correct**. Engine SHA returned to `9febb23f…`; a contract diff across all 23
kit workbooks had shown the tolerant lookup was behaviour-neutral, but a
behaviour change with a disproved premise does not belong in the release.

Issue 9 stands: folder 15 genuinely cannot test 11H, because the contract
genuinely disables it. The fix is a fixture, not a code change.

## Corrected fixtures

### `fixtures/SAKS_11H_3OFF_ENABLED.xlsx`

Three Instructions cells changed; nothing else. The 660-minute shifts were
already in the library.

| Cell | Setting | Before | After |
|---|---|---|---|
| r14c3 | Allowed Shift Durations Hours | `9` | `9, 11` |
| r15c3 | Use 11H/3OFF | `No` | `Yes` |
| r27c3 | Short Break Count | `2` | `3` |

Paired against the **unmodified** original as the prohibited case — same shift
library, so the pair isolates the contract flag:

| | prohibited (original) | enabled (fixture) |
|---|---|---|
| `use_11h_3off` | False | True |
| shift durations | `[540]` | `[540, 660]` |
| 11H shifts in library | 0 of 10 | **8 of 18** |
| break contract | 15+30+15 = 60 min | **15+15+15+30 = 75 min** |

sha256 `c636d4c7…`; source `8ce4d9e0…`.

### `fixtures/NMG_EN_SP_DIRECTIONAL_BILINGUAL.xlsx`

The Language Setup sheet **already encoded** the directional mapping — English
covers `English`, Spanish covers `English,Spanish`. The English rule was dropped
only because its `Minimum Per Interval` was `0`, and `_parse_language_rules`
correctly skips zero-minimum rows. One cell changed: English minimum `0 → 1`.

| | rules | eligibility |
|---|---|---|
| original | 1 | Spanish: required `{spanish}`, eligible `{spanish}` |
| fixture | **2** | English: required `{english}`, eligible `{english, spanish}`; Spanish unchanged |

Direction verified against the engine's own predicate:

| Check | Result |
|---|---|
| Spanish speaker satisfies **English** requirement | **True** — assist allowed |
| English speaker satisfies **Spanish** requirement | **False** — not symmetric |

sha256 `891fc9d8…`; source `d318723a…`.

## 11H/3OFF proven by solve — first time in this project

Both sides solved (`SKELETON_ONLY_COMPLETE`), 600s, seed 9000:

| | 11H ENABLED | 11H PROHIBITED |
|---|---|---|
| shift durations used | 540 ×140, **660 ×88** | 540 ×250 |
| associates on 11H | **22** | **0** |
| of those with exactly 3 OFF | **22** | — |
| OFF violations | **none** | none |

Independent validation of the enabled case: **PASS, 0 hard failures**,
`artifact_role: BEST_BEFORE_BREAKS`, 246/252 target, 252/252 floor, zero
language, opening and zero-staffed gaps.

Closes M11, M12, and both 11H rows of the rule matrix — with real solves, not
parse checks.

## Issue 13 — the validator could not read a before-breaks export

**Severity:** high — every skeleton-only run failed independent validation for a
parsing reason
**Status:** FIXED

`parse_output_schedule` located its header by "SF Name" and then looked for day
columns on that same row. Exported schedules put day **names** on the banner row
and calendar **dates** on the "SF Name" row, so no day column was found and it
raised `ValueError: Output schedule is missing name/day columns` — aborting
before evaluating a single rule.

Fixed by searching the header row and its neighbours, accepting short or full
day names (the engine's own `_day_columns` convention). The error message now
names the rows searched. After the fix the same artifact validates **PASS**.

## Issue 14 — a validator crash was reported as a schedule failure

**Severity:** high — destroys the meaning of the release gate
**Status:** FIXED

`RUN_UNIVERSAL_PRODUCTION.py` mapped the validator result as
`'PASS' if vrc == 0 else 'FAIL'`. The validator exits **2** when it has evaluated
the schedule and found hard-rule violations, and **1** when it crashed. Both were
reported as `FAIL`.

That is a materially different claim: one says the schedule is invalid, the other
says the checker broke. The 11H runs surfaced it — they returned `rc=4` with
`"status": "FAIL"` while the schedules were in fact valid.

Now three-way: `PASS` / `FAIL` (exit 2, evaluated and failed) /
`ERROR_VALIDATOR_DID_NOT_COMPLETE` (anything else). **All non-zero codes still
set `rc=4`** — an unvalidated schedule must never pass — but they are no longer
conflated.

## Verification (iteration 3)

| Check | Result |
|---|---|
| `py_compile` — engine, production, tools, tests | PASS |
| rule semantics | **30/30** |
| selector integrity | **28/28** |
| validator parity | **23/23** (7 new) |
| engine selfcheck | PASS, **byte-identical to the pre-change baseline** |
| wrapper selfcheck | PASS |
| contract diff, 23 kit workbooks | no unintended change |

**Release recommendation unchanged: NO-GO. RC9.1 remains the production engine.**
Break-stage regression, deep regression and Gate 8 (folder 12's real input)
remain outstanding.

---

# Iteration 4 — NMG SP reconciled at root; Cricut narrowed to four associates

## Issue 15 — NMG SP: engine and validator disagreed on carry-in coverage

**Severity:** high — this is the long-open `Independent validator exact
agreement across suite = FAIL` gate
**Status:** ROOT-CAUSED AND FIXED

A full NMG SP run (RC=0, with breaks, guaranteed-correct pairing since the
output was produced from that exact input) reproduced the discrepancy:

| metric | engine | validator | delta |
|---|---|---|---|
| before_target | 126 | 122 | **−4** |
| after_target | 123 | 119 | **−4** |
| before_floor | 126 | 124 | −2 |
| after_floor | 124 | 122 | −2 |
| max_consecutive_floor_gaps | 1 | 2 | +1 |

Same magnitude of 4 as the historical record, and present in the **before**
metrics — so breaks were never involved. It was coverage.

**Root cause.** The validator resolved previous-Saturday carry-in by looking the
label up in *this week's* shift library:
`shift_map.get(norm(assoc.previous_saturday))`. The engine parses the label
directly via `shift_parts`. The NMG SP library holds a **single** label (it is
filtered by allowed durations and start window), while two associates carry in
`16:00 - 01:00` and `21:00 - 06:00`. Neither is in the library, so the validator
**silently dropped both**, under-counting Sunday coverage.

The engine is correct. Carry-in is historical fact — the associate worked that
shift last week. The library constrains what may be *assigned this week*, not
what *was worked*. The validator was also inconsistent with itself: it already
parses the same label directly for the rest check via
`eng.previous_saturday_compatible`, then demanded library membership for
coverage.

**Result after the fix — every coverage metric reconciles exactly:**

| metric | engine | validator before | validator after |
|---|---|---|---|
| before_target | 126 | 122 | **126** |
| after_target | 123 | 119 | **123** |
| before_floor | 126 | 124 | **126** |
| after_floor | 124 | 122 | **124** |
| severe_floor_gaps | 0 | 0 | **0** |
| max_consecutive_floor_gaps | 1 | 2 | **1** |

6 of 6 reconciled, 0 disagreements. Validator RC=0, PASS.

Regression-checked: the roster-reconciled Cricut case is unchanged at 33
failures, and SAKS 11H enabled still validates PASS/0.

## Issue 7 revisited — Cricut roster reconciliation

Building the 40-associate input was worth doing, and it narrows the problem
sharply rather than solving it.

`fixtures/Cricut_Voice_ROSTER_RECONCILED_40.xlsx` adds the eight associates the
output names but the input lacks, with the languages the **output itself
states** (all English) and no invented fixed/leave/OFF configuration. Demand and
shift library verified identical; roster 33 → 41.

**147 → 33 failures.** The 114 `UNKNOWN_BREAK_ASSOCIATE_OR_DAY` were pure roster
membership and cleared legitimately.

The surviving 33 are all on associates present in **both** files, and concentrate
in just **four** people:

| Associate | Contradiction |
|---|---|
| Abdullah Khashab | fixed `14:00 - 23:00`; output assigns five different shifts |
| Maryam AbdulWahab | fixed `10:00 - 19:00`; output assigns evenings and an OFF |
| Zyad Mahrous | fixed `00:00/01:00 - 09:00/10:00`; output assigns nights |
| Mariem Mohamed | on **leave** all week in the input; scheduled all week in the output |

Plus three Friday `HARD_OFF` violations, all `17:00 - 02:00`, and one associate
(`Kamal Aboaly`) present in the input but absent from the output.

That is not noise. The output was produced from a revision in which those four
had no fixed/leave/hard-OFF constraints. **No roster patch can close this**, and
the constraints were deliberately not stripped to force a PASS — deleting the
expected behaviour is not a fix.

**Still an external blocker**, but now a precise one: the required artifact is a
Cricut Voice input with the same 40-name roster in which Khashab, AbdulWahab,
Mahrous and Mohamed carry no fixed/leave/OFF configuration.

## Verification (iteration 4)

| Check | Result |
|---|---|
| `py_compile` | PASS |
| rule semantics | **30/30** |
| selector integrity | **28/28** |
| validator parity | **28/28** (5 new) |
| engine selfcheck | PASS, **byte-identical to the pre-change baseline** |
| wrapper selfcheck | PASS |
| Cricut regression after carry-in fix | 33, unchanged |
| SAKS 11H regression after carry-in fix | PASS/0, unchanged |

**Release recommendation unchanged: NO-GO.** Gate 8's exact-agreement failure is
now closed, but break-stage regression and deep regression remain unevidenced.
