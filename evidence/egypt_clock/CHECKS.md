# Egypt clock: Cairo time instead of a fixed UTC+3

Owner, 2026-10-14: "yes fix it and update the line".

## The defect

Seven website modules fixed Egypt time at UTC+3 (`timezone(timedelta(hours=3))`):
app, analytics, coach, exports, notify, schedules (attendance takes it from schedules)
and versions (the Version Notes tab). Egypt is UTC+3 only in summer. From midnight on
Thursday 29 October 2026 until the last Friday of April 2027 Cairo is UTC+2, so the
website would have run one hour ahead all winter:

- the RTA's "today" and its now line, and Rescue the day's lost-so-far;
- the day's break posts at their set time, and post times;
- every recorded and exported time, "Downloaded at", and week boundaries late on Saturday.

Python's `zoneinfo` (system tzdata 2025b here) gives Cairo +03:00 up to 29 Oct 23:59
and +02:00 from then (23:00 to 23:59 on 29 Oct happen twice), and +03:00 again from
Friday 30 April 2027 01:00.

## The fix

- `webapp/clock.py`: `EGYPT = ZoneInfo("Africa/Cairo")`, the one source. No fallback
  to a fixed offset: without the zone data the website stops at start-up.
- The seven modules import it; the unused `timezone` imports went with the old lines.
- The export's About tab says "All times are Egypt time (Cairo clock: UTC+3 in summer,
  UTC+2 in winter)."
- `deploy/install.sh` installs `tzdata` with the other system packages.
- `CLAUDE.md` and the documentation-and-adrs local note: Egypt time on the Africa/Cairo clock.

The browser's now line takes its minutes from the server, so `app.js` needed no change.
The engine has no time zone code (checked: no `ZoneInfo` or fixed offset under `engine/`).

## Tests

- New `webapp/tests/test_egypt_clock.py` (8 tests). Failed first (19 failures, all
  offsets one hour ahead), then passed.
- New `test_deploy.TheDryRun.test_installs_time_zone_data`. Failed first, then passed.
- Re-pinned with a reason in each file: the "today" helpers in test_achievement,
  test_channel_needs, test_schedules_by_week and test_ui_playwright (5 places) used a
  fixed UTC+3, which names the wrong day from 22:00 to 23:00 Egypt time all winter.
- Left alone: the notification tests' fixed UTC+3 times, all between 10 and 25 October 2026,
  when UTC+3 is Cairo's offset.
