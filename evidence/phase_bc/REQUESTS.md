# Phase BC: channel consistency that rotates (owner, 2026-10-26)

Owner: "When I chose keep each person on the same channel in channel assignment it didn't change the channel per day instead it kept a fixed
one for each associate kinda, yet my request was to balance, if you remember, keep it for 2-3 hours and avoid a lot of changes in and out
from channels."

## What was measured first (before any change; `evidence/phase_bc/stretches.py base_16`, 16 made-up people, Mon to Fri, fair off)

| Setting | Channels per person-day | Average stretch | Longest stretch (average of each day's longest) | Same main channel as the day before |
|---|---|---|---|---|
| Both off | 2.51 | 2.24 h | 3.64 h | 55% |
| Tick on (what the owner chose) | 2.23 | 3.20 h | 4.95 h | 78% |
| Fair + tick | 2.66 | 2.44 h | 3.85 h | 44% |

Cause: the tick prices a change of channel (CONSISTENT 20) and a stretch under 2 hours (STRETCH_COST 22), and nothing prices a stretch that
runs on too long, so the cheapest plan is one channel for most of the day, and the same one the next day (the week's fair spread is a separate
setting, off by default, and the tick does not turn it on). The rule meant "a couple of hours on a channel, then another", not "one channel".

## Rule (pre-registered before the first measured arm; channel planner only, only with the tick on; tick off must give the plan it gave before)

1. With the tick on, a person who can work two or more channels today is charged DAY_MIX per quarter hour on one channel beyond a share of the day:
   the cap is their quarter hours on a channel (count of working quarters) divided by their number of channels, plus DAY_SLACK (4) quarter hours.
   Single-channel people are not charged. Below every shortfall cost, so coverage and language minimums still come first.
2. DAY_MIX is chosen from {4, 8, 12} by sweeping two teams (base_16, tight_16); the middle one that meets the acceptance is kept.
3. Measured by `score_day()["stretch_minutes"]` (every stretch on one channel, breaks do not end it) over 7 made-up teams, Mon to Fri, tick on,
   fair off, against the same arm without the new term.

**Acceptance (every scenario):**
- average stretch between 2.0 and 3.0 hours (was 3.2 on base_16);
- the longest stretch (average per person-day) at most 4.0 hours (was 4.95);
- stretches under 2 hours per person-day at most 1.15 times the tick-only arm's;
- channel changes per person-day not above the baseline's (both off);
- hours short not above the tick-only arm's by more than 0.5 h a day; no planner problems; no day over 25 s.
Reported, not gated: same main channel as the day before; the fair spread.
Not changed: the engine, the validator, the workbooks, tick off.

## Sweep result (tick on, fair off, Mon to Fri, `tools/channel_scenarios.py --arms baseline tick --set DAY_MIX=N`; made-up teams; 2026-10-26)

| DAY_MIX | team | changes per person-day (baseline 2.56 / 2.92) | stretches under 2 h per person-day | average stretch h | longest stretch h | hours short | slowest day s |
|---|---|---|---|---|---|---|---|
| 0 (no term) | base_16 | 1.80 | 0.65 | 2.86 | 4.81 | 2.5 | 14.2 |
| 4 | base_16 | 2.39 | 0.79 | 2.36 | 3.95 | 2.5 | 14.5 |
| 8 | base_16 | 2.36 | 0.85 | 2.38 | 3.87 | 2.5 | 14.6 |
| 12 | base_16 | 2.45 | 0.76 | 2.32 | 3.84 | 2.5 | 16.4 |
| 0 (no term) | tight_16 | 2.17 | 0.96 | 2.52 | 4.71 | 69.75 | 14.2 |
| 4 | tight_16 | 2.29 | 1.00 | 2.43 | 4.44 | 68.75 | 14.5 |
| 8 | tight_16 | 2.29 | 0.99 | 2.43 | 4.40 | 68.75 | 14.5 |
| 12 | tight_16 | 2.46 | 1.18 | 2.31 | 4.24 | 68.75 | 14.4 |

**Against the acceptance (stated plainly).** Met at every weight: average stretch between 2.0 and 3.0 h; changes not above the baseline's; hours short not
above the tick-only arm's; no planner problems; no day over 25 s. **Missed at every weight:** the longest stretch is at most 4.0 h only on base_16
(3.95, 3.87, 3.84), not on tight_16 (4.44, 4.40, 4.24: a tight team has no one free to rotate to); stretches under 2 h per person-day are above 1.15 times
the tick-only arm's (0.65 x 1.15 = 0.75) on base_16 at every weight (0.79, 0.85, 0.76) and on tight_16 at 12 (1.18 against 1.10).
**Ruling: DAY_MIX = 8** (the middle one; 12 costs most on the tight team, 4 keeps the longest stretch longer). The cost, plainly: the tick's
calm shrinks. Against the tick-only arm, changes per person-day go from 1.8 to 2.4 on base_16 (the baseline, tick off, is 2.6) and stretches under 2 h from 0.65 to 0.85
(baseline 1.2). The tick still changes channel less often than off, but only by about 9 % instead of 30 %. The owner chose rotation over calm:
"keep it for 2-3 hours" beside "avoid a lot of changes". If more calm is wanted, lower DAY_MIX (4 or 0); the tick alone already existed.
Fair spread is not part of this change: it stays its own setting, and "Fair + tick" is the one that also changes the main channel from day to day.

## Two ticks (owner, 2026-10-26: "make the 2 modules for channel if we need fixed as much as possible or the balanced one, with 2 different ticks")

Both are measured configurations from the sweep above, so nothing new is tuned:
- **Fixed** (`consistent`, Channel Setup row "Keep each person on the same channel through the day", Plan channels tick "Keep each person on one channel as much as possible"): the Phase AY tick as it was, the DAY_MIX = 0 arm of the sweep (changes per person-day 1.80, stretches under 2 h 0.65, longest stretch 4.81 h on base_16).
- **Balanced** (`balanced`, Channel Setup row "Balance each person's channels through the day", Plan channels tick "Balance channels: a couple of hours on one, then another"): the same costs plus DAY_MIX = 8 (changes 2.36, under 2 h 0.85, longest 3.87 h on base_16).
- Both ticked (page or tab): Balanced is used (it contains Fixed's calm). Both off: the plan is exactly what it was. An old workbook without the new row reads as Balanced off.
- `tools/channel_scenarios.py --arms balanced fair+balanced` measures the new arms next to `tick` and `fair+tick`.

## Breaks as separators (owner, 2026-10-26: "one issue, I think it considers a break as a separator, that's why it kept associates the whole day on the same channel")

**Measured first (`evidence/phase_bc/where_changes.py base_16`, fair off, Mon to Fri; changes per person-day, in the middle of a stretch / at a break or lunch):**
both ticks off 0.59 / 2.09; Fixed 0.79 / 0.64; Balanced 1.09 / 1.26. So with the tick off, three quarters of the changes happen at a break, which is the natural
place to move; the tick prices a change at a break exactly like one in the middle of a stretch (CONSISTENT 20 per quarter hour, "also across a break"),
which stops people moving at breaks and pushes the few changes that remain into the middle of stretches. The owner's reading is right.

**Rule (pre-registered before any arm is run; only the Balanced tick; Fixed keeps pricing breaks like the middle of a stretch, because "as fixed as possible" is its job).**
1. With Balanced on, a change of channel with a break or lunch between the two blocks costs BREAK_CHANGE per quarter hour instead of CONSISTENT. Arms: BREAK_CHANGE 20 (as now), 5, 0.
2. A change in the middle of a stretch keeps CONSISTENT (20) and the short-stretch charge.
3. The share-of-the-day charge (DAY_MIX 8) stays.
**Acceptance (base_16 and tight_16, Mon to Fri, `--arms balanced`, compared with the BREAK_CHANGE 20 arm):**
- changes in the middle of a stretch per person-day: lower than the 20 arm's (the owner's "avoid changes in and out");
- the longest stretch (breaks do not end it) not above the 20 arm's;
- stretches under 2 hours per person-day not above the 20 arm's by more than 0.1;
- total changes per person-day not above the both-off baseline's;
- hours short not above the 20 arm's by more than 0.5 h a day; no planner problems; no day over 25 s.
The middle arm that meets all of it is kept; if only the 0 arm does, that one.
Not changed: Fixed, both off, the engine, the validator, the workbooks.
