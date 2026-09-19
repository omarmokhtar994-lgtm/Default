# Where the 8 GB goes — and why the CP-SAT memory limit may not help

Single AE_AR_B2B run, 1800s budget, `--num-workers 1`, RSS sampled every 10s
with the machine otherwise idle.

## Peak: 8,244 MB on ONE run

**This corrects my earlier reading.** I suggested the 3600s OOM was driven by
running four cases concurrently. It was not: a *single* run reaches 8.2 GB.
Two independent sources agree — this sampler, and the kernel's own OOM message
from the sweep, which recorded `anon-rss:7758648kB` for one process.

## The curve has two distinct growth regions

| window | RSS | phase(s) owning it |
|---|---|---|
| t=711 → 1312 | 793 → 795 MB (flat) | `stage1_search`, `break_search` |
| t=1412 → 1712 | 1360 → 3968 MB | **`joint_refinement`** (1394–1635), `coordinated_repair` |
| **t=1712 → 1812** | **3968 → 8244 MB** | **`target_lock_recovery` (1710–1737) + `finalization` (1737–1800)** |

Phase boundaries are from the run's own `global_budget`:

```
stage1_search        810s  deadline 941
break_search         453s  deadline 1394
joint_refinement     241s  deadline 1635
coordinated_repair    48s  deadline 1683
post_break_repair     27s  deadline 1710
target_lock_recovery  27s  deadline 1737
finalization          63s  deadline 1800
```

The solver phases are flat. **Memory more than doubles in the final ~100
seconds**, after the search is over.

## The consequence for the fix already applied

`max_memory_in_mb` bounds **CP-SAT**. If the bulk of this growth is in Python
during `finalization` — writing six output workbooks, running the independent
validator, computing the canonical metric surface while candidate schedules are
still held — then **the solver memory limit will not prevent this OOM.**

That does not make the limit wrong: CP-SAT's 10,000 MB default genuinely
exceeds container budgets and joint_refinement does add ~2.3 GB. But it is a
partial mitigation at best, and it must not be reported as the fix for the OOM
until the finalization growth is attributed.

Earlier I measured workbook I/O at 0.77s load / 0.46s save for a 54-sheet,
51k-cell workbook, and concluded I/O was not a runtime bottleneck. That remains
true for *time*. It says nothing about peak *memory* when several candidate
workbooks are materialised at once.

## What this does not yet establish

Sampling is 10-second granularity, so the final figure could include a
transient peak during workbook serialisation rather than a sustained
allocation. Attributing the last 4.3 GB needs `tracemalloc` around
finalization, not a sampler.

Not run now: the 4-vs-5-vs-8 worker test currently owns the machine, and
memory profiling would contend with it.

## Ranking

The finalization region is the larger contributor (4.3 GB vs 2.3 GB) and is
plain Python, so it should be both easier to fix and higher value than anything
in the solver.
