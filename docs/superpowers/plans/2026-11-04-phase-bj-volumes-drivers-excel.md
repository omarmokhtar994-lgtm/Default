# Phase BJ: volumes with the same weeks for every weekday, what else is known about the week, data entry and Excel formulas

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, per CLAUDE.md). This file is the record of the plan as it was executed; the evidence is in `evidence/phase_bj/CHECKS.md`.

**Goal:** Make the volumes forecast read the same number of whole weeks for every weekday (adjustable, six by default), let the planner enter actuals by typing per interval or by filling a
downloaded draft, ask what the history cannot know (promotions and events, AI and automation, customer growth, last year) and show how each answer moves the suggestion, and give the Erlang
staffing as one Excel formula (`=AGENTS(...)`).

**Architecture:** Pure modules with no new dependency: `webapp/drivers.py` (events, AI periods, growth, last year, the waterfall), `webapp/excel_agents.py` (the one-cell formula and the Excel 365 definitions),
`webapp/volumes_draft.py` (draft workbook and its reader, through the existing `parse_grid`), `webapp/volumes_formulas.py` (the workbook with live formulas). `forecast.choose_weeks` picks whole weeks.
`VolumeBook` joins them; a saved forecast keeps its own grid. One new table (`volume_drivers`) and two columns (`volume_forecasts.grid`, `.basis`).

**Tech Stack:** Python, SQLite (existing store), Flask/Jinja, vanilla JS (strict CSP, Trusted Types), openpyxl; LibreOffice (already used by tests) recalculates the Excel formulas.

**Spec:** The owner's message of 2026-11-04 (quoted in `evidence/phase_bj/CHECKS.md`).

## Global constraints
- Chat replies caveman style; code, docs, commits normal prose, sentence case; copyright line in the first four lines of every new file; strict CSP; made-up data only.
- No engine change; protected baselines untouched; no test weakened (the Phase BI forecast tests were re-pinned because the owner changed the contract: reason is in their docstrings).
- Program walls and Roles: new routes are in the permission map (`volumes_view` for downloads, `volumes_edit` for changes); every form carries the token; uploads go through the existing guards.

## Review focus (inputs the spec implies and tests pin)
- A weekday with holes in the history (missing day, outage day, holiday week): the whole week is left out with its reason and an older clean week steps in. Pinned: `test_bj_volumes_book.TheWeeksOfHistory`, `test_bj_invariants.TheEqualDaysRule`.
- A forecast saved last week must not move when the history, events, settings or growth change later. Pinned: `TheSavedForecast`, `test_a_saved_forecast_is_never_moved_by_later_changes`.
- Overlapping AI periods, AI that "moves" to its own channel, a rise that "moves", a percent of -100 or 900, a promotion that ends before it starts, a name that starts like a formula: refused in words, nothing kept. Pinned: `test_bj_drivers`, `TheForecastPage`.
- A draft with a typed word, a negative number, a future week, a missing date, an extra sheet, a card number, a giant sheet: refused whole. Pinned: `test_bj_draft`, `test_bj_volumes_routes.TheDraft`.
- The Excel formula against the site's Erlang on thousands of cases and on changed inputs. Pinned: `test_bj_excel_agents` (8,000 cases measured), `test_bj_volumes_formulas`, `test_bj_invariants.TheFormulaWorkbookOnRandomInputs`.

## Tasks (all done; checks in `evidence/phase_bj/CHECKS.md`)
1. **The one-cell formula.** `excel_agents.agents_formula` / `service_level_formula` / `lambda_definitions`; Python compares to 12 places (`erlang.TOLERANCE`) like a spreadsheet.
2. **Whole weeks.** `forecast.choose_weeks` (missing or zero open day, a day far below or above its weekday's usual, a part day, an odd week total, or left out by the planner: the week is dropped as a
   whole; the next older clean week steps in), `build_profile` over those weeks (shares normalised per day and per week, medians over the same weeks), gap-aware `suggest_total`.
