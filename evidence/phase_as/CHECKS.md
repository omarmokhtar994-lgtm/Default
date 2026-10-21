# © 2026 Omar Mokhtar. All rights reserved.
# Phase AS: checks

Run on the final tree, 2026-10-21 (Egypt time evening). Details of what the phase built: `REQUESTS.md`, `RELEASE_NOTES.md`.

- Website suite, both halves: 688 + 769 tests; one failure, `test_runs.TheProgramAccess.test_own_programs_and_runs_open`,
  which still expected an upload into another program to work. Re-pinned in Phase AR (owner: each program keeps its own
  uploads) with the reason in the test; rerun OK.
- Browser tests: 82 OK.
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow, 0 logged errors. Two "leaks" are old-tool assumptions:
  Home ignores the `program` query (nothing of that program shown, covered by the walls crawl), and a supervisor holds
  the People permission by default since Phase AK (covered by the role-matrix test).
- Release gate: 1551 tests, 2 skipped, PASS.
