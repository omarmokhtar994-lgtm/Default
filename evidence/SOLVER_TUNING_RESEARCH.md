# What CP-SAT offers that this engine never asked for

Researched 2026-09-19 against ortools 9.15.6755, the version actually installed.
Every parameter below was probed on the live library, not taken from docs.

## 1. The memory ceiling the engine never sets

`max_memory_in_mb` **defaults to 10000** and the engine sets it nowhere
(0 occurrences). The OOM that killed AE_AR_B2B at 3600s died at **7.76 GB**
resident while CP-SAT was still working toward its own 10 GB ceiling — the
solver was aiming above the limit that would kill it.

Caveat recorded rather than glossed: OR-Tools issue #1944 reports
`max_memory_in_mb` is not reliably enforced in all cases. This is a mitigation,
not a guarantee.

## 2. The gap stop, quantified on our own data

`relative_gap_limit` exists (default 0.0 = off). Measured on AE_FR_Choice:

```
objective 26,211,272   bound 26,211,120   gap 152   (0.00058% relative)
slice_utilisation 1.0  -- consumed the entire 45s slice
```

Because phase deadlines are cumulative, seconds returned here flow forward to
break search rather than being lost. This is a quality lever, not only a speed
one.

## 3. The finding with the largest potential effect: worker count thresholds

CP-SAT's subsolver portfolio is gated on worker count:

| workers | what you get |
|---|---|
| 1 | the default subsolver only |
| 2+ | incomplete subsolvers (LNS) appear |
| **5** | **a first-solution subsolver appears** |
| 8 / 16 | the counts CP-SAT is actually tuned for |
| 32 | all 15 full-problem subsolvers |

The shipped default is `max(1, min(8, os.cpu_count() or 4))`.

**On a 4-core machine that is 4 workers — one below the threshold where CP-SAT
adds the subsolver whose entire job is finding a feasible solution quickly.**
That is precisely the UNKNOWN symptom seen on AE_AR_B2B and AE_FR_B2B at 600s.
OR-Tools issue #3662 reports a model that could not be proven optimal below 5
workers and was solved instantly at or above it.

This is a hypothesis with a clear mechanism, not a measured result here. It is
testable directly: same workbook, same seed, 4 workers versus 8, count UNKNOWNs.

**It also qualifies every measurement in this review.** All deterministic work
used `--num-workers 1`, which is reproducible but has no LNS and no
first-solution subsolver. Those numbers are a lower bound on production
quality, and the budget curve may have a different shape at 8 workers.

## 4. Checked and not worth pursuing

* **Solution hints as a reliability fix.** Hints are soft: the solver follows
  them briefly then reverts. Per issue #3750, a time limit reached during
  presolve returns UNKNOWN even when the log states the hint is complete and
  feasible. Hints cannot guarantee a solution.
* **Top-level search parameters.** The CP-SAT primer warns that changing them
  perturbs the whole subsolver portfolio including LNS workers, and can produce
  a default subsolver incompatible with the model. Termination *limits* are
  exempt — they select no subsolver — which is why only limits are applied here.
* **Symmetry breaking.** Already settled in B-6: presolve installs a 137x24
  orbitope unaided.

## 5. Version-specific caution

OR-Tools issue #5025 reports a segfault on **9.15** — the version in use — when
solving with many cores. Any move to higher worker counts should watch for it.

## Applied

`tools/apply_solver_limits.py` adds `configure_solver_limits()` at all three
solver configuration sites, exposing both limits and recording what was applied
into the audit.

**Defaults are deliberately inert**: gap limit 0.0 (CP-SAT's own default, no
stop) and memory limit unset. Shipping this changes no schedule. Each value has
to be chosen and A/B'd before any default moves — the same discipline that
caught B-10, S9-2, S15-3 and the retracted reliability claim.