3. **Saved forecast keeps its grid.** `volume_forecasts.grid` and `.basis` (weeks, handle time, shape factors); `VolumeBook.save_forecast` refuses without history; the report and downloads use the saved grid.
4. **Drivers.** `drivers.py` and the `volume_drivers` table; the suggestion is built step by step (the waterfall) and adds up exactly; a typed total is used as typed and events and AI only shape its days.
5. **Entry.** Typed grid on the Actuals tab (Excel paste by header and times), draft workbook (download, fill, upload), both through the existing check-then-save.
6. **The Forecast page.** Weeks of history, left-out weeks (remembered on request), start from history or last year, the questions panel, the waterfall, notes.
7. **Excel.** Workbook with live formulas and the site's figures beside them, and the `=AGENTS` definitions to copy.
8. **Checks.** Seeded invariant and fuzz tests, browser tests at 1280, 768 and 360 px, route map re-pinned for three routes, the chain, the package.

## Rulings (what was decided without asking, and what it costs if wrong)
- **The total is always the planner's (owner, 2026-11-04: "weeks only set the pattern, total is mine, I will give like 1000 calls").** The last N weeks set only the pattern (the share of each day and of each interval). With no number typed the page asks for one and shows no grid; the suggestion, the events, AI, growth and last year sit in an optional help block and the suggestion is taken only when the planner presses Use the suggestion. Events and AI never change a typed total; they only shape its days. The requirement workbook is written from saved forecasts only. Cost if wrong: a planner who expected the page to fill in a number by itself must type or press Use. This replaced my first reading, in which the trend suggestion became the week's total when none was typed.
- **AI periods on one channel cannot overlap.** The next period starts the day after the last ends. Cost: a planner who wanted two reductions to stack must split the dates.
- **Moves between channels** take a share of what AI removes on the source channel (from the source's history-based forecast, with its events) and add it to the destination's suggestion only; never to a typed total. A destination day with no hours takes none and says so.
- **Growth** has two modes: the measured trend (default) or the typed year-over-year rate, in which every past week is brought forward to the forecast week at the rate and the median is the starting point. A channel with the rate mode but no rate falls back to the trend and says so.
- **Last year** is the same weekdays 52 weeks back (364 days), grown by the rate; it is shown beside the suggestion and used only when the planner starts from it.
- **Weeks of history** 3 to 26, six by default (the channel's setting); the old look-back of eight older weeks is kept so a left-out week is replaced by an older clean one.
- **Drivers are stored per program and edited without a lock.** Two planners adding at the same second could lose one entry (last write wins). Cost: one entry to re-add; the page shows what is stored.
- **New controls were built without a sample round** because the owner asked for the whole feature to be finished in one go ("dont come back unless this is 500% accurate"); they use the site's existing components and tokens. Screens: `evidence/phase_bj/screens/take.py`. The owner may ask for changes.
- **Time zones (owner, 2026-11-04: "I may add actuals in EST and request required associates in Egypt time").** The program's volumes are kept in one zone (Settings, "The volumes are kept in", Cairo unless set; the zones are the site's own list, with clock changes by date). Typed, pasted, uploaded and draft actuals each say which zone they are in
  ("Times in", the program's zone first) and are moved into the program's zone when checked: an evening in New York can be the next morning in Cairo. A time the clocks cannot place (the hour a region skips, or the hour it repeats, and the file does not say which) refuses the whole upload, naming the day. Rows moved from another zone are saved
  cell by cell, so a partial first or last day never wipes the rest of that day; a same-zone upload still replaces a day as a whole. The forecast page and the Excel downloads can show the grids in another zone ("Show times in"); the week is turned as a whole (the hours that spill over the edge go to the other end of the same week, this week's pattern standing in for the neighbouring week), so a total is never lost or made up.
  The requirement tabs for the input workbook stay in the program's zone. **Limits:** changing the program's zone does not move volumes already saved; "How we did" lines the schedule's requirement (in the schedule's own zone) beside volumes (in the program's zone), so set the program's zone to the one the schedules are made in; half-hour zones (India, Nepal) are not offered because every zone in the site's list has a whole-hour offset.
