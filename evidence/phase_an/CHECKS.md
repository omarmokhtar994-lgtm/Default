# Phase AN: what was brought in and the checks

© 2026 Omar Mokhtar. All rights reserved.

Checks run Fri 16 Oct 2026, finished about 21:10 Egypt time, on the Phase AN tree (branch `ccr-90ec94cc-a37tqk`).
The decisions and rulings are in `REQUESTS.md`; the work came from ChatGPT's third delivery round ("Completed") and was
checked by Claude, not taken on trust: ChatGPT's own run had no browser and no release gate.

## What came in

| Area | What changed | Tests |
| --- | --- | --- |
| Time zones | Schedules and the zoned download convert each shift and break on its own date (clock changes); a source hour that repeats or does not exist is refused with a message; the RTA reads "now" in the schedule's own zone | `test_an_zones`, `test_an_clock_safety`, `test_an_correctness` |
| RTA clock change | Where one conversion offset cannot hold across yesterday, today and tomorrow, the RTA shows the schedule's own zone and says so; old cross-zone forms are refused before writing | `test_an_clock_safety` |
| Channels | Plan channels counts demand with no staff, overnight tails, fixed cover (language, Email Hours) and Sunday's cover from the week before | `test_an_correctness`, `test_an_repair` |
| Channel solver | Every channel solve runs in a bounded child process; a crash, a hang or a malformed answer keeps the draft (`webapp/channel_solver.py`) | `test_an_solver_process` |
| Fix channels | Same scope as AM (today's shifts); applied all or nothing in one transaction, one Undo | `test_an_repair`, `test_am_fix_channels` |
| Go-to search | Pages, programs and the roster are listed only when the role may open them | `test_an_routes`, `test_an_http` |
| Tools | `tools/validate_website_release.py` (one fail-closed validation entry), `tools/review_website_routes.py` (route audit); `protobuf==6.33.6` pinned | `test_an_route_audit` |

Not taken: the rewrite of `tests_staged/test_rc9_2_19_joint_solve_isolation.py` (REQUESTS ruling 2) and the `/proc` helper.
Owner's decisions kept: B (Fix channels as in AM), C (short manual blocks warn), D (no draft lock).

## Checks

- pyflakes: clean except the old unused imports named in the handoff.
- Website suite in two halves: 595 tests OK (1 skipped) and 658 tests OK. 1253 in all (AM: 1183).
- Browser tests: 77 OK.
- Page review, every page at 360 and 1440 px in the dark and light looks: 0 problems.
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow, nothing logged. The same 2 "leaks" by design and
  222 "None" hits that are the word None written on purpose (as in Phase AI and AM).
- Templates: 6 changed lines in 3 files; no inline script, style or handler; the new RTA notice is a native paragraph
  with `role="status"`.
- Security: the new POST guard runs after sign-in, permission and CSRF checks; Go-to now follows the permission map.
- Release gate: see the package line below.

## Known and left

- The RTA keeps wall-clock minutes; it cannot show both occurrences of a repeated hour (the fallback above is the safe
  answer, not a redesign).
- Different channel rules inside one window are refused for Fix channels and the repair tool; the planner works one
  calendar day at a time.
- The original missing-schedule incident still needs that run's input and logs.
- Chrome and the sandbox: ChatGPT could not run the browser tests; here they pass.
