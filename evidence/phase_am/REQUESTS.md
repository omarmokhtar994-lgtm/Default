# Phase AM: the owner's requests

© 2026 Omar Mokhtar. All rights reserved.

Received Fri 16 Oct 2026, about 01:15 Egypt time, with two photos: the Weeks page's Hours needed table, and Home's Runs
list with "no data" under Covered.

## The owner's words

> Couple of notes for schedule rescheduling in RTA view should be a button such as fix breaks etc 1 click fix things,
>
> When changing timezone in schedules tab it's working fine now but not downloadable with the new timezone
>
> In weeks tab for As planned i dont have the option to choose after break or before break or a different version
>
> In this view and weeks and all views not showing percentage of intervals if it's only before breaks
>
> A it should show the percentage
> B in cas i pressed on plan breaks it should show the new percentage after breaks or as per my in use selection

## 1. One click to fix the day on the RTA (question)

What exists:
- "Rescue the day" and "Fix the day's breaks" each apply with one click, but they only move breaks.
- The day-off and overtime suggestions (Hours needed on Weeks, the RTA's Overtime and VTO tab) only list what to do
  and who could do it: "Cancel a day off, 16:00 to 01:00; possible: X, Y or Z", then overtime per interval. Applying
  one means typing it on the Overtime and VTO tab.

Questions:
1. **What does one click apply?**
   - (a) An "Apply" on each suggestion. One click records that day-off cancellation or overtime for the first
     person offered, with a preview first and Undo after.
   - (b) A "Fix the day" button that applies every suggestion for the day at once: days off cancelled first, then
     overtime. It shows the whole list first, then one Apply, then one Undo.
   - (c) Both (recommended).
2. **Who is picked** when several people could do it?
   - The first one offered: the most rest before the shift, then the fewest hours this week (recommended).
   - Or always ask the RTA to pick.
3. **Where:** on the RTA, as a tab next to Fix the day's breaks and Rescue the day (recommended), and/or from the
   Hours needed cells on Weeks?

## 2. Download in the zone picked (bug)

**Root cause:** the Download (.xlsx) link on a schedule (`schedules.html`) carries no zone. `schedule_download`
sends the stored workbook unchanged, always in the schedule's own zone.

**Fix (TDD):** with "Times in" set to another zone, Download gives a copy whose shift and break times are moved to
that zone. The file name says the zone. A shift that starts the day before or the next day stays in its own day's
column, marked as on the page ("(day before)"). Ruling: this matches what the page shows. Cost if wrong: a layout
change in the copy.

## 3. Weeks: choose which version "As planned" shows (feature)

**What exists:**
- The Weeks page's grid reads the figures the engine kept for the run.
- "As planned" in Hours needed reads the version in use, or the newest one.
- Neither lets you pick "Tool, after breaks", "Tool, before breaks", "Tool, more consistent" or an edited version.

**Fix:** a "Version" pick on the Weeks page, listing that week's versions (the one in use first). It sets both the grid
and Hours needed's "As planned". Each version is labelled with whether its breaks are planned. The RTA and "As
recorded" keep following the version in use.

## 4. Percentages when a schedule has only before-break times (bug)

**Root cause:**
- Home's Runs list ("Covered") and the Weeks grid read an engine run's figures only from the engine's own check of
  its after-breaks workbook. A run made with "Before breaks only" has no such check, so they show "no data" and an
  empty grid.
- Every kept version has its own check with full interval figures: a before-breaks version too, where the figures are
  the floor with no breaks. Measured on the B1 before-breaks fixture: 112 of 112 intervals. The website reads those
  only for uploaded ready schedules.
- So planning breaks (a new version) or setting a version in use never changes those figures for an engine run.

**Fix (TDD):**
- **A:** Runs list, Weeks and the run's page read the version in use. With none in use, they read the version the
  Schedules list shows for that run, which is the engine's figures for a full run, as now. A version with no breaks
  yet says "before breaks".
- **B:** after "Plan breaks" saves a version with breaks, setting it in use (or it being the one shown) brings its
  after-breaks percentage everywhere.

Question:
4. With no version in use, should Home and Weeks show the **newest version with breaks** (so a "Plan breaks" result
   shows at once), or **only the version in use** (recommended: the one in use; with none in use, the engine's own,
   as now)?
