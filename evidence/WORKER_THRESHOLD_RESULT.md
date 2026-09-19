# The 5-worker threshold: mechanism real, effect absent

18 runs, AE_AR_B2B and AE_FR_B2B, workers {4,5,8}, seeds 9000-9002, 300s,
strictly sequential on an otherwise idle 4-core box.

## Primary metric: the hypothesis is NOT supported

| case | workers | UNKNOWN rate | mean after_target |
|---|---|---|---|
| AE_AR_B2B | 4 | **3/3** | 163.0 |
| AE_AR_B2B | 5 | **3/3** | 161.0 |
| AE_AR_B2B | 8 | **3/3** | 160.3 |
| AE_FR_B2B | 4 | 2/3 | 107.0 |
| AE_FR_B2B | 5 | **3/3** | 100.3 |
| AE_FR_B2B | 8 | 1/3 | 107.7 |

Crossing the 5-worker threshold **did not reduce UNKNOWN**. On AE_AR_B2B the
rate is 3/3 at every worker count. On AE_FR_B2B it was *worse* at 5 than at 4.

The subsolver portfolio change is real — proven directly on 9.15.6755, zero
first-solution subsolvers at 4 workers and `fj` + `fs_random_no_lp` at 5. It
simply is not what causes our UNKNOWNs. Adding Feasibility Jump to the
portfolio changed nothing about them.

**The cause of the Stage-2 UNKNOWNs remains unexplained.** It is not the
subsolver threshold, and (per the earlier retraction) it is not a reliability
problem either — every one of these runs still produced a valid schedule.

Quality also did not improve with workers; on a 4-core host it drifted mildly
down, consistent with the oversubscription confound declared before the run.

## The finding that did emerge, and it is large

Compare against the budget sweep on the same case and engine:

| configuration | budget | after_target |
|---|---|---|
| 1 worker (sweep) | 600s | 131 |
| 1 worker (sweep) | 1800s | 165 |
| **4 workers** | **300s** | **165, 165, 159** |

**300 seconds at 4 workers matches 1800 seconds at 1 worker** — roughly a
**6x** effective speedup from the portfolio, far outside the +/-1-4 interval
noise band that dogged every single-worker comparison.

## This re-opens a question I thought was settled

The budget sweep concluded that long budgets are genuinely used on the hard
case, because AE_AR_B2B climbed 131 -> 142 -> 165 across 600/900/1800s. **That
was measured at one worker.** At four workers the same case reaches 165 in 300
seconds.

So my retraction of the "budgets are oversized" claim may itself need
retracting. The correct statement today is narrower: **the budget curve has
only ever been measured in a crippled configuration, and the production
question is open.** Re-running the sweep at realistic worker counts is now the
highest-value measurement available.

It also means every single-worker number in this review is a **lower bound**,
and the gap is much larger than I assumed when I called them "valid as an A/B
instrument". They remain valid for comparing two engines; they badly
under-represent production quality.

## Incidental

`stage1_attempts` was **0** in 16 of 18 runs at 300s regardless of worker
count, so Stage-1 budget starvation at short budgets is independent of workers.
