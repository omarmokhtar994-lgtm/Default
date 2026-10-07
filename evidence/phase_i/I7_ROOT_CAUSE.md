# I7: why the shortfall test failed on the Oracle server (root cause)

2026-10-08, ~00:30 Egypt time. Procedure: systematic-debugging (root cause before any fix).

**Symptom.** In the safety gate on the owner's ARM server, `test_the_pass_exports_a_listed_non_releasable_schedule`
(tests_staged/test_rc9_2_32) found one extra zero-coverage half-hour (Sat 15:30) besides the planted
Sunday 03:00-03:45 hour, with the Phase H budget D = 10.

**Reproduction on x86 (this container).** `I7_shortfall_diag.py` runs the pass exactly as the test does
(case S04, seed 9000, 2 workers, D = 10, pinned to 2 cores) and records every stage. 40 runs: 4 failed
(`I7_DIAG_D10_X86.json`), each with one extra weekday-morning half-hour (Tue 08:45, Fri 08:45, Wed 08:45,
Fri 08:15). Earlier: 1 of 15 failed. Together about 1 in 11.

**What differs between passing and failing runs: nothing in the stage statuses.** In all 40 runs the
minimum-shortfall solve is OPTIMAL, while the coverage refinement and the elastic break placement both end
FEASIBLE (not proven best) when their share of the budget runs out. With two search threads the path differs
from run to run, so whether that last half-hour gets covered is chance at this budget.

**Root cause.** The test's work budget (D = 10, chosen in Phase H with the smallest candidate that passed
5/5) leaves the last two solves stopped short of their best answer about 1 time in 10. The server's single
failure is consistent with that rate; there is no evidence that ARM behaves differently.

**Production is not affected the same way**: real runs give the shortfall pass minutes of wall-clock time,
not a fixed 10-unit work budget.

**Fix (rule `I7_SHORTFALL_BUDGET_RULE.txt`, written before measuring):** the x86 probe chose D = 40
(20/20 unloaded; loaded step in `I7_PROBE_X86.txt`). D = 20 failed 1/20.
