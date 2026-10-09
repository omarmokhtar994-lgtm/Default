# Phase XY: review fixes and colours Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build every Phase X review fix and all three parts of the Phase Y colour proposal on the website, as the owner approved them (2026-10-10 00:5x Egypt time: "All of them", parts 1, 2 and 3).

**Architecture:** Website only (`webapp/`): two server changes (error pages, the department removal check), markup in four templates, two behaviours in `static/app.js`, and the colour system rebuilt in `static/app.css` from `evidence/phase_y/proposal.css` (tokens into the token blocks, each rule into the rule it overrides). The engine is not touched.

**Tech Stack:** Flask 3.1, Jinja2, one stylesheet and one script under a strict CSP, unittest, Playwright with Chromium 141 (`/opt/pw-browsers/chromium`).

**Spec:** `evidence/phase_x/REVIEW.md` (findings 1-14, samples `evidence/phase_x/samples/01-09`) and `evidence/phase_y/PALETTE.md` with `evidence/phase_y/proposal.css` (samples `evidence/phase_y/samples/01-10`).

## Global Constraints

- Engine untouched; protected workbooks and `engine/regression_assets` untouched.
- Strict CSP: no inline script, style or event handler; new markup uses classes, new behaviour lives in `app.js`.
- Copy in sentence case, plain words; no exclamation marks; errors say what to do next.
- Colour values exactly as in `evidence/phase_y/proposal.css` (night and day blocks, both `:root[data-theme="light"]` and the `prefers-color-scheme` block).
- Every text pair 4.5:1 or more, every edge and status shape 3:1 or more, measured on the rendered page.
- Do not modify tests to pass; re-pin only where the owner changed the contract, with the reason in the test.
- Times in Egypt time; commit and push only to `claude/handoff-document-m6egz2`; gate `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`.

## Review Focus

1. A list opened with Alt+Down or Space and closed with Enter must save once, with no second Enter (the pending state is only for arrows on a closed list).
2. A schedule that finishes while the New run form is in use must not reload Home; the panel says it finished and links to it.
3. A pending attendance change left with Tab must go back to the saved value and drop the note, never stay half-saved on screen.
4. The 403 for a LOB names "Program, LOB" (the unit label), and a stale `?remove=` id shows no check panel.
5. A person who picked the day look (`data-theme="light"`) gets the same colours as a device in light mode.

Each line has its test in the owning task (Tasks 4, 5, 4, 1 and 2, 6).

---

### Task 1: Error pages say why and what to do

**Files:**
- Modify: `webapp/app.py:250-258` (program check), `webapp/app.py:2276-2289` (handlers)
- Modify: `webapp/auth.py:52-70` (`manager_required`, `admin_required`)
- Modify: `webapp/templates/error.html`
- Test: `webapp/tests/test_errors.py` (new)

**Interfaces:**
- Produces: `error.html` takes `message` (h1) and `hint` (paragraph, may be empty) and links "Go to Home".

