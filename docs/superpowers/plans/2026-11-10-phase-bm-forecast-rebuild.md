# Phase BM: the forecast section rebuilt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (inline; CLAUDE.md). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hourly history is read as hourly, the page can be viewed at 30 or 60 minutes and in any zone everywhere, the suggested week total comes from the method that back-tests best on the program's own history (with its accuracy shown), and the page reads as three steps: data, forecast, staffing.

**Architecture:** Storage is unchanged (rows at the program's interval, in the program's zone): every new thing is a pure function over what is stored, in three new modules (`volumes_grain.py`, `forecast_methods.py`, additions to `volumes_zone.py`), wired through `volumes.py`, `routes/volumes.py` and `templates/volumes.html`. The engine is not touched.

**Tech Stack:** Python 3, Flask + Jinja, plain CSS and JS under the strict CSP, unittest, Playwright.

**Spec:** the owner's messages of 2026-11-10 (screens of the forecast grid and the hours worked) and the proposal they confirmed: "30-60 only", "Yea it's hourly", "All together". Quoted in each task.

## Global Constraints

- Website files: strict CSP (no inline script, style or handlers), sentence-case copy, `© 2026 Omar Mokhtar. All rights reserved.` in the first 4 lines; made-up "Associate NN" data only.
- The engine, the baseline workbooks and `engine/regression_assets` are not touched; the release gate stays at 1621 tests.
- No test is weakened. A test is re-pinned only where the owner's request changed the measured contract, with the reason in the test.
- The requirement tabs and everything the schedule reads stay at the program's interval and in the program's zone.
- View interval: 30 or 60 minutes only, and only values that are a multiple of the program's interval.
- No new dependency.

## Rulings made while planning (each costs what it says if wrong)

- **Storage is not moved to UTC.** The proposal said "stored once in UTC"; the same visible result (any place shown in any zone, nothing lost, no rights needed to look) is reached by converting what is stored, without rewriting two years of rows. Cost if wrong: a later migration.
- **A forecast shown in another zone** takes the hours that cross the week's edge from the neighbouring weeks' saved forecasts when they exist, and from this week's own pattern when they do not (said on the page). Cost if wrong: the edge hours of an unsaved neighbour are this week's.
- **Unusual weeks** are left out of the back-test and the level automatically and are marked in the list of weeks; leaving one out of the weekday pattern stays the planner's tick (the existing one). Cost if wrong: one more stored list.
- **The total stays the planner's** (owner, Phase BJ: "the total is always typed"): the best method changes the suggestion and its range, never the saved forecast.
- **The three steps** are the page's tabs renamed and ordered (Data, Forecast, Staffing, Months ahead, How did we do, More options); what each form does is unchanged. This is structure inside the current look, so it is built and shown as screenshots, not sent as a sample first.

## Review Focus

- A real half-hourly day whose :30 intervals are all zero by chance (a quiet night): must not be read as hourly.
- A program whose interval is 60 or 15: the interval choice offers only what divides.
- A zone a day ahead or behind (Cairo against Los Angeles): the weekday of hours worked moves with the time.
- Fewer than eight clean weeks of history: the suggestion is exactly what it was (the measured trend).
- A week of zeros or one enormous week in the back-test: no division by zero, the enormous week does not pick the method.

---

### Task 1: Hourly history is read as hourly

Owner: "why it's showing like this? Even if it's 30 mins" (a number at :00, zero at :30) and "Yea it's hourly".

**Files:** Create `webapp/volumes_grain.py`, `webapp/tests/test_bm_grain.py`. Modify `webapp/volumes.py` (save path, `hourly_days`, `spread_hourly`), `webapp/routes/volumes.py` (new POST `/volumes/actuals/spread-hourly`), `webapp/templates/volumes.html` (notice on the Data tab), `webapp/permissions`/audit labels as the existing routes do, `webapp/tests/route_map.json`.

**Interfaces (produces):**
- `volumes_grain.looks_hourly(slots: Sequence[float], step: int) -> bool`: true when `step` is 30 (or 15), every interval off the hour is 0 and at least `MIN_HOURS = 6` hours hold volume.
- `volumes_grain.spread_hour(slots: Sequence[float], step: int) -> List[int]`: each hour's volume shared over its intervals, whole numbers, the day's total unchanged, the remainder to the first interval.
- `volumes_grain.regrid(grid, step, to_step, combine) -> List[List[Any]]`: `combine` is `"sum"`, `"max"` or `"mean"`; `to_step` a multiple of `step`; None cells stay None when all parts are None.
- `Volumes.hourly_days(key, channel) -> List[str]`; `Volumes.spread_hourly(key, channel, user_id) -> int` (days changed; handle times copied to both halves).
- Saving actuals (file, draft or typed grid) spreads hourly days before they are kept and says how many in the summary notes.

