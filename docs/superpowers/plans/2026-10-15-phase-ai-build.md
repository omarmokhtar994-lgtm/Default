# Phase AI: the owner's list of 2026-10-15. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reported defects, add exam leave, runs by program with queue counts, pages instead of endless
lists, a tidy rest of the week, and one RTA calendar day that works in any time zone and from any start time.

**Architecture:** Defects get a failing test first (root causes found in `evidence/phase_ai/REQUESTS.md` and below).
The one calendar day stitches the schedule's days into one full RTA view in a window frame; every time shown or
typed is the chosen zone's clock (one request-wide clock offset), and the server turns typed times back into the
schedule's own zone before any change is kept, so posts to the group stay in the schedule's zone.

**Tech Stack:** Flask, Jinja, SQLite, vanilla JS, OR-Tools CP-SAT, unittest, Playwright.

**Spec:** `evidence/phase_ai/REQUESTS.md` (the owner's words, readings and answers).

## Global Constraints

- CLAUDE.md: engine untouched, failing test first, re-pin only for an owner-changed contract (say why), strict CSP,
  sentence case, "Associate NN" names, copyright line in every website file, Egypt time, push to the branch only.
- The owner said "go ahead fix everything" (2026-10-15): built without samples; screens of every changed page go to
  the owner with the package.

## Root causes found before the plan

- Board drag and drop: the board's twelve columns need about 1,318 px but the row box is 1,110 px, so the last
  columns hang outside their row and drops there miss it (Playwright: 6 of 36 drop points failed, all in the last
  three columns); the drop outline flickers on every child element (dragleave).
- "Same departments and names": the lists are per program (LOBs of one program share them, as Phase U set); what
  leaks is the RTA's With suggestions, which list every active user on the site.
- Channels on the Timeline: drawn only on the Channels tab; the Timeline never shows them.
- Wallboard: a page of its own with no Back.
- Runs: already seen by program; runs of other programs are hidden entirely, so nobody knows why they wait.

## Tasks

| # | Task | Files | Test |
| --- | --- | --- | --- |
| T1 | With suggestions: only people who can open the program | app.py | test_ai_fixes |
| T2 | Wallboard Back | wallboard.html | test_ai_fixes |
| T3 | Board drag and drop: the row holds every column; one board-level drop handler; no flicker; the drop says where | app.css, app.js | test_ui_playwright (every cell takes the drop) |
| T4 | Channels on the Timeline: coloured stretches on each bar, Phone / Chat / Email rows; a note when the day has no channel plan | day.html, app.css | test_ai_fixes |
| T5 | Hover: "in at" from the RTA's marks, worked so far without away time; the whole row answers | day.py, day.html, app.js | test_af_hover (re-pin: late login), test_ai_fixes |
| T6 | Exam leave: RTA status (whole shift), leave kind (TM then RTA), schedule cell; client shrinkage only | day.py, leave.py, versions.py, shrinkage.py | test_ai_exam |
| T7 | Runs by program; other programs only as "N running, N waiting" with your wait | app.py, dashboard.html | test_ai_runs |
| T8 | Pages of 20: runs, overtime offers, changes log, requests decided, notifications | app.py, templates, _macros.html | test_ai_pages |
| T9 | Overview: the rest of the week as one short row per day with a link to the details | _outlook.html, app.css | test_af_outlook |
| T10 | One calendar day: zone and day start on the RTA, every tab, changes kept in the schedule's zone | day.py, attendance.py, app.py, day.html, app.js | test_ai_window |
| T11 | The 11 tests that already failed before Phase AH: root cause each | tests, code | the same tests |
| T12 | Deep review: every agreed item of AF, AG, AH and AI, every page at 360 and 1440 px in both looks, console, route sweep | evidence | CHECKS |
| T13 | Suite, gate, package, report | | |

## T10 design (rulings)

- Window: anchor schedule date X, window start W (schedule minutes from X's midnight), frame f = minute - W in
  [0, 1440). Display clock = W + f + zone shift, shown by every time label in the request (one clock offset that
  `day._hm` and `attendance.hm` read). Cost if wrong: one helper.
- The stitched view has the full day view's shape (lanes, segments with their source date, breaks, activities,
  cells with ticks, languages, channel rows, tiles), so the Timeline, board, adherence, hover, Now panel, glance and
  target strip work unchanged on it.
- Rescue the day, Fix breaks and Change several breaks work on the schedule's own day that holds the window's start
  hour ... ruling: on the anchor schedule day X, times shown in the chosen zone. Cost if wrong: tools on a window.
- Every change posts the segment's own schedule date and a displayed time; the server subtracts the zone shift
  before calling the DayBook, so the journal, undo and group posts stay in the schedule's zone.
- The separate read-only zoned page goes; the program's operating-day start stays as one of the start choices.
- The start choice is kept per program for the session (switching tabs and days keeps it).
