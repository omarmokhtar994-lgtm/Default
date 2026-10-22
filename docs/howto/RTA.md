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
