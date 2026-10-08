# Phase N: schedule versions, manual edits, and the day Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scheduler edits a run's schedule (after or before breaks) shift by shift; each edit is checked by the independent validator, warned about (Yes/No with a reason) and kept as a new version marked red or yellow where it breaks something; one version is "in use" for the week and every version downloads as Excel. On the day page, attendance and actual breaks (5-minute steps) for the schedule in use show, per interval, who is on the floor against what is needed, plus or minus in hours, and language coverage.

**Architecture:** `webapp/versions.py` reads and edits schedule workbooks (Schedule, Final Schedule, Break Schedule tabs) and runs `engine/tools/independent_validator.py` on them (about 3 s), turning its findings into plain problems with severity and cells. `webapp/schedules.py` keeps versions (SQLite rows + workbook files under `DATA_DIR/schedules/<run>/`, input workbook copied so checks work after the run's files expire). `webapp/day.py` computes the day from the in-use version's own workbook (demand, shrinkage, language setup, shifts, planned breaks, previous day's overnight shifts) and the day's attendance and actual breaks.

**Spec:** Owner, 2026-10-08, verbatim: "if scheduler did an edit to do it on the schedule manually after choose the file he wish to continue with … this to be stored somewhere so we can grab either or the main one from the tool and the edited one … i want to include attendance and break scheduling"; "manual edits needs to be accepted somehow … show a warning first with the error followed by yes or no before u continue and even if warning is acceptable to show that day marked as yellow or red based on severity"; "based on attendance … we were scheduling 20 but we have 18 so u should show available time per each interval for a chosen specific day … scheduler should start plotting actual breaks away from what the engine scheduled and we should see if we are still in a good terms or bad + or - in hours language coverage"; decisions: run owner or admin marks "in use"; schedules kept 13 months; Shift Library + OFF + Leave; anyone signed in marks attendance and moves breaks (logged); statuses Present, Unplanned leave, Late, Sick, Left early (+ Training, Coaching, Meeting, System issue); breaks move "every 5 mins". Samples approved: `evidence/phase_n/samples/`.

## Global Constraints

- The tool's own schedules never change; every accepted edit lands in a draft version (a tool version or the in-use version is copied first).
- Severity: a validator failure is red; a validator warning is yellow; missing breaks on a day whose shift was edited is yellow ("breaks to plan").
- Only the problems an edit adds are shown in its warning; the version's checks panel shows all.
- Coverage per interval on the day: needed = ceil(required ÷ (1 − shrinkage)); on the floor counted per 5 minutes (present, on shift, not on break), averaged over the interval; plus/minus hours = (on the floor × (1 − shrinkage) − required) × interval hours. Late and Left early count from/until their time; the other non-present statuses take the person off the floor for their shift.
- Language rows: per language, people of that language (or who can cover it, per Language Setup) on the floor inside that language's hours; red below its minimum; zero inside its hours is yellow when no minimum is set.
- Names stay on the server; schedules, attendance and actual breaks are deleted 13 months after their week.
- CSP unchanged: no inline styles or scripts; the day timeline is SVG with attributes.

## Review Focus

- Wednesday's early hours include Tuesday's overnight shifts and their breaks (`test_overnight_carry_in_counts`).
- An edit on the in-use version or a tool version creates a draft; the in-use version stays as it was (`test_editing_never_changes_the_tool_or_in_use_version`).
- A run whose files expired: its versions still open, check and download (`test_versions_survive_run_expiry`).
- A break moved outside its shift or onto another break: refused with a message (`test_break_must_stay_inside_the_shift`).
- Two people editing the same draft at once: changes apply one after the other, none lost (`test_concurrent_edits_both_kept`).

---

### Task 1: `webapp/versions.py` (workbooks and checks)

**Produces:** `read_week(path) -> dict` (`associates: [{name, emp_id, language, tl, days: [7 str]}]`, `breaks: [{associate, day, kind, start, minutes}]`, `shifts: [str]` (library labels, then OFF, Leave), `stage: "after"|"before"`); `apply_change(src, dst, name, day, value) -> None`; `validate(input_path, schedule_path, package_root, options=None) -> dict` (`status, failures, warnings, metrics, intervals`); `problems(result, edited=set()) -> list[{key, severity, text, cells: [(name, day)], days: [day]}]`; `marks(problems) -> {"cells": {"name|day": sev}, "days": {day: sev}}`.
- [ ] Tests (`webapp/tests/test_versions.py`, fixture: real B3 schedule + input under `webapp/tests/fixtures/versions/`): `test_read_week`, `test_apply_change_writes_both_tabs_and_drops_that_days_breaks`, `test_unknown_associate_or_value_refused`, `test_validate_finds_rest_variety_and_missing_breaks` (red, red, yellow on the edited cell), `test_marks_cells_and_days`, `test_before_breaks_version_has_no_break_problems`.

### Task 2: versions kept (store + service)

**Files:** `store.py` (tables `schedules`, `schedule_changes`), `webapp/schedules.py`, `runs.py` (copy tool versions when a run finishes; backfill at startup), cleanup (13 months).
**Produces:** `ScheduleBook(store, data_dir, package_root)`: `ensure(run) -> list[dict]`, `versions(run_id)`, `check(sid, name, day, value) -> dict` (new problems, all problems), `change(sid, user, name, day, value, reason) -> int` (the draft's id), `set_in_use(sid, user)`, `path(sid)`.
- [ ] Tests: `test_finished_run_gets_tool_versions`, `test_editing_never_changes_the_tool_or_in_use_version`, `test_change_log_keeps_who_what_why`, `test_one_version_in_use_per_program_week`, `test_versions_survive_run_expiry`, `test_concurrent_edits_both_kept`, `test_versions_deleted_after_13_months`.

### Task 3: the schedules page

**Files:** `app.py` (routes: `GET /runs/<id>/schedules`, `POST /schedules/<sid>/check` JSON, `POST /schedules/<sid>/change`, `POST /schedules/<sid>/in-use`, `GET /schedules/<sid>/download`, `GET /schedules/<sid>/week`), `templates/schedules.html`, `app.js` (editor: pick, check, warning Yes/No with reason), `app.css`; links from the run, program and week pages.
- [ ] Tests: `test_schedules_page_lists_versions_and_marks`, `test_check_returns_new_problems_only`, `test_change_needs_a_reason_when_it_breaks_rules`, `test_in_use_only_for_owner_or_admin`, `test_download_a_version`, browser `test_edit_with_warning_and_marks` (screens to `evidence/phase_n/screens`).

### Task 4: `webapp/day.py` and the day page

**Files:** `webapp/day.py`, `store.py` (tables `attendance`, `actual_breaks`), `app.py` (`GET /day?program=&date=`, `POST /day/attendance`, `POST /day/break`), `templates/day.html` (SVG timeline), `app.js` (status change, break drag in 5-minute steps with a keyboard alternative), `app.css`; menu "Today".
**Produces:** `day_view(week, inputs, day_index, attendance, actual) -> dict` (`lanes`, `cells` per interval: need, plan, now, plus_minus_hours, languages; `tiles`).
- [ ] Tests (`test_day.py` on the real Voice day): `test_overnight_carry_in_counts`, `test_unplanned_leave_lowers_the_floor`, `test_late_counts_from_arrival`, `test_moved_break_changes_two_intervals`, `test_break_must_stay_inside_the_shift`, `test_language_rows`, `test_five_minute_steps_only`; page tests and browser `test_day_page` with screens.

### Finish

- [ ] Website suite, gate, package, push, send screens, package and update steps.
