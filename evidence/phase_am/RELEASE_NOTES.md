# What is new in this package (Phase AM, 16 Oct 2026)

© 2026 Omar Mokhtar. All rights reserved.

For the RTA team and planners. Made from the Phase AM commits on top of the Phase AL package.

## New

- **Fix channels, in one click, on the RTA's Channels tab.** The button re-plans everyone's channels from the next
  quarter hour to the end of their shifts, for people who are on the floor, to cover every channel and language.
  - Breaks, away time and activities stay where they are. Someone already on the channel they are needed on stays
    there.
  - People are moved only where coverage needs it; between equal plans, the fairer one is picked.
  - You see each change first, with the shortfall per channel now and after. Then "Apply all" keeps them as one
    change, and Undo takes them all back.
- **Weeks: a Version pick.** Choose which of the week's versions the grid and Hours needed "As planned" show: after
  breaks, before breaks, more consistent, or an edited version. The one in use comes first. "As recorded" and the RTA
  keep following the version in use.

## Changed

- **Download in the zone picked.** With "Times in" set to another zone on a schedule, Download (.xlsx) gives a copy in
  that zone's clock. Each shift reads as the page shows it, marked when it moves to the day before or the next day.
  Each break moves the same. The kept workbook stays as it is.

## Fixed

- A run made with "Before breaks only" showed "no data" on Home and its own page. It now shows its percentage, marked
  "before breaks". Home and the run page follow the version in use: after "Plan breaks", set that version in use and
  its after-breaks percentage shows.
- A run that had just finished could, for a moment, show its figures without their outcome.
