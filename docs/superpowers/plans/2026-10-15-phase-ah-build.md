# Phase AH: hours needed, target colours and the 10-minute cushion. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colour every interval by the week's target with a tight mark, add the Weeks page's Hours needed table with
suggestions and an Excel export, show the RTA's records on the Schedules page, and make Rescue the day and Fix breaks
aim for 10 minutes over the target.

**Architecture:** One rule in `day.py` (band, minutes over the target, tight, the safe floor) used by every page. A
new `needed.py` builds the table from the DayBook's own day pages (as recorded, or as planned with the records left
out) and writes the workbook. Rescue's CP-SAT objective and Fix breaks' greedy score gain the safe count.

**Tech Stack:** Flask, Jinja, SQLite, vanilla JS, openpyxl, OR-Tools CP-SAT, unittest, Playwright.

**Spec:** `evidence/phase_ah/SAMPLES.md` (the approved sample and the owner's answers of 2026-10-15) and
`evidence/phase_ah/samples/` (ah01 screens, ah02 export).

## Global Constraints

- CLAUDE.md rules: engine untouched, failing test first, no weakened validation, re-pin only where the owner changed
  the contract (say why in the test), strict CSP (no inline script, style or handlers), sentence case, made-up
  "Associate NN" names, the copyright line in every website file, Egypt time.
- Colours: 100% or more teal (`ok`/`covered`); from the target to 99% amber (`warn`/`short`); below the target red
  (`bad`/`gap`). "At the target" keeps today's count: the page's figure (one decimal) at or over target x demand.
- Tight: amber and under 10 minutes over the target, counted in exact person-minutes (5-minute ticks where the page
  has them). `CUSHION = 10`. Safe: at the target with 10 minutes or more over it, or at 100% (the cushion never asks
  for more than demand).
- Hours needed: to 100% or to the safe level (the RTA's drop-down, `aim=full|target`), in exact person-minutes,
  rounded up to the quarter hour.
- Fix breaks keeps its aim: the weakest interval first.

## Review Focus

1. A week whose kept target is 100%: no amber band, nothing tight, Hours needed to target equals to 100%.
2. Intervals of 15 or 30 minutes: the cushion is still 10 person-minutes per interval, capped at demand.
3. A week with a missing input workbook on one day: the table shows that day empty and says why, never a 500.
4. Today: suggestions only for shifts still ahead; past days show figures, no suggestions.
5. `basis`, `aim` and `show` query values outside their lists fall back to the defaults (recorded, full, all).

---

### Task 1: One rule for an interval's standing

**Files:** Modify `webapp/day.py` (constants, `at_target`), `webapp/attendance.py` (`DayBook.page` recolours the
view's cells). Test: `webapp/tests/test_ah_rule.py`.

**Interfaces — Produces:**
- `CUSHION = 10`
- `band(now: float, required: float, target: float) -> str` ("none", "ok", "warn", "bad")
- `minutes_over(cell: dict, target: float) -> float`: exact person-minutes over target x demand (from `slots`).
- `safe_level(required: float, target: float, step: int) -> float`: min(required, target x required + CUSHION / step).
- `at_target(cells, target)` cells gain `cls`, `tight`, `over`; the result gains `safe` (count) and `tight` (count).
- `DayBook.page` view cells: `cls` by `band`, plus `tight` and `over`.

- [ ] Tests: 91% of 5 at 60 minutes with 3 minutes over is warn and tight; 4.8 of 5 (18 minutes over) is warn, not
  tight; 100% is ok; below 90% is bad; target 1.0 has no warn; at 15 minutes the safe level is capped at demand;
  `at_target` counts unchanged, `safe` and `tight` counted; a page's cell for a sick-heavy hour is bad only below the
  week's target (the old rule painted any interval within one person amber).
- [ ] Run, watch fail; implement; run; commit.

### Task 2: The colour rule on every page

**Files:** `webapp/week.py` (`view(..., target=0.9)`), `webapp/results.py` (`_cell_class` with the target),
`webapp/break_plan.py` (strip by the target), `webapp/day.py` (`board(view, target)`: states `good`, `under`,
`short` with `tight`; ticks by the target), `webapp/app.py` (pass the week's target: kept, else the workbook's own),
templates `week.html`, `_macros.html`, `breaks.html`, `day.html`, `_target_tile.html`, `overview.html`,
`day_zoned.html`, `wallboard.html`, `static/app.css` (the tight mark and the `under` state).
Test: `webapp/tests/test_ah_colours.py`; re-pin old 90%/within-one-person pins with the owner's reason.

- [ ] Tests: `week.view` with target 0.8 paints 85% amber (was red); legends say the week's target, not "90 to 99%";
  board states for below target, under 100% and full; the achievement strip has three colours and a tight mark;
  pages render with no inline style.
- [ ] Run, fail, implement, run, commit.

### Task 3: Rescue the day aims for 10 minutes over the target

**Files:** `webapp/rescue.py` (a `safe` flag per interval; objective: most safe, then most at the target, then
fewest given up, fewest moves, least moving), `webapp/attendance.py` (`rescue_plan` confirms the gain on
(safe, at the target) and says how many more have 10 minutes to spare). Load cpsat-engine-modeling first.
Test: `webapp/tests/test_ah_cushion.py`.

- [ ] Known-answer day where the old model leaves an interval at the target by 5 minutes and a move gives it 10:
  new answer safe; the TheModel tests in `test_rescue.py` still pass unchanged.
- [ ] Probe both fixtures again (scratch audit scripts): no rule broken; record before/after in CHECKS.
- [ ] Commit.

### Task 4: Fix breaks keeps the cushion

**Files:** `webapp/day.py` (`replan(view, inputs, now=0, rounds=400, target=None)`: score (tightest, safe count,
-hours short); before/after gain `safe`), `webapp/attendance.py` (`DayBook.replan` passes the target), `day.html`
(the result names intervals with 10 minutes to spare). Test: `test_ah_cushion.py`.

- [ ] Known-answer day where two placements give the same tightest buffer and only one leaves 10 minutes over the
  target: the new answer takes it; without a target the old result is unchanged.
- [ ] Commit.

### Task 5: Hours needed on the Weeks page

**Files:** Create `webapp/needed.py`; modify `webapp/attendance.py` (`page(..., recorded=True)`;
`dayoff_plan(page, after=0, aim=None)`), `webapp/day.py` (`dayoff_proposals(..., aim=None)`), `webapp/app.py`
(`week_page` builds the table for the week in use), `templates/week.html`, `static/app.css`.
Test: `webapp/tests/test_ah_needed.py`.

**Interfaces — Produces:** `needed.week_table(days, target, aim, show) -> dict` with `rows` (folded runs and rows of
seven cells: `cls`, `tight`, `pct`, `hours`, `fix`), `totals` per day, `counts` (all, ot, dayoff), `cards` per day.

- [ ] Tests: fold, quarter-hour hours rounded up, fix tags (Day off, OT, Day off + OT), aim target smaller than full,
  planned basis ignores a sick mark, filters, bad query values fall back, the page renders the panel.
- [ ] Commit.

### Task 6: Download the table

**Files:** `webapp/needed.py` (`workbook(table, title) -> bytes`), `webapp/app.py` (`/week/hours-needed.xlsx`).
Test: `test_ah_needed.py`.

- [ ] Tests: same cells and fills (D5F2EE, FBE9C9, F8D3D0), tight said in the cell, a "What to do" sheet, access
  checked (403 for a program the person cannot open).
- [ ] Commit.

### Task 7: The Schedules page shows the RTA's records

**Files:** `webapp/app.py` (`run_schedules`: the in-use row's recorded figure), `templates/schedules.html`.
Test: `test_ah_needed.py`.

- [ ] Test: after a sick mark the in-use row says one fewer at the target "as recorded on the RTA"; the schedule
  file's figure is unchanged.
- [ ] Commit.

### Task 8: Browser check, suite, gate, package

- [ ] Playwright: Weeks (both looks, 360 px phone), RTA, Overview, export download; no console errors, no sideways
  scroll. Screens in `evidence/phase_ah/screens/`.
- [ ] Full website suite, `run_tests.sh` gate, package, `evidence/phase_ah/CHECKS.md`, push, report.
