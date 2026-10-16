# Handoff: carrying on in a new chat

© 2026 Omar Mokhtar. All rights reserved.

Written Thu 15 Oct 2026, 13:11 Egypt time, at the end of Phase AI; brought up to date at 18:30, end of Phase AJ, at 23:00, end of Phase AK, on Fri 16 Oct, 00:10, end of Phase AL, and at 03:05, end of Phase AM. A new chat reads `CLAUDE.md` (it loads by itself)
and then this file. Together they hold the rules, the owner's ways of working, where the work stands and how to
check it. What they cannot hold is the chat itself: when something here is not enough, the record is in git
(`git log`), the plans (`docs/superpowers/plans/`) and each phase's evidence (`evidence/phase_*/`).

## The owner and how they work

- Omar Mokhtar, the owner. Runs workforce planning and real-time (RTA) for call-centre programs (for example SAKS,
  NMG Tier 2). Sends requests as a numbered list, often typed fast on a phone: read for meaning, not spelling.
- Chat replies in caveman style (terse fragments, no filler, every technical fact kept). Code, commits, docs and
  evidence in plain normal prose, sentence case.
- Prefers efficiency: no check-ins between tasks, no "should I continue?". When the owner says go ahead, carry the
  whole phase through to the package without stopping ("Don't stop until u finish").
- Wants a final, working result: hunt for bugs before calling it done, and say plainly what was not done.
- Ask only about decisions that are the owner's (samples, behaviour changes, new dependencies, anything visual). Take
  the sensible default for the rest and record it as a ruling with what it costs if wrong.
- Times in Egypt time (Africa/Cairo). The container's clock is UTC.

## Skills at each step (owner, 2026-10-15)

Load each with the Skill tool at the step it covers; following it from memory does not count.

- Every fix and feature: systematic-debugging for any bug (root cause first); test-driven-development (a failing test
  first); verification-before-completion (evidence before saying anything is done).
- Each phase: writing-plans, then executing-plans, inline. subagent-driven-development and requesting-code-review only
  when the owner asks.
- Engine (CP-SAT): cpsat-engine-modeling with TDD for any engine change or diagnosis.
- Tests and Python: python-testing-patterns; property-based-testing (Hypothesis is a new dependency: ask first);
  python-error-handling and python-anti-patterns on changed code only; python-performance-optimization before long
  full-CPU runs.
- Website design: frontend-design, ui-ux-pro-max, and the account's design-taste-frontend, impeccable and design-md.
  New libraries and visual changes go to the owner as samples first.
- Website review before shipping: web-interface-guidelines on changed files; better-interface, better-accessibility,
  better-colors, better-layout, better-typography, better-ui, better-writing; web-quality-audit, accessibility,
  best-practices, performance, core-web-vitals. interface-review only on /interface-review.
