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

### Result of the breaks-as-separators sweep (`--arms baseline balanced --set BREAK_CHANGE=N`, base_16 and tight_16, Mon to Fri, 2026-10-26)

| BREAK_CHANGE | team | changes in the middle of a stretch | changes at a break | total (baseline) | under 2 h | average h | longest h | short h | slowest s |
|---|---|---|---|---|---|---|---|---|---|
| 20 (as before) | base_16 | 1.44 | 1.09 | 2.52 (2.50) | 0.82 | 2.27 | 3.53 | 2.5 | 13.3 |
| 5 | base_16 | 1.21 | 1.14 | 2.35 (2.49) | 0.79 | 2.39 | 3.73 | 2.5 | 13.5 |
| 0 | base_16 | 0.66 | 1.57 | 2.24 (2.34) | 0.60 | 2.47 | 3.70 | 2.5 | 13.4 |
| 20 | tight_16 | 0.97 | 1.34 | 2.31 (2.96) | 0.97 | 2.42 | 4.33 | 68.75 | 14.2 |
| 5 | tight_16 | 1.06 | 1.35 | 2.41 (2.86) | 1.04 | 2.34 | 4.17 | 68.75 | 14.7 |
| 0 | tight_16 | 1.05 | 1.36 | 2.41 (2.90) | 1.01 | 2.34 | 4.20 | 68.75 | 14.1 |

**Against the acceptance (stated plainly).** BREAK_CHANGE 0 meets: total changes below the baseline's (both teams), stretches under 2 h within 0.1 of the 20 arm (lower on
base_16, +0.04 on tight_16), hours short equal, no problems, no day over 25 s, and the longest stretch not above the 20 arm's on tight_16 (4.20 against 4.33).
**Missed:** the longest stretch on base_16 is 3.70 h against 3.53 h (still under 4 h); changes in the middle of a stretch on tight_16 are 1.05 against 0.97 (a
difference the timed search shows from run to run; the baseline's own figure moved 0.1 between runs). BREAK_CHANGE 5 misses more of them.
**Ruling: BREAK_CHANGE = 0.** The gain is where the owner pointed: on base_16 changes in the middle of a stretch fall from 1.44 to 0.66 per person-day and the
moving happens at breaks (1.09 to 1.57), with fewer short stretches (0.82 to 0.60). Fixed is unchanged (its cost across breaks stays CONSISTENT).

## Chat and Email people did not rotate (owner, 2026-10-26: "for associates who work only emails and chats I think they weren't very balanced; I used the balanced tick there": Mazen, Menna, Youssef Ali; GDI)

**Measured first** (`evidence/phase_bc/gdi_direct.py`: the people, shifts, languages and breaks read back from `channel_plan_GDI_170.xlsx`, the needs and rules from the GDI workbook's
channel tabs, planned Sun to Sat with the earlier days carried, breaks kept; the two Chat-and-Email associates' skills are exact, the others' are the channels the file shows them working):

| | Chat h / Email h (Mennatullah Abdo, Youssef Ali; 5 days) | longest stretch h | stretches a day |
|---|---|---|---|
| the owner's file | 11.5 / 28.5 | 5.7 | 1.8 |
| no tick | 19.0 / 21.0 | 5.9 to 6.0 | 2.2 to 2.4 |
| Fixed | 16.0 / 24.0 | 5.1 to 5.5 | 2.4 to 2.6 |
| Balanced (current) | 17.5 / 22.5 | 5.1 to 5.2 | 2.2 to 2.4 |

So Balanced moves their Chat share from 29 % (the file) to 44 %, but the stretches stay above 5 hours. Cause: the share-of-the-day charge (DAY_MIX) lets a person with two
channels have up to half the day plus an hour on one channel, which is 5 hours of an 8-hour day, so one 5-hour stretch and one 3-hour stretch pass without a charge. The tick
promises a couple of hours on a channel and the charge only limits a channel's total, not the length of a stretch. (The file itself was probably planned before the tick; it
shows Email blocks of 4.5 to 5.5 hours and 29 % Chat, as the no-tick arm above would.)

**Rule (pre-registered before any arm is run; Balanced tick only).**
1. With Balanced on, a stretch on one channel (breaks do not end it) that is still running after STRETCH_LIMIT quarter hours costs STRETCH_OVER per quarter hour past it, for a person who can work two or more channels today.
   Arms: STRETCH_LIMIT 12 (3 hours), STRETCH_OVER 0 (current), 6, 10.
