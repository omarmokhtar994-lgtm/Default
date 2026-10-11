# Phase AD checks, 2026-10-11 Egypt time

The owner asked for: a way to cancel a break (with a reason); Undo of the last change or two; Change several breaks
at once (cancel, move, set, back to plan); bulk changes held from the group until Send, with a question before
sending the same thing again; and a "Rescue the day" button that gives up at most 3 intervals (never below 50%) to
bring more of the other intervals to the target, interval by interval, not weighted by volume. The request and the
five answers are in `SPEC.md`; samples 01 to 06 (`samples/`) were approved with "Go". Screens are in `screens/`
(written by `ThePhaseADInTheBrowser`), with made-up "Associate NN" data and a made-up Slack link.

## What was built, and how it was proven

| # | Feature | Test (failed first, then passed) |
| --- | --- | --- |
| 1 | Cancel a break with a reason. The person stays on the floor. The reason is kept on the site and in the breaks export ("Cancelled because"), never in the group post. Back to plan brings it back | `test_cancel_break` (10), browser |
| 2 | Undo takes back your own last 2 changes on a LOB's day (each bulk change is one step). A change made again since is refused, naming who changed it | `test_undo` (7), browser (third press says why not) |
| 3 | Bulk changes (Fix breaks, Change several breaks, Rescue the day) wait at the top of the page for Send. Send again asks first, in a dialog (or on the page without script). Undoing a posted bulk change offers Send the correction. Single changes post as before | `test_held_posts` (7), browser |
| 4 | `+ Add` opens on Overtime, for the nearest shift, at an hour with nobody present on shift. Fix breaks applies as one change | `test_add_overtime_default` (3), browser |
| 5 | Change several breaks: pick people and a break, then cancel (with a reason), move by the same amount, set the same time or put back to plan. The effect shows before anything is kept, and anyone a change does not fit is listed with why | `test_bulk_breaks` (8), browser |
| 6 | Rescue the day (CP-SAT): see below | `test_rescue` (13), browser |

## Rescue the day

- **Model** (`webapp/rescue.py`): one choice per break not started, among its legal 5-minute starts. Priorities, in
  order: the most intervals at the week's target, then the fewest given up, then the fewest breaks moved, then the
  least moving. These are one weighted solve whose weights keep that order exactly.
- **Limits:** at most 3 intervals given up per day, counting those already lost before the press. A given-up interval
  never falls below 50% of demand. Every other interval stays at the target or no lower than now. Breaks keep their
  shift, order and the program's gaps. No language or channel drops below its minimum.
- **Recounted by the page:** every figure on the page (tiles, strips, given up, rescued) comes from the page's own
  count with the moves applied. A proposal the page does not confirm is not offered, and the page says so.
- **Tests:** small made-up days whose best answer is known by counting (give up 1, rescue 1; give up 2, rescue 2;
  nothing to give up, no rescue), plus the 50% floor, the language minimum, 5-minute steps inside the shift, the
  lost-so-far rule, and a made-short fixture day where every move passes the single-move checks and the gap rules.
- **Mutation checks:** four, each turning a test red: the 50% floor removed, the language rule removed, the gap rules
  removed, the 3-interval limit removed.
- **Solver settings, by two pre-registered A/Bs** (rules written before the runs, every case listed with its losses):
  - `RESCUE_PROBING_RULE.txt` / `_AB.txt`: probing off. 99 s became 77 s over 13 cases, and three stress days that
    were not solved now are.
  - `RESCUE_ONESOLVE_RULE.txt` / `_AB.txt`: one solve instead of two. 1,358 breaks moved became 222, with the same
    intervals at the target and the same total time.
- **Time:** days of up to 60 people finish proven best in 1.4 to 3.8 s; real LOBs here have up to about 49 people.
  Made-up 100 to 150 person days take 6.5 to 14 s; two of them end FEASIBLE (best found, not proven), which the page
  says.

## Found while checking

- **The bulk preview opened a person dialog over itself.** Change several breaks names its picked people `who`, which
  the day page also reads as "open this person's day". The dialog covered the Apply button. Found by the browser
  test; `test_bulk_breaks.test_the_people_picked_open_no_person_dialog` failed first. Change several breaks' `who`
  now means its picked people only, as Find a time's already did.
