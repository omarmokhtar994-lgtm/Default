# Phase AF: checks (2026-10-14, Egypt time)

Built from `evidence/phase_af/OWNER_NOTES.md` (sections A to F and "Samples answered") and the plan
`docs/superpowers/plans/2026-10-14-phase-af-build.md`. Nothing that existed was removed. The engine is not touched.

## What was built

| Item | Commit | Where |
| --- | --- | --- |
| X1-X3, A2: language rows, one row per language, overnight Email Hours, break edges | b589b25 | day, channels, break_plan |
| A1: channel grids of 15, 30 or 60 minutes for any interval | 03738e2 | channels |
| A3: Channel Setup drop-downs, 20 rows, windows inside coverage | 3a1d794 | channel_template, channels |
| B2, B3: no break while alone; no short stint before a break | a907913 | channel_plan |
| B1: Plan channels suggests every day in one action | 8ecf763 | app, channels.html |
| C2: each associate's channels on the RTA, as stretches | b417e59 | channel_day, day.html |
| C1: Plan channels as stretches (the quarter-hour table kept under "Show quarter hours") | 15b7ceb | channel_page, channels.html |
| C3: change a channel from the RTA, with a preview first | 99ca7b1 | attendance, app |
| C4: the channel plan download in two views (table and timeline) | 22fd29a | channel_export |
| D2-D4: what hovering shows; a dragged break asks "Change ... from Y to Z?" | 824a38e | day, app.js |
| D6: today at a glance | 1de8387 | day, day.html |
| E2, E3: Task and Public holiday statuses | 9b2bf27 | day, attendance, app.js |
| E1: shrinkage in office and out of office (Sutherland and client) | 548ad0f | shrinkage, store |
| F1, F2: Rescue the day proposes days off to cancel, then overtime | 0912f3a | day |
| F3, F4: absences known for later days; the rest of the week on Week | 591680c | attendance, week.html |
| Z1, Z2: the schedule's zone at upload; times in any zone; the operating day | d016926 | clock, week, day_zoned.html |
| Browser check fixes ("all day", one-row forms) and screens | b03b5cd | screens/ |

## Rulings made while building (each says what it costs if wrong)

- **E1:** the mapping is kept per program key in its own table, because program options feed engine runs. Admins
  and supervisors edit it from the RTA. Late and Left early are not in it (not in the approved sample). A called-in
  day off counts as scheduled. Cost if wrong: one row or one count.
- **F1:** the website has no days-in-a-row or weekly-hours setting. The engine's contract is 2 days off a week (3 for
  11-hour shifts). Bends are said as measured facts: rest below the workbook's rest gap, fewer days off left than
  the week has, 6 or more days in a row. Cost if wrong: one wording or one limit.
- **F3, F4:** the outlook sits on Week (F4 "perhaps on Week") and lists the days after today. Absences are entered
  from the RTA (owner: "Enter on the RTA").
- **Z2:** the RTA in another zone, or as the operating day, is read only: who is on and every interval, from one
  window stitched from the schedule's days. Every change stays on the schedule's own day, linked from the page. The
  operating day shows a full 24 hours from its start. Offsets are taken at noon of the date shown; every listed zone
  has a whole-hour offset.

## Deferred

- Making every RTA tab and form work in another zone (Z2 shows timeline and intervals read only).
- Moving the outlook to Overview as well (F4 left it open).

## Tests

New test files: test_af_language_rows, test_af_break_edges, test_af_email_overnight, test_af_channel_grids,
test_af_channel_setup, test_af_planner_rules, test_af_hover, test_af_glance, test_af_statuses, test_af_shrinkage,
test_af_dayoff, test_af_outlook, test_af_zones. Each failed first for the reason it names, then passed.

## Browser check (review server, 1366 px, both looks)

Screens in `screens/` (af10 to af19). No console errors or CSP reports besides the sandbox's refused certificate
for Google Fonts. Pages load in 0.8 to 2.0 s; the slowest is Rescue the day on a later day (about 2 s), which now
also works out the day-off proposals.

## Results

(filled in below after the full suite and the release gate)