- [ ] **Step 1: Write the failing tests** in `webapp/tests/test_errors.py`, class `TheErrorPages` (setUp as `test_contacts.TheContactsPage`: admin `omar`, supervisor `nour` of SAKS, planner `lina` with no program, program SAKS with LOB "NMG Tier 2"):
  - `test_a_program_you_do_not_have_says_so_and_who_can_fix_it`: lina GETs `/day?program=SAKS+NMG+Tier+2` → 403; body contains `SAKS, NMG Tier 2 is not one of your programs` and `Ask an admin to add this one to your programs.`; not `This page is for admins.`
  - `test_a_page_for_admins_and_supervisors_says_so`: lina GETs `/admin/users` → 403, `Only admins and supervisors can open this page.`
  - `test_a_page_for_admins_says_so`: nour GETs `/setup/programs` → 403, `Only admins can open this page.`
  - `test_a_missing_page_says_so_and_offers_home`: GET `/nothing-here` → 404, `This page does not exist.`, `The link may be old, or the page moved.`, a link with text `Go to Home`; `Back to runs` absent.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_errors -v` → 4 FAIL on the old texts.
- [ ] **Step 3: Implement.** Program check: `abort(403, description=f"{label} is not one of your programs")` with `g.error_hint = "Your account opens only the programs given to you. Ask an admin to add this one to your programs."`, label from the `unit` filter function. `manager_required`: description `Only admins and supervisors can open this page.`; `admin_required`: `Only admins can open this page.` Handler: use `err.description` when it differs from the class default, else `{403: "Your account cannot do this.", 404: "This page does not exist.", 413: "That file is larger than 25 MB."}`; hints `{403: "Ask an admin if you need it.", 404: "The link may be old, or the page moved.", 413: "Pick a smaller workbook."}` unless `g.error_hint` is set. `error.html`: `<h1>{{ message }}</h1>`, `<p>{{ hint }}</p>` when set, `<p><a class="button primary" href="{{ url_for('home') }}">Go to Home</a></p>`.
- [ ] **Step 4: Run** the four tests → PASS; run `test_auth`, `test_contacts`, `test_programs` → no new failure.
- [ ] **Step 5: Commit** "Phase XY task 1: error pages say why and what to do".

### Task 2: Removing a department and its people takes a check

**Files:**
- Modify: `webapp/app.py:956-978` (`with_setup`), `webapp/templates/with_setup.html:18`
- Test: `webapp/tests/test_contacts.py` (new tests in `TheContactsPage`; re-pin `test_add_paste_and_remove_on_the_page`)

**Interfaces:**
- Produces: GET `/setup/with?program=K&remove=<id>` renders the check inside that department (`id="remove-<id>"`); its form POSTs `action=remove_department`, `id`, `confirm=yes`.

- [ ] **Step 1: Write the failing tests:**
  - `test_removing_a_department_asks_first`: after pasting `Quality, Lina / Quality, Omar`, POST `action=remove_department, id` without `confirm` → 303 to `?program=…&remove=<id>`; the department is still there. GET that URL → contains `Remove Quality and its 2 people?`, `This cannot be undone`, button `Remove Quality and 2 people`, link `Keep Quality`. POST with `confirm=yes` → removed; flash `Removed the department Quality and its people.`
  - `test_a_stale_check_shows_nothing`: GET `?remove=99999` → 200, no `cannot be undone`.
  - Re-pin `test_add_paste_and_remove_on_the_page`: its remove_department POST gains `confirm="yes"`, with the comment `# Phase XY (owner-approved sample 5): removing a department takes a check first; its button sends confirm=yes.`
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_contacts -v` → the two new tests FAIL (removed at once; no check text).
- [ ] **Step 3: Implement.** Head control becomes a link `Remove the department and its people` (class `link danger`) to `?remove=<id>#remove-<id>`. With `remove` matching a listed department, render under it a `.panel.check-save` (`id="remove-<id>"`): h2 `Remove {name} and its {n} {person|people}?`, p `They come off the department lists for {program}, so nobody can pick them as With any more. This cannot be undone: you would add them again by hand.`, a POST form with button `.danger` `Remove {name} and {n} {person|people}` and a link `Keep {name}` back to the page. Server: `remove_department` without `confirm == "yes"` redirects (303) to the check and changes nothing.
- [ ] **Step 4: Run** `test_contacts` → all PASS.
- [ ] **Step 5: Commit** "Phase XY task 2: removing a department takes a check".

### Task 3: Markup: skip link, names for the timeline, + Add and scroll boxes, colour-free copy

**Files:**
- Modify: `webapp/templates/base.html:15-17,60`, `webapp/templates/day.html:112,133,265,95,210,217,239,248`, `webapp/templates/week.html:64,84,95`
- Modify: `webapp/static/app.css` (new section "Phase XY: skip link")
- Test: `webapp/tests/test_markup_xy.py` (new)

**Interfaces:**
- Produces: `<main id="main" tabindex="-1">`; `.skip` link first in `<body>`; `.scroll` boxes carry `role="region"`, `tabindex="0"`, `aria-label`.

