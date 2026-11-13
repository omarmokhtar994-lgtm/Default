# © 2026 Omar Mokhtar. All rights reserved.
# Phase AQ: checks

Pre-registered rule: `REQUESTS.md`. Input: owner's GDI week of 18 Oct (scratch copy), Quick, before breaks.
Arm A = ALL_ROWS + START, arm B = ALL_ROWS + WHOLE_SHIFT. Run 2026-10-21 16:56 to ~17:19 UTC (19:56 to 20:19 Egypt time).

| Rule | Result |
|---|---|
| 1. B feasible, same limit | Pass. Both arms RELEASABLE, SKELETON_ONLY_COMPLETE, independent validation PASS, hard failures 0, probe OPTIMAL. |
| 2. No shift outside its window in B | Pass. `tools/clean_room_check.py` with `language_window_whole_shift: true` reports only `shift_without_breaks` (126, expected before breaks); no language-window violation. |
| 3. Coverage at the 80% floor within 2 of 156 | Pass. 142 in both arms. Target coverage 133 (B) vs 134 (A); 90% level 135 in both. |
| 4. Default path unchanged | Pass. Contract hash for a blank row unchanged (payload key only added when not START); gate and regression assets run in the release gate (see the package gate report). |

Deviations, recorded:
- Time limit 1500 s and 2 workers per arm instead of the 3600 s rule. Two earlier attempts (about 15:27 and 15:52 UTC) were killed by container restarts; the relaunch used the shorter budget so both arms could finish on 4 CPUs in parallel.
- Active intervals are 156, not the 140 written in the rule; the "2 intervals" margin was kept as written.
- The arms ran in a scratch copy of the package with the new engine identity; nothing under `engine/regression_assets` was touched.

Verdict: accept WHOLE_SHIFT as an optional row. START stays the default.
