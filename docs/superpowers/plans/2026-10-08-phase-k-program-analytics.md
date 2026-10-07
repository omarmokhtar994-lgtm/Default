# Phase K: program analytics Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every run is tagged with its program and schedule week, and an analytics area shows each program's history week by week (associates, coverage before and after breaks, hours, efficiency, what stops 100%, what-if targets, recurring problem hours), per-user activity, and plain-language insights and suggestions computed from the scheduler's own files.

**Architecture:** `webapp/results.py` gains the analyses that need the run's files (restriction causes, target what-if, schedule efficiency, per-day coverage); a compact `metrics` JSON is stored on the run row when it finishes, so history survives the 30-day file deletion. `webapp/analytics.py` turns rows into weekly series, deltas, recurring windows, insights and suggestions; `webapp/charts.py` renders server-side SVG (no chart library, CSP unchanged) with hover tips and a table view for every chart.

**Tech Stack:** as Phase J; charts are inline SVG built in Python; one small JS tooltip.

**Spec:** Owner, 2026-10-08: "write the program name while adding the schedule", "measure HC changes based on each run", "analysis for each program based on selection and for each user", "insights written automatically", "total number of associates per each week schedule for that program with increase decrease trends", "if I watched that page I would know what happened to the program historically", "trends for coverage before break and after break", "show what is restricting us from 100% achievement, say suggestions for better results for example go from 100% intervals to 90%", "be open, be smart". AI-written summaries: later (owner chose "Yea" to rule-based first).

## Global Constraints

- Every number comes from the run's own files (validator, solver audit capacity diagnostics, run status). Estimates are labelled as estimates with their basis. No employee names leave the run directory; metrics hold counts and times only.
- A program week's figures come from one run: the latest finished run (Approved or Needs review) for that program and week; the page says which run and how many runs that week had.
- Chart palette validated on the dark surface `#15243A` (dataviz validator, all checks pass): blue `#3987e5`, aqua `#199e70`, orange `#d95926`, yellow `#c98500`; status colours keep their Phase J meaning. One y-axis per chart; legend for 2+ series; table view for every chart.
- Times in Egypt time; weeks start on Sunday.
- Copyright header in every new file.

## Review Focus

- A run finished before Phase K (no program, no week, no metrics): it appears under "Untagged" with its week taken from the run date, and the owner can tag it (`test_untagged_runs_can_be_tagged`).
- Two runs for the same program and week (Quick then Deep): the later finished one counts, and the page says 2 runs (`test_latest_run_counts_for_the_week`).
- A program with one week only: no deltas, no "vs last week" sentences, charts still render (`test_one_week_has_no_deltas`).
- Files expired after 30 days: the history still shows the week (`test_history_survives_file_expiry`).
- A program name with odd characters (`AE/AR <B2B>`): escaped everywhere, URL-safe (`test_program_names_are_escaped_and_url_safe`).

---

### Task 1: analyses from the run's files

**Files:** `webapp/results.py`; Test `webapp/tests/test_results.py`.
**Produces:** `summarize()` adds `targets` (list of `{"pct": int, "after": int, "before": int}` for 100/95/90/85/80), `efficiency` (`{"pct": int, "under_hours": float, "over_hours": float}`; efficiency = 1 - (under + over FTE-hours) / required FTE-hours over active half-hours), `day_coverage` (7 x `{"day", "after_pct", "before_pct"}` share fully covered), `restrictions` (`{"total": int, "causes": [{"key", "label", "count", "examples": [str]}]}` over half-hours below 100% after breaks; keys `capacity` (engine's upper bound of people who could be there, ceil(required / (1 - shrinkage)) needed, below it), `breaks` (fully covered before breaks), `weekly_hours` (aggregate productive hours below target hours), `rules` (the rest: rest, days off, start times, language windows)), and `metrics(summary) -> dict` (compact, names-free).
- [ ] Tests: `test_target_counts_match_the_validator` (100% -> 107, 90% -> 121, equal to the validator's own counts), `test_restriction_causes_add_up` (sum = 126 - 107), `test_capacity_cause_from_the_engine_bound` (planted bound below need), `test_breaks_cause` (before >= 100%, after < 100%), `test_efficiency_counts_over_and_under`, `test_metrics_hold_no_names`.

### Task 2: program and week on every run, metrics kept

**Files:** `webapp/store.py` (columns `program`, `week_start`, `metrics`; migration), `webapp/runs.py` (store metrics at finish; keep on expiry), `webapp/app.py` (upload fields, tag edit `POST /runs/<id>/tag` for the run's owner or an admin), templates; Test `webapp/tests/test_runs.py`.
- [ ] Tests: `test_upload_records_program_and_week`, `test_metrics_saved_when_a_run_finishes`, `test_history_survives_file_expiry`, `test_untagged_runs_can_be_tagged` (owner or admin only, 403 otherwise), `test_old_database_gains_analytics_columns`.

### Task 3: analytics

**Files:** `webapp/analytics.py`; Test `webapp/tests/test_analytics.py`.
**Produces:** `program_weeks(runs) -> dict[program, list[week]]`; `week` rows hold the metrics, run id, runs that week, deltas vs previous week; `insights(weeks) -> list[str]`; `suggestions(week) -> list[dict(level, text)]`; `recurring(weeks) -> grid` (weeks short per day and hour); `team(runs) -> list[dict]` per user.
- [ ] Tests: `test_latest_run_counts_for_the_week`, `test_one_week_has_no_deltas`, `test_associates_trend_sentence` ("7 -> 6, down 1"), `test_coverage_before_and_after_trend_sentences`, `test_recurring_short_hours_counted_across_weeks`, `test_target_suggestion_names_the_90_percent_share`, `test_team_activity_per_user`.

### Task 4: charts

**Files:** `webapp/charts.py`; Test `webapp/tests/test_charts.py`.
**Produces:** `columns(labels, values, unit, deltas=None)`, `lines(labels, series: list[(name, colour, values)], y_max=100, unit="%")`, `hbars(rows: list[(label, value, colour)])`, `heat(rows, cols, grid)` -> SVG `Markup`; each mark carries `data-tip`; values escaped.
- [ ] Tests: `test_columns_have_one_bar_per_week_and_capped_width`, `test_lines_have_a_legend_for_two_series`, `test_labels_are_escaped`, `test_empty_series_says_no_data`.

### Task 5: pages

**Files:** templates `programs.html`, `program.html`, `team.html`; `webapp/static/app.css`, `app.js` (tooltip); nav; Test `test_runs.py`, `test_ui_playwright.py`.
- [ ] Tests: `test_programs_page_lists_programs_with_latest_figures`, `test_program_page_shows_history_insights_and_suggestions`, `test_program_names_are_escaped_and_url_safe`, `test_team_page`, browser `test_program_analytics_page` with screenshots.

### Finish

- [ ] Website suite, full gate, package, push, send screenshots and package.
