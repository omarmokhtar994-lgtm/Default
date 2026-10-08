# Phase L: friendly failures, readiness Start, navigation, upload, workbooks, themes

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A failed run or readiness check says on its page why it stopped and what to change in the input workbook; a passed readiness check starts the real run (Quick, Deep or Overnight) from the same workbook; every page has Back and Home; the workbook can be dropped onto the upload area; clean input workbooks (blank and example) download from the home page; the site has a light and a dark theme.

**Architecture:** `webapp/outcome.py` reads the engine's own `BUSINESS_OUTCOME.json` (headline, summary, findings, affected examples, shortfalls, recommended actions) and shapes it for the page; a compact copy (code, category, headline) is kept on the run row (`engine_outcome` column) so labels survive file expiry. Readiness checks are judged by that outcome, not the runner's exit code (the runner also scores release gates, which a run that builds no schedule always fails). Themes are CSS tokens on `:root` switched by `data-theme`, set server-side from a cookie (no flash, works without script); chart marks use classes instead of colour attributes so they follow the theme.

**Tech Stack:** as Phase K.

**Spec:** Owner, 2026-10-08 (verbatim): "inside the run page i do[n't] see the easy friendly reason for failure ive to download the zip and look into outcome and can['t] find how to resolve that easily or what to do in input sheet to let this run", "for smoke test resume button should be start and To choose quick/deep/overnight to start running", "smoke showing not approved regularly reason was that was not an actual run", "we should have a back bottom and home page button in each page", "when uploading the input file i should have the option to drop it", "we need source for clean input sheet to be download from the homeoage", then "C" (both a blank and an example workbook) "and make the website as well dark/white for different preference". Samples approved: `evidence/phase_l/samples/`.

## Global Constraints

- The fix list shows the engine's own words (headline, summary, findings, recommended actions); the website only groups, orders and formats them. A finding code with no plain wording is shown humanised with its values, never dropped. Sentences that point at developer tools (`tools/...`) are left out of the page (still in the zip).
- No engine change. Protected workbooks and `engine/regression_assets` untouched; the example workbook is built from the synthetic `fixtures/synthetic_suite/SYNTH_M2_MULTI_START_WITH_BREAKS.xlsx` (made-up names) with the existing friendly builder, whose engine-reading proof must pass.
- A readiness check is "Ready to run" only when the engine's outcome is `DIAGNOSTICS_ONLY_COMPLETE`; anything else, including a missing outcome, is "Not ready" with the reason (fail closed).
- Light and dark both meet the dataviz checks on their own surface (validator run per mode); status colours keep their meaning in both.
- CSP unchanged (scripts and styles from the site only); everything works without script except drag-and-drop and the history-aware Back.
- Copyright header in every new file; Egypt time.

## Review Focus

- A failed run whose files have expired: the label and headline still show from the row (`test_outcome_survives_file_expiry`).
- A failed run with no outcome file at all (engine crashed before writing it): the page says so and keeps Resume (`test_crash_without_outcome_keeps_resume`).
- A readiness check whose runner exited 2 but whose outcome is `DIAGNOSTICS_ONLY_COMPLETE`: Ready to run, not Not approved (`test_readiness_judged_by_engine_outcome`).
- Start from a readiness check whose input file is gone (expired): a clear message, no new run (`test_start_needs_the_input`).
- A dropped file that is not .xlsx: the drop area says so and keeps the previous choice (`test_drop_rejects_other_files`, browser).

---

### Task 1: the engine's outcome on the run page

