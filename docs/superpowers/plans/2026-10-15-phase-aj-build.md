# Phase AJ: overtime up to 4 hours, and cover from outside the roster. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overtime before or after a shift up to 4 hours (the bug the owner hit), and a way to record a team manager
or support member who is not on the roster logging in to cover intervals, counted in the interval figures.

**Spec:** `evidence/phase_aj/REQUESTS.md` (the owner's words, the root cause, the answers).

## Global constraints

CLAUDE.md: engine untouched, failing test first, re-pin only for an owner-changed contract (say why), strict CSP,
sentence case, "Associate NN" names in fixtures, copyright line in every website file, Egypt time, push to the
session's branch only.

## Tasks

| # | Task | Files | Test |
| --- | --- | --- | --- |
| T1 | Overtime cap 4 h (`OVERTIME_MAX = 240`); notes say 4 hours; the + Add default reaches 4 h | day.py, app.py, day.html | test_aj_overtime; re-pins in test_attendance, test_day, test_add_overtime_default |
| T2 | Cover records: table `outside_cover` (typed name, role, from, to, channel), in the day's journal (Undo), the day clean-up and program rename | store.py | test_aj_cover |
| T3 | DayBook `add_cover` / `cancel_cover`: checks, day log, group post (kind "overtime"), Undo lines | attendance.py, notify.py | test_aj_cover |
| T4 | Counted in the intervals: `day_view(cover=...)` adds each person to every 5 minutes they cover (yesterday's late part too); the cell says how many; channels count them on the channel picked | day.py, channel_day.py, attendance.py | test_aj_cover |
| T5 | RTA: a "Cover from outside the roster" panel on the Overtime and VTO tab (name, role, from, to, channel, post tick), listed with Delete; times in the zone shown | app.py, day.html | test_aj_cover |
| T6 | Exports: "Cover from outside the roster" is a tick: ticked, its own sheet and their minutes counted in the Daily summary; unticked, the export is the roster alone | exports.py | test_aj_cover |
| T7 | Checks, package, report | evidence | CHECKS |

## Rulings while building (each with what it costs if wrong)

- T1: the owner did not answer the cap at first; after "raise it to the options we do have" the cap is 4 h, the
  longest + Add length, everywhere overtime is offered (+ Add, the Overtime and VTO tab, the board's cover panel).
  Cost: one constant.
- T3: roles are "Team manager" and "Support" (the owner's "TM or support"). A cover is 5-minute steps, at most 12 hours,
  may run past midnight, and one name cannot cover two overlapping stretches. Cost: one list and one number.
- T3: group posts go under "Overtime and VTO" (renamed "Overtime, VTO and cover"), so groups that post overtime post
  cover without anyone ticking a new box. Cost: a new kind if the owner wants them apart.
- T4: cover counts as one person on the floor, never for a language rule (their language is not known), and is not
  in the plan, adherence, worked hours or shrinkage (they are not on the roster). Cost: a language field.
- T6: the owner's "check box to include them or not" is read as the export's tick; the RTA always counts them (answer
  b). Cost: a tick on the RTA too if the owner meant the live page.
- T6: "Changes recorded" in the Daily summary counts every change made on the RTA that day, a cover included, ticked
  or not (it is the day's audit count, not a staffing figure). Cost: one filter on the day log.
- T4: the board names a cover in the interval it starts ("support from outside the roster, covering 10:00 to 12:00");
  the Timeline has no bar for them (they are not on the roster). Cost: a lane of their own if the owner wants one.
- Item 3 (added by the owner while building): the next day's view carries last night's channel stretches after
  midnight; the Channels tab's "Who" list for a channel change still names only that day's own shifts, so a change
  is never offered for someone whose shift belongs to the day before. Cost: one list.
- Samples: none were made first. The cover panel uses the existing form styles of the RTA (the Find a time form), so
  nothing new was designed; screens are in `evidence/phase_aj/screens`. Cost: a restyle if the owner wants it otherwise.
- Item 4: the languages offered are the day's language rules and the channels' language rules; "None of these" keeps
  a cover out of every language row. Cost: a free-typed language if the owner wants one not in the rules.
- Item 5: only overtime warns instead of refusing; a day off cancelled (called in) still keeps the rest gap, and the
  overtime offers on the board and the Overtime and VTO tab still list only people within it (they are suggestions).
  The warning is in the day's log line; the group post stays as before. Cost: one rule each if the owner wants them
  the same way.
