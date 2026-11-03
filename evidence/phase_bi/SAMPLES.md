# Phase BI samples: volumes, forecast, Erlang, OTF (2026-11-03)

© 2026 Omar Mokhtar. All rights reserved.

Owner: "adding actuals as input for volumes received per channel if needed, forecasted volumes to calculate the OTF and see trends, give the count of calls for next
week and it calculates calls per interval, Erlang to calculate the needed associates per interval if the program is SL, interval-wise programs see trends only, how did we
do vs what was in the system vs what was required; be smart, be light." Answers: OTF is offered over forecast; the export has offered volume and AHT only; voice by Erlang C,
chat by concurrency, email by workload. Made-up "Program 01" numbers; nothing is built yet. Plan: `docs/superpowers/plans/2026-11-03-phase-bi-volumes-forecast-erlang.md`.

## Built and tested already (no page, no table)
`webapp/erlang.py` (Erlang C by recursion, service level, agents needed with an occupancy cap, chat concurrency, email workload; checked against the direct textbook formula) and
`webapp/forecast.py` (weekday and interval shape from the last eight weeks with holidays and named days left out, suggested week total with a range, a total spread over days and
intervals in whole numbers that add up, OTF and bands). 46 tests.

## Sample 1: Forecast and people needed (`samples/bi_forecast_dark.png`, `_light.png`)
Pick program, channel and week; type the calls expected (or press "Use the suggestion": 12,405, range 12,500 to 12,595 in the made-up data, from the trend of the last weeks). The
Days table shows each day's usual share and calls, and a box to type a day's calls (the rest share what is left). Below: one day interval by interval, with calls, Erlangs, people
needed on the floor, the figure with shrinkage, and the service level that staffing gives. A button downloads the requirement tabs (FT Wise and Phone) in the layout the input
workbook already uses. The FT Wise figure is the people needed on the floor; the engine adds shrinkage itself from the Shrinkage tab (checked in `webapp/day.py` and the engine).

## Sample 2: How did we do, a service-level program (`samples/bi_howdid_dark.png`, `_light.png`)
Offered over forecast for the week and the last eight weeks, by day with a reading (under, on target, over; 90 to 110 % unless you set another band), and for one day: calls forecast
against actual; four lines of people (needed in the system, needed at the calls that came, on shift, on the floor); and the service level the staffing would have given at the calls
that came. That last line is modelled (the export has no service level) and says so on the page; it falls steeply wherever the floor is below the need.

## Sample 3: How did we do, an interval-compliance program (`samples/bi_interval_dark.png`, `_light.png`)
Trends only, no Erlang: offered over forecast by week, and the busiest interval of each week against the system's requirement and the floor.

## Decisions I took, and what each costs if wrong
- A week's shape uses the median of the last eight weeks per weekday; a day under a quarter or over two and a half times the weekday's usual total is left out and listed (cost: a real
  campaign day is called odd; you can name days to leave out and the list shows what was dropped).
- A weekday with fewer than three usable weeks borrows part of its shape from the others and is flagged "thin".
- The suggestion is a robust trend line, damped by half, with a range from the spread; it never saves anything by itself.
- Erlang C assumes nobody abandons, so it over-staffs where callers do; an abandon-aware method is a later step if you want it.
- Chat: Erlang C on handle time divided by concurrency. Email: work arriving divided by the productive time one agent has in the interval.

## For you to answer
1. Do these three pages look right (one tab set under Insights, Actuals / Forecast and needs / How we did)?
2. Where does the program's channel mix come from: one forecast per channel typed by you (as drawn), or one total split by last weeks' channel share?
3. Actuals upload: one file per upload with Date, Interval start, Channel, Offered, AHT (seconds). OK?
