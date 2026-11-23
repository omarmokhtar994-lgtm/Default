# Phase BA: three looks, list handling, icons, wallboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: executing-plans (inline; the owner asked for no check-ins). Steps use checkbox syntax.

**Goal:** Ship the owner's three approved looks (Tide, Night watch, Drafting table), make every long table a scroll panel or a paged list by one rule, add the missing icons, and make the Wallboard show everything a floor needs, without touching the engine.

**Architecture:** The site already has token-based looks in `webapp/static/app.css` (`:root` dark, `[data-theme=light]`, `[data-theme=ocean]`) and a server-side pager (`ctx._paged`). The looks are new token sets plus a `.sheet` wrapper in `base.html`; scroll panels are a CSS class on the existing `.scroll` regions; paging reuses `_paged`. The Wallboard and the RTA lane list get template changes with tests first.

**Tech stack:** Flask, Jinja, vanilla JS, one stylesheet, unittest, Playwright (Chromium at `/opt/pw-browsers/chromium`).

**Spec:** `evidence/phase_az/SUGGESTIONS.md` (sections 2 to 2d, 3), `evidence/phase_az/prototype/` (approved looks A Tide, B Night watch, C Drafting table), `evidence/phase_ba/REQUESTS.md`.

## Global constraints

- Strict CSP: no inline script, style or event handlers. Sentence-case copy. `© 2026 Omar Mokhtar. All rights reserved.` in the first 4 lines of every website file. Made-up "Associate NN" data only.
- Engine, baseline workbooks and `engine/regression_assets` untouched. Cookie value names `light`, `dark`, `ocean` kept (Tide, Night watch, Drafting table); labels change, so `test_ag_look.py` and `test_ui_playwright.py` are re-pinned with the reason in the test.
- Status colours mean state only; channel colours Phone `#1A47A8`, Email `#2F7D5B`; Chat darkens to `#B4468F` (white text 5.0:1; was `#C2549F`, 4.1:1). Large teal text uses `--covered-text`.
- Every pair measured; text 4.5:1, large text and controls 3:1.
- Route map pinned (`route_map.json`): no route added or renamed.

## Review focus

- A table that is empty, has one row, or has hundreds of rows still renders (no JS needed to read all rows).
- A paged list keeps the filters and the other lists' page numbers in its links.
- Scroll panels are keyboard reachable, labelled, and print in full.
- Looks switch without a flash and the device setting still decides when no cookie is set.
- Phone at 360 px: no sideways page scroll.

### Task 1: Icons
**Files:** `tools/build_icons_css.py`, `webapp/static/icons.css`, `webapp/tests/` (icon test)
- [ ] Test `test_every_menu_link_has_an_icon`: render the menu for an admin and assert each `.leftnav nav a` href prefix has a `MENU` rule (parse `icons.css`); fails today for `/shrinkage` and `/incidents`.
- [ ] Add icons `chart-pie-slice` (Shrinkage), `warning-circle` (Incidents), `sliders-horizontal`? no: only `gear` (Settings, exists), `sign-out` (exists), `palette` (Look); write `MENU` rules; rebuild `icons.css` from Phosphor `core` SVGs (fetched from the repository's raw files; shapes MIT).
- [ ] Run test, commit.

### Task 2: Looks
**Files:** `webapp/static/app.css`, `webapp/templates/base.html`, `webapp/DESIGN.md`, tests `test_ag_look.py`, `test_ui_playwright.py`
- [ ] Re-pin look-switch tests: labels "Tide", "Night watch", "Drafting table" in one "Look" control; cookie values unchanged.
- [ ] Tokens: `:root` and `[data-theme=dark]` Night watch; `prefers-color-scheme: light` and `[data-theme=light]` Tide; `[data-theme=ocean]` Drafting table; `.sheet` wrapper around header and frame; `meta theme-color` per look.
- [ ] Contrast script over every token pair (`evidence/phase_ba/contrast.py`), commit.

### Task 3: One rule for long lists
**Rule:** tables and grids people scan or compare (Weeks overtime and extra hours, heat maps, adherence, coach, matrices) are scroll panels (`.scroll.panel`, max height `min(28rem, 62dvh)`, sticky header). Lists that grow over time and are read one by one (runs, requests decided, change logs, posts, people) are pages of 20 with `_paged`.
**Files:** `webapp/static/app.css`, templates `week.html`, `day.html`, `coach.html`, `roles.html`, `channel_setup.html`, `run_schedules` template (`schedules_week`/`run`), `admin_users.html`, routes `admin.py`, `schedule_versions.py`.
- [ ] Test per page: the long table sits in a labelled scroll panel (`role="region"`, `tabindex="0"`, class `panel-scroll`); the long lists render at most 20 rows with a pager when more exist.
- [ ] Implement, run the page tests, commit.

### Task 4: RTA lane list, scrolling panel or whole list
**Files:** `webapp/templates/day.html`, `webapp/static/app.js`, `webapp/static/app.css`, `test_ui_playwright.py`
- [ ] Browser test: default is the scrolling panel; "Whole list" removes the inner scroll; the choice is kept in `localStorage` (page works without it).
- [ ] Implement, commit.

### Task 5: Wallboard completeness
**Files:** `webapp/templates/wallboard.html`, `webapp/routes/day.py`, tests.
- [ ] List what a floor needs (see REQUESTS.md) and test each is shown: next 4 hours need and buffer (exists), on break now (exists), next 30 minutes (exists), languages now (exists), channel cover now, late or absent and called in, overtime or VTO offers, target achievement today, shift changes in the next hour, and the time the data was drawn.
- [ ] Implement, commit.

### Task 6: Spacing and organisation, page by page
- [ ] Screens of all 31 pages in the three looks at 1440 and 390 px; fix what the owner's rule exposes (Incidents Show button, header grouping, stat tiles, crumbs, intro text), re-shoot.

### Task 7: Floating note
- [ ] `liveWatch` in `app.js`: the "page out of date" message becomes the fixed bottom note with Refresh and Hide; test.

### Task 8: Checks and package
- [ ] Suites in two halves, browser tests, page review (360 and 1440, three looks), route sweep, gate, `CHECKS.md`, `HANDOFF.md`, patch with `tools/make_patch.py`.
