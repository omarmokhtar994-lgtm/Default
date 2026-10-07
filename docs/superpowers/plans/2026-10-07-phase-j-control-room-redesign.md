# Phase J: control-room redesign, real coverage wall, installer fixes

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the team website as a dark "control room" whose centrepiece is a week-coverage wall built from each run's own validation data, with plain-language findings, and fix the two installer problems seen on the first install.

**Architecture:** A new `webapp/results.py` reads a finished run's `INDEPENDENT_VALIDATION.json` into a small summary (grid, numbers, findings) saved as `summary.json` next to the run; templates, CSS and one small JS file render it. No engine, validator or runner change.

**Tech Stack:** as Phase I (Flask, Jinja2, plain CSS/JS, Playwright tests).

**Spec:** `webapp/DESIGN.md` (v2) and `docs/NEXT_PACKAGE_BACKLOG.md` items 1-2. Owner, 2026-10-07: "Control room (dark)", keep "Team Scheduler"; "Go ahead" to the 9 research additions and the Advanced options fold; plus "show how many hours pending until we start running that file, how many schedules are queued now, when is your turn, current status of the run, suggestions for the HC to achieve what you have requested if we are overstaffed or understaffed".

## Global Constraints

- Nothing on the wall or in the numbers is invented: every value comes from `INDEPENDENT_VALIDATION.json`; a run without it shows a sentence saying why.
- Colour classes use only what the validator wrote: `after_pct` (>= 1.0 fully covered; >= 0.9 "90-99%"; below 0.9 "under 90%") and its `severe_overage` flag (over-staffed). No target or floor ratio is guessed (they are not in the JSON).
- Copyright line stays in every page footer and every new file header; `test_rc9_2_56` enforces it.
- The website still never judges a schedule: status words come from the runner exit code and the run-level release verdict (Phase I).
- Times in Egypt time (UTC+3).

## Review Focus

- A run whose results have no `INDEPENDENT_VALIDATION.json` (rejected, readiness check, stopped, shortfall schedule): the page explains, no empty grid (`test_no_validation_file_gives_no_wall`).
- A workbook with 15- or 60-minute intervals: the wall's columns follow the intervals in the file (`test_wall_columns_follow_the_interval_length`).
- A validation file with unknown warning types: shown as a readable sentence, never dropped (`test_unknown_warning_type_is_still_listed`).
- A phone at 390 px: no horizontal page scroll; the wall scrolls inside its panel (`test_mobile_width_has_no_horizontal_scroll`).
- The admin username prompt given "Omar Mokhtar": refused with the rule, asked again (`test_usernames_with_spaces_are_refused`).
- A database created by Phase I (no options column) after the update: the column is added, old runs show "followed the workbook" (`test_old_database_gains_the_options_column`).

---

### Task 1: run summary from the validator's file

**Files:** Create `webapp/results.py`, `webapp/tests/fixtures/INDEPENDENT_VALIDATION.json` (the real file from the Phase I end-to-end run, trimmed to the keys read); modify `webapp/runs.py` (write `summary.json` after scoring); Test `webapp/tests/test_results.py`.

**Interfaces (produced):** `summarize(results_dir: Path) -> Optional[dict]` with keys `case`, `interval_minutes`, `days` (list of 7 day names, Sunday first), `slots` (column labels), `cells` (7 lists of `None` or `{"cls": "covered"|"short"|"gap"|"over", "pct": int, "people": int, "title": str}`), `numbers` (`active`, `fully_covered`, `at_90`, `floor_gaps`, `zero_staffed`), `findings` (list of plain sentences), `hard_fail_count`. `RunQueue.summary(run_id) -> Optional[dict]` reads `summary.json`.

- [ ] Failing tests: `test_summary_reads_the_real_validation_file` (126 active, 107 fully covered, 121 at 90%+, 0 floor gaps; Fri 21:30 break finding present), `test_cell_classes_follow_the_validator` (a severe_overage row is "over"; 0.95 is "short"; 0.85 is "gap"), `test_wall_columns_follow_the_interval_length` (15-minute rows give 96 columns), `test_no_validation_file_gives_no_wall`, `test_unknown_warning_type_is_still_listed`, `test_summary_saved_when_a_run_finishes` (fake runner writes the fixture).
- [ ] Run; save `evidence/phase_j/J1_TESTS_BEFORE.txt`. Implement. Pass. Commit.

### Task 2: the control-room look

**Files:** `webapp/templates/*.html`, `webapp/templates/_macros.html` (ring, wall), `webapp/static/app.css`, `webapp/static/app.js`, `webapp/app.py` (500 handler, dashboard "now" and "latest" data); Test `webapp/tests/test_ui_playwright.py`, `webapp/tests/test_runs.py`.

