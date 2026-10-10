# Phase AC checks, 2026-10-10 Egypt time

The owner asked: "Fix rest of the items, and make a deep review on the website current status and fix any bugs or
improve any vision use ur skills while doing that". The review is `REVIEW.md` (12 findings and the open items from
earlier phases). This file records how each fix was proven. No new look was proposed: the review found consistency
gaps only, fixed inside DESIGN.md v3. Screens are in `screens/` (written by `ThePhaseACInTheBrowser`), with
made-up "Associate NN" data and a made-up Slack link.

## The twelve findings

| # | Finding | Fix | Test (failed first, then passed) |
| --- | --- | --- | --- |
| 1 | After signing in, or after picking a look, a crafted `next` such as `/<tab>/example.com` sent people off the site | One rule (`safe_next`) for every redirect: a path on this site, with no second slash, backslash or control character | `test_review_security.TheRedirects` |
| 2 | Two workbook caches shared by the server's threads raised KeyError and RuntimeError (34 errors in 8 threads) | A lock around every cache read and write; the workbook itself is read outside it | `test_review_crashes.TheCaches` (8 to 13 errors before, none after) |
| 3 | A password reset left the person's other sessions signed in | Each session carries a stamp of the password; a new password ends the other sessions; your own change keeps the device you changed it on; sessions from before the upgrade stay | `test_review_security.TheSessions` |
| 4 | `+ Add` opened on someone marked sick, with an error before anything was picked | Sick and leave go last and say so ("..., sick") | `test_review_rta.TheWhoList`, browser |
| 5 | The Week page's Associates tile was blank for an uploaded schedule | Counted from the week's own people (anyone with a shift) | `test_review_pages.TheWeekTiles` |
| 6 | A form's address reloaded showed the framework's "Method Not Allowed" | The site's own page: "This address opens only from its form." / "Go back, then send the form again." | `test_review_crashes.test_wrong_method_says_what_to_do` |
| 7 | A date such as 9999-12-31 in an address crashed the page (500) | Dates outside 2000 to 2099 are treated as no date | `test_review_crashes.test_far_dates_are_refused_not_crashed` (10 addresses) |
| 8 | Time fields were unstyled beside styled lists | One field style for time fields; under the label like the other fields; compact in the breaks grid | `test_review_polish.TheTimeFields`, before/after shots in both looks |
| 9 | "167 of 168" wrapped to two lines; "1 intervals" | "of N" smaller on the figure's line; singular and plural words | `test_review_pages.TheWeekTiles`, browser at 1366 px |
| 10 | `+ Add` title "Add to 10:00 to 11:00"; overtime falls outside the interval | "Add for 10:00 to 11:00", and "Add overtime for Associate NN" while Overtime is picked | `test_review_rta.TheTitle`, browser |
| 11 | The wallboard had no main region and showed the LOB's key | A main region; the LOB's name | `test_review_rta.TheNames` |
| 12 | Scrolling past a dialog's end scrolled the page behind | `overscroll-behavior: contain` on dialogs | CSS (Task 3) |

## Open items from earlier phases

| Item | Outcome | Test |
| --- | --- | --- |
| AB: text typed on the RTA could form a link in a Teams post | "[a](b)" can no longer form a link; ordinary brackets stay readable | `test_notify_posts` |
| AB: the Notifications page read each LOB one at a time | Two queries for every LOB (60 extra queries for 30 LOBs before) | `test_notifications_page.TheQueries` |
| AB: the "Post to the group" tick showed for changes that never post, and said "Post" in preview | Shown only for kinds the LOB posts; preview says "Show in the preview on the Notifications page"; without script the tick stays as before | `test_review_rta.TheTick`, browser |
| AA: an unreadable kept input made the Schedules page an error page | The page opens and the Channels panel says why and what to do | `test_review_pages.test_unreadable_input_keeps_the_schedules_page` |
| AA: a save written over more than 2 s showed as two saves | Grouped by the gap to the change before | `test_review_pages.TheSaves` |
| AA: "removes it and its 0 versions" for a failed run | "removes it for everyone"; flash "Deleted failed.xlsx." | `test_review_pages.test_failed_run_delete_wording` |
| AA: Phase W's screen cropped the summary line | `rta_intervals_at_target.png` shows the achievement block (screenshot target only) | `ThePhaseWInTheBrowser` |
| W: Back could return to the sign-in page | The Back trail never records or returns to it | browser (failed first on `/login`) |
| T: Resume accepted a readiness check or a can't-be-scheduled run when posted directly | One rule for the page and the route; refused with what to do | `test_review_pages.test_resume_refused_for_readiness_and_unschedulable` |
| V: a day with channel tabs and no channel plan listed everyone on the floor | One line: "No channel plan for this day yet: plan channels for it to count each channel." | `test_review_pages.TheChannelsWithoutAPlan` |
| P: program names of only dots made broken page links | A name needs a letter or a number | `test_review_polish.TheNames` |
| Q: uploads left in the staging folder by a crash were never swept | Swept after a day; a fresh one stays | `test_review_polish.TheStagingFolder` |
| XY: no `theme-color` | The browser's own bar takes each look's page colour | `test_review_polish.TheBrowserBar` |
| R: the left menu's picker waiting for Enter was not browser-tested | Tested with two programs | browser |

