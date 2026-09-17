# B-4, B-5, B-6 — measured, and two of the three were not what I called them

What this file answers: for each of the three remaining open items, is there a
defect, how big is it, and what is the evidence. Two of the three turned out to
be mischaracterised in my own earlier reports, and those corrections are the
main content here.

Engine lineage: RC5 + P-1 + C-1 + capacity gate + stage-aware gates + workbook
search controls + warm slice floor.

---

## B-4 — a real defect, with the headroom proved exactly

### The claim, re-measured after B-3

Before B-3, AE_FR_Choice lost 6 target intervals to break placement. After
B-3 it loses **3**, from a skeleton worth 112. The engine says the roster has
room:

```
break_capacity_headcount.status      BREAK_CAPACITY_SUFFICIENT
break_capacity_deficit               0
estimated_additional_headcount        0
headline   "Headcount is not the constraint: 408 lossless slots exist
            for 280 break-quarters."
```

Aggregate room is not a placement, so that headline is not proof. The proof
needs CP-SAT.

### The probe

`load_seed_skeleton` reconstructs the exact exported skeleton from the run's
own before-break workbook. The reconstruction is faithful — 112 target, 112
floor, 112 active, identical to the run. Then `solve_breaks` is asked for a
placement holding every interval:

| `min_target_hits` | meaning | result |
|---|---|---|
| **112** | lose nothing | **INFEASIBLE in 1.6s** |
| **111** | lose one | **FEASIBLE**, hard-clean, 0 no-break exceptions, after_floor 112 |

INFEASIBLE at 112 is a *proof*, returned in under two seconds, not a timeout:
zero loss is impossible on this skeleton. FEASIBLE at 111 is a *witness*: one
loss is achievable, hard-clean, with no exceptions.

**The provable minimum is 1. The engine shipped 3.**

### How much is really on the table — a correction from a second run

A repeat of that exact configuration (same workbook, same seed 9000, same 900s,
byte-identical budget plan, same 3 Stage-1 profiles attempted) returned
`after_target` **110**, not 109 — two losses rather than three.

These runs are budgeted by wall clock, so how much search completes moves with
machine load. The two runs differ only in `after_target` (109 vs 110) and two
overage metrics; `before_target`, `before_floor`, `after_floor` and
`floor_gaps` are identical, and so is every phase allocation.

So the honest figure is **1 to 2 intervals of headroom, not a firm 2**: the
proven floor is 1 loss, and the engine delivers 2 or 3 depending on the run.
The defect is unchanged — the recovery phase never runs — but the size of the
prize is a range, and a single run cannot measure it.

**This matters for how the remediation is measured.** An A/B over a quantity
whose run-to-run variance is +/-1 interval cannot be decided by one run per
arm; it needs repeats. Recorded here so the follow-up is not designed badly.

### Why they were left

Not capacity — the capacity verdict is correct. Not candidate generation,
retention or selection — `final_before_target_loss_vs_global_best` is 0. The
phase whose entire job is this recovery never ran:

```
target_lock_recovery.execution
    eligible_candidate_count  14
    attempted                  0
    skip_reason               INSUFFICIENT_RESERVED_TIME
```

`run_target_lock_recovery_phase` needs **65 seconds** at its entry guard before
it will make its first attempt. The budget plan gave it **19**. At a 900-second
budget its ceiling is 53 seconds even when Stage 1 states no need at all, so at
QUICK no configuration can fund it:

```
  total   tlr alloc (stage1 need=0)   tlr alloc (need=0.45*total)   viable?
    900                          53                            19    NEVER
   1800                          72                            27    partly
   3600                         144                            70      yes
  14400                         576                           576      yes
```

### A fix I implemented and then reverted

I first made `build_global_budget_plan` drop any phase allocated less than its
own entry guard and return the seconds to break search. It was wrong, and my
own data disproved it: **phase deadlines here are cumulative**, so a phase
inherits whatever earlier phases did not spend. On the same run,
`post_break_repair` held a nominal 19 seconds against a 35-second entry guard
and **still attempted one repair**, because Stage 1 and break search underran.
Dropping phases on nominal allocation would have deleted work that was really
happening.

What is kept is the diagnostic only, with no allocation change:
`audit.budget_phase_viability` records each phase's entry guard and which
phases are nominally below theirs, with an explicit note that a nominal
shortfall is not proof of starvation — it must be read beside the phase's own
`attempted` count. A phase listed there that *also* reports
`INSUFFICIENT_RESERVED_TIME` was genuinely starved; one that attempted work was
not. That distinction is exactly what was missing when this looked like a
break-placement defect.

### What remains open

Funding `target_lock_recovery` at QUICK is a real trade-off: its 65 seconds
would come out of Stage-1 or break search, both of which B-3 showed are worth
real coverage. The headroom is +2 intervals on this one case. That decision
needs its own A/B and has not been made here.

---

## B-5 — measured precisely, no symptom, no change made

### What the objective actually is

`skeleton_profiles()` declares weights spanning about **533 : 1**. The
coefficients CP-SAT actually receives are those weights multiplied through
model construction, so the built model is the only honest source:

| | AE_FR_Choice |
|---|---|
| model variables / constraints | 3,300 / 5,744 |
| objective terms | 2,109 |
| **distinct coefficients** | **14** |
| smallest non-zero / largest | 8 / 3,200,000,000 |
| **dynamic range** | **400,000,000 : 1** |

