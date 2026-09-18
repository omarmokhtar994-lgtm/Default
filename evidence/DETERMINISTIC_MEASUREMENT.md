# The measurement problem, and its fix

## What went wrong all session

Every A/B in this review was fought against a noise band of plus or minus 1 to
4 intervals. That band forced multi-seed repeats, made single runs
uninterpretable, and produced at least two confident conclusions that later
reversed:

  - AE_IT_Choice appeared to be unblocked by the applied stack at seed 9000.
    At seed 9001 the UNPATCHED arm unblocked it too, and at 9002 neither did.
  - B-13 appeared to cost 4 target and 1 floor interval at seed 9000. See below.

## The cause was the solver, not the schedule

CP-SAT is a portfolio solver. With several workers it races different strategies
and shares information between them, so the result depends on thread timing.
Google's own issue tracker carries cases of one model returning OPTIMAL on a
single worker and INFEASIBLE on eight, and reports of higher worker counts being
dramatically SLOWER -- 13.6 seconds on one thread against 807 seconds on
thirty-two for the same instance.

The engine runs `--num-workers 2`. That is two racing strategies, and every
measurement inherited their timing.

## The fix, verified here

`--num-workers 1` removes the race. Two runs of AE_IT_B2B at seed 9000 returned
byte-identical metrics, including `after_avoidable_overage_fte_sum` at 23.625 to
three decimals.

**One run per arm is therefore sufficient.** Any difference is attributable to
the code, because nothing else varied.

## It immediately settled B-13

Re-running the B-13 comparison deterministically, control tree against the B-13
tree, one worker, same seed:

    metric                      control   B-13   delta
    before_target                    73     73     +0
    after_target                     67     67     +0
    before_floor                     91     91     +0
    after_floor                      87     87     +0
    floor_losses_from_breaks          4      4     +0
    target_losses_from_breaks         6      6     +0

Identical. The earlier "-4 target, -1 floor" that prompted the revert was
**noise**, not a regression. The revert was still right, for the reason the
arithmetic gave: where `min_after_floor` is passed it is tighter than the
gameable bound (88 against 91-6=85), so replacing the gameable bound is a no-op.
Now measured as well as argued.

## What to use

`tools/deterministic_ab.sh <control_tree> <treatment_tree> <workbook> [seconds]`

Two runs, one worker each, diffs the full canonical metric surface and reports
either IDENTICAL or the exact fields that moved.

**This is a measurement tool, not a production setting.** Production should keep
multiple workers, because the portfolio finds better schedules in the same wall
clock. Single-worker is for answering "did this change do anything", where
reproducibility beats quality.

## What it would have saved

The multi-seed repeats in this review cost roughly six hours of solver time and
still left B-13 ambiguous. The deterministic pair cost ten minutes and settled
it. Any future engine change should be measured this way first, and only taken
to multi-worker multi-seed runs if the deterministic comparison shows a
difference worth characterising.

---

## Result: what the nine-fix stack actually did to schedules

Measured 2026-09-18 at `--num-workers 1 --solver-random-seed 9000 --time-limit 300`,
one run per arm (deterministic, so one run is the whole answer).

| | ORIGINAL | NINE FIXES |
|---|---|---|
| Engine SHA256 | `f5f997890bfc3f53` | `172d771001193ea0` |
| Input SHA256 (AR) | `5c15a9bc363a36a2` | `5c15a9bc363a36a2` — SAME |
| Input SHA256 (IT) | `83080efc496cb7ca` | `83080efc496cb7ca` — SAME |

A/B validity holds: the input is bit-identical in both arms, the engine is not.
`Contract SHA256` differs because B-9 added seven fields to the contract — that is
the change under test, not a confound.

### Headline

**The nine fixes changed no schedule.** On both `AE_AR_B2B` and `AE_IT_B2B`,
every one of the 46 pre-existing canonical metric fields is identical between
arms. Coverage numbers, break placement, candidate selection: unchanged.

Sheet-by-sheet content comparison of the final workbook (53 sheets) confirms it.
The only sheets that differ are:

- `Production Summary` — Run ID, Contract SHA256, Engine SHA256, input path
- `Optimization Audit` — Run ID, input/output paths
- `Candidate Leaderboard` — one row, see below

