# Phase BR (forecast accuracy) and Phase BS (capacity plan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the owner's standing choice: inline). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Owner, 2026-11-18: "Develop current forecast first to be perfect then add capacity plan." Make the week forecast measurably better where
the measurement says it can be, fix what a review of the forecast screens finds, then add a capacity plan (people needed against people held, week
by week, months ahead, with the hiring it implies).

**Architecture:** Every forecast change is a behaviour change, so each one is a candidate with a rule written in `evidence/phase_br/RULES.md`
before its first run, measured on made-up histories with a known truth, and shipped only if it meets the rule. The capacity plan is a new pure module
(`webapp/capacity.py`) fed by the existing months-ahead model (`outlook`), the forecast's weekday shape and the existing Erlang code, with a new
Volumes tab and an Excel download. The engine is not touched.

**Tech Stack:** Python 3 standard library, Flask/Jinja, unittest, Playwright (already installed). No new dependency.

**Spec:** this file (the owner's request above is the whole of the spec); context in `docs/HANDOFF.md` (Phases BI, BJ, BL, BM) and
`docs/howto/FORECAST_INTERVAL_ZONES_METHODS.md`.

## Global Constraints
- CLAUDE.md rules win: no speculative behaviour change (pre-registered rule or measured configuration), no test weakened, no protected file touched.
- Website files: strict CSP (no inline script, style or handler), sentence-case copy, `© 2026 Omar Mokhtar. All rights reserved.` in the first 4 lines.
- Made-up data only ("Associate NN", made-up programs and volumes).
- The planner's typed numbers always win; a suggestion is never taken without a press.
- Run tests with `TMPDIR` set to a folder deleted afterwards (Phase BM lesson).
- Release gate: `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`; package via `tools/build_production_package.py`; sealed check `tools/readonly_check.py --gate`.

## Review Focus
1. A program with very little volume (a few contacts an interval): shape and handle time must not swing on one odd day.
2. Intervals with volume but no handle time recorded (blank AHT column): the forecast must fall back, not plan for zero work.
3. Capacity with no history, or under 3 clean weeks: the tab says what is missing; nothing is invented.
4. Capacity numbers a planner types wrong (attrition 120 %, negative head count, a class in the past): refused in words, nothing kept.
5. Capacity for Email (workload, no Erlang) and Chat (concurrency): the needed hours use each channel's own rule, as the Staffing tab does.

---

### Task 1: The measurement harness and the pre-registered rules

**Files:**
- Create: `evidence/phase_br/RULES.md` (written and committed before any run)
- Create: `evidence/phase_br/accuracy.py` (made-up histories with a known truth; runs the candidates; prints a table)

**Rules to write (exact):**
- **R1, the interval shape.** Today: each weekday's shape is the per-interval median of day shares over the chosen weeks, renormalised (`M`).
  Candidates: `A` the per-interval mean of day shares; `P` pooled (each interval's contacts summed over the weeks, over the weekday's total).
  Histories: 30-minute intervals, 6 chosen weeks, Poisson counts around a known weekday shape (a two-peak day, open 08:00 to 24:00; a lighter
  weekend), at four week volumes (1,500; 7,000; 35,000; 200,000), and a fifth, "drift", at 7,000 where the evening peak grows 2 % a week.
  Score: interval WAPE of the forecast week against the known expected counts, given the true week total (so only the shape is scored).
  **Adopt a candidate** only if, on two seed sets (1 to 5 and 101 to 105), its WAPE is lower than `M`'s on at least 4 of the 5 histories and never
  more than 0.5 points higher on any. If both pass, the lower mean WAPE. Otherwise `M` stays.
- **R2, handle time by interval.** Today: one handle time for the whole week (volume-weighted over the chosen weeks). Candidate `H`: per weekday and
  interval, the volume-weighted handle time of the chosen weeks, pulled towards the week's handle time where little volume stands behind it
  (weight n / (n + 20), n = contacts behind that interval). Histories: the four volume levels above with a true handle time that runs 25 % above the
  day's average from 20:00 and 15 % below it from 08:00 to 11:00, plus each level again with a flat true handle time (the control).
  Score: people needed per interval (Erlang C, 80/20, occupancy cap 88 %) from the forecast against the people needed with the true counts and the true
  handle time: sum of absolute differences over the sum of the true needs.
  **Adopt `H`** only if, on both seed sets, its error is lower on all four varying histories and no more than 1 point higher on any flat control.
  Otherwise the single handle time stays.

- [ ] **Step 1:** Write `RULES.md` with R1 and R2 exactly as above; commit it alone (`Phase BR: rules written before the runs`).
- [ ] **Step 2:** Write `accuracy.py` (pure functions from `webapp.forecast` and `webapp.erlang`; the candidates live in the script; `python
  evidence/phase_br/accuracy.py SEEDSET` prints one table per rule).
- [ ] **Step 3:** Run both seed sets; save `accuracy_run_1to5.txt`, `accuracy_run_101to105.txt`; write the result and the verdict under each rule
  in `RULES.md`. Commit.

### Task 2: Ship what passed (only if a rule is met)

**Files:** Modify `webapp/forecast.py` (`build_profile`) for R1; `webapp/volumes.py` (`_aht`, `_needs`, `forecast`, saved basis) for R2.
Test: `webapp/tests/test_br_forecast_accuracy.py`.

**Interfaces (R2, if adopted):** `VolumeBook._aht_profile(key, channel, used) -> Tuple[float, List[List[Optional[float]]]]` (the week's handle time
and, per day Sun..Sat and interval, the handle time to use); `_needs(..., aht: float, ..., aht_grid: Optional[List[List[Optional[float]]]] = None)`.
A typed handle time on Settings still wins everywhere (the grid is not used). A saved forecast keeps its grid in `basis["aht_grid"]`; one saved before
this phase has none and is planned with its single handle time, as before.

- [ ] **Step 1:** Failing tests: (R1) the chosen estimator's shape on a fixed small history equals the hand-worked numbers; (R2) a history whose
  evening handle time is twice the morning's plans more people per contact in the evening than the morning; a typed handle time gives the same needs
  as before this phase; an interval with contacts but no handle time uses the week's; a saved forecast from before the phase reads unchanged.
- [ ] **Step 2:** Run, see them fail. **Step 3:** Implement. **Step 4:** Run the new file and the volumes tests (`webapp/tests/test_bi_*`,
  `test_bj_*`, `test_bl_*`, `test_bm_*`); all pass. **Step 5:** Commit.
- If a rule is not met: no code change for it; the evidence and verdict are the deliverable, and the how-to says so.

### Task 3: Forecast screens reviewed

- [ ] **Step 1:** Seed a made-up program with 60 weeks of Phone and Chat history; Playwright screenshots (desktop 1440 wide and phone 390 wide) of
  Data, Forecast (with and without a typed total), Staffing, Months ahead, How we did, Settings into `evidence/phase_br/screens/`.
- [ ] **Step 2:** Review them with better-interface and web-interface-guidelines; list each finding in `evidence/phase_br/REVIEW.md` as fix /
  leave (with why).
- [ ] **Step 3:** Each "fix" is a defect: a failing test first (template or browser test), then the fix. Commit per fix.

### Task 4: The capacity model (pure)

**Files:** Create `webapp/capacity.py`; test `webapp/tests/test_bs_capacity.py`.

**Interfaces:**
- `check_inputs(raw: Dict[str, Any], first_week: date) -> Dict[str, Any]`: strict; returns `{"head_count": float, "hours_per_week": float,
  "attrition": float, "training_weeks": int, "nesting_weeks": int, "nesting_output": float, "classes": [{"week": "YYYY-MM-DD", "people": int}]}`.
  Ranges: head count 0 to 5,000; hours a week 10 to 60 (default 40); attrition 0 to 30 % a month (default 0, the page asks for the program's own);
  training 0 to 26 weeks (default 4); nesting 0 to 12 weeks (default 2) at 10 to 100 % output (default 50); classes up to 20, each 1 to 500 people,
  starting on a week start no earlier than `first_week - 26 weeks`. Bad value: `ValueError` naming the field.
- `plan(weeks: List[Dict[str, Any]], inputs: Dict[str, Any], shrinkage: float) -> Dict[str, Any]` where each week is `{"week": "YYYY-MM-DD",
  "hours": float, "low": float, "high": float}` (agent hours needed on the floor). Returns `{"weeks": [{"week", "needed", "needed_low",
  "needed_high", "available", "gap", "classes_live"}], "first_short": Optional[str], "suggestion": Optional[{"start": "YYYY-MM-DD", "people": int,
  "ready": "YYYY-MM-DD"}]}`.
  needed = hours / (hours_per_week x (1 - shrinkage)); available = head count shrunk by weekly attrition (1 - a)^(1/4.345) each week, plus each class
  from its start (0 while training, `nesting_output` while nesting, 1 after; a class shrinks by attrition from its start); gap = available - needed.
  suggestion: the first week with gap < 0 (on `needed`), a class of ceil(shortfall / survival through training and nesting) starting training +
  nesting weeks before it (no earlier than the first week; then `ready` is later than the short week, and the page says so).
- [ ] Steps: failing tests for each formula on hand-worked numbers, each refusal, no history -> empty weeks; implement; pass; commit.

### Task 5: The capacity tab and download

**Files:** Modify `webapp/volumes.py` (`capacity_inputs`, `set_capacity_inputs`, `capacity(key, channel, months)`), `webapp/routes/volumes.py`
(tab `capacity`, `POST /volumes/capacity`, `GET /volumes/capacity.xlsx`), `webapp/templates/volumes.html`, `webapp/static/app.css`;
`webapp/tests/test_az_route_map.py`'s `route_map.json` regenerated with `--write` (two routes added on purpose); tests in `test_bs_capacity.py` and a
browser class `TheBsCapacityInTheBrowser` in `webapp/tests/test_ui_playwright.py`.

- `VolumeBook.capacity(key, channel, months)`: the outlook's weeks (expected, low, high totals) -> each week's calls per interval through the latest
  forecast shape (`forecast_week`) -> people needed per interval through `_needs` (Erlang, chat concurrency, email workload as on Staffing) -> agent
  hours = sum of needs x interval hours -> `capacity.plan`. Inputs kept in the volume settings under `"capacity"` per channel (who may edit: as
  Settings). Head count, when not typed, is shown beside the roster count as a hint, never taken silently.
- Tab "Capacity" after "Months ahead": inputs form, a table per week (needed, range, available, gap; short weeks marked in words, not colour only),
  the suggestion sentence, the chart (columns needed, line available) and "Download for Excel".
- [ ] Steps: failing tests (page shows the table for a seeded program; POST refuses a bad attrition with the message and keeps nothing; viewer
  without edit right cannot POST; the download opens with openpyxl and its numbers equal the page's); implement; pass; route map; commit.

### Task 6: Docs, handoff, full check, package
- [ ] How-to `docs/howto/CAPACITY_PLAN.md`; update `docs/howto/FORECAST_INTERVAL_ZONES_METHODS.md` with R1/R2 outcomes; `docs/HANDOFF.md` sections
  for BR and BS (rulings listed); full chain; package; sealed check; send the package.

## Rulings (the owner can overturn)
- Capacity counts people on the floor as the forecast does and adds the channel's shrinkage from Settings once (the schedule engine adds it itself
  for the schedule; the capacity plan has no engine behind it).
- Attrition is typed per month and applied weekly; it has no default from history (the site holds no leaver records).
- Intraday reforecast is not in this phase (it is a new screen, not the current forecast); it stays on the list.
