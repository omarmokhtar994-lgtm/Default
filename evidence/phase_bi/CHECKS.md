# Phase BI: built and checked (2026-11-03)

© 2026 Omar Mokhtar. All rights reserved.

Owner: "add a view the same as the input sheet, days and intervals, so it is easy to copy and paste ... and do everything needed". Built from the approved plan
(`docs/superpowers/plans/2026-11-03-phase-bi-volumes-forecast-erlang.md`); screens: `evidence/phase_bi/screens/` (made-up people and numbers; script `take.py`).

## What was built
- `webapp/erlang.py`, `webapp/forecast.py` (calculation core, 46 tests), `webapp/volumes_io.py` (reading actuals), `webapp/volumes.py` (the volume book), `webapp/routes/volumes.py`,
  `webapp/templates/volumes.html`, tables `volume_actuals`, `volume_forecasts`, `volume_settings`, a Volumes link in the left menu, two Roles entries (`volumes_view`, `volumes_edit`).
- **Four tabs** (`/volumes?tab=`): Actuals (what is held per channel; check then save; delete days; template), Forecast and needs, How we did, Settings.
- **The input sheet's layout everywhere:** every grid is a table with the header `Interval, Sun ... Sat` and a row per interval of the day, with **Copy for Excel** (tab separated, header
  first, percent signs dropped) and **Download (Excel)**. Actuals can be pasted in the same layout (one week, one channel, with an optional second grid for handle time) or uploaded long
  (Date, Interval, Channel, Offered, AHT) as csv or xlsx.
- **Forecast:** type the contacts for the week (or press "Use the suggestion"); optional day totals; spread over days and intervals from the last 8 weeks (median shape, odd days left out and
  listed, thin weekdays flagged); saved per channel and week.
- **People needed** for programs counted by service level or volume weighted: Phone Erlang C, Chat Erlang C with chats at once, Email workload; the requirement workbook (`FT Wise {n} Min`
  plus a tab per channel) is people needed on the floor (the engine adds shrinkage itself), laid out as the input sheet. Interval-compliance programs get no Erlang.
- **How we did:** offered over forecast per interval, day and week with a band (default 90 to 110 %, per channel), the trend over weeks, and for a day: contacts, people needed in the system, needed
  at actual calls (Erlang), on shift, on the floor, and a modelled service level (labelled as modelled).

## Checks
- 46 core tests, 13 store tests, 30 reading tests, 33 volume-book tests, 28 page tests (walls between programs and roles, check-then-save, forecast, downloads, hostile input), 5 browser tests
  (Copy puts the input sheet's layout on the clipboard and the grand total equals the typed total; opens at the first hour with volume; no sideways scroll at 768 and 360 px; 24 px targets).
- Route map re-pinned for the six new routes and the `volumes` extension (reason in the test); the sweeps of earlier phases (roles, walls, forms without a token, hostile queries, CSRF) cover the new
  routes automatically and pass.

## Not done, on purpose
- Erlang A (abandonment) and a service-level method for email; the ACD's own service level (the export has none).
- A forecast per interval typed by hand; holiday calendars (days can be left out of the shape only by the 25 % / 250 % rule today).
