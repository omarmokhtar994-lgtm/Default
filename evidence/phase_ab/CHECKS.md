# Phase AB checks, 2026-10-10 Egypt time

The owner saw samples 01 to 04 and said "Start the Teams/Slack notifications now". All four were built. This file
records how the built site was checked. Screens are in `screens/` (written by `ThePhaseABInTheBrowser`), made-up
"Associate NN" data and a made-up Slack link; the group is a fake that records what it receives.

## What was built, and the tests that pin it

| Part | Tests |
| --- | --- |
| Which group links are accepted (HTTPS on hooks.slack.com, or a Teams Workflows host); the post text for Teams (one Adaptive Card) and Slack (escaped, split under Slack's limits) | `webapp/tests/test_notify_posts.py` |
| The queue and sender: a LOB's changes wait its hold and go as one post per day; a change undone before posting is left out; preview sends nothing; a failed post is tried again after 1, 5 and 15 minutes, then shows why; one LOB's trouble never stops another; an RTA change never waits for a slow group; a restart loses nothing and sends nothing twice; redirects are not followed | `webapp/tests/test_notify_sender.py` |
| Every RTA change carries its kind and a group-safe text (an aux's why stays on the website); sick, unplanned leave and back to present are private; the day log itself is unchanged; a renamed program takes its group settings with it | `webapp/tests/test_notify_daybook.py` |
| The Notifications page: admins only; the link shown again only by its last four characters (never in the page, events, exports or flashes); the rule; Send test message; Remove link; the last post and recent posts | `webapp/tests/test_notifications_page.py` |
| The RTA: each line under Changes today says what happened to it; the break dialog and + Add carry one tick to keep a change off the group; an LOB that posts nowhere looks as before | `webapp/tests/test_notify_rta.py` |
| The day's breaks post: by shift, once a day, within two hours of its time, the evening before when asked, nothing for a day without a schedule, a day that cannot be read said once | `webapp/tests/test_notify_morning.py` |

## Final review (self-review)

One finding fixed: the group-link field was a password field, so a browser could offer to keep the link in its
password manager, which syncs it off the server. It is now a plain text field with autocomplete off
(`test_save_a_slack_link_then_it_is_masked`, failed first, then passed). Four minor points are listed in the report.

## Browser (Playwright, Chromium 141)

`webapp/tests/test_ui_playwright.py`, class `ThePhaseABInTheBrowser`, `test_notifications_page_and_rta_posts`: save a
Slack link and see it shown only by its end; Send test message reaches the group; on the RTA, one break move with the
tick on and one with it off; the sender posts the first only; Changes today shows "Posted to Slack, HH:MM" and "Not
posted: left out on the RTA"; the Notifications page shows the last post; no sideways scroll at 390 and 320 px; no
page errors. It failed first at 320 px (the right-hand column sized itself to the recent-posts table, 351 px) and
passed after the column was given `minmax(0, 1fr)`.

## axe-core 4.14 (WCAG 2.2 A and AA), the whole signed-in site

A crawl of 70 pages plus the sign-in page, in the night look and the day look (142 page-looks), including the
Notifications page with a saved link and posts.

| Check | Result |
| --- | --- |
| axe violations | none |
| Sideways scroll at 320 px and at 640 px | none (140 page-widths) |
| axe "incomplete" for colour contrast | 130 page-looks, from the background grid drawn with a gradient (as in Phases XY, Z and AA) |

## Not checked

The real Teams and Slack apps (no account here, and the network policy): the posts follow each app's documented
format (Teams' "Send webhook alerts to a channel" workflow with an Adaptive Card 1.4; Slack's Incoming Webhooks with
blocks), and Send test message checks the link on the owner's own group. Windows high-contrast mode, screen readers
by ear, and real phones.
