# RC9.2.1 Test Kit — Evidence Audit

Source: `RC9_2_1_PATCH_COMPLETE_TEST_UPLOAD_KIT.zip`, delivered as three parts.
17 of 18 numbered folders present (01/02 smoke folders absent). Inputs and
runners only — **no results, leaderboards, audits or checkpoints from prior
RC9.2.1 runs are included**, except the RC9.1 Cricut resume bundle in folder 13.

## Identity verification

| Item | Result |
|---|---|
| Engine ZIP copies in kit | 17, **all hashing `f8ef5bd1…8829bd`** |
| Extracted engine | `56ec2eef…c441a` — identical to the audited RC9.2.1 build |
| GDI REAL28 input | `edd1f1ec…` — matches the copy supplied at handoff |

The kit's engine is the same build this repository baselined at commit `cf7637f`.

## Finding 6 — Every NMG EN fixture in the kit fails preflight

**Severity:** high — blocks the scenario the entire overage investigation is about
**Status:** OPEN, not an engine defect

Preflight sweep, run with `--diagnostics-only` on the fixed engine:

| Workbook | Status | Failures | Headline |
|---|---|---|---|
| AE_AR_B2B | WARN | 0 | hard-feasibility search ended UNKNOWN |
| Cricut_Chat_RC9_1_READY_SKELETON | WARN | 0 | final schedule generated |
| Cricut_Voice_RC9_1_READY_SKELETON | WARN | 0 | final schedule generated |
| GDI_REAL28_…_FINAL_READY | WARN | 0 | final schedule generated |
| NMG_EN&SP | WARN | 0 | final schedule generated |
| NMG_SP_RC9_1_READY_FIXED | WARN | 0 | final schedule generated |
| **NMG_EN_FIXED_NESTING_REST_SAFE_REGRESSION_CLEAN** | **FAIL** | **36** | English coverage impossible in a required window |
| **NMG_EN_RANDOMIZED_NAMES** | **FAIL** | 1 | fixed schedules violate minimum rest |
| **NMG_EN_RC9_1_HISTORICAL_AB_INPUT** | **FAIL** | 1 | fixed schedules violate minimum rest |

All 36 failures on the CLEAN fixture are at **Sun 02:00**: *"requires 1
English-qualified associate(s), but the maximum possible qualified coverage is
0."*

The two fixtures trade one blocking failure for the other. Patch note Fix 3
says the cleanup left "the two deliberate previous-Saturday rest-safe rows …
OFF" — that removes the Sunday 02:00 carry-in, which is what made English
coverage possible at that hour. Rest-safe and Sunday-02:00-feasible appear to be
mutually exclusive for this roster.

**Impact.** Folders 03, 04, 05, 06 and 10 all consume `…_CLEAN.xlsx`. That
includes folders 04 and 05, which `README_RC9_2_1_PATCH_FIRST.txt` designates as
the first and second tests to run and calls *"the first real proof of
protected-tier + residual OFF polish."* Neither can produce a schedule.

Confirmed identical on the unmodified baseline engine (`56ec2eef…`) and the
corrected engine — both return `FAIL_PRE_SOLVER_CONTRACT`, RC=2, 36 failures.
This is a property of the fixture, not of any change in this repository.

**Also note:** the input consumed by the recorded 4H run
(`…CLEAN2 (1).xlsx`, SHA `fd6b0cc9…`) is **not in the kit**. The shipped
`…CLEAN.xlsx` is `ac24a0fe…` — a different file. No run against the kit's
fixture is byte-comparable to the recorded 4H evidence.

## Finding 7 — Folder 12 pairs the validator output with the wrong input

**Severity:** high — invalidates the only recorded PASS for the independent-validation gate
**Status:** OPEN, not an engine defect

`RELEASE_GATES.csv` records:

> `Independent validator known-good final output,PASS,Cricut Voice 0 hard failures`

Running that exact pair from folder 12 returns **FAIL, 147 hard failures** —
identically on the baseline and corrected engines.