- [ ] Tests first: a day with 12 hours of volume and zero halves is hourly and spreads to equal halves with the same total (odd counts keep the total); a quiet day with 3 hours of volume is not; a day with one non-zero half-hour is not; step 60 is never; `regrid` sums, takes the largest and averages; saving such a file keeps spread rows and the note; `hourly_days` lists held days and `spread_hourly` fixes them once (a second call changes 0); the route needs `volumes_edit`, a POST and the CSRF token, and is in the audit.
- [ ] Run: fail. Implement. Run: pass. Re-pin `route_map.json` (one new route, reason in `test_az_route_map`). Commit.

### Task 2: Look at it every 30 or 60 minutes

Owner: "why not have option to switch between 30 mins and 60 mins?" and "30-60 only".

**Files:** Modify `webapp/volumes.py` (`view_every`), `webapp/routes/volumes.py` (param `every` on the page, the forecast POST redirect and `table.xlsx`), `webapp/templates/volumes.html`. Test `webapp/tests/test_bm_every.py`.

**Interfaces:**
- `Volumes.every_choices(key) -> List[int]`: the values of (30, 60) that are multiples of the program's interval and not finer than it; the program's own interval first when it is one of them.
- `Volumes.view_every(f: Dict, every: int) -> Dict`: a copy with `calls` summed, `needs` the largest, `service` the mean weighted by calls, `step` = `every`, and `shown_every`; the program's own interval returns `f` itself. Typing a day's contacts stays at the program's interval.
- The choice travels in links and forms like `show_tz` does (`every=60`); an unknown value is refused in words.

- [ ] Tests first: choices for programs at 15, 30 and 60; a 30-minute forecast seen at 60 has half the rows, the same totals per day, the larger of each pair of needs; service weighted; the page shows the picker and keeps the choice across the channel and week links; `table.xlsx` at 60 has 24 rows a day; the requirement tabs ignore it.
- [ ] Run: fail. Implement. Run: pass. Commit.

### Task 3: The time zone in every place

Owner: "time zones is working bad!! We need zones to be an option in each place actuals/forecast part so here which timezone is used? And why cant be changed".

**Files:** Modify `webapp/volumes_zone.py` (`shift_hours`, `stitch`), `webapp/volumes.py` (`view_in`, `report` in a zone, hours typed in a zone), `webapp/routes/volumes.py`, `webapp/templates/volumes.html`. Test `webapp/tests/test_bm_zones.py`.

**Interfaces:**
- `volumes_zone.stitch(before, this, after, week_start, from_zone, to_zone, step, combine) -> grid`: the week in `to_zone` with its edge hours taken from the neighbouring weeks' grids (`before`/`after` may be None: then this week's own, as `rotate_grid` does today). `Volumes.view_in` uses the neighbours' saved forecasts and sets `edge` to `"saved"`, `"pattern"` or `"mixed"` for the page's sentence.
- `Volumes.report(..., zone=None)`: the actuals and the forecast of the week as read in `zone`, from the real neighbouring days (`convert_rows` over the week and a day each side).
- `volumes_zone.shift_hours(days: Dict[str, Any], minutes: int) -> Dict[str, Any]`: hours worked moved by a whole number of minutes, the weekday moving with the opening time; `Volumes.set_open_hours(..., typed_in=zone)` converts with the difference between the two zones on the day of saving and the page says so.
- Every tab says in one line which zone its numbers are in, with a "Show times in" picker on Forecast, Staffing, How did we do and Months ahead (day level), and "Times in" on the Data forms and the hours worked. Looking in another zone needs no edit right. The requirement tabs stay in the program's zone and say so.

- [ ] Tests first: a week seen in a zone 7 hours behind takes its first hours from the saved week before and its total is the sum of what is shown; with no neighbour saved it equals today's rotation and says "pattern"; the report in another zone uses the real next day; hours worked 16:00 to 04:00 typed in New York are kept as Cairo hours with the weekday right, including an opening time that crosses midnight; a reader without `volumes_edit` can switch zones; the zone note is on every tab.
- [ ] Run: fail. Implement. Run: pass. Commit.

### Task 4: The suggestion comes from the method that back-tests best

Owner: "make it super advanced and super best forecasting tool but still simple and easy to use".

**Files:** Create `webapp/forecast_methods.py`, `webapp/tests/test_bm_methods.py`. Modify `webapp/volumes.py` (`_history_base`, `forecast` output `accuracy`, `outlook` months), `webapp/templates/volumes.html` (accuracy panel). Evidence `evidence/phase_bm/methods.md` (the rule below, written before any run on real-shaped data).

