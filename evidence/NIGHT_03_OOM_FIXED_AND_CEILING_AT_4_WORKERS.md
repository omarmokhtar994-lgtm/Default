# Overnight fact #3: the OOM is fixed, and 4 workers reach 100% coverage at half the budget

## The OOM is fixed, verified at the exact budget that crashed

`AE_AR_B2B` at **3600s** — the run the cgroup OOM killer terminated at
**7,758,648 kB** resident, producing no schedule and `independent_validation:
NOT_RUN`.

| | before | after joint-off default |
|---|---|---|
| peak RSS | **7760 MB (SIGKILL)** | **827 MB** |
| return code | -9 | **0** |
| schedule produced | none | valid, production eligible |

A 9.4x reduction at the shipped QUICK budget, and the crash class is closed.

## 4 workers reach the theoretical ceiling at 1800s

| run | budget | workers | before_target | after_target | after_floor | peak |
|---|---|---|---|---|---|---|
| AE_AR_B2B | 600 | 4 | 168 | 165 | 168 | 915 MB |
| **AE_AR_B2B** | **1800** | **4** | **168** | **168** | **168** | 1070 MB |
| AE_FR_B2B | 600 | 4 | 102 | 102 | 107 | 726 MB |
| **AE_FR_B2B** | **1800** | **4** | **112** | **112** | **112** | 934 MB |

Both 1800s runs are **at the ceiling**:

```
AE_AR_B2B  active_intervals 168  ->  after_target 168  =  100.0%
AE_FR_B2B  active_intervals 112  ->  after_target 112  =  100.0%
```

Every active interval covered at target, **before and after breaks**, with zero
break loss. No schedule can be better. `AE_AR_B2B` at 168/168 also **matches
the RC9.1 production baseline exactly**.

## What this does to the budget question

Compare the same case across worker counts:

| budget | 1 worker | 4 workers |
|---|---|---|
| 600s | 131 | **165** |
| 900s | 142 | — |
| 1800s | 165 | **168 (ceiling)** |
| 3600s | OOM-killed | — |

**600s at 4 workers matches 1800s at 1 worker.** Roughly 3x effective budget,
consistent with the earlier 300s@4w observation.

More importantly: **the 1-worker curve was still climbing at 1800s, which is
why I concluded long budgets were genuinely needed. At 4 workers the same case
is finished at 1800s.** That conclusion was an artifact of a crippled
configuration, and my retraction of the "budgets are oversized" claim now looks
like it was the wrong retraction.

Stated precisely and no further: **on these two workbooks, at 4 workers, QUICK's
3600s budget is at least 2x larger than needed.**

## What is NOT established

* **Two workbooks.** AE_AR_B2B and AE_FR_B2B both reach 100%, which may simply
  mean both are capacity-rich. Cases that are genuinely hard — Cricut_Chat
  (176/163), Cricut_Voice (246/224), NMG, GDI — have not been run at 4 workers
  and may still use the full budget.
* **No 3600s @ 4 workers run exists**, so "1800 is enough" is inferred from
  hitting the ceiling, not from a flat 1800-vs-3600 comparison. Hitting 100%
  is strong evidence since nothing can exceed it, but the budget default should
  not move on two cases.
* **Production worker count varies by host**: `max(1, min(8, cpu_count))`. These
  runs used 4 on a 4-core box. An 8-core host gets 8 workers and the curve may
  shift again.

## Next measurement that would settle the budget default

The hard cases at 4 workers, 1800s vs 3600s. If they also plateau, QUICK can
drop to 1800 with corpus backing rather than two data points.
