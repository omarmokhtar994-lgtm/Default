# Phase BL: 8.5 hour shifts, part-timers, working hours, sites, email by day, months-ahead forecast

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the engine schedule an 8.5 hour shift and part-time associates, and let the website forecast by operating hours, by site, by day for email, and for months ahead.

**Architecture:** Engine: new optional columns on the input workbook's Schedule sheet (`Shift Length`, `Type`, `Off Days`, `Breaks`) read into `Associate`, and used by the shift-eligibility, off-day and break code that today assumes one length and 2 or 3 off days. Website: three new per-program settings (open hours, sites with share rules, history input for email) feeding `webapp/volumes.py`, plus a months-ahead view built from `webapp/drivers.py` figures that already exist.

**Tech Stack:** OR-Tools CP-SAT (engine), Flask, Jinja, SQLite, vanilla JS (website), unittest.

**Spec:** the owner's request of 2026-11-07 (chat) and the answers to the three questions asked the same day: both sites are worked out, an associate is either an 8.5 h or a 9 h person for the whole week, and a year or more of day-by-day history exists.

## Global Constraints

- Project rules in `CLAUDE.md` win. The RC9.1 baseline workbooks and `engine/regression_assets` keep their exact bytes; no baseline result is regenerated.
- Every engine behaviour change is backed by a pre-registered A/B rule written in the task before the run. With the new columns blank, a workbook must give the same result as today: the A/B arm is the current engine on the current benchmark workbooks, and the pass rule is "identical Production Summary and identical schedule rows".
- No validation is weakened. A bad value in a new column is a named `HARD_` refusal, never a silent fallback.
- Website: strict CSP, sentence-case copy, `© 2026 Omar Mokhtar. All rights reserved.` in the first 4 lines of each new file, CSRF on every POST, made-up "Associate NN" data only.
- Commit and push only to `ccr-90ec94cc-a37tqk`. Times in Egypt time.
- Release gate: `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`; raise the minimums only for tests this phase adds.

## Rulings taken (owner can overturn)

- Ruling: an 8.5 h associate gets the same break set as a 9 h associate, because the owner chose the "fixed per associate" option, which says nothing about breaks. The existing `break_sets_by_shift_length` input already lets the workbook state a different set for 510 minutes; cost if wrong: one workbook row.
- Ruling: with no volume in an open interval, Phone and Chat keep 1 agent (a "minimum cover" setting, default 1, 0 allowed); Email has none. Cost if wrong: change the default.
- Ruling: email work for a day is spread evenly over that day's open intervals, because the 24 hour email service level makes the timing inside the day unimportant. Cost if wrong: one function.
- Ruling: the internal site is the one the scheduler plans; every other site is shown for information (its required agents), not scheduled.

## Review Focus

- A part-timer with 0 off days or more off days than days in the week: refuse in words.
- A week where every associate is 8.5 h but the Shift Library has no 8.5 h shift: refuse, name the associate.
- Site shares on a day that do not add up to 100 %: refuse, name the day and channel.
- Open hours that cross midnight (an overnight operation) and daylight-saving days.
- History with gaps or a partial first and last week: use the existing "at least 5 days of data counts as a week" rule, say which weeks were left out.

---

## Part 1: Engine

### Task 1: Per-associate columns on the Schedule sheet

**Files:**
- Modify: `engine/_tools/l632_universal_scheduler.py` (`Associate` dataclass near line 681; roster reader near line 1700)
- Test: `webapp/tests/test_bl_engine_columns.py` (builds a small workbook with `openpyxl`, calls the parser; no solve)

**Interfaces:**
- Produces: `Associate.shift_minutes: Optional[int]` (None = the workbook default), `Associate.part_time: bool`, `Associate.off_days: Optional[int]`, `Associate.breaks_per_day: Optional[int]`.
- Header names, case and spacing ignored: `Shift Length` (hours, e.g. 8.5), `Type` (`Full time` or `Part time`), `Off Days` (whole number), `Breaks` (whole number a day).

