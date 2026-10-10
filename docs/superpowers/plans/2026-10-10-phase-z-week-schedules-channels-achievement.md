# Phase Z: one week's schedules, channel needs, today's achievement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the owner's three Phase Z complaints and the "strange things" found with them, as approved in samples 01-05 (2026-10-10).

**Architecture:** Website only. A week's schedules become one list (built by `ScheduleBook.week_list`) shown on every Schedules page, and the menu, Home and Week page follow the schedule in use. Channel needs can be attached to an existing run as `<runs>/<run_id>/channels.xlsx`; one lookup (`ScheduleBook.channel_path`) feeds every channel reader. The RTA's target tile becomes a "Today's achievement" block above the tabs, with per-interval results on the board and the Timeline.

**Tech Stack:** Flask 3.1, Jinja2, SQLite store, openpyxl, vanilla JS (strict CSP), Playwright tests.

**Spec:** `evidence/phase_z/DIAGNOSIS.md` and `evidence/phase_z/samples/01-05`; owner answers 2026-10-10: build 1, 2 and 3; channels "Panel + tabs"; "check rest of my comments above" (the strange things in DIAGNOSIS.md and below). Channel tab layout: the approved Phase V sample `evidence/phase_v/samples/channels_input_sample.xlsx`.

## Global Constraints

- Engine untouched ("dont change anything kn the engine"); protected workbooks and `engine/regression_assets` untouched.
- Strict CSP: no inline script, style or event handlers (a per-cell width or position comes from a class or CSSOM in app.js, never a `style=` attribute).
- Copy in sentence case; made-up "Associate NN" names only in fixtures.
- Colour means state (DESIGN.md v3): at target `--covered`, below target `--short`, actions ink.
- Do not weaken validation or edit tests to pass; re-pin only with the reason in the test.
- Times shown in Egypt time.

## Review Focus

1. A week with one schedule shows no list clutter: the week list appears only when the week has two or more schedules (runs).
2. A run uploaded without a program or start date has no week list and no In use tag, and its pages still render.
3. Channel needs uploaded to a run whose own workbook already has channel tabs: the attached file wins, and the panel says which file is used.
4. A channel-needs file for the wrong interval (60-minute tabs on a 30-minute program) is refused with the tab named, and nothing is attached.
5. The achievement block on a past or future day says the date, not "Today", and draws no "now" mark.

Tests for each line are in Tasks 1, 1, 4, 4 and 6.

---

### Task 1: The week's schedules, and pages that follow the one in use

**Files:**
- Modify: `webapp/schedules.py` (`ScheduleBook.week_list`), `webapp/app.py:1735-1745` (`schedules_for`), `webapp/app.py` `run_schedules` (pass `week_list`), Week page note (`others` as links), `_version_week` (not-in-use note)
- Modify: `webapp/templates/schedules.html`, `webapp/templates/week.html`, `webapp/static/app.css` (section "Phase Z: the week's schedules")
- Test: `webapp/tests/test_week_list.py` (new)

**Interfaces:**
- Produces: `ScheduleBook.week_list(program: str, week_start: str) -> List[Dict[str, Any]]`, one dict per run with versions for that program and week: `{"run": run row (with by_name), "shown": the run's in-use version else its newest, "count": int, "in_use": bool, "covered": (after_100, active) or None, "has_breaks": bool}`; the in-use run first, then newest run first. Empty for an empty program or week.
- Template: `week_list` (list above) and the current run id; the section has `id="week-list"`.

