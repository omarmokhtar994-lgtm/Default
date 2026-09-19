# Budget plateau sweep, and an OOM kill at the production default

16 runs, 4 cases x 4 budgets, `--num-workers 1`, seed 9000, deterministic.
Batched **by budget**, 4 runs per batch on a 4-core box, so every run inside a
comparison faced identical CPU load. Mixing budgets in a batch would have let
short runs finish early and hand their cores to long ones, manufacturing the
"longer budget is better" result the experiment exists to test.

## Results

| case | 600s | 900s | 1800s | 3600s |
|---|---|---|---|---|
| AE_AR_B2B | 131 | 142 | **165** | **OOM-KILLED** |
| AE_IT_B2B | 69 | 69 | 71 | 66 † |
| AE_FR_B2B | 93 | 110 | **112** (perfect) | 112 † |
| AE_FR_Choice | 110 | **108** | 110 | 110 † |

*(after_target; † contaminated — see below)*

## The 3600s row is not usable

`AE_AR_B2B` at 3600s was killed by the cgroup OOM killer:

```
Memory cgroup out of memory: Killed process 881 (python3)
  total-vm:8134756kB, anon-rss:7758648kB
  constraint=CONSTRAINT_MEMCG
```

**7.76 GB resident in a single process**, and `return_code: -9`, no schedule
produced, `independent_validation: NOT_RUN`.

The other three 3600s runs survived but all three overran their budget by
**247s** (3847 vs 3600), against roughly +30-50s at every other budget. That is
consistent with memory pressure on the whole batch. So the entire 3600s row is
confounded and **no conclusion may be drawn from it** — including AE_IT_B2B's
apparent 71 -> 66 regression, which is as likely to be memory pressure as a
search defect. It must be re-run one case at a time before it means anything.

## The OOM itself is a real defect, independent of this harness

Peak RSS scales with budget: the same workbook completes at 1800s and dies at
3600s. 3600s is the **shipped QUICK default**. Even run one at a time, 7.8 GB is
a large footprint, and it would fail outright on a smaller machine.

Plausible mechanism, not yet confirmed: the engine builds a fresh `CpModel` per
profile and per break attempt (8,732 variables / 67,628 constraints on this
workbook). If those models, or the solutions derived from them, are retained by
the candidate pool or the audit structure, memory grows linearly with the number
of attempts — and attempt count grows with budget. That arithmetic fits 7.8 GB.
Confirming it needs a memory profile, not a guess.

## What survives from the clean batches (600 / 900 / 1800)

**The long budgets are genuinely used on the hard case.** AE_AR_B2B climbs
131 -> 142 -> 165. My earlier claim that the budgets are oversized by 5-8x,
inferred from the stale 240s-slice arithmetic, is **not supported**.

**AE_FR_B2B plateaus at 1800s** at 112/112 — a perfect schedule, zero break
loss. For that case 3600s buys nothing.

**A real monotonicity violation at 900s.** AE_FR_Choice: 110 -> 108 -> 110. The
selector is not at fault — it picks the pool's best every time (600s pool best
110, selected 110; 900s pool best 108, selected 108). The 900s search simply
never generated a 110. Because phase deadlines are absolute offsets, a different
budget produces a *different* search, not a *longer* one. Nothing is lost or
mis-ranked; the search is not nested.

Also of note: Stage-1 profiles attempted go 1 -> 3 -> 9/10 across 600/900/1800,
so even at 1800s a third of the portfolio never runs.

## Solver telemetry: applied, gated, verified

`tools/apply_solver_telemetry.py` applied to the release tree. Gate **PASS,
20 suites**. End-to-end run confirms the data reaches the audit JSON.

It earned its keep on the first run. A Stage-1 solve on AE_FR_Choice:

```
objective_value        26211272.0
best_objective_bound   26211120.0
absolute_gap                152.0      <- 0.00058% relative
wall_time_sec            45.004
slice_utilisation         1.0          <- used its ENTIRE slice
```

The solve was within **0.00058%** of proven optimal and then spent the rest of
its 45-second slice. By contrast `hard_feasibility_probe` shows
`slice_utilisation: 0.083` — it stopped at 8.3% of its slice because it proved
OPTIMAL, so early exit already works when optimality is *proven*.

That is the bound-based early-exit lever, quantified: a relative-gap stop rule
would return roughly 40 of those 45 seconds with no measurable quality cost.
Before this change the gap was not recorded at all, and on UNKNOWN the bound was
written as None.
