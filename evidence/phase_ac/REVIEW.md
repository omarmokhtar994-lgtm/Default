# Phase AC: deep review of the website, 2026-10-10 Egypt time

Owner, 2026-10-10: "Fix rest of the items, and make a deep review on the website current status and fix any bugs or
improve any vision use ur skills while doing that". Skills used: web-quality-audit, better-interface with
better-accessibility, better-layout, better-writing, better-typography, better-colors and better-ui, webapp-testing,
systematic-debugging. Made-up "Associate NN" data throughout.

## Scope

- **Runtime sweep, the whole site:** every route (67) as admin, supervisor, planner, a planner without programs and
  signed out, plus bad values on every query and every POST sent with nothing, with garbage and without its token
  (`acsweep.py`: 825 requests).
- **Browser crawl, the whole signed-in site:** 81 page kinds, console, page errors, CSP, failed loads, landmarks,
  duplicate ids, timing (`acconsole.py`). axe-core 4.14 was clean on 142 page-looks in Phase AB.
- **Interface review (six better-\* domains):** the parts added since the Phase XY review: Schedules by week, the
  Week page switch, the run's Schedules page (Channels, Delete), the RTA's achievement block, `+ Add` and its tick,
  Notifications, plus the Week page tiles. Pages unchanged since Phase XY were not re-reviewed by eye.
- **Code review:** redirects, output escaping, file names, number parsing, sessions, shared caches.
- **Open items:** every "minor (deferred)" left by Phases P to AB, re-checked against the code as it is now.

## Measured results

| Check | Result |
| --- | --- |
| Server errors in 825 requests | 1 route: `/day?date=9999-12-31` (OverflowError) |
| Access | No leak. A planner without SAKS sees the program's name in the New schedule picker (open to everyone by design), never its schedules |
| Slowest response | 0.89 s (a week's summary export); no page over 1.5 s |
| Browser console | No page errors, no CSP violations. Google Fonts blocked by this sandbox's network only. Six 400s from `+ Add`'s preview (finding 4) |
| Headers | CSP, X-Frame-Options DENY, nosniff, Referrer-Policy same-origin; HSTS set by Caddy |
| Keyboard walk (new pages) | Every stop has a visible ring and a name |

## Findings, most severe first

| # | Severity | Finding | Evidence |
| --- | --- | --- | --- |
| 1 | HIGH (security) | Sign-in and the theme switch redirect off the site: `next=/<tab>/example.com` becomes `Location: //example.com`. A real sign-in link could land a team member on a look-alike page | `webapp/app.py:458` and `:482`; reproduced with the test client |
| 2 | HIGH | Two caches shared by the server's threads (input workbooks, channel tabs) evict without a lock: 34 crashes (KeyError, RuntimeError) from 8 threads, which would show as an occasional error page on the RTA when more than 8 workbooks are in use | `webapp/day.py:133-159`, `webapp/channels.py:366-466`; reproduced |
| 3 | MEDIUM (security) | A session stays signed in for up to 12 hours after an admin resets the password or the person changes it, so a reset does not lock out a lost laptop | `webapp/auth.py:29-38` |
| 4 | MEDIUM | `+ Add` opens with someone marked sick picked first, and greets the RTA with "Associate 006 is marked sick for this shift." | `webapp/app.py:2057`; seen in the browser |
| 5 | MEDIUM | Week page: the Associates tile is blank for an uploaded schedule (its figures have no count, and a missing value prints as nothing, not "–") | `webapp/templates/week.html:55`; screenshot |
| 6 | MEDIUM | A wrong-method request (for example reloading `/runs` after an upload) shows the framework's own "Method Not Allowed" page, outside the site and with no way forward | `webapp/app.py:2566` (no 405 handler) |
| 7 | MEDIUM | `/day?date=9999-12-31` crashes (date arithmetic past the calendar's end) | `webapp/app.py:1939` |
| 8 | LOW | Time fields (`+ Add`'s From, Plan breaks, Notifications) are drawn by the browser while every other field has the site's style | `webapp/static/app.css:139` |
| 9 | LOW | Week page: "167 of 168" breaks onto two lines in its tile; "1 intervals" | `webapp/templates/week.html:52-53` |
| 10 | LOW | `+ Add`'s title reads "Add to 10:00 to 11:00" and stays so when Overtime (before or after the shift) is picked | `webapp/templates/day.html` add dialog |
| 11 | LOW | Wallboard has no `<main>`, and says "No schedule for SAKS NMG Tier 2" with the key; the RTA's tab title also uses the key | `webapp/templates/wallboard.html`, `day.html` title |
| 12 | LOW | Dialogs scroll the page behind them when scrolled past their end on a phone | `webapp/static/app.css` `.dlg` |

## Open items from earlier phases, re-checked

| Item | Now |
| --- | --- |
| AB: in Preview only the tick reads "Post to the Slack group" | still true: fix |
| AB: `+ Add` shows the tick for kinds that never post | still true: fix |
| AB: text an RTA types could form a link in a Teams post | still true: fix |
| AB: Notifications page reads each LOB one at a time | still true: fix |
| AA: an unreadable input makes the run's Schedules page an error page | still true: fix |
| AA: changes saved over more than 2 s show as two saves | still true: fix |
| AA: Phase W's screen crops the summary line | still true: fix the screenshot target |
| AA: "removes it and its 0 versions" for a failed run | still true: fix |
| AA: `+ Add` title for overtime | finding 10 |
| W: Back can return to the sign-in page | still true: fix |
| T: Resume accepts a readiness check or a can't-be-scheduled run if posted directly | still true: fix |
| V: a day with channel tabs but no channel plan lists everyone on the floor | still true: one line instead |
| P: program names of only dots get a broken page link | still true: refuse such names |
| Q: `_incoming` leftovers after a crash are never swept | still true: fix |
| XY: no `theme-color` meta | still true: fix |
| R: the left-menu picker's keyboard wait is not browser-tested | still true: add the test |
| S: Copy to days marks unchanged days unsaved | already fixed (`app.py:1646`) |
| Q: a program with no scored week has no page | already fixed (`program_empty.html`) |
| Coverage panel on a failed run | stands: its text says why there is no data |
| Safety gate retried by every queued run | stands: a failed gate is deliberately never cached (`webapp/gate.py:9`), so a passing retry is never blocked |
| Analytics and dashboard read every run per request | stands: measured under 1 s |
| A flash lost when a preview finishes after a save; a Saturday-night shift on a week without the week before; spacing warning after Suggest; release verdict lines untranslated | stand: rare, already say what to do, or engine output |

## Vision

No new look is proposed. The review found consistency gaps inside the current design (findings 8 to 12) and no
place where the design itself fails a task. Fixes keep DESIGN.md v3, the strict CSP and sentence case.

## Verdict

Block until findings 1 and 2 are fixed; all twelve and the open items above go into the Phase AC plan.
