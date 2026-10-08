# Phase Q: programs, LOBs, access and the new layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Programs hold LOBs and the defaults a new schedule starts from; each person sees only their programs (admins all; supervisors manage their programs' planners); the site gets a slim top bar and a left menu; Home starts from the programs; a program's Overview is separate from its RTA.

**Architecture:** Every table keeps its `program` text column as the stable key of a schedule unit (a LOB, or a program without LOBs). A registry (`programs`, `lobs`) says which program and LOB a key belongs to, so nothing stored is rewritten and existing names such as "AE/AR B2B" are adopted into a program as a LOB from the Programs and LOBs page. `webapp/access.py` answers who may open which keys and manage whom; routes check it. Layout changes live in `base.html`, `app.css` and `app.js`.

**Tech Stack:** Flask 3.1, SQLite, Jinja2, unittest, Playwright.

**Spec:** the owner's message of 2026-10-08 ("in the home page first choose the program and i can assign user for each program … supervisor access … today view … separated … top bar … sign out only and settings … left or right side … rest of tabs") with the owner's answers: a LOB is a team inside a program; people see only their assigned programs, New schedule open to everyone for any program; supervisors manage only their programs' planners. Samples: `phase_q_home.png`, `phase_q_overview.png`, `phase_q_rta.png`, `phase_q_people.png`, `phase_q_settings.png` (sent 2026-10-08).

## Global Constraints

- Engine untouched ("dont change anything in the engine"). Protected workbooks and `engine/regression_assets` untouched.
- No hidden errors; fail closed on access (an unknown key or a program not assigned → 403, never an empty page that looks like no data).
- Do not modify tests to pass: where the owner changed a contract (layout, access), the test is re-pinned with the reason in it; test fixtures may grant the old all-programs access with a comment.
- People from before Phase Q keep all-programs access (`all_programs = 1` set once when the column is added) so nobody is locked out by the update; new people get the programs chosen when they are added.
- Strict CSP (no inline style or script); CSRF on every POST; passwords never shown except the one-time temporary password, never logged.
- Real employee names never in fixtures or samples: "Associate NN".
- Egypt time; commit and push only to `claude/handoff-document-m6egz2`.

## Review Focus

1. A person with programs assigned opens another program's key by URL (`/day?program=…`, `/overview`, `/week`, `/programs/<key>`, `/exports/download?program=…`, `/schedules/<id>`) → 403 — test each route family.
2. A supervisor tries to reset an admin's or another supervisor's password, or give a planner a program the supervisor does not have → refused, nothing changed — test.
3. Adopting an existing key that has runs, versions and day records under a program as a LOB keeps every page working for that key (no data moved) — test the day page and program page after adoption.
4. A program with no LOBs still works as one unit (its name is its key) — test.
5. The left menu at phone width collapses above the content without horizontal scroll — browser test at 390 px.

---

### Task 1: The registry and access (store, programs.py, access.py)

**Files:** Modify `webapp/store.py` (tables `programs`, `lobs`, `user_programs`; users columns `is_supervisor`, `all_programs` with the one-time migration), Create `webapp/programs.py`, `webapp/access.py`; Test `webapp/tests/test_programs.py`.

