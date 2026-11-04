# Phase BJ: built and checked (2026-11-04)

© 2026 Omar Mokhtar. All rights reserved.

Owner, 2026-11-04: "I want the one equals =agents() in excel / And to choose the historical trend for 6 weeks u need to normalize data as well while using it make entery is manual on site per interval or excel
sheet to be uploaded and make a draft of sheet can be filled / Or more or less for that 6 weeks make it adjustable / But must be same count of days / So no if 6 sundays must be 6 Saturdays etc / Be smart search well
make this perfect dont come back unless this is 500% accurate and working 0 problems / Also add forecasting part in there and ask necessary questions for promotions start end expected increase % based on that,
maybe ask about customer increase YoY and other items that might help with accurate forecasting based on historical and additional insights, ask if AI will reduce volumes as well and from which channel what % in
which period and if will increase in next period then to how much etc". Plan and rulings: `docs/superpowers/plans/2026-11-04-phase-bj-volumes-drivers-excel.md`. Screens: `evidence/phase_bj/screens/take.py`.

## What was built, against the request
- **"=agents() in Excel".** `webapp/excel_agents.py`: one ordinary cell formula (POISSON, SUMPRODUCT, ROW, INDIRECT, EXP, ROUNDUP, INT, IF; no LET, no LAMBDA, no array entry, no macro) that works in every Excel and in LibreOffice,
  and the Excel 365 `=AGENTS(calls, aht, interval_seconds, target, answer_seconds, max_occupancy)` and `SERVICELEVEL` definitions to paste into Name Manager. The Forecast tab has the definitions with a Copy button and a download of
  a workbook whose people-needed grid is made of the formula (`webapp/volumes_formulas.py`), with the site's own figures beside it and a count of intervals that differ.
