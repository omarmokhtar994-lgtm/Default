# F-03 result: RC5 vs FINAL, 6 paired seeds

Scored on 2026-10-02 at 19:05 UTC by `score.py`, against `PREREGISTERED_RULE.txt`
as amended by `AMENDMENTS.txt` (A1: seeds 9000-9005, MIN_PAIRS 5; A2: comparator
failure). The full output is in `SCORE_OUTPUT.txt`. All 72 runs were recorded,
none contaminated, and none timed out.

## Verdict: INCONCLUSIVE (rule 3 fails)

| rule | result |
|---|---|
| 1 validity: every FINAL run validated | PASS: 36 of 36 |
| 2 robustness: FINAL failures <= RC5 failures | PASS: 0 vs 7 |
| 3 non-inferiority, each real case | **FAIL**: details below |
| 4 synthetic after_target CI lower >= -3 | PASS: H1 +20.0, M2 +6.2 |
| 5 superiority: summed real after_target CI lower > 0 | PASS: +24.0, CI [+15.8, +33.2] |
| 6 resources: elapsed <= 3,780 s, RSS <= 8 GB | PASS |
| 7 contract | PASS |

No real case regressed on after_target. That rules out ROLLBACK.

## What was measured

### Robustness

- **FINAL:** validated 36 of 36 runs.
- **RC5:** failed its own validator on 7 of 36 runs, every time with `FAIL_METRIC_PARITY`: the engine's metrics disagreed with its validator.
  - NMG_SP failed on 6 of 6 seeds. Under A2, NMGSP is therefore a comparator failure, reported but not compared.
  - Chat failed on seed 9001.

### Primary metric: after-break target coverage (FINAL - RC5, mean of paired deltas)

| case | delta | 95% CI |
|---|---|---|
| CHAT | +15.8 | [+11.0, +20.6] |
| VOICE | +4.2 | [-0.5, +11.5] |
| AEIT | +4.0 | [+0.3, +7.3] |
| H1 | +20.0 | [+14.0, +26.5] |
| M2 | +6.2 | [+4.3, +7.8] |

### Break concurrency violations

FINAL is lower on every case:

| case | RC5 | FINAL |
|---|---|---|
| CHAT | 10.2 | 0.4 |
| VOICE | 20.5 | 3.8 |
| AEIT | 14.2 | 1.2 |
| H1 | 2.2 | 0.2 |
| M2 | 4.2 | 0.0 |

## Why rule 3 fails

1. **AE_IT_B2B after-break floor coverage is worse, beyond the margin.**
   - `after_floor` is -4.0 with CI [-5.2, -2.7]. `floor_gaps` is +4.0 and `severe_floor_gaps` is +2.3, CI [+0.2, +4.5].
   - FINAL gives up about 4 floor quarters for +4 target quarters and about 13 fewer break concurrency violations per run.
   - More seeds would not change this; it is a real effect.
   - Not proven: RC5's floor coverage on this case may be partly bought by breaking the concurrency cap (8 to 21 violations per run, against 0 to 3 for FINAL).
2. **Best before-break target is slightly lower on all three compared real cases.**

   | case | delta | 95% CI |
   |---|---|---|
   | CHAT | -3.2 | [-5.4, -0.6] |
   | VOICE | -1.3 | [-1.8, -0.7] |
   | AEIT | -2.3 | [-4.0, -0.7] |

   All three CIs straddle the -1 margin. The mean losses are small and consistent: FINAL keeps less of the pre-break skeleton and more after breaks.
3. **Some CIs are just wide at n = 5 or 6.**
   - CHAT `after_floor` has mean +2.0 but CI [-2.0, +5.2].
   - CHAT `severe_floor_gaps` has mean -3.0 but CI upper +1.6.
   - VOICE `severe_floor_gaps` has mean -0.8 but CI upper +1.2.

## What the registered outcome says, and what this result supports

**Registered outcome for INCONCLUSIVE:** "keep current production and add 10 seeds for the affected cases".

**What this result supports:**
- FINAL is more robust than RC5: 0 failures against 7.
- FINAL is better on the primary after-break target: summed +24, with a CI that excludes 0.
- FINAL is far better on break concurrency.
- FINAL is **not** shown non-inferior on secondary metrics.
  - Its AE_IT_B2B after-break floor is worse by about 4 quarters, beyond the registered margin.
  - Its before-break target tends to be 1 to 3 quarters lower.

**Not concluded:** that FINAL is better than RC5 overall, or that it is no worse on every metric.

**Not measured:** the other five AE workbooks, E2 and Union. FINAL vs RC5 on them is still unknown.
