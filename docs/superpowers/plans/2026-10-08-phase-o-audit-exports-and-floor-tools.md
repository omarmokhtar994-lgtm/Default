# Phase O: audit trail, exports, adherence, meeting finder, overtime / VTO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, owner's standing choice). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every action on the website is recorded with who and when and can be exported for any period; the day's attendance turns into adherence, conformance and actual-shrinkage figures; the day page finds the best time for a meeting or training and suggests overtime or voluntary time off.

**Architecture:** a single `events` table records the actions not already logged (version created, set in use, run started / stopped / resumed, people admin); exports read `events` plus the existing logs (`schedule_changes`, `day_log`, `attendance`, `actual_breaks`, `runs`) for a date range and write one Excel workbook (a tab per kind) or a CSV. Adherence is computed per person per day from the same `day_view` segments the day page uses. The meeting finder and overtime / VTO suggestions reuse the 5-minute counts and `advice`-style deltas from `webapp/day.py`.

**Tech Stack:** Flask, SQLite, openpyxl (already a dependency), Jinja; no new packages.

**Spec:** owner's messages of 2026-10-08 (in the session): "keep the data for such things for at least a year backdated but the zip files etc can last for 30-60 days", "export attendance, activities done on a day or week or month or whatever period and who did the change/edit, same for schedule changes", "online search between different tools, tell me what other options we are missing, add as well". Market research (same day): audit-log export (Zendesk WFM, Daktela, HotSchedules), meeting finder with service-level impact (Talkdesk, Peopleware), overtime / VTO levers (Telus, Calabrio), adherence vs conformance (ServiceNow, NICE CXone exports), pay status on activities (Talkdesk).

## Global Constraints

- Records (schedules, changes, attendance, breaks, day log, events) kept at least 12 months: 395 days, as today.
- Run files (zips, results) kept `RUN_FILES_DAYS`, default 30, allowed 30 to 60; a value outside is refused at start-up (fail closed).
- No engine change; protected workbooks untouched; Egypt time (UTC+3) in every export.
- Samples before UI code (owner): exports page, adherence report, meeting finder, overtime / VTO (sent 2026-10-08; owner answered "Be creative": build, adding Tasks 7–10).
- Names in samples and new fixtures: "Associate NN".

## Review Focus

- A period spanning a version change (the in-use version switched mid-week): exports use what was recorded, never re-derive old rows from the new version.
- Exports for a long range (13 months, many programs): bounded memory (stream rows into the workbook), refuse ranges over 400 days.
- Overnight shifts: a status or break belongs to its shift date in every export and in adherence.
- Overtime that crosses midnight or breaks the rest rule with the next day's shift: refused or warned, never silently kept.
- An export asked for by someone who is not signed in: refused (login required), and a CSV cell starting with = + - @ is written as text (no formula injection).

---

### Task 1: events table and the actions it records

**Files:** `webapp/store.py` (table `events`: id, at, user_id, kind, program, week_start, run_id, schedule_id, subject, detail), `webapp/app.py`, `webapp/runs.py`, `webapp/schedules.py`; tests `webapp/tests/test_events.py`.
**Produces:** `Store.add_event(**fields)`, `Store.list_events(start_ts, end_ts, program=None, user_id=None, kinds=None)`; kinds: `run_started`, `run_stopped`, `run_resumed`, `version_created`, `set_in_use`, `downloaded`, `user_added`, `user_disabled`, `password_reset`.
- [ ] Tests: `test_set_in_use_is_recorded`, `test_run_start_stop_resume_recorded`, `test_events_kept_13_months_then_deleted`.

### Task 2: exports

**Files:** `webapp/exports.py`, `webapp/app.py` (`GET /exports`, `GET /exports/download`), `templates/exports.html`; tests `webapp/tests/test_exports.py`, page tests in `test_runs.py`.
**Produces:** `build(store, start: date, end: date, program: str|None, user_id: int|None, kinds: list[str], fmt: "xlsx"|"csv") -> (bytes, filename)`. Kinds and columns:
- attendance: shift date, program, associate, slot, shift, status, from, to, billable, recorded by, recorded at
- day activity: date, program, associate, what, by, at (the day log: statuses and break moves)
- breaks: date, program, associate, break, planned, taken, moved by, at
- schedule changes: program, week, version, associate, day, old, new, reason, severity, problems, by, at
- versions and in use: program, week, version, event, by, at
- runs: workbook, program, week, mode, status, started by, created, finished
- worked hours and adherence (Task 3)
- [ ] Tests: `test_period_filters_by_shift_date`, `test_who_filter`, `test_one_tab_per_kind_and_an_about_tab`, `test_csv_cells_never_formulas`, `test_range_over_400_days_refused`, `test_export_needs_sign_in`.

### Task 3: adherence, conformance and actual shrinkage