**Interfaces (produces):**
- `ProgramBook(store)`: `sync() -> int` (registers each run program key that no program or LOB claims as a program of that name); `tree() -> List[Dict]` (each `{"id", "name", "start_day", "run_mode", "options", "lobs": [{"id","name","key"}], "units": [key, …]}`; `units` = LOB keys, plus the program's own name when it has no LOBs or runs exist under it); `unit(key) -> Optional[Dict]` (`{"program": prog, "lob": lob or None, "label": "AE, AR B2B" or "NMG"}`); `add_program(name) -> int`; `add_lob(program_id, name) -> str` (new key `f"{program} {lob}"`, refused if taken); `adopt(key, program_id, lob_name)` (an existing key becomes a LOB of that program; a bare program row of that name with no LOBs is removed and its people are given the target program); `set_defaults(program_id, start_day: int, run_mode: str, options: Dict)`; `rename(program_id=None, lob_id=None, name)` (display names only; keys never change).
- `Access(store, user)`: `keys() -> Optional[Set[str]]` (None = every key: admins and `all_programs`); `can_open(key) -> bool`; `programs() -> List[Dict]` (the tree filtered); `can_manage(target) -> bool` (admin: anyone but themselves for switch-off; supervisor: planners whose programs meet theirs); `grantable() -> List[Dict]` (programs an actor may give).
- Roles: `role(user) -> str` in access.py: "Admin" if `is_admin`, "Supervisor" if `is_supervisor`, else "Planner".

- [ ] Tests (`test_programs.py`): `test_sync_registers_existing_keys`; `test_add_lob_makes_a_unit`; `test_adopt_keeps_the_key_and_its_data` (runs/versions/attendance under "AE/AR B2B" adopted as AE / AR B2B → `unit("AE/AR B2B")["label"] == "AE, AR B2B"`, DayBook page still found); `test_program_without_lobs_is_one_unit`; `test_planner_sees_only_their_programs`; `test_people_from_before_keep_all_programs` (old database without the columns → existing users `all_programs == 1`); `test_supervisor_manages_their_programs_planners_only` (not admins, not supervisors, not planners of other programs).
- [ ] RED, implement, GREEN, commit.

### Task 2: People and roles

**Files:** Modify `webapp/app.py` (`admin_users`, `admin_user_action` → `people_page`, `person_action` at the same URLs; `admin_required` → `manager_required` for supervisors too), `webapp/templates/admin_users.html`; Test `webapp/tests/test_runs.py` (`ThePeoplePage`).

Rules: add a person with role (Planner; Supervisor and Admin by admins only) and programs (checkboxes of `grantable()`, or "All programs" for admins to give); per row: Programs (edit), Reset password, Switch off/on; supervisors see and act only on `can_manage` people; every action recorded as now plus `user_programs_changed`.

- [ ] Tests: admin adds a supervisor for AE; supervisor adds a planner for AE (not for NMG: 403/refused); supervisor resets the planner's password (temporary shown once, not recorded); supervisor cannot reset an admin's (403); events list `user_programs_changed` without passwords.
- [ ] RED, implement, GREEN, commit.

### Task 3: Programs and LOBs page and program defaults

**Files:** Create `webapp/templates/program_setup.html`; Modify `webapp/app.py` (`GET/POST /setup/programs`, admin only), `dashboard.html` (New schedule: Program and LOB selects from `Access.programs()` for the dropdowns, all programs for New schedule; start date, run length and advanced options prefilled from the program's defaults via `data-` attributes and app.js); Test `test_runs.py` (`TheProgramSetup`).

- [ ] Tests: admin adds program AE, LOB "IT", adopts "AE/AR B2B" as LOB "AR B2B", sets Monday start and Deep; the upload form offers AE with LOBs AR B2B and IT and its `data-defaults` carry `{"start_day": 1, "run_mode": "DEEP"}`; an upload with program AE, LOB IT stores key "AE IT".
- [ ] RED, implement, GREEN, commit.

### Task 4: Access on every program page

**Files:** Modify `webapp/app.py` (helper `_unit_or_403(key)`; day/overview/week/programs/program/schedules/exports/coach/handover/wallboard/run pages and their POSTs; lists filtered: home runs, programs, team, exports' program choices); Test `test_runs.py` (`TheProgramAccess`); fixture `make_app` gives `sara` `all_programs` with a comment.

- [ ] Tests: Lina (planner, NMG only) gets 403 on AE's day, overview, week, program page, schedules, exports download and on a POST to /day/attendance; sees only NMG on Home and in Exports' choices; can still upload a run for any program and open her own run.
- [ ] RED, implement, GREEN, commit.

### Task 5: Layout, Home, Overview and RTA

**Files:** Modify `base.html` (top bar: brand; name and role; Light/Dark look; Settings → account page; Sign out. Left menu: New schedule; program and LOB pickers when a unit is open; All programs, Overview, RTA, Week, Schedules, Analysis, Exports; Manage: People, Programs and LOBs, Team), `app.css` (left menu; phone: menu above content), `app.js` (pickers navigate), `dashboard.html` (Home: program cards from `Access.programs()` with LOB chips and each unit's latest week; New schedule panel; runs in progress; recent runs), Create `overview.html` and route `/overview` (tiles, next six hours, needs attention, shortcuts), Modify `day.html` (RTA: the big tiles move to Overview; a one-line summary stays); Test `test_runs.py`, `test_ui_playwright.py` (`TheNewLayoutInTheBrowser`, screens to `evidence/phase_q/screens/`).

- [ ] Tests: the top bar holds only the name, the look switch, Settings and Sign out; the left menu lists the program pages with the open one marked; Home lists only the person's programs; `/overview` shows the four tiles and the next six intervals; `/day` keeps the board and timeline; at 390 px the page has no horizontal scroll. Earlier tests that pin the old top-bar links are re-pinned with the reason.
- [ ] RED, implement, GREEN, commit.

### Task 6: LOB filters, verify and ship

**Files:** Modify `exports.html`/`exports.py` route args (program then LOB; "all LOBs" = the program's keys), `coach.html`, `week.html`, `programs.html` (programs with their LOBs; each LOB's page as today); Test `test_runs.py`.

- [ ] Tests: Exports with program AE and all LOBs includes both keys' rows; with LOB IT only its key; Programs page groups AR B2B and IT under AE.
- [ ] Full website suite; earlier screenshots restored; gate + package; engine and protected workbooks unchanged; send screenshots, package and update steps.
