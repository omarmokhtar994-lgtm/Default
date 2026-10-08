# Phase M: the week view Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For one upload, or one program and week, show what was achieved in every interval of the week (the workbook's own interval, 30 or 60 minutes), where overtime is needed (associates needed for 100% and the hours), and where extra hours are available.

**Architecture:** `webapp/week.py` turns the validator's interval rows into the view (grid with folded no-demand hours, per-day share at 100%, the two tables, totals). A compact copy of the interval rows is kept in the run's stored figures (`metrics["intervals"]`), so the view works after the run's files are deleted; older runs get it from their files at startup. Pages: `/runs/<id>/week` and `/week?program=&week=` (the week's counted run, as on the program page), with program and week pickers.

**Spec:** Owner, 2026-10-08: "a view … review specific upload or program for specific week and it will show us the achieved per 30 mins or 60 mins for that program all over the week and table where overtime is needed with the count of associates needed to achieve each interval and another table with extra hours available per interval"; sample approved ("Awesome go ahead"): `evidence/phase_m/samples/sample_week_view.png`.

## Global Constraints

- Associates needed for 100% in an interval = ceil(required ÷ one person's productive share), the share being that interval's effective ÷ people on the floor (the validator's own figures); with nobody on the floor, the week's median share. Overtime = needed − on the floor (when positive); extra = on the floor − needed (when positive); hours = associates × interval length.
- Whole associates, so these differ from the program page's efficiency hours (fractions of a person); the page says so.
- Colours as the run page's wall (covered, 90–99%, under 90%, over the engine's over-staffing cap; before breaks has no over-staffing flag).
- Names never stored; the interval copy holds counts and times only.

## Review Focus

- A 60-minute workbook: one associate for one interval is 1 hour, rows every hour (`test_sixty_minute_week`).
- An interval with demand and nobody on the floor: needed comes from the week's median share, not a division by zero (`test_nobody_on_the_floor`).
- A week whose run's files expired: the view still shows from the stored copy (`test_week_view_survives_file_expiry`).
- A run finished before this phase (figures without intervals) whose files exist: gets the intervals at startup (`test_older_runs_gain_intervals`).
- A program and week with no counted run: the pickers stay and the page says no finished run (`test_unknown_week_says_so`).

---

### Task 1: `webapp/week.py`

**Produces:** `compact(rows) -> list[list]` (`[day_index, "HH:MM", required, after_eff, after_raw, before_eff, before_raw, severe]`); `view(intervals, side="after") -> dict` with `step`, `grid` (rows of cells or `{"fold": "02:00 to 16:30"}`), `days_at_full`, `short`, `extra` (each row `day, time, need, have, pct, people, hours`), `totals` (`active, full, overtime_hours, overtime_people, extra_hours, extra_people`).
- [x] Tests (`webapp/tests/test_week.py`, real run): `test_real_week_totals` (107 of 126; overtime 19 associates, 9.5 h; extra 49 associates, 24.5 h), `test_sunday_2130_needs_one_more` (need 4, have 3, 96%), `test_no_demand_hours_fold` ("02:00 to 16:30"), `test_before_breaks_view`, `test_sixty_minute_week`, `test_nobody_on_the_floor`.

### Task 2: stored, backfilled, shown

**Files:** `results.py` (`metrics()` adds `intervals`), `runs.py` (backfill runs whose figures lack intervals), `app.py` (`/runs/<id>/week`, `/week`), `templates/week.html`, links from the run page and the program page's week table, `app.css`; Test `test_runs.py`, `test_ui_playwright.py` (screens to `evidence/phase_m/screens`).
- [x] Tests: `test_week_view_for_a_run`, `test_week_view_by_program_and_week`, `test_week_view_survives_file_expiry`, `test_older_runs_gain_intervals`, `test_unknown_week_says_so`, `test_week_links_from_run_and_program_pages`, browser `test_week_view_page`.

### Finish

- [ ] Website suite, gate, package, push, send.
