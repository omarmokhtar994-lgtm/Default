# Phase AM: fix the channels in one click, download in the zone picked, a version pick on Weeks, percentages for before-breaks schedules. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task,
> inline (the owner's choice). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner's four items of 2026-10-16 with the answers given.

**Architecture:**
- Download: a moved copy of the workbook made at download time.
- Percentages: `version_figures(run)` picks the version whose own check the Runs list, Weeks and the run page read.
- Weeks: a `v` parameter that both the grid and Hours needed (through `DayBook.page(..., version_id=)`) follow.
- Fix channels: `DayBook.channel_fix_plan`, `channel_plan.plan_day(..., carry_in=)`, and `DayBook.apply_channel_fix`
  as one bulk journal entry.

**Tech Stack:** Flask, Jinja, SQLite, OR-Tools CP-SAT, unittest, Playwright.

**Spec:** `evidence/phase_am/REQUESTS.md`.

## Global Constraints

- CLAUDE.md: engine untouched (the website's channel planner is not the engine); failing test first; re-pin only with
  the reason; strict CSP; sentence case; "Associate NN" names; the copyright line; CSRF on every POST; Egypt time.
- Fix channels (owner): the channel planner re-plans channels from now to the end of the shifts, for people on
  shift and present.
  - Breaks never move. Coverage first; fairness decides between plans that cover the same.
  - The changes show first, then one Apply and one Undo.
- Figures (owner): read the version in use. With none in use, read the engine's own figures, as now. Ruling: when the
  engine has none, read the run's shown version.

## Review Focus

1. Fix channels never changes a minute before now: a change starting before now is refused at Apply ("has
   passed: open Fix channels again"). Test in Task 4.
2. A person who is absent all shift, or away, gets no channel while away. Test in Task 4.
3. A version picked on Weeks that belongs to another program or week is refused (404), not shown. Test in Task 3.
4. A download in another zone keeps a shift crossing midnight readable (marked as on the page), and the stored
   workbook is unchanged. Test in Task 1.
5. A run with versions but no engine figures and none in use still shows a percentage, marked "before breaks" when
   the version has no breaks. Test in Task 2.

---

### Task 1: Download in the zone picked

**Files:**
- `webapp/templates/schedules.html`: the Download link carries `tz` when the page shows another zone.
- `webapp/app.py` (`schedule_download`): with a `tz` other than the schedule's own, it sends a moved copy.
- `webapp/versions.py`: a new `zoned_copy(src: Path, dst: Path, minutes: int) -> None`. It rewrites every shift cell
  and break time with `clock.moved_text` and leaves OFF and Leave as they are.
- Test: `webapp/tests/test_am_zone_download.py`.

- [ ] Failing tests:
  - Downloaded with `tz=Europe/London` from an Egypt schedule, "Associate 001" Wed reads the moved text the page
    shows (`zone_cell`), and a break time moves by the same minutes.
  - The file name ends "_London time.xlsx".
  - Without `tz`, the bytes equal the stored workbook.
  - The stored workbook is unchanged after a zoned download.
- [ ] Implement; run with test_ak_schedule_zone, test_versions; commit.

### Task 2: Percentages from the version (in use, else the engine's, else the version shown)

**Files:**
- `webapp/app.py`: new `_version_figures(run) -> Optional[dict]`. It returns `version_summary(checks)` of the
  version in use. With none in use, it returns the engine summary (`queue.summary`, as now). With no engine summary,
  it returns the version `ScheduleBook.week_list` shows for the run, plus `version_label` and `breaks_planned`.
  - The Runs list (`summaries` in the dashboard), the run page's figures and `_week_page`'s grid read it.
  - The Weeks grid's "before breaks" side follows a version that has no breaks.
- `webapp/templates/dashboard.html`: the Covered cell says "before breaks" when `breaks_planned` is false.
- Test: `webapp/tests/test_am_figures.py`.

- [ ] Failing tests:
  - A run whose files hold only a before-breaks schedule shows a percentage on Home with "before breaks", and on
    Weeks a grid.
  - Setting its "Plan breaks" version in use shows that version's after-breaks percentage on Home and Weeks.
  - A full run with nothing in use shows the engine's figures as before.
- [ ] Implement; run with test_runs, test_week, test_schedules_by_week; commit.

### Task 3: Weeks: pick the version

**Files:**
- `webapp/attendance.py`: `DayBook.page(..., version_id: Optional[int] = None)` reads that version for the day when
  it covers the day and program; else `ValueError`.
- `webapp/app.py` (`week_page`): `v`, a version of that program and week (else 404). The grid reads `v`'s checks.
  Hours needed "As planned" passes `version_id=v`; "As recorded" ignores `v`.
- `webapp/templates/week.html`: a "Version" select listing the week's versions, the one in use first. Each is labelled
  with its run, its label and "breaks planned" or "before breaks". It sits with the basis toggle; JS
  `data-autosubmit` with a noscript button.
- Test: `webapp/tests/test_am_week_version.py`.

- [ ] Failing tests:
  - The select lists the week's versions.
  - `v=<tool_before>` shows the grid and Hours needed from that version.
  - A `v` from another week or program answers 404.
  - "As recorded" with `v` still reads the version in use.
- [ ] Implement; run with test_week, test_needed; commit.

### Task 4: Fix channels in one click on the RTA

**Files:**
- `webapp/channel_plan.py`: `plan_day(..., carry_in: Optional[Dict[str, str]] = None)`, passed to `_solve`. A run
  that starts at a person's first slot with the channel in `carry_in[name]` is a continuation: the minimum-stretch
  rule does not apply to it, and a different channel at the first slot costs `SWITCH`. Load cpsat-engine-modeling
  first.
- `webapp/attendance.py`:
  - `channel_fix_plan(program, on, now: Optional[int] = None) -> Dict` returns `{"changes": [(name, lo, hi,
    letter, was)], "short_before": {letter: hours}, "short_after": {...}, "note": str, "seconds": float}`.
  - People: today's shifts (offset 0) with status Present, from the next quarter hour after now to the shift's end.
    Their breaks, away time and activities other than overtime are fixed breaks. Last night's people (offset -1)
    count through `before` with their current channels.
  - `carry` is the minutes per channel this week (fair spread on).
  - `apply_channel_fix(program, on, changes, user_id, now=None) -> int`: one bulk entry labelled "Fix channels
    changed N stretches". Each change goes through `channel_move`; a change starting at or before now is refused.
- `webapp/app.py`: `GET /day?view=channels&fix=1` shows the preview; `POST /day/channels/fix` applies hidden
  `name|lo|hi|letter` items.
- `webapp/templates/day.html`: on the Channels tab, a "Fix channels" button, the preview list ("Associate 003: Chat
  15:00 to 16:30, was Phone"), shortfall before and after per channel, "Apply all N" and Cancel.
- Test: `webapp/tests/test_am_fix_channels.py`.

- [ ] Failing tests (channel fixture of test_ai_fixes, a fixed "now"):
  - With Phone short from 18:00, the plan proposes changes that cut the Phone shortfall, and none starts before now.
  - Apply records them as one action; one Undo takes all back.
  - An absent person gets no change.
  - A break is not given a channel.
  - With `carry_in`, a person already on Phone who can stay on it is not changed.
  - The planner unit test: `carry_in` lets a 15-minute continuation stand where the minimum stretch is 60.
- [ ] Implement; run with test_channel_plan, test_channel_day, test_ai_fixes; commit.

### Task 5: Reviews, checks, package

- [ ] Website review skills on the changed pages; security on the new POST; the fixes, each with its test.
- [ ] Suite, browser tests, page review, sweep, gate in the package; CHECKS.md; release notes; handoff; parts;
  report.

## Rulings while building (each with what it costs if wrong)

- Fix channels plans today's own shifts; last night's people are held as they are and counted; tomorrow's early
  shifts are not planned. Cost: a second pass for a window that starts late.
- Channels change on 15-minute steps from the next quarter hour. Cost: up to 14 minutes left as they are.
- Overtime minutes count as on shift; other activities and away time are held as breaks. Cost: one rule.
