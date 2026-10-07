# H4: the Colab shortfall test made machine-independent (2026-10-07 ~20:00-20:20 Egypt)

Owner approved ("Yes") the fix proposed in `evidence/phase_g/G2_SHORTFALL_REPRO.md`.
Rule pre-registered before measuring: `H4_DETERMINISTIC_BUDGET_RULE.txt`.

Engine change (default off, production unchanged): `run_shortfall_pass(...,
deterministic_time=None)`. When set, its three solves get 0.4 / 0.3 / 0.3 of the
budget as CP-SAT `max_deterministic_time` (applied in `configure_solver_limits`
through `SOLVER_DETERMINISTIC_TIME`, restored after each solve); `time_limit`
stays the outer wall-clock cap. No production call passes it.

Calibration (2 cores pinned, `taskset -c 0,1`; S04 case, seed 9000, 2 workers):

| run | D | result | wall s |
|---|---|---|---|
| unloaded 1 | 10 | PASS | 16.7 |
| unloaded 2 | 10 | PASS | 16.8 |
| unloaded 3 | 10 | PASS | 16.0 |
| unloaded 4 | 10 | PASS | 18.8 |
| unloaded 5 | 10 | PASS | 15.9 |
| loaded 1 | 10 | PASS | 38.7 |
| loaded 2 | 10 | PASS | 34.4 |
| loaded 3 | 10 | PASS | 32.7 |
| loaded 4 | 10 | PASS | 32.9 |
| loaded 5 | 10 | PASS | 37.3 |
| loaded 6 | 10 | PASS | 36.0 |
| loaded 7 | 10 | PASS | 36.3 |
| loaded 8 | 10 | PASS | 32.8 |
| loaded 9 | 10 | PASS | 33.1 |
| loaded 10 | 10 | PASS | 40.6 |

Result: D = 10 (first candidate) met step 1 (5/5 unloaded, median 16.7 s) and
step 2 (10/10 under two busy-loop processes on the same 2 cores; G2 measured
7/10 with the 40 s wall-clock limit). Under load each run takes about twice
as long (same work, half the CPU), 33-41 s. The test now passes
`deterministic_time=10.0, time_limit=600`; its assertions are unchanged.