- Browser checks: webapp-testing (Playwright screens) and playwright-cli.
- Security: security-and-hardening for sign-in, sessions, uploads, group links, secrets or outbound posts.
- Server logs: observability-and-instrumentation (a metrics stack is a new dependency: ask).
- Records: documentation-and-adrs in the repo's own layout (plans, evidence); changelog-generator for release notes.
- External reviews (for example ChatGPT): receiving-code-review.
- Motion only if an approved sample needs it: gsap-*, lenis, react-bits (ideas only, ported to plain CSS and JS).
- Other: graphify only on /graphify; find-skills to look for new skills; img2threejs only if asked.
- Style: caveman for chat replies; the Karpathy guidelines in CLAUDE.md for code.
- Plugins (owner, 2026-10-15): Superpowers (the superpowers:* process skills: brainstorming, writing and executing
  plans, TDD, systematic debugging, verification, finishing a branch); Headroom (headroom:peek and headroom:headroom
  to read large files and logs, such as app.py or the suite logs, in parts); burn (burn:burn, the session's cost,
  when asked or at the end of a phase); claude-code-setup (claude-code-setup:claude-automation-recommender, hooks and
  automation suggestions, which go to the owner before anything is set); security: the claude-security / Security
  Guidance plugin is not installed in these sessions, so security-review (on the branch's changes) and
  security-and-hardening stand in for it.

## Safety rules the owner set (still in force)

- The server's private key stays with the owner. Never ask for it, never send it, never put it in the repository or
  chat. Do not go looking for key, address or password details in old chats or files.
- Notification secrets (SMTP passwords, bot tokens, Teams and Slack links) live only on the server, never in the
  repository or chat. Passwords never on command lines, never stored or logged.
- Real employee names never in fixtures, samples or screens: made-up "Associate NN" names only.
- This session cannot reach the owner's Oracle server or Cloud Shell. The owner installs every package themselves.

## The project

- **Engine** (`engine/`, release RC9.2.2): an OR-Tools CP-SAT scheduler that builds a week's schedule from an input
  workbook. Untouched since the website phases began; protected files and folders are listed in `CLAUDE.md`.
- **Team Scheduler website** (`webapp/`): Flask, Jinja, SQLite (`store.py`), vanilla JS (`static/app.js`), one
  stylesheet (`static/app.css`), served by waitress behind Caddy on an Oracle Cloud Always Free server. Design rules:
  `webapp/DESIGN.md` (v4 "shift desk", three looks, Graphite night by default).
- Website rules: strict CSP (no inline script, style or event handlers); sentence-case copy; the line
  `© 2026 Omar Mokhtar. All rights reserved.` in the first 4 lines of every website file; CSRF on every POST.
- Pages: Home, RTA (`/day`: Timeline, Interval board, Adherence, Find a time, Overtime and VTO, Channels, Rescue the
  day, Fix breaks, Change several breaks), Overview, Wallboard, Handover, Weeks, Schedules, Runs, Leave and swaps,
  Analysis, Programs, Exports, Team, People, Departments and people, Notifications, Coaching, My week (associates).
- Branch: the session's designated branch (Phase AJ: `ccr-90ec94cc-a37tqk`, started from `claude/handoff-document-m6egz2`); no pull request unless asked.

## How a phase runs

1. The owner sends a list. Write `evidence/phase_xx/REQUESTS.md`: each item in their words, what it is read to
   mean, and the questions only the owner can answer. Send the questions; wait for answers.
2. Samples first for anything visual or a new library (`evidence/phase_xx/samples`).
3. Plan in `docs/superpowers/plans/YYYY-MM-DD-phase-xx-build.md`; "Rulings while building" at its end.
4. Build test first (a failing test, then the code). Never edit an old test to pass; re-pin only when the owner
   changed the contract, and say why in the test.
5. Checks, all on the final commit: the website suite, the browser tests, every page at 360 and 1440 px in both
   looks, the route sweep, the interface checklist, the release gate. Record them in `evidence/phase_xx/CHECKS.md`.
6. Package, split into parts, send them, and report in caveman style: what changed, rulings with their cost, what
   is known and left, Egypt times, screens.

## Where things stand (end of Phase AM)

- Phase AM is complete and pushed (branch `ccr-90ec94cc-a37tqk`):
  - Fix channels on the RTA's Channels tab (`DayBook.channel_fix_plan` / `apply_channel_fix`; `plan_day` gained
    `carry_in` and `keep`).
  - Download in the zone picked (`versions.zoned_copy`).
  - A Version pick on Weeks (`DayBook.page(version_id=)`).
  - Home and the run page read the version in use, else the engine's figures, else the version shown
    (`_run_figures`).
  - A finished run's outcome is stamped before its status.
  - Requests and answers: `evidence/phase_am/REQUESTS.md`; checks: `evidence/phase_am/CHECKS.md`; plan and rulings:
    `docs/superpowers/plans/2026-10-16-phase-am-build.md`.
- Package `RC9_2_2_PRODUCTION_PACKAGE.zip`, 2729 files, 93.66 MB, sha256
  `0aabe9d44f8003b92ebed8073bbe08d0e421cc9d17d2fdf7123f68435c4d0a79`, sent as AM_part_0 to AM_part_3.
  - It contains AK and AL.
  - Installing it is the owner's step.
- Check tools: `evidence/phase_am/tools/` (`am_screens.py` and `am_audit.py` stop the clock with
  `mock.patch("webapp.app.datetime", _Clock)`).
- Expected on Phase AM:
  - Suite halves: 624 and 559 tests OK (1 skipped). Browser tests: 77 OK.
  - GATE PASS with 1537 tests (2 skipped).
  - Page review: 0 problems. Sweep: 0 exceptions and 0 server errors.

## Earlier: end of Phase AL

