# Phase AA: overtime before or after, delete a schedule, schedules by week — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four samples the owner approved on 2026-10-10: overtime picked as before or after the shift, a
delete for schedules that are not needed, a Schedules page that compares any week's schedules, and the same schedule
switch on the Week page.

**Architecture:** Website only (Flask, Jinja, app.css, app.js under the strict CSP). Overtime keeps its rule in
`DayBook.add_activity`; the dialog sends a side and the server works out the times. Delete removes a run's own rows and
files and keeps every day record. The Schedules page reuses `ScheduleBook.week_list` (Phase Z) and the week view's
own figures (`webapp.week.view`).

**Tech Stack:** Python 3.11, Flask 3.1, SQLite store, openpyxl, Playwright (Chromium) for browser checks.

**Spec:** `evidence/phase_aa/DIAGNOSIS.md` and the approved samples `evidence/phase_aa/samples/01..04` (owner, 2026-10-10:
"1. Overtime before/after, 2. Delete an upload, 3. Schedules by week, 4. Week page switch"; delete: "Uploader or admin
(Recommended)": admins, and the person who uploaded or ran it, can delete any schedule that is not in use, uploaded or
run by the engine).

## Global Constraints

- The engine is not changed ("dont change anything kn the engine"); RC9.1 baseline workbooks and `engine/regression_assets` keep their bytes.
- Strict CSP: no inline script, style or event handlers; no `style=` attributes; positions through classes or CSSOM in `app.js`.
- Copy in sentence case; colours per DESIGN.md v3 (actions ink; teal/amber/red/violet only for covered/short/gap/over; `button.danger` for delete).
- Tests are not weakened; a re-pin says why in the test (three planned below, each from an approved sample).
- Made-up "Associate NN" names only; times in Egypt time (UTC+3).
- Release gate `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`; commit and push only to `claude/handoff-document-m6egz2`.

## Review Focus

1. A shift that starts just after midnight (00:30) with 1 h "Before the shift": refused, saying it would start the day before and offering a shorter length or After the shift — never a confusing "has to start when the shift ends" (Task 1).
2. A shift that ends after midnight (22:00 to 07:00) with "After the shift": overtime from 07:00 on the next morning, as the rule already counts it (Task 1).
3. Delete pressed for the schedule in use, a run still running or queued, or by someone who is neither an admin nor the uploader: refused (403 for the person), nothing deleted (Task 3).
4. Deleting the only schedule of a week: the week leaves the week picker and the redirect lands on a page that exists (Task 3).
5. A week with three schedules, or one whose version has no interval figures: the comparison shows "–" for missing figures, marks "better" only among schedules that all have breaks, and scrolls sideways on a phone (Task 2).

---

### Task 1: Overtime before or after the shift

