# Why Cricut Chat gets WORSE with more workers: Stage-1 is blind to breaks

## The observation

| workers | before_target | after_target |
|---|---|---|
| 1 | 176 | **163** |
| 2 | 195 (pool best) | 159 |
| 4 | **194** (pool best) | **159** |

More workers produce a *better* skeleton and a *worse* schedule.

## It is not solver noise, and not a selection bug

At 4 workers the Stage-1 search works dramatically better. Conflicts per
profile, 1 worker versus 4:

```
1 worker :  5,  0, 36, 16, 24, 12, 28,  0,  0      branches/conflict up to 73,797
4 workers: 201739, 239871, 278517, 252102, 282040, 438456, 216020, 416175
                                                   branches/conflict 1.4 - 7.1
```

Four workers learn ~10,000x more conflicts and stop enumerating. The search is
functioning as intended.

## The actual mechanism

The 4-worker candidate pool:

| skeleton profile | before_target | after_target | lost to breaks |
|---|---|---|---|
| `target_floor_pareto_master` | **194** | 130 | **-64** |
| `target90_restore_champion` | 193 | 134 | -59 |
| `release_gate_floor_satisfaction` | 190 | 132 | -58 |
| `floor_gate_hunter_before` | 187 | 129 | -58 |
| `hard_feasibility_probe` | **169** | **159** | **-10** | <- SELECTED |

**The selector is correct.** It ranks on `after_target`, and 159 beats 134, 132,
130 and 129. It picked the best available final schedule.

The problem is upstream: **every high-coverage skeleton loses roughly 60
intervals to break placement, while the weak one loses 10.** Stage-1 packs
coverage so tightly that no legal break placement survives.

At 1 worker the search was too weak to find those tightly-packed skeletons, so
it never generated the trap. Better search walks straight into it.

## What this means

**Stage-1 optimises before-break coverage with no model of break
compatibility.** A skeleton that scores better on Stage-1's objective can be
strictly worse as a finished schedule. Improving Stage-1 search quality
therefore does not reliably improve the product, and on this workbook it makes
it worse.

This is the same effect recorded elsewhere as the "breakability trade-off"
(A34: `target loss 10/168 = 6.0% from break placement`) and as Gate 5
"rewards a worse skeleton" -- seen here as a mechanism rather than a symptom.

It also raises the stakes on joint refinement. That phase exists to optimise
shifts and breaks *together*, which is precisely the gap demonstrated above --
and it has now been measured at **69 attempts across 7 workbooks with zero
improvements**. The one component designed to close this gap does not work.

## Scope

One workbook, one run per worker count. The mechanism is visible directly in
the candidate pool rather than inferred, but the size of the effect on other
workbooks is unmeasured. AE_AR_B2B and AE_FR_B2B reach 100% at 4 workers, so
they show no such trap -- consistent with break-compatibility only binding when
coverage is tight relative to capacity.

## Cheap next test

Feed the 194-coverage skeleton to `solve_breaks` with `min_target_hits` swept
downward, the way B-4 established its headroom. That separates "breaks cannot
be placed on this skeleton" from "the break search did not find the placement",
and the answer decides whether the fix belongs in Stage-1's objective or in
Stage-2's search.