- [ ] **Step 1:** Write `test_blank_columns_read_as_none`, `test_columns_read_when_present`, `test_bad_values_are_refused_by_name` (`HARD_INVALID_SHIFT_LENGTH`, `HARD_INVALID_ASSOCIATE_TYPE`, `HARD_INVALID_OFF_DAYS`, `HARD_INVALID_BREAKS`). Run: expect FAIL (attributes missing).
- [ ] **Step 2:** Add the four fields (defaults None/False) and read them by header in the roster reader, appending the `HARD_` warnings for bad values. Run the tests: expect PASS.
- [ ] **Step 3:** Run the existing parser tests (`python -m unittest discover -s webapp/tests -p "test_*input*"` and the engine selfchecks via `run_tests.sh --quick` if it has one). Expect PASS, then commit.

### Task 2: The 8.5 hour shift, fixed per associate

**Files:**
- Modify: `engine/_tools/l632_universal_scheduler.py` (`associate_day_eligible_shifts`, `_parse_duration_set` only if 8.5 is refused today)
- Test: `webapp/tests/test_bl_engine_85.py`

**Interfaces:**
- Consumes: `Associate.shift_minutes`.
- Rule: an associate with `shift_minutes` set may only be given library shifts of that length (within the existing 5 minute tolerance); blank keeps today's behaviour.

- [ ] **Step 1:** Pre-register the A/B rule in this file's docstring: arm A is the current engine, arm B the changed engine, on the benchmark workbooks with the new columns blank; pass when schedules and Production Summary are identical.
- [ ] **Step 2:** Test `test_a_510_minute_associate_only_gets_510_minute_shifts` on a small workbook (Allowed Shift Durations `9, 8.5`, library with both lengths, two associates) with a short solver limit; and `test_no_matching_shift_in_the_library_is_refused_by_name`. Expect FAIL.
- [ ] **Step 3:** Filter eligible shifts by `shift_minutes` in `associate_day_eligible_shifts`; add the refusal. Run the tests: PASS.
- [ ] **Step 4:** Run the A/B: both arms on the benchmark workbooks, compare. Record the result in `evidence/phase_bl/ab_columns_blank.md`. Do not touch `engine/regression_assets`.

### Task 3: Part-timers

**Files:**
- Modify: `engine/_tools/l632_universal_scheduler.py` (`required_off_days` at line 5707, the break builders that read `break_sets_by_shift_length`)
- Test: `webapp/tests/test_bl_engine_parttime.py`

**Interfaces:**
- Consumes: `Associate.part_time`, `.shift_minutes`, `.off_days`, `.breaks_per_day`.
- Produces: `required_off_days(parsed, associate, long_mode)` returns `associate.off_days` when set (checked to be 0..6, and at most 7 minus the days the associate must work), else today's 2 or 3.

