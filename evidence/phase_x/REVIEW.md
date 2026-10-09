# Website interface review (Phase X), 2026-10-09 22:18 Egypt time

Review only: nothing in the website has changed. The owner approves the samples in `samples/` before any fix is
built ("U can change things as much as u need but show me to approve").

## Scope and coverage

- **Scope:** the whole signed-in website (`webapp/`): 49 pages reached from the menu (Home, Overview, every RTA tab
  and dialog, Weeks, Schedules and the shift editor, Plan breaks, Analysis, Programs, Exports, Team, People,
  Departments and people, Associate channels, LOBs and defaults, handover, wallboard, coach) plus sign-in and the
  error pages, in the light and the dark look, at 1280 px, 320 px and 200% zoom.
- **Stack:** Flask and Jinja templates, one stylesheet (`webapp/static/app.css`, tokens on `:root` with a light
  block), one script (`webapp/static/app.js`), strict CSP (no inline script or style), native `<dialog>`.
- **Project documents read:** `CLAUDE.md` (project rules), `webapp/DESIGN.md` (control-room design: tokens, type,
  layout). No CONTRIBUTING or design-system docs exist.
- **Data:** the Phase W test workbook ("Associate NN" names), served by a review copy of the site; no real names.
- **Not in scope:** security headers, page speed and SEO (a separate site-quality audit), and the engine (unchanged).

| Domain | Evidence inspected | Result |
| --- | --- | --- |
| Accessibility | axe-core 4.14 (WCAG 2.2 A/AA) on 49 pages x 2 looks; keyboard walk of 7 pages (90 stops each); Shift+Tab walk on 5 pages; accessibility tree of the RTA timeline; `app.js` dialogs, pickers and refreshes; live regions in the templates | 7 findings |
| Layout | 49 pages at 320 px and at 200% zoom (640 px): sideways scroll and elements outside the window; 320 px screenshots of Home and the RTA timeline | 1 finding |
| Writing | every template, `app.js` strings, error handlers and flash messages in `app.py` | 3 findings |
| Typography | type rules in `app.css` (sizes, units, line-heights), form fields under 16 px | 2 findings |
| Colors | axe contrast pairs per element, contrast computed for every status fill with white and the dark ink, colour-blind check of the four status colours (dataviz palette validator) | 2 findings |
| UI | transitions and animations in `app.css` (named properties, reduced-motion guards), view transitions, hover after a tap (Chromium touch emulation) | Clear |

What already works, measured: no page scrolls sideways at 320 px or at 200% zoom; every keyboard stop shows a focus
ring; dialogs are native and keep focus inside; result messages are announced (live regions); the four status
colours stay apart for colour-blind readers (worst pair ΔE 11.6, target 8); axe found only 3 kinds of failure in 98
page runs.

## Findings