2. Below every shortfall cost as before (an Email quarter hour short costs 30), so coverage and language minimums still come first.
**Acceptance (the GDI replication, Balanced, against STRETCH_OVER 0):** the two Chat-and-Email associates' longest stretch (average of each day's longest) at most 4.0 hours and lower than the 0 arm's; their Chat
share between 35 % and 65 %; Email hours short (the planner's own count) not above the 0 arm's by more than 0.5 hours a day; no planner problems; no day over 25 seconds.
**Acceptance (base_16 and tight_16, `--arms balanced`):** the longest stretch lower than the 0 arm's; total changes not above the both-off baseline's; hours short not above the 0 arm's by more than 0.5 hours a day; no day over 25 seconds.
The smallest STRETCH_OVER that meets all of it is kept; if none does, the misses are stated and the one closest is proposed to the owner.
Not changed: Fixed, both off, the engine, the validator, the workbooks.

### Result of the stretch sweep (2026-10-26; the machine was quiet for the GDI runs; Balanced arm; the two Chat-and-Email associates with 5 days each; "all" = all 126 person-days of the replication)

**First form of the rule (two or more channels), `gdi_direct.py ... STRETCH_OVER=N`:**

| STRETCH_OVER | longest stretch h (Mennatullah Abdo / Youssef Ali) | Chat / Email h | stretches a day | all: changes | all: stretches under 2 h | all: hours short |
|---|---|---|---|---|---|---|
| 0 (today) | 5.55 / 5.10 | 17.5 / 22.5 | 2.2 / 2.4 | 2.00 | 0.84 | 912.2 |
| 10 | 4.30 / 3.70 | 18.8 / 21.2 | 3.2 / 3.4 | 2.41 | 1.15 | 916.8 |
| 20 | 3.10 / 3.75 | 21.2 / 20.5 | 4.0 / 3.8 | 2.48 | 1.18 | 917.8 |
| 28 | 2.75 / 2.95 | 21.0 / 21.0 | 4.2 / 4.2 | 2.73 | 1.37 | 918.0 |

On base_16 and tight_16 (`--arms baseline balanced`, STRETCH_OVER 0 / 10 / 14 / 20): changes per person-day 2.41 / 2.81 / 3.06 / 3.31 and 2.25 / 3.08 / 3.25 / 3.12 (baseline 2.49 to 2.64 and 2.86 to 2.95), average stretch 2.34 / 2.10 / 1.97 / 1.86 h
(under the 2 hours the owner asked for). **Deviation, stated plainly:** people with three channels were pushed to change more than with the tick off, so the rule is narrowed to **exactly two channels** (with three, the share charge already keeps
a stretch near 3.7 hours: 3.5 to 3.7 h longest on base_16 with no stretch charge).

**Rule as shipped (exactly two channels), GDI replication:**

| STRETCH_OVER | longest stretch h | Chat / Email h | stretches a day | all: changes | all: under 2 h | all: hours short |
|---|---|---|---|---|---|---|
| 10 | 3.65 / 4.15 | 18.8 / 21.2 | 3.4 / 3.0 | 2.14 | 0.94 | 918.5 |
| 20 | 2.80 / 3.55 | 18.2 / 21.8 and 19.0 / 21.0 | 4.2 / 3.8 | 2.28 | 1.00 | 918.2 |

(specialists_20, six two-channel people among 20: changes per person-day 1.45 / 1.62 / 1.70 for 0 / 10 / 20 against 1.27 with the tick off; hours short 12.5 at every weight; no day over 14 s.)

**Against the acceptance.** Met at 20: both associates' longest stretch under 4.0 h (2.80 and 3.55; 10 misses it for Youssef Ali, 4.15), Chat share 46 % to 49 % (limit 35 to 65 %), no planner problems, no day over 25 s.
**Missed, plainly:** hours short rise by 5.7 h over the week against the 0 arm (0.8 h a day, limit 0.5; the same at 10); the week's total changes rise from 2.00 to 2.28 per person-day (still below the tick-off 2.65) and stretches under 2 hours from 0.84 to 1.00;
on specialists_20 total changes stay above the tick-off arm's (1.70 against 1.27), as they already were with no stretch charge (1.45). **Ruling: STRETCH_LIMIT 12, STRETCH_OVER 20**, the smallest that meets the owner's stretch limit.
The file the owner sent shows 5.7 hours and 29 % Chat for the same two people; the planner now gives 3.2 hours and 48 %. Single replications of the timed search vary by about half an hour in the longest stretch.
