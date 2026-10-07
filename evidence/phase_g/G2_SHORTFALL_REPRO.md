# G2: Colab shortfall-test failure reproduced (2026-10-07 ~15:35-15:45 Egypt)

Test: `tests_staged/test_rc9_2_32_phase_c_shortfall.py::C1ShortfallPass::test_the_pass_exports_a_listed_non_releasable_schedule`
(case S04: 0.5 FTE on Sunday 03:00 that no legal day shift reaches; the
shortfall pass runs with a 40 s wall-clock limit, 2 workers, seed 9000, and the
test requires every exported shortfall to be Sunday 03:xx).
Machine: 4 cores; every run pinned to 2 cores (`taskset -c 0,1`). "Loaded" =
two busy-loop processes pinned to the same 2 cores (Colab-like: 2 vCPUs with
noisy neighbours). Script and per-run logs: scratchpad `g2/`; every run logged.
The test was not edited.

| run | result | wall s | extra shortfalls (beyond Sun 03:00-03:45) |
|---|---|---|---|
| loaded 1 | PASS | 40.4 | - |
| loaded 2 | FAIL | 36.8 | no schedule exported: NO_BREAK_PLAN_MEETS_THE_PERSON_RULES within 40 s |
| loaded 3 | FAIL | 37.9 | Tue 08:30, Tue 10:45 |
| loaded 4 | PASS | 40.6 | - |
| loaded 5 | FAIL | 38.7 | Fri 08:45 |
| loaded 6 | PASS | 40.1 | - |
| loaded 7 | PASS | 39.9 | - |
| loaded 8 | PASS | 39.7 | - |
| loaded 9 | PASS | 39.9 | - |
| loaded 10 | PASS | 39.8 | - |
| unloaded 1 | PASS | 37.4 | - |
| unloaded 2 | PASS | 37.4 | - |
| unloaded 3 | PASS | 37.5 | - |
| unloaded 4 | PASS | 37.2 | - |
| unloaded 5 | PASS | 37.3 | - |

Totals: loaded 7 PASS / 3 FAIL; unloaded 5 PASS / 0 FAIL.

## Reading

Pre-registered (plan, before the runs): "a failure is a regression only if
the extra shortfalls also appear unloaded or the model proves them avoidable;
if they appear only under load, the test encodes a time-limited search
outcome."

* The extra shortfalls appear only under load (0 of 5 unloaded runs). The
  unloaded runs also show they are avoidable: the same case, seed and limit
  give schedules without the daytime gaps. The rule's two clauses therefore
  point different ways; the rule was ambiguous (recorded as a ruling). The
  measured facts, stated without the label:
  1. the engine has not regressed on this case at full CPU: 5/5 unloaded passes,
     the same result as every repo gate run;
  2. under 2-core contention the 40 s wall-clock shortfall pass fails 3 of 10
     times: twice it exports a schedule with 1-2 extra daytime gaps that a
     better break plan avoids, once it finds no break plan at all in time;
  3. this matches the Colab report (a slower, shared 2-vCPU machine).
* Product effect: the shortfall schedule is never releasable and lists every
  gap, and production gives the pass far more than 40 s. Under heavy CPU
  contention its shortfall list can include gaps a longer search would avoid,
  so it can overstate what is unavoidable.

## Options for the owner (nothing changed)

1. Make the test machine-independent by solving the shortfall pass to a
   deterministic-time limit (CP-SAT `max_deterministic_time`) instead of 40 s
   wall clock in this test; same assertions. Needs an engine parameter
   (default unchanged) - a behaviour change, so pre-registered and gated. The
   engine already uses `max_deterministic_time` for the shift-consistency swap
   solve, so the mechanism has a precedent here.
2. Keep the test as is and treat a Colab failure of it as "machine too slow
   for this test", documented in the run guide.
3. Engine: have the shortfall pass re-check exported gaps against the
   capacity proof and say which gaps are proven unavoidable vs left by the
   search (larger change).

Recommendation: option 1 (smallest change that removes the dependence on
machine speed without loosening any assertion).
