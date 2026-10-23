# Phase AY: checks

© 2026 Omar Mokhtar. All rights reserved.

Owner's questions (2026-10-23, Egypt time): why a Quick run took 1 h 25 m and then failed "Not approved"; "increase the 90 mins cap
only by 15 to 20 mins"; "do 1 and fix grace period, pack everything together".

## What the server showed (run `a1f30203c2b3`, Test program, 27 associates, Quick, 2 seeds side by side, 2 workers each)

| Time (Egypt) | Event |
|---|---|
| 02:09 | Run starts; the gate had run once for this package on 22 Oct 18:21 (stamp `98576db8...`); guards skipped. |
| 03:25 | Seed 9000's last line (75.8 min); its engine clock says `elapsed_sec` 3661. Result: PASS with quality warnings. |
| 03:35 | Seed 9001's last line (85.7 min). Result: FINAL_VERIFIED, independent validation PASS, 0 hard failures. |
| 03:39:30 | The runner stops the portfolio: `TimeoutExpired ... after 5400 seconds` (3600 s budget + 1800 s grace). No `PORTFOLIO_SUMMARY.json`. |

The workbook sets `Language Working Window = ALL_ROWS` and `Language Working Window Shift Rule = WHOLE_SHIFT`. The input check
printed "A shift is inside a window when it STARTS inside it" regardless (fixed text); fixed. Server: 4 cores, 23 GB, no memory
pressure. Patches (`AX_all_in_one`) did not change `MANIFEST.json` (mtime 22 Oct 10:02, older than every patch backup).

## Changes

| Change | Test |
|---|---|
| Input check names the rule in use (`tools/check_input_workbook.py`) | `TheInputCheckSaysWhichRuleIsSet` (2 tests), failed first for WHOLE_SHIFT |
| `GRACE_SECONDS = 3000`, `engine_timeout(budget, rounds)` in the runner: Quick 6600 s, Deep 13200 s, Overnight 19800 s | `test_rc9_2_20_depth_presets` (2 tests), failed first |
| Rescue on timeout: `RUN_PORTFOLIO.py --collect-only`, `seed_return_code`, `rc921_runner.run_portfolio` keeps the finished seeds; `rescue_note` on the run page | `test_rc9_2_59_portfolio_rescue` (13: 2, 4 and 6 seeds, none finished, unvalidated, in time), `webapp/tests/test_ay_rescue_note.py` (5), all failed first |
| Day off cancelled (call in) that breaks the rest gap is kept with a warning (`_call_in`, `add_item`, `/day/activity`); `add_activity(..., "Called in", dry_run=True)` no longer keeps the record | `webapp/tests/test_ay_callin_rest.py` (8), failed first; `test_attendance` re-pinned in 4 places with the reason |
| Open pages ask whether they changed | `webapp/tests/test_ay_live.py` (15), 3 browser tests |
| Breaks of one shift spread over the quarter hours | `test_ax_break_fit` (4); `AMPLE` 1 h lost 0.25 h of the tightest interval in `test_au_break_shape`, so it is 3 h |

Re-pin with its reason in the test: the browser contrast test measured `.wk.short` on a fixture week that no longer has an interval
between the target and 100% (134 cells over, 34 covered), so it lays a cell of that class into the grid.

## Not decided, not built

- Whether WHOLE_SHIFT is what lengthens the stages after the search: run the same workbook with the row at START and compare when the seeds finish.
- Deep and Overnight are Quick seeds in rounds (4 and 6 seeds, 2 at a time), so the grace is per round: caps 3 h 40 m and 5 h 30 m.
