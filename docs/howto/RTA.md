<!-- © 2026 Omar Mokhtar. All rights reserved. -->
# Team scheduler for the RTA

## Requests tab (on the RTA page)
- Break change and coaching requests wait here, soonest first, with a count on the tab and the menu. In the all-LOBs view
  the tab lists every LOB's requests, each marked with its LOB.
- Each shows the intervals it touches: needed, on the floor now (from your records, not the plan), after the change, the
  buffer, and the share off the queue.
- **Overlap** warns when other waiting requests land on the same time and how many people would be off at once.
- **Stale** warns when the break is no longer where the request found it (you moved it). You can only reject it.
- **Approve as asked**, or **approve at a nearby time**. A changed time or a rejection needs a comment: the person sees it.
- A request whose time passes undecided expires. New requests are also posted to the LOB's group.

## Break shape (Plan breaks automatically)
First break 2 to 3.5 h after the shift starts, lunch 2 to 3 h of work after it, the last break after lunch and clear of the
last hour. It bends when an interval would go short (the target plus the 10-minute cushion). See
`evidence/phase_au/BREAKS_RULE.md`.

## Group posts
Notifications (admin) picks, per LOB, which changes post. "Answers to break change and coaching requests" covers new
requests, rejections, changed-time approvals, coaching answers and leave and swap decisions. A break's repeated moves
post only the latest, followed by "Breaks now: ...".

## Booking several people, and the missed-break tick (Phase AV)
- **Find a time** books the same people at a time you type: tick them, set the length, type the time under "Or a time you
  choose" and press "Book everyone at this time". If anyone is not free, nobody is booked. On the Interval board, "Book
  several" next to an interval opens Find a time with that interval filled in.
- **Booked sessions** lists each group booked together. Tick some or all of the people, then move them to a new time or
  take them out. A move happens for everyone ticked or for nobody; Undo reverses it.
- **Missed break**: tick it on the break dialog, or on Change several breaks, when the associate missed the break. It is
  kept as an incident and shows on the Incidents page and in the Incidents export.

## Replan the day's breaks, and choosing LOBs to view together (Phase AX)
- **Replan the day's breaks** sits next to "Fix the rest of the day's breaks". It lifts every break that has not started and
  places each one again as the program's default break rules place it (the same planner as Plan breaks > Suggest), for
  the day and "Day starts at" picked, from now on for today, whole for a day to come, nothing for a day that has passed.
  A time the day itself refuses (away time, an activity, the program's gaps, a language below its minimum) gives way to the
  nearest allowed one. You see the moves, the tightest interval and the hours short before and after, and nothing is kept
  until you press Apply. It changes nothing else: attendance, shifts and breaks that have started stay. Undo takes an
  applied replan back. The first time for a schedule it reads the break rules from its workbook, which can take a minute;
  if they cannot be read it says so and places the breaks by the day page's own score instead.
- **View** (day and week): tick the LOBs of the program to show together, for example two out of five. The LOB the page is
  opened on is always shown. Untick the others to go back to one LOB.
- **Download** buttons sit under each chart (PNG picture, SVG drawing) and each table (CSV, opens in Excel) on the
  Shrinkage and Incidents pages. They save what the page shows for the period and choices picked.

## Adherence and the Incidents counts (Phase AX)
- Adherence is measured against the schedule as the RTA holds it. Moving a break in the RTA is not a miss, and costs no
  adherence. A break ticked as **Missed break** is out of adherence for its minutes, once however often it is moved.
- "Out of adherence" is no longer an incident type on the Incidents page. The Adherence percentage stays.
- The Incidents page has **Counts by type**: a count and the time for each kind (missed breaks, unplanned leave, sick,
  planned leave, late logins, early leave, coaching, training, meetings, system issues, tasks, bio breaks), for everyone in
  the period and for one associate when one is open.

## The break rules, in one model (Phase AX)
- The workbook's break rules are three layers. Intervals come first in the RTA tools (Fix the rest, Rescue). Then the default
  shape (first break 2 to 3.5 hours into the shift, lunch 2 to 3 hours of work after it, the last break ending an hour before
  the shift does). Then the engine's rules. When a tool has to give something up for an interval it gives up the least: it is
  measured in minutes off the shape and off the rules.
- The minimum gap ("Break Absolute Minimum Gap") is absolute for the tools. The maximum ("Break Normal Maximum Gap") is a
  normal: the tools may pass it by as little as needed, and Plan channels does too when a channel's need asks for it.
- What people choose by hand never stops them. A single move, Change several breaks and an associate's break request list
  every time the shift and the other breaks allow, and mark a time that is closer than the minimum gap, further than the
  normal maximum or off the default with what it breaks. The RTA sees the same words on the request.

## Open pages notice changes (Phase AY)

An open page asks the server every 30 seconds (plus a random 0 to 5 seconds, so that many open pages do not ask together) whether what it shows has changed.

- **Reloads by itself:** My day and My week (associates), and the Overview. If a field has the focus or has been typed in, the page shows a bar instead, so nothing typed is lost.
- **Shows a bar, never reloads:** the RTA day (Timeline, Interval board, Adherence) and Requests. The bar says "The page changed" with a link, "Refresh to see it".
- **No watching:** reports and setup pages (Incidents, Shrinkage, Analysis, Exports, the schedule editors, Plan breaks, Plan channels, People and settings), where a reload would lose the period or the choice made.

The page compares a stamp of what it shows, not the database's write counter. An associate's stamp covers only their own shifts (yesterday, today, tomorrow) and requests, so a colleague's change or someone opening a page does not reload it. A stamp is kept 10 seconds, so a change shows within about 45 seconds. The asks stop while the tab is hidden, and wait longer (up to 5 minutes) after a failure. The server log notes how many stamps were asked and built.