- [ ] Failing tests: `test_run_page_shows_the_week_wall_and_numbers`, `test_dashboard_shows_now_and_latest_wall`, `test_technical_details_are_folded`, `test_server_error_page_is_friendly` (500 page text: "Something went wrong on our side. Your runs are safe. Tell your admin."). Re-pin, with the reason in the test, the v1 selectors that the owner-approved redesign removes (`.stagebar` on the run page becomes `.ring`).
- [ ] Implement per DESIGN.md v2; screenshots to `evidence/phase_j/screens/`; review them; commit.

### Task 3: installer fixes

**Files:** `webapp/manage.py`, `deploy/install.sh`; Test `webapp/tests/test_auth.py`, `webapp/tests/test_deploy.py`.

- [ ] Failing tests: `test_usernames_with_spaces_are_refused` (manage refuses "omar mokhtar" with the People-page rule), `test_install_asks_again_after_a_mismatch` (install.sh wraps create-admin in a retry loop of at most 3 tries, no `set -e` exit on the first mismatch; the username prompt re-asks on a refused name).
- [ ] Implement; pass; commit.

### Task 4: queue position and start estimates

**Files:** `webapp/eta.py`, `webapp/app.py`, templates; Test `webapp/tests/test_eta.py`.

**Interfaces:** `expected_minutes(mode: str, cpus: int, history: list[float]) -> int` (median of the last 5 finished runs of that mode when there are at least 2; otherwise the runner's own plan: seeds per mode {SMOKE 1, QUICK 2, DEEP 4, OVERNIGHT 6} run side by side in rounds of max(1, min(seeds, cpus // 2)), 60 min per round (SMOKE: 15 min), + 10 min export/validation); `queue_plan(runs: list[dict], now: float, cpus: int, gate_pending: bool) -> dict[run_id, {"position": int, "ahead": int, "starts_in_min": int, "starts_at": float, "basis": str}]` (current run's remaining = max(5, expected - elapsed); + 30 min once if the safety gate has no PASS stamp).
- [ ] Failing tests: `test_quick_on_four_cores_is_one_round`, `test_history_overrides_the_plan`, `test_second_in_line_waits_for_the_running_one`, `test_gate_time_is_added_once_when_not_yet_passed`. Implement; show "2 runs ahead of you, starts in about 1 h 20 min (around 23:40 Egypt time), estimate based on ..." on the run page and the dashboard's Now strip.

### Task 5: headcount suggestions from the engine's capacity figures

**Files:** `webapp/results.py`; Test `webapp/tests/test_results.py`.

**Interfaces:** `summarize()` gains `staffing`: `{"roster": int, "productive_hours": float, "target_hours": float, "slack_hours": float, "headroom_pct": int, "class": str, "add_for_target": int, "add_for_floor": int, "add_for_breaks": int, "per_person_hours": float, "release_estimate": int, "headline": str, "short_windows": [...], "over_windows": [...]}` read from `*solver_audit.json` (`capacity_diagnostics`) and `UNIVERSAL_RUN_STATUS.json` (`additional_headcount_for_breaks`); windows grouped from consecutive interval rows (after_pct below the configured target ratio; severe_overage).
- [ ] Failing tests: `test_staffing_from_the_real_run` (7 people, 280 h, 207 h needed, 0 to add, release_estimate 1 = floor(72.6 / 40)), `test_understaffed_case_names_people_to_add` (synthetic audit with estimated_additional_hc_for_target 2), `test_windows_group_consecutive_half_hours`. Every suggestion is labelled an estimate with its basis.

### Task 6: Advanced options fold (the Colab settings)

**Files:** `webapp/store.py` (runs.options JSON text, added by migration), `webapp/runs.py`, `webapp/app.py`, dashboard template; Test `webapp/tests/test_runs.py`.
- [ ] Failing tests: `test_advanced_options_reach_the_runner` (ALL_ROWS gives `--language-working-window ALL_ROWS`; VOLUME_WEIGHTED gives `--coverage-objective-weighting VOLUME_WEIGHTED`; BEFORE_BREAKS_ONLY gives `--stage BEFORE_BREAKS_ONLY`; OVERNIGHT mode accepted), `test_follow_the_workbook_adds_no_flags`, `test_unknown_option_values_are_refused`, `test_old_database_gains_the_options_column`.

### Finish

- [ ] Shortfall-test budget per `evidence/phase_i/I7_SHORTFALL_BUDGET_RULE.txt` once both platforms are measured (x86 here, ARM on the owner's server); full gate; GATE_MINIMUMS for added tests; package rebuild; push; send screenshots and package with update steps.
