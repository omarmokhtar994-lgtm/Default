# Phase AC: review fixes and open items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the twelve findings and the still-open items of `evidence/phase_ac/REVIEW.md`, each proven by a
test that failed first.

**Architecture:** Small, local fixes in the existing modules; no new pages, no new look. Security and crash fixes
first, then the RTA, posts, the schedule pages, then polish.

**Tech Stack:** Flask 3.1, Jinja2 (strict CSP), vanilla JS, SQLite, Playwright.

**Spec:** `evidence/phase_ac/REVIEW.md` (owner, 2026-10-10: "Fix rest of the items, and make a deep review on the
website current status and fix any bugs or improve any vision").

## Global Constraints

- Engine untouched; protected workbooks and `engine/regression_assets` untouched.
- Strict CSP: no inline script, style or event handlers; sentence case; DESIGN.md v3 colours.
- Do not modify or delete tests to pass; re-pin only when this phase changes the measured contract, with the reason.
- Notification links never shown or logged; times in Egypt time.
- Release gate: `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`.

## Review Focus

1. Signed-in people at the moment of the upgrade must not all be signed out (session stamp missing = taken as
   current). Task 1 `test_sessions_from_before_the_upgrade_stay`.
2. A user changing their own password stays signed in on that device. Task 1 `test_own_password_change_keeps_this_session`.
3. The cache lock must not hold a slow workbook read (only dict operations). Task 2 `test_a_slow_read_does_not_block_other_files`.
4. The `+ Add` tick with JavaScript off still posts (server default unchanged). Task 3 `test_without_script_the_tick_is_plain`.
5. Teams text keeps ordinary brackets readable. Task 4 `test_brackets_stay_readable`.

---

### Task 1: Security: redirects stay on the site; a password change ends other sessions

**Files:** Modify `webapp/app.py` (login, set_theme, change_password, admin reset), `webapp/auth.py`; Test
`webapp/tests/test_review_security.py`.

**Interfaces:** Produces `safe_next(target: str) -> str` in `webapp/auth.py` (returns `target` only when it matches
`^/(?![/\\])[^\x00-\x20\\]*$`, else `""`) and `session_stamp(user) -> str` (first 16 hex of sha256 of
`password_hash`).

- [ ] **Step 1: failing tests:** `test_sign_in_never_redirects_off_site` (next values `/\texample.com`,
  `/\t/example.com`, `/\nexample.com`, `//example.com`, `/\\example.com`, `https://example.com`, `/%09/example.com`
  each give `Location: /`; `/day?program=X` is kept); `test_theme_never_redirects_off_site` (same values);
  `test_password_reset_ends_other_sessions` (admin resets Nour's password: Nour's open client is sent to the sign-in
  page); `test_own_password_change_keeps_this_session` (Nour changes her own: this client stays, a second client of
  Nour's is signed out); `test_sessions_from_before_the_upgrade_stay` (a session without a stamp stays signed in and
  gets one).
- [ ] **Step 2:** run `$PY -m unittest webapp.tests.test_review_security` — Expected: failures.
- [ ] **Step 3:** implement; login sets `session["pw"]`; `load_user` clears the session on a mismatch and sets a
  missing stamp; `change_password` refreshes this session's stamp.
- [ ] **Step 4:** run it plus `test_auth`/`test_runs` sign-in tests — Expected: pass.
- [ ] **Step 5:** commit "Phase AC task 1: redirects stay on the site; a password change ends other sessions".

### Task 2: Crashes: locked caches, dates in range, a 405 page

**Files:** Modify `webapp/day.py`, `webapp/channels.py`, `webapp/app.py`; Test `webapp/tests/test_review_crashes.py`.

- [ ] **Step 1: failing tests:** `test_channel_cache_survives_threads` (8 threads × 2000 `has_channel_needs` over
  20 files with `sys.setswitchinterval(1e-6)` and the workbook reader stubbed: no exception);
  `test_input_cache_survives_threads` (same over `day._remember`-style helper via `read_inputs` with `load_workbook`
  stubbed); `test_a_slow_read_does_not_block_other_files`; `test_far_dates_are_refused_not_crashed`
  (`/day?date=9999-12-31`, `0001-01-01`, `/overview?date=9999-12-31`, `/week?week=9999-12-26` → 200 with the
  normal "pick a day" state, never 500); `test_wrong_method_says_what_to_do` (GET `/runs` → 405 page in the site's
  layout: "This address opens only from its form." and "Go back, then send the form again.").
- [ ] **Step 2:** run — Expected: failures.
- [ ] **Step 3:** a module `threading.Lock` around every read and write of each `_CACHE` (reading the workbook stays
  outside the lock); `_date` returns None outside 2000-01-01..2099-12-31; `start_date` likewise; `@app.errorhandler(405)`.
- [ ] **Step 4:** run it plus `test_day`, `test_channels`, `test_channel_needs` — Expected: pass.
- [ ] **Step 5:** commit.

### Task 3: The RTA

**Files:** Modify `webapp/app.py` (add panel, day title), `webapp/templates/day.html`, `webapp/templates/wallboard.html`,
`webapp/static/app.js`, `webapp/static/app.css`; Test `webapp/tests/test_review_rta.py`.

- [ ] **Step 1: failing tests:** `test_add_lists_absent_people_last_and_says_so` (with Associate 006 sick: the first
  option is someone present; the sick option reads "Associate 006, 03:00 - 12:00, ENG, sick");
  `test_the_tick_knows_what_posts` (dialog carries `data-post-kinds` of the LOB's ticked kinds and each `what` radio
  a `data-kind`: Sick → private, Coaching → aux, Overtime → overtime); `test_preview_tick_says_preview`
  ("Show in the preview on the Notifications page" with mode preview); `test_without_script_the_tick_is_plain`;
  `test_wallboard_has_main_and_names` (`<main` once; "No schedule for SAKS, NMG Tier 2 today.");
  `test_day_title_uses_the_name` (`<title>The day: SAKS, NMG Tier 2 on Team Scheduler`).
- [ ] **Step 2:** run — Expected: failures.
- [ ] **Step 3:** sort key `(status in ABSENT, not on shift now, start, name)` and a sixth tuple item "sick" /
  "unplanned leave"; tick hidden by app.js when the picked kind is private or not ticked; `+ Add` title "Add for
  10:00 to 11:00", and "Add overtime for {name}" while Overtime is picked (app.js); `.dlg { overscroll-behavior:
  contain }`.
- [ ] **Step 4:** run it plus `test_notify_rta`, `test_day`, `test_overtime_side` — Expected: pass; re-pin any
  assertion on the old title or option text with the reason.
- [ ] **Step 5:** commit.

### Task 4: Group posts

**Files:** Modify `webapp/notify.py`, `webapp/app.py`, `webapp/store.py`; Test extend `webapp/tests/test_notify_posts.py`
and `webapp/tests/test_notifications_page.py`.

- [ ] **Step 1: failing tests:** `test_teams_text_cannot_make_a_link` (`"with [Lina](https://evil.example)"` → no
  `](` in the card); `test_brackets_stay_readable` ("Break [1]" unchanged); `test_page_reads_every_lob_at_once`
  (the Notifications page makes at most 4 store queries for 30 LOBs, counted by wrapping `Store._db`).
- [ ] **Step 2–5:** run, implement (`_plain` for Teams replaces `](` with `] (`; `Store.notify_overview()` returns
  settings and newest post per unit in two queries), run, commit.

### Task 5: Schedule, Week and run pages

**Files:** Modify `webapp/app.py`, `webapp/schedules.py`, `webapp/runs.py`, `webapp/templates/week.html`,
`webapp/templates/schedules.html`, `webapp/templates/day.html`; Test `webapp/tests/test_review_pages.py`.

- [ ] **Step 1: failing tests:** `test_associates_tile_for_an_uploaded_schedule` (the count of people with a shift
  that week, and "–" when unknown); `test_plural_words` ("1 interval", "1 associate-interval");
  `test_tile_fraction_stays_on_one_line` (`<b>167<small class="of"> of 168</small></b>`);
  `test_failed_run_delete_wording` ("removes it for everyone" with no version count when there are none);
  `test_unreadable_input_keeps_the_schedules_page` (input.xlsx replaced by garbage: 200, Channels panel says the
  input cannot be read); `test_resume_refused_for_readiness_and_unschedulable` (POST resume → "This run cannot be
  resumed: …", status unchanged); `test_a_long_save_is_one_save` (changes 1.5 s apart over 6 s → one group);
  `test_no_channel_plan_is_one_line` (channel tabs, no plan: "No channel plan for this day yet." and no name list).
- [ ] **Step 2–5:** run, implement (`can_resume(run)` used by the page and the route; group by the gap to the
  previous change), run with `test_week_list`, `test_schedules_by_week`, `test_delete_schedule`, `test_channel_day`,
  commit.

### Task 6: Polish and housekeeping

**Files:** Modify `webapp/static/app.css`, `webapp/templates/base.html`, `webapp/static/app.js`, `webapp/programs.py`,
`webapp/runs.py`; Test `webapp/tests/test_review_polish.py`.

- [ ] **Step 1: failing tests:** `test_time_fields_share_the_field_style` (app.css gives `input[type=time]` the
  padding, background and radius of text fields); `test_theme_color_meta` (`<meta name="theme-color"` for each look);
  `test_names_of_only_dots_are_refused` ("." and ".." refused: "Use letters or numbers in the name.");
  `test_incoming_leftovers_are_swept` (an `_incoming/*.upload` older than a day goes on cleanup; a fresh one stays).
- [ ] **Step 2–5:** run, implement, run with `test_programs`, `test_runs`, commit. The Back trail skipping the sign-in
  page is proven in Task 7's browser test.

### Task 7: Browser checks, suite, gate, package

- [ ] `ThePhaseACInTheBrowser`: `+ Add` opens on a present person with no error; picking Sick hides the tick,
  Overtime retitles the dialog; Back after signing in with a `next` never shows the sign-in page; the left-menu
  picker waits for Enter with two programs; Week page tiles on one line at 1366 px; no sideways scroll at 390 and
  320; no page errors. Point Phase W's `rta_intervals_at_target.png` at the achievement block (screenshot target
  only; its assertions unchanged).
- [ ] Re-run `acsweep.py` and `acconsole.py`: no exceptions, no 5xx.
- [ ] Full suite; `git checkout -- evidence/`; self-review; gate and package; two halves of different sizes; push.