- Phase AL is complete and pushed (branch `ccr-90ec94cc-a37tqk`): Email deep green `#2F7D5B` with a white E; the
  engine's MORE_CONSISTENT_CANDIDATE kept as "Tool, more consistent" (offered, never set in use by itself; finished
  runs get it once at start); a Fairness section on Plan channels (`webapp/channel_fair.py`). Requests, root cause and
  answers: `evidence/phase_al/REQUESTS.md`; checks: `evidence/phase_al/CHECKS.md`; release notes:
  `evidence/phase_al/RELEASE_NOTES.md`; plan and rulings: `docs/superpowers/plans/2026-10-15-phase-al-build.md`.
- Package `RC9_2_2_PRODUCTION_PACKAGE.zip`, 2693 files, 92.21 MB, sha256
  `4281a5eeb81a5626adc7c79543cf64733d41c63eb6e7af0801666f6a07cc1a8a`, sent as AL_part_0 to AL_part_3. The AK package
  was sent before it; installing either is the owner's step (AL contains AK).
- Next for fairness (owner's answers): the planner may weigh it later, the week first and the day where the week
  cannot, and coverage always wins. The view came first, as asked.
- Check tools: `evidence/phase_al/tools/`. Expected on Phase AL: 618 and 539 tests OK (1 skipped), 77 browser tests
  OK, GATE PASS with 1537 tests (2 skipped), page review 0 problems, sweep 0 exceptions and 0 server errors.

## Earlier: end of Phase AK

- Phase AK is complete and pushed (branch `ccr-90ec94cc-a37tqk`): channel colours D with letters on the Timeline,
  Times in on a schedule, Fix breaks / Rescue / Change several breaks on the 24 hours from "Day starts at", the Team
  manager role with associates assigned and approvals by team manager, and the Roles page (what each role may see and
  do). Requests and answers: `evidence/phase_ak/REQUESTS.md`; checks: `evidence/phase_ak/CHECKS.md`; release notes:
  `evidence/phase_ak/RELEASE_NOTES.md`; rulings at the end of `docs/superpowers/plans/2026-10-15-phase-ak-build.md`
  and in the ledger.
- Package `RC9_2_2_PRODUCTION_PACKAGE.zip`, 2663 files, 88.89 MB, sha256
  `708aa29419e5a543e0694aa066e752804e99ffe8202b47203f31c62d027d1afd`, sent as AK_part_0 to AK_part_3; installing it
  is the owner's step.
- Open for the owner: the C letter (white on Chat `#C2549F`) measures 4.15:1, under 4.5:1; `#B04A90` would give
  4.97:1.
- Check tools for a fresh container: `evidence/phase_ak/tools/` (replace phase_ai with phase_ak in the commands
  below; `route_sweep.py` takes the output path). Expected on Phase AK: 614 and 530 tests OK (1 skipped), 77
  browser tests OK, GATE PASS with 1537 tests (2 skipped), page review 0 problems, sweep 0 exceptions and 0 server
  errors.

### Phase AK decisions to remember

- `webapp/permissions.py` holds the catalogue (14 keys), the endpoint map and `allowed()`; `before_request` checks
  every mapped endpoint; admins always pass; a `manager_required` route missing from the map is admin-only. The role
  grid is read once per request (`g`), stored in `role_permissions`.
- `webapp/approvals.py`: an associate's team manager approves first; backups are admins and supervisors with
  `approve_tm`; an associate with no team manager is approved by any team manager of the program. Swaps keep
  `tm_a_id` and `tm_b_id` per side.
- `webapp/window_tools.py`: the three RTA tools run on the window view rebased to minute 0; moves carry
  `name|idx|minute|date`; people whose shift began before the window are not moved.
- Schedules in another zone are shown only; changes happen in the schedule's own zone.

## Earlier: end of Phase AJ

- Phase AI is installed on the server (owner, 2026-10-15).
- Phase AJ is complete and pushed (branch `ccr-90ec94cc-a37tqk`, from the handoff branch): overtime up to 4 hours,
  cover from outside the roster (a TM or support member counted in the intervals), channel colours after midnight.
  Requests, root causes and answers: `evidence/phase_aj/REQUESTS.md`; checks: `evidence/phase_aj/CHECKS.md`; rulings
  at the end of `docs/superpowers/plans/2026-10-15-phase-aj-build.md`.
- The first AJ package (sha256 `d2c474ae...`, items 1 to 3) is installed (owner, 2026-10-15). The second
  (items 4 and 5: cover language, overtime warns instead of refusing on the rest gap) is
  `RC9_2_2_PRODUCTION_PACKAGE.zip`, 2604 files, 79.64 MB, sha256
  `7fdba96a3eca83af0451fc0954211f18fba42ca855287b61eb1210ad4e585a30`, sent as AJ2_part_0 to AJ2_part_3; installing it is
  the owner's step. In Cloud Shell `$SERVER` is lost when the shell restarts: it is set again from history (`!114`
  on 2026-10-15), never asked for.
