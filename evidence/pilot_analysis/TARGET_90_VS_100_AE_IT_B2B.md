# AE IT B2B pilot: target 90% vs 100% (2026-10-05)

Inputs: `AE_IT_B2B_WEEKLY_INPUT - Copy - Copy - Copy2.xlsx`, two versions (sha 5a3fb2d5 = target 100%,
sha 6f2cf2c9 = target 90%). Parsed with the engine: the ONLY difference is `target_ratio`. 13 associates,
410 FTE weekly demand, 60-minute grid, 8 legal shifts, QUICK, 2 seeds each, package `a3fc3ab2` (pre-F-37,
so the runs reported exit 1; every seed had a validated schedule).

Same yardstick for all (independent validator interval rows, after breaks, 112 active intervals):

| Workbook | Schedule | >=100% | >=90% | >=80% | <70% | FTE short of demand | FTE over demand |
|---|---|---|---|---|---|---|---|
| T100 | published s9000 / s9001 | 87 / 88 | 92 / 91 | 96 / 95 | 14 / 15 | 45.3 / 46.5 | 52.9 / 54.1 |
| T100 | MAX_FLOOR alternative s9000 / s9001 | 45 / 46 | 74 / 74 | 109 / 107 | 0 / 1 | 34.6 / 34.8 | |
| T90 | published s9000 / s9001 | 39 / 43 | 82 / 90 | 106 / 103 | 1 / 3 | 35.6 / 33.9 | 43.2 / 41.5 |

Staffed effective FTE is 417.6 in every schedule: the roster is the same, only the placement differs.
Engine capacity check: "Capacity-ample: 54 spare productive hours on 410 needed (13% headroom)".

Why: selection is lexicographic on the count of intervals at target, then floor. An interval at 95% is
worth the same as one at 40% when the target is 100%, so the search buys one more fully covered interval
with unlimited depth elsewhere (14-15 intervals below 70%, FLOOR_GAP_RATIO_EXCEEDED 17, 6 consecutive).
At 90% the same people reach the bar in more intervals and the leftover spreads, so deep holes nearly
vanish and total shortfall drops by about 11 FTE. Not a bug: the engine optimises the stated target.
The 100% run did produce the no-deep-holes schedule (MAX_FLOOR), validated, and ranked it second.

Both versions still miss about 34 FTE while overstaffing about 42 FTE elsewhere: with 8 legal shifts on a
60-minute grid the shift shapes cannot follow the demand curve (a shift-library question, not headcount).

The third workbook (`... - Copy - Copy - Copy.xlsx`, sha 85955a0e) was refused before solving:
HARD_DUPLICATE_EMPLOYEE_ID 716522 on rows 11 and 14.
