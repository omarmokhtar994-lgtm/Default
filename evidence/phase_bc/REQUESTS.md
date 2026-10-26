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
