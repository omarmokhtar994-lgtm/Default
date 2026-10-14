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

## Results (2026-10-14, Egypt time)

- Full website suite (05:16 to 05:41): 873 tests, 7 failures, 1 error, 1 skipped. All 8 are
  calendar collisions, not the clock change: each test uses Wednesday 14 October 2026 as its
  sample "other day", and that was the day of the run. The same 8 fail identically on the
  commit before the change (bb3d2d1). They pass on any other day. Not changed: the measured
  contract did not change.
  - test_achievement (2), test_bulk_breaks.test_panel_preview_and_apply,
    test_cancel_break.test_route_answers_like_a_move,
    test_channel_day.test_as_planned_every_channel_and_language_is_covered,
    test_interval_target.test_the_day_tile_and_row_use_the_week_target,
    test_rescue.test_apply_route, test_ui_playwright.test_cancel_a_break_with_a_reason_and_bring_it_back.
- The browser tests rewrite the old phases' screenshots under evidence/*/screens when they run.
  The 142 rewritten files were restored to their committed bytes before packaging.
- Release gate (run_tests.sh, tests_staged/GATE_MINIMUMS.json): GATE PASS, 77 suites, 1537
  tests (2 skipped), 2 selfchecks, call signatures, undefined-name sweep. The first build was
  refused because test_egypt_clock.py lacked the copyright line every website file carries;
  it was added (commit b1f5b56) and the gate re-run.
- Package: dist/RC9_2_2_PRODUCTION_PACKAGE.zip, 2521 files, 59.09 MB,
  sha256 3164fa94ad912870d95098f52243ec3c78b218a1d417c21c96d68d060860c556.
