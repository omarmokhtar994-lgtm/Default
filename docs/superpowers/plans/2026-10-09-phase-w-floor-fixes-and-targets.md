# Phase W: Back, faster exports, the schedule in use, auto breaks, shift filter, interval target — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Back link and the slow or hanging exports, make every page follow the schedule in use, add one-click break planning, a shift filter on the RTA Timeline and a per-week interval target counted on the RTA.

**Architecture:** Website only (Flask, SQLite, Jinja2, strict CSP, vanilla JS in app.js). The engine is not touched. Break planning reuses `break_plan.suggest` and `ScheduleBook.save_breaks`; the day figures reuse `day_view` cells (`required`, `now`, `plan`).

**Tech Stack:** Python 3.11, Flask 3.1, openpyxl, unittest, Playwright (Chromium at /opt/pw-browsers/chromium).

**Spec:** the owner's messages of 2026-10-09 (quoted below) and the approved samples `evidence/phase_w/samples/1..9` (copied from the session scratchpad in Task 1).

- "if i did choose before breaks in use i need a button to auto fill breaks for the selected schedule in case it doesnt have breaks in case it already has breaks we needed it to be rescheduled breaks, back button is not working to do anything"
- "Exporting as well lags alot and sometimes it just keeps loading with no actual export"
- "i need a filter RTA Timeline to filter by shift so we can mark attendance per shift easily"
- "a drop for each week to choose the complaince target per interval for example if 90% and on a daily basis view in RTA to have something showing count of intervals above 90% or the choosen tatget / total intervals"
- Answered "Yea" to: upload warning for a week that already has schedules, Week/analytics follow the schedule in use, newest schedule when none is in use, a note for records of people not in the schedule in use. "Go ahead" on the samples with the stated defaults.

## Global Constraints

