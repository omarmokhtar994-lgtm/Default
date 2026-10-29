# Handover to ChatGPT: Team Scheduler

© 2026 Omar Mokhtar. All rights reserved.

Written Fri 16 Oct 2026, about 03:30 Egypt time, by Claude at the end of Phase AM. It stands on its own: paste it
whole into a new ChatGPT chat. If you can read the repository, `CLAUDE.md` and `docs/HANDOFF.md` hold the same rules
in more detail, and `git log` is the full record.

## 1. Who you are working for

- **Omar Mokhtar, the owner.** Runs workforce planning and real-time (RTA) for call-centre programs, for example
  "SAKS, NMG Tier 2".
- **How requests arrive.** As numbered lists, often typed fast on a phone. Read them for meaning, not spelling. Photos
  of the screen are common.
- **Replies.** Terse and plain: short fragments, no filler, every technical fact kept. Code, docs and commit messages
  are written in normal prose and sentence case.
- **Ask only about decisions that are his:**
  - anything visual (show a sample first);
  - behaviour changes;
  - new dependencies.

  For everything else, take the sensible default and say so, as "Ruling: what I decided, and what it costs if
  wrong".
- **No check-ins between steps.** Once he says go, finish the whole piece of work through to the package, then report.
- **Times in Egypt time** (Africa/Cairo, UTC+3 in summer).

## 2. Rules that never bend

- **Secrets.** Never ask for, store, print or search for the server's private key, passwords, SMTP passwords, bot
  tokens, or Teams and Slack links. They live only on the server or with the owner. He installs packages on the
  server himself.
- **Names.** Real employee names never go into fixtures, samples, screenshots or docs. Use made-up "Associate NN"
  names only. His photos show real names: do not copy them anywhere.
- **The scheduling engine** (`engine/`, release RC9.2.2, OR-Tools CP-SAT) is protected and has been untouched through
  all website work. These workbooks keep their exact bytes:
  - `AE_AR_B2B.xlsx`
  - `Cricut_Voice_RC9_1_READY_SKELETON.xlsx`
  - `NMG_SP_RC9_1_READY_FIXED.xlsx`
  - everything in `engine/regression_assets`

  Never regenerate or fake baseline results.
- **Tests.**
  - Write a failing test first, then the code.
  - Never weaken validation or edit a test just to make it pass.
  - Re-pin a test only when the owner changed what it measures, and say why inside the test.
- **Never hide errors** or silently change the roster or demand numbers.
- **The release gate** is `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`. It runs inside the package build.

## 3. The product

- **Team Scheduler website** (`webapp/`):
  - Stack: Python Flask, Jinja templates, SQLite (`store.py`), vanilla JS (`static/app.js`) and one stylesheet
    (`static/app.css`).
  - Serving: waitress behind Caddy, on an Oracle Cloud Always Free server.
  - Design rules: `webapp/DESIGN.md`. Three looks: Graphite night (the default), light, and Ocean.
- **Website rules:**
  - Strict CSP: no inline script, inline style or inline event handlers. Data goes in `data-*` attributes; JS lives
    in app.js.
  - Copy in sentence case.
  - The line `© 2026 Omar Mokhtar. All rights reserved.` within the first 4 lines of every website file.
  - CSRF on every POST.
- **Pages:**
  - Home (runs list, latest week).
  - RTA (`/day`), with these tabs: Timeline, Interval board, Adherence, Find a time, Overtime and VTO, Channels (with
    Fix channels), Fix breaks, Rescue the day, Change several breaks.
  - Overview, Wallboard, Handover.
  - Weeks (grid, Hours needed, Version pick), Schedules (versions, edits, Times in, download), Runs.
  - Leave and swaps, Analysis, Programs, Exports, Team.
  - People (accounts, team managers), Roles (what each role may do), Departments and people, Notifications,
    Coaching.
  - My week (for associates).
- **Key modules:**

| File | What it holds |
| --- | --- |
| `webapp/app.py` | All routes; `before_request` enforces role permissions |
| `webapp/attendance.py` | `DayBook`: the RTA day, every change journaled with Undo (`action(..., bulk=True)` makes one Undo step), Fix breaks, Rescue the day, Fix channels |
| `webapp/day.py` | The day and window views the RTA draws |
| `webapp/channel_plan.py` | The website's own CP-SAT channel planner (not the engine) |
| `webapp/channel_day.py` | Channel counts and warnings on the RTA |
| `webapp/channel_fair.py` | The fairness view on Plan channels |
| `webapp/schedules.py`, `webapp/versions.py` | Schedule versions read from and written to Excel |
| `webapp/runs.py` | Runs the engine, keeps results and versions |
| `webapp/permissions.py` | 14 permissions per role (Planner, Team manager, Supervisor; Admin has all) |
| `webapp/approvals.py`, `webapp/leave.py`, `webapp/swaps.py` | Approvals by team manager, with backups |
| `webapp/window_tools.py` | The RTA tools on the 24 hours from "Day starts at" |

## 4. How a piece of work runs here

1. Write the owner's items in `evidence/phase_xx/REQUESTS.md`, in his words, with what each is read to mean and the
   questions only he can answer. Send the questions and wait.
