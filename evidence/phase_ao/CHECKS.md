# Phase AO: what changed and the checks

© 2026 Omar Mokhtar. All rights reserved.

Checks run Wed 21 Oct 2026 on the Phase AO tree (branch `ccr-90ec94cc-a37tqk`). Requests and answers are in
`REQUESTS.md`; the engine findings are in `ENGINE_LANGUAGE_WINDOW.md`. The engine is untouched.

## What changed

| Area | What changed | Tests |
| --- | --- | --- |
| Overtime after 00:00 | Overtime after a shift that ends at 00:00 shows on the next day and counts on its floor | `test_ao_midnight_overtime` |
| Names | Name lists and team manager lists follow the programs picked; names are read from the last 4 kept weeks and matched without regard to case and spaces | `test_ao_names`, browser `ThePeoplePickersInTheBrowser` |
| Swaps | A colleague who breaks a rule is listed with the warning and can be offered; the warning shows again at approval; the reason for an empty list is said | `test_ao_swaps` |
| Full-week swap | One request swaps each remaining day of the week; Leave, past, same-shift and both-off days stay | `test_ao_week_swap` |
| My week | A week picker (this week and later weeks with a schedule); each day shows breaks, lunch and the RTA's aux | `test_ao_my_week` |
| Leave, no schedule yet | Approved leave is stored; after a run for that week it is marked Leave in a new version in use; a missing name only warns; listed in Exports | `test_ao_leave_later` |
| Web workbooks | Optional row "Break Set For Shifts Of 11 Hours Or More" (`15, 30, 15, 15`) in the example and blank input workbooks | `test_ao_web_workbook_breaks` |

Re-pinned tests (each says why in the test): `test_ag_associates`, `test_ag_swaps`, `test_ag_leave`,
`test_rc9_2_57_web_workbooks`, browser `ThePhaseADInTheBrowser` (clock-dependent, now next week).

## Checks

- Website suite in two halves: 616 OK (1 skipped) and 677 OK. 1293 in all (AN: 1253).
- Browser tests: 79 OK.
- Page review, every page at 360 and 1440 px, both looks: 0 problems.
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow, nothing logged. Same 2 "leaks" by design and 222
  "None" hits that are the word None on purpose (as in AN).
- Templates: no inline script, style or handler in the added lines; every new POST form carries the CSRF token and
  runs after sign-in and permission checks; names are escaped by Jinja.
- Release gate: GATE PASS, 77 suites, 1537 tests (2 skipped) inside the staged package.

## Rulings

See `.superpowers/sdd/.../progress.md` lines marked Ruling; the main ones: names read from 4 kept weeks; swap
columns added by additive migration; coaching means the RTA's aux plus breaks, lunch and overtime; approved leave for
a later week is applied as in use; a week swap leaves Leave, past, same-shift and both-off days alone.

## Known and left

- Planned future coaching is not held by the site (only what the RTA records).
- "Name not found": the cause found is fixed; no example from the owner yet.
- Phase AP (merging LOBs, hours per channel, per-associate daily download) is next, with a sample first.