- [ ] **Step 1: Write the failing tests** (`TheMarkup`, app and data as `test_ui_playwright.ThePhaseWInTheBrowser.setUpClass`, rendered with the test client):
  - `test_the_first_link_skips_to_the_page`: any signed-in page: the first `<a` after `<body>` is `<a class="skip" href="#main">Skip to the page</a>`; `<main id="main" tabindex="-1">` present.
  - `test_timeline_lanes_are_groups`: day page: no `role="img"` on `svg.tl-track`; each has `role="group"` and its `aria-label`.
  - `test_each_add_link_names_its_interval`: board page: every `rb-add` link text is `+ Add<span class="sr-only"> to HH:MM</span>` (the row's start).
  - `test_scroll_boxes_are_named_regions`: week page and adherence tab: every `div.scroll` has `role="region"`, `tabindex="0"` and a non-empty `aria-label`.
  - `test_the_timeline_note_matches_the_new_colours`: day page has `Shifts are the blue bars; breaks are the marks on them.` and not `breaks in amber`. (The coach note "teal: less" stays true: its cells keep the covered teal, Task 6.)
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_markup_xy -v` → 5 FAIL.
- [ ] **Step 3: Implement** the markup; region labels are the section heading plus ` (scrolls sideways)`. CSS: `.skip` hidden above the page until focused (`top: -80px` → `top: 12px` on `:focus`), styled like `.crumbs a`; `main:focus { outline: none; }`.
- [ ] **Step 4: Run** the five tests → PASS.
- [ ] **Step 5: Commit** "Phase XY task 3: skip link, named timeline, + Add and scroll boxes".

### Task 4: Pickers that act on change wait for Enter when moved by the keyboard

**Files:**
- Modify: `webapp/static/app.js:91-102` (autosubmit), `:305-361` (attendance), `:652-665` (left menu picker)
- Modify: `webapp/static/app.css` (section "Phase XY: keyboard pickers")
- Test: `webapp/tests/test_ui_playwright.py` (new class `ThePhaseXYInTheBrowser`, set up as `ThePhaseWInTheBrowser` plus a RUNNING run, a planner without programs and `seed_history`)

**Interfaces:**
- Produces: `keyedPick(select, act)` in `app.js`: arrow, Home, End, PageUp, PageDown and letter keys on a closed list set a pending state (class `pending`, a `p.pick-note[role=status]` after the field); Enter calls `act()`; Escape and leaving the field put back the saved value and remove the note; a change with no such key before it calls `act()` at once.

- [ ] **Step 1: Write the failing browser tests:**
  - `test_one_arrow_does_not_save_attendance`: focus a `select.att` showing Present, press ArrowDown → no POST to `/day/attendance` in 1.5 s, the select has class `pending`, `p.pick-note` reads `Not saved yet. Press Enter to save Unplanned leave, or Esc to keep Present.`; press Enter → POST, after reload the select shows Unplanned leave.
  - `test_escape_and_tab_put_attendance_back`: ArrowDown then Escape → value Present, no note, no POST; ArrowDown then Tab → value Present, no note, no POST.
  - `test_a_mouse_pick_still_saves_at_once`: `select_option("Sick")` on another lane → POST at once.
  - `test_one_arrow_does_not_change_the_measure`: focus the Measure picker, ArrowDown → no navigation in 1.5 s, note `Press Enter to show …, or Esc to go back.`; Enter → navigates with `measure=sl`.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_ui_playwright.ThePhaseXYInTheBrowser -v` → the three keyboard tests FAIL (saved or navigated at once); the mouse test passes (guard).
- [ ] **Step 3: Implement `keyedPick`** and use it for `select.att`, `[data-autosubmit]` (including the date field) and `select[data-unit-pick]`. Attendance texts: `Not saved yet. Press Enter to save {new}, or Esc to keep {old}.`; pickers: `Press Enter to show {new}, or Esc to go back.` CSS: `.pending` dashed `--short` border; `.pick-note` like `.notice`, small.
- [ ] **Step 4: Run** the class → PASS; rerun `ThePhaseWInTheBrowser` (its attendance `select_option` must still save).
- [ ] **Step 5: Commit** "Phase XY task 4: keyboard moves in pickers wait for Enter".

### Task 5: Home stops reloading once the New run form is in use

**Files:**
- Modify: `webapp/static/app.js:533-541`, `webapp/templates/dashboard.html:39-58` (status URL on the now panel)
- Test: `webapp/tests/test_ui_playwright.py` (`ThePhaseXYInTheBrowser`)

**Interfaces:**
- Consumes: `/runs/<id>/status` JSON (`label`, `status`, `stages[].state`, `final`), as the run page uses it.
- Produces: `section.now` has `data-status-url` when a run is active.

- [ ] **Step 1: Write the failing tests** (`page.clock.install()` before loading Home):
  - `test_home_does_not_reload_over_a_form_in_use`: choose a file and Upload a ready schedule, fast-forward 65 s → no `load` event; the file and the choice are still there; `.now` shows `Updates paused while you fill in this form. They start again when you submit it.`
  - `test_home_still_refreshes_when_the_form_is_untouched`: fast-forward 31 s → one reload.
  - `test_a_finished_run_says_so_without_reloading`: form touched, the RUNNING run set to DONE in the store, fast-forward 31 s → no reload; `.now` contains `This schedule finished.` and a link `Open it`.
- [ ] **Step 2: Run** → the first and third FAIL (reloaded).
- [ ] **Step 3: Implement:** any `input` or `change` inside the New run form sets `touched`; the reload timer skips the reload when touched and instead fetches the status URL every 30 s, redraws the small ring's arcs and word, and on `final` shows the finished line; the paused note is inserted once at the top of the form.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** "Phase XY task 5: Home keeps a form in use".

### Task 6: The colour system and the layout fixes in app.css

**Files:**
- Modify: `webapp/static/app.css` (tokens `:2-74`, rules named in `proposal.css`, `:106-108`, `:349`, `:526-529`, `:540`, `:600-601`, `:712`, `:826-827`, `:874`, `:906-911`, every `font-size`/`font` in px)
- Modify: `webapp/DESIGN.md` (tokens table, the "colour means state" rule); `.coach-t td.down b` takes `--covered-text` so the coach note "teal: less" stays true
- Test: `webapp/tests/test_markup_xy.py` (`TheStylesheet`), `webapp/tests/test_ui_playwright.py` (`ThePhaseXYInTheBrowser`)

**Interfaces:**
- Consumes: `evidence/phase_y/proposal.css` (values and selectors), Task 3's `.skip`, Task 4's `.pending`/`.pick-note`.
- Produces: tokens `--action`, `--action-hover`, `--on-action`, `--edge`, `--selected`, `--covered-text`, `--over-text`, `--on-covered`, `--on-short`, `--on-gap`, `--on-over`; new `--done`, day-look status fills and `--ch-email` values.

- [ ] **Step 1: Write the failing tests:**
  - `TheStylesheet.test_every_font_size_is_in_rem`: no `font-size: <n>px` and no px size in a `font:` shorthand outside `@media print`.
  - `TheStylesheet.test_the_proposed_tokens_are_in_both_day_blocks`: each day-look value from `proposal.css` appears in both the `prefers-color-scheme: light` block and `:root[data-theme="light"]`.
  - Browser `test_rendered_pairs_pass_in_both_looks`: for night, day (device) and day (picked with the theme switch): measured from computed styles, text on `.tc.ok`, `.chip small`, `.wk.over`, `.wk.over small`, `.bp-strip .ok` ≥ 4.5; an input's border against its panel ≥ 3.0; a teal and an amber week-wall cell against the panel ≥ 3.0; a link's colour is not the covered teal (hue difference ≥ 15° or chroma < 0.03).
  - Browser `test_focus_never_hides_under_the_top_bar`: at 1280 and 390 wide, schedule editor, a cell put just under the bar and reached with Shift+Tab ends with its top at or below the bar's bottom.
  - Browser `test_a_focused_break_shows_its_ring`: focused `rect.brk` has a 2 px solid outline in the action colour.
  - Browser `test_names_fit_on_a_phone`: at 320 wide, every `.tl-who b` shows its whole name (`scrollWidth <= clientWidth`) and `select.att` computes `font-size` ≥ 16 px.
- [ ] **Step 2: Run** → all FAIL on today's stylesheet.
- [ ] **Step 3: Implement:** move `proposal.css` into `app.css` (tokens into the three token blocks; each rule merged into the rule with the same selector, new ones into a "Phase XY: colour means state" section); `html { scroll-padding-top }` from the measured top-bar heights per breakpoint, deleting the anchor rules at `:712` and `:874`; phone timeline as in Phase X sample 8 (name on its own line, `select.att` 16 px under 720 px, `.add-dlg select.att` 16 px); px font sizes to rem (n/16, same rendering at the default size); `DESIGN.md` v3 tokens.
- [ ] **Step 4: Run** the tests → PASS; render the nine Phase Y sample pages with the new `app.css` and no layer, and compare with `evidence/phase_y/samples` (differences only where Tasks 3-6 change something on purpose).
- [ ] **Step 5: Commit** "Phase XY task 6: colour means state; layout fixes".

### Task 7: Browser check, screens, suite, gate, package, report

**Files:**
- Modify: `webapp/tests/test_ui_playwright.py` (`ThePhaseXYInTheBrowser.test_phase_xy_screens` writing `evidence/phase_xy/screens/`)

- [ ] **Step 1:** Add `test_phase_xy_screens`: Home (night), RTA timeline (day and night), board (day), week (day), editor (night), exports (day), the 403 page, the department check, the skip link focused, phone timeline; no page errors.
- [ ] **Step 2:** axe-core run (scratch copy, not a dependency) on every page, both looks → no colour-contrast failure; record in `evidence/phase_xy/CHECKS.md`.
- [ ] **Step 3:** Full website suite `$PY -m unittest discover -s webapp/tests -t .` → OK (count and skips recorded); `git checkout -- evidence/` for regenerated screens of earlier phases.
- [ ] **Step 4:** `python3 tools/build_production_package.py` (runs the gate) → PASS; split into halves under 30 MiB.
- [ ] **Step 5:** Commit and push; report with screens and the package.
