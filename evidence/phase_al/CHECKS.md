# Phase AL: what was built and the checks

© 2026 Omar Mokhtar. All rights reserved.

Checks run on code commit c573b9a (later commits change only the release notes and the check tools), Fri 16 Oct
2026, finished about 00:10 Egypt time. Tools: `evidence/phase_al/tools/` (Phase AK's, plus `al_screens.py`
and `al_audit.py`).

## What was built

| # | Owner's item | What changed | Tests |
| --- | --- | --- | --- |
| 1 | "I didn't like the green color that much" (answer: sample al01 option C) | Email `#2F7D5B` with a white E like Phone and Chat; the dark-ink rules for Email go | re-pinned with the reason: test_ak_colours, test_markup_xy |
| 2 | "why consistent schedule is not being captured now from the engine run zip" | Root cause: the engine writes the steadier week as `<id>_MORE_CONSISTENT_CANDIDATE.xlsx` beside its schedule (since 2026-10-04); the website kept only the after and before breaks workbooks. Now a candidate the validator passed with no worse coverage is kept as "Tool, more consistent", with the engine's start-time figures on the Schedules list; offered, never set in use by itself; the week still opens on "Tool, after breaks"; finished runs get it once at start; kept apart from the other copies so one bad file never keeps it out | test_al_consistent (4) |
| 3 | Fairness for channels (answers: share and turns; week mainly, day where the week cannot; coverage wins; a view first; same channels and language) | `webapp/channel_fair.py` and a Fairness section on Plan channels: the week, then the day; per group, time and share per channel, points from even, the furthest named in words at 10 points or more, the longest time on one channel in a day; breaks are not channel time and do not end a turn | test_al_fairness (9) |

## Reviews

- better-interface (better-accessibility, better-layout, better-writing, better-typography, better-colors,
  better-ui) and web-interface-guidelines on the Fairness section, the Schedules list line and the Timeline colour.
  - Fixed: "1 points" now reads "1 point".
  - Fixed: at phone width a time and its share broke over three lines ("21 / h 30 / (54%)"). They now stay on one line,
    with even-width figures, and the table scrolls sideways.
  - Measured: the white E on Email is 4.99:1. Email's hue is 22° from the "covered" teal.
- Live baseline on Plan channels, the Schedules page and the Timeline at 1440 and 320 px:
  - 200 with the CSP header, 0 console errors, 0 duplicate ids, 0 unnamed controls.
  - Load 77 to 442 ms in the lab.
  - The Schedules page scrolls 9 px sideways at 320 px. Bisected to the old Delete panel's tick label, which cannot
    wrap the long test workbook name "VERSIONED_CONSISTENT_week.xlsx". The same page with a shorter name fits; this
    was there before Phase AL.
- Security: no new route, form or POST. The engine's record only picks a file by its exact name inside the run's own
  folder. Its figures are escaped by the templates.

## Checks

- Website suite in two halves: 618 tests OK and 539 tests OK (1 skipped).
- Browser tests: 77 OK (the older phases' screenshots they rewrite were put back).
- Page review, every page at 360 and 1440 px in the dark and light looks: 0 problems.
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow, nothing logged. The same 2 "leaks" by design and
  the same 222 "None" words as before.
- Release gate (`run_tests.sh`, run inside the package build): GATE PASS, 77 suites, 1537 tests (2 skipped), engine
  untouched.
- Screens: `evidence/phase_al/screens` (the Timeline with Email in deep green, the Fairness section, a run's
  Schedules list with "Tool, more consistent"; 1440 and 390 px, dark and light).

## Known and left

- The Delete panel's tick label overflows by 9 px at 320 px with a long workbook name that has no spaces (from
  before this phase).
- Fairness counts the schedule's channel plan (the version and its unsaved draft), not the RTA's changes on the day.
- The C letter, white on Chat `#C2549F`, stays at 4.15:1 (the owner's colour; `#B04A90` would give 4.97:1).

## Package

`RC9_2_2_PRODUCTION_PACKAGE.zip`, 2693 files, 92.21 MB, sha256
`4281a5eeb81a5626adc7c79543cf64733d41c63eb6e7af0801666f6a07cc1a8a`, sent as AL_part_0 to AL_part_3. This file was
written after the build copied its files, so it is not inside the package.