2. Make a sample first for anything visual (`evidence/phase_xx/samples`).
3. Write a plan in `docs/superpowers/plans/YYYY-MM-DD-phase-xx-build.md`, with "Rulings while building" at its end.
4. Build test first.
5. Run the checks on the final commit:
   - the website suite, in two halves;
   - the browser tests (Playwright);
   - every page at 360 and 1440 px in both looks;
   - the route sweep;
   - the interface reviews;
   - the release gate.

   Record them in `evidence/phase_xx/CHECKS.md`.
6. Build the package (`tools/build_production_package.py`, which runs the gate).
7. Split the package into 26 MB parts, send them, and report: what changed, rulings and their costs, what is known
   and left, the sha256, and the install commands.

## 5. Where things stand (Fri 16 Oct 2026, 03:30)

All work is on branch `ccr-90ec94cc-a37tqk` (head 069d07e). Every phase is pushed.

| Phase | What it did | Package |
| --- | --- | --- |
| AJ | Overtime up to 4 hours. Cover from outside the roster (team manager or support member), counted in intervals and languages. Channel colours after midnight. Overtime that breaks the rest gap is kept, with a warning. | first package installed, second sent |
| AK | Channel colours on the Timeline with P, C and E letters. "Times in" on a schedule. Fix breaks, Rescue the day and Change several breaks work on the 24 hours from "Day starts at". The Team manager role, with approvals by team manager (backups, both team managers for a swap, where each request waits). An admin Roles page. | sent |
| AL | Email deep green `#2F7D5B`. The engine's `MORE_CONSISTENT_CANDIDATE` kept as the version "Tool, more consistent" (offered, never set in use by itself). A Fairness view on Plan channels (share and turns, week then day, same channels and language). | sent |
| AM | Fix channels in one click on the RTA (the planner re-plans from now; breaks held; coverage first, then fairness; preview, Apply all, one Undo). Download in the zone picked. A Version pick on Weeks. Percentages for "Before breaks only" runs (Home follows the version in use). A race fixed: a run's outcome is now stamped before it shows as finished. | sent, not yet installed |

**Latest package:** `RC9_2_2_PRODUCTION_PACKAGE.zip`, 2729 files, 93.66 MB, sha256
`0aabe9d44f8003b92ebed8073bbe08d0e421cc9d17d2fdf7123f68435c4d0a79`, in parts AM_part_0 to AM_part_3. It contains AK
and AL.

**Last checks:**
- Website suite: 624 and 559 tests OK (1 skipped). Browser tests: 77 OK.
- GATE PASS: 77 suites, 1537 tests (2 skipped).
- Page review: 0 problems. Route sweep: 0 errors.

**Install, in the owner's Google Cloud Shell, after uploading the parts.** `!114` restores `$SERVER` from history;
never ask for the address.

```
!114
cat AM_part_0 AM_part_1 AM_part_2 AM_part_3 > RC9_2_2_PRODUCTION_PACKAGE.zip
sha256sum RC9_2_2_PRODUCTION_PACKAGE.zip
scp -i ~/ssh-key-2026-10-07.key RC9_2_2_PRODUCTION_PACKAGE.zip $SERVER:~
ssh -t -i ~/ssh-key-2026-10-07.key $SERVER 'sudo bash /opt/scheduler/package/deploy/update.sh ~/RC9_2_2_PRODUCTION_PACKAGE.zip'
```

## 6. Open items and known limits

- **Fairness in the planner itself.** The owner's answers: the week mainly, the day where the week cannot; coverage
  always wins. Not built yet; the view and Fix channels came first.
- **Fix channels limits:**
  - It plans today's own shifts. Last night's people are counted but not moved; tomorrow's early shifts are not
    planned.
  - It works in 15-minute steps from the next quarter hour.
  - It gives a channel to people on the floor who have none planned.
  - Someone who works several channels gets Email only inside the day's Email hours.
- **Chat letter contrast.** White C on Chat `#C2549F` is 4.15:1, under WCAG's 4.5:1. `#B04A90` would give 4.97:1. It
  is the owner's colour: change it only if he says so.
- **Narrow screens.** A long workbook name with no spaces makes the Schedules page's Delete box 9 px too wide at
  320 px. It predates these phases; a one-line `overflow-wrap` fix.
- **Bulk team manager form.** "Set the team manager of several associates" stops at the first associate outside the
  user's programs. Only a hand-made request can do this.
- **Wording.** The approval message still says "the TM" while the pages say "team manager".
- **Old unused imports.** Three remain, for example `BreakRefused` in app.py. Left alone on purpose.

## 7. If you will change code

- **Set-up:** Python 3.13 venv with `deploy/requirements.txt`, pyflakes and `playwright==1.63.0`. Chromium is at
  `/opt/pw-browsers/chromium` in the Claude environment.
- **Tests:** `python -m unittest webapp.tests.<module>`.
- **Fixtures:**
  - `webapp/tests/fakes.py` stands in for the engine runner. Stems in the workbook name pick what it writes:
    `VERSIONED`, `CONSISTENT`, `BEFOREONLY`, `REAL`, `SHORTFALL`.
  - Real anonymised weeks are in `fixtures/real_runs/`.
- **Stopping the clock in tests:** `mock.patch("webapp.app.datetime", _Clock)` (from `webapp/tests/test_af_outlook.py`)
  sets the website's clock to Wednesday 14 Oct 2026, 10:00.
- **Check tools:** in `evidence/phase_am/tools/`: review server, page review, route sweep, screens, audit, and the
  suite and browser-test scripts.
- **Your first step:** give the owner your plan and questions in his style, then build test first.
