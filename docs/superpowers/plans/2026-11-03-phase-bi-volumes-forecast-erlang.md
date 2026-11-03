# Phase BI: volumes, forecast, Erlang and OTF Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, per CLAUDE.md) to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Take actual volumes (offered per interval, per channel, with AHT) as input; turn a next-week call count into a per-day, per-interval forecast shaped like the program's own history; compute the people needed per interval with Erlang for service-level programs; and show how the week went (OTF and trends) against what the system had, what was required and what was staffed.

**Architecture:** Three small pure modules with no new dependency (`webapp/erlang.py`, `webapp/forecast.py`, `webapp/volume_report.py`), one narrow table of actuals, program settings in one JSON column, and four pages built on the site's own look and SVG charts. The engine is not touched: the output is a requirement workbook laid out like the existing `FT Wise {n} Min` and `Chat/Phone/Email {n} Min` tabs, which the site already reads. Nothing per-interval is stored for forecasts; every grid is computed on request from the actuals and the week's totals (a few thousand numbers).

**Tech Stack:** Python `math` only, SQLite (existing store), Flask/Jinja, vanilla JS, `webapp/charts.py` SVG, openpyxl for the download.

**Spec:** The owner's message of 2026-11-03 and the answers below (no separate spec file; this plan is the record).

## Spec (owner, 2026-11-03, with the decisions taken)
- "adding actuals as input for volumes received per channel if needed": upload per interval, per channel. Owner's export gives **offered volume and AHT only** (no abandons, no answered-in-X, no real SL).
- "add forecasted volumes to calculate the OTF": **OTF = offered ÷ forecast** as a percent, per interval, day and week (100 % = forecast was right, above 100 % = more came than planned).
- "see trends to suggest the volumes will be received per interval as a %": interval and day shares built from the program's own recent weeks, with a suggested week total from the trend.
- "i can give like count of calls for next week and it automatically calculate calls per interval": the week total in, per day and per interval out (whole numbers that add up to the total exactly); per-day totals may be typed instead.
- "use Erlang ... needed associates per each interval if the program is SL": the site already has a per-program Measure (interval compliance, service level, volume weighted). **Service level** and **volume weighted** programs get Erlang; **interval compliance** programs get trends only.
- "how did we do vs what was in the system vs what was required": per interval, four lines: forecast, actual; the system's requirement (the `FT Wise` tab of the schedule in use); the requirement recomputed from the actual volume and AHT (Erlang); what was scheduled and on the floor (the day book). For SL programs also the service level the staffing would have delivered at the actual volume (modelled, not the ACD's own figure).
- Methods per channel (owner chose): **voice** Erlang C to a service level (X % in Y s); **chat** Erlang C with a concurrency factor; **email** workload method. "Be light": no new dependency, no background job, small tables, grids computed on request.

## Global Constraints
- Chat replies in caveman style; code, docs, commits in normal prose, sentence case. Copyright line in the first four lines of each new file.
- Strict CSP: no inline script, style or event handler. No new library. Made-up "Associate NN" and "Program NN" data in fixtures and samples.
- Every new page needs a sample the owner approves first (project rule for visual changes); no page is built before that.
- Program walls (Phase AR/AT): a person sees and changes only the programs they have; new permissions go in the Roles matrix; uploads go through the existing upload guards; exports never turn typed text into a formula (`exports.RISKY`).
- No change to the engine, its tests or the protected baselines. The release gate (`run_tests.sh`) and website suites stay green; raise `GATE_MINIMUMS.json` only for tests in `tests_staged`.
- Report times in Egypt time. Dates are the program's own week (`start_day`).

## Review Focus
- An interval with zero offered volume or zero forecast: OTF is blank, never a division by zero or 0 %; Erlang needs 0 agents, not 1.
- A week total typed as 0, negative, a decimal or text: refused with a plain message; a total smaller than the number of open intervals still distributes (many zeros).
- Day-of-week shares when history has a holiday, a partial day or a day with no data: excluded from the profile and said on the page; fewer than 3 usable weeks for a weekday: the page says the shape is thin and falls back to all days' shape, never a silent guess.
- Very high volume (Erlangs above 500): Erlang C must not overflow or take noticeable time (use the Erlang B recursion, not factorials).
- Daylight-saving weeks (Cairo, 29 Oct 2026): 23 or 25-hour days must not misalign intervals; the grid is built on the schedule's own interval index, as the rest of the site does.
- An upload with another program's name, duplicate rows, overlapping dates, 15 versus 30-minute rows, a wrong channel name, huge files or formulas: refused or merged by a stated rule, never partly applied.