- **The cancel box's error showed at the top of the dialog**, far from the Why field it is about. It now shows under
  the field, tied to it (`aria-describedby`, `aria-invalid`); browser test and `screens/cancel_needs_a_reason.png`.
- **The browser fixture had no breaks** (a ready upload has none until breaks are planned); the class now plans
  them, as Phase AB's does.

## Browser (Playwright, Chromium)

`webapp/tests/test_ui_playwright.py`, class `ThePhaseADInTheBrowser` (each test on its own weekday, so one test's
changes never meet another's Undo):

- **Cancel a break:** the reason is asked for, next to the field. Once cancelled, the break shows as cancelled, the
  log keeps the reason, and Back to plan brings it back (`cancel_needs_a_reason.png`, `cancel_a_break.png`).
- **Change several breaks:** cancels 3 breaks. The bar shows "Not posted to the Slack group yet." with Send to
  group. After Send, Send again asks in a dialog: "Keep it as it is" sends nothing, "Send again" sends once more
  (`change_several_breaks.png`, `bar_send.png`, `send_again_asks.png`).
- **Undo:** after three moves, Undo twice; then the button is gone, and a third request says "Nothing of yours to
  undo on this day: Undo goes back 2 changes at most." The first move stays (`bar_undo.png`).
- **Rescue the day:** on a day made short, the preview lists the same moves as the plan; Apply keeps them as one
  change held for Send, and the page then counts what the plan said (`rescue_the_day.png`,
  `rescue_the_day_light.png`).
- **`+ Add`:** at an hour with nobody present, it opens on Overtime (`add_opens_on_overtime.png`).
- **Phones:** no sideways scroll at 390 and 320 px on the RTA, Change several breaks (empty and with a preview),
  Rescue the day, Fix breaks and today (`phone_rescue.png`, `phone_bar.png`). No page errors in any test.

## Sweep and console

- **Route sweep** (`acsweep.py` with the new views and bad values added, every route as admin, supervisor and
  planner, every form with nothing and with garbage): 872 requests, no exceptions, no 5xx, nothing slow. The same
  two access flags as in Phase AC, by design.
- **Browser console crawl** (`acconsole.py`, 83 pages): no page errors, no duplicate ids, one main region and an h1
  everywhere. Failed loads:
  - Google Fonts, which this sandbox blocks;
  - `+ Add` previews refused for a person with no shift, the designed answer, as in Phase AC.

  Rescue the day is the one page over the crawl's speed mark, at 1.9 s, because it runs the solver.

## For the owner (not changed)

- Rescue the day works the plan out each time its page opens (2 to 4 s on days of this size). Two people opening it
  at once each run it. A queue or a cache would only matter for much larger LOBs.
- The time field in the break dialog shows a clipped "AM" marker in some browsers' 12-hour display. It predates this
  phase; it can be styled with the other time fields if you want.

## Suite, gate and package

- Website suite: `python -m unittest discover -s webapp/tests -t .`, 852 tests, OK (1 skipped), 04:21 to 04:54
  Egypt time (33 min). Rescue the day's "no answer in the time" message changed after the suite had loaded the
  code, so `test_rescue`, `test_bulk_breaks` and `ThePhaseADInTheBrowser` ran again on the final code: 27 tests, OK.
- Release gate inside the staged package (`tools/build_production_package.py`): GATE PASS, 77 suites, 1537 tests
  (2 skipped), 2 self-checks, call signatures and the undefined-name sweep; run alone, 04:56 to 05:13 Egypt time,
  memory in use at most 1.11 GB of 16 GB (sampled every 5 s).
- `RC9_2_2_PRODUCTION_PACKAGE.zip`: 2405 files, 58,620,706 bytes, sha256
  `83f6c248db38fe03095f5f5dc84bb4b125b411cbac28f84d572e6af1841dde62`. Sent in two halves, `AD_half_A.zip`
  (29,700,000 bytes) and `AD_half_B.zip` (28,920,706 bytes); joined, they give the same sha256.
- No engine file, protected workbook or `engine/regression_assets` file changed in this phase.
