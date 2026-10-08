# Phase P: admin edits of run details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An administrator can correct any run's details (program, schedule week, who submitted it, workbook name) and rename or merge a program everywhere, with the run's schedule versions moving along, nothing hidden, and every change kept in the record.

**Architecture:** One module `webapp/run_admin.py` works out what a change would do (preview) and applies it; `webapp/store.py` gains the SQL that moves rows in one transaction. The run page's existing "program and week" form becomes "Edit details"; the program page gains "Rename or merge" (admin only). A change with consequences (a version stops being in use, day records stay where they are) shows a Yes/No check with a reason first.

**Tech Stack:** Flask 3.1, SQLite, Jinja2, unittest, Playwright (screenshots).

**Spec:** the owner's request (2026-10-08): "as an administrator i need to have the ability to change program name submitted/week start etc for all details", read with the defect found: `/runs/<id>/tag` changes the run but not its schedule versions (`schedules.program`, `schedules.week_start` are copies made when the run finished), so the day page, Weeks and "in use" lose the versions after a change.

## Global Constraints

- CLAUDE.md: no hidden errors; no silent roster or demand changes; do not modify tests to pass (the existing `test_untagged_runs_can_be_tagged` keeps passing unchanged); Egypt time; commit only to `claude/handoff-document-m6egz2`.
- Engine untouched; kept workbooks (inputs, results, version files) are never rewritten: only database rows change.
- Strict CSP: no inline style or script; every new POST carries `csrf_token`; login required; admin-only fields refused (403) for others.
- Who may change what: the run's submitter changes program and week of their own run (as today); an admin changes program, week, submitted by and workbook name of any run, and renames programs.
- Events are history: past events keep the program name they were recorded under; the change itself is a new event.

## Review Focus

1. A program name holding "/" ("AE/AR B2B") in the rename form: the rename posts the old name in the form body, not the URL path — test renames "AE/AR B2B".
2. A run changed while still queued: the versions made when it finishes carry the new details — covered by `ensure` reading the run at finish (runs.py:138); test changes a queued run then waits for its versions.
3. Rename that only changes case or spacing ("ae/ar  b2b" → "AE/AR B2B") is a rename, not a merge — test.
4. Merge where both programs have attendance for the same person and day: refused, listing the first clashes, nothing changed — test.
5. Clearing the week or program (empty) keeps working as today, and the versions follow (in-use scope falls back to the run) — test.

---

### Task 1: Moving a run (store + preview + apply)

**Files:**
- Create: `webapp/run_admin.py`
- Modify: `webapp/store.py` (new methods after `update_run`)
- Test: `webapp/tests/test_run_admin.py`