- [ ] **Step 1:** Tests: `test_a_part_timer_gets_the_off_days_the_sheet_says` (for example 4 off days = 3 shift days), `test_breaks_per_day_overrides_the_break_set_for_that_person`, `test_a_part_timer_counts_in_coverage_for_the_hours_they_work`, `test_off_days_beyond_the_week_are_refused`. Expect FAIL.
- [ ] **Step 2:** Implement the off-day rule first, run; then the break-count rule (keep the break set's own lengths and windows; only the count changes, taken from the front of the set); run.
- [ ] **Step 3:** Same A/B as Task 2 with all four columns blank. Record in `evidence/phase_bl/ab_columns_blank.md`.
- [ ] **Step 4:** Solve a small mixed workbook (3 full-time, 2 part-time) end to end and keep the output as `evidence/phase_bl/mixed_week_check.md` (what was asked, what the schedule gave).

---

## Part 2: Website

### Task 4: Open hours and minimum cover

**Files:**
- Modify: `webapp/volumes.py` (settings, requirement calculation), `webapp/store.py` (a `volume_hours` table), `webapp/routes/volumes.py` (`/volumes/settings`), `webapp/templates/volumes.html`
- Test: `webapp/tests/test_bl_open_hours.py`

**Interfaces:**
- Produces: `VolumeBook.open_hours(key) -> {channel: {weekday: (from_min, to_min)}}` (an end past 1440 means past midnight) and a `min_cover` setting per channel; `needs_for(...)` returns `max(needed, min_cover)` inside open hours and `0` outside them.

- [ ] **Step 1:** Tests: `test_zero_volume_inside_open_hours_keeps_the_minimum_cover`, `test_outside_open_hours_needs_nothing`, `test_open_hours_past_midnight`, `test_email_has_no_minimum_cover`. FAIL first.
- [ ] **Step 2:** Add the table and the two getters/setters, apply in the requirement calculation, add the settings form (hours per weekday per channel, minimum cover), sentence-case labels. PASS.

### Task 5: Email from daily history, worked out by volume

**Files:**
- Modify: `webapp/volumes_io.py` (accept a day-by-day email sheet), `webapp/volumes.py` (spread), `webapp/templates/volumes.html`
- Test: `webapp/tests/test_bl_email_daily.py`

**Interfaces:**
- Produces: for Email, history may be one value per day; `day_to_intervals(total, open_hours, pattern=None)` spreads a day evenly over the open intervals. The requirement stays `workload_agents` (volume × handle time ÷ occupancy). Example pinned in a test: 10 emails × 480 s = 4800 s, 1 agent for 80 minutes.

- [ ] **Step 1:** Tests: `test_daily_email_history_is_accepted`, `test_the_80_minute_example`, `test_a_day_spreads_over_open_intervals_only`, `test_per_interval_email_history_still_works`. FAIL first.
- [ ] **Step 2:** Implement and show the weekly email figure per day on the forecast page. PASS.

### Task 6: Sites and share rules

**Files:**
- Create: `webapp/sites.py` (rules and the split), `webapp/templates/sites.html` (or a block in the program settings)
- Modify: `webapp/store.py` (`sites`, `site_rules` tables), `webapp/routes/volumes.py`, `webapp/volumes.py`
- Test: `webapp/tests/test_bl_sites.py`

**Interfaces:**
- Produces: `SiteBook.rules(key)` rows `(channel, days, from_min, to_min, site, share_pct)`; `split(channel, weekday, minute) -> {site: share}` summing to 100 or raising `ValueError` naming the day and channel; `VolumeBook.requirement_by_site(...)`. The owner's example is a test: Phone 100 % Sutherland; Chat 100 % internal 09:00–16:00 and 100 % Sutherland 16:00–24:00; Email 60/40 on weekdays; everything 100 % Sutherland at weekends.

- [ ] **Step 1:** Tests: `test_the_owners_example_splits_as_described`, `test_shares_that_do_not_add_to_100_are_refused_by_name`, `test_overlapping_rules_are_refused`, `test_requirement_by_site_sums_to_the_whole`. FAIL first.
- [ ] **Step 2:** Implement rules, the split and the settings page; show required agents per site on the forecast page and in the requirement workbook (one sheet per site). PASS.

### Task 7: Months-ahead forecast

**Files:**
- Create: `webapp/months_ahead.py`
- Modify: `webapp/routes/volumes.py`, `webapp/templates/volumes.html`
- Test: `webapp/tests/test_bl_months_ahead.py`

**Interfaces:**
- Consumes: day-by-day history, `drivers` (YoY growth, events and promotions with start and end dates, AI periods).
- Produces: `months_ahead(history, drivers, start, months) -> [{month, low, expected, high}]` from a weekly trend plus a week-of-year seasonal index, then growth and promotion uplift on top. Fewer than 52 weeks of data: trend only, with a plain note (the owner has a year or more, so this path is a guard).

- [ ] **Step 1:** Tests on made-up series with a known answer: `test_flat_history_forecasts_flat`, `test_a_yearly_peak_repeats_next_year`, `test_yoy_growth_scales_the_months`, `test_a_promotion_adds_its_uplift_only_inside_its_dates`, `test_short_history_falls_back_to_trend_with_a_note`. FAIL first.
- [ ] **Step 2:** Implement with the standard library only (no new dependency); add a "Months ahead" table and a download. PASS.

### Task 8: Gate, package, handoff

- [ ] **Step 1:** Run the full chain (`/tmp/chain4.sh` pattern: units two at a time, browser classes one at a time), then `tools/build_production_package.py`.
- [ ] **Step 2:** Update `docs/HANDOFF.md` and add `evidence/phase_bl/`; deliver the package with its sha256.
