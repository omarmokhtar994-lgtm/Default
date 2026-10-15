# Phase AI: checks (2026-10-15, Egypt time)

© 2026 Omar Mokhtar. All rights reserved.

Built from the owner's list of 2026-10-15 (`REQUESTS.md`), the owner's answers the same day and the plan
`docs/superpowers/plans/2026-10-15-phase-ai-build.md` (its rulings are at the end of the plan). The owner said "go
ahead fix everything": built without samples; screens of the changed pages are in `screens/`. The engine is not
touched.

## What was built

| # | The owner's words | What changed | Test |
| --- | --- | --- | --- |
| 1 | "Drag and drop for breaks is lagging ... several places in the box are lagging and not working" | The interval board's rows hold all twelve columns (the last three hung outside their row), the drop outline has its own class (the old one took the upload box's padding, so rows grew under the pointer), and the drag follows the pointer with the time it moves to | test_ui_playwright: every visible cell of a row takes the drop |
| 2, 6 | "change the day start time ... on the same page ... keep it for all tabs"; "i dont need operating day to be something different than calendar day" | Times in and Day starts at are on the RTA, kept per program; the Timeline, the Interval board and Adherence show the 24 hours from the start; the other tabs work on the schedule's day with times in the zone; the read-only page is gone | test_ai_window, test_af_zones (re-pinned) |
| 6 | "break should show in the new time zone and can be changed but ... the time should be based the schedule default" | Every time shown or typed is in the zone picked; the server reads typed times back into the schedule's time; the log, undo and group posts keep the schedule's time | test_ai_window, browser test in New York from 16:00 |
| 3 | "exam leave ... not to be counted in Sutherland shrinkage but in client shrinkage"; "both" | An RTA status for the whole shift and a leave kind (TM then RTA); client shrinkage only by default; an approved request's Leave counts by its kind | test_ai_exam |
| 4 | "chsnnels not coloredd here" | The Timeline draws each person's channel stretches and the channel rows, and says when the schedule has no channel needs or the day no channel plan | test_ai_fixes |
| 5 | "no back button in wallboard" | Back to the RTA | test_ai_fixes |
| 7 | "i still csn dee same departments and names from another department" | The With suggestions list only people who can open the program (the department lists were already per program) | test_ai_fixes |
| 8 | "supervisor see everything based on accounts assigned ... both can download anything for saks" | Runs by program; other programs show only as running or waiting, with when a new run would start | test_ai_runs |
| 9 | "rest of week view in overall view is not organized" | One short row a day with Plan this day | test_ai_outlook, test_ag_overview (re-pinned) |
| 10 | "instead of endless scrolling they might have some pages" | Pages of 20: runs, changes today, overtime and VTO offers, decided requests, group posts | test_ai_pages |
| 11, 12 | "howlong is he logged in ... when i stand any where" | Logged in from the RTA's marks (a late login counts from when they came in); anywhere on a person's row shows the card | test_ai_fixes, test_af_hover (re-pinned) |

## Found and fixed on the way

- An approved Public holiday request counted as planned leave in Sutherland's shrinkage; it counts as a public holiday
  (the owner's formula of 2026-10-14).
- T10 named a helper the same as the week breaks pages' helper in one scope; Plan breaks would have broken. Found by
  pyflakes before any test ran it; fixed in 5162afb.
- Phase AG's minors: an approval a stopped server left half done is put back to the RTA at start; My week's swap
  finder says why nobody is listed; a two-week leave has its own test; one unused variable, one import.
- Found in the final review: a person can have two shifts in the RTA's 24 hours (from 20:00, a shift at 21:00 and the
  next day's at 19:00). Hovering the first bar showed the second shift's card, and hovering a channel showed the
  row's card even when the channel was on the other shift (also on a plain day, for a shift from the day before).
  Each bar now has its own card, and a channel shows the card of the shift under it. Tests: test_ai_window (two
  shifts in the window, as data and on the page) and a browser test on Phase V's channel day; each failed first.
- The 9 channel day tests that failed before Phase AH: they read the real clock and their Wednesday had passed. Their
  module stops the clock on the Tuesday before.

## Results

Times are Egypt time, 2026-10-15.

- Website suite, in two halves after the last code change to the server (5162afb): 552 tests OK and 500 tests OK
  (1 skipped), 07:20 to 07:39.
- Browser module (Playwright, 76 tests): 70 passed and 6 failed at 11:53. The 6 were found and fixed in 5617f04:
  three phone pages scrolled sideways by 462 px (a screen-reader-only table header sat outside its scroll box; every
  scroll box now holds its contents), and three screen tests read the real clock (they now stop it on the day they
  were written for). The 6 again: OK at 11:57.
- Every page at 360 and 1440 px, in the dark and light looks, signed in as the owner and as an associate: 0 problems
  (no error status, no console error, no sideways scroll on a phone), 11:59. Screens of the RTA in New York time from
  16:00 and in Cairo time are in `screens/`.
- Interface checklist (web-interface-guidelines) over the changed templates, CSS and JS: no findings.
- Route sweep (every route as admin, supervisor, planner, a planner without programs and signed out; bad values on
  every query; every POST empty, with garbage and without its token), 12:03: 872 requests, 0 exceptions, 0 server
  errors, 0 errors logged. Also reported, each checked:
  - 2 "leaks", the same two as in Phases AC and AD, both by design: a planner without programs sees a program's name
    in the New schedule picker (never its schedules), and supervisors open People to manage their own programs'
    planners.
  - 1 response over 1.5 s: a supervisor's coaching workbook download, 1.7 s (not changed since Phase AF); the next
    slowest page took 0.80 s.
  - 222 "odd" hits for the text `None`: all are the word None written on purpose (186 on the RTA's Language gaps tile,
    36 in the rest of the week's Short, Overtime needed and Days off to cancel columns), not a missing value.
- pyflakes over `webapp/*.py`: four unused imports, all older than Phase AI (`BreakRefused` in app.py, `Any` and
  `Optional` in channel_people.py, `DAYS` in exports.py). Left as they are (no change without a request).
- Final review of the whole Phase AI diff: a self-review (subagents run only when the owner asks).
