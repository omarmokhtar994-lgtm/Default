# Phase Z diagnosis, 2026-10-10 Egypt time

Owner, after installing Phase XY:

> The part of multiple schedules for same week this is very very confusing now and i cant find the one was not used
> lol and strange things
>
> Associates channels found but i cannot find where i can add the required per channel and where can it run lol
>
> Cant find any where in timeline or interval board todays achievement as discussed ?

Reproduced on the review server (made-up "Associate NN" data): SAKS, NMG Tier 2, week of Sun 04 Oct, with the first
upload (`week.xlsx`, breaks planned automatically, in use) and a second ready upload for the same week
(`week41_NMG_v2.xlsx`, not in use). Nothing in the website was changed for this diagnosis.

## 1. Two schedules for one week: each page shows a different one, none shows both

| Where | Shows | Why (code) |
| --- | --- | --- |
| Menu, Schedules | only `week41_NMG_v2.xlsx` (not in use), titled "week of 04 Oct: schedules" | `schedules_for` redirects to the newest run of the program (`app.py:1735`); there is no list of a week's schedules |
| That Schedules page | never says another schedule is in use this week | `schedules.html` only knows its own run |
| Week page | "This week also has week41_NMG_v2.xlsx (not in use). Compare or switch" | the link opens the schedule already in use (`week.html:11`), so the other one cannot be reached from here |
| Home, "Latest schedule" panel | `week41_NMG_v2.xlsx` (the newest, not in use) | newest run, not the schedule in use |
| Home, Runs table | both runs, neither marked in use | the table has no in-use column |
| RTA, Overview, Analysis | the schedule in use (`week.xlsx`) | they follow the in-use rule (Phase W) |

So the menu and Home show the schedule that is not used, while the RTA, Week and Analysis use the other one, and the
only link to "compare or switch" leads back to the one already in use.

Strange wording on an uploaded schedule's page: "No changes: this is the tool's schedule." and "Already in the
tool's schedule (188)". An upload is the planner's own schedule, not the tool's. "168 of 168 intervals fully covered
after breaks" shows on a version that has no breaks yet.

## 2. Channel needs: there is nowhere to type them

- The site reads channel needs only from tabs in the input workbook: `Chat 30 Min`, `Phone 30 Min`, `Email 30 Min`
  (or 60 / 15), `Email Hours` and `Channel Setup` (`webapp/channels.py`).
- The two workbooks offered on Home, "Blank input workbook" and "filled example", have none of these tabs
  (`webapp/workbooks/*.xlsx`; their builder `tools/build_web_workbooks.py` predates Phase V).
- "Plan channels" appears on the Schedules page only for a schedule whose workbook had those tabs
  (`schedules.html:37`), so without them nothing on the site points to it.
- The Associate channels page says who can work which channel, but not where the needs go or where planning runs.
- Getting needs in today means re-uploading the whole schedule with the tabs, which adds one more schedule for the
  same week (problem 1).

## 3. Today's achievement: it exists but does not read as one

- The count the owner asked for ("count of intervals above 90% or the chosen target / total intervals") is on the
  RTA: "Intervals at 100% or more 24 of 24 (100%), plan 24 of 24" (`_target_tile.html`).
- It is one plain line in the summary strip above the tabs, the same size as "On shift today", and it never says
  "achievement" or "compliance".
- Interval board: no per-interval achievement at all.
- Timeline: the per-interval "Achieved (target 100%)" row is under every person's lane (31 lanes here), so it is
  off screen unless you scroll to the bottom.

Screens: `scratchpad` captures `01_home` to `07_channels_setup` (review server, night look, 1440 px).

## 4. More strange things found while checking (owner: "check rest of my comments above")

- Run pages never say whether that schedule is in use, and the in-use run still says "Plan the week's breaks next"
  after its breaks were planned (Version 2).
- Every automatically planned break is logged as its own change, each tagged "warning" (184 lines), because the
  save's one warning is copied onto every line.
- The week view of a version that is not in use has the same title as the week in use and does not say it is not
  used.
- Home's "Latest schedule" panel and its Runs table cover every program, although Home otherwise shows only the
  program picked on the left (Phase R).
- Analysis for a program whose schedules were all uploaded ready says "No analysis yet" and lists the uploads
  without saying which one is in use. Analysis from uploaded schedules is a new feature, so it is offered for
  later rather than built in this phase.