**Files:**
- Modify: `webapp/attendance.py` (`add_item`, `preview_item`), `webapp/app.py` (`_add_fields`, `day_add`, `day_add_preview`, the `+ Add` panel's people), `webapp/templates/day.html` (add dialog), `webapp/static/app.js` (dialog), `webapp/static/app.css`
- Test: `webapp/tests/test_overtime_side.py` (new)

**Interfaces:**
- Produces: `DayBook.add_item(..., side: str = "")` and `DayBook.preview_item(..., side: str = "")`. With `what == "Overtime"` and `side` in `("before", "after")`, `start` is ignored: after starts at the shift's end, before starts `minutes` before the shift's start. Any other `side` keeps today's From behaviour.
- Produces: form field `side` (`before` | `after`) on `/day/add` and `/day/add-preview`; each Who option carries `data-start` and `data-end` (minutes of the person's own shift that day).

- [ ] **Step 1: Failing tests** (fixture: a ready upload of `make_ready` for SAKS, NMG Tier 2, week of Sun 11 Oct; Wed 14 Oct; a person whose shift is 08:00 to 17:00, found from the day page):
  - `test_after_the_shift_starts_when_it_ends`: `add_item(..., "Overtime", "", 60, side="after", dry_run=True)` → `(lo, hi) == (end, end + 60)`.
  - `test_before_the_shift_ends_when_it_starts`: side="before", 60 → `(start - 60, start)`; From ignored (pass "10:00").
  - `test_a_shift_ending_after_midnight_gets_overtime_the_next_morning` (Review Focus 2): a person on an overnight shift; after, 60 → `lo == span end` (> 1440).
  - `test_before_a_shift_starting_after_midnight_is_refused_clearly` (Review Focus 1): a shift starting at 00:30 (or the earliest start under 02:00 in the fixture); before, 60 → ValueError with "would start the day before" and "After the shift".
  - `test_the_dialog_offers_before_and_after`: GET `/day?...&view=board&add=<start>&person=<name>` → `<fieldset class="ot-side" data-ot-side hidden>` with radios `name="side" value="before"` (checked) and `value="after"`; the person's option has `data-start="480" data-end="1020"`.
  - `test_the_person_panel_default_now_records_overtime_before`: POST `/day/add` with `what=Overtime, from=08:00, minutes=60, side=before` → flash `Recorded: <name>, Overtime 07:00 to 08:00.`
  - `test_the_preview_says_the_times`: POST `/day/add-preview` with side=after, 30 → JSON text contains `17:00 to 17:30`.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_overtime_side -v` → FAIL.
- [ ] **Step 3: Implement.** `add_item`: for side mode, take the span from `self._shift(program, on, name)`; before with `span[0] - minutes < 0` → `ValueError(f"{name}'s shift starts at {hm(span[0])}, so {length} of overtime before it would start the day before. Pick a shorter length, or After the shift.")`. Dialog: with Overtime picked, From is hidden and disabled, the side fieldset shows, and each choice's times follow the Who and Length (app.js, from `data-start`/`data-end`; without script the server still works them out). Copy: legend "When"; "Before the shift" with "Comes in early"; "After the shift" with "Stays on"; a line "<name>'s shift today: 08:00 to 17:00." Submit text stays "Add overtime".
- [ ] **Step 4: Run** the new tests plus `webapp.tests.test_day webapp.tests.test_runs webapp.tests.test_channel_day` → PASS.
- [ ] **Step 5: Commit** "Phase AA task 1: overtime picked before or after the shift".

### Task 2: Schedules by week

**Files:**
- Create: `webapp/templates/schedules_week.html`
- Modify: `webapp/app.py` (`schedules_for` renders the page), `webapp/schedules.py` (`week_compare`, `kept_weeks`), `webapp/static/app.css`; re-pin `webapp/tests/test_runs.py:1143` and `webapp/tests/test_week_list.py:69` (approved sample 03: the menu's Schedules is its own page)
- Test: `webapp/tests/test_schedules_by_week.py` (new)

**Interfaces:**
- Consumes: `ScheduleBook.week_list(program, week) -> List[Dict]` (Phase Z), `ScheduleBook.channel_path(run_id)`, `webapp.week.view(intervals, side)["tiles"]` (`full`, `active`, `overtime_hours`, `extra_hours`).
- Produces: `ScheduleBook.kept_weeks(program: str) -> List[Dict]` (`{"week", "count"}` for each week with a kept schedule, oldest first; count = distinct runs) and `ScheduleBook.week_compare(program: str, week: str) -> List[Dict]` (each `week_list` entry plus `"figures": {"full", "active", "overtime", "extra"}` or None, `"channels": "added" | "workbook" | None`, `"channels_at"`, and `"better": set of figure keys` — set only when every entry has breaks and figures).
- Route: GET `/schedules?program=<unit>&week=<iso>`; week defaults to this week's Sunday (Egypt time) when it has a schedule, else the newest kept week; an unknown week falls back the same way.

- [ ] **Step 1: Failing tests** (fixture as Phase Z's `TwoSchedulesForOneWeek` plus one upload for the week before and one for the week after):
  - `test_the_menu_opens_the_week_page`: GET `/schedules?program=<key>` → 200, `<h1>Schedules: SAKS, NMG Tier 2</h1>`, a week picker `<nav class="weekpick"` with three weeks, `Week of 11 Oct` marked `aria-current`, and counts `1 schedule` / `2 schedules`.
  - `test_the_weeks_schedules_sit_side_by_side`: the compare table has one column per schedule in that week, In use first, rows `Versions`, `Hours at 100%`, `Overtime needed for 100%`, `Extra hours available`, `Breaks planned`, `Channel needs`; values equal `week_view(...)["tiles"]` of each shown version.
  - `test_better_is_marked_only_when_both_have_breaks` (Review Focus 5): with week_v2 without breaks, no `class="better"`, and its figures say `before breaks: not compared`; after planning week_v2's breaks, the better figure of each row is marked.
  - `test_actions_follow_permissions`: Open and Week view for each; Set in use only on the one not in use; Delete only for the one not in use, linking to `/runs/<id>/schedules#delete`; a planner who is not the uploader sees no Delete.
  - `test_a_week_with_three_schedules_and_one_without_figures` (Review Focus 5): a third upload with no intervals kept shows `–` and nothing breaks; the table sits in a named `.scroll` region.
  - `test_another_week_from_the_picker`: `&week=2026-10-04` shows that week's one schedule; `&week=2020-01-05` falls back to the default week.
  - Re-pins (reason in each test): `test_runs.test_overview_and_rta_are_separate` and `test_week_list.test_the_menu_opens_the_schedule_in_use` assert 200 and a link to the in-use run's Schedules page instead of a 302.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_schedules_by_week -v` → FAIL.
- [ ] **Step 3: Implement.** Columns per schedule; better marks bold with a small "better" under the figure; empty program or no kept week: "No schedules for {unit} yet. Upload one from Home." with a link. Copy for the note: "The RTA, the Week page, exports and analysis use the one in use. Figures are each schedule's own version shown (the one in use, else its newest). They are compared only when both have their breaks planned: a schedule without breaks always looks better than it will be."
- [ ] **Step 4: Run** the new tests, `webapp.tests.test_week_list webapp.tests.test_runs` → PASS.
- [ ] **Step 5: Commit** "Phase AA task 2: Schedules by week, side by side".

### Task 3: Delete a schedule that is not needed

**Files:**
- Modify: `webapp/store.py` (`delete_run`), `webapp/schedules.py` (`delete_run`), `webapp/app.py` (route, `_may_delete`), `webapp/templates/schedules.html` (section `id="delete"`), `webapp/exports.py` (label), `webapp/static/app.css`
- Test: `webapp/tests/test_delete_schedule.py` (new)

**Interfaces:**
- Produces: `Store.delete_run(run_id: str) -> int` (deletes the run row, its schedules, their changes, break drafts and channel drafts; returns the number of versions deleted; leaves events, attendance, actual breaks, activities, channel moves, day log and interval targets) and `ScheduleBook.delete_run(run_id: str) -> int` (ValueError when a version is in use; removes `root/<run_id>`).
- Route: POST `/runs/<run_id>/delete` with `confirm=1`; allowed for admins and the run's own user (`_may_delete(run)`), else 403; refused with a flash when the run is QUEUED or in `ACTIVE`, when a version is in use, or without the tick; on success removes the run's own files too, records `run_deleted` ("Schedule deleted" in Exports), flashes `Deleted <workbook> and its <n> version(s).` and redirects to `/schedules?program=<unit>&week=<week>` (or Home when the run had no program).

- [ ] **Step 1: Failing tests:**
  - `test_an_upload_not_in_use_is_deleted_and_the_days_records_stay`: mark someone Sick on a day of the week first; delete week_v2 → run, versions and `schedules/<run>` gone; attendance row kept; event `run_deleted` kept; flash text; the week's page lists one schedule.
  - `test_the_schedule_in_use_cannot_be_deleted` (Review Focus 3): flash `week_v1.xlsx is the schedule in use for the week, so it cannot be deleted. Set another schedule in use first.`; nothing deleted.
  - `test_a_running_run_cannot_be_deleted` (Review Focus 3): status RUNNING → flash `still running: stop it first`; nothing deleted.
  - `test_only_admins_and_the_uploader_may_delete` (Review Focus 3): a planner with access who did not upload → 403 and nothing deleted; the uploader (planner) → deleted.
  - `test_without_the_tick_nothing_is_deleted`: no `confirm` → flash `Tick the box to confirm`; nothing deleted.
  - `test_deleting_a_weeks_only_schedule_leaves_the_picker` (Review Focus 4): delete the next week's only upload → redirect target answers 200 and the week is gone from the picker.
  - `test_the_section_says_what_goes_and_what_stays`: the not-in-use page has `id="delete"`, the tick label and `Delete schedule` (danger); the in-use page says it cannot be deleted; a non-uploader planner sees no section.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_delete_schedule -v` → FAIL.
- [ ] **Step 3: Implement** (copy from sample 02).
- [ ] **Step 4: Run** the new tests plus `webapp.tests.test_week_list webapp.tests.test_schedules_by_week webapp.tests.test_exports webapp.tests.test_events` → PASS.
- [ ] **Step 5: Commit** "Phase AA task 3: delete a schedule that is not needed".

### Task 4: The Week page switches schedule

**Files:**
- Modify: `webapp/app.py` (`week_page`, `schedule_week`, `_version_week`), `webapp/templates/week.html`, `webapp/static/app.css`; re-pin `webapp/tests/test_week_list.py::test_the_week_page_links_to_the_other_schedule` (approved sample 04 replaces the sentence with the switch)
- Test: `webapp/tests/test_week_switch.py` (new)

**Interfaces:**
- Consumes: `ScheduleBook.week_list(program, week)`.
- Produces: `week.html` gets `switch` (list of `{"workbook", "in_use", "url", "here"}`) when the week has 2+ schedules; the in-use one links to `/week?program=&week=`, the others to `/schedules/<shown id>/week`.

- [ ] **Step 1: Failing tests:**
  - `test_the_week_page_has_a_schedule_switch`: `<div class="wk-switch" role="group" aria-label="Schedule shown">` with `week_v1.xlsx` (`aria-current`, "in use") and `week_v2.xlsx` ("not in use") links, and `Compare the week's schedules` linking to `/schedules?program=...&week=2026-10-11`.
  - `test_the_other_schedule_says_not_in_use_with_set_in_use`: its week view has the same switch with week_v2 current, the Phase Z "Not in use: ..." line, and a form to `/schedules/<id>/in-use` with `Set week_v2.xlsx in use` when allowed.
  - `test_one_schedule_no_switch`: a week with one schedule has no `wk-switch`.
  - Re-pin (reason in the test): `test_the_week_page_links_to_the_other_schedule` asserts the switch link to week_v2 instead of the sentence.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** the new tests plus `webapp.tests.test_week_list webapp.tests.test_week webapp.tests.test_week_in_use` → PASS.
- [ ] **Step 5: Commit** "Phase AA task 4: the Week page switches between a week's schedules".

### Task 5: Browser check, screens, suite, gate, package

- [ ] **Step 1:** `ThePhaseAAInTheBrowser` in `webapp/tests/test_ui_playwright.py`: the + Add dialog with Overtime (From hidden, the two choices with times that follow Length, After the shift recorded); Delete with the tick (button disabled until ticked, then the week's page); the Schedules page week picker and comparison; the Week page switch; phone 390 and 320 px without sideways scroll; no page errors → `evidence/phase_aa/screens/`.
- [ ] **Step 2:** axe crawl in both looks (scratch copy) → no violations; `evidence/phase_aa/CHECKS.md`.
- [ ] **Step 3:** full suite → OK; `git checkout -- evidence/` for earlier phases' screens.
- [ ] **Step 4:** `python3 tools/build_production_package.py` → GATE PASS; halves under 30 MiB; rejoin hash matches.
- [ ] **Step 5:** self-review of the branch, commit, push, report (rulings, deferred minors, install steps with the size-based join).
