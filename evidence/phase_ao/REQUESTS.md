# Phase AO: the owner's requests

© 2026 Omar Mokhtar. All rights reserved.

Received Tue 20 Oct 2026, after the AN2 package (the Home 500 fix). One message with ten items. Claude read the code
behind each item (no code changed yet) and found the cause where there is a fault. The items split into Phase AO
(items 1 to 9, fixes and the leave rule) and Phase AP (item 10, merging LOBs, which needs a sample first).

## The owner's words

> From associate view they can't see next week schedule or all schedule raised for them and inuse for future weeks
> They can't see their schedule breaks or coachings etc
> They cant swap full week
>
> Also when trying to add OT for shift 3 pm to 00:00 it adds before normally but it glitch for after hours OT for that
> shift only it reflects that associate is there but the hours not being added this is only for that shift for that case
>
> I think swap rules are broke because when i choose any day it doesn't show that i can proceed with any swaps always
> showing no one available under rules etc, also it should show the option with warning
> When I'm selecting GDI and updating associates name should only show names under that roaster not for saks associates
> for example
> Same when assigning a team manager should show the ones related to the assigned program only
> And when i choose a name on the roaster it's not found and telling me not existing
>
> For leaves it can be for future dates even if schedule was not raised and this should reflect in the future as a
> warning that requested leave and it's approve but not considered while building the schedule or it can be considered
> automatically moving forward while building the schedule once we upload the sheet the site to add this in preference
> tab or to give the order to engine to add them but if failed to be a warning not to stop the schedule building like if
> associate name for example is not part of the roaster uploaded or something something smart like that or at least to
> store them to be exported for that week later on from export
>
> We need to add the ability in RTA to merge between two lobs even they are uploaded in different time zones to show in
> RTA tab as one schedule with 1 requirements and 1 actuals 1 shrinkage etc, also to have the ability same on week tab
> and schedule tab and i can have the total hours scheduled for each channel per day and on the overall from RTA tab and
> schedule tab and a daily view for each associate same as we have now but downloadable from RTA tab after the changes
> if any during the day

## What Claude found, item by item

**1. An associate sees only one week, in-use today (`/me`).** The page reads the week of the version in use today.
Next week and any later week that has a schedule kept are never offered.
**2. An associate sees only the shift text per day.** The day's breaks and lunch are drawn only for today's card. The
week table holds the shift, leave and swap notes, nothing else.
**3. A swap is one day at a time** (`me_swap`: one `day`).
**4. Swap candidates: "Nobody can take your shift that day within the rules."** Two causes:
- the page lists only colleagues who pass every rule (rest gap, language, channels) and who also have an associate
  account (`swaps.account`), so a colleague with no account, or one failing any rule, never shows;
- the message is the same for every cause (no schedule that day, no account, a rule).
**5. Overtime after a shift that ends at 00:00 is recorded but not drawn or counted.** Reproduced: a 15:00 to 00:00
shift with 1 hour of overtime after saves 24:00 to 01:00, but the day's lane stops at 24:00, and the next day's page
carries yesterday's shift only when it ends after 24:00 (`day._segments`: `end <= 0` is skipped). A shift ending after
midnight (21:00 to 06:00) works. So the hour after midnight is on no day's floor count.
**6. The name pickers list every program's names, not the picked program's.** On People, the roster name list
(`roster_names`) is built from every program the person may grant; the bulk team-manager select lists every team
manager (`leaders`), where the one-by-one select is already filtered.
**7. "Name not found".** The name check (`_roster_problem`) reads only the newest kept week of each LOB, and only the
LOBs of the programs picked. Likely causes: the name is from another program's list (item 6), or it is not on that
LOB's newest kept week (for example a partly filled newer week). Needs one example to be certain.
**8. Leave for dates with no schedule yet is accepted today**, counted as "no schedule yet", and when the RTA approves
it only says "mark it when that week is planned". Nothing is stored for later, and nothing warns when that week is
later uploaded.
**9. (Same as 8: the three options the owner gave.)**
**10. Merging LOBs: not in the product.** Every page, run, version and RTA day is keyed by one LOB.

## Decisions taken without asking (each with what it costs if wrong)

- Names and team managers are filtered by the programs picked on the form. Cost: none to speak of.
- A swap offer that breaks a rule is shown with its warning (the owner asked). It is kept as a request; the team
  manager and the RTA see the warning when they decide. Cost: one more thing to read at approval.
- A colleague with no account is shown with "has no account: ask your team manager", not hidden.
- The reason for an empty list is always said (no shift, no account, leave, a rule).

## Questions for the owner (answered in chat)

1. My week: show this week and every later week that has a schedule kept (a week picker), with each day's shift, breaks
   and lunch, and the aux, meetings and coaching recorded for it? Where do "coachings" come from: the aux recorded on the
   RTA, or something planned ahead that the site does not hold yet?
2. A full-week swap: swap the whole week (each day's shift or day off, one request, warnings per day), or only the
   days both work?
3. Leave with no schedule yet: which of these?
   - A: keep it stored; show a warning on the week when it is uploaded ("approved leave not in the schedule"), listed in
     Exports.
   - B: A, and after a run finishes, mark the approved leave as Leave in a new version (set in use or only offered), with
     the coverage it costs. A name not on the roster is a warning, never a stop. The engine is not changed.
4. Merge LOBs (Phase AP): which LOBs go together (any two in a program, or any two at all), is the merged view
   read-only or do edits go through to the LOB each person belongs to, and what time zone shows it? A sample comes first.
