# Stage-2's break search plans 168 attempts and runs zero

This is the root cause behind NIGHT_06's correction, and it is corpus-wide
rather than a Cricut Chat quirk.

## The record

`C_CHAT_1800_w4`, the run that delivered `after_target 159` while 159 was
provably reachable on a skeleton it scored at 130:

```json
{"phase": "adaptive_fully_compliant_break_search",
 "cp_status": "STOPPED_INSUFFICIENT_BREAK_SEARCH_DEPTH",
 "attempts_completed": 0, "attempts_planned": 168,
 "proposed_slice_sec": 139.851, "minimum_slice_sec": 180.0}
```

**Zero of 168.** The phase that places breaks against the real coverage
objective never ran.

## Where the 452 seconds went

`break_search` is allocated 452s of the 1800s ladder. By the time the loop
reached it:

| | seconds |
|---|---|
| `break_search` allocated | 452 |
| already consumed when the Stage-2 anchor started | 175 |
| `phase_remaining_at_start_sec` (anchor) | 277.008 |
| granted to `guaranteed_stage2_anchor` | 135.0 |
| left for the adaptive loop | 139.851 |
| `BREAK_MIN_MEANINGFUL_SLICE_SEC` | 180.0 |

Short by 40 seconds, so the loop stopped without a single attempt. The anchor
that consumed the 135s returned `"status": "UNKNOWN"`, `"hard_clean": false`,
`"candidate_class": "rejected"` -- it produced nothing usable.

Phase deadlines are absolute offsets from process start, so Stage-1 overrunning
its 1038s mark does not delay `break_search`; it *consumes* it. That is the 175s.

## What the pool was left with

With no real break search, four of the six production skeletons entered the
final pool only as `fully_compliant_diagnostic_fallback` -- promoted solutions
from `minimum_exception_diagnostic`, a model that minimises exception cells and
is blind to coverage (the whole quality block is gated behind
`if not diagnostic_mode`).

| skeleton | before_target | after_target | break profile |
|---|---|---|---|
| `hard_feasibility_probe` | 169 | **159** | `fully_compliant_target_priority` |
| `target90_restore_champion` | 193 | 134 | diagnostic fallback |
| `release_gate_floor_satisfaction` | 190 | 132 | diagnostic fallback |
| `target_floor_pareto_master` | 194 | 130 | diagnostic fallback |
| `floor_gate_hunter_before` | 187 | 129 | diagnostic fallback |

The ~60-interval "break damage" on the strong skeletons is not break damage. It
is the coverage-blind fallback being read as if it were a break-search result.

## The natural experiment

At 3600s the same phase could fund three attempts. Same workbook, same
skeleton (`target90_restore_champion`, `before_target 194`), two paths:

| path | after_target | objective |
|---|---|---|
| diagnostic fallback | 137 | -- |
| real `target_priority` break solve, 180s | **164** | 1,960,983,785 |

**+27 intervals from running the search that QUICK skips.** And across that
run's three real attempts the objective is monotone in coverage --
164 -> 1.96e9, 135 -> 3.54e9, 131 -> 3.91e9. Lower objective, higher
`after_target`, every time.

That settles the question NIGHT_08 pre-registered: **the objective is not
misweighted. It ranks coverage correctly. The search is starved.**

## Corpus census

`tools/stage2_attempt_census.py` over 117 audits:

| budget | runs | runs with ZERO real attempts | median attempts | max |
|---:|---:|---:|---:|---:|
| 600 | 6 | 5 | 0 | 1 |
| 900 | 17 | 11 | 0 | 2 |
| **1800** | **22** | **15** | **0** | 3 |
| 2400 | 8 | 6 | 0 | 97 |
| 3600 | 16 | 4 | 2 | 7 |
| 14400 | 4 | 1 | 24 | 24 |

At the production QUICK budget of 1800s, **15 of 22 runs place breaks without
ever running the break search.** The engine plans 28-168 attempts and executes
a median of zero.

## This is not the B-10 floor

B-10 was retracted correctly: the 180s floor is right, because 90-150s returns
160 and 180s returns 162. Lowering the floor buys worse schedules. The defect
is upstream of the floor -- `break_search` never *has* 180 seconds to offer.

## Fix candidates, both untested

1. **Contain Stage-1.** The 175s that `break_search` lost before it began is
   Stage-1 and its diagnostic loop running past `stage1_deadline`. Enforcing
   the mark returns one fundable attempt at 1800s.
2. **Size the anchor to leave one attempt.** Cap the anchor grant so
   `remaining - granted >= 180` whenever the phase can afford both. On Chat
   that converts 135s of rejected anchor into one real attempt.

Neither is applied. Recorded as measurement, not remediation: on Chat the
first planned adaptive task is `target_floor_pareto_master`, which at 3600s
returned 135 -- below the 159 that run actually shipped. So *one* recovered
attempt is not automatically an improvement; the +27 came from the second.
Funding the phase properly needs ~540s at QUICK against 452 allocated, and
that is a budget-ladder change that must be A/B'd per workbook before it ships.
