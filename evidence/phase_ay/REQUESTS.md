# Phase AY: the limit on breaks at once follows the gate mode (pre-registered rule)

© 2026 Omar Mokhtar. All rights reserved.

Owner, 2026-10-23, after a screenshot of an RTA day whose first breaks were 4 to 5 hours into the shift: "work on the website to
follow the shape as long as we have enough buffer in the intervals and ignore the cap".

## Facts (measured and read before any code)

- With no row in the Instructions sheet the engine uses 4 at a time and 30% of the people on shift (blank or empty cell: the same; 0 gives
  1 and 5%; 99 and 99% give 99 and 75%).
- The engine's Break Concurrency Gate Mode is Warn by default: an excess costs about as much as a missed target interval, so it goes over
  the limit only when that saves one. Fail makes it a hard constraint. Off lifts it.
- The website's planners ignored the mode: `break_plan.suggest` ranked "not above the limit" first, before the intervals' buffer and the
  usual shape; `channel_plan` made the limit a hard constraint.

## Change

The website reads `Break Concurrency Gate Mode` with the other break rules (`concurrency_mode`; a schedule whose rules were kept before this
has none and counts as Warn). Fail: the limit stays first in `suggest` and a hard constraint in `channel_plan`, as before. Warn and Off: the
limit does not decide where a break goes; the intervals' buffer, then the usual shape, then the engine's gap rules do.

## Accept the change only if all hold (test_day Wednesday, 29 people, with the limit at 4 and at 2, Arm A = Fail, Arm B = Warn)

1. People whose breaks are off the usual shape: B no more than A, at both limits, and the worst distance no larger.
2. The tightest interval (`min` of the floor's per-interval buffer): B no lower than A by more than 0.25 h.
3. Every break still keeps the engine's gaps and does not overlap (engine-rule distance 0 for everyone).
4. Fail gives the same plan as before the change.

## Result

Measured on test_day Wednesday (29 people), `webapp/tests/test_ay_cap_mode.py` pins it:

| Limit | Arm | People off the usual shape | Worst distance | Most on a break at once |
|---|---|---|---|---|
| 4 | A (Fail, as before) | 2 | 45 min | 4 |
| 4 | B (Warn or Off) | 1 | 15 min | 6 |
| 2 | A (Fail, as before) | 7 | 75 min | 6 |
| 2 | B (Warn or Off) | 1 | 15 min | 6 |

Rules 1 to 4 hold (the tests check the tightest interval within 0.25 h, engine-rule distance 0, and Fail unchanged): ACCEPTED.

## Bilingual counting by need (owner, 2026-10-23: "go for A, or it can be shown as per the actual requirements: if the bilingual is needed to cover English and not French, count them there as a whole 1 and 0 for French; if both need them, split")

Today a person counts in full in every language row their label can cover, so one bilingual agent counts twice in the same interval and can hide a gap.

**Rule (pre-registered, RTA day view only).** For each 5-minute slot, the people on the floor are spread over the language rows whose window is open:
1. A person whose label serves one open row counts there (1).
2. A person whose label serves several open rows is given, one person at a time, to the row that is furthest below its minimum. Rows tied for furthest below share the person equally (½ and ½, or ⅓ each).
3. When no row they serve is below its minimum, the person is split equally over the rows they serve.
4. Labels with fewer rows are spread first, then by name, so the result does not depend on the order people are listed in.
5. A person is counted once in total: the counts of all rows add up to the people who serve an open row.
A row's count for an interval is its lowest count over the interval's 5-minute slots, as before; a count that is not whole shows with up to 2 decimals.

**Not changed:** the engine, the validator and the workbook (no new row), so no baseline workbook or result moves; Fix breaks, Rescue and the other RTA tools still check a break against the earlier, wider count. The RTA page can therefore show a language gap the validator does not report; that is the point.

**Checks:** (1) one bilingual needed by English only counts 1 in English and 0 in French; (2) both rows short by the same amount: ½ each; (3) nobody short: split equally; (4) a label serving one row behaves as before; (5) the counts add up to the people; (6) the order of people does not change the result.

## Channel consistency tick (owner, 2026-10-23: "make channel planning more consistent and avoid multiple changes in channel for the same associate during the day, optional like a tick")

**Rule (pre-registered, channel planner only).** A new setting `consistent` (Channel Setup row "Keep each person on the same channel through the day", and a tick on the Plan channels page that overrides it for that Suggest). Default off.
1. Off: the plan is exactly what it was.
2. On: a change of channel costs 20 per quarter hour changed, also across a break or lunch (a change at a break was free). This is below every shortfall cost (a language 200, a channel 30 to 100), so coverage and language minimums still come first; the tick only chooses between plans that cover alike.
3. Measured by `score_day()["moves"]` (channel changes per person over the day, breaks ignored): on must have at least 25% fewer moves than off on the 16-person test day (the timed search moves by 1 or 2 between runs), with hours short per channel and language not worse than off by more than 0.5 h in total.
Not changed: the engine, the validator, the workbooks.
4. (owner, same day: "consistent is to stay on the same channel for a couple of hours, not chat for an hour, back to voice for an hour, back to chat") With the tick on, a stretch on one channel (breaks do not end it) that lasts under 2 hours and is followed by another channel costs 15 more. Measured by `score_day()["short_stretches"]`: on must have at most 60% of off's. Measured on the 16-person day: 16 short stretches off, 6 on; channel changes 34 and 20; hours short unchanged.