- **Normalised, the same N weeks for every weekday, adjustable.** `forecast.choose_weeks`: the newest N clean whole weeks (six unless the channel's setting or the page says otherwise, 3 to 26). A week is dropped as a whole, with its
  reason, for a missing or zero open day, a day far below (25 %) or above (250 %) its weekday's usual, a day with under half its usual busy intervals, a week total outside 60 to 160 % of the usual week, or the planner leaving it out; the next
  older clean week steps in (look-back N + 8). Every open weekday is read from those same weeks, so six Sundays means six Saturdays. Normalisation: each day becomes shares of its own total, each week becomes shares of its own total,
  medians over the same weeks; a growing history does not bias the day mix; the trend is a Theil-Sen line that respects gaps, damped by half each week ahead.
- **Entry per interval on the site, or by Excel, with a draft.** Actuals tab: (1) download the draft for a week (a sheet per channel, the input sheet's layout, week start in B2, a contacts block and a handle-time block, Excel refuses bad
  entries), (2) a typed grid (intervals down, Sun to Sat across; paste from Excel fills by the header and the times, or down and across from the cell; Enter and arrows move down), (3) upload or paste as before. All three go through the same
  check-then-save: one wrong cell and nothing is taken.
- **The questions.** Forecast tab, "What else do you know about this week?": promotions, launches, outages and holidays (channels, dates, change %, a dip or lift for some days after); AI and automation (channel, period, change %, a later period can
  reduce more, less or increase; optional share that moves to another channel); customer growth year over year per channel (trend measured or the typed rate); last year's same week per channel. "How the suggestion is built" shows each answer as
  a step with the days it touches and the change in contacts, adding up exactly to the suggested total.

## Checks measured (all passing on 2026-11-04)
- Excel against Python: 8,000 random cases recalculated by LibreOffice (`test_bj_excel_agents`), 0 differences after the 12-place comparison (an exact 70 % occupancy had been refused by a float hair; fixed in Python and formula). The workbook:
  every cell of Phone, Chat and Email equals the site's figure after LibreOffice recalculates it; changed inputs (target, answer time, occupancy, handle time, chats at once, a changed contacts cell) equal the site's Erlang; six random input
  sets equal it too (`test_bj_volumes_formulas`, `test_bj_invariants`).
- Tests added in Phase BJ: drivers 33, volume book 42, draft 24, Excel formula 6, formulas workbook 16, pages 41, seeded invariants and fuzz 12, browser 17. Earlier volumes modules still pass (forecast 36, store 18, reading 30, book 33, pages 28); the forecast and
  book tests were re-pinned because the contract changed (reasons in their docstrings) and no case they covered was dropped.
- Invariants on many seeded random cases: every open weekday has the same count of weeks; a forecast grid adds up exactly to its total and is whole numbers, zero where the weekday is closed; people only where there are contacts; the people needed
  meet the target or the occupancy cap binds; a saved forecast never moves when history, drivers or settings change later; the waterfall adds up exactly; moved contacts equal what the source lost times the share; hostile values (NaN, infinity, huge,
  unicode digits, nested, markup, formula leads) are refused or clean, never a crash; a tampered stored document never crashes the page; uploads keep all or nothing.
- Pages: walls between programs and roles for every new route, the token on every form, markup shown as text, bad weeks and bad dates said in words, downloads follow the page and a bad request is a 400.
- Browser (real Chromium): the typed grid is built in the program's interval; paste by header and times, bare paste, numbers that do not fit are left out and said; keys; typed week checked then saved; a mistake keeps nothing; no sideways scroll and 24 px
  targets at 1280, 768 and 360 px with every question open; an event added in the page becomes a step; the definitions copy to the clipboard; the workbook downloads.
- Route map re-pinned for exactly three new routes (`/volumes/draft.xlsx`, `/volumes/drivers`, `/volumes/formulas.xlsx`); the Roles matrix and the audit-event labels know them.

## The total is the planner's (owner, 2026-11-04, after delivery)
"The weeks only set the pattern, the total is mine, I will give like 1000 calls expected and it should show everything based on that." Changed: `VolumeBook.forecast` never takes the suggestion as the total (`needs_total` instead); the page asks for a number and shows
no grid until one is typed or saved; the weeks are labelled "Weeks for the pattern"; the suggestion, events, AI, growth and last year are one optional "Help with the number" block; the requirement workbook is written from saved forecasts only. Tests that pinned the old behaviour
(`test_bi_volumes`, `test_bi_volumes_routes`, `test_bj_volumes_book`, `test_bj_invariants`) were re-pinned with the reason in them; new page tests: no number gives a prompt and no grid, 1000 gives the grids, the people needed, the tiles and the charts, and a grid that adds up to 1000.

## Review pass after the first full build (2026-11-04, owner asked "are you sure 100 %?")
Skills used: verification-before-completion, security-and-hardening, web-interface-guidelines, better-accessibility, better-writing; outside checks: Microsoft Support pages for the LAMBDA steps (Name Manager, Refers to: matches the Read me),
for SUMPRODUCT (an array function without Ctrl+Shift+Enter) and for POISSON (a compatibility function that still works; the modern name POISSON.DIST takes the same arguments: the Read me says what to change if a future Excel drops it).
Found and fixed, each with a test that failed first:
- **A week at the edge of the calendar crashed a page** (OverflowError at year 1 and 9999; the BI history code had it too). Now refused in words by every entry point and the pages accept dates from 2015 to 2100 only.
- **A write to a week that was not a date was moved to the default week** (last year's totals could be saved into next week). Every writing route now refuses a bad week.
- **"²" and "①" passed the digit test and then crashed int()**: the message echoed the typed text. Now refused with the generic message.
- **Typed numbers were lost if the person left the page**: the grid now asks before leaving (and not after Check, Clear or an empty grid).
- **A refused answer or an added entry closed its panel**: the panel with entries, or the one just refused, stays open.
- **336 cells to tab through**: a "Skip the grid to Check" link and Left and Right arrows at the edges of a cell.
- **The page scrolled sideways at 320 px** (the day-totals table from Phase BI sat outside a scroll region): wrapped; 320 px added to the checks.
- The weeks table says "Status" with "Used" or "Not used: the reason"; errors say how to fix; removing names what was removed; the definitions box has a name for a screen reader.
Not checked: Microsoft Excel itself (only LibreOffice recalculates the formulas here; the workbook's own "intervals that differ" cell shows any difference at once), a screen reader, and an independent reviewer.

## Not done, on purpose
- Erlang A (abandonment), a service-level method for email, the ACD's own service level, holiday calendars by country, per-interval hand-typed forecasts.
- A lock between two planners editing events at the same second (last write wins; see the plan's rulings).
- A sample round for the new controls (see the plan's rulings): please look at the screens and say what to change.
