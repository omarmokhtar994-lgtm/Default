# The 5-worker threshold, measured on the installed solver

Probed directly against ortools **9.15.6755** by enabling `log_search_progress`
in an isolated harness and reading back which subsolvers CP-SAT actually
instantiates. Not taken from documentation.

| workers | full problem | **first solution** | interleaved | first-solution subsolvers |
|---|---|---|---|---|
| 1 | 0 | 0 | 0 | — |
| 2 | 0 | 0 | 9 | — |
| 3 | 2 | 0 | 9 | — |
| **4** | 3 | **0** | 9 | **none** |
| **5** | 3 | **2** | 9 | `fj`, `fs_random_no_lp` |
| 6 | 4 | 2 | 9 | `fj`, `fs_random_no_lp` |
| 8 | 6 | 2 | 9 | `fj`, `fs_random_no_lp` |
| 16 | 11 | 5 | 11 | `fj(2)`, `fs_random`, `fs_random_no_lp` |

**The discontinuity is exactly at 5**, as documented, and it is confirmed on the
version actually in use rather than assumed.

`fj` is Feasibility Jump — a local-search heuristic whose specific job is
finding a feasible solution quickly. Below 5 workers it is not in the portfolio
at all.

## Why this matters here

The shipped default is `max(1, min(8, os.cpu_count() or 4))`.

On a 4-core host that resolves to **4 workers — one below the threshold**. The
engine therefore runs with zero first-solution subsolvers on any 4-core machine,
which is the exact shape of the `UNKNOWN` results seen on AE_AR_B2B and
AE_FR_B2B: the solve found no feasible solution at all inside its slice.

## What is proven and what is not

**Proven:** the portfolio threshold, on this version, at 5.

**Not yet proven:** that crossing it changes this engine's output. The
end-to-end test is running — AE_AR_B2B and AE_FR_B2B, workers 4 / 5 / 8, seeds
9000-9002, 300s, **strictly sequential** because the box has 4 cores and the
worker count is the variable under test. Primary metric is the binary
`stage2 == UNKNOWN`, which is more robust than coverage counts.

**Limitation stated up front:** on a 4-core box, 5 and 8 workers oversubscribe.
That is a genuine confound for any *quality* comparison — each worker gets a
fraction of a core. It is much weaker for the UNKNOWN question, because
Feasibility Jump is cheap and finding a first solution is not throughput-bound.
So this test can credibly answer "does crossing the threshold stop the UNKNOWNs"
but **cannot** measure the full production quality effect. That needs an 8+ core
host.

## Caveat on every measurement in this review

All deterministic work used `--num-workers 1`, which has **no** first-solution
subsolvers, **no** LNS, and a single default subsolver. Those numbers remain
valid as a reproducible A/B instrument — the comparison was always like for
like — but they are a **lower bound** on production quality, and the budget
curve may have a different shape at 8 workers.

## Related version caution

OR-Tools issue #5025 reports a segfault on 9.15, the version in use, when
solving with many cores. Worth watching if worker counts are raised.