## Found while checking

- **Signing in dropped the page's program and date.** A page opened while signed out (for example a shared RTA link)
  came back after signing in without its query, so the person landed on another program or day. The sign-in now
  returns to the whole address (still checked by `safe_next`). Found by the new browser test; unit test
  `test_sign_in_returns_to_the_whole_address` failed first.
- **An unclear refusal.** Resuming a run the engine said cannot be scheduled said "it ended without one it could
  continue"; it now says the engine found the workbook needs a change, and to fix it and run it again (self-review).

## Final review (self-review)

One finding, fixed above (the resume refusal wording; the test was extended and a mutation check showed it fails
without the rule). The locks hold only dictionary work; every redirect goes through `safe_next`; no engine file,
protected workbook or `engine/regression_assets` file changed (`git diff 32d291f..HEAD` lists only `webapp/`,
`evidence/`, `docs/` and the ledger).

## Browser (Playwright, Chromium)

`webapp/tests/test_ui_playwright.py`, class `ThePhaseACInTheBrowser`:

- `+ Add` opens on someone present with no error after the first person is marked sick; that person is listed last as
  "..., sick"; picking Sick hides the tick; Overtime retitles the dialog and shows the tick; Break brings the title
  back (`screens/add_overtime.png`).
- Signing in from a `/week?program=...` link returns to that whole address, and Back then never shows the sign-in
  page (failed first: Back went to `/login?next=...`).
- The left menu's program picker: one arrow does not leave the page and says "Press Enter to show ..."; Enter opens
  the other program.
- The Week page's figures each stay on one line at 1366 px (`screens/week_tiles.png`).
- No sideways scroll at 390 and 320 px on the RTA, `+ Add`, Week, Schedules by week, a run's Schedules,
  Notifications, the wallboard and Runs (`screens/phone_week.png`); no page errors.

## Sweep and console, after the fixes

- Route sweep (`acsweep.py`, every route as admin, supervisor and planner, every form with bad input): 827 requests,
  no exceptions, no 5xx, nothing slow (before: one crash, the far date). The two access flags are by design, as in
  the review: a planner sees program names in the New schedule picker, and a supervisor sees People.
- Browser console crawl (`acconsole.py`, 81 pages): no page errors, no duplicate ids, every page has exactly one main
  region and an h1 (before: the wallboard's two addresses had no main region). The only failed loads are Google Fonts, which this sandbox
  blocks (the site falls back to its system fonts), and two `+ Add` previews at 00:00, which answer "Break has to fall
  inside Associate NN's shift" because nobody is on shift then (correct, see below).

## For the owner (not changed)

- `+ Add` at an hour when nobody is on shift opens on Break and says the break must fall inside the first person's
  shift. Opening on Overtime there would save a click; it is a behaviour change, so it waits for your yes.
- The items that stand from the review (coverage text on a failed run, the gate retried per queued run, Analytics
  read per request, the rare lost flash and the three engine-side lines) are unchanged; reasons in `REVIEW.md`.

## Suite, gate and package

- Website suite: `python -m unittest discover -s webapp/tests -t .`, 798 tests, OK (1 skipped), 23:24 to 23:55 Egypt
  time (31 min). After the self-review's wording change, `test_review_pages` and `test_runs` again: 162 tests, OK.
- Release gate inside the staged package (`tools/build_production_package.py`): GATE PASS, 77 suites, 1537 tests
  (2 skipped), 2 self-checks, call signatures and the undefined-name sweep; run alone, 23:56 to 00:13 Egypt time,
  memory in use at most 1.16 GB of 16 GB.
- `RC9_2_2_PRODUCTION_PACKAGE.zip`: 2371 files, 55,919,823 bytes, sha256
  `388b7dae1b52e9ebd6d2109a0223720415d42a1249c164ff47bc9a3a74ec670a`. Sent in two halves, `AC_half_A.zip`
  (28,500,000 bytes) and `AC_half_B.zip` (27,419,823 bytes); joined, they give the same sha256.
