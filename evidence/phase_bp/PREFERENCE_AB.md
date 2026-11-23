# Phase BP A/B: shift Preferences with a coverage allowance (owner, 2026-11-12)

Rule and amendments: `PREFERENCE_ALLOWANCE_RULE.txt` (each written before the run it governs). Whole engine, QUICK, `--time-limit 300`, 2 workers, default
seed; made-up agents. Before-arm: the engine at commit bc83eb5; after-arm: this phase. "Honoured" is an exact count from the published Schedule sheet
(asked shift equals worked shift), not the engine's own figure.

| Case | Before-arm selected | After-arm selected | After-arm PREFERENCE_CANDIDATE |
|---|---|---|---|
| Shipped workbooks (7) | no shift Preferences in any (parsed: 0 cells) | the step has nothing to move | none |
| Toy 1, 12 people, all ask what demand needs | 60 of 60 | 60 of 60 | none (nothing to gain) |
| Toy 2, one-day requests 3 h away | 59 of 60 | 59 of 60 | none: the move costs about 4% and is refused |
| Toy 3, one-day requests 1 h away, 2 people per shift | 58 of 60 | 58 of 60 | none: one move breaks a row or cell rule, the other would open a severe floor gap (50% in that hour) |
| Toy 4, 36 people, 6 per shift, three one-day requests 1 h away | 177 of 180, twice (no candidate: 0 swaps) | 144 of 180 | **161 of 180**: 5 swaps, 9 moves, validator PASS, coverage cost none |

## Verdict against the rule
- Shipped workbooks unchanged, protected baselines untouched: met (the step has no candidate cell; `git status` shows no workbook changed).
- Toy 1: met. Toys 2 and 3: the pre-registered "honours more" line is **not met**; in both the refusal is the rule itself (past 2%, or a new gap).
- Toy 4: met. The after-arm's selected schedule misses 36 requests, the before-arm has no candidate, and the after-arm publishes one that honours
  17 more, passes the independent validator with 0 hard failures, and costs no coverage.
- Not shown by any full run: a candidate that actually spends part of the 2%. That path is covered by the unit tests only
  (`tests_staged/test_rc9_2_62_preference_allowance.py`: one interval of 60 kept, the second refused).

## Two things the runs showed that are not fixed here
1. **The selected schedule differs between the arms on toy 4 (177 against 144), and this change is not the cause.** The two scheduler logs are the
   same for 93 lines and part at a time window: the before-arm had 66 s left for the Stage 1 portfolio and funded one profile, the after-arm had 23 s
   and funded none, so it kept the `deterministic_target_baseline` skeleton, which weighs Preferences least. The preference step runs after the
   schedule is chosen. This is the likeliest cause of the owner's complaint (a): **when a run is short of time, the schedule comes from a skeleton
   that barely looks at Preferences.** Whether to give Preferences more weight there is a Stage 1 behaviour change and needs its own A/B.
2. **The step stopped on its time limit after 1.1 s** (`stopped_by_time_limit: true`) with 19 requests still open: it gets what is left of the run
   after the reserves, and at 300 s that was the 1 s minimum. A 3,600 s production run leaves more, but this was not measured.
3. The engine's own `preference_match_count` read 177 -> 180 where the exact count is 144 -> 161, so it is not an exact-match count. Not changed.

Raw outputs: session scratchpad (`pref/out/TOY*`), not kept in the repository.
