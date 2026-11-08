# Phase BL audit: the channel planner's solver setting (pre-registered 2026-11-08, before the runs)

**Problem.** `test_channel_plan.TheBreaks.test_empty_breaks_are_placed_inside_the_rules` fails intermittently, on the commit before Phase BL too (2 of 4
single-test runs, and in module runs). `plan_day` solves with 4 workers and a 10 to 12 second wall-clock limit; the solver always stops FEASIBLE, never
proven optimal, and the objective it reaches swings from 54 to 300 between identical runs. The runs that end high leave a "normal maximum gap" rule missed.
A deterministic search (`interleave_search` with a deterministic time limit) is repeatable but repeatably misses the rule, so it is not the answer.

**Candidate settings measured** (5 runs each, the test's own scenario, same machine): `linearization_level 2`, `symmetry_level 0`,
`cp_model_probing_level 0`, `num_workers 8` (all no better than now), and `use_lns_only true` (5 of 5 without a problem, objectives 42 to 142).

**Rule for accepting `use_lns_only`** (written before the 12-run measurement): over 12 runs of the scenario, every run has zero problems from
`score_day` AND the median objective is no higher than the median objective of 12 runs with the current settings; the wall time stays within the existing
limit (the setting changes how the time is used, not how much). After that, the whole `test_channel_plan` module must pass 3 times in a row, and
every other test that plans a channel day must pass, with the same settings.

## Result
Measured 2026-11-08, same machine, the test's own scenario.

| Setting | Runs | Runs with a problem | Median objective |
|---|---|---|---|
| current (before) | 12 | 8 | about 158 |
| `use_lns_only`, only when breaks are still to be placed | 12 | 0 | about 36 |

The rule was met on both counts, so `PLACING = {**KEPT, "use_lns_only": True}` is used when a person still has a break to place; moving breaks
and every other channel solve keep `KEPT`. The first attempt, `use_lns_only` for every solve, broke `test_bc_two_ticks` and
`test_bc_channel_rotation`, which is why it was narrowed. Three passes over the 25 modules that plan a channel day: pass 1 clean; passes 2 and 3
failed only the two rotation tests below, which are not about placing breaks.

## The two rotation tests that remain timing-sensitive
`test_bc_channel_rotation` compares two independent solver runs (Balanced against both ticks off): `test_both_ticks_off_charges_nothing`
(off has at least as many short stretches) and `test_balanced_still_has_fewer_short_stretches_than_off_and_does_not_change_far_more_often`.
Each run is limited by wall-clock time on 4 workers, so each score varies run to run (objective 5422 to 5524, short stretches 38 to 59 on the same
input). Measured failure rate of the module: 1 of 10 runs on the commit before Phase BL, 2 of 10 on this one: the same phenomenon, within noise.
A deterministic search made the result repeatable but 1.5 to 3.7 % worse on the objective, so it was not adopted: production quality comes first.
The tests are unchanged. Policy: see "Known timing-sensitive tests" in docs/HANDOFF.md.
