# Joint refinement at DEEP: funded, enabled, never reached

Recorded as open ("joint refinement at DEEP (5400s reserve, untested)").
Measured from the corpus.

## What the DEEP runs record

| run | budget | `joint_refinement` allocated | enabled | status | attempts |
|---|---|---|---|---|---|
| `VOICE_DEEP` | 14400 | **5040s** | true | **PENDING** | 0 |
| `NMG_EN` | 14400 | **2645s** | true | **PENDING** | 0 |

`PENDING` is the initial state. The phase was switched on, given up to
**5040 seconds**, and the run finished without ever entering it.

Across all 54 recorded runs at 3600s or longer -- 50 of them with a non-zero
joint-refinement allocation -- the total is **0 attempts and 0 improvements**.

## Why this matters for the default

Joint refinement was already defaulted OFF at SMOKE and QUICK on measured
grounds: 69 attempts across 7 workbooks with `improved: 0`. The open question
was whether DEEP, with a much larger reserve, would behave differently.

It does not, and for a blunter reason than "it tries and fails": at DEEP it
**does not try at all**. The phase sits behind Stage-1, the break search, the
coordinated repair and the recovery phases on an absolute-offset ladder, and
the budget is gone before its turn arrives.

So the phase that exists to co-optimise shifts and breaks together has, in this
entire corpus, never improved a schedule at any budget -- and at the budget
where it was given the most time, it never executed.

## What this does NOT say

* It does not say joint refinement cannot work. It says the current phase
  ordering never lets it run at DEEP, and that where it did run at lower
  budgets it never improved anything.
* The two 14400s runs are a small sample, and both are Voice/NMG rather than
  the full corpus.
* Nothing here is changed. DEEP and OVERNIGHT keep their current defaults;
  turning the phase off there would be a behaviour change with no measured
  upside either way, since it is already not running.

## The cheaper reading

5040 seconds of a 14400-second budget are nominally reserved for a phase that
never starts. That is not wasted wall clock -- absolute deadlines mean the time
flows forward to whatever runs next -- but it does mean the ladder's stated
allocation and its real behaviour disagree, which is the same class of problem
NIGHT_09 found in `break_search`.