Roster comparison between the two files:

| | |
|---|---|
| Input roster (`Cricut_Voice_RC9_1_READY_SKELETON.xlsx`) | **33** associates |
| Output roster (`Cricut_Voice__4_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx`) | **40** associates |
| Present in both | 32 |
| Input only | 1 — `kamal aboaly` |
| Output only | 8 — abdelrahman khaled, ezzelden morgan, jana alkhunaizi, jana sultan, menna soliman, rahma alsayed, sherif yusri, zainab elsaftey |

The failure profile is entirely explained by that mismatch:

| Count | Failure type | Cause |
|---|---|---|
| 114 | `UNKNOWN_BREAK_ASSOCIATE_OR_DAY` | break rows belonging to the 8 extra associates |
| 15 | `FIXED_SHIFT_VIOLATION` | a different roster's fixed-shift configuration |
| 7 | `UNKNOWN_OR_BLANK_ASSIGNMENT` | the missing associate's empty row |
| 5 | `LEAVE_VIOLATION` | different leave configuration |
| 4 | `HARD_OFF_VIOLATION` | different hard-OFF configuration |
| 1 | `MISSING_ASSOCIATE` | `kamal aboaly` absent from output |
| 1 | `OFF_COUNT_VIOLATION` | consequence of the missing row |

The output workbook was produced from a **different, larger input** that is not
in the kit. The recorded "0 hard failures" PASS must have been obtained against
that 40-associate workbook.

This is precisely the failure mode the handoff warns about: identity established
by filename rather than by input/contract/engine hash. The validator behaved
correctly — it caught a mispaired artifact, which is what it exists to do.

**Required:** the 40-associate Cricut Voice input that actually produced that
output, or the gate is unevidenced.

## Real-data calibration of the deficit-quantization fix — it is a no-op here

Folder 13's `Cricut_RC9_1_RESUME_CHECKPOINT_BUNDLE.zip` carries genuine RC9.1
candidate pools (`RUN_IDENTITY.json` → `engine_sha256 = da21c3ba…`, the RC9.1
engine). Both were replayed through the pre-fix and post-fix orderings:

| Pool | Size | Distinct floor deficits | Champion changed? |
|---|---|---|---|
| `CANDIDATE_POOL_CHECKPOINT.json` (compliant) | 7 | 7 values, 0.00 → 4.00, **7 distinct buckets** | **No** — before and after prefixes |
| `SKELETON_CHECKPOINTS.json` | 10 | 1 value — **all 0.0** | **No** |

**The correction changes nothing on either real pool, and that is the correct
behaviour in both cases.** In the first, the candidates' floor deficits are
genuinely material — every pair is more than one quantum apart, so the ordering
rightly decides on floor before reaching balance. In the second, every skeleton
meets the floor everywhere, so the deficit terms tie exactly and the balance
terms decide even without the fix.

**This materially tempers the synthetic estimate recorded in Correction Pass 01.**
That study (78.2% of pools changing champion, mean 109 FTE saved) deliberately
constructed *floor-equivalent* candidates, which is the one condition where the
masking bites. Neither real pool available is floor-equivalent. The synthetic
figure describes the mechanism, and should not be read as an expected benefit.

The masking defect is real and demonstrable — the index-9 experiment in
Correction Pass 01 stands. But it only bites on candidates that **miss the floor
by nearly-equal amounts**. NMG EN, at 232 floor hits of 252 active intervals, is
the plausible instance — and it is the one scenario the kit cannot run.

Status of the fix on this evidence: **safe and correct, benefit unproven.**

## What the kit still does not answer

| Question | Blocker |
|---|---|
| Did the masking cause 1103.08 → 1244.11 FTE? | needs the 4H candidate leaderboard; no results in kit |
| Does a runnable NMG EN fixture exist? | all three in the kit fail preflight |
| Did RC9.1 share the masking ordering? | RC9.1 engine source still absent (only its SHA, in the checkpoint) |
| NMG SP ±4 reconciliation | needs a correctly-paired input/output; folder 12 shows pairing is not reliable |
| Gate 8 independent-validation PASS | needs the 40-associate Cricut Voice input |