**Files:** Create `webapp/outcome.py`; modify `webapp/store.py` (column `engine_outcome`), `webapp/runs.py` (`_execute` stores it, message from its headline), `webapp/app.py` (`label`), `webapp/templates/run.html`; Test `webapp/tests/test_outcome.py`, `webapp/tests/test_runs.py`; fixtures `webapp/tests/fixtures/outcomes/*.json` (copies of real engine outcomes, names replaced).
**Produces:** `read(results_dir) -> Optional[dict]`; `compact(outcome) -> dict` (`code`, `category`, `headline`); `view(outcome) -> dict` (`headline`, `summary`, `blockers: [str]`, `people: [{associate, days, shift, window}]`, `people_total`, `shortfalls: [str]`, `actions: [str]`, `cannot_schedule: bool`); `CANNOT_SCHEDULE` codes.
- [x] Tests: `test_conflict_outcome_names_rules_people_and_actions` (language/fixed conflict: two blockers, people grouped "Sun to Thu", the engine's action kept, the `tools/` sentence left out), `test_shortfall_rows_read_plainly` ("Sun 03:00: Nobody on the floor after breaks, required 1, short by 1"), `test_coded_finding_is_humanised_with_values`, `test_failed_run_page_shows_why_and_what_to_change`, `test_outcome_survives_file_expiry`, `test_crash_without_outcome_keeps_resume`.

### Task 2: readiness check judged by its outcome; Start from it

**Files:** `webapp/runs.py` (`outcome()` for SMOKE uses the engine outcome; `start_from(run_id, user_id, mode) -> Optional[str]`), `webapp/app.py` (`POST /runs/<id>/start`; Resume hidden for readiness checks and for "can't be scheduled"), `run.html`, `dashboard.html` (prefill program and week from the query string); Test `test_runs.py`.
- [x] Tests: `test_readiness_judged_by_engine_outcome` (runner exit 2 + `DIAGNOSTICS_ONLY_COMPLETE` -> DONE, label "Ready to run"), `test_readiness_not_ready_shows_reason` (label "Not ready"), `test_start_from_readiness_queues_the_same_workbook` (new run, mode QUICK, same program, week and options, input bytes equal), `test_start_needs_the_input`, `test_readiness_page_offers_start_not_resume`, `test_corrected_upload_link_prefills_program_and_week`.

### Task 3: Back and Home everywhere; drag-and-drop upload

**Files:** `base.html` (crumbs row on every page but home; nav "Runs" -> "Home"), `app.py` (`BACK` parent per endpoint), `app.js` (history-aware Back; drop area), `dashboard.html`, `app.css`; Test `test_runs.py`, `test_ui_playwright.py`.
- [x] Tests: `test_every_page_has_back_and_home` (run, program, programs, team, people, password), `test_drop_a_workbook_onto_the_upload_area` (browser: DataTransfer drop fills the file input and shows the name), `test_drop_rejects_other_files` (browser).

### Task 4: clean input workbooks

**Files:** Create `tools/build_web_workbooks.py`, `webapp/workbooks/Scheduler_Input_Blank.xlsx`, `webapp/workbooks/Scheduler_Input_Example.xlsx`; `app.py` (`GET /workbooks/<name>`, login required, two names only); `dashboard.html`; Test `tests_staged/test_rc9_2_45_web_workbooks.py` (engine available there), `test_runs.py` (route).
- [x] Tests: `test_example_reads_like_its_synthetic_source` (engine parse of the example equals the source's), `test_example_passes_the_input_check`, `test_blank_has_every_tab_and_no_people_or_demand`, `test_only_the_two_workbooks_download`.

### Task 5: light and dark themes

**Files:** `app.css` (tokens for both; every literal colour becomes a token), `charts.py` (series and heat levels as classes), `program_page.py`, `base.html` (`data-theme` from cookie; toggle), `app.py` (`POST /theme`), `app.js`; Test `test_charts.py`, `test_runs.py`, `test_ui_playwright.py` (screens of both themes to `evidence/phase_l/screens`).
- [x] Tests: `test_marks_use_series_classes_not_colours`, `test_theme_cookie_sets_the_page_theme`, `test_theme_toggle_needs_csrf`, browser `test_light_theme_pages`.
- [x] Palette: run the dataviz validator for the light series steps on the light surface; record the output in `evidence/phase_l/PALETTE_LIGHT.txt`.

### Finish

- [ ] Website suite, full gate (`run_tests.sh`, floor raised by the new staged tests), package, push, send screenshots, package and update steps.
