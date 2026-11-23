# What is new in this package (Phase AO, 21 Oct 2026)

© 2026 Omar Mokhtar. All rights reserved.

For associates, team managers and the RTA team. Made on top of the Phase AN package (it contains AK to AN).

## New

- **My week** has a week picker: this week and later weeks that have a schedule. Each day shows the shift, breaks,
  lunch and what the RTA recorded (aux, meetings, coaching, overtime).
- **Swap the whole week** in one request. Days with Leave, days already past, equal shifts and days both are off stay
  as they are.
- **Swap offers show warnings** instead of "nobody available". A colleague who breaks a rule is listed with the
  reason and can still be offered; the team manager and the RTA see the warning when they decide. A colleague with no
  account is shown as such.
- **Leave for weeks with no schedule yet** is kept. When that week's schedule is uploaded and kept, the approved leave
  is marked Leave in a new version in use, with a warning on the page. A name not on the roster only warns. The
  requests are listed in Exports ("Leave requests").
- **Input sheet**: new optional row "Break Set For Shifts Of 11 Hours Or More" (default `15, 30, 15, 15`).

## Fixed

- Overtime after a shift that ends at 00:00 now shows and counts on the next day.
- Name lists and team manager lists on People show only the programs picked. A name typed in other case or with
  extra spaces is found, and names are read from the last 4 kept weeks.

## Not changed

- The scheduling engine and the baseline workbooks are untouched.
- Merging LOBs in the RTA is Phase AP.

## For the server

- No new packages. The database adds three columns to swap requests by itself on start.
