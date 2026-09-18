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
