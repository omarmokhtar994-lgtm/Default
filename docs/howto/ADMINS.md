<!-- © 2026 Omar Mokhtar. All rights reserved. -->
# Team scheduler for admins and supervisors

## People
- **Add a person**: a blank password is made up and shown once. A temporary password works for 7 days.
- **Add many from a file**, **Download the people list**, **Switch several off or on**, **Delete** (the name stays in the
  history). A person switched off or deleted has their waiting requests cancelled.
- Sign-in problems: Exports, Other actions, "Sign-in failed" shows the reason (`bad`, `locked`, `expired`, `disabled`).
  An address held after too many wrong sign-ins is listed on People with a button to lift it.
- **Settings, Sign out other devices** ends every other session of the same account.

## Programs (LOBs and defaults)
One page holds every default of a program and its LOBs. They are the defaults on every other page; a week's own target, or
a LOB's own operating day or shrinkage set on the RTA, still wins (the page lists those and lets you go back to the
program's).
- **Coverage measure** (interval, service level, volume): the RTA, Weeks, Overview, wallboard, exports and the handover note
  start from it, and so does a new run's coverage option.
- **Default target** (percent): colours intervals everywhere unless a week has its own; blank follows the workbook.
- **Operating day starts**: offered on the RTA under "Day starts at" (the RTA still opens on the calendar day). Picked,
  the page runs from that start to the end of the last shift that starts in it (24 hours when that cannot be worked out).
- **What counts as shrinkage**: the in-office and out-of-office mapping for all LOBs of the program.
- **Coverage measure** (interval, service level, volume) decides how billable time counts.
- **Break change requests**: on or off, a lead time in minutes, and a daily limit per associate (0 = none).

## Before a release
`python tools/audit_dependencies.py` (needs internet and `pip install pip-audit`), then the gate and the package.
