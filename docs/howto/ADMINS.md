<!-- © 2026 Omar Mokhtar. All rights reserved. -->
# Team scheduler for admins and supervisors

## People
- **Add a person**: a blank password is made up and shown once. A temporary password works for 7 days.
- **Add many from a file**, **Download the people list**, **Switch several off or on**, **Delete** (the name stays in the
  history). A person switched off or deleted has their waiting requests cancelled.
- Sign-in problems: Exports, Other actions, "Sign-in failed" shows the reason (`bad`, `locked`, `expired`, `disabled`).
  An address held after too many wrong sign-ins is listed on People with a button to lift it.
- **Settings, Sign out other devices** ends every other session of the same account.

## Programs
- **Coverage measure** (interval, service level, volume) decides how billable time counts.
- **Break change requests**: on or off, a lead time in minutes, and a daily limit per associate (0 = none).

## Before a release
`python tools/audit_dependencies.py` (needs internet and `pip install pip-audit`), then the gate and the package.
