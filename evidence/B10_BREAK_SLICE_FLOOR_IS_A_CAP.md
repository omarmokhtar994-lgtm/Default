# B-10: the adaptive break search never runs, because a cap is used as a floor

What this file answers: why the 112-task adaptive break search completes zero
attempts on essentially every run — including the RC5 authors' own recorded
runs — and why the constant responsible is being read backwards.

---

## 1. The measurement

Every run records the truncation. `planned` is the size of the break-search
portfolio; `completed` is how many of those attempts actually ran:

| run | budget | planned | completed | proposed slice |
|---|---|---|---|---|
| `B3_FRC_DEFAULT45` | 900s | 112 | **0** | 151.0s |
| `B4_DIAG` | 900s | 112 | **0** | 114.7s |
| `B3_SLICE30` | 900s | 168 | **0** | 132.6s |
| `B3_ARB2B_DEFAULT45` | 900s | 84 | **0** | 117.3s |
| `B1_FULL` | 900s | 28 | 1 | 162.0s |
| `AE_AR_Choice` *(authors, 3600s)* | 3600s | 140 | **0** | 68.1s |
| `AE_IT_B2B` *(authors, 3600s)* | 3600s | 112 | 2 | 112.0s |
| `AE_FR_Choice` *(authors, 3600s)* | 3600s | 112 | 3 | 105.4s |

Every one stops for the same reason, and the audit says so plainly:

```
adaptive_search_v1.status           TRUNCATED_BY_GLOBAL_BUDGET
adaptive_search_v1.planned_task_count   112
adaptive_search_v1.attempted_task_count   1
```

Longer budgets do not fix it. The authors' 3600s runs truncate *harder* than
the 900s ones, because a longer run plans a larger portfolio, which divides the
window into smaller slices.

## 2. Where the window goes

`B3_FRC_DEFAULT45`, from the budget event log:

```
break_search window          471s → 700s   (229s allocated)
ADAPTIVE_BREAK_SEARCH_STOPPED_INSUFFICIENT_DEPTH at 549s
```

The search stopped at 549s with **151 seconds of its own phase still
unspent** — exactly the `proposed_slice_sec: 150.989` it rejected.

That time is not destroyed: phase deadlines are cumulative, so it passes to
`joint_refinement`, which then runs 549 → 787 instead of 700 → 802. But it has
been silently reallocated from a **112-task portfolio** (7 objective modes × 4
widths × 4 skeletons) to a **single narrower operator**. Nothing reports that
trade as having been made.

## 3. The constant is being read backwards

`BREAK_MIN_MEANINGFUL_SLICE_SEC = 180.0` is used as a **precondition to
attempt**:

```python
if slice_sec < BREAK_MIN_MEANINGFUL_SLICE_SEC:
    ...
    break          # abandons the whole portfolio
```

Its own recorded justification, verbatim from the source:

> ```
> 20s UNKNOWN | 60s UNKNOWN | 90s 160 | 120s 160 | 150s 160
> 180s 162    | 450s 162
> ```
> Feasibility appears between 60s and 90s and the result plateaus at 180s, so
> **180 is the point past which more time per attempt buys nothing** and the
> remaining budget is better spent on the next attempt.

That is an argument for a **ceiling** — *do not spend more than 180 on one
attempt*. It is being used as a **floor** — *do not attempt at all below 180*.

The same evidence puts the feasibility cliff at **90 seconds**. A 151-second
attempt is not a wasted attempt; by this curve it returns 160, and a
120-second one returns 160 as well.

Stage 1 gets this right and has both constants:

| | floor | cap |
|---|---|---|
| Stage 1 | `STAGE1_MIN_MEANINGFUL_SLICE_SEC` | `STAGE1_MAX_SLICE_SEC = 1800` |
| break search | `BREAK_MIN_MEANINGFUL_SLICE_SEC = 180` (used as floor) | **none** |

The break search has one constant, justified as a cap, doing the job of a
floor.

## 4. It is also B-3's defect a second time

`tools/break_slice_depth_probe.py`, which produced that curve:

```python
sol = E.solve_breaks(parsed, skeleton, width, False, slice_sec, 2, sys.stderr,
                     objective_mode="target_priority", random_seed=9000)
```

**No `hint_solution`. Cold.**

The adaptive loop:

```python
hint_solution = hints_by_fingerprint.get(fingerprint)
solution = solve_breaks(..., hint_solution=hint_solution, ...)
```

**Warm**, wherever a prior break solution exists for that skeleton — which,
after the early incumbent sweep, is most of them. Exactly the mismatch B-3 was:
a floor measured cold, applied to warm-started solves.

The difference from B-3 is that **no new measurement is needed to act**. B-3
required a warm curve because the cold curve said 45s was infeasible. Here the
recorded *cold* curve already shows feasibility at 90s and full quality at 150s;
warm can only be better.

## 5. Interaction with B-3 — my fix made this worse

B-3 increased the number of Stage-1 skeletons that survive, which increases the
break portfolio, which shrinks the per-attempt slice:

| | planned break tasks | completed |
|---|---|---|
| `B1_FULL` (floor 240, pre-B-3) | 28 | 1 |
| `B3_FRC_DEFAULT45` (floor 45, post-B-3) | 112 | **0** |

B-3 still produced the better schedule (112/109 against 105/101), so this is
not a regression in outcome. But it is a real interaction, and it means the
value of fixing B-10 has gone **up** since B-3 landed, not down.

## 6. Proposed fix

Split the constant, mirroring Stage 1:

* `BREAK_MIN_MEANINGFUL_SLICE_SEC` → **90–120** — the measured cliff (60–90)
  plus margin, the same method that set Stage 1's floor.
* `BREAK_MAX_SLICE_SEC = 180` → the cap the evidence actually supports.

Then A/B on an easy and a hard workbook. The B-4 lesson applies: run-to-run
variance on these quantities is ±1 interval, so one run per arm cannot decide
it.

## 7. What is not claimed

* **No coverage number is promised.** The portfolio being skipped is 112
  attempts the engine planned and did not make; whether making them improves a
  schedule is what the A/B is for.
* **The time is not being wasted outright.** It flows to joint refinement. The
  defect is that a broad portfolio search is silently traded for a narrow
  operator, on a rule that misreads its own evidence.
* **Not measured while the sweep runs.** Both are solver work and concurrent
  solves on one container is what produced a false finding earlier in this work.

---

## Appendix: two smaller things found in the same pass

**The Stage-1 retention cap is not binding.** `MAX_RETAINED_STAGE1_SKELETONS =
16`; observed retention across eleven runs is 1–7, `CAP_NOT_REACHED` every
time. Not a constraint today, including after B-3.

**`deterministic_target_baseline` has a fixed 60-second floor** that overrides
the budget-derived value: `min(420, max(60, min(total*0.05, remaining*0.18)))`.
At a 900s budget the budget-derived share is 45s and it takes 60s — the same
"floor beats budget" shape, 15 seconds' worth. Minor, recorded for completeness.