- Check tools for a fresh container: `evidence/phase_aj/tools/` (replace phase_ai with phase_aj in the commands
  below). Expected on Phase AJ: 502 and 581 tests OK (1 skipped), 77 browser tests OK, GATE PASS with 1537 tests
  (2 skipped), page review 0 problems, sweep 0 exceptions and 0 server errors.

### Phase AJ decisions to remember

- `OVERTIME_MAX` is 240 minutes, the longest "+ Add" length (owner, 2026-10-15). Overtime breaking the rest gap is
  kept with a warning (`_rest(..., refuse=False)`); call-ins still refuse; offers still keep the gap.
- Cover takes a language (`outside_cover.language`, `DayBook.cover_languages`).
- Cover from outside the roster: table `outside_cover`, `DayBook.add_cover` / `cancel_cover` / `covers`,
  `day_view(cover=...)` adds them to every 5 minutes (cell key `outside`), `page(cover=False)` leaves them out (the
  export's tick). Group posts go under the "overtime" kind.
- `channel_day._timelines` keeps last night's stretches after midnight in `runs` (the words in `timelines` stay with
  the day the shift starts).

## Earlier: end of Phase AI


- Phase AI is complete and pushed (last code commit 1a8e849, results 71e9b5c). The owner's 12 items are in
  `evidence/phase_ai/REQUESTS.md`; what was built, the checks and the rulings are in `evidence/phase_ai/CHECKS.md`
  and at the end of `docs/superpowers/plans/2026-10-15-phase-ai-build.md`.
- Package: `RC9_2_2_PRODUCTION_PACKAGE.zip`, 2689 files, 75.24 MB, sha256
  `cda2507cd5d4c5aebbda648563c803cc6870be31d25fce9efd2dd182c2354ea0`, sent as AI_part_0 to AI_part_2 (`dist/` is
  not in git; rebuild it with the command below if needed).
- **Installing it is the owner's step** (ask whether it is done). The key and the server are already set up in the
  owner's Oracle Cloud Shell (agreed 2026-10-14): never ask for them again. Their earlier `scp` and `ssh` commands
  are in Cloud Shell's history (`history | grep -E "scp |ssh "`); point there. The owner was given these steps: upload the three
  parts; `cat AI_part_0 AI_part_1 AI_part_2 > RC9_2_2_PRODUCTION_PACKAGE.zip`; check `sha256sum`; copy it to the
  server and sign in as in `deploy/ORACLE_SETUP_GUIDE.md` step 3; run
  `sudo bash /opt/scheduler/package/deploy/update.sh ~/RC9_2_2_PRODUCTION_PACKAGE.zip`; answer n to the safety gate
  if Cloud Shell may time out (the first run does it). If it prints `UPDATE STOPPED`, ask for that text only.
- Known and left as they are (owner told): a row holding two shifts in the RTA's 24 hours has one attendance box
  (it marks the first shift); four unused imports older than Phase AI (`BreakRefused` in app.py, `Any` and
  `Optional` in channel_people.py, `DAYS` in exports.py); the coaching workbook download took 1.7 s in the sweep.
- Older agreed backlog: `docs/NEXT_PACKAGE_BACKLOG.md` (most of it built in later phases; check before reusing).

### Phase AI decisions to remember

- The RTA's zone ("Times in") and day start ("Day starts at") are kept per program in the sign-in session; a new
  sign-in starts from Cairo at midnight. `window=operating` starts the day at the program's operating start.
- Timeline, Interval board and Adherence show the 24 hours from the start picked; the other RTA tools work on the
  schedule's day with every time in the zone picked.
- Every time is shown and typed in the zone picked; the server reads a form's times in the zone the form was shown
  in (its hidden `tz`), never the session's. Saved records, the change log, undo and group posts stay in the
  schedule's own time.
- Exam leave: an RTA status and a leave kind; approved leave still writes "Leave" on the schedule, and shrinkage
  counts it by kind (client shrinkage only).
- Runs are seen by program; other programs' runs show only as running or waiting. Long lists show 20 per page.

### Main code of Phase AI

- `webapp/clock.py`: `SHOWN` (minutes the page shows times ahead of the schedule), `shown()`, `moved_text()`,
  `to_schedule()`.