**Files:** `webapp/adherence.py`, `templates/adherence.html` (or a tab of the day page), export tab.
**Produces:** `person_day(view, name) -> {scheduled, worked, late, early, absent, aux_billable, aux_unbillable, breaks_planned, breaks_taken, out_of_schedule, adherence, conformance}` (minutes and %); `interval_shrinkage(view, inputs) -> [{t, planned_people, on_floor, actual_shrinkage, input_shrinkage}]`.
Definitions: adherence = minutes doing what the schedule says (on the floor when planned on the floor, on a break when the break was planned then) ÷ scheduled minutes; conformance = minutes worked ÷ scheduled minutes; actual shrinkage = 1 − on the floor ÷ planned people per interval.
- [ ] Tests on the real Voice day: `test_moved_break_costs_adherence_not_conformance`, `test_late_costs_both`, `test_billable_aux_counts_as_worked`, `test_actual_vs_input_shrinkage_per_interval`.

### Task 4: meeting / training finder

**Files:** `webapp/day.py` (`meeting_slots(view, names, minutes, earliest, latest) -> [{start, end, tightest_buffer, clashes}]`), route `POST /day/meeting-slots`, `POST /day/meeting` (records the aux for each person, logged), dialog on the day page.
- [ ] Tests: `test_slots_avoid_breaks_and_other_aux`, `test_ranked_by_tightest_buffer`, `test_booking_records_aux_for_each_person`.

### Task 5: overtime and voluntary time off suggestions

**Files:** `webapp/day.py` (`overtime(view, week, inputs, settings)`, `vto(view, ...)`), statuses "Overtime" (extends the shift before or after, on the floor) and "VTO" (leaves early, like Left early but voluntary), day page panel.
Rules: overtime only next to a short interval, at most 2 hours, keeps the rest gap (Instructions: rest gap hours) to the previous and next day's shifts; VTO only where the buffer stays at or above zero and every language keeps its minimum.
- [ ] Tests: `test_overtime_only_next_to_short_intervals`, `test_overtime_respects_rest_gap`, `test_vto_keeps_buffer_and_languages`, `test_overtime_counts_on_the_floor`.

### Task 6: run files kept 30 to 60 days (setting)

**Files:** `webapp/runs.py`, `deploy/` env file comment; test in `test_runs.py`.
- [ ] Tests: `test_run_files_days_setting`, `test_run_files_days_outside_30_60_refused`.

### Task 7: fix the rest of the day's breaks (autopilot)

**Files:** `webapp/day.py` (`replan(view, inputs, now: int) -> {moves: [{name, idx, kind, start_from, start_to}], before: {tightest, short_hours}, after: {...}}`), routes `POST /day/replan` (preview) and `POST /day/replan/apply` (each move kept and logged "by autopilot, approved by <name>"), dialog on the day page.
Rules: only breaks not yet started (start >= now) of people on shift and present; 5-minute steps; inside the shift; breaks keep their order; gaps within the program's minimum / normal maximum when set; no overlap. Greedy local search: repeatedly take the tightest interval and try moving a break out of it to where it raises the lowest buffer most; stop when nothing improves. Deterministic.
- [ ] Tests (Voice day): `test_never_makes_the_tightest_worse`, `test_taken_breaks_never_move`, `test_rules_hold_after_replan`, `test_apply_logs_each_move`.

### Task 8: shrinkage coach

**Files:** `webapp/coach.py` (`actual_shrinkage(daybook, program, start, end) -> {weekday: {minute: (actual, input, days)}}`, `corrected_tab(...) -> BytesIO`), route `GET /coach?program=&from=&to=` and its download.
Actual shrinkage per interval = 1 − on the floor ÷ people paid on shift (from recorded attendance, breaks taken and aux); averaged per weekday over the period; the suggested value is the actual average where at least 3 days were recorded, else the input's value (said so in the cell's note).
- [ ] Tests: `test_average_per_weekday_and_interval`, `test_too_few_days_keeps_the_input`, `test_corrected_tab_has_the_input_layout`.

### Task 9: shift handover note

**Files:** `webapp/handover.py` (`note(daybook, program, day) -> dict`), `templates/handover.html` (printable), Exports tab "Daily summary".
- [ ] Tests: `test_note_lists_absences_lates_moves_and_short_intervals`, `test_watch_tomorrow_from_the_plan`.

### Task 10: wallboard

**Files:** route `GET /day/wallboard?program=`, `templates/wallboard.html` (big type, refreshes every 60 s, no controls), now / next three intervals, on break now and in the next 30 minutes, language counts.
- [ ] Tests: `test_wallboard_shows_now_and_next_intervals`, `test_wallboard_refreshes`.

### Later (not this phase; owner decides)

One-day shift swap (parked by the owner), time-off requests with allowances, blackout days and auto approve / deny (needs associate log-ins), associate self-service and a shift-trade board, adherence from the phone system's state export (ACD file import), schedule-change notifications (email), intraday reforecast from actual volumes.

### Finish

Website suite; restore earlier phases' screenshots; gate (`run_tests.sh`, `tests_staged/GATE_MINIMUMS.json`); package; protected workbooks and engine unchanged; push; screenshots, package and update steps to the owner.
