# What is new in this package (Phase AN, 16 Oct 2026)

© 2026 Omar Mokhtar. All rights reserved.

For the RTA team and planners. Made from the Phase AN commits on top of the Phase AM package (it contains AK to AM).

## Fixed

- **Times in another zone are right on every day.** A schedule shown or downloaded in another zone converts each shift
  and break on its own date, so a week with a clock change (London on 25 October, New York on 1 November) reads
  correctly. A time that repeats or does not exist that night is refused with a message that says what to do: use the
  original-zone workbook.
- **The RTA's "now" follows the schedule's own zone**, not always Cairo time.
- **On a night when the clocks change**, the RTA shows the schedule's own zone and says so. An old form left open in
  another zone is refused instead of saving a wrong time.
- **Plan channels counts what was missed**: demand with nobody on shift, overnight tails, cover from outside the
  roster and Email Hours targets. Sunday uses the week before's overnight cover.
- **Fix channels applies all or nothing.** If one change is refused, none is kept. Undo still takes them all back.
- **Go-to search** shows only the pages, programs and people your role may open.
- A planner crash can no longer take the website down: each channel plan runs on its own and keeps your draft if it
  stops.

## Not changed

- Fix channels plans today's shifts only, as in the last package. Short blocks set by hand on Plan channels still only
  warn. There is no lock on Plan breaks or Plan channels.
- The scheduling engine and the baseline workbooks are untouched.

## For the server

- `protobuf==6.33.6` is pinned in `deploy/requirements.txt` (the version already in use with OR-Tools 9.15.6755).