## File Structure
- `webapp/erlang.py` (new): Erlang B/C, service level, ASA, occupancy, agents needed, FTE after shrinkage; chat concurrency; email workload.
- `webapp/forecast.py` (new): history shape (interval and day shares), exclusion of odd days, week total suggestion with trend, distribution of a total to days and intervals, OTF and bands.
- `webapp/volumes.py` (new): upload parsing and checks, the store calls, settings, the grids the pages show, the requirement workbook.
- `webapp/store.py` (modify): table `volume_actuals`, column `programs.volumes`, a table `volume_forecasts` (week totals only).
- `webapp/routes/volumes.py`, `webapp/templates/volumes*.html` (new, after samples).
- `evidence/phase_bi/` samples, REQUESTS.md (pre-registered rules), CHECKS.md.

---

## Phase 1: the calculation core (no page, no table; starts now)

### Task 1: Erlang

**Files:**
- Create: `webapp/erlang.py`
- Test: `webapp/tests/test_bi_erlang.py`

**Interfaces:**
- Produces:
  - `erlangs(calls: float, aht_s: float, interval_s: int) -> float` (traffic `A`)
  - `erlang_c(agents: int, traffic: float) -> float` probability a call waits (1.0 when `agents <= traffic`)
  - `service_level(agents: int, calls: float, aht_s: float, interval_s: int, threshold_s: float) -> float` fraction in 0 to 1
  - `average_wait(agents, calls, aht_s, interval_s) -> Optional[float]` seconds (None when unstable)
  - `agents_needed(calls, aht_s, interval_s, target: float, threshold_s: float, max_occupancy: float = 1.0) -> int`
  - `fte_required(agents: float, shrinkage: float) -> float` (`agents / (1 - shrinkage)`)
  - `chat_agents_needed(calls, aht_s, interval_s, target, threshold_s, concurrency: float, max_occupancy: float) -> int` (Erlang C on `aht_s / concurrency`)
  - `workload_agents(calls, aht_s, interval_s, max_occupancy) -> float` (email: `calls * aht_s / (interval_s * max_occupancy)`)

- [ ] **Step 1: Write the failing tests** (`test_bi_erlang.py`): `erlang_c` equals an independent direct-sum formula (`A^N/N! * N/(N-A)` over the sum) to 1e-9 for (A, N) in a grid of 30 pairs; `erlang_c(5, 5.0) == 1.0`; `erlangs(100, 180, 1800) == 10.0`; `agents_needed(0, 180, 1800, .8, 20) == 0`; `agents_needed(100, 180, 1800, .8, 20)` is the smallest `N` whose `service_level` is at least 0.8 (asserted by checking `N` passes and `N-1` fails) and is above 10; max occupancy 0.85 never returns an `N` with `A/N` above 0.85; `service_level` rises with each extra agent; chat with concurrency 2 needs fewer agents than voice at the same volume and at least `ceil(A/2)`; `workload_agents(60, 600, 1800, .9) == 60*600/(1800*.9)`; `erlang_c(2000, 1900.0)` returns in under 50 ms without overflow; `fte_required(10, .3) == 10/.7`.
- [ ] **Step 2: Run** `PYTHONPATH=. python -m unittest webapp.tests.test_bi_erlang`. Expected: ImportError (module missing).
- [ ] **Step 3: Implement `webapp/erlang.py`.** Erlang B by the recursion `B(n) = A*B(n-1) / (n + A*B(n-1))`; `C = B / (1 - (A/N) * (1 - B))`; `SL = 1 - C * exp(-(N - A) * T / AHT)`; `agents_needed` starts at `floor(A) + 1` and steps up, also requiring `A / N <= max_occupancy`.
- [ ] **Step 4: Run the tests.** Expected: all pass.
- [x] **Step 5: Commit** (`Phase BI: Erlang core`). Done: 19 tests.

### Task 2: Forecast shape, totals, distribution, OTF