- `webapp/day.py`: `window_view()` (the 24 hours from a start, from the days that hold them), `hover_tips()` keyed
  per shift as (name, offset, start) and (name, offset).
- `webapp/app.py`: `_rta_choice`, `_own_zone`, `_typed`, `_say`, `_shown_data`, `_refused` for the zone; `_paged`
  with `webapp/paging.py` for pages of 20.
- `webapp/attendance.py`: `plain_hm` for internal times that are parsed again (never shifted).

## Running the checks in a fresh container

The scratch tools of earlier chats are gone with their containers; the ones used for Phase AI are kept in
`evidence/phase_ai/tools/`. From the repository root:

```bash
python3 -m venv /tmp/webvenv
/tmp/webvenv/bin/pip install -r deploy/requirements.txt pyflakes playwright==1.63.0
export PY=/tmp/webvenv/bin/python   # Chromium is at /opt/pw-browsers/chromium; do not run playwright install

# website suite in two halves at once (about 15 minutes), and the browser tests (about 11 minutes)
bash evidence/phase_ai/tools/suite_half.sh 0 2 /tmp/half0.log &
bash evidence/phase_ai/tools/suite_half.sh 1 2 /tmp/half1.log &
bash evidence/phase_ai/tools/browser_tests.sh /tmp/browser.log & wait
# the browser tests rewrite older phases' screenshots: put them back
git status --short | grep "evidence/" | grep -v phase_ai | awk '{print $2}' | xargs -r git checkout --

# release gate (engine; about 15 minutes) and the package (runs the gate again inside it)
PYTHON=$PY bash run_tests.sh
PATH=/tmp/webvenv/bin:$PATH PYTHON=$PY $PY tools/build_production_package.py
cd dist && split -b 26000000 -d -a 1 RC9_2_2_PRODUCTION_PACKAGE.zip XX_part_

# a review server with made-up data on 127.0.0.1:8767, then every page at 360 and 1440 px, and the route sweep
$PY evidence/phase_ai/tools/review_server.py /tmp/server.json &
$PY evidence/phase_ai/tools/page_review.py /tmp/server.json /tmp/screens
$PY evidence/phase_ai/tools/route_sweep.py /tmp/sweep.json
```

Expected on the Phase AI commit: 552 and 502 tests OK (1 skipped), 77 browser tests OK, GATE PASS with 1537 tests
(2 skipped), page review 0 problems, sweep 0 exceptions and 0 server errors (its 2 "leaks" are by design, and its
"None" hits are the word None written on purpose; see `evidence/phase_ai/CHECKS.md`).

Lessons: never put `unittest webapp.tests` in a `pkill` or `pgrep` pattern (it matches your own shell); tests that
read the real clock break when their date passes, so stop the clock with `mock.patch` as `test_channel_day` does.

## Phase history (each has a plan in docs/superpowers/plans and evidence in evidence/phase_*)

- A to D, E to H: engine fixes, audits, benchmarks and the production package (RC9.x).
- I to Q: the website: runs, results, control-room design, analytics, weeks, versions, exports, programs and LOBs.
- R: picked programs, + Add on the RTA, ready-schedule upload, a week's breaks. S: owner fixes. T: aux with who and
  why. U: departments and people. V: channels (Phone, Chat, Email) with a CP-SAT planner. W: floor fixes, interval
  target. X, Y, XY: website review and colours. Z: a week's schedules, channel needs, today's achievement.
- AA: overtime before or after, delete a schedule, schedules by week. AB: Teams and Slack group posts. AC: deep
  review fixes. AD: cancel a break, undo, held posts, change several breaks, rescue the day. AE: Slack Workflow text.
- AF: shrinkage in and out of office, day-off cancellations, rest of the week, time zones and the operating day.
- AG: v4 redesign, associates' accounts, leave requests and approval, shift swaps, My week.
- AH: one rule for an interval's standing by the week's target, hours needed table, 10-minute cushion.
- AI: the 12 items above.
- AJ: overtime up to 4 hours, cover from outside the roster, channel colours after midnight.
- AK: channel colours D, Times in on a schedule, RTA tools on the day's 24 hours, team managers, Roles.
- AL: Email deep green, the engine's more consistent schedule as a version, a channel fairness view.
- AM: Fix channels on the RTA, download in the zone picked, a Version pick on Weeks, percentages for before-breaks runs.
