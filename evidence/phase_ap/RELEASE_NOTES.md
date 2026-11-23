# What is new in this package (Phase AP, 21 Oct 2026)

© 2026 Omar Mokhtar. All rights reserved.

For the RTA team and planners. Made on top of the Phase AO package (it contains AK to AO).

## New

- **All LOBs of a program together.** On the RTA, Week and Schedules pages a program with two or more LOBs has a View
  pick: this LOB, or "All LOBs of <program>". Only the LOBs of one program merge, in the zone picked in "Times in".
  - **RTA:** one requirement, one staffed count, one shrinkage and one target for the whole program, with a LOB chip
    on each person. It works on the Timeline, the Interval board and Adherence. The other tabs plan or change one LOB's
    schedule, so they ask you to pick one LOB.
  - **Changes go to the person's own LOB.** A break, an absence or an aux made on the merged page is saved on the LOB
    that person belongs to, in that LOB's own time.
  - **Week:** one grid of the requirement and the staff of every LOB, one target (each LOB's own, weighted by what it
    needs).
  - **Schedules:** a panel with the merged week and the hours per channel of all LOBs.
  - A merged page says so instead of guessing when LOBs use different interval lengths, when a person is on two LOBs,
    or when clocks change in the window for one of them.
- **Scheduled hours per channel.** Phone, Chat and Email (and blended time, and time with no channel planned) per day
  and for the week, on the RTA Timeline and on Schedules, for one LOB or all of them. Exports has a new item, "Hours per
  channel" (Excel or CSV).
- **Daily views download.** A link on the RTA, "Download daily views": one Excel workbook with a sheet for each
  associate on the page (one LOB or all), after the day's changes, in the zone and from the start picked. Each sheet
  has the shift, the day hour by hour (work or channel, breaks) and what the RTA recorded (aux, meetings, coaching,
  overtime, VTO).

## Not changed

- The scheduling engine and the baseline workbooks are untouched.
- On a merged page Undo, the group Send bar and group posts are not offered: open the LOB for those.

## For the server

- No new packages, no database change.
