# Phase R: RTA actions, picked programs and ready schedules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Programs and LOBs are picked, never typed; stray programs move into their LOB and empty programs/LOBs can be deleted; Home shows the program picked on the left; RTA can add a break, lunch, aux, attendance, overtime or VTO in any interval, open one person's day and delete what was recorded, and pick overtime and VTO lengths; a ready schedule (shifts already made) can be uploaded without the engine and its breaks planned for the week.

**Architecture:** No engine change. Program keys stay the stable key of every table (Phase Q); moving a stray key's data reuses Phase P's `preview_rename`/`apply_rename`, now limited to registered unit keys. Day-level breaks and lunches are activities (kinds `Break`, `Lunch`) like aux, always off the floor. The RTA dialogs are server-rendered from query parameters (`add=<minute>`, `who=<name>`) and upgraded to modals by `app.js`; a JSON preview endpoint runs the same checks dry. A ready schedule is the input workbook with its Schedule tab filled: the run is recorded with mode `READY` and status `DONE` without queueing, and the workbook itself becomes version 1 (kind `ready`). The week's breaks are planned on a grid whose rules (break set per shift length, windows, edge margin, gaps) come from the engine's own parser, run in a subprocess exactly like the validator, and are saved as a new version through `ScheduleBook._save`.

**Tech Stack:** Flask 3.1, SQLite, Jinja2, openpyxl, unittest, Playwright.

**Spec:** the owner's message of 2026-10-08 (the eight callouts: program name typed creates new programs instead of merging; no delete for submitted OT/VTO; add coaching/breaks in any interval; unplanned leave from RTA; OT/VTO length forced; cannot delete a program or LOB; Home shows all programs while one is picked on the left; upload a ready schedule without breaks and plot breaks manually) with the samples `r1_home.png` … `r8_plan_breaks.png` (sent 2026-10-08) and the owner's answers: ready file = our input workbook with the Schedule tab filled; breaks = week grid (with Suggest times) plus RTA; delete = move first, then delete; Home = only the picked program.

## Global Constraints

