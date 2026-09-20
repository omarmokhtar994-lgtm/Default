# Stage-2: is the objective wrong, or is the search wrong?

NIGHT_06's correction established that `after_target 159` is *reachable* on
the tightly-packed Cricut Chat skeleton that production delivered at **130**
-- at least 29 target intervals left unclaimed. Reachability alone does not
name the defect, and the two candidates need opposite fixes:

| verdict | meaning | fix belongs in |
|---|---|---|
| `obj(159) > obj(130)` | the model is minimising correctly; 130 really is its optimum | the **weights** |
| `obj(159) < obj(130)` | 159 is better under the engine's own objective and the search never reached it | the **search** |

## Why the two objective values are comparable

`min_target_hits` only **adds a constraint**
(`l632_universal_scheduler.py:7800-7801`); the objective is assembled from the
identical `objective_terms` list and minimised at `:7823`. Same function,
different feasible region -- so the objective values can be compared directly.

## Arithmetic: is the weighting story even possible?

Weights for `target_priority` (read from engine source, not retyped) and
structure measured from the Cricut Chat workbook:

| quantity | value |
|---|---|
| `target_miss` | 12,000,000 |
| `floor_miss` | 2,500,000 |
| `quality_global_gap` | 3,000,000 |
| `quality_run_gap` | 2,500,000 |
| `quality_daily_gap` | 1,000,000 |
| active floor intervals | 242 |
| `maximum_consecutive_floor_gaps` | 3 -> run window length **4** |
| run windows | **224** |

```
29 target intervals                         348,000,000
quality_run_gap pool (224 windows)          560,000,000
quality_global_gap pool (242 intervals)     726,000,000
floor_miss pool (242 intervals)             605,000,000
```

The pools are large enough, so "the objective honestly prefers 130" is **not**
absurd: 140 of 224 run-gap windows would cover the 348M.

## But the exchange rate makes it implausible

`all_gap` is forced to 1 **only when every interval in its 4-wide window is
missed** (`model.Add(sum(vars_window) + all_gap >= 1)`, minimised). Tripping
140 windows therefore requires roughly 143 *consecutive* floor misses -- which
on its own also costs ~357M in `floor_miss`. Charging 348M through the quality
terms cannot be done cheaply; it drags a comparable `floor_miss` bill with it.

So for the weighting verdict to hold, moving `after_target` 130 -> 159 must
cost on the order of **140 floor intervals** -- an exchange rate of 1 target
interval per 4.8 floor intervals. Target and floor are thresholds on the *same*
coverage counts, so they normally move together, not against each other at
5:1.

**Pre-registered prediction: SEARCH DEFECT** (`obj(159) < obj(130)`). Recorded
before running the probe.

## Result

_pending -- probe is `scratchpad/stage2_decisive.py`, runs once the
deterministic regression check releases the cores._
