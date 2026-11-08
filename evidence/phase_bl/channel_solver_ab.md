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

**Fixed 2026-11-08 (owner: "I need to make this flaky stable").** Root cause: one run against one run. Measured, short stretches per run: Balanced 9 to 17
(10 runs, median 12), both ticks off 14 to 19 (12 runs, median 15.5): overlapping ranges, so one pair said "Balanced is not calmer" about 1 time in 6.
Moves are far apart (34 to 44 against 62 to 73 with the fair tick on; 33 to 40 with it off) and never failed. Deterministic single-worker solve tried:
repeatable but Balanced 20 against off 19 (a worse plan, and it fails the test every time), 3.5 minutes for 5 plans, so rejected. Change: the two tests
compare the mean of 8 runs per side, planned once for the class; claim and limits unchanged, re-pin reason written in the test.
Estimated failure rate from the measured spread: below 1 in 300. Result: 7 of 7 runs green (1 module run, 6 repeats of the two tests).
Mutation check (Balanced arm given both ticks off, so it must not be calmer): failed 3 of 4 runs, the fourth passed by chance (two equal sides).
The "Known timing-sensitive tests" section in docs/HANDOFF.md is replaced by this fix.

## Second look, 2026-11-08 evening (owner: "fix everything 100%")
With `use_lns_only` the empty-breaks test still failed 3 of 20 single-test runs (Associate 014 or 016: Break 2 starts 225 to 300 minutes after Lunch
ends; normal maximum 210). 16 more runs logging the solver's own objective: no problem in any, objective 22 to 116 (median 47). The rule is a cost
(GAP = 2 a quarter hour, Phase AX: a normal, not an absolute); a run that misses it pays at least 6, and runs without a miss reach 22, so a miss is the
search stopping on the clock far from the best plan, not the best plan choosing to miss. Root cause: the placing solve starts from nothing (an empty
break has no hint), and 12 seconds on 4 workers does not always get close.

**Candidate:** hint every empty break at the candidate start nearest to an even spread of the person's breaks over the shift
(break k of n at start + (k + 1) * length / (n + 1) - its minutes / 2). A hint is only a starting point: the model, its costs and its limits are unchanged.

**Rule for accepting it** (written before the runs): over 20 runs of the test's scenario, zero runs with a problem from `score_day`, AND the median
objective no higher than the 16-run median above (47); the time limit unchanged. Then `test_channel_plan` passes 3 times in a row and every module that
plans a channel day passes.