The ladder: 8, 40, 400, 1 600, 6 000, 45 000, 450 000, 550 000, 900 000,
70 000 000, 180 000 000, 260 000 000, 420 000 000, 3 200 000 000.

### It reads like a priority order and is not one

A weighted sum behaves lexicographically only if each tier's **maximum total
contribution** is below **one unit** of the tier above. Measured against each
objective variable's declared domain:

| weight | terms | max total contribution | below one unit of the next tier? |
|---|---|---|---|
| 8 | 112 | 896 | **no** (next tier is 40) |
| 40 | 112 | 448,000,000 | **no** |
| 400 | 112 | 4,480,000,000 | **no** |
| … | | | |
| 420,000,000 | 112 | 47,040,000,000 | **no** |

**13 of the 14 tiers can be outvoted in aggregate by the tier below them.**

### But it is not a bug, and I am not changing it

* **The engine does not rely on the objective for priority.** Candidate
  *selection* is a genuine lexicographic tuple (`_candidate_quality_tuple`),
  and hard guarantees are hard constraints (`min_target_hits`, `min_floor_hits`)
  — the B-4 probe above uses exactly that mechanism. The weighted sum
  *generates* diverse candidates; it is not the thing that orders them.
* **No overflow risk.** Worst-case objective value across all eight packaged
  workbooks is 7.0e12 – 1.5e13, leaving **~600,000× int64 headroom**.
* **No symptom.** My earlier report named B-5 as the root cause of B-3. The
  B-3 measurement disproved that — the cause was a cold-measured slice floor.
  I have no measurement showing the objective's conditioning costs coverage.

Restructuring a solver objective with a measurement but no symptom is the
speculative change this work has avoided throughout. What is added instead is a
guard test pinning the tier count, the range and the int64 headroom, so a
future weight change that risks overflow or collapses the ladder is caught.

---

## B-6 — not a defect; my earlier description was wrong

### The symmetry is real

Associates grouped by every input the model distinguishes them by (language,
skills, fixed requests, preferences, carry-in, shift variety):

| workbook | associates | orbits | largest orbit | equivalent permutations |
|---|---|---|---|---|
| Cricut_Chat | 27 | 4 | **24** | **6.204e+23** |
| RC9_2_2_NMG_EN_PRODUCTION | 42 | 8 | 15 | 4.925e+26 |
| NMG_EN_FIXED_NESTING | 42 | 7 | 15 | 3.247e+25 |
| Cricut_Voice | 33 | 11 | 16 | 2.109e+17 |
| GDI_REAL28 | 29 | 13 | 7 | 3.484e+07 |
| AE_AR_B2B | 35 | 24 | 8 | 645,120 |
| NMG_SP | 7 | 5 | 2 | 4 |

The 6.2e23 figure I reported is confirmed — it is Cricut_Chat, 24 of 27
associates in a single orbit.

### Two corrections

**First: `symmetry_level` is not "unset" in the sense I implied.** The engine
never assigns it, and OR-Tools 9.15.6755 defaults it to **2** — the enabled
level. There is no missing solver setting.

**Second, and decisive: the symmetry is not unbroken.** CP-SAT's presolve finds
it and breaks it, on both large cases:

```
Cricut_Chat (6.2e23):
  [Symmetry] #generators: 1047, average support size: 7.97
  [Symmetry] 613 orbits on 4788 variables with sizes: 24,24,24,24,...
  [Symmetry] Found orbitope of size 137 x 24

RC9_2_2_NMG_EN_PRODUCTION (4.9e26):
  [Symmetry] #generators: 409
  [Symmetry] 316 orbits on 1562 variables with sizes: 10,10,10,...
  [Symmetry] Found orbitope of size 94 x 10
```

It recovers exactly the 24-associate orbit computed independently above, and
builds an **orbitope** — the canonical and strongest symmetry break for
interchangeable columns, and precisely the structure hand-written symmetry
breaking would try to add.

Adding manual symmetry-breaking constraints on top would at best duplicate
this and at worst interact badly with the orbitope CP-SAT installs. **No change
made, and none warranted.**

---

## Summary

| | verdict | evidence |
|---|---|---|
| **B-4** | **real defect** | zero loss proved INFEASIBLE in 1.6s; one loss proved FEASIBLE and hard-clean; engine shipped three on one run and two on a byte-identical repeat, so the headroom is 1-2 intervals; the recovery phase attempted 0 of 14 with a 19s allocation against a 65s guard it cannot reach at QUICK |
| **B-5** | measured, no symptom | 400,000,000:1 over 14 tiers, 13 non-separating; ~600,000× int64 headroom; priority is enforced by lexicographic selection and hard constraints, not by the weights |
| **B-6** | **not a defect** | symmetry real (6.2e23) but `symmetry_level` already defaults to 2 and presolve installs a 137×24 orbitope |

One change to shipped behaviour: none. One diagnostic added. One fix written
and reverted because my own data disproved its premise.

The diagnostic was itself regression-checked on a full run: the budget plan is
byte-identical to the run before it, phase for phase, and the gate pins that
asking for diagnostics cannot change the plan. The coverage difference between
those two runs is wall-clock search variance, which is what prompted the
correction above.