- [ ] **Step 1: Write the failing tests** (client tests, two ready uploads of `make_ready` for the same LOB and week, the first with auto breaks set in use):
  - `test_the_menu_opens_the_schedule_in_use`: GET `/schedules?program=…` redirects to the first run's schedules page, not the newest run's.
  - `test_every_schedules_page_lists_the_weeks_schedules`: both runs' pages contain `id="week-list"`, both workbook names, exactly one `In use` tag in the list, `Not in use` for the other, `You are here` on the page's own run, and a `Set in use` form for the other run's shown version.
  - `test_a_week_with_one_schedule_has_no_list` (Review Focus 1): a program with one run: no `id="week-list"`.
  - `test_a_run_without_a_week_has_no_list` (Review Focus 2): a run with no program and no start date renders its schedules page (200) without the list.
  - `test_the_week_page_links_to_the_other_schedule`: the Week page note links the other workbook to its run's schedules page and has `See both schedules` linking to `…/schedules#week-list`; "Compare or switch" is gone.
  - `test_a_version_not_in_use_says_so_on_its_week_view`: `/schedules/<other shown id>/week` says `Not in use: the RTA, exports and analysis use week.xlsx for this week.`
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_week_list -v` → FAIL (no list; the menu opens the newest run).
- [ ] **Step 3: Implement** `week_list`; `schedules_for` picks the latest week of the program and, in it, the run of `pick_version`'s choice; render the panel as in sample 01 (heading `Schedules for the week of {dd Mon} ({n})`, note `The RTA, the Week page, exports and analysis use the one in use. Open another to look at it or compare, and set it in use if it should count.`, columns Schedule / Newest version / Covered after breaks / Status); Week page note `This week also has <a>X</a> (not in use), uploaded on {Ddd dd Mon}. <a>See both schedules</a>`.
- [ ] **Step 4: Run** the new tests and `webapp.tests.test_week_in_use webapp.tests.test_schedules webapp.tests.test_versions` → PASS (re-pin with a reason only where a test pinned "Compare or switch" or the menu's newest-run rule).
- [ ] **Step 5: Commit** "Phase Z task 1: a week's schedules in one list; pages follow the one in use".

### Task 2: Home follows the picked program and the schedule in use

**Files:**
- Modify: `webapp/app.py` `home` (latest panel, runs filter, in-use map), `webapp/templates/dashboard.html`
- Test: `webapp/tests/test_week_list.py` (class `TheHomePage`)

**Interfaces:**
- Consumes: `store.in_use_runs() -> Dict[(program, week_start), run_id]`.
- Produces: template `in_use_ids: Set[str]`, `not_in_use_ids: Set[str]` (runs whose week has another run in use).

- [ ] **Step 1: Failing tests:**
  - `test_home_shows_the_schedule_in_use_for_the_picked_program`: with SAKS picked and the second upload newer, the panel heading is `In use this week: week.xlsx` (linking the in-use run), not the newest upload.
  - `test_the_runs_table_tags_in_use_and_not_in_use`: the in-use run's row has `In use`, the other `Not in use`; a run of a week with a single run has neither.
  - `test_the_runs_table_shows_only_the_picked_program`: a run of another program is not listed when a program is picked, and is listed with `?all=1`; the table says `Showing SAKS, NMG Tier 2 only. Show runs of all my programs` with that link.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** in `home`: with a program picked, `latest` = the run of `pick_version` for the picked program's latest week when it has a summary, else the newest finished run of that program; heading `In use this week:` when that version is in use, else `Latest schedule:`. Runs filtered to the picked program unless `all=1`.
- [ ] **Step 4: Run** the class plus `webapp.tests.test_runs` → PASS.
- [ ] **Step 5: Commit** "Phase Z task 2: Home follows the picked program and the schedule in use".

### Task 3: The strange things

**Files:**
- Modify: `webapp/templates/schedules.html` (wording, change log), `webapp/templates/run.html` (in-use line, breaks hint), `webapp/app.py` `run_detail` (pass `in_use_note`, `breaks_planned`)
- Test: `webapp/tests/test_week_list.py` (class `TheWording`)

**Interfaces:**
- Produces: `group_changes(changes: List[Dict]) -> List[Dict]` in `webapp/schedules.py`: consecutive changes of one save (same `at` within 2 s, same `reason`, same `problems`) become one group `{"at", "by_name", "reason", "severity", "problems": [str], "items": [change], "people": int}`.

- [ ] **Step 1: Failing tests:**
  - `test_an_upload_is_not_called_the_tools_schedule`: an uploaded run's first version says `No changes: this is the schedule as uploaded.`; the checks list reads `Already in the uploaded schedule (` and the byline `The uploaded schedule never changes;`. An engine run keeps `the tool's schedule`.
  - `test_planned_breaks_are_one_change_with_one_warning`: after auto breaks, the log has one line `Breaks planned automatically for {n} people ({m} changes)` with the save's problems once (`warning: <text>`), and a `<details>` holding the per-person lines; no per-line `warning` tags.
  - `test_the_run_page_says_whether_it_is_in_use`: the in-use run's page says `In use for the week of 04 Oct.`; the other says `Not in use: the RTA uses week.xlsx for the week of 04 Oct.` with a link to `#week-list`.
  - `test_a_version_without_breaks_does_not_claim_after_breaks`: the checks panel of a version with no breaks reads `168 of 168 intervals fully covered (no breaks planned yet)`, not `after breaks`.
  - `test_the_run_page_stops_asking_to_plan_breaks_once_planned`: the in-use run (breaks planned) says `Breaks are planned in Version 2: breaks planned automatically.` and not `Plan the week's breaks next`; the other still offers Plan breaks.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (group in Python, render groups of 3+ changes as one line; 1-2 stay as today).
- [ ] **Step 4: Run** the class plus `webapp.tests.test_schedules webapp.tests.test_auto_breaks webapp.tests.test_ready` → PASS.
- [ ] **Step 5: Commit** "Phase Z task 3: uploads named as uploads, one line per break plan, run pages say in use".

### Task 4: Channel needs for an existing schedule

**Files:**
- Create: `webapp/channel_template.py`
- Modify: `webapp/schedules.py` (`channel_path`, `attach_channels`), `webapp/app.py` (`_channel_lines`, `plan_channels`, two new routes), `webapp/attendance.py:325,380` (the channel source), `webapp/templates/schedules.html` (Channels panel), `webapp/templates/channel_setup.html` (pointer)
- Test: `webapp/tests/test_channel_needs.py` (new)

**Interfaces:**
- Produces: `add_channel_tabs(wb, step: int, languages: List[str], need: Optional[Callable[[str, int, int], float]] = None) -> None` (tabs `Channels - read me`, `Chat {step} Min`, `Phone {step} Min`, `Email {step} Min`, `Email Hours`, `Channel Setup` laid out as the Phase V sample; `need(letter, day, minute)` fills Chat/Phone, else 0; Email per interval empty; Email Hours 0 per day with `Of which {language}` columns when 2+ languages; Channel Setup with the sample's settings and empty language and all-channels sections) and `channel_workbook(path: Path, step: int, languages: List[str]) -> Path`.
- Produces: `ScheduleBook.channel_path(run_id) -> Optional[Path]` (the attached `channels.xlsx`, else the input workbook when it has channel tabs, else None) and `ScheduleBook.attach_channels(run_id, upload: Path) -> List[Tuple[str, str]]` (reads with `read_channels` at the run's interval: ValueError leaves nothing attached; returns `check_lines`).
- Routes: GET `/runs/<run_id>/channel-needs.xlsx` (download name `Channel_needs_{program}_{week}.xlsx`), POST `/runs/<run_id>/channel-needs` (field `workbook`; same permission as editing the run's schedules), redirect to `run_schedules` + `#channels` with a flash.

- [ ] **Step 1: Failing tests:**
  - `test_the_downloaded_workbook_reads_as_empty_needs`: `read_channels` on the download at the run's interval gives Chat and Phone all 0 and email mode `none`; its tabs are the six above.
  - `test_needs_uploaded_to_a_schedule_are_used_without_a_new_run`: filled Chat/Phone uploaded: run count unchanged, `channels.xlsx` exists, the schedules page shows `Plan channels`, and `/schedules/<id>/channels` opens (200).
  - `test_the_rta_counts_channels_from_the_attached_needs`: the day page has the Channels tab after attaching.
  - `test_a_wrong_interval_file_is_refused_and_nothing_is_attached` (Review Focus 4): 60-minute tabs on the 30-minute run: flash names `Chat 60 Min`, no `channels.xlsx`.
  - `test_attached_needs_win_over_the_workbooks_own_tabs` (Review Focus 3): a run uploaded with channel tabs, then needs attached: the panel says `From channel needs added on {date}`, and `channel_path` is the attached file.
  - `test_the_panel_shows_three_steps_without_needs`: copy from sample 03 (`This schedule has no channel needs yet, so its channels cannot be planned.`).
  - `test_associate_channels_points_to_the_schedules`: the pointer copy from sample 03 with a link to the program's Schedules.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_channel_needs -v` → FAIL.
- [ ] **Step 3: Implement**; all four channel readers take `channel_path` (inputs and the requirement tab still come from `input_path`).
- [ ] **Step 4: Run** the new tests plus `webapp.tests.test_channels webapp.tests.test_channel_page webapp.tests.test_channel_day webapp.tests.test_channel_people webapp.tests.test_channel_plan` → PASS.
- [ ] **Step 5: Commit** "Phase Z task 4: add channel needs to a schedule; one channel source".

### Task 5: Channel tabs in the Blank and Example workbooks

**Files:**
- Modify: `tools/build_web_workbooks.py` (call `add_channel_tabs` after building; Example: Phone = ceil(60% of FT Wise), Chat = the rest, so the check matches FT Wise), `webapp/workbooks/*.xlsx` (rebuilt by the tool)
- Test: `webapp/tests/test_channel_needs.py` (class `TheHomeWorkbooks`)

- [ ] **Step 1: Failing tests:** `test_the_home_workbooks_have_the_channel_tabs` (both have the six tabs); `test_the_engine_still_reads_ft_wise` (the engine's own `_discover_requirement_sheet`, imported read-only, returns `FT Wise 30 Min` for both); `test_the_example_needs_match_ft_wise` (`check_lines` on the Example has no `warn`).
- [ ] **Step 2: Run** → FAIL. **Step 3:** extend the builder and run `python3 tools/build_web_workbooks.py` (its own engine check must pass). **Step 4:** tests PASS, plus `webapp.tests.test_runs` (the workbook links). **Step 5: Commit** "Phase Z task 5: the home workbooks carry the channel tabs".

### Task 6: Today's achievement

**Files:**
- Modify: `webapp/templates/_target_tile.html` (the block), `webapp/templates/day.html` (block above the summary line; board Cover cell; Achieved row under the axis), `webapp/static/app.js` (the "now" mark position via CSSOM), `webapp/static/app.css` (section "Phase Z: today's achievement")
- Test: `webapp/tests/test_markup_xy.py` style server tests in `webapp/tests/test_achievement.py` (new) and browser tests in `ThePhaseZInTheBrowser`

**Interfaces:**
- Consumes: `page.target` from `day.at_target` (unchanged): `target, intervals, now, plan, cells[t, pct, ok]`.
- Produces: `target_tile(t, week_url, on, today)` macro: `<section class="achv" aria-labelledby="achv-h">`, heading `Today's achievement` when `on == today`, else `Achievement on {Ddd dd Mon}`; `<p class="achv-num"><b>{now} of {intervals}</b> intervals at {pct}% or more</p>`; share line `{share}% of {today's|the day's} intervals reach the target, with attendance as marked. The plan had {plan} of {intervals}.` + link `Target {pct}% for this week`; strip `<div class="achv-strip" data-now="{minutes}">` with one `<i class="ok|below|none" title="HH:MM: NN%">` per cell; key `At {pct}% or more`, `Below {pct}%`.

- [ ] **Step 1: Failing tests:** `test_the_block_sits_above_the_tabs_on_every_tab` (timeline, board, adherence: `class="achv"` before `class="daybar"`); `test_one_block_per_interval_with_its_result` (count of `<i class=` equals cells; classes match `ok` flags); `test_another_day_is_not_called_today` (Review Focus 5: heading `Achievement on`, no `data-now`); `test_the_board_says_at_target_or_below` (each row with demand has `At target` or `Below` matching the cell's ok); `test_the_timeline_puts_achieved_under_the_hours` (the Achieved row comes right after the axis row); browser `test_the_now_mark_sits_at_the_current_time` (left offset within 1% of minutes/1440 for today).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (strip grid columns by `repeat(n)` through a class per common count `cols-24/48/96` set in CSS, else CSSOM from app.js). **Step 4:** PASS, plus `webapp.tests.test_interval_target webapp.tests.test_day webapp.tests.test_markup_xy`. **Step 5: Commit** "Phase Z task 6: today's achievement on every RTA tab".

### Task 7: Browser check, screens, suite, gate, package

- [ ] **Step 1:** `ThePhaseZInTheBrowser.test_phase_z_screens` → `evidence/phase_z/screens/` (Schedules page with the week list, Home, Week page, Channels panel, Associate channels, RTA timeline and board with achievement, phone RTA); no page errors; phone width ≤ 390 without sideways scroll.
- [ ] **Step 2:** axe crawl (scratch copy) both looks → no violations; note in `evidence/phase_z/CHECKS.md`.
- [ ] **Step 3:** full suite `$PY -m unittest discover -s webapp/tests -t .` → OK; `git checkout -- evidence/` for earlier phases' screens.
- [ ] **Step 4:** `python3 tools/build_production_package.py` → GATE PASS; split into halves under 30 MiB; rejoin hash matches.
- [ ] **Step 5:** commit, push, report (rulings, deferred minors, install steps with the size-based join).
