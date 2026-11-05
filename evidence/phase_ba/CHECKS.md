# Phase BA checks (2026-10-25, Egypt time)

Three looks (Tide, Night watch, Drafting table), one rule for long content (scroll panels, pages of 20, RTA scrolling
panel or whole list), wallboard completeness, floating "page out of date" note, missing icons, and a little CSS-only 3D.

| Check | Result |
|---|---|
| Website suite, half 0 | 1136 tests; 1 failure, `test_ay_channel_scenarios` spread bound, load-dependent (three suites ran at once against the solver time limit); passes alone (4 tests OK) |
| Website suite, half 1 | 1070 tests OK (1 skipped) |
| Browser suite | 103 tests; 1 failure (sign-in test looked for the old `.week` bars), re-pinned to `.deck3d` with a reason, passes |
| Release gate (`run_tests.sh`) | PASS, 80 suites, 1579 tests (2 skipped); `min_tests` raised from 1551 to 1579 |
| Contrast | 0 failures across the three looks (`contrast.py`) |
| List audit | 0 findings, 3 looks x 31 pages x 1440 and 390 px (`audit.py`) |
| 3D budget | about 23 layers, 1.3 KB gzip CSS, off for reduced motion, never on RTA, tables, forms or wallboard; no server cost |

Re-pinned with reasons in each test: `test_av_shrink_page`, `test_runs` (look control), `test_ui_playwright` (sign-in deck,
look buttons, live note), `test_ag_look`, `test_review_polish`, `test_markup_xy`, `test_ak_colours`, `test_ay_live`.

Also in this package: patch AY7 (channel planner, includes AY5 and AY6) and the Egypt clock fix (Africa/Cairo, tzdata in install.sh).
