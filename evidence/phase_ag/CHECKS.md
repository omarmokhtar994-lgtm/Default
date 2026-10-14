# Phase AG: checks (2026-10-14 and 15, Egypt time)

© 2026 Omar Mokhtar. All rights reserved.

Built from the approved samples (`evidence/phase_ag/DESIGN_PLAN.md`, `samples/`), the owner's answers of 2026-10-14
and the plan `docs/superpowers/plans/2026-10-14-phase-ag-build.md`. Nothing that existed was removed. The engine is
not touched.

## What was built

| Item | Commit | Where |
| --- | --- | --- |
| T1 v4 foundation: self-hosted Archivo and Atkinson Hyperlegible Next, Phosphor icons in icons.css, menu by job, CSP `'self'` only | 4e0cc08 | base.html, app.css, icons.css, app.py |
| T2 the RTA's Now panel: the next hour and what needs attention | 354c171 | day.py, day.html |
| T3 Go to (Ctrl K): pages, programs, the day's people | 7e6a65d | app.py, base.html, app.js |
| T4 associate accounts linked to their name on the schedule, kept to My week | 7975521 | store, auth, access, app.py, admin_users.html |
| Owner's answers on leave, swaps and colours, in the plan | 950f989 | plan |
| T5 leave: Planned leave and Public holiday, coverage per day, TM then RTA approval, balances | 2b79d6a | leave.py, store, schedules, requests.html |
| T6 swaps: rest gap, language unless no impact, channels each can work; colleague then TM | 197d42e | swaps.py, versions.py, attendance |
| T7 My week on a phone: today's band, now and next, the week, sheets | 6965d21 | day.py, me.html |
| T8 the day in another zone gains language and channel rows; Overview has the rest of the week | 307a386 | day.py, day_zoned.html, _outlook.html |
| T9 the v4 pass over every page and motion; colour samples for the owner (not applied) | b98e07f | app.css, colours/ |
| T10 16 px phone fields; screens | 76db22b | app.css, screens/ |
| T10 the Now panel fits a 320 px phone (found by the full suite) | 66cbea1 | app.css |

## Rulings made while building (each says what it costs if wrong)

- Icons and licences: the Phosphor shapes live in our icons.css as data URIs, the licence files have no suffix
  (the gate wants the copyright line in every .svg and .txt under webapp). Cost: a file move.
- Font shorthands with the display face carry `semi-condensed` (a shorthand resets a numeric width). Cost: a width tweak.
- The Now panel sits above the tabs, not beside the timeline, which needs the full width. Cost: a layout move.
- An associate's name must be on the newest kept week of their programs, one account per name per program;
  associates never get all programs. Cost: an associate added before their first schedule waits for it.
- "5 yes" to an either/or question is read as the plan's choice: an approval saves a new version and sets it in
  use, the earlier one kept. Cost: approvals would edit the version in use instead.
- TM is a supervisor or an admin; the RTA is any other staff member with the program; one person cannot give both
  approvals. Cost: a one-person team needs a second account.
- Leave may be asked for days with no schedule yet; approval says them ("mark it when that week is planned").
  Cost: the planner re-enters them when the week is planned.
- The balance warns the approvers and never refuses (the owner: approvals cover the balance). Cost: a refusal rule.
- A swap is one day, shift for shift; each takes the other's breaks and channel stretches. Cost: a give-away to add.
- The channel rule reads the schedule's channel plan: each must work every channel the other's shift has stretches
  on. Cost: a coverage-based check instead.
- Only colleagues with an associate account are offered a swap (they must accept). Cost: staff accept for them.
- Zone-aware forms stay deferred: changes are made on the schedule's own day; the other zone is read only.
- Colours stay as measured in Phase Y until the owner picks a sample (answer 7: "show me first").

## Results

- Feature tests: test_ag_look 6, test_ag_rta 6, test_ag_goto 5, test_ag_associates 9, test_ag_leave 14,
  test_ag_swaps 13, test_ag_myweek 7, test_ag_overview 2, test_af_zones (4 new): all pass.
- Browser (Playwright, review server with associates, a leave waiting for the TM, one for the RTA and a swap):
  - 360 px: My week, its swap finder, Requests and People have no sideways scroll, every field 16 px or more, no
    console errors.
  - Screens in `screens/ag_*` (night and day looks): RTA, Requests, People, Overview, the day in New York, My week
    and its swap finder on a phone.
- Full website suite, Wed 14 Oct 23:27 to Thu 15 Oct 00:05: 1047 tests, 20 failures, 3 errors, 1 skipped.
  - 3 were this phase's: today's Now panel made the RTA 333 px wide on a 320 px phone (two phone tests and the AB
    notifications test, which checks the same width). Fixed in 66cbea1; measured 333 then 320; the 3 re-run green.
  - The other 20 are calendar and time-of-day collisions, not this phase. Their fixture day is Wednesday
    14 October 2026, the day of the run, which started after its 15:00 to 16:00 warnings:
    - the 18 known from Phase AF;
    - test_runs.test_vto_offers_pick_from_and_to and test_ui_playwright.test_phase_r_screens. VTO is offered only
      for intervals still ahead, and both pass at 00:06, once the 14th is past.
    - test_phase_v_screens fails the same way on f35fbad, before Phase AG.
- The browser tests rewrite the old phases' screenshots; the rewritten files were restored before packaging.
- Release gate (run_tests.sh, tests_staged/GATE_MINIMUMS.json), Thu 15 Oct 00:10 to 00:26: GATE PASS, 77 suites,
  1537 tests (2 skipped), 2 selfchecks, call signatures, undefined-name sweep; again inside the staged package
  (00:27 to 00:44).
- Package: dist/RC9_2_2_PRODUCTION_PACKAGE.zip, 2640 files, 69.43 MB,
  sha256 c6d504bb4c5e6179dde794b22a33a902b55ba366151ff50be6f6ec42a364edc9. Sent in three parts (AG_part_0 to
  AG_part_2); joined in order they give the same sha256.

## Colours: the owner's pick (2026-10-15)

"I recommend A as well but keep deep ocean as well as a third option so to have 3 views" (accee28):
- Graphite night is the default, its light version is the day look, and Deep ocean is a third look ("Ocean look" in
  the top bar, kept in the same cookie). Status and channel colours unchanged in every look.
- Re-pinned, each saying why: test_review_polish.test_theme_color_meta, test_markup_xy approved tokens,
  test_ui_playwright.test_light_theme_run_page (the day page background).
- Browser: the switch goes Graphite, Ocean, Day, Ocean, Dark with the page background right each time, no console
  errors (`screens/looks_*.png`); the rendered contrast test passes in both looks.
- Package rebuilt, 01:08 to 01:24: GATE PASS (77 suites, 1537 tests); 2647 files, 71.56 MB,
  sha256 b9917744b6fdc90aa8f853e55b6b81c0914bb724829430527e39230ac9e21fc6, sent as AG2_part_0 to AG2_part_2
  (joined in order they give the same sha256). It replaces the earlier AG package.

## Deferred minors

- A request left "applying" by a server crash during an approval stays so; it needs a manual reset.
- A leave over two weeks with both schedules kept is handled (one version per week) but has no test of its own.
- My week's swap finder says nobody can take the shift when the person has leave asked that day; it could say why.
- Pre-existing pyflakes notes outside this phase: versions.py "io" in a string annotation; app.py unused
  fixed_input.
