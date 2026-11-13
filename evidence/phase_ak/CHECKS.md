# Phase AK: what was built and the checks

© 2026 Omar Mokhtar. All rights reserved.

Checks run on code commit 9886534 (website code; later commits change only a test's pinned words, the release notes
and the check tools), Thu 15 Oct 2026, finished about 22:45 Egypt time. Tools: `evidence/phase_ak/tools/` (Phase AJ's,
with the review server's TM account made a Team manager, plus `ak_screens.py` and `channel_screens.py`).

## What was built

| # | Owner's item | What changed | Tests |
| --- | --- | --- | --- |
| 1 | Phone and Email hard to read on the Timeline (answer: option D) | Phone `#1A47A8`, Chat `#C2549F`, Email `#A6D96A` on a grey bar; P, C, E letters on stretches of 30 minutes or more that no break covers, kept upright on the stretched track by app.js and hidden from screen readers | test_ak_colours (8); re-pinned with the reason: test_markup_xy (the approved Email colour) |
| 2 | No "Times in" on the Schedules tab (answer: the schedule page) | `/runs/<id>/schedules` has Times in; shifts show moved, marked the day before or the next day; shifts are changed only in the schedule's own zone (buttons rest, a link goes back) | test_ak_schedule_zone (4) |
| 3 | Fix breaks, Rescue the day and Change several breaks on the 24 hours from "Day starts at" | The tools run on the Timeline's window moved to start at minute 0 (`webapp/window_tools.py`), with a channel hold over the window's days; each move keeps its shift's own date; one Undo | test_ak_window_tools (8) |
| 4 | Team manager accounts and associates assigned to them | New Team manager role; a pick per associate on People and a form for several at once; only an active team manager of the associate's programs | test_ak_team_managers (8) |
| 4 | Approvals by team manager, backups, both team managers for swaps, where a request waits | `webapp/approvals.py`; leave and swaps read it; per-side approval on swaps; "Waiting for …" on Requests and My week, grouped per team manager | test_ak_approvals (12); re-pinned with the reason: test_ag_leave, test_ag_swaps, test_errors |
| 5 | What each role may see and do, adjustable | `webapp/permissions.py` (14 permissions, defaults keep today's behaviour), checked on the server before every mapped page and change, menu shows only what is allowed, admin page Roles; putting every role back to the defaults asks for a tick | test_ak_roles (10) |

## Reviews

- web-interface-guidelines on the changed templates, CSS and JS: the Timeline letters are hidden from screen readers.
- better-interface (better-accessibility, better-layout, better-writing, better-typography, better-colors, better-ui):
  - Fixed: Roles' "Back to the defaults" acted at once with no confirmation; it is now its own form with a required
    "I understand" tick (test_back_to_the_defaults_needs_the_tick).
  - Fixed: two buttons named "Save" in each associate's row; the new one says "Save team manager".
  - Left for the owner: the C letter, white on Chat `#C2549F`, measures 4.15:1, under WCAG's 4.5:1 for small text.
    `#B04A90` would measure 4.97:1. The colour is the owner's option D, so it was not changed.
  - Checked and clear: the People table at 320 and 390 px scrolls sideways to every control (overflow auto); every
    keyboard stop on Roles and People shows a focus ring.
- web-quality-audit, accessibility, best-practices, performance, core-web-vitals (Playwright, no Lighthouse here) on
  Roles, People, Requests, a schedule in London time and the Timeline, Fix breaks, Rescue and Change several breaks
  from 07:00, at 1440 and 320 px: every page 200 with the CSP header, 0 console errors, 0 duplicate ids, 0 unnamed
  controls, `lang="en"`, one h1, no sideways page scroll, CLS 0, LCP 92 to 476 ms (lab, local). A checkbox click
  reaches the next frame in 9 ms; the letters' resize work takes 0.3 ms (45 letters, 26 rows). Field data is not
  available for an internal tool.
- security-and-hardening while building; security-review of the branch: no findings. Every POST route is guarded
  by the permission map, `admin_required` or the approval checks; CSRF on every new form; queries parameterised.

## Checks

- Website suite in two halves: 614 tests OK and 530 tests OK (1 skipped), after one AG swap test was re-pinned to the
  grouped "Waiting for a team manager (Associate 007 and Associate 014)." (the first run failed only there).
- Browser tests: 77 OK (the older phases' screenshots they rewrite were put back).
- Page review, every page at 360 and 1440 px in the dark and light looks: 0 problems.
- Route sweep: 872 requests, 0 exceptions, 0 server errors, 0 slow, nothing logged; the same 2 "leaks" by design
  (a planner without programs sees a program name in the New schedule picker; a supervisor opens People) and the same
  222 "None" words as Phase AI.
- Release gate (`run_tests.sh`, run inside the package build): GATE PASS, 77 suites, 1537 tests (2 skipped), engine
  untouched.
- Screens: `evidence/phase_ak/screens` (Roles, People, Requests as admin and as team manager, a schedule in London
  time, Fix breaks from 07:00, the Timeline with channels in the three looks; 1440 and 390 px).

## Known and left

- `/admin/users/team` stops with 403 at the first associate outside the user's programs and keeps those set before
  it. Only a hand-made request can do this; the page lists only associates the user manages.
- The decide message still says "Approved by the TM: the RTA decides next." while the pages say "team manager".
- From earlier phases, unchanged: one attendance box for a row holding two shifts in the RTA's 24 hours; three old
  unused imports.

## Package

`RC9_2_2_PRODUCTION_PACKAGE.zip`, 2663 files, 88.89 MB, sha256
`708aa29419e5a543e0694aa066e752804e99ffe8202b47203f31c62d027d1afd`, sent as AK_part_0 to AK_part_3 (26 MB each, the
last 10.9 MB). It is larger than AJ's (79.64 MB) by this phase's screens, samples and tools. This file was written
after the build copied its files, so it is not inside the package.
