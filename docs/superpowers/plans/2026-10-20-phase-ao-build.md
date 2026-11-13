# Phase AO: associate view, swaps, name lists, overtime after midnight, leave for weeks not yet planned. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task,
> inline (the owner's choice). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner's items 1 to 9 of 2026-10-20 with the answers given.

**Architecture:** Fixes in the existing modules (`day.py`, `swaps.py`, `leave.py`, `app.py` and templates); no engine
change. Merging LOBs (item 10) is Phase AP, after a sample.

**Tech Stack:** Flask, Jinja, SQLite, unittest, Playwright.

**Spec:** `evidence/phase_ao/REQUESTS.md`.

## Global Constraints

- CLAUDE.md: engine untouched; failing test first; strict CSP; sentence case; "Associate NN" names; copyright line;
  CSRF on every POST; no speculative behaviour change; Egypt time.
- Owner's answers: 1 My week based on the RTA (aux recorded on the RTA); 2 a full-week swap as recommended (the whole
  week, each day's shift or day off, one request, warnings per day); 3 B (store, warn, and mark the approved leave in
  a new version after a run; a name not on the roster is a warning, never a stop); names and team managers by program.

## Review Focus

1. Overtime after a shift that ends at 00:00 counts on the next day's floor, and a shift ending after 00:00 still does.
2. A swap offer that breaks a rule is shown with its warning and can be sent; approval shows the warning again.
3. A name list never shows another program's names; a name typed with other case or spaces is found.
4. Leave for a week with no schedule is never lost: stored, warned, and applied after the run, a missing name only warns.
5. My week of a week with no schedule says so, and never shows another associate's data.

---

### Task 1: Overtime after a shift that ends at 00:00

**Files:** `webapp/day.py` (`_segments`, `day_view`); test `webapp/tests/test_ao_midnight_overtime.py`.

- [ ] Failing test: a 15:00 to 00:00 shift with 60 minutes of overtime after; the next day's view has a lane segment for
  it (offset -1, end 60) with the overtime counted on the floor from 00:00 to 01:00; a shift ending at 23:00 gets none.
- [ ] `_segments(..., carried=frozenset())` keeps an offset -1 segment that ends at 0 when its name is in `carried`;
  `day_view` passes the names whose (-1, name) activities hold overtime past 1440.
- [ ] Run test_ao_midnight_overtime, test_overtime_side, test_day; commit.

### Task 2: Name lists and "not found"

**Files:** `webapp/app.py` (`_roster_names`, `_roster_problem`, `admin_users`), `webapp/templates/admin_users.html`,
`webapp/static/app.js`; test `webapp/tests/test_ao_names.py`.

- [ ] Failing tests: the roster-name list for GDI holds only GDI names; a name typed with other case or extra spaces is
  matched to the schedule's own spelling; the bulk team-manager select offers only team managers of the picked
  associates' programs.
- [ ] Implement; run test_ag_associates, test_ak_team; commit.

### Task 3: Swap offers with warnings

**Files:** `webapp/swaps.py` (`candidates`, `offer`, `check`), `webapp/app.py` (`me`, `me_swap`), `webapp/templates/me.html`;
test `webapp/tests/test_ao_swaps.py`.

- [ ] Failing tests: a candidate failing a rule is listed with `ok` False and its problems; a candidate with no account is
  listed with that said; `offer` with `allow_warnings` keeps the request and stores the warnings for the approvers.
- [ ] Implement; run test_ag_swaps; commit.

### Task 4: A full-week swap

**Files:** `webapp/swaps.py`, `webapp/app.py`, `webapp/templates/me.html`; test `webapp/tests/test_ao_week_swap.py`.

- [ ] Failing tests: `week_candidates(program, week_start, name)`; `offer_week` makes one request for the week; approval
  swaps each day's cell as one new version; a day that breaks a rule carries its warning.
- [ ] Implement; commit.

### Task 5: My week

**Files:** `webapp/app.py` (`me`), `webapp/templates/me.html`; test `webapp/tests/test_ao_my_week.py`.

- [ ] Failing tests: `?week=` shows another week that has a schedule; the weeks offered are this week and later weeks
  with a schedule kept; each day lists breaks, lunch and the aux, meetings and coaching recorded on the RTA; a week with
  no schedule says so.
- [ ] Implement; commit.

### Task 6: Leave for a week with no schedule

**Files:** `webapp/leave.py`, `webapp/store.py` (no new table if the request row can say), `webapp/runs.py` or
`webapp/schedules.py` (after a run), `webapp/exports.py`, templates; test `webapp/tests/test_ao_leave_later.py`.

- [ ] Failing tests: approved leave on a week with no schedule stays stored as waiting for the week; when a run for that
  week finishes, a new version marks the Leave and is set in use, and the week page and run page warn
  "approved leave not in the engine's schedule"; a name not on the roster only warns; Exports lists it.
- [ ] Implement; commit.

### Task 7: Reviews, checks, package

- [ ] Website review skills on the changed pages; security on the new POSTs; suite, browser tests, page review, sweep,
  gate in the package; CHECKS.md, release notes, handoff; parts; report.

## Rulings while building (each with what it costs if wrong)

Recorded in `.superpowers/sdd` and copied here at the end.
