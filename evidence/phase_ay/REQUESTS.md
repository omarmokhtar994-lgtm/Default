# Phase AY: the limit on breaks at once follows the gate mode (pre-registered rule)

© 2026 Omar Mokhtar. All rights reserved.

Owner, 2026-10-23, after a screenshot of an RTA day whose first breaks were 4 to 5 hours into the shift: "work on the website to
follow the shape as long as we have enough buffer in the intervals and ignore the cap".

## Facts (measured and read before any code)

- With no row in the Instructions sheet the engine uses 4 at a time and 30% of the people on shift (blank or empty cell: the same; 0 gives
  1 and 5%; 99 and 99% give 99 and 75%).
- The engine's Break Concurrency Gate Mode is Warn by default: an excess costs about as much as a missed target interval, so it goes over
  the limit only when that saves one. Fail makes it a hard constraint. Off lifts it.
- The website's planners ignored the mode: `break_plan.suggest` ranked "not above the limit" first, before the intervals' buffer and the
  usual shape; `channel_plan` made the limit a hard constraint.

## Change

The website reads `Break Concurrency Gate Mode` with the other break rules (`concurrency_mode`; a schedule whose rules were kept before this
has none and counts as Warn). Fail: the limit stays first in `suggest` and a hard constraint in `channel_plan`, as before. Warn and Off: the
limit does not decide where a break goes; the intervals' buffer, then the usual shape, then the engine's gap rules do.

## Accept the change only if all hold (test_day Wednesday, 29 people, with the limit at 4 and at 2, Arm A = Fail, Arm B = Warn)

1. People whose breaks are off the usual shape: B no more than A, at both limits, and the worst distance no larger.
2. The tightest interval (`min` of the floor's per-interval buffer): B no lower than A by more than 0.25 h.
3. Every break still keeps the engine's gaps and does not overlap (engine-rule distance 0 for everyone).
4. Fail gives the same plan as before the change.

## Result

Measured on test_day Wednesday (29 people), `webapp/tests/test_ay_cap_mode.py` pins it:

| Limit | Arm | People off the usual shape | Worst distance | Most on a break at once |
|---|---|---|---|---|
| 4 | A (Fail, as before) | 2 | 45 min | 4 |
| 4 | B (Warn or Off) | 1 | 15 min | 6 |
| 2 | A (Fail, as before) | 7 | 75 min | 6 |
| 2 | B (Warn or Off) | 1 | 15 min | 6 |

Rules 1 to 4 hold (the tests check the tightest interval within 0.25 h, engine-rule distance 0, and Fail unchanged): ACCEPTED.
