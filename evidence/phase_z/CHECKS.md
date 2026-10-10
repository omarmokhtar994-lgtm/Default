# Phase Z checks, 2026-10-10 Egypt time

The owner approved samples 01 to 05 ("1. Week's schedules list, 2. Channel needs, 3. Today's achievement, Check rest
of my comments above") and "Panel + tabs" for channel needs. This file records how the built site was checked.
Screens are in `screens/` (written by `ThePhaseZInTheBrowser.test_phase_z_screens`), made-up "Associate NN" data.

## What was built, and the tests that pin it

| Part | Tests |
| --- | --- |
| Every Schedules page lists the week's schedules; the menu, Home and the Week page follow the one in use | `webapp/tests/test_week_list.py` (`TheWeekList`, `TheHomePage`) |
| The strange things: uploads named as uploads, "after breaks" only with breaks, a break plan logged as one change, run pages say in use or not | `test_week_list.py` (`TheWording`) |
| Channel needs added to a schedule (no new run); one channel source for Plan channels, the RTA and channel changes; wrong interval refused by tab; empty tabs ask for nobody | `webapp/tests/test_channel_needs.py` |
| The Blank and Example workbooks carry the channel tabs; the engine reads them exactly as before | `test_channel_needs.py` (`TheHomeWorkbooks`), and the builder's own check (135 fields on the Example; the requirement tab on the Blank) |
| Today's achievement above the RTA's tabs, At target or Below on the board, Achieved under the hours | `webapp/tests/test_achievement.py` |

## Browser (Playwright, Chromium 141)

`webapp/tests/test_ui_playwright.py`, class `ThePhaseZInTheBrowser`:

| Test | What it proves |
| --- | --- |
| `test_the_now_mark_sits_at_the_current_time` | on today the "now" line sits within 1% of the time of day across the strip; another day of the week is "Achievement on ..." with no line. A run with the placement removed fails it (0.0 against 0.265). |
| `test_phase_z_screens` | Home, the week's schedules, the Channels panel (download named `Channel_needs_SAKS_NMG_Tier_2_...`, the needs added through the real file picker), Associate channels, the Week page, the RTA Timeline and board in both looks; no sideways scroll at 390 px and 320 px; no page errors |

Three problems were found here and fixed: the first two with the failing check first, the third seen on the board's screen:

- The week list widened a phone page (390 px became 457 px): its hidden "Actions" column label escaped the list's
  sideways scroll. The list's scroll box now holds it.
- At 320 px the Channels panel's three steps widened the page to 357 px: the file picker's own width held each step
  open. The steps and the picker now shrink to the screen.
- On the Interval board, "At target" ran into the Status column; the Cover column is 16 px wider.

## axe-core 4.14 (WCAG 2.2 A and AA), the whole signed-in site

A crawl of 65 pages plus the sign-in page, in the night look and the day look (130 page-looks), on a server with this
week's data: two uploads for one week (one in use with breaks planned, one with channel needs added), a 90% target and
three people sick today. axe was injected from a scratch copy (not a dependency of the site).

| Check | Result |
| --- | --- |
| axe violations | none |
| Sideways scroll at 320 px and at 640 px (200% zoom of a 1280 px window) | none on any page (128 page-widths) |
| axe "incomplete" for colour contrast | 122 page-looks, from the faint background grid drawn with a gradient, which axe does not measure (Phase XY had the same); the status colours on text are measured in the browser tests of Phase XY |

## Not checked

Windows high-contrast mode, screen readers by ear, and real phones.