| # | Severity | Domain | Location | Now | Proposed | Why |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | HIGH | Accessibility | `static/app.js:307-318` (attendance), `:95-101` (Program, Day, Measure), `:656-661` (left menu picker) | Each picker acts on `change`. With the box focused, one Down arrow saved Associate 022, and on a second run Associate 024, as Unplanned leave (the option after Present) and logged it; the Measure picker reloaded the page on one arrow | A pick with the mouse or a tap acts at once, as today. With the keyboard, arrows only preview; Enter saves, Esc puts the old value back, a short note says so (sample 1) | WCAG 3.2.2 On Input: on Windows, Chrome and Edge change a closed list with the arrow keys, so a keyboard user looking through the choices records an absence by accident |
| 2 | HIGH | Accessibility | `static/app.js:536-539`, the New run form at `templates/dashboard.html:65` | Home reloads every 30 s while anything runs or waits. After 29.7 s the chosen workbook was gone and "Upload a ready schedule" went back to "Build the schedule" | Stop the reload once the form is touched and say "Updates paused while you fill in this form"; update the running schedule in place, as the run page already does (sample 2) | WCAG 2.2.1 Timing Adjustable; a run lasts up to an hour, so starting a second schedule in that hour loses what was picked |
| 3 | HIGH | Accessibility | `static/app.css:106-108` (sticky top bar), per-anchor fixes at `:712` and `:874` | Shift+Tab landed fully under the top bar on 9 of 100 stops in the shift editor and 1 on the interval board (18 more partly) | `html { scroll-padding-top: 72px }` and delete the two per-anchor rules it replaces (sample 3) | WCAG 2.4.11 Focus Not Obscured: a keyboard user cannot see the cell they are on |
| 4 | HIGH | Colors | `static/app.css:548` (`.tc`), `:586` (`.chip small`), `:848-849` (`.bp-strip`), `:433-434` (`.wk`), light tokens `:47-49` and `:62-64` | Light look: white on teal 2.75:1 (RTA numbers, 46 a day; Plan breaks strip), white on amber 2.16:1 (break badges), white on red 3.93:1 (computed: the test data has no red cells); over-staffed week cells 4.23:1 and their counts 3.57:1 (4.17:1 dark) | One role token `--on-status: #0E1A2B` for text on status fills in both looks (6.35:1 teal, 8.07:1 amber); light `--over` #887AE8 (4.99:1) and `--gap` #DF574F (4.67:1); counts at full opacity. axe after the change: 0 failing nodes on all 5 pages, both looks (sample 4) | WCAG 1.4.3 Contrast; `--on-accent` is used outside its role (text on the accent button) |
| 5 | HIGH | Writing | `templates/with_setup.html:18`, `app.py:969-971` | "Remove the department and its people" removed Quality and its 4 people in one click; the page said so afterwards, with no undo | A check first: "Remove Quality and its 4 people?", what it means, "This cannot be undone", buttons "Remove Quality and 4 people" and "Keep Quality", in the site's check-before-saving style (sample 5) | Destroys many items at once with neither confirmation nor undo |
| 6 | HIGH | Writing | `app.py:2285-2289`, `:258`, `templates/error.html:3` | A planner opening a program they are not given reads "This page is for admins." (also shown to supervisors on pages they can open); 404 reads "There is nothing here." with "Back to runs" | "SAKS, NMG Tier 2 is not one of your programs. Your account opens only the programs given to you. Ask an admin to add this one." with Go to Home; manager pages "Only admins and supervisors can open this page."; 404 "This page does not exist. The link may be old." (sample 6) | The error misleads and names no way to recover; "runs" is no longer the menu's word |
| 7 | MEDIUM | Accessibility | `templates/base.html:15-17`, `<main>` at `:60` | The 20th Tab press is the first inside the page, on all 7 pages walked (top bar, New schedule, program picker, 13 menu links) | "Skip to the page" as the first link, shown on focus, jumping to `<main id="main">` (sample 7) | WCAG 2.4.1 Bypass Blocks is met by landmarks, but sighted keyboard users cannot use landmarks |
| 8 | MEDIUM | Layout | `static/app.css:600-601`, `:526-529`; `templates/day.html:128-129` | At 320 px every RTA timeline name shows as "Associ…": the 250 px name column also holds slot, language and the attendance box | Phones only: the name on its own line, tags and box under it (sample 8) | Marking attendance by name on a phone needs the name; the full name is only one tap away, but on every row |
| 9 | MEDIUM | Typography | `static/app.css:529` (11 px), `:826-827` (15 px) | Attendance boxes use 11 px and 15 px text | 16 px on phones (sample 8) | iPhones zoom the whole page into form fields under 16 px. Not verified on an iPhone here |
| 10 | MEDIUM | Colors | light `--covered`/`--short` at `static/app.css:48`, `:63`, used by `span.cell` `:267-268`, `.stagebar` `:185-186`, `.tk` `:575-576`, `.bp-strip` on phones `:860`, ring arcs `:158-161` | Teal 2.75:1 and amber 2.17:1 against the white panel where the cell carries no number (week wall, stage bars, 5-minute ticks) | A 1 px edge in `--dim` (6.25:1 against white) on teal and amber marks, light look only; or darker fills, which changes the look (owner's choice) (sample 9) | WCAG 1.4.11 Non-text Contrast |
| 11 | MEDIUM | Accessibility | `templates/day.html:133` with the break buttons at `:139` | Each timeline lane is `role="img"` and holds focusable `role="button"` breaks (axe nested-interactive, 224 nodes). Chrome 141 still exposes all 81 buttons; browsers that flatten images do not | `role="group"` on the lane, keeping its label | Children of an image are presentational in ARIA: screen readers outside Chrome may not reach the breaks |
| 12 | LOW | Writing | `templates/day.html:265` | Every board row has a link named "+ Add" | Add the interval to the name for screen readers only: "+ Add<span class="sr-only"> to 09:00</span>" | A links list shows many identical "+ Add" |
| 13 | LOW | Accessibility | flagged: `templates/week.html:95`, `templates/day.html:239`; the same box at `week.html:64`, `:84` and `day.html:95`, `:210`, `:217`, `:248` | Sideways-scrolling tables have no name and no tab stop (axe scrollable-region-focusable); Chrome 141 lets Tab reach them, Safari does not | `role="region"`, an `aria-label` and `tabindex="0"` on these boxes | Keyboard users in every browser can scroll them, and screen readers name them |
| 14 | LOW | Typography | `static/app.css:81` and the type rules throughout | Every font size is in px | rem, with the same sizes at the default 16 px | A browser's text-size setting has no effect |

## Verification

Passed (commands run against the review copy at 127.0.0.1:8765, Chromium 141.0.7390.37):

- `audit.py`: crawl, axe-core 4.14 (tags wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa) on 49 pages x light and dark;
  overflow at 320 px and 640 px: 0 of 96 page runs scroll sideways or put an element outside the window.
- `checks.py`: keyboard walk (90 Tab stops on 7 pages; every stop has a visible ring; date fields checked by
  screenshot), Shift+Tab walk (5 pages), Home refresh (33 s with a filled form), arrow key on the attendance and
  Measure pickers, accessibility tree of the RTA timeline (81 break buttons exposed in Chrome), hover after a tap
  (Chromium touch emulation: no hover left behind), targets under 24 px with a neighbour inside 12 px (none that
  matter).
- `contrast.py`, `verify_ink.py`: the failing pairs per element, and 0 failing nodes after the proposed colour change on
  /day, /day board, /week, /schedules/2/week and /schedules/1/breaks in both looks.
- Department removal and the 403 and 404 pages, reproduced in the browser (`dept.py`, `more.py`).
- The four status colours in the dataviz palette validator (all pairs): colour-blind separation passes in both looks.

Not verified: hover left behind after a tap on a real iPhone (emulation shows none); the iPhone zoom on fields under
16 px (a documented Safari behaviour, not run here); screen readers other than Chrome's accessibility tree.

## Verdict

**Block:** six HIGH findings (1 to 6). Every domain was inspected; none is "Not reviewed".