**Files:**
- Create: `webapp/forecast.py`
- Test: `webapp/tests/test_bi_forecast.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces:
  - `Profile` dataclass: `step: int`, `shares: Dict[int, List[float]]` (weekday 0 to 6, each list sums to 1 per open weekday), `day_shares: Dict[int, float]` (sum to 1 over the week), `weeks_used: Dict[int, int]`, `excluded: List[Tuple[str, str]]` (date, reason), `thin: List[int]` (weekdays with fewer than 3 usable weeks).
  - `build_profile(days: Dict[date, List[float]], step: int, weeks: int = 8, today: Optional[date] = None, exclude: Iterable[date] = ()) -> Profile`: uses the last `weeks` weeks before `today`; per weekday the interval shares are the per-interval median across usable days then renormalised to 1; a day is unusable when its total is below 25 % or above 250 % of that weekday's median total, when it is in `exclude`, or when it has no volume; weekdays with no usable day fall back to the average shape of the other weekdays and are listed in `thin`.
  - `suggest_total(weekly_totals: List[float]) -> Optional[Tuple[int, int, int]]`: `(suggested, low, high)` from the last up to 8 weeks: robust slope (Theil-Sen) damped by half, applied to the median of the last 4; range from the median absolute deviation; `None` for fewer than 3 weeks.
  - `distribute(total: int, shares: Sequence[float]) -> List[int]`: largest-remainder rounding, always sums to `total`.
  - `forecast_week(total: int, profile: Profile, day_totals: Optional[Dict[int, int]] = None) -> Dict[int, List[int]]`: weekday to per-interval whole numbers; typed day totals win and the rest share what is left by `day_shares`; raises `ValueError` when typed day totals exceed the total.
  - `otf(actual: float, forecast: float) -> Optional[float]` (percent; `None` when `forecast <= 0`); `otf_total(actuals: Sequence[float], forecasts: Sequence[float]) -> Optional[float]` (ratio of sums); `band(value: Optional[float], low: float = 90.0, high: float = 110.0) -> str` (`"under"`, `"on"`, `"over"`, `"none"`).

- [ ] **Step 1: Write the failing tests** (`test_bi_forecast.py`): a made-up eight-week history with a known shape (a Monday peak at 10:00, flat 6 % per hour) gives shares within 0.5 point of the truth; a holiday Monday at 20 % of the usual is excluded and appears in `excluded`; a weekday seen only twice is in `thin` and uses the fallback shape; `distribute(1000, shares)` sums to 1000 for random shares (30 cases) and `distribute(3, [0.2]*5)` has three ones and two zeros; `forecast_week(7000, ...)` sums to 7000 over all days and intervals; typed Monday total 1500 is kept exactly and the rest sums to 5500; typed days above the total raise `ValueError`; `otf(110, 100) == 110.0`, `otf(5, 0) is None`, `otf_total([10, 0], [5, 5]) == 100.0`; `band(89.9) == "under"`, `band(110.0) == "on"`, `band(None) == "none"`; `suggest_total([1000, 1010, 1020, 1030, 1040, 1050])` is above 1050 only by a damped step and inside `(low, high)`; fewer than 3 weeks gives `None`; a flat series gives the same value and a narrow range.
- [ ] **Step 2: Run** the test file. Expected: ImportError.
- [ ] **Step 3: Implement `webapp/forecast.py`** (median and MAD by hand with `statistics`; no numpy).
- [ ] **Step 4: Run the tests.** Expected: all pass.
- [x] **Step 5: Commit** (`Phase BI: forecast core`). Done: 27 tests.

---

## Phase 2: actuals in (after Phase 1; table and upload, no page yet beyond the sample)

### Task 3: Store and upload
**Files:** `webapp/store.py`, `webapp/volumes.py`, `webapp/tests/test_bi_volumes_store.py`.
**Interfaces:** `Store.set_volume_rows(program, channel, rows: List[Tuple[str, int, float, Optional[float]]], user_id, at) -> int`, `Store.volume_rows(program, channel, first, last) -> List[dict]`, `Store.purge_volumes_before(day) -> int`; `volumes.parse_upload(path, interval: int) -> ParsedVolumes(rows, problems, summary)`; table `volume_actuals(program text, channel text, day text, slot integer, offered real, aht real, primary key (program, channel, day, slot))`, kept 2 years; template download `Volumes_Actuals_Template.xlsx` (Date, Interval start, Channel, Offered, AHT seconds).
- Tests (each before code): a good file stores the rows and says how many days and channels; the same file twice changes nothing; a row for a day already stored replaces it and the page says so; 15-minute rows in a 30-minute program are summed into slots; a wrong channel name, negative, decimal offered, a date outside the plausible range, an interval that is not on the grid, more than 400,000 rows, a macro workbook, a formula in a cell: refused with the row named and nothing stored; another program's data cannot be written without that program; purge removes only rows older than 2 years; an upload event is recorded.

### Task 4: Settings
`programs.volumes` JSON: per channel `{aht, sl_target, sl_seconds, shrinkage, max_occupancy, concurrency, sla_hours, forecast_weeks}` with ranges validated (SL 50 to 100 percent, seconds 5 to 600, shrinkage 0 to 60 percent, occupancy 50 to 100 percent, concurrency 1 to 5); `Programs.volume_settings(program_id)`, `set_volume_settings(...)`. Defaults: voice 80 percent in 20 s, AHT from the actuals when present; chat 80 percent in 30 s with concurrency 2; email workload, occupancy 85 percent.

## Phase 3: forecast and requirements (starts when sample 1 is approved)

### Task 5: The forecast page and the requirement workbook
`volumes.forecast_grid(program, week, total_by_channel, day_overrides)` returns per channel the per-weekday, per-interval volumes plus the Erlang requirement for SL and volume-weighted programs; `volumes.requirement_workbook(...)` writes `FT Wise {n} Min` (the sum of the channels: people needed on the floor, NOT divided by shrinkage, because the engine divides by (1 - shrinkage) itself from the Shrinkage tab) and `Chat/Phone/Email {n} Min` tabs in the exact layout `webapp/channels.py` reads, so the download can be pasted into an input workbook; tests: the written workbook is read back by `channels.read_channels` and `check_lines` finds the channel tabs equal to the FT Wise tab; every cell is a number, never text from a user; typed totals are saved in `volume_forecasts(program, channel, week_start, total, days, user_id, at)`; an interval-compliance program shows the volume forecast and no Erlang numbers.

## Phase 4: how did we do (starts when sample 2 is approved)

### Task 6: OTF and trends
`volume_report.week_report(program, week)`: per channel and interval forecast, actual, OTF, band; day and week roll-ups as ratio of sums; last 8 weeks' OTF, bias and weighted absolute error as a trend; for SL programs the Erlang requirement at actual volume and AHT, the system's requirement (the `required` of the version in use, `webapp/day.py` workbook read), scheduled and on the floor (the day book), and the modelled service level at the staffing that was on the floor (`erlang.service_level`), labelled as modelled. Tests: a made-up week with known numbers gives known OTF per interval, day and week; a week with no forecast says so; an interval-compliance program gets no Erlang or SL rows; the figures equal a hand calculation for one day.

## Phase 5: the pages, the menu entry, permissions
Pages `/volumes` (Actuals, Forecast, Requirements, Trends tabs), a Roles entry (`volumes_view`, `volumes_edit`), the home menu link under Insights, DESIGN.md note, browser test at 1440, 768 and 360 px in both looks (Tab ring, no sideways scroll, 24 px targets), attack tests (walls, CSRF, uploads), the website suites, the package.

## Rulings taken from the code
- The engine reads FT Wise as effective FTE on the floor and applies the Shrinkage tab itself (`webapp/day.py` header, engine `effective_factor = 1 - shrinkage`). So the requirement the site writes is the Erlang agents, not agents divided by shrinkage; the page shows the with-shrinkage figure only as information.
- Sample pages (made-up numbers, the site's own shell and charts) are in `evidence/phase_bi/samples/`; nothing is built into the site until the owner approves them.

## Risks and rulings taken
- Erlang C assumes no abandonment and a single queue; it over-staffs where customers abandon. Stated on the page; an abandon-aware (Erlang A) option is a later, owner-approved step.
- Chat concurrency and email workload are standard simplifications; the page names the formula it used.
- Actuals carry no real service level; the "how did we do" service level is modelled from staffing and volume and is labelled that way.
- Trend suggestions are suggestions: the typed number always wins and nothing is saved without a click.
- Light: one narrow table (about 50 thousand rows per channel-year at 30 minutes), no job, no cache, no library; a week grid is computed in milliseconds.
