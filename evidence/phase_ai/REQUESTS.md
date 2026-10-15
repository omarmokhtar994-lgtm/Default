# Phase AI: the owner's requests (2026-10-15, Egypt time)

© 2026 Omar Mokhtar. All rights reserved.

Noted from the owner's message of 2026-10-15, about 05:16, with two photos of the live site (the RTA timeline as the
operating day, and the interval board while dragging a break). Nothing is built yet: defects get a failing test
first, visual changes a sample first.

Owner, verbatim: "Drag and drop for breacks is lagging needs to be jn specefic place sevral places in the box are
lagging and not working probably, in calendar day i need to have the option to change the day statt time same as the
one in operating day but it should be on the same page and by changing the statt time it should keep it for all tabs
timeline, interval board adherence etc, we need to add exam leave as something as well and not to be counted in
Sutherland shrinkage but in client shrinkage, chsnnels not coloredd here even u mentioned it's updated, no back
button in wallboard , and i dont need operating day to be something different than calendar day when i change
timezone or change day start time it should all be on the same calendar day options with everything, when i choose
different program i still csn dee same departments and names from another department, runned schedules should be
seen by others or downloadable they can onyl see if something js running count of queued and how much time they will
wait, rest kf week view in oversll view is not organized , instead nof endless scrolling they might have some pages to
see more of runned schedules same for OT and other staff"

| # | Request | Kind | Reading |
| --- | --- | --- | --- |
| 1 | Drag and drop of breaks on the interval board lags; it drops only on one spot, several places in a box do not take the drop | defect | The whole interval row (every column) takes the drop, the move shows at once, nothing waits on the server before the break looks moved |
| 2 | Change the day's start time on the calendar day, on the same page, kept for every tab (timeline, interval board, adherence and the rest) | change | One "day starts at" choice on the RTA itself, remembered while moving between tabs and days |
| 3 | Exam leave | new | A whole-shift absence on the RTA (and a leave kind to ask for), counted in the client's shrinkage, not Sutherland's |
| 4 | Channels are not coloured on the timeline (photo 1) | check | Find why: no channel plan for that schedule, or a defect |
| 5 | No Back button on the wallboard | defect | The wallboard gets the same Back as every other page |
| 6 | No separate operating day: changing the time zone or the day's start keeps everything on the one calendar day page, with everything working | change | The other-zone and operating-day views stop being a separate read-only page; the calendar day itself shifts, with its tabs and actions |
| 7 | Another program still shows the same departments and names | defect | Departments and people show only the picked program's own |
| 8 | Run schedules: who may see and download them | change, to confirm | Read as: people see others' runs only as "something is running", how many are queued and how long they will wait; a run's schedule and downloads only for whoever ran it (and admins) |
| 9 | Rest of the week on Overview is not organized | change | A sample first |
| 10 | Pages instead of endless scrolling: runs, overtime and the other long lists | change | Page through them (for example 20 at a time) |

## To confirm with the owner

- 8: "should be seen by others or downloadable" with "they can only see if something is running": is it "should
  NOT be seen by others", leaving only the queue? And do supervisors and admins still see everyone's runs?
- 3: exam leave asked for like planned leave (TM then RTA approval), recorded on the RTA like sick, or both?
- 6: with one calendar day, does a change made in another time zone (moving a break) apply as if made on the
  schedule's own day? Today that is read only.
