# B-3: a slice floor measured cold, applied to warm-started solves

What this file answers: why a 900-second `FULL_SCHEDULE` run attempts **zero**
of its fifteen Stage-1 profiles, what that costs, and a correction to my own
earlier diagnosis.

Engine lineage: RC5 + P-1 + C-1 + capacity gate + stage-aware gates + workbook
search controls (B-7) + this measurement.

---

## 1. A correction to what I said before

I previously reported B-3 as *"Stage 1 starved by the budget split"* and named
B-5 — the 77-term weighted sum spanning 800,000,000 : 1 — as its root cause.

**The measurement does not support that.** On `AE_FR_Choice` at 900s:

| | |
|---|---|
| Stage-1 allocation in the budget plan | 405s |
| Stage-1 window left when the portfolio starts | 171s |
| Stage-1 **solver** seconds actually used | **67s** (3 solves, one a repair) |
| Stage-2 solver seconds | **760s** (16 attempts) |

The abandoned Stage-1 window is **not discarded** — phase deadlines are
absolute offsets, so time Stage 1 does not spend flows forward and Stage 2
consumes it. Stage 2 received 760 seconds. It was not starved of time; it was
given a worse skeleton to polish.

The objective's dynamic range is not what stops the portfolio. A single line
does:

```python
remaining = stage1_profile_deadline - time.time()
if remaining < STAGE1_MIN_MEANINGFUL_SLICE_SEC:   # 171 < 240
    break                                          # 0 of 15 attempted
```

B-5 may still be worth addressing on its own merits. It is not the cause of
B-3, and I should not have asserted the chain before measuring it.

## 2. The root cause: a constant measured cold, applied warm

`STAGE1_MIN_MEANINGFUL_SLICE_SEC = 240.0` is evidence-based, and the evidence
is recorded in the constant's own comment: on **AE AR B2B, the hardest packaged
scenario**, the same profile and seed returns UNKNOWN at 45s and at 150s, and
166 of 168 before-break target intervals at 210s.

That measurement was taken by `tools/stage1_slice_depth_probe.py`, which calls:

```python
solution = E.build_skeleton(parsed, profile, hard, slice_sec, 2, sys.stderr, random_seed=0)
```

**No `hint_skeleton`. A cold start.**

The Stage-1 portfolio loop never solves cold:

```python
solution = build_skeleton(
    parsed, profile, base_hard, slice_sec, workers, log,
    random_seed=solver_random_seed,
    hint_skeleton=select_stage1_hint_skeleton(parsed, successful_skeletons),
    ...)
```

By the time the portfolio runs, the hard-feasibility probe and the
deterministic baseline have both produced feasible skeletons, and **every
profile is warm-started from them**. The floor was calibrated on a scenario the
loop never creates.

The probe now supports a `warm` mode that rebuilds the anchor the run itself
holds. Same workbook, same profile, same seed:

| slice | COLD (set the constant) | **WARM (what the loop does)** |
|---|---|---|
| 15s | — | UNKNOWN |
| 30s | — | **FEASIBLE 168/168** |
| 45s | **UNKNOWN** | **FEASIBLE 168/168** |
| 60s | — | **FEASIBLE 168/168** |
| 120s | — | FEASIBLE 168/168 |
| 150s | **UNKNOWN** | — |
| 210s | **166/168** | — |
| 240s | — | FEASIBLE 168/168 |

The cliff moves from 150–210s to 15–30s — an order of magnitude — and warm
quality saturates immediately at **168 of 168**, which is RC9.1's recorded best
and better than anything the cold curve reached.

This is the whole of B-3. The engine was refusing a 171-second window for a
solve that needed 30, on the strength of a number measured under conditions
that never occur.

## 3. The new default, and how it was chosen

`STAGE1_MIN_MEANINGFUL_SLICE_SEC = 45.0`, by the same method that chose 240:
clear the measured cliff with margin. The warm cliff is between 15s and 30s, so
45s clears it by 50% and is itself measured FEASIBLE at full quality.

The constant is also reachable now — workbook row `Stage 1 Minimum Slice
Seconds`, flag `--stage1-minimum-slice-sec` — under the B-7 precedence, so it
can be re-tuned per roster without a code change.

## 4. What it costs — measured end to end

Same workbook, same seed, same 900s budget, shipped default versus shipped
default:

**AE_FR_Choice**

| | floor 240 | **floor 45** |
|---|---|---|
| portfolio profiles attempted | 0 of 15 | **3 of 15** |
| before_target | 105 | **112** (+7) |
| after_target | 101 | **109** (+8) |
| before / after floor | 112 / 110 | **112 / 112** |
| floor gaps | 2 | **0** |
| return code | 0 | 0 |

**AE_AR_B2B** — the workbook 240 was calibrated on

| | floor 240 | **floor 45** |
|---|---|---|
| portfolio profiles attempted | 0 of 15 | **3 of 15** |
| before_target | 166 | **168** (+2, the maximum) |
| after_target | 161 | **164** (+3) |
| before / after floor | 168 / 167 | **168 / 168** |
| floor gaps | 1 | **0** |
| return code | 4 | **0** |

The feared risk did not materialise. Every 45-second warm slice on the hard
workbook returned FEASIBLE, not UNKNOWN, and the hard workbook gained more in
return code terms than the easy one: it now reaches its maximum before-break
coverage and closes its last floor gap.

`112` and `168` are exactly what the `BEFORE_BREAKS_ONLY` runs reach, so these
are not lucky draws — they are the skeleton quality that was always available
and never generated.

**One honest caveat.** An exploratory run at floor 30 reached `after_target`
167 on AE_AR_B2B, above the 164 the shipped 45 reached. Both beat the baseline
161. A single point either way is inside the run-to-run variation of a
wall-clock-budgeted search, and I am not claiming 30 is better than 45 on that
basis — but it is recorded rather than dropped, and it is a reason to re-tune
per roster with the workbook control rather than treat 45 as settled.

**This also shrinks B-4.** On AE_FR_Choice `target_losses_from_breaks` falls
from 6 to 3: part of what looked like break-placement loss was break placement
doing its best from a skeleton worth 105.

## 5. A defect found along the way

The AE_AR_B2B baseline failed its gate with `rc 4 / FAIL_METRIC_PARITY` — one
field, `week_boundary_imbalance_violation_count`, engine 1 versus validator 0,
with the other 40 agreeing. That turned out to be a defect in the independent
validator, not in the schedule: it measured next-Sunday adjacency between whole
intervals while the solver constrains adjacent quarter slots. Recorded and
fixed separately as B-8 (`evidence/B8_NEXT_SUNDAY_ADJACENCY_GRANULARITY.md`);
it is why the floor-45 AE_AR_B2B run returns 0 where its baseline returned 4.

## 6. What is *not* claimed

* **Two workbooks at one budget is not a full regression sweep.** Both are real
  rosters measured end to end through the whole runner, and both improve on
  every coverage measure. They are two points, at QUICK/900s, seed 9000, two
  workers. The other five packaged scenarios have not been re-run at the new
  default.
* **The gain is budget-dependent by construction.** At DEEP the Stage-1 window
  clears 240s anyway, so this changes little there. It matters most at the
  shorter budgets, which is where the defect was doing its damage.
* **B-5 is not resolved.** The 77-term weighted sum spanning 800,000,000 : 1 is
  still there. It is simply not the cause of B-3, which is the only claim this
  file makes about it.
* **No contract changed.** The canonical contract hash is unchanged on all 14
  workbooks; this is a search-budget constant, not a coverage rule.
