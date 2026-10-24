# Phase AP: merged LOBs, hours per channel, per-associate daily download. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task,
> inline (the owner's choice). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sample ap01, approved by the owner on 2026-10-21 (A to D, "one workbook"): a merged view of the LOBs of one
program on the RTA, Week and Schedules pages; scheduled hours per channel per day and per week; a daily view per
associate downloaded from the RTA.

**Architecture:** A "unit" is a LOB key (`ProgramBook.tree()` lists a program's `units`). `?merge=1` on a page means
"every unit of this unit's program that the person may open and that has a schedule that day". Pure helpers in new
modules (`webapp/merge.py`, `webapp/channel_hours.py`, `webapp/daily_views.py`) do the arithmetic; the routes only
gather each unit's own view. No engine change.

**Tech Stack:** Flask, Jinja, openpyxl, unittest, Playwright.

**Spec:** `evidence/phase_ap/REQUESTS.md`, sample `evidence/phase_ap/samples/ap01_merged_lobs.html`.

## Global Constraints

- CLAUDE.md: engine untouched; failing test first; strict CSP; sentence case; "Associate NN" names; copyright line;
  CSRF on every POST; no speculative behaviour change; Egypt time; no real names.
- Owner's answers: same program only; edits on the merged view go through to each person's own LOB; the zone is the
  one picked in "Times in"; D is one workbook with a sheet per associate.
- A merged view needs one interval length. LOBs with different intervals are refused with a message that names them.

## Review Focus

1. Merging never mixes programs, and never shows a LOB the person may not open.
2. A LOB uploaded in another zone lands on the right clock hour of the picked zone (summer time included); a clock-change
   window the existing RTA cannot hold falls back with a message, never a guess.
3. An edit on the merged view (attendance, break, overtime) is saved on that person's LOB, in that LOB's own time.
4. Totals equal the sum of the LOBs' own totals (requirement, staffed, shrinkage, hours per channel).
5. The daily download holds only people the viewer may see, with the day's RTA changes, and no other program's names.

---

### Task 1: Hours per channel (pure)

**Files:** Create `webapp/channel_hours.py`; test `webapp/tests/test_ap_channel_hours.py`.
**Interfaces — Produces:** `day_hours(view) -> Dict[str, float]` (hours by channel letter from a day view's
`channels.runs`); `week_hours(days: List[Optional[view]]) -> {"rows": [{"letter","name","days":[h x7],"total"}], "total": [...]}`.
- [ ] Failing test: a day view with one person on Phone 09:00 to 11:00 and Chat 11:00 to 12:30 gives Phone 2.0, Chat
  1.5; seven days sum per channel and in an all-channels row; a day with no channel plan gives `{}` and the week says
  "no channel plan" for it.
- [ ] Implement; commit.

### Task 2: Hours per channel on the RTA, Schedules and Exports

**Files:** `webapp/app.py` (`_day_body`, `run_schedules`), `webapp/templates/day.html`, `schedules.html`,
`webapp/exports.py`, `exports.html`; test `webapp/tests/test_ap_channel_hours_pages.py`.
- [ ] Failing tests: the RTA Timeline tab shows the day's hours per channel; the Schedules page shows the week table;
  Exports offers kind `channel_hours` as CSV with the week's rows.
- [ ] Implement; commit.

### Task 3: Merge core (pure)

**Files:** Create `webapp/merge.py`; test `webapp/tests/test_ap_merge.py`.
**Interfaces — Produces:** `merge_intervals(rows_by_unit: Dict[str, List[list]]) -> List[list]` (sums columns 2 to 6
by day and time, ORs the last); `shift_view(view, by) -> view` (every time moved `by` minutes);
`merge_views(views: Dict[str, view]) -> view` (cells summed, lanes kept with `lob` set, tiles recounted, channels
rows and runs joined, languages summed); `same_interval(views) -> None` raising `ValueError` naming the LOBs.
- [ ] Failing tests for each: two units' interval rows sum; two day views with one shifted by 180 minutes merge so a
  cell holds both LOBs' staff and requirement; tiles equal the sum; lanes carry `lob`; unequal intervals refuse.
- [ ] Implement; commit.

### Task 4: Merged Week and Schedules

**Files:** `webapp/app.py` (`week_page`, `_version_week`, `run_schedules`), `webapp/templates/week.html`,
`schedules.html`; test `webapp/tests/test_ap_merge_week.py`.
- [ ] Failing tests: `/week?program=<unit>&merge=1` shows one grid built from every unit of the program in the picked
  zone; the View pick appears only when the program has two or more units the person may open; the merged target is the
  units' targets weighted by requirement and the page says so; Schedules shows the merged week totals for the run's week.
- [ ] Implement; commit.

### Task 4b: Merged RTA day

**Files:** `webapp/app.py` (`day_page`, `_day_body`), `webapp/templates/day.html`; test
`webapp/tests/test_ap_merge_day.py`.
- [ ] Failing tests: `/day?program=<unit>&merge=1` shows one requirement, one staffed count, shrinkage, a LOB chip per
  person and the View pick; Timeline, Interval board, Adherence and channel view work merged; other tabs say "Pick one
  LOB for this tab"; a person's forms post their own LOB as `program`; a posted break or absence lands on that LOB.
- [ ] Implement; commit.

### Task 5: Daily views download

**Files:** Create `webapp/daily_views.py`; `webapp/app.py` (route `/day/daily-views.xlsx`), `day.html`; test
`webapp/tests/test_ap_daily_views.py`.
- [ ] Failing tests: the workbook has one sheet per associate on the view (merged or one LOB), each with shift, breaks,
  lunch, aux and overtime recorded that day, in the zone picked; sheet names are valid and unique; needs the RTA view
  permission; people outside the viewer's programs are absent.
- [ ] Implement; commit.

### Task 6: Reviews, checks, package

- [ ] Template review, security review of the new routes, suite halves, browser tests (add a merged-view class),
  page review, sweep, gate in the package; CHECKS.md, release notes, handoff; parts; report.

## Rulings while building (each with what it costs if wrong)

Recorded in `.superpowers/sdd/2026-10-21-phase-ap-build/progress.md` and copied here at the end.
