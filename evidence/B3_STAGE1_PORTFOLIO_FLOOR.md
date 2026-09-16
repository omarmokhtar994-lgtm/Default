# B-3: the Stage-1 portfolio refuses to start a profile it could finish

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

## 2. Why the floor fires when it should not

`STAGE1_MIN_MEANINGFUL_SLICE_SEC = 240.0` is evidence-based, and its evidence
is sound — it is recorded in the constant's own comment. On **AE AR B2B, the
hardest packaged scenario**, the same profile and seed returns UNKNOWN at 45s
and at 150s, and 166 of 168 before-break target intervals at 210s. The
feasibility cliff sits between 150s and 210s, so 240 clears it with margin.

The defect is that a floor calibrated on the hardest workbook is applied as a
**universal** precondition for attempting anything at all. On `AE_FR_Choice`:

```
STAGE1 target_locked_protected_tier_polish status=OPTIMAL elapsed=13.40s
```

Thirteen seconds to optimality. The run had **171 seconds** and spent **zero**,
because 171 < 240.

The helper's own docstring anticipates the easy case — *"A profile that solves
fast returns long before its slice expires (NMG SP proves OPTIMAL in 0.2s), so
an easy scenario still explores everything"* — but that reasoning only holds
once a profile is **allowed to start**. The guard above decides before any
profile runs, so an easy scenario with 171 seconds explores nothing.

## 3. What it costs — measured

Same workbook, same seed, same 900s budget, same engine. The only difference is
the Stage-1 floor, stated from the workbook via the B-7 route (no code
difference between the two runs):

| | floor 240 (default) | floor 30 (workbook) |
|---|---|---|
| portfolio profiles attempted | **0 of 15** | **5 of 15** |
| Stage-1 solves / seconds | 3 / 67s | 8 / 214s |
| Stage-2 attempts / seconds | 16 / 760s | 19 / 601s |
| **before_target** | 105 | **112** (+7) |
| **after_target** | 101 | **109** (+8) |
| before / after floor | 112 / 110 | **112 / 112** |
| **floor gaps** | 2 | **0** |
| runner return code | 0 | 0 |
| independent validation | PASS | PASS |
| metric parity | PASS | PASS |

Eight more intervals at target and the floor gaps eliminated, from spending 147
more seconds in Stage 1 and 159 fewer in Stage 2. Stage 2 also ran *more*
attempts (19 vs 16) on the smaller budget, because it was working from better
skeletons.

`112` is exactly what the `BEFORE_BREAKS_ONLY` run reaches, so the +7 is not a
lucky draw — it is the skeleton quality that was always available and never
generated.

**This also shrinks B-4.** `target_losses_from_breaks` was 6 in the baseline;
at 112 → 109 it is 3. Part of what looked like break-placement loss was break
placement doing its best from a skeleton worth 105.

## 4. What has and has not been changed

**Changed:** `STAGE1_MIN_MEANINGFUL_SLICE_SEC` is now reachable — as the
workbook row `Stage 1 Minimum Slice Seconds` and the flag
`--stage1-minimum-slice-sec`, through the same precedence B-7 established
(explicit command line > workbook > engine default). `stage1_slice_seconds` and
`stage1_fundable_profile_count` take the floor as a parameter and keep every
guarantee they made, at any value.

**Not changed: the default is still 240.** The A/B above is one workbook, and
it is an *easy* one. The constant was calibrated on the hardest scenario
precisely because a short slice there returns no skeleton at all — and on that
workbook the time would be taken from a Stage 2 that used all of it. Lowering
the default on this evidence alone would be the mistake this file exists to
avoid.

The outstanding measurement is `AE_AR_B2B` at the same 900s budget, floor 240
versus floor 30. Its baseline shows the identical shape —

```
STAGE1_PORTFOLIO window=168s runnable=15 funds=0 at 240s minimum depth
STAGE1_PORTFOLIO_TRUNCATED attempted=0 of 15 runnable
```

— so the hard workbook also attempts zero profiles at this budget, which means
the floor is not currently protecting it from anything. Whether a 168-second
slice helps or wastes time there is the open question, and it decides the
default.

## 5. The likely shape of the fix

Not "lower the constant". The floor is right about *depth*; it is wrong about
using depth as a precondition for *attempting*. The narrow rule that follows
from the evidence is: **when the portfolio would otherwise attempt zero
profiles, spend the remaining window on one.** Zero is categorically different
from fewer — it means Stage 2 selects only from bootstrap artifacts — and the
cost is bounded to a single slice. That rule will be measured on both
workbooks before it becomes the default, not asserted.

## 6. What is *not* claimed

* **No default changed.** A workbook with no `Stage 1 Minimum Slice Seconds`
  row behaves exactly as before; the contract hash is unchanged on all 14
  workbooks available.
* **One workbook is not a result.** The +8 is `AE_FR_Choice` at 900s QUICK,
  seed 9000, two workers. It is a real measurement on a real roster, and it is
  one point.
* **B-5 is not resolved.** It is decoupled from B-3, which is the only claim
  this file makes about it.