**Interfaces:**
- `forecast_methods.METHODS`: ordered names `trend` (today's `forecast.suggest_total`), `recent` (last four clean weeks weighted 4, 3, 2, 1), `last_week`, `seasonal` (the same week a year before times the ratio of the last four weeks to the same four a year before; needs 56 weeks), `blend` (the median of the others that could answer).
- `forecast_methods.predict(name, series: Sequence[Tuple[date, float]], target: date) -> Optional[float]`: from weeks strictly before `target` only.
- `forecast_methods.unusual(series) -> Dict[date, str]`: weeks whose total sits more than `3.5 x 1.4826 x MAD` from the robust line, with the reason in words.
- `forecast_methods.backtest(series, target, weeks=8) -> {"tested": n, "methods": {name: {"wape": float, "bias": float}}, "best": name or None, "range": float}`: each of the last `weeks` clean weeks is predicted from the weeks before it (at least four); error is the sum of absolute misses over the sum of actuals; `best` is the lowest, the earlier name on a tie; None with fewer than four tested weeks; `range` is the best method's 80th percentile absolute miss as a share.
- `Volumes.forecast(...)["accuracy"]`: the back-test, the weeks left out as unusual, and the method used. With the program's method "measured trend" and a `best`, the suggestion's base, low and high come from it; with fewer than eight clean weeks, or the year-over-year method chosen, everything is as before.
- `Volumes.outlook(...)["months"]`: the weeks summed into calendar months (a week belongs to the month of its Thursday).

**Pre-registered rule (in `evidence/phase_bm/methods.md` before the runs):** on four made-up histories with a known truth (flat with noise, a steady rise, a yearly season, a level shift), the chosen method's error on the held-out last four weeks is no higher than the trend's on at least three of the four and never more than 2 percentage points higher on the fourth; otherwise the suggestion stays the trend and the back-test is shown as information only.

- [ ] Tests first: each method on a hand-made series; `predict` never reads the target or later; `unusual` marks a doubled week and not a steady rise; `backtest` on a flat series picks a method with a low error and on a rising one does not pick `last_week`; zeros do not divide; fewer than eight weeks leaves the suggestion exactly as before (pinned against `suggest_total`); the page shows "Off by N % on average over the last M weeks" and the table; months add up to the weeks.
- [ ] Run: fail. Implement. Run the rule's four histories, write the result. Run: pass. Commit.

### Task 5: Three steps on the page

Owner: "still simple and easy to use".

**Files:** Modify `webapp/templates/volumes.html`, `webapp/routes/volumes.py` (tab `staffing`), `webapp/static/` CSS as needed, `webapp/tests/test_ui_playwright.py` (class `TheBmScreensInTheBrowser`), `webapp/tests/test_bm_page.py`. Load `frontend-design`, `better-interface` and `web-interface-guidelines` first; screenshots to `evidence/phase_bm/screens/`.

- Tabs in this order and with these names: `Data` (actuals), `Forecast`, `Staffing` (new: people needed and service level for the week, the requirement and formula downloads, the hours worked in one line with a link to change them), `Months ahead`, `How did we do`, `More options` (settings). The first three carry their step number. Old `tab=` values keep working.
- Forecast opens with one summary line (the week, the suggestion with its range, the method and its accuracy) and the contacts; the questions, last year and the weeks used sit under "More options for this forecast" (a `details`). Nothing a form does changes.
- Empty states say the next step ("Add actual volumes on the Data tab").

- [ ] Tests first (`test_bm_page.py`): the six tabs and their order; `tab=staffing` shows the needs and the downloads for a saved forecast and the next step when there is none; every old tab name answers; each page has the copyright line and no inline script or style. Browser class: the three steps at 360 px and 1440 px with no horizontal page scroll, the interval and zone pickers working, a keyboard pass over the pickers.
- [ ] Run: fail. Implement. Run: pass; screenshots read. Commit.

### Task 6: Documents, the whole check, the package

- [ ] `docs/howto/` (the forecast how-to: interval, zones, hourly history, the back-test in plain words), `docs/HANDOFF.md` (Phase BM section), `CHANGELOG` entry with `changelog-generator`.
- [ ] `webapp/tests/solver_modules.txt` unchanged unless a new module plans channels.
- [ ] The whole chain (web units, solver modules one at a time, browser classes, gate, package) with 0 failures; `sha256sum`; send the package.

## Self-review

- Coverage: the 30/60 switch (Task 2), the zero half-hours (Task 1), zones in every place and why it could not be changed (Task 3), the best forecasting tool (Task 4), simple (Task 5). Each owner sentence has a task.
- Types: `regrid` (Task 1) is what `view_every` (Task 2) and the report use; `stitch` (Task 3) takes grids at the program's interval, so the interval view is applied after the zone view.
- Review Focus lines each have a test in Tasks 1 to 4.
