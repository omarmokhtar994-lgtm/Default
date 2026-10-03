# AE_IT_B2B after-break floor: FINAL 4 lower than RC5 (F-03 rule 3)

The rule for the last test was registered first (`RULE.txt`, commit 4e47d9e).
All runs: QUICK 3600 s, 2 workers, each pinned to 2 cores, validator PASS.

## Where the 4 intervals go

From the 12 F-03 runs (means, FINAL - RC5):

- **Before breaks:** the chosen skeleton's floor is about -3 (FINAL 90.7, RC5 93.7).
- **Placing breaks:** about -1 more (FINAL loses 3.2 floor intervals to breaks, RC5 2.2).

## Hypotheses tested

| hypothesis | test | result |
|---|---|---|
| The selector passes over a better candidate | FINAL seed 9002 rerun with the full audit; its 34-candidate pool | **Refuted.** No candidate has target >= 70 and floor >= 91. The high-floor candidates (floor 99-105) have target 28-39. The published schedule is picked from skeletons within 6 before-target intervals of the best one (`--max-final-before-target-loss 6`), the same rule as RC5. |
| FINAL respects the break-concurrency limit and RC5 did not (RC5 had 8-21 violations per run, FINAL 0-3) | Limit lifted (ratio 0.75, count 99), seeds 9002 and 9004 | **Refuted.** 76/89 and 78/88. FINAL still used at most 3-4 concurrent breaks, and its floor stayed in its own 85-89 range. |
| B-3: Stage-1 minimum slice cut from 240 s (RC5) to 45 s (FINAL), so RC5 runs 3 deep profiles and FINAL 10-11 shallow ones | Slice 240 on FINAL, seeds 9002 and 9004 (registered rule) | **Refuted for floor:** 72/88 and 69/85, both <= 89. Best before-break target: 85 and 82, so B-3 partly explains rule 3's before-target item. |

| run | after target | after floor | before floor | best before target | Stage-1 profiles |
|---|---|---|---|---|---|
| RC5, 6-seed mean (F-03) | 68.2 | 91.5 | 93.7 | 84.5 | 3 / 15 |
| FINAL, 6-seed mean (F-03) | 72.2 | 87.5 | 90.7 | 82.2 | 10-11 / 15 |
| FINAL 9002 rerun | 71 | 87 | 91 | 82 | 10 |
| FINAL 9002, no concurrency limit | 76 | 89 | 98 | 77 | 11 |
| FINAL 9004, no concurrency limit | 78 | 88 | 91 | 82 | 12 |
| FINAL 9002, slice 240 | 72 | 88 | 91 | 85 | 1 |
| FINAL 9004, slice 240 | 69 | 85 | 90 | 82 | 2 |

## Conclusion

- **What it is not.** The floor loss is real, and it is not:
  - a selection defect;
  - the price of the break-concurrency limit;
  - the Stage-1 slice change on its own.
- **Where it sits.** In the search outcome, mostly before breaks. At a similar
  before-break target, FINAL's Stage-1 skeletons hold less floor than RC5's.
- **What could cause it.** The remaining RC5 -> FINAL differences that act there
  are the Stage-1 portfolio sizing and budget phases (A34/A35/A37) and the
  profile mix. They are interlocked, so a single-factor test cannot isolate them.
- **The trade-off on this case.** FINAL is about +4 on target and -4 on floor.
  Every FINAL schedule here passed the validator, and FINAL keeps the break
  concurrency limit, which RC5 broke 8-21 times per run.
- **Next step, if this trade is not acceptable for AE_IT.** A stage-by-stage
  bisection between RC5 and FINAL on AE_IT, with at least 5 seeds per arm. This
  is the registered "bisect along the stage diffs" action. No engine change is
  made without it.
