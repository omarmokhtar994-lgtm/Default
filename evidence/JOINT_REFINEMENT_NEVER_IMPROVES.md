# The phase that eats 7.6 GB has never improved a schedule

Scanned **44 solver audits** — every run produced in this session: the 16-run
budget sweep, the 18-run worker test, the deterministic A/B pairs, and the
memory probes.

| | |
|---|---|
| runs where joint refinement executed | 18 |
| total attempts | **37** |
| accepted | 8 |
| **improved** | **0** |

Attempt outcomes:

| outcome | count |
|---|---|
| `NO_FEASIBLE_SOLUTION` | **26** |
| `ANCHOR_REPLAY_FEASIBLE` | 8 |
| `ANCHOR_REPLAY_INFEASIBLE` | 3 |

The 8 "accepted" are all `ANCHOR_REPLAY_FEASIBLE` — the phase reproduced the
anchor it started from. That is not an improvement, and the engine's own
counter agrees: `improved: 0` in every single audit.

## Cost of that zero

* **Memory.** Peak RSS tracks joint-refinement execution across three
  otherwise-identical 1800s runs: 2 attempts -> 8244 MB and 8297 MB; 0 attempts
  -> 645 MB. The A/B isolating the flag is still running.
* **Budget.** `joint_refinement_reserve_sec` is **900s at QUICK** — a quarter of
  the 3600s default — and 5400s at DEEP.

## The two runs where it burned 7.6 GB, in full

```
MEMPROBE / FINEPROBE   joint_refinement: attempted 2, accepted 0, improved 0
   attempt 1  incumbent_replay        45s  ->  ANCHOR_REPLAY_INFEASIBLE
   attempt 2  release_quality_master  90s  ->  NO_FEASIBLE_SOLUTION
   final quality: before_target 166 -> after_target 165, floor 167 -> 167
```

Both attempts failed. The schedule shipped is the one break search produced.

## A trap to avoid when reading this

TM18 (0 joint attempts) finished at `after_target` **142** against MEMPROBE's
**165**, which looks like joint refinement being worth 23 intervals. It is not.
TM18 ran **2** Stage-1 attempts against MEMPROBE's **9**, and its skeleton was
worse before breaks were ever placed: `before_target` **145 vs 166**. The
deficit is entirely Stage-1's; joint refinement contributed `improved: 0` in
both.

Attributing that gap to joint refinement would have been exactly the error
this review keeps catching — reading a difference between two runs that differ
in more than one way.

## Scope, stated honestly

Every one of these 44 runs is QUICK mode at 300-1800s. At DEEP the phase gets
5400s and may behave differently; that is **untested**. The claim here is
narrow and empirical: *across 37 attempts at the budgets actually measured,
joint refinement has never improved a schedule.*

## Related

B-13 found both joint bounds comparing `model.NewBoolVar` on both sides, so
they constrain nothing. A structurally inert bound is consistent with a phase
that cannot steer itself toward a better solution, though 26 of 37 attempts
returning `NO_FEASIBLE_SOLUTION` points at the joint model being too hard to
solve in its slice rather than at the bound alone.
