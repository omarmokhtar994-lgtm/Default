# A40 controlled experiment — does scaling the break-concurrency penalty help?

One skeleton, one break solve, two penalty weights, everything else identical.
Engine RC9.2.2, NMG EN+SP, `release_gate_floor_satisfaction` skeleton at a 300s
slice, width 115, objective mode `target_priority`, seed 9000, 4 workers, 300s
per break solve.

Skeleton: before_target **185**, before_floor **244**.

| penalty | after_target | after_floor | target lost to breaks | max concurrent breaks | avoidable overage FTE |
|---|---|---|---|---|---|
| OLD fixed 5,000 | 140 | 207 | 45 | **5** | 22.82 |
| NEW derived | **141** | **208** | **44** | **4** | 22.82 |

## Verdict: the mechanism works, the problem does not move

**What the fix does do.** Maximum concurrent breaks drops from 5 to 4, which is
exactly the workbook's configured `Maximum Concurrent Breaks = 4`. The penalty
was previously inert at a ratio of about 1:140,000 against the coverage terms;
it now binds and pulls concurrency to the cap. The defect in A40 was real and is
corrected.

**What the fix does not do.** Break damage moves by **one interval** — 45 to 44
of 252. Overage is identical to two decimal places. On a single seed that is
inside noise. The 11.1% structural break cost is still being exceeded (44/252 =
17.5%), so this skeleton is still losing more coverage to breaks than blind
placement would cost.

## What this means, plainly

I framed break-concurrency clustering as the likely cause of NMG EN+SP's
worse-than-blind break damage, on the strength of 18 recorded violations and an
arithmetically inert guard. **That framing is not supported by this
measurement.** Concurrency was genuinely broken and is genuinely fixed, and the
coverage loss it was supposed to explain is still there.

A40 is kept: it corrects a guard that could not function, it brings concurrency
within the configured cap, and it costs nothing (+1 target, +1 floor, identical
overage, identical runtime). It is **not** the fix for break damage and must not
be reported as one.

## Where the NMG EN+SP break damage actually comes from — still open

Ruled out by measurement:
* **Search budget** — 7 of 7 objective modes, 121 adaptive attempts, zero
  UNKNOWN, `break_search` 5,694s (Colab run 2).
* **Break-slice depth** — A37, attempts now run to 180s.
* **Concurrency clustering** — this experiment.
* **Shrinkage double-count** — the business confirms shrinkage is out-of-office
  only, so the measurement is correct.

Still candidates, in order of what the evidence supports:
1. **Break window rules** — spacing, edge margins and the permitted window per
   segment may force breaks onto covered intervals regardless of objective. The
   run recorded 82 break-spacing compressions.
2. **Skeleton break-compatibility** — the chosen skeleton may have thin
   simultaneous margins everywhere, so no placement is good. Cricut Voice
   absorbs 97% on the same engine, so this is scenario shape rather than engine
   capability.
3. **The selector** — it ranks on `after_target` first, so it is choosing among
   already-damaged candidates rather than preventing the damage.

The next diagnostic should be interval-level: for the intervals that lose
target to breaks, was any legal alternative placement available? That
distinguishes "the break rules forbid a better placement" from "the objective
did not look for one", and no further solver time is needed to answer it.
