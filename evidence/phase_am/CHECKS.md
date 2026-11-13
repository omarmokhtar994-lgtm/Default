# Phase AM: what was built and the checks

© 2026 Omar Mokhtar. All rights reserved.

Checks run on code commit f644986 (the last code change: a finished run's outcome stamped first),
Fri 16 Oct 2026, finished about 03:05 Egypt time. Tools: `evidence/phase_am/tools/` (Phase AL's, plus
`am_screens.py` and `am_audit.py`, the clock stopped on Wednesday 14 October 2026 at 10:00).

## What was built

| # | Owner's item | What changed | Tests |
| --- | --- | --- | --- |
| 1 | A one-click fix for channels on the RTA (answers: re-plan from now with the channel planner, channels only, coverage first then fairness, changes shown first) | `DayBook.channel_fix_plan` and `apply_channel_fix`; `plan_day` takes `carry_in` (carrying on is no new stint) and `keep` (a quarter hour off the current channel costs more than the fair spread, less than any shortfall); a Fix channels button, preview (each change, the shortfall per channel and language now and after), Apply all as one Undo step, refused for a change that has passed; the `rta_change` permission | test_am_fix_channels (10) |
| 2 | Download not in the zone picked | Root cause: the link carried no zone and the route sent the kept workbook. Now a copy in that zone's clock (`versions.zoned_copy`), shifts as the page shows them, breaks moved the same, the zone in the file name | test_am_zone_download (5) |
| 3 | Weeks: choose the version for "As planned" | A Version pick on Weeks; the grid and Hours needed "As planned" (and its download) follow it; "As recorded" and the RTA keep the one in use; another week's version answers 404 | test_am_week_version (4) |
| 4 | No percentage for a before-breaks-only schedule | Root cause: Home and the run page read an engine run's figures only from the engine's after-breaks check. Now the version in use, else the engine's, else the version the week shows, marked "before breaks". The Weeks grid already read the version | test_am_figures (2) |

Also fixed while checking: a finished run's outcome is now stamped before its status says finished (a race seen once
under the parallel suite load).

## Reviews

- web-interface-guidelines on the changed templates: pass. Every new control is native and labelled. Apply has Undo
  and Cancel. Each refusal says what to do next.
- Live audit (Fix channels preview, Weeks with the Version pick, Home, a schedule in London time) at 1440 and 320 px:
  - Every page answers 200 with the CSP header. 0 duplicate ids, 0 unnamed controls, no sideways scroll.
  - One console warning on Home at 320 px: the font preload is not used yet. It comes from the page template, from
    before this phase.
- Security: the new POST `/day/channels/fix` has CSRF (the global check) and the `rta_change` permission. Each change
  is parsed strictly and checked again by `channel_move`.

## Checks

- Website suite in two halves: 624 tests OK and 559 tests OK (1 skipped). The first run of the first half had one
  error, from the race fixed above; after the fix: 624 OK.
- Browser tests: 77 OK (the older phases' screenshots they rewrite were put back).
- Page review, every page at 360 and 1440 px in the dark and light looks: 0 problems.
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow, nothing logged. The same 2 "leaks" by design.
- Release gate (`run_tests.sh`, inside the package build): GATE PASS, 77 suites, 1537 tests (2 skipped), engine
  untouched. The first build was stopped by a container restart; the second ran through.
- Screens: `evidence/phase_am/screens`:
  - the Fix channels button and preview;
  - the Weeks page with the Version pick;
  - Home with a "Before breaks only" run ("100% before breaks");
  - a schedule in London time with its download button.

## Known and left

- Fix channels plans today's own shifts. Last night's people are held and counted; tomorrow's early shifts are not
  planned.
- Channels change on quarter hours, from the next quarter hour.
- People with no channel planned on the floor (after midnight in the fixture) are given one.
- The planner offers Email to someone who works several channels only inside the day's Email hours. Someone on Email
  outside them is moved.

## Package

`RC9_2_2_PRODUCTION_PACKAGE.zip`, 2729 files, 93.66 MB, sha256
`0aabe9d44f8003b92ebed8073bbe08d0e421cc9d17d2fdf7123f68435c4d0a79`, sent as AM_part_0 to AM_part_3. It contains AK and
AL too. This file was written after the build copied its files, so it is not inside the package.
