# Phase AA checks, 2026-10-10 Egypt time

The owner approved samples 01 to 04 ("1. Overtime before/after, 2. Delete an upload, 3. Schedules by week, 4. Week
page switch") and "Uploader or admin (Recommended)" for who may delete. This file records how the built site was
checked. Screens are in `screens/` (written by `ThePhaseAAInTheBrowser`), made-up "Associate NN" data.

## What was built, and the tests that pin it

| Part | Tests |
| --- | --- |
| Overtime picked before or after the shift; the times come from the person's shift; a length that would start the day before is refused clearly; an overnight shift's overtime after starts the next morning | `webapp/tests/test_overtime_side.py` |
| The menu's Schedules: a week picker and the week's schedules side by side; "better" only when every schedule has breaks; actions follow who may do them | `webapp/tests/test_schedules_by_week.py` |
| Delete a schedule that is not needed: admins and the uploader; refused for the one in use, a running run, another person (403) or without the tick; the days' records stay; logged | `webapp/tests/test_delete_schedule.py` |
| The Week page's schedule switch; the one not in use says so and offers Set in use | `webapp/tests/test_week_switch.py` |

Three earlier assertions were re-pinned, each with its reason in the test, because an approved sample changed what
they measured: the menu's Schedules is a page rather than a redirect (two tests), and the Week page's "This week also
has ..." sentence became the switch (one test).

## Browser (Playwright, Chromium 141)

`webapp/tests/test_ui_playwright.py`, class `ThePhaseAAInTheBrowser`:

| Test | What it proves |
| --- | --- |
| `test_overtime_before_or_after_the_shift` | with Overtime picked, From hides; the shift and both choices show their times, which follow the length; After the shift for 30 min is recorded as 17:00 to 17:30 |
| `test_phase_aa_screens` | the Schedules page (picker, three schedules, the one in use first), the Week page switch and the other schedule's Set in use, Delete refused by the browser without the tick and done with it, then the week's page with two schedules; no sideways scroll at 390 and 320 px; no page errors |

## axe-core 4.14 (WCAG 2.2 A and AA), the whole signed-in site

A crawl of 70 pages plus the sign-in page, in the night look and the day look (142 page-looks), on a server with three
weeks of data (this week with two schedules, one in use with breaks planned and one with channel needs added).

| Check | Result |
| --- | --- |
| axe violations | none |
| Sideways scroll at 320 px and at 640 px | none (140 page-widths) |
| axe "incomplete" for colour contrast | 130 page-looks, from the background grid drawn with a gradient (as in Phases XY and Z) |

## Not checked

Windows high-contrast mode, screen readers by ear, and real phones.
