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

## Calling someone in on a day off (Phase AY)

"Day off cancelled" keeps the call-in even when it leaves less rest than the program's rest gap. The page and the day's log say it, for example "Warning: Kevin Tarek would rest 9 hours after the previous shift; the rule is 12." The other rules still refuse, because they mean the change cannot be made at all: the person works that day (add overtime instead), the person is already called in, typed times not in 15-minute steps, or a length outside 1 hour up to the longest library shift.

## Removing cover from outside the roster (Phase AY)

Two places: the button **Delete cover** beside each cover in the panel "Cover from outside the roster" (tab Overtime and VTO), and a **Remove** button beside the cover's entry in the Interval board's row (the interval where the cover starts). Remove brings you back to the board. A cover that began last night and runs past midnight shows on this day's board but is removed from yesterday's list, so it has no Remove button here.

## Long group posts go as several messages (Phase AY)

A change with more lines than one Slack message holds is no longer cut with "open the RTA to see them". It goes as several messages, titled "(1 of 3)", "(2 of 3)" and so on, every line once and in order, with "Changed on the RTA by ..." on the last. A change that fits is one message as before. If a message fails, the retries (after 1, 5 and 15 minutes) go on from that message and do not repeat the ones already posted. Teams posts are unchanged: one card.

## The limit on breaks at once follows the workbook's gate mode (Phase AY)

The tools that place breaks (Plan breaks, the fill of a new schedule, Fix, Replan and Plan channels) read the workbook's **Break Concurrency Gate Mode**:

- **Fail:** the limit on people on a break at once stays first, as the engine's hard rule.
- **Warn** (the engine's default, and what a schedule without the setting counts as) **and Off:** the limit does not decide where a break goes. The intervals' buffer comes first, then the usual shape (first break 2 to 3.5 hours after the start), then the engine's gap rules. The validator still lists an excess as a yellow warning in Warn.

So with enough buffer the first breaks go where the usual shape puts them, even when more than 4 people share that time.

## Last night's records and editing coaching (Phase AY)

- **Overtime, call-in and cover that began last night** (a shift that runs past midnight) are listed on this day's Overtime and VTO tab, under "Activities on this day" and "Cover from outside the roster", marked "shift of Wed 14 Oct" or "from Wed 14 Oct", each with a Delete that acts on its own date and brings you back to this day. A shift that ended before midnight is not listed here: open that day.
- **Booked sessions** (meeting, training, coaching for several people): tick the people, set **New start** and **New end**, press **Change the time of the ticked**. A longer or a shorter session, all or none: if anyone is not free for the new time, nobody changes and the message names who. **Move the ticked (same length)** is the old move. Undo takes a change back.
- **One booked activity** (coaching, meeting, training, an added break): in "Activities on this day" each one has a start, an end and **Save time**. Overtime, VTO and a call-in are not edited this way: delete and add them again.

## Breaks for a call-in (Phase AY)

The Timeline already draws a call-in as a bar and overtime beside the shift. A call-in for a Shift Library shift takes the breaks of the people on that shift. A call-in for typed times that nobody else works has none: on the Overtime and VTO tab, its row in "Activities on this day" shows **Plan their breaks**. It places the breaks the workbook gives a shift of that length, by the same rules as Plan breaks automatically (the usual shape first, then the engine's gaps), with everyone else's breaks where they are. They are kept as breaks added on the day, each named in the log, and one Undo takes them all back. The button does not show once the person has breaks. Overtime needs nothing: it extends a shift that has its breaks already.

## Breaks while adding overtime or a call-in, and how far back records can be removed (Phase AY)

- **Counts on the add forms.** The "+ Add" dialog and the overtime offers have **Short breaks** and **Lunches** (0 by default). Any other number is placed at once, inside the overtime or call-in time, by the same rules as Plan breaks automatically, with everyone else's breaks where they are; the lengths are the workbook's. The record and its breaks are one Undo. If the planner finds no room, the record stays and the page says the breaks were not planned.
- **How far back a day can be changed** (every change from the day page: overtime, call-ins, cover, activities, breaks, attendance, undo and the rest). Most roles: today and 1 day back. A supervisor: 7 days back. An admin: no limit. An older day shows the message "... is closed to changes for your role" and nothing is changed; viewing is never limited. "Today" is counted where the person is: the browser's own zone, kept in a cookie called `pc_tz` (falls back to the zone the page shows, then Egypt). Pages also open in that zone by default (when it is one of the zones in the "Times in" list, else Egypt); a zone picked on the page is kept for that program over the computer's. The first page after a new sign-in on a computer opens in Egypt, because the browser reports its zone after that page loads.
- **Coaching, meeting, training, system issue and task** are drawn on the Timeline as a full-height box on the person's bar, like a break, each reason in its own colour (the legend names the reasons that are on the day). An added break or lunch takes the break's colour.
- **Hour labels** on the Timeline now sit at their true hour on a short window ("Day starts at", the operating day); they were laid out for 24 hours and drifted from the intervals below.

## Split view, late logins and early leaves, VTO (Phase AY)

- **Split view** (the link beside Handover note): up to 3 RTA days together, stacked or side by side, each with its own program, day, zone and tab. Each pane is the ordinary RTA page, so its checks hold; a program you cannot open is not shown. Pick a program in the empty pane and press Show to add one.
- **Late login or early leave: the allowance.** A booking is checked while it is made: its minutes (late: shift start to arrival; early: leaving time to shift end) and how many this month (Late and Left early together, from the allowance only). The allowance is 2 hours and 2 times a month. Past either, the dialog says so and asks for the account manager's approval as an exception: tick it and write a comment, and it is booked anyway; the comment is kept with the booking and in the day's log. The server refuses without both.
- **A late login can be an incident.** The dialog first asks: from the allowance, or an incident. An incident is not held to the limits, does not use the allowance and is kept as an incident on the associate (Incidents, exports). An early leave is always from the allowance. Records from before this never count against the 2 a month. The attendance export has a "Counted as" column (Incident or From the allowance).
- **VTO is gone.** It can no longer be booked or offered, and the Overtime and VTO tab is now Overtime. Every VTO already recorded was changed to an Early leave at the VTO's start on its own date (a note says it came from a VTO; a person with another status that shift is skipped and their VTO stays as history).
