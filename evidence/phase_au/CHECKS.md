# © 2026 Omar Mokhtar. All rights reserved.
# Phase AU: checks

Run on the final tree, 2026-10-21 (Egypt evening). What it built: `docs/HANDOFF.md`; the break shape rule and arms:
`BREAKS_RULE.md`; screens of the AR, AS and AT pages after the owner's feedback: `screens/` (made by `tools/screens.py`).

- Website suite, both halves: 792 + 717 tests, all pass (1 skipped).
- Browser tests: 85 pass, including the new Today and Weeks tabs, a break change for tomorrow, the RTA deciding on its tab
  and staying there, and the coaching search.
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow, 0 logged errors. Its two "leaks" are the same old
  tool assumptions as in Phase AP to AS (Home ignores the `program` query; a supervisor holds People by default).
- Defects found by the new "pages offer only what the role may use" test and the browser run, and fixed: Home offered
  New schedule and its week check to a team manager whose role may not start runs (the server refused it: a 403 in the
  console); the auto-breaks form was offered to a team manager on Week.
- Re-pinned with reasons in the tests: associates land on Today; the day card moved to My day; "My breaks today" is now
  "My day"; an upload is for the person's own programs (Phase AR).
- Leftovers added after that run, re-checked 2026-10-21 evening: website suite both halves OK after re-pinning two
  event-list tests (a sign-in is an event now) and one browser heading match ("People" now matched exactly, other headings
  contain the word); browser tests 85 (one re-pinned heading, rerun OK); route sweep 872 requests, 0 exceptions, 0 errors.
- Second walk, final tree 2026-10-21 night: website suite both halves OK (the first run of half 1 caught that the new zip
  check refused the fake workbooks the run tests upload; the check now leaves an unreadable zip to the workbook readers,
  `test_runs` 154 OK); browser tests 85 OK; route sweep 872 requests, 0 exceptions, 0 errors; accessibility tool
  `tools/a11y.py` 0 problems (two found and fixed: sideways scroll of the impact tables on a phone, supervisor chip contrast).
- Not run here: the release gate and package (the owner has not asked for the build yet).
