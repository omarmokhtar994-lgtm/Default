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

---

# CORRECTION: the skeleton is NOT the blocker. Stage-2 is.

The conclusion above -- that Stage-1 packs coverage too tightly for breaks to
fit -- is **wrong**, and the B-4-style probe disproves it.

## The probe

Rebuilt `target_floor_pareto_master` on Cricut Chat (4 workers, 180s), giving
`before_target 193 / before_floor 238` -- the same tightly-packed skeleton whose
run delivered `after_target 130`. Then asked `solve_breaks` directly whether
higher after-break coverage is reachable on it:

| `min_target_hits` | status | time |
|---|---|---|
| **159** | **FEASIBLE** | 121s |
| 145 | FEASIBLE | 121s |
| 130 | FEASIBLE | 121s |

**159 is achievable on this skeleton.** The production run delivered **130**.

So the high-coverage skeleton can hold its breaks at least as well as the weak
skeleton did (169 -> 159). It was never break-incompatible. **Stage-2's break
search left at least 29 target intervals unclaimed.**

## What this changes

The routing decision flips:

* **NOT** Stage-1's objective. The skeleton is fine; teaching Stage-1 about
  break compatibility would be solving a problem that does not exist.
* **Stage-2's break search** is the defect. Given a demanding skeleton it
  settles far below what is provably reachable.

The earlier reasoning confused *"the selected candidate had a big before/after
drop"* with *"that drop was forced"*. It was not forced. The selector picked
the 169-skeleton because it scored best **as produced**, not because the
194-skeleton was incapable.

## Honest limit on the probe

`min_target_hits` is a hard constraint, so it converts optimisation into
feasibility and steers the solver. Production Stage-2 runs unguided. This
proves **a placement exists at 159**; it does not prove an unguided search
should have found it in its slice. The gap is nonetheless 29+ intervals with
45s+ slices available, which is large.

## Where this leaves the ranking

This makes Stage-2 break search the top engineering item, ahead of anything in
Stage-1. It also re-frames B-4, which found the same shape on AE_FR_Choice --
break placement giving up coverage it had room to keep, proven by exactly this
method. B-4 measured 1-2 intervals there. Here it is at least 29.

Joint refinement remains relevant but demoted: the phase exists to co-optimise
shifts and breaks, and the evidence now says breaks alone have the headroom.


---

# ANNOTATION (later): the `min_target_hits` probe above is weaker than stated

The "159 FEASIBLE" table proves `sum(target_hit_vars) >= 159` is satisfiable.
It does **not** prove `after_target >= 159`, because the model counter and the
`after_target` metric use different arithmetic -- integer `ceil_units`
thresholds versus a percentage compare (see NIGHT_08, "Open defect"). A later
run locked at 159 reported `after_target` 157, reproducing the gap.

The conclusion of the CORRECTION section is nevertheless **upheld**, on
evidence that does not use `min_target_hits` at all:

* an unguided `solve_breaks` on the same tightly-packed skeleton reached
  `after_target` **163** in 121s, against the 130 production recorded;
* at 3600s the same skeleton yielded **137** through the coverage-blind
  diagnostic fallback and **164** through a real 180s break solve.

Stage-2 is the defect, and NIGHT_09 names the mechanism: at the production
QUICK budget the break search runs zero of its planned attempts.


---

# ANNOTATION WITHDRAWN: the probe above is sound after all

The annotation immediately above said the `min_target_hits` probe proved less
than claimed. That was wrong, and the measurement is in NIGHT_08: across all
242 demanded intervals the model's `target_hit` threshold is stricter than the
`after_target` metric on 242 and looser on 0. A lock at 159 forces the metric
to 159.

The "159 FEASIBLE" table therefore means what it originally said. The
CORRECTION section's conclusion -- Stage-2, not Stage-1 -- was already upheld
on independent evidence; it is now also upheld on its original evidence.