- Engine untouched ("dont change anything in the engine"); the break-rules helper only imports the engine's parser in a subprocess, as `engine/tools/independent_validator.py` already does. Protected workbooks and `engine/regression_assets` untouched.
- Nothing is deleted while data is stored under it; a move shows what moves and what clashes before it is saved (Phase P check page).
- No hidden errors: every refusal names the person, time or cell and the rule; nothing is dropped silently (a drafted break for someone no longer working that day is reported, not saved).
- Do not modify tests to pass. Where the owner changed a contract (program typed → picked; Home shows the picked program), re-pin the test and say why in it.
- Strict CSP (no inline style or script); CSRF on every POST; access: every new route checks the program (or the version's program) with `Access.can_open`.
- Real employee names never in fixtures or samples: "Associate NN".
- Plan breaks on 15-minute steps (the validator's `BREAK_NOT_QUARTER_HOUR_ALIGNED`); day-level RTA times stay on 5-minute steps (`STEP`).
- Egypt time; commit and push only to `claude/handoff-document-m6egz2`.

## Review Focus

1. Late / Left early from the Add dialog with a time outside the shift, or Late without an arrival time → refused with the shift's times, nothing recorded (Task 4 test `test_add_late_outside_shift_is_refused`).
2. Deleting a LOB or program that still has runs, versions or day records, or a program that still has LOBs → refused with the counts; after moving its data the delete works (Task 2 tests).
3. A ready workbook with a shift that is not in the Shift Library, an empty day cell or a repeated name → rejected naming the row, person and day; no run is queued and no version is made (Task 7 test `test_ready_workbook_with_unknown_shift_is_rejected`).
4. An overnight shift (22:00 - 07:00) in the break grid: times after midnight belong to that shift for the checks, the suggestion and the saved Break Schedule (Task 8 test `test_overnight_shift_breaks_cross_midnight`).
5. A break draft for someone whose shift that day changed or became OFF since it was drafted → that row is left out of the save and named in the message (Task 8 test `test_draft_for_a_day_off_is_reported_not_saved`).

---

### Task 1: Program and LOB picked from a list, never typed

**Files:**
- Modify: `webapp/app.py` (`run_tag`, `program_rename`, the run page and program page contexts), `webapp/run_admin.py`
- Modify: `webapp/templates/run.html:19-20`, `webapp/templates/program.html:26-27`
- Test: `webapp/tests/test_runs.py` (new class `ThePickedProgram`), re-pins where a test types a new name

**Interfaces:**
- Produces: `run_admin.unit_keys(store) -> set` (every registered unit key: LOB keys and LOB-less program keys, after `ProgramBook.sync`); `_unit_choices` (existing) feeds the selects.
- `run_admin._check(store, new)` refuses `program` not in `unit_keys` with "Pick a program and LOB set up under LOBs and defaults." (empty program still allowed: "no program").
- `preview_rename(store, old, new)` refuses `new` not in `unit_keys` with the same words.

- [ ] Step 1: tests `test_edit_details_offers_program_and_lob_select` (run page has `<select name="program">` with an optgroup per program and the LOB label "SAKS, NMG Tier 2"; no `<input name="program"`), `test_typed_program_is_refused` (POST `/runs/<id>/tag` with `program="SAKS, NMG Tier 2"` when only key "SAKS NMG Tier 2" exists → page says "Pick a program and LOB", run unchanged, no new program row), `test_program_page_moves_into_a_picked_unit` (program page shows "Move everything into" select; POST `/programs/rename` with an unregistered `new` → refused).
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement; templates use `_unit_choices(ProgramBook(store).tree())` (admins see all units).
- [ ] Step 4: run the class, then `python -m unittest webapp.tests.test_runs webapp.tests.test_run_admin`; re-pin tests that rename to a free-typed name (reason: "owner 2026-10-08: programs are picked from the list, typing made stray programs").
- [ ] Step 5: commit.

### Task 2: Move a stray program into its LOB, delete empty programs and LOBs

**Files:**
- Modify: `webapp/store.py`, `webapp/programs.py`, `webapp/app.py` (`program_setup` actions `delete_program`, `delete_lob`; setup context `usage`), `webapp/templates/program_setup.html`, `webapp/exports.py` (`OTHER_EVENTS`: `program_deleted`, `lob_deleted`)
- Test: `webapp/tests/test_programs.py` (class `TheDeletes`), `webapp/tests/test_runs.py::TheProgramSetup`

**Interfaces:**
- Produces: `Store.key_usage(key: str) -> Dict[str, int]` with keys `runs`, `versions`, `attendance`, `breaks`, `activities`, `log`; `Store.delete_program_row(program_id)` (also its `user_programs` rows), `Store.delete_lob_row(lob_id)`.
- `ProgramBook.usage(key) -> Dict[str, int]`; `ProgramBook.delete_program(program_id) -> str` (its name) refuses with LOBs ("Delete or move its LOBs first.") or with usage ("{name} still has 1 run, 1 version and 3 day records: move them into a program or LOB first."); `ProgramBook.delete_lob(lob_id) -> str` refuses with usage.
- Setup page: a program row whose key has data and no LOBs gets "Move all of it into" (select of other units, POST `/programs/rename` with `old`, `new`; the Phase P check page follows) and "Delete program" (disabled with the reason while usage > 0); each LOB gets "Delete LOB" (disabled with the reason while it has data).

- [ ] Step 1: tests `test_delete_empty_lob`, `test_delete_lob_with_data_is_refused_with_counts`, `test_delete_program_with_lobs_is_refused`, `test_move_then_delete_stray_program` (stray key "SAKS, NMG Tier 2" with a run → `apply_rename` into "SAKS NMG Tier 2" → `delete_program` works, `sync()` does not bring it back, the day page of the LOB reads the moved run), `test_setup_page_offers_move_and_delete` (route level, event `program_deleted` recorded).
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement.
- [ ] Step 4: run `webapp.tests.test_programs` and `webapp.tests.test_runs`.
- [ ] Step 5: commit.

### Task 3: Home shows the program picked on the left

**Files:**
- Modify: `webapp/app.py` (`home`, `_program_cards`, `PROGRAM_PAGES["home"] = "/?program={key}"`), `webapp/templates/dashboard.html`
- Test: `webapp/tests/test_runs.py` (class `TheHomeFollowsThePicker`)

**Interfaces:**
- `_program_cards(runs, only: Optional[str])` → the card of the program holding unit `only` (all cards when `only` is None); `home` passes `only=None` when `?all=1`, else the menu's unit (`_left_menu()["nav_unit"]`), and `other_programs` = the person's other program names with their first unit key.

- [ ] Step 1: tests `test_home_shows_the_picked_program_only` (two programs; `/?program=<B key>` → card B only, links to A and "Show all my programs"), `test_home_all_shows_every_program` (`/?all=1`), `test_planner_home_never_lists_other_programs` (planner with A only: no B anywhere on Home), `test_menu_picker_on_home_stays_on_home` (`data-target="/?program={key}"` on Home).
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement; re-pin Phase Q tests that expect every card on Home (reason in the test: owner 2026-10-08).
- [ ] Step 4: run `webapp.tests.test_runs`.
- [ ] Step 5: commit.

### Task 4: Add anything in an interval (backend), day-level breaks, VTO any stretch

**Files:**
- Modify: `webapp/day.py` (`EXTRA_BREAKS = ("Break", "Lunch")`; `day_view` counts them off the floor and in `breaks`; `board` lists them as chips with `added: True`; wallboard reads them), `webapp/attendance.py`, `webapp/adherence.py` (added breaks count as non-billable away), `webapp/app.py` (routes `POST /day/add`, `POST /day/add-preview`, `POST /day/undo`)
- Test: `webapp/tests/test_attendance.py` (class `TheAddDialog`), `webapp/tests/test_runs.py::TheDayPage`

**Interfaces:**
- `ADD_KINDS = {"Off the floor": ["Break", "Lunch", "Coaching", "Meeting", "Training", "System issue"], "Attendance": ["Unplanned leave", "Sick", "Late", "Left early"], "Hours": ["Overtime", "VTO"]}` in `attendance.py`; `ACTIVITY_KINDS` gains `Break`, `Lunch`.
- `DayBook.add_item(program, on, name, what, start: str, minutes: int, user_id, billable=False, note="", dry_run=False) -> Dict[str, Any]` returns `{"text": <what was recorded>, "lo": int, "hi": int, "record": {...}}`: Unplanned leave / Sick → whole shift; Late → `start` is the arrival; Left early → `start` is when they left; others → `start` to `start + minutes`. `dry_run=True` runs every check and writes nothing (`set_status` and `add_activity` gain `dry_run`).
- `add_activity`: `Break`/`Lunch` inside the shift, 5-minute steps, not over the person's planned (or moved) breaks or other activities; `VTO` any stretch inside the shift (was: to the end of the shift); described "VTO 16:00 to 18:00".
- `DayBook.preview_item(program, on, name, what, start, minutes, billable, measure) -> {"text": str, "level": "ok"|"warn"|"bad"}`: the tightest buffer over the affected intervals before and after, from `page(..., extra=record)`; `page` gains `extra: Optional[Dict]` merged into the records.
- `POST /day/undo` (form, redirect back): `what=status` → Present; `what=break&idx=N` → back to plan.

- [ ] Step 1: tests `test_add_break_in_an_interval_takes_them_off_the_floor` (now count drops by 1 for 10:15-10:30; chip on the board), `test_add_unplanned_leave_from_the_dialog` (tile present 25 of 26), `test_add_late_outside_shift_is_refused`, `test_add_overtime_with_a_chosen_length`, `test_vto_any_stretch_inside_the_shift` (14:00 to 15:00 accepted; 06:00 to 07:00 before the shift refused), `test_added_break_cannot_overlap_a_planned_break`, `test_preview_changes_nothing_and_says_the_effect` (buffer text, no rows written), `test_undo_status_and_break`, route `test_add_route_records_and_redirects_to_the_board_row`.
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement.
- [ ] Step 4: run `webapp.tests.test_attendance webapp.tests.test_day webapp.tests.test_adherence webapp.tests.test_runs`.
- [ ] Step 5: commit.

### Task 5: RTA screens: "+ Add" on every interval and one person's day

**Files:**
- Modify: `webapp/app.py` (`day_page` reads `add` and `who`), `webapp/templates/day.html`, `webapp/static/app.js`, `webapp/static/app.css`
- Test: `webapp/tests/test_runs.py::TheDayPage`, `webapp/tests/test_ui_playwright.py` (class `TheRtaActionsInTheBrowser`)

**Interfaces:**
- Board rows get "+ Add" (`?view=board&add=<t>#add`); the timeline gets "+ Add" per lane name row (opens with that person chosen). `add` renders `<dialog id="add-dialog" open>` with Who (people on shift that day), What (`ADD_KINDS` groups as radio chips), From (prefilled, 5-minute step), Length (5 min to the shift's end; hidden for whole-shift kinds), Billable (aux only); posts `/day/add`. `app.js` shows it modal and fetches `/day/add-preview` on change into `[data-effect]`.
- Every name (board chips, timeline lane, recorded lists) links `?who=<name>`; `who` renders `<dialog id="person-dialog" open>`: attendance select (posts `/day/attendance` via the existing JS), and every record of that person that day with Delete (activities → `/day/activity/cancel`), Set back (status → `/day/undo`), Back to plan (moved break → `/day/undo`), Move (planned break → the existing break dialog).
- The Overtime and VTO tab's recorded list says "Delete", not "Cancel".

- [ ] Step 1: route tests `test_board_rows_offer_add`, `test_add_dialog_lists_kinds_and_prefills_the_interval`, `test_person_dialog_lists_records_with_delete`; browser test `test_add_a_break_from_the_board` (open "+ Add" at 10:00, choose Break, see the preview, Add → chip shown) and `test_delete_overtime_from_the_person_dialog`.
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement (load frontend-design before the CSS; webapp-testing for the browser test).
- [ ] Step 4: run `webapp.tests.test_runs` and the browser class.
- [ ] Step 5: commit.

### Task 6: Overtime and VTO with a chosen length

**Files:**
- Modify: `webapp/day.py` (`overtime_offers` adds `side` "after"/"before" and `max` minutes within `OVERTIME_MAX` and the rest gap), `webapp/templates/day.html` (cover tab and the board's cover panel), `webapp/app.py` (`day_activity` accepts `span="HH:MM|HH:MM"`)
- Test: `webapp/tests/test_day.py`, `webapp/tests/test_runs.py::TheDayPage`

**Interfaces:**
- Overtime offer form: `<select name="span">` with options every 15 minutes from 15 to `max` (value `"from|to"`, label "1 h (17:00 to 18:00)"), the offer's own length selected; VTO offer form: `from` and `to` selects in 15-minute steps inside the shift, defaults the offer's start and the shift's end.

- [ ] Step 1: tests `test_overtime_offer_says_side_and_max` (rest gap 12 h and next shift at 07:00 → `max` capped), `test_cover_tab_offers_lengths`, `test_record_overtime_with_span`, `test_record_vto_stretch_from_the_tab`.
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement.
- [ ] Step 4: run `webapp.tests.test_day webapp.tests.test_runs`.
- [ ] Step 5: commit.

### Task 7: Upload a ready schedule (no engine)

**Files:**
- Create: `webapp/ready.py`
- Modify: `webapp/runs.py` (`RunQueue.submit_ready`), `webapp/schedules.py` (`ensure_ready`; `edited_cells` treats every working cell of a `ready` lineage as planned-next so missing breaks are yellow), `webapp/app.py` (`submit_run` reads `kind`), `webapp/templates/dashboard.html`, `webapp/templates/run.html`, `webapp/static/app.js` (hide run length and options for a ready upload)
- Test: `webapp/tests/test_ready.py`

**Interfaces:**
- `ready.check_ready(path: Path) -> List[str]`: problems in plain words, each naming the tab, row, person and day; empty list = accepted. Checks: a Schedule tab with a name column and Sun..Sat; at least one person; every day cell is a Shift Library shift, OFF or Leave (case and spaces ignored); no empty day cell; no repeated name.
- `RunQueue.submit_ready(user_id, upload_path, workbook_name, program, week_start) -> str`: run row mode `READY`; rejected → status `REJECTED` with the problems; accepted → `ScheduleBook.ensure_ready(run, input_path)` makes version 1 (kind `ready`, label "Ready schedule (uploaded)", file `<run>/ready.xlsx`, checked by the validator), then status `DONE`, `started` = `finished` = now, message "Ready schedule uploaded; the engine did not run. Plan its breaks from its schedule."
- Run page for `READY`: no engine sections; links "Open the schedule" and "Plan breaks".

- [ ] Step 1: tests (fixture: the B3 input with its Schedule tab filled from the B3 after-breaks schedule, built in `setUpClass`) `test_ready_upload_makes_a_version_without_the_engine` (runner never called; version kind ready; status DONE), `test_ready_workbook_with_unknown_shift_is_rejected`, `test_ready_missing_breaks_are_yellow_not_red`, `test_ready_run_page_and_rta_work` (run page 200 with "Plan breaks"; `/day` for a date in the week shows the people with no breaks), `test_upload_form_offers_build_or_ready`.
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement.
- [ ] Step 4: run `webapp.tests.test_ready webapp.tests.test_runs webapp.tests.test_schedules`.
- [ ] Step 5: commit.

### Task 8: Plan a week's breaks (grid, Suggest times, save as a version)

**Files:**
- Create: `webapp/break_rules_cli.py` (subprocess: load the engine like the validator, `parse_input`, print the break rules as JSON), `webapp/break_plan.py`
- Modify: `webapp/versions.py` (`write_breaks`), `webapp/schedules.py` (`break_rules`, `save_breaks`), `webapp/store.py` (`break_drafts` table), `webapp/app.py` (routes `GET/POST /schedules/<id>/breaks`), `webapp/templates/breaks.html` (new), `webapp/templates/schedules.html` (link "Plan breaks"), `webapp/static/app.css`
- Test: `webapp/tests/test_break_plan.py`

**Interfaces:**
- `break_rules_cli.py --input X --engine Y` prints `{"segments": [[minutes, label], ...], "by_length": [[threshold_minutes, [[minutes, label], ...]], ...], "windows": {label_lower: {"earliest": m|null, "latest": m|null}}, "edge_margin": m|null, "min_gap": m, "preferred_gap": m, "max_gap": m}` (all minutes).
- `ScheduleBook.break_rules(schedule_id) -> Dict` (cached in `<run>/break_rules.json`, made once per run input).
- `break_plan.slots_for(rules, duration_min) -> List[Tuple[str, int]]` (label, minutes) in order; `break_plan.check_row(rules, label, starts) -> Tuple[str, str]` (level ok/warn/none, plain text); `break_plan.suggest(week, inputs, rules, d, plan) -> Dict[str, List[int]]` fills only empty slots, 15-minute steps, each slot inside its window, edge margin and gaps, choosing the start that keeps the floor's buffer highest over its span, ties to the preferred gap; `break_plan.floor(week, inputs, d, plan) -> List[Dict]` per interval (`t`, `pm`, `cls`).
- `Store.set_break_draft(schedule_id, day, rows, user_id)`, `get_break_draft(schedule_id) -> {day: {name: [start|None]}}`, `clear_break_draft(schedule_id)`.
- `versions.write_breaks(src, dst, plan, labels)` replaces the planned cells' rows on every Break Schedule tab (creates "Break Schedule" with headers Associate, Day, Shift, Break Type, Start, Duration Minutes, Status when absent).
- `ScheduleBook.save_breaks(schedule_id, user_id, plan, reason) -> Tuple[int, List[str]]` (version id, rows left out and why); one change row per (person, day): old/new "Break 1 11:45, Lunch 14:30, Break 2 17:30".
- Page actions (POST, `action`): `keep` (store this day's times in the draft, go to `go` day), `suggest`, `copy` (this day's times to the person's other days with the same shift), `save` (new version; draft cleared), `discard`.

- [ ] Step 1: tests `test_rules_come_from_the_engine_parser` (B3 input: Break 1 15, Lunch 30, Break 2 15; min gap 60), `test_check_row_names_the_gap`, `test_suggest_fills_empty_slots_inside_the_rules` (every suggested day passes the validator's break checks: save then validate → no BREAK_* failures for those cells), `test_overnight_shift_breaks_cross_midnight`, `test_draft_survives_switching_days_and_save_makes_a_version`, `test_draft_for_a_day_off_is_reported_not_saved`, `test_ready_schedule_with_planned_breaks_shows_them_in_rta`, route `test_breaks_page_access_is_checked` (403 for a planner without the program).
- [ ] Step 2: run, watch them fail.
- [ ] Step 3: implement.
- [ ] Step 4: run `webapp.tests.test_break_plan webapp.tests.test_schedules webapp.tests.test_runs`.
- [ ] Step 5: commit.

### Task 9: Browser checks, screenshots, release

**Files:**
- Modify: `webapp/tests/test_ui_playwright.py` (class `ThePhaseRInTheBrowser`: screens to `evidence/phase_r/screens/`)
- Ledger and package as before

- [ ] Step 1: browser test saves `home_picked`, `board_add`, `person`, `ot_vto`, `programs_move_delete`, `edit_details`, `upload_ready`, `plan_breaks`, `phone_board` (390 px, no sideways scroll).
- [ ] Step 2: website suite, then `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`.
- [ ] Step 3: package build, split under 30 MiB (larger half first), send with the screens and install steps.
- [ ] Step 4: commit and push.
