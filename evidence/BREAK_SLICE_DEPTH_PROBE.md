# Break-search slice depth probe — what break placement returns per second

**Why this exists.** After A34 funded Stage 1 and A35 stopped the guaranteed
anchor eating the break phase, the adaptive break search still ran **every**
attempt at exactly 20.0 seconds — its own `minimum` — and ten of twenty-five
attempts returned `UNKNOWN`. Rather than assume a third slice floor needed
raising, this measures it.

**Method.** `tools/break_slice_depth_probe.py`: build one skeleton, then call
`solve_breaks` on that same skeleton at a range of time limits. Same workbook,
skeleton, pattern width, objective mode and seed throughout — only the time
limit varies.

Engine `L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1`, OR-Tools
9.15.6755. Input `AE_AR_B2B.xlsx`, skeleton from
`release_gate_floor_satisfaction` at a 450s slice (**168 / 168** before breaks),
pattern width 115, objective mode `target_priority`, seed 9000, 2 workers.

## Results

| break slice | cp_status | `after_target` | `after_floor` | loss |
|---|---|---|---|---|
| **20s** (the engine's floor) | **UNKNOWN** | — | — | — |
| 60s | **UNKNOWN** | — | — | — |
| 90s | FEASIBLE | 160 | 168 | 8 |
| 120s | FEASIBLE | 160 | 168 | 8 |
| 150s | FEASIBLE | 160 | 168 | 8 |
| **180s** | FEASIBLE | **162** | **168** | 6 |
| 450s | FEASIBLE | 162 | 168 | 6 |

## What the numbers say

**1. At the engine's own floor, break placement produces nothing.** 20 seconds
returns `UNKNOWN` — no schedule. So do 60. This is the same shape as Stage 1's
45-second floor in A34: the search was run many times at a depth that cannot
converge.

**2. There are two boundaries, not one.** Feasibility appears between 60s and
90s. Quality steps once more between 150s and 180s (160 → 162) and then stops:
450s returns exactly what 180s returns.

**3. Depth beats breadth here, decisively.** The A35 verification run made
**25 attempts at 20.0s** across all seven objective modes and shipped
`after_target` **156**. **One** attempt at 180s ships **162**, with
`after_floor` at a full 168.

**4. This is what gate 5 was actually measuring.** 162/168 leaves a break loss
of 6 — but reached by improving the schedule, not by lowering the starting
point, which is the distinction A38 exists to make visible.

## What was set from this

`BREAK_MIN_MEANINGFUL_SLICE_SEC = 180.0` in `l632_universal_scheduler.py`, and
the adaptive loop now **stops** when the phase cannot fund an attempt of that
length instead of spending the tail on attempts that return nothing. Stopping
is recorded in the audit as `STOPPED_INSUFFICIENT_BREAK_SEARCH_DEPTH` rather
than passing silently — A28's lesson.

## Limits of this evidence

One scenario, one skeleton, one objective mode. AE AR B2B is the hardest case
in the regression set and the one whose gate 5 verdict was in question; whether
180s is also the right boundary for Cricut Voice, Cricut Chat or GDI REAL28 is
not established here and needs the full re-run to confirm.
