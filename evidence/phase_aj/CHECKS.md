# Phase AJ: what was built and the checks

© 2026 Omar Mokhtar. All rights reserved.

Checks run on code commit c9c0d29 (Thu 15 Oct 2026, finished about 18:20 Egypt time). Tools: `evidence/phase_aj/tools/`
(Phase AI's, with the review server setting the upload with channel needs in use and adding one cover, plus
`aj_screens.py`).

## What was built

| # | Owner's item | What changed | Tests |
| --- | --- | --- | --- |
| 1 | Overtime 4 h before a 20:00 to 05:00 shift refused with the wrong reason | Cap raised to 4 h (owner's answer: "raise it to the options we do have"). Root cause: + Add offered 4 h, the server capped at 2 h and read a start more than 2 h before the shift as the next day | test_aj_overtime (6); re-pinned with the reason: test_attendance, test_day (2), test_add_overtime_default, test_runs (cover panel lengths) |
| 2 | Cover from outside the roster (TM or support) counted in the intervals | Overtime and VTO tab: name (typed), role, from, to, channel when the program has channels, post tick. One more person on the floor for those minutes (past midnight too), on their channel; not in the plan, lanes, languages, adherence or shrinkage. Journal and Undo, day log, group posts (under "Overtime, VTO and cover from outside the roster"), the board names them, program rename and the 13-month clean-up include them. Exports: a tick; ticked, their own sheet and "Cover min" in the Daily summary with them counted; unticked, the roster alone | test_aj_cover (20); re-pinned with the reason: test_exports_speed (page's new tick), test_run_admin (rename counts a "cover" entry) |
| 3 | No channel colour on the Timeline after 00:00 | Root cause: a day's channel stretches were made only for shifts starting that day and only up to midnight. The next day's view now carries last night's stretches; the 24 hours from a start join them. The channel change list still names only the day's own shifts | test_aj_midnight (3) |

## Checks

- Website suite in two halves: 502 tests OK (1 skipped) and 581 tests OK.
- Browser tests: 77 OK (the older phases' screenshots they rewrite were put back).
- Release gate (`run_tests.sh`): GATE PASS, 77 suites, 1537 tests (2 skipped), engine untouched.
- Page review, every page at 360 and 1440 px in the dark and light looks: 0 problems (status, console errors,
  sideways scroll on a phone).
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow; the same 2 "leaks" by design and the same 222
  "None" words written on purpose as Phase AI (`evidence/phase_ai/CHECKS.md`).
- pyflakes on the changed files: only the old unused `DAYS` import in exports.py (known, left as it was).
- Screens: `evidence/phase_aj/screens` (the cover panel at 1440 and 360 px in both looks; the Timeline from 07:00).

## Known and left

- The review data has channel needs but no channel plan, so the Timeline screen cannot show item 3's colours; the
  fix is proved by test_aj_midnight on the channel fixture (Associate 016, 17:00 to 02:00, on Email after midnight).
- A person covering from outside the roster has no bar on the Timeline (they are not on the roster); the board and
  the tab's list name them.
- From Phase AI, unchanged: one attendance box for a row holding two shifts in the RTA's 24 hours; three old
  unused imports.
