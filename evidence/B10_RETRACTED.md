# B-10 retracted: the break-slice constant is a FLOOR, and correctly so

B-10 claimed `BREAK_MIN_MEANINGFUL_SLICE_SEC = 180.0` was evidence for a CAP
being used as a FLOOR. That was my misreading of the engine's own probe.

The recorded curve:

    20s UNKNOWN | 60s UNKNOWN | 90s 160 | 120s 160 | 150s 160
    180s 162    | 450s 162

I read "the result plateaus at 180s" as "past 180 buys nothing, so 180 is a
cap, and using it as an entry guard needlessly declines shorter attempts that
the evidence shows succeeding".

The second half of that is wrong. 90 to 150 seconds return **160**. 180 returns
**162**. The plateau is the BEST value and 180 is where it is first reached, so
a shorter attempt does not fail -- it ships a materially worse schedule, two
intervals down. 180 is therefore correctly a floor as well as a cap: spend
exactly 180, no more and no less.

Stopping when the phase cannot fund 180 is also correct, for a reason separate
from the curve: the guaranteed Stage-2 anchor has already secured a compliant
candidate by that point, so a short attempt risks budget for a result that is
known to be worse than what is already in hand.

## How it was caught

The gate, immediately:

    AssertionError: the loop must stop when the phase cannot fund a real attempt
    AssertionError: the break slice must come from the measured minimum

`tests/test_rc9_2_1_selector_integrity.py` pins this deliberately, with the
probe data in its docstring and a test named
`test_the_minimum_reaches_the_measured_plateau` whose comment states plainly:
"90-150s all return 160; 180s is where 162 appears."

Those tests exist because this exact constant was got wrong once before -- the
old 20-second floor, fixed under A37. They were written to stop it regressing,
and they did their job on me.

No code change. B-10 is closed as not-a-defect, and the applier is discarded
rather than kept around to be mistaken for pending work.