- Engine untouched ("dont change anything kn the engine"); protected workbooks and `engine/regression_assets` keep their bytes.
- No silent roster or demand changes; every saved change is a new version checked by the validator, as today.
- Fail closed and say why in plain words; never a hidden error.
- Strict CSP: no inline JS or CSS; JS in `webapp/static/app.js`, CSS in `webapp/static/app.css`.
- Real employee names never in fixtures; "Associate NN".
- Times in Egypt time (UTC+3).
- Gate: `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`; website suite `python -m unittest discover -s webapp/tests -t .`.
- Defaults the owner accepted: a re-plan is put in use only when it is not worse; targets 100, 95, 90, 85, 80 % (plus the workbook's own if different); admins and supervisors change the target.

## Review Focus

1. A version that is an edited draft not in use: auto breaks must still leave it as it is (new version), not edit it in place — test in Task 5.
2. A day with no demand at all (every interval `required` 0): the target tile says "no intervals with demand", never "0 of 0 (0%)" or a division error — test in Task 6.
3. Two schedules for the week where neither is in use and one is an engine run older than an uploaded one: the newer wins everywhere the fallback is used (RTA, Week page) — test in Task 3.
4. An export whose period has a missing input workbook for one LOB: still skipped as today (no crash), and the 5-minute stop still says what to untick — test in Task 1.
5. The shift filter on a day with overnight people from yesterday: they appear under "From yesterday", and a filter value matching no one shows an empty state with a link to all shifts — test in Task 4.

---

### Task 1: Faster exports that say what they are doing

**Files:** Modify `webapp/day.py` (read_inputs), `webapp/exports.py`, `webapp/app.py` (exports_download), `webapp/templates/exports.html`, `webapp/static/app.js`, `webapp/static/app.css`. Test: `webapp/tests/test_exports_speed.py`. Copy samples to `evidence/phase_w/samples/`.

**Interfaces:**
- Produces: `read_inputs(path)` cached per (path, mtime) and returning a new key `"target"` (ratio, from the instruction "Target" / "Coverage Target" / "Interval Target", the engine's names; 0.90 when unset; a value above 1 is a percent). `exports.build(..., deadline: Optional[float] = None)`; `exports.ExportTooSlow(ValueError)`; `exports.SLOW_SAID` (the message).

- [ ] Step 1: tests (RED): `test_a_workbook_is_read_once` (patch `webapp.day.load_workbook` with `wraps`; two `read_inputs` calls → 1 load); `test_the_workbook_target_is_read` (fixture with Instructions "Target" 0.85 → 0.85; without → 0.9); `test_worked_and_summary_share_each_day` (count `DayBook.page` calls during `build(kinds=["worked","summary"])` = one per LOB-day plus the summary's next-day look, not two per LOB-day); `test_an_export_past_its_deadline_stops_and_says_what_to_untick` (deadline in the past → `ExportTooSlow` whose text names "Worked hours and adherence" and "Daily summary"); `test_the_download_answers_a_script_in_json` (GET with header `X-Requested-With: fetch` and a bad period → 400 JSON `{"error": ...}`).
- [ ] Step 2: run, expect the five to fail for the stated reasons.
- [ ] Step 3: implement. read_inputs: rename the loop variable (the root cause: `for key, names in ...` overwrote the cache key). exports: a `_Days` wrapper memoising `page(program, on, measure)` and delegating everything else; check `deadline` once per LOB-day in the per-day builders. Route: `deadline = time.monotonic() + 300`; JSON error when `X-Requested-With: fetch`. JS: the export form downloads through `fetch`, shows "Preparing your export…" with a seconds counter, then "Ready: <file> (<KB> KB) downloaded in N s. Download again", or the error in an `.alert.bad`; without JS the form still works as a plain GET.
- [ ] Step 4: run the file and `test_exports` (existing) → OK. Measure the scratch profile again (before 45.4 s) and ledger the number.
- [ ] Step 5: commit.

### Task 2: Back goes to the last different page, else up one level

**Files:** Modify `webapp/app.py` (`BACK`, `_globals`), `webapp/static/app.js`. Test: `webapp/tests/test_back.py`.

**Interfaces:** Produces `_parent_url(endpoint, view_args) -> str`: plan_breaks, plan_channels, schedule_week, schedule_download → that version's run schedules page; run_schedules, run_week → run page; program → programs; day pages → home; others → home.

- [ ] Step 1: tests (RED): `test_plan_breaks_goes_up_to_its_schedule` (the page's `data-back` href is `/runs/<run>/schedules?v=<id>`); `test_a_run_schedules_page_goes_up_to_the_run`.
- [ ] Step 2: run → FAIL (href is `/`).
- [ ] Step 3: implement the parent map; JS keeps a short trail in `sessionStorage` (`ts-trail`, last 20 addresses, a reload of the same address not added) and Back goes to the newest entry whose path differs from this page's path, else follows the link. Storage errors fall back to the link.
- [ ] Step 4: run → OK (the browser behaviour is checked in Task 7).
- [ ] Step 5: commit.

### Task 3: Which schedule counts for a week

**Files:** Modify `webapp/attendance.py` (`pick_version`), `webapp/analytics.py` (`program_weeks`), `webapp/app.py` (`week_page`, new `/runs/week-check`, upload flash), `webapp/templates/week.html`, `webapp/templates/dashboard.html`, `webapp/static/app.js`. Test: `webapp/tests/test_week_in_use.py`.

**Interfaces:**
- Produces `pick_version(versions)`: in use first; else the newest by the run's first version time, the tool's "after breaks" before "before breaks" within one run (FALLBACK notes unchanged).
- `program_weeks(runs, in_use: Optional[Dict[Tuple[str, str], str]] = None)`: per (program, week) the run whose version is in use when it is counted, else the latest finished (unchanged).
- `ScheduleBook.week_note(program, week_start) -> Dict` {"count", "in_use": row or None, "others": [workbook names]}; `GET /runs/week-check?program=&week=` → JSON {"count", "text"} (empty text when none); the same text flashed after an upload.
- `/week?program=&week=`: when the week has versions, the week view of the version `pick_version` chooses, with "From the schedule in use: …" (or the fallback note) and "This week also has …"; weeks listed = run weeks ∪ version weeks.

- [ ] Step 1: tests (RED): `test_the_newest_schedule_counts_when_none_is_in_use`; `test_one_runs_after_breaks_beats_its_before_breaks`; `test_analytics_follow_the_schedule_in_use`; `test_the_week_page_shows_an_uploaded_schedule` (no "No finished run"); `test_the_upload_says_the_week_already_has_schedules` (JSON text names the count, the label in use and its workbook; the flash after a second upload says it).
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement; the warning text: "{unit} has {n} schedule(s) for the week of {Sun dd Mon}. In use: {label} from {workbook}. Yours is kept next to them. The RTA keeps reading the one in use until you choose another on the Schedules page." (no in-use version: "None is in use; the RTA reads the newest.").
- [ ] Step 4: run this file plus `test_attendance`, `test_analytics`, `test_week` → OK; re-pin only with a written reason.
- [ ] Step 5: commit.

### Task 4: The RTA: records not shown, and the Timeline by shift start

**Files:** Modify `webapp/attendance.py` (`page`), `webapp/day.py` (new `shift_groups`), `webapp/app.py` (day route `shift` arg), `webapp/templates/day.html`, `webapp/static/app.css`. Test: `webapp/tests/test_shift_filter.py`.

**Interfaces:**
- `DayBook.page(...)["unlisted"]`: [{"name", "what"}] for people with this day's attendance, activities, break moves or channel changes who are not on the floor list; "what" in words ("Sick", "Late, arrived 09:20", "2 records").
- `shift_groups(view, from_now: Optional[int]) -> List[Dict]`: {"key": "09:00" or "earlier", "label", "people", "late", "off", "aux", "next": bool}, sorted by start, "earlier" (From yesterday) first.
- Day route: `shift=` keeps only lanes whose own start (or "earlier") matches; the attendance select reload keeps the address, so the filter stays.

- [ ] Step 1: tests (RED): `test_records_of_people_not_in_the_schedule_are_said`; `test_shift_groups_count_people_late_and_off`; `test_the_timeline_keeps_only_the_chosen_start`; `test_overnight_people_are_under_from_yesterday`; `test_a_start_no_one_has_says_so`.
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement; chips are links (no JS), the chosen one `aria-current`, "starts next" on today only.
- [ ] Step 4: run this file plus `test_attendance`, `test_day` → OK.
- [ ] Step 5: commit.

### Task 5: Plan breaks automatically

**Files:** Modify `webapp/schedules.py` (`auto_breaks`, `_save`/`_draft_from` gain `fresh` and `label`), `webapp/app.py` (`POST /schedules/<id>/auto-breaks`), `webapp/templates/schedules.html`, `webapp/templates/week.html`. Test: `webapp/tests/test_auto_breaks.py`.

**Interfaces:**
- `ScheduleBook.auto_breaks(schedule_id, user_id, use: bool) -> Dict` {"id", "mode": "fill"|"replan", "placed", "empty", "used": bool, "before": metrics, "after": metrics, "said": str}. Fill when the version has no breaks; otherwise every break is planned again. Days planned in order with `suggest` on the week so far (`week_with`), so overnight breaks see the day before. Saved with `save_breaks(..., fresh=True, label="Version N: breaks planned automatically")`; reason "Breaks planned automatically".
- Use rule (pre-registered): fill → in use when `use`; re-plan → in use only when `use` and the new version's fully covered intervals after breaks are at least the old's and its broken rules are no more than the old's; else kept, said.

- [ ] Step 1: tests (RED): `test_a_version_without_breaks_gets_every_break` (placed > 0, every working person-day has its breaks, the source version unchanged, new version in use, change reason); `test_an_edited_draft_is_left_as_it_is`; `test_not_worse_compares_covered_intervals_and_broken_rules` (`not_worse(before, after)` on hand-made metric dicts: fewer covered intervals → False; more broken rules → False; equal → True); `test_a_replan_is_used_only_when_not_worse` (a re-plan of a version planned by this same button is equal, so it is used; with `not_worse` returning False the new version is kept, not in use, and the flash says so); `test_the_buttons_say_fill_or_replan` (Schedules page shows "Plan breaks automatically" for a version without breaks and "Re-plan breaks automatically" with breaks; the Week page shows it for the version shown; planners who may not set in use see it without the "Use it" box).
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement; the flash says what the sample says.
- [ ] Step 4: run this file plus `test_breaks_plan` (existing break page tests) and `test_channel_page` → OK.
- [ ] Step 5: commit.

### Task 6: The interval target

**Files:** Modify `webapp/store.py` (table `interval_targets`, `get/set_interval_target`, rename/delete cascade), `webapp/attendance.py` (`target_for`), `webapp/day.py` (`at_target(cells, target)`), `webapp/app.py` (`POST /week/target`, day and week pages), `webapp/handover.py`, `webapp/exports.py` (summary columns, `interval_target_changed` in OTHER_EVENTS), templates `day.html`, `week.html`. Test: `webapp/tests/test_interval_target.py`.

**Interfaces:**
- `at_target(cells, target) -> {"target", "intervals", "now", "plan"}`: intervals = cells with `required > 0`; an interval is achieved when `now >= target × required` (plan likewise with `plan`).
- `DayBook.target_for(program, on) -> (ratio, source)` source "set" (with who) or "workbook".
- `POST /week/target` (`manager_required`), fields program, week, target ∈ {100, 95, 90, 85, 80, the workbook's own}; event `interval_target_changed`.
- Day page tile: "Intervals at {t}% or more: {now} of {n} ({share}%), plan {plan} of {n}" or "No intervals with demand"; a Timeline row "Achieved (target {t}%)" per interval (below target marked). Week page panel with the drop-down and the seven days. Daily summary export columns "Interval target %", "Intervals at target", "Intervals with demand".

- [ ] Step 1: tests (RED): `test_at_target_counts_against_required`; `test_a_day_without_demand_says_so`; `test_the_week_target_defaults_to_the_workbook`; `test_a_supervisor_sets_the_target_a_planner_cannot`; `test_the_day_tile_and_row_use_the_week_target`; `test_the_daily_summary_carries_the_target`; `test_a_rename_moves_the_targets`.
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement.
- [ ] Step 4: run this file plus `test_exports`, `test_run_admin`, `test_handover` → OK.
- [ ] Step 5: commit.

### Task 7: Browser check, suite, gate, package, report

**Files:** Modify `webapp/tests/test_ui_playwright.py` (class `ThePhaseWInTheBrowser` at the end), screens in `evidence/phase_w/screens/`.

- [ ] Step 1: browser test: Back after Suggest on Plan breaks leaves the page; export downloads through the button with "Ready"; Plan breaks automatically makes the version and the flash; the shift chips filter the Timeline and survive an attendance change; the target drop-down changes the RTA tile; the upload warning appears after picking the LOB and week.
- [ ] Step 2: full website suite, then restore the screenshots of other phases.
- [ ] Step 3: final self-review (ledger), fixes RED→GREEN.
- [ ] Step 4: `run_tests.sh` gate via `tools/build_production_package.py`, split into halves under 30 MB, send, report with rulings and deferred minors.