Every scheduling sheet is byte-identical: `Final Schedule`, `Break Schedule`,
`Interval Coverage Audit`, `Coverage Before Breaks`, `Overage Audit`,
`Whole Week Balance Audit`, `Rest Gap Audit`, all FT-wise sheets.

### What the fixes did add

Seven metrics that were previously computed but never checked are now on the
parity surface, taking the compared-field count from 46 to 53:

`target_losses_from_breaks`, `floor_losses_from_breaks`,
`before_severe_floor_gap_count`, `hard_floor_gap_count`,
`week_boundary_hard_failure_count`, `week_boundary_max_adjacent_raw_change`,
`week_boundary_max_coverage_ratio`

Naming note: the last three appear on the canonical metric surface as
`week_boundary_*` but are written into `INDEPENDENT_VALIDATION.csv` as
`next_sunday_*`. Same three metrics, two names, two artifacts. Not a defect
in the numbers, but anyone grepping one name will miss the other.

All seven cross-check PASS against the independent validator on both cases.
`metric_parity_status` stays PASS, `metric_parity_mismatch_count` stays 0 —
so the seven newly-checked metrics agree between engine and validator, which
is the first time that has been established.

### The one behavioural delta

`AE_IT_B2B`, candidate leaderboard row 2 (`skeleton_profile=target90_restore_champion`),
**not selected** in either arm:

| field | orig | new |
|---|---|---|
| `after_severe_overage_count` | 14 | 13 |
| `floor_deficit_sum` | 6.71625 | 6.705 |
| `whole_week_imbalance_violations` | 2 | 1 |
| `transferable_overstaffing_pairs` | 4 | 5 |
| `objective` | 1417534190.0 | 1417536836.0 |

The new tree produced a marginally better candidate here. It did not win
selection, so it reached no output. This is the only evidence in the whole
comparison that the fixes touch search behaviour at all, and it is one
non-selected candidate on one case.

### Interpretation

The nine fixes are **diagnostic and safety work, not coverage work**. They
close fail-open paths (B-11), remove dead code (S13-2), align shadow defaults
(RC-B), convert silent cross-metric fallbacks into loud failures (RC-A), and
widen the parity gate (B-9). None of that was ever going to move a coverage
number, and measurement now confirms it did not.

This does not argue against the fixes — a fail-open parser that silently drops
a roster row is worth fixing whether or not it changes today's numbers. It
argues against claiming a coverage improvement. The earlier
**"+0.15% target, 0.00% floor"** figure came from multi-worker runs and was
solver noise; the honest figure is **0.00% / 0.00%**.

### Consequence for the release decision

Unchanged: **keep RC9.1 as production.** RC9.2.2 is now better instrumented
and has fewer fail-open paths, but it delivers no measured schedule improvement
on the two cases tested. There is no coverage case for promoting it, and the
instrumentation case is not urgent.

### Extended to the remaining AE cases

Same protocol, `AE_FR_B2B` and `AE_FR_Choice`:

| case | orig outcome | new outcome | shared fields | differing |
|---|---|---|---|---|
| `AE_FR_B2B` | `FINAL_SCHEDULE_GENERATED_WITH_DECLARED_QUALITY_DEBT` | same | 46 | **0** |
| `AE_FR_Choice` | `FINAL_SCHEDULE_GENERATED_WITH_DECLARED_QUALITY_DEBT` | same | 46 | **0** |

Both arms `production_eligible: true`, `independent_validation: PASS`,
`metric_parity: PASS`, surface 46 -> 53.

### Final tally across all four AE cases

| case | shared fields identical | new fields added | schedule changed |
|---|---|---|---|
| `AE_AR_B2B` | 46 / 46 | 7 | no |
| `AE_IT_B2B` | 46 / 46 | 7 | no (one non-selected candidate differs) |
| `AE_FR_B2B` | 46 / 46 | 7 | no |
| `AE_FR_Choice` | 46 / 46 | 7 | no |

184 of 184 pre-existing metric comparisons identical. The nine-fix stack is
coverage-neutral on the entire AE corpus, and the parity gate now checks
seven more metrics on every case.