**Interfaces:**
- Produces: `store.move_run(run_id: str, fields: Dict[str, Any], stop_in_use: List[int]) -> None` (updates `runs` with `fields`; sets `schedules.program/week_start` of the run to the new values when given; `in_use = 0` for ids in `stop_in_use`; one transaction).
- Produces: `store.day_record_counts(program: str, start: str, end: str) -> Dict[str, int]` keys `attendance`, `breaks`, `activities`, `log`.
- Produces: `run_admin.preview_run_change(store, run: Dict, new: Dict[str, Any]) -> Dict` with `changes: List[Tuple[str, str, str]]` (label, old, new; labels "Program", "Schedule week", "Submitted by", "Workbook"), `stop_in_use: List[Dict]` (id, label), `kept_by_target: Optional[str]` (label in use at the target), `old_records: Dict[str,int]`, `old_week_after: Optional[str]` (label the old week's day page then uses, None = no schedule), `target_records: Dict[str,int]`, `needs_check: bool`.
- Produces: `run_admin.apply_run_change(store, run, new, user_id: int, reason: str) -> Dict` (the preview it applied); records event `run_details_changed` with `detail` = "Program: A → B; Schedule week: … ; Reason: …".

- [ ] Step 1: failing tests in `test_run_admin.py` (fixture: one run "AE/AR B2B" week 2026-10-11 with its two tool versions via `ScheduleBook.ensure`, a second run "AE/AR B2B" 2026-10-18):
  - `test_versions_move_with_the_run`: change program to "AE AR B2B" → `list_schedules(run_id)` all have the new program; `DayBook.version("AE AR B2B", 2026-10-14)` finds the run's tool version; `needs_check` False.
  - `test_in_use_at_the_target_wins`: set run B's version in use for 2026-10-18, set run A's in use for 2026-10-11, move A to 2026-10-18 → preview `stop_in_use` = [A's label], `kept_by_target` = B's label, `needs_check` True; after apply exactly one in use for 2026-10-18 (B's).
  - `test_day_records_stay_and_are_listed`: attendance + activity on 2026-10-14 for "AE/AR B2B", move A to 2026-10-18 → preview `old_records` = {"attendance": 1, "activities": 1, …}, `old_week_after` None, `needs_check` True; after apply the records are still on 2026-10-14 under "AE/AR B2B".
  - `test_clearing_program_and_week`: program "" and week "" → versions follow; no exception.
  - `test_change_is_recorded`: apply with reason "typo" → one `run_details_changed` event with "Program: AE/AR B2B → AE AR B2B" and "Reason: typo" in `detail`, `run_id` set.
- [ ] Step 2: run `python -m unittest webapp.tests.test_run_admin` → FAIL (module missing).
- [ ] Step 3: implement the store methods and `run_admin` functions.
- [ ] Step 4: run → PASS.
- [ ] Step 5: commit.

### Task 2: Rename or merge a program

**Files:** Modify `webapp/run_admin.py`, `webapp/store.py`; Test `webapp/tests/test_run_admin.py`.

**Interfaces:**
- Produces: `store.rename_program(old: str, new: str, stop_in_use: List[int]) -> Dict[str, int]` (counts per table; one transaction over `runs`, `schedules`, `attendance`, `actual_breaks`, `activities`, `day_log`; `events` untouched).
- Produces: `store.program_clashes(old: str, new: str, limit: int = 5) -> List[Dict]` (attendance and moved-break keys present under both names).
- Produces: `run_admin.preview_rename(store, old, new) -> Dict` keys `merge: bool`, `runs`, `versions`, `records: Dict[str,int]`, `stop_in_use: List[Dict]` (week, label), `clashes: List[str]` (plain sentences); raises `ValueError` for an empty new name, an unknown old name, or the same name.
- Produces: `run_admin.apply_rename(store, old, new, user_id, reason) -> Dict`; refuses (`ValueError`) when `clashes`; records event `program_renamed` (`program` = new, `subject` = old, `detail` = counts + reason).

- [ ] Step 1: failing tests: `test_rename_moves_everything` ("AE/AR B2B" → "AE-AR B2B": runs, versions, attendance, break moves, activities, day log all move; `DayBook.page("AE-AR B2B", WED)` shows the recorded status; events keep the old name); `test_case_only_rename_is_not_a_merge`; `test_merge_keeps_the_target_in_use` (both programs with an in-use version for 2026-10-11 → `stop_in_use` lists the renamed one's; after apply one in use, the target's); `test_merge_refused_on_clashing_records` (attendance for Associate 001 on 2026-10-14 under both → `ValueError` naming "Associate 001" and "14 Oct"; nothing changed); `test_rename_refusals` (empty, same, unknown).
- [ ] Step 2: run → FAIL.  Step 3: implement.  Step 4: run → PASS.  Step 5: commit.

### Task 3: Pages and routes

**Files:** Modify `webapp/app.py` (`run_tag` route extended in place; new `POST /programs/rename`), `webapp/templates/run.html`, `webapp/templates/program.html`, `webapp/static/app.css`, `webapp/exports.py` (`OTHER_EVENTS` gains `"run_details_changed": "Run details changed"`, `"program_renamed": "Program renamed"`); Test `webapp/tests/test_runs.py`, `webapp/tests/test_ui_playwright.py`.

Form rules: `run_tag` reads `program`, `week_start`, and for admins `user_id` (an active user, or the current submitter) and `workbook` (stripped, 1–120 characters); a non-admin posting `user_id`/`workbook` that differ gets 403; a preview with `needs_check` and no `confirm=1` renders the run page with a "Check before saving" panel (what changes, which version stops being in use, which day records stay and what that week then uses, a required reason, Yes save / No keep); `confirm=1` without a reason re-shows the panel with "Give a reason."; otherwise apply and flash "Details saved." Rename: admin only (403 otherwise); first post shows the preview panel on the program page; `confirm=1` + reason applies and redirects to the new program's page; clashes show as the refusal.

- [ ] Step 1: failing tests in `test_runs.py`: `TheRunDetails.test_admin_edits_every_detail` (admin changes submitted by to Lina and workbook name; run page shows "started by Lina"; the Exports "Other actions" tab lists "Run details changed"), `test_submitter_edits_program_and_week_only` (Lina's own run: program change OK; `workbook` → 403), `test_check_before_saving` (day record present → page shows "Check before saving" and "stay", nothing changed until confirm with reason), `test_program_rename_page` (admin renames "AE/AR B2B" via `/programs/rename`, preview then confirm; non-admin 403); keep `test_untagged_runs_can_be_tagged` unchanged and passing.
- [ ] Step 2: run → FAIL.  Step 3: implement.  Step 4: run → PASS.
- [ ] Step 5: browser test `TheRunDetailsInTheBrowser.test_edit_and_rename` with screenshots `evidence/phase_p/screens/run_edit_details.png`, `run_check_before_saving.png`, `program_rename.png`.
- [ ] Step 6: full website suite, earlier phases' screenshots restored; commit; gate + package.

---

## Addendum (owner, 2026-10-08): the schedule's real start date

"I need a drop down while submitting to choose the actual start date of the schedule because some programs starts on Monday not Sunday … this can be edited by admin … it will determine the first day for the schedule uploaded for example 11 October or 12 October."

Facts: the input and the schedules label days Sun…Sat; the engine plans that Sun…Sat week, checks rest between neighbouring days including Saturday into Sunday, and applies the "Previous week scheduled" carry-in before Sunday. A run's `week_start` becomes the schedule's first date (any weekday; the form offers Sundays and Mondays). A date reads the column of its weekday name from the run whose seven days contain it.

Global constraint added: engine untouched — what a Monday start means for the engine's week edges is reported to the owner, not changed.

### Task 4: Dates map to the run that covers them

**Files:** Modify `webapp/store.py` (`list_schedules(..., covering: Optional[str])`: `week_start` between covering−6 and covering), `webapp/attendance.py` (`pick_version` prefers in use, then the latest start, then tool after breaks, newest; `DayBook.version` uses `covering`; `_records` reads the previous date from the run that covers it; `page` passes the previous date's week to `day_view`; `page["week_start"]` is the run's start; `next_week_unknown(program, on)` is "no schedule covers tomorrow"; `NEXT_UNCHECKED` names tomorrow's weekday; `neighbours` falls back to the input's carry-in only when no run covers yesterday), `webapp/day.py` (`day_view(..., before=...)`, `_segments(..., before)`: `before` = (week, column) of the previous date, `None` = the input's carry-in tab, default = the legacy same-week rule), `webapp/exports.py` (`_Weeks` caches by version id, not by Sunday). Test `webapp/tests/test_attendance.py` (`TheStartDay`), `webapp/tests/test_day.py`, `webapp/tests/test_exports.py`.

- [ ] Tests: `test_a_monday_start_covers_monday_to_sunday` (version for Mon 12 … Sun 18 is the run; Sun 11 and Mon 19 none); `test_the_last_day_takes_saturday_night_from_the_same_run` (Sun 18: Associate 004's Saturday 20:00 - 05:00 is carried in); `test_the_first_day_takes_last_night_from_the_run_before` (two Monday runs: Mon 19 carries in Sun 18's 23:00 - 08:00 for Associate 004, not the input tab's Associate 001); `test_the_first_day_without_a_run_before_uses_the_input_tab` (Mon 12: Associate 001's 16:00 - 01:00 from the tab; Associate 004's Sunday shift of the same run is not carried in); `test_overlapping_runs_latest_start_unless_in_use`; `test_tomorrow_unchecked_on_the_last_day` (Sun 18 True, Sat 17 False); exports `test_breaks_follow_a_monday_start`.
- [ ] RED, implement, GREEN, commit.

### Task 5: The start-date dropdown

**Files:** Modify `webapp/app.py` (`start_choices(around: date, keep: str) -> List[Tuple[str, str]]`: Sundays and Mondays from 4 weeks back to 10 weeks ahead plus `keep`; upload and edit store the chosen date as given — no Sunday snapping; `?week=` prefill keeps its date), `webapp/templates/dashboard.html` and `run.html` (select "Schedule starts"), `webapp/static/app.js` (picking a known program preselects the next date on its usual start weekday until the person picks one), `webapp/run_admin.py` (any valid date; label "Schedule starts"). Test `webapp/tests/test_runs.py` (`TheStartDate`).

- [ ] Tests: upload with `week_start=2026-10-12` keeps 2026-10-12; the form lists "Mon 12 Oct 2026" and "Sun 11 Oct 2026" with the prefilled one selected; the edit form offers the same and an admin moves a run to Monday 12; the run page says "starts Monday 12 Oct".
- [ ] RED, implement, GREEN, commit.

### Task 6: Verify and ship

- [ ] Browser: upload form dropdown, Edit details, Check before saving, Rename (screens to `evidence/phase_p/screens/`).
- [ ] Full website suite; earlier phases' screenshots restored; gate + package; engine and protected workbooks unchanged.
