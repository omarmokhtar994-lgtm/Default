# Phase AG build ("Shift desk", leave, swaps, My week) Implementation Plan

> **For agentic workers:** run inline (executing-plans), as CLAUDE.md asks. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the approved Phase AG samples: the v4 look, the RTA's first screen, Go to, associate accounts with My
week, leave requests and approval, shift swaps, and the two Phase AF leftovers.

**Architecture:** Server-rendered Flask and Jinja, one `app.js` and `app.css`, SQLite through `webapp/store.py`.
Leave and swaps live in their own modules (`leave.py`, `swaps.py`); an approval edits the schedule in use through
`ScheduleBook.change` and `set_in_use` (a new version, the old one kept). Associates are users with a role and a
roster name; one guard in `before_request` keeps them to their own pages.

**Tech Stack:** Python 3.11, Flask, openpyxl; self-hosted Archivo and Atkinson Hyperlegible Next (OFL); Phosphor
icons (MIT) as one SVG sprite; Playwright for browser checks.

**Spec:** `evidence/phase_ag/DESIGN_PLAN.md`, the samples in `evidence/phase_ag/samples/`, and the owner's answer
(2026-10-14): "Unblock any thing open anything change colors if needed u have all my approval for anything".

## Rulings (owner gave blanket approval; each says what it costs if wrong)

- Colours: the measured Phase Y tokens stay for now; the owner allows new colours (answer 7: "feel free to change colors
  ... show me first"), so T9 sends colour samples first and applies them only after the owner picks.
- Tab names stay (Timeline, Interval board, ...): people know them and tests drive them. Rescue the day, Change
  several breaks and Re-plan are grouped under "Fix the day" beside the tabs.
- Leave (owner's answer 3, 2026-10-14: "as per coverage and for balance ... covered by TM and RTA approval ... for
  public holiday and for planned leave"): types Planned leave and Public holiday; no fixed places a day, the
  coverage a request would leave decides (shown per day); a Planned leave balance per person per year, typed by
  managers, shown to the approvers (it warns, the approvers decide); two approvals: the TM (a supervisor or an admin)
  first, then the RTA (any other staff member of the program), whose approval changes the schedule.
- Associates: an admin or supervisor creates each account, linked to the person's name on the schedule; first sign-in
  changes the password (as for everyone). Associates see only My week, their requests and swaps.
- An approved leave or swap changes the schedule in use as a new version that is set in use (history and the earlier
  version kept, so it can be put back).
- A swap needs the colleague to accept, then a manager to approve (owner's answer 6). Both speak the same languages,
  unless swapping changes no language coverage; when their channels differ (Chat and Phone against all three), the
  swap is offered only if no channel's coverage changes; otherwise it cannot be sent.
- Every RTA tab in another zone: the stitched read-only view gains the language and channel rows; changes stay on the
  schedule's own day (zone-aware forms deferred again, said in the report).

## Global Constraints

- Strict CSP: no inline script, style or event handlers; CSP becomes `'self'` only (fonts self-hosted).
- Copy in sentence case; made-up "Associate NN" names; Egypt time unless a page's zone says otherwise.
- Nothing existing is removed; failing test first; re-pin a test only for an owner-changed contract, saying why.
- Every new website file starts with `# © 2026 Omar Mokhtar. All rights reserved.` (or the template/CSS/JS form).
- The engine is not touched.

## Review Focus

- An associate signed in: every page outside My week, their requests and swaps answers 403 or sends them to My week.
- A leave over a day off, or a range with days of another week: only working days change; the rest are said.
- Two managers approving the same request: the second sees "already decided", nothing applies twice.
- A swap whose colleague is on leave or breaks the rest gap: not offered; at approval the check runs again.
- Phone width 360 px: My week and its sheets with no sideways scroll; 16 px inputs.

---

### Task T1: the v4 foundation (type, fonts, icons, menu)
**Files:** `webapp/static/fonts/` (Archivo variable, Atkinson Hyperlegible Next, `OFL.txt`), `webapp/static/icons.svg`
(Phosphor sprite, `LICENSE-phosphor.txt`), `base.html` (no Google link; menu groups Today, This week, Requests,
Insights, Setup; labels unchanged), `app.css` (`@font-face`, headings Archivo width 112, figures width 75), CSP in
`app.py`, `webapp/DESIGN.md` v4; test `webapp/tests/test_ag_look.py`.
- Tests: no `fonts.googleapis` in any page; CSP has no external host; `/static/fonts/*.woff2` and `/static/icons.svg`
  served; the menu shows the group names in order; menu icons come from CSS (`a[href^="/day"]` etc.), markup of the
  links unchanged.

### Task T2: the RTA's first screen
**Files:** `webapp/day.py` (`now_panel(view, now, step, horizon=60) -> Dict`), `day.html` (day strip above the tabs;
Now column beside the timeline), `app.css`; test `webapp/tests/test_ag_rta.py`.
- `now_panel`: `{"on": int, "need": int, "short_until": str|None, "next": [{"t", "name", "what"}], "attention": [...],
  "shrinkage": {...}}`; next = breaks and shift starts within `horizon` minutes, sorted by time.
- Day strip: one cell per interval from `page.target.cells` (state class), past cells faded, now marker, hour ticks.

### Task T3: Go to (Ctrl K)
**Files:** `app.py` (`GET /goto?q=` JSON: pages, programs, people with today's shift, actions), `base.html` (button
and dialog), `app.js`; test in `test_ag_look.py`.

### Task T4: associate accounts and the guard
**Files:** `store.py` (users gain `is_associate`, `roster_name`), `app.py` (People page: role "associate" with a
roster name picked from the program's schedules; guard in `_before`), `auth.py` (`associate_allowed(endpoint)`);
test `webapp/tests/test_ag_associates.py`.

### Task T5: leave requests and approval
**Files:** `webapp/leave.py` (`LeaveBook`: `ask`, `cancel`, `decide`, `places`, `balance`, `impact`), `store.py`
(`leave_requests`, `leave_rules`, `leave_balances`), routes (`/me/leave`, `/requests`, `/requests/leave/<id>`,
`/requests/rules`), `requests.html`; test `webapp/tests/test_ag_leave.py`.

### Task T6: shift swaps
**Files:** `webapp/swaps.py` (`SwapBook`: `candidates`, `offer`, `answer`, `decide`), `store.py` (`swap_requests`),
routes (`/me/swap`, `/me/swap/<id>/answer`, `/requests/swap/<id>`), inbox rows; test `webapp/tests/test_ag_swaps.py`.

### Task T7: My week on a phone
**Files:** `app.py` (`GET /me`), `me.html` (today card with channel band and now/next, the week, requests, sheets for
leave and swap), `app.css`; test `webapp/tests/test_ag_myweek.py`.

### Task T8: Phase AF leftovers
**Files:** `day.py` (`stitch` gains language and channel rows), `day_zoned.html`, overview page (`_outlook`); tests
in `test_af_zones.py` (new cases) and `test_ag_overview.py`.

### Task T9: every page in the v4 look, and motion
**Files:** `app.css` (panels, tables, forms, buttons, chips, dialogs in both looks; now marker breathing, view
transitions, approve feedback, all under reduced motion), templates where a class is needed; browser check of every
page at 1366 px and 390 px in both looks.

### Task T10: wrap-up
Browser check and screens, full suite, release gate, package, evidence notes, report.
