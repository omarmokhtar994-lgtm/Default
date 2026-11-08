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
(filled in after the runs)
