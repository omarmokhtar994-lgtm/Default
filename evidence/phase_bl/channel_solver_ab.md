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

**Result of the hint:** rejected by its rule. 20 runs: 1 with a problem (Associate 014, 225 minutes against 210, objective 42) and median objective
about 88 against 47. Reverted.

**What the miss in a good plan shows.** That run reached 42 and still missed by one quarter hour, which costs GAP = 2. Every preference in the model
costs more than that per quarter hour (KEEP 3, SHAPE 3, MOVE 5, DAY_MIX 8, CONSISTENT 20, STRETCH_OVER 20, STRETCH_COST 22), so the planner
gives up the maximum gap for a preference. The owner-facing rule (docs/howto/RTA.md, Phase AX) says the opposite: "Plan channels passes it only when a
channel's need asks for it", and the cost's own comment says "so it is passed only for a channel's need". The weight does not do what the rule says.
That is the root cause; the clock only decides which of the cheap misses a run lands on.

**Candidate 2:** GAP = 25: above every preference (the largest is 22) and below every need (the smallest is a channel's shortfall, 30 a quarter hour;
a long run 40, alone 50, a language 200), so a need still wins and a preference no longer does.

**Rule for accepting it** (written before the runs): over 20 runs of the empty-breaks scenario, zero runs with a problem; `test_ax_channel_shape`
passes (a need still passes the maximum, by the least); every module that plans a channel day passes twice in a row with the change.

**Result of candidate 2 (GAP = 25):** rejected by its rule. The 20 empty-breaks runs had no problem, but `test_ax_channel_shape`
(a need that forces a longer gap gets it, by the least) failed: with 25 a quarter hour the planner kept the gap and gave the need up. The arithmetic:
there the need is met by passing the maximum by 2 quarter hours, so 2 x GAP must stay below one quarter hour of a channel's need (30), so GAP < 15.
"Above every preference" (22) and "below every need" cannot both hold with one weight a quarter hour.

**Candidate 3:** GAP = 14, the largest weight that keeps the need case (2 x 14 = 28 < 30); above KEEP, SHAPE, MOVE and DAY_MIX (3 to 8), below
CONSISTENT, STRETCH_OVER and STRETCH_COST (20 to 22). **Rule** (written before the runs): as for candidate 2. If it fails, the trade-off goes to the
owner and the weight stays 2.

**Result of candidate 3 (GAP = 14):** rejected by its rule: `test_ax_channel_shape` fails the same way (the need case keeps the gap, 45 minutes inside
it). The need case trades more than one cost, so no weight found between 2 and 14 keeps it. Three candidates (a hint, 25, 14) failed; the weight stays 2
and the planner is unchanged. Under weight 2 the empty-breaks scenario misses the normal maximum gap in about 3 of 20 runs (by 15 to 90 minutes),
which the page reports as a warning. How to settle it is the owner's decision (asked 2026-11-08).
