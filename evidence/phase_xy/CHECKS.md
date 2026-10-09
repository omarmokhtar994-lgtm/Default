# Phase XY checks, 2026-10-10 Egypt time

The owner approved every Phase X review fix and the three parts of the Phase Y colour proposal. This file records
how the built site was checked. Screens are in `screens/` (written by
`ThePhaseXYInTheBrowser.test_phase_xy_screens`).

## axe-core 4.14 (WCAG 2.2 A and AA), the whole signed-in site

A crawl of 70 pages plus the sign-in page, each in the night look and the day look (140 page-looks), with axe-core
injected from a scratch copy (not a dependency of the site).

| Rule | Phase X review (49 pages, before) | Now (70 pages) |
| --- | --- | --- |
| colour-contrast | 20 page-looks, 80 elements | none |
| nested-interactive (breaks inside a timeline image) | 8 page-looks, 32 elements | none |
| scrollable-region-focusable (unnamed scroll boxes) | 14 page-looks, 14 elements | none |
| any other rule | none | none |

Sideways scroll at 320 px and at 640 px (200% zoom of a 1280 px window): none on any page (138 page-widths).

What axe could not decide: on 128 page-looks it marks some text "incomplete" for colour contrast because the page
background is a faint grid drawn with a gradient, which axe does not measure (Phase X had the same, 84 page-looks).
Those pairs are measured instead by the browser tests below, from the colours the browser actually draws.

## Browser tests (Playwright, Chromium 141)

`webapp/tests/test_ui_playwright.py`, class `ThePhaseXYInTheBrowser`:

| Test | What it proves |
| --- | --- |
| `test_one_arrow_does_not_save_attendance` | one Down arrow on an attendance box saves nothing; the note says Enter saves, Esc keeps; Enter saves |
| `test_escape_and_tab_put_attendance_back` | Esc and Tab both put Present back, with no save and no note |
| `test_a_mouse_pick_still_saves_at_once` | a pick with the mouse saves at once, as before |
| `test_an_open_list_saves_with_one_enter` | a list opened with Alt+Down or Space and closed with Enter saves once |
| `test_one_arrow_does_not_change_the_measure` | the Measure picker waits for Enter |
| `test_home_does_not_reload_over_a_form_in_use` | with a workbook chosen, Home does not reload for 65 s and says updates are paused |
| `test_home_still_refreshes_when_the_form_is_untouched` | an untouched Home still refreshes after 30 s |
| `test_a_finished_run_says_so_without_reloading` | the running schedule ends: "This schedule finished." with an Open it link, and the form keeps its file |
| `test_rendered_pairs_pass_in_both_looks` | night, day (device) and day (picked): text on status cells and break badges 4.5:1 or more; field edges and status cells 3:1 or more; links are not the covered teal |
| `test_ticks_are_ink_and_every_field_has_an_edge` | checkboxes and radios are ink; time fields and text areas have the field edge |
| `test_focus_never_hides_under_the_top_bar` | at 1280 and 390 px, Shift+Tab never leaves the focused cell under the sticky bar |
| `test_focus_clears_a_top_bar_that_wraps` | a long name wraps the bar to 83 px at 960 px; focus still clears it |
| `test_a_focused_break_shows_its_ring` | a focused break has a 2 px ink outline in both looks |
| `test_names_fit_on_a_phone` | at 320 px every name on the timeline is whole and attendance boxes use 16 px text |
| `test_phase_xy_screens` | the screens in `screens/`, with no page errors |

`webapp/tests/test_markup_xy.py`: the skip link, timeline lanes as groups, "+ Add" naming its interval, every scroll
box a named region, the timeline note's new words, every font size in rem, and the approved token values in the
night block and in both day blocks. `webapp/tests/test_errors.py`: the error pages, including a made-up program in a link (its words are not repeated back). `webapp/tests/test_contacts.py`:
the department removal check.

`webapp/tests/test_session_cookie.py` (found in the final review): a save's message ("Added coaching…") was
sometimes missing on the next page, because a preview started before the save and answered after it put back the
session from before the save. The browser suite had caught it twice (Phase T and Phase U screens). A page's own
background requests no longer re-send the session cookie; page loads and real session changes still do.

## Against the approved Phase Y samples

The nine Phase Y sample pages were drawn again with the new `app.css` alone (no proposal layer) and compared pixel by
pixel with the approved "after" shots: week (day), editor (night), run page (day) and analysis (night) are identical;
home, the timeline (both looks), the board and exports differ only in data (the program picked, today's date) and
one-pixel text offsets. The compare also caught two parts of the proposal the first merge missed (checkboxes and
radios in ink; time fields and text areas with the field edge); both were fixed with a failing test first.

## Not checked

Windows high-contrast mode, screen readers by ear, and real phones: the colours and sizes were measured in Chromium,
not looked at on a device.
