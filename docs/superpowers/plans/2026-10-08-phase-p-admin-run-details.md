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
