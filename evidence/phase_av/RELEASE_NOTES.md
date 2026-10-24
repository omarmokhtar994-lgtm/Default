# Phase AV release notes (with AP to AU in the same package)

**Install:** run `pip install -r deploy/requirements.txt` on the server once (it now pins `defusedxml`, and the website refuses to
start without it). The database upgrades itself on start (new tables `incidents`, `app_settings`, `revoked_sessions` and a column
`activities.session`); nothing stored is changed. Checked by opening a copy of the previous version's data with this version.

- **RTA:** book several people at a set time (Find a time, and "Book several" on the Interval board); a Booked sessions tab to
  move or remove some of them together; a "Missed break" tick when a break is moved (single and bulk), kept as an incident.
- **Bio break:** a new aux (no who or why, never billable); counted as in-office shrinkage, in incident counts and in exports.
- **Incidents page** (Insights): missed breaks, leave, late, early leave, coaching, training, meetings, system issues, tasks, bio
  breaks and out-of-adherence time, with counts and durations; overview, LOBs, associates, one associate; absenteeism %, three
  shrinkage figures and adherence, each against the period before; weekday pattern; repeated incidents; absenteeism counts chosen
  on the page (RTA and client: unplanned + sick; Sutherland: unplanned only).
- **Shrinkage page** (Insights): out of office, in office or both; day over day, week over week (weeks begin on the program's start
  day) and per interval with a heat table; period, interval, hour window, weekdays and what counts all adjustable.
- **Exports:** Late and Left early have a duration; new reports: incidents, booked sessions, break and coaching requests, swap
  requests, absenteeism and shrinkage, incidents per associate.
- **Setting** (Programs and LOBs): the most weeks at a time the heavy pages allow people other than admins, supervisors and RTAs
  (default 13, recommended 6).
- **Uploads:** a workbook with other tabs than the input workbook's, card numbers, street addresses, bank numbers, macros or links
  to other files is refused and deleted, and recorded by kind. Phone numbers and emails are not looked for.
- **Security:** a signed-out session cookie no longer works; usernames cannot be found by timing; very long upload names are
  handled; XML entity bombs in a workbook are refused. Attack results: `evidence/phase_av/security/FINDINGS.md`.
- **Speed:** a built day is kept until something it is built from changes (database writes to day tables, schedule or channel
  files, expiry), per viewing zone, never inside an open change; 500 users (475 associates, 20 managers, 5 RTAs) measured in
  `evidence/phase_av/LOAD.md`. The server accepts 1000 open connections instead of 100.
- **Fixed on the way:** the board's "nothing" dash and the new heat tables are readable and scroll inside their panel.
Docs: `docs/howto/`.
