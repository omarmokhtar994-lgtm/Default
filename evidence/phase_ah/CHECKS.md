# Phase AH: checks (2026-10-15, Egypt time)

© 2026 Omar Mokhtar. All rights reserved.

Built from the approved sample (`SAMPLES.md`, `samples/`), the owner's answers of 2026-10-15 and the plan
`docs/superpowers/plans/2026-10-15-phase-ah-build.md`. The engine is not touched.

## What was built

- **One rule for an interval's standing** (`day.band`, `day.at_target`): 100% or more teal, from the week's target to
  99% amber, below the target red. An amber interval under 10 person-minutes over the target is marked tight (a
  dashed ring), counted from the page's 5-minute ticks. The count of intervals at the target is unchanged (owner:
  "at target, marked tight").
- **On every page that colours intervals:** the Weeks grid, the run and Home walls, the plan-breaks strip, the RTA's
  timeline, achievement strip, interval board (Below the target / Under 100% or Tight / Good buffer or Covered),
  Now panel, Rescue strip, wallboard, Overview, the day in another zone and the handover. Legends name the week's
  own target instead of 90%.
- **Hours needed** on the Weeks page (sample ah01): intervals by day, hours to 100% or (the RTA's drop-down) to the
  target with 10 minutes over it, rounded up to the quarter hour; Day off / OT tags; filter; as recorded on the RTA
  or as planned; totals; what to do per day with names. **Download this table** gives the same table and colours in
  Excel with the suggestions on a second sheet (sample ah02).
- **The Schedules page** says, for the schedule in use, how many intervals are at the target as the RTA records them;
  the schedule file is never changed by the RTA's records.
- **Rescue the day** aims for the most intervals at the target, then the most with 10 minutes over it, then the
  fewest given up and moved. **Fix breaks** keeps its aim (the weakest interval first), then the most intervals with
  10 minutes over the target, then the hours short.

## Rulings (each says what it costs if wrong)

- The 10 minutes are person-minutes per interval over target x demand (the owner's "91% ... 2-3 mins" is per
  interval); at 100% an interval is never tight. Cost: a per-hour reading would change `CUSHION`'s use in one place.
- Hours needed round up to the quarter hour, so a short interval never shows 0 h. Cost: the sample rounded to the
  nearest quarter.
- Rescue never trades an interval at the target for 10 minutes elsewhere (at the target ranks first). Cost: one
  weight order.
- What to do covers today (shifts still ahead) and the days to come; past days show figures only.
- "As planned" leaves out the RTA's attendance, break moves and activities; channel moves still count.
- The program page's and run page's "at 90% or more" counts are the validator's own metric and stay as they are.

## Results

- New tests: test_ah_rule 7, test_ah_colours 8, test_ah_cushion 4, test_ah_needed 11: all pass. Each was watched
  failing first (missing function, old rule, or `no gain` from the old Rescue).
- Re-pinned, each saying why in the test: test_ag_rta (the Now panel says below the target / at the target),
  test_ui_playwright.test_rendered_pairs_pass_in_both_looks (its week set to 90%: the workbook's own 100% has no
  amber band). test_attendance passes the week's target to `board`.
- Found by the suite and fixed: the Week page lost its target panel's figures (a reused name, 869a196).
- Rescue the day and Fix breaks, re-checked on two fixture weeks (as they are, 8 and 14 more people sick, and at
  13:07): no rule broken (fewer at the target, more given up, below 50%, new language or channel gaps, a break
  outside its shift or moved into the past). Review week, Saturday with 6 sick, target 90%, as (at the target, with
  10 minutes over it, tightest hours, hours short):
  - before (19, 19, -1.75, 6.25);
  - Fix breaks (22, 21, -1.25, 5.33): before Phase AH it reached 20 at the target;
  - Rescue (23, 23, -1.75, 5.25).
  Friday: Fix breaks (24, 23), Rescue (24, 24), from (23, 23).
- Browser (Playwright, review server with people sick on Thu, Fri and Sat): Weeks (night, day, 360 px phone with no
  sideways scroll after the drop-down was allowed to shrink), RTA strip and legend, board, Rescue, Fix breaks,
  Schedules, handover, the export downloaded and read back. No console errors. Screens in `screens/`.
- The Weeks page with the table takes 0.8 to 1.0 s on the test week (seven day pages and three days' plans).
- Full website suite, Thu 15 Oct 03:20 to 03:55: 1079 tests, 10 failures, 2 errors, 1 skipped:
  - the contrast test above (fixed in 26ec013; its class re-run green, 15 tests);
  - 9 in test_channel_day and 2 browser tests (bulk change, Phase V screens) fail the same way on 5c46cd3, before
    this phase: not this phase's.
- The browser tests rewrite the old phases' screenshots; those files were restored before packaging.
