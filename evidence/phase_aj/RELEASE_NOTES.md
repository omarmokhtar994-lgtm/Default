# What is new in this package (Phase AJ, 15 Oct 2026)

© 2026 Omar Mokhtar. All rights reserved.

For the RTA team. Made from the Phase AJ commits on top of the Phase AI package.

## New

- **Cover from outside the roster.** On the RTA's Overtime and VTO tab, record a team manager or support member who
  is not on the schedule and logs in to cover: their name, Team manager or Support, from and to (it can run past
  midnight), the channel they take when the program has channels, and the language they take. They count as one more
  person on the floor for those minutes, on that channel and for that language. The Interval board names them, the
  change goes to the group like overtime, and Undo takes it back. They stay out of the roster's hours, adherence and
  shrinkage.
- **Exports: a tick for that cover.** Ticked, the export has their own sheet and counts them in the Daily summary
  ("Cover min"); unticked, the export is the roster alone.

## Changed

- **Overtime up to 4 hours**, before or after the shift (it was 2 hours).
- **Overtime that breaks the rest gap is kept, with a warning** that says how much rest it leaves, on the page, in the
  "+ Add" preview and in the day's changes. A day off cancelled still keeps the rest gap.

## Fixed

- Overtime of 3 or 4 hours before a night shift (for example 16:00 to 20:00 before a 20:00 shift) was refused with
  "Overtime has to start when the shift ends or end when it starts".
- The Timeline showed no channel colour after 00:00 on night shifts.