**Release recommendation unchanged: NO-GO. RC9.1 remains the production engine.**

---

# GDI REAL28 24/7 A/B — first fresh CP-SAT evidence

Input `edd1f1ec…`, skeleton-only, seed 9000, 900s budget, identical on both
sides; only the engine differs (`56ec2eef…` baseline vs corrected).

## Round 1 — 2 workers, both RC=0

Five candidates tied at **exactly** 153 target / 156 floor / 153 100% / 153 90% /
156 80%, with 0 severe gaps and 0 max floor run — the precise condition under
which the deficit terms decide.

| Metric | baseline | fixed | delta |
|---|---|---|---|
| before_target / _100 / _90 | 153 / 153 / 153 | 153 / 153 / 153 | — |
| before_80 / before_floor | 156 / 156 | 156 / 156 | — |
| champion profile | `floor_gate_hunter_before` | `target_locked_residual_balance_polish` | **changed** |
| **avoidable_overage_fte_sum** | **260.20** | **246.88** | **−13.32** |
| overage_peak_fte | 8.00 | 9.68 | +1.68 |
| overage_stddev_fte | 1.6796 | 1.8064 | +0.1268 |

Coverage identical at every tier; total avoidable overage down 13.32 FTE (−5.1%).
That is the corrected ordering doing exactly what it was built to do.

**Two honest caveats.**

1. **The pools differ.** Rows 6–10 of the two leaderboards contain different
   candidates with different metrics, so multi-worker CP-SAT nondeterminism is
   confounded with the change. The 13.32 FTE cannot be attributed to the
   selector alone from this run.
2. **The fix also steers the search, not just the final pick.**
   `select_stage1_hint_skeleton` ranks with the same tuple, so a different hint
   changes the solver's trajectory and therefore which skeletons are found. The
   correction is not purely post-hoc.

## Round 2 — 1 worker (deterministic search), divergent outcomes

| | baseline | fixed |
|---|---|---|
| return code | **2** | **0** |
| status | `FAIL_NO_HARD_CLEAN_BEFORE_BREAK_SKELETON` | `SKELETON_ONLY_COMPLETE` |
| before_target / _90 / _80 / floor | — | 145 / 148 / 156 / 156 |
| avoidable overage | — | 265.60 |

At single-worker the baseline found no hard-clean skeleton inside the budget
while the corrected engine did. This is **not** evidence that the fix improves
feasibility — it is the caveat-2 effect: a different Stage-1 hint sends the
search down a different path in a budget-starved regime. Both single-worker
results are weaker than the 2-worker run (145 vs 153 target) and neither is a
controlled comparison.

## Finding 8 — skeleton-only leaderboards could not explain their own selection

**Severity:** medium — blocks after-the-fact audit of exactly this question
**Status:** FIXED

`before_break_leaderboard_rows` never populated `floor_deficit_sum`,
`target_deficit_sum`, or any avoidable/target overage field. Confirmed on the
real GDI exports: those columns are blank for all 10 candidates.

Skeleton-only is the mode used for before-break proof runs — including the NMG
EN 4H run. So the exported Candidate Leaderboard omitted precisely the terms
that decide the champion once target, protected tier, floor and gap quality tie,
and no overage regression could be diagnosed from the artifact afterwards. Had
the 4H leaderboard arrived, it would have had the same blank columns.

Now populated, plus `floor_deficit_bucket` for traceability. Three guards added.

## How to attribute cleanly

Both rounds are confounded because the selector steers search. The clean
experiment is to **rank one fixed pool two ways offline**, with no solver in the
loop. That is now possible: run once on the corrected engine so the leaderboard
carries deficits and overage, then `tools/replay_candidate_ranking.py` re-ranks
that single pool under both orderings. No re-solve, no nondeterminism.

**Release recommendation unchanged: NO-GO. RC9.1 remains the production engine.**
