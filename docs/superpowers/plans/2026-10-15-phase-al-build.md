# Phase AL: Email colour C, the engine's more consistent schedule as a version, a channel fairness view. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task,
> inline (the owner's choice). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner's three items of 2026-10-15 (night) with the answers given: Email colour option C; the steadier
week the engine writes beside its schedule kept as a version; a fairness view of who works which channel, for the
week first and the day.

**Architecture:** The colour is two CSS tokens. The steadier week is a third version kept from a finished run's files
(`Schedules.ensure_consistent`), with its steadiness read from the engine's `BUSINESS_OUTCOME.json`. Fairness is a new
module `webapp/channel_fair.py` that counts each person's 15-minute slots per channel from the same plan the Plan
channels page shows, and a section on that page.

**Tech Stack:** Flask, Jinja, SQLite, unittest, Playwright.

**Spec:** `evidence/phase_al/REQUESTS.md` (the owner's words, sample al01, the root cause and the answers).

## Global Constraints

- CLAUDE.md: engine untouched; failing test first; re-pin only for an owner-changed contract, saying why; strict CSP;
  sentence case; "Associate NN" names; the copyright line in the first 4 lines of every website file; CSRF on every
  POST; Egypt time; push to the session's branch only.
- Owner's answers: Email option C, `#2F7D5B` with a white E. Fairness: (1) both same share and turns; (2) the week
  mainly, the day where the week cannot; (3) coverage wins; (4) a fairness view first, the planner unchanged; (5)
  compared only among people with the same channels and the same language.
- Not answered, ruled on the recommended side: the more consistent version is offered, never set in use by itself;
  finished runs get it once when the website starts. The C letter's 4.15:1 stays (the owner's colour).

## Review Focus

1. A run whose more consistent workbook failed the validator or lost coverage: no version is kept. Test in Task 2.
2. With nothing in use, the week still opens on "Tool, after breaks", never on the more consistent version (the RTA's
   `pick_version` and the Schedules list's version shown). Test in Task 2.
3. Starting the website twice adds the more consistent version once. Test in Task 2.
4. A person alone in their group (no one with the same channels and language) is listed, not compared, and never
   flagged. Test in Task 3.
5. A break inside a channel stretch is not counted as channel time, and does not end a turn on that channel. Test in
   Task 3.

---

### Task 1: Email colour C

**Files:** Modify `webapp/static/app.css` (`--ch-email: #2F7D5B`; the E letter and `.ch-E` ink white like P and C;
`--ch-email-ink` and `.tl-ch-t.e` go), `webapp/templates/day.html` (no `e` class on the letter), `webapp/DESIGN.md`.
Test: `webapp/tests/test_ak_colours.py` (re-pin, with the reason: owner's 2026-10-15 choice of al01 option C),
`webapp/tests/test_markup_xy.py` if it pins the Email hex.

- [ ] Re-pin the colour tests to `#2F7D5B` and a white E; run; see them fail.
- [ ] Change the tokens and the template; run the colour, markup and AK day tests; commit.

### Task 2: The more consistent schedule as a version

**Files:** Modify `webapp/runs.py` (`consistent_schedule(run_id) -> Optional[Tuple[Path, Dict]]`: the
`*_MORE_CONSISTENT_CANDIDATE.xlsx` outside `debug/` whose entry in `BUSINESS_OUTCOME.json`
`independent_validation.alternative_exports` has role `MORE_CONSISTENT_CANDIDATE`, status `PASS` and
`coverage_no_worse` true, with that entry's `consistency`; `keep_schedules` and `backfill_schedules` call
`Schedules.ensure_consistent`), `webapp/schedules.py` (`ensure_consistent(run, path, consistency) -> Optional[dict]`:
kind `tool_consistent`, label "Tool, more consistent", file `tool_consistent.xlsx`, `checks["consistency"]` holds the
engine's before and after; once per run; `week_list` shows `tool_after` over it), `webapp/attendance.py`
(`pick_version` order unchanged for it), `webapp/templates/schedules.html` (its line says "steadier start times: 66 h
to 53 h of start-time changes, 60 to 59 different starts"). Test: `webapp/tests/test_al_consistent.py`.

- [ ] Failing tests: a finished run whose results hold a passed candidate gets three versions, the third "Tool, more
  consistent", not in use, with the engine's figures on the Schedules page; a failed or coverage-losing candidate
  gives two; `backfill_schedules` twice adds it once to a run that already had two versions; with nothing in use,
  `pick_version` and `week_list` choose "Tool, after breaks".
- [ ] Implement; run with test_versions, test_schedules_by_week, test_attendance; commit.

### Task 3: Fairness counts

**Files:** Create `webapp/channel_fair.py`: `fairness(week, rules, draft, skills, language_rows, d) -> Dict` with
`{"week": [group], "day": [group]}`; a group is `{"label": str, "people": [row], "even": {letter: share}}` and a row
`{"name", "minutes": {letter: int}, "share": {letter: float}, "gap": float | None, "longest": int, "longest_day": str,
"furthest": bool}`. Letters P, C, E and A (all channels at once). Minutes come from the plan the page shows
(`channel_page.current`), breaks taken out (`channel_page._at` order: a break slot is not channel time). `gap` is the
largest difference, in percentage points, between the person's share and the group's even share; `furthest` marks
the largest gap in a group of 2 or more when it is 10 points or more. `longest` is the longest time on one channel in
one day, counting through breaks. Groups are people with the same channels (`can_work`) and the same language.
Test: `webapp/tests/test_al_fairness.py`.

- [ ] Failing tests: two people with the same channels and language, one all Phone, one half Phone half Chat: shares,
  even share, gaps 25 and 25 points, the first marked; a 30-minute break inside Phone counts 30 minutes less and the
  turn runs through it; a person alone in their group has `gap` None and is never marked; the day table counts day d
  only, the week every day; a draft day counts instead of the version's.
- [ ] Implement; run; commit.

### Task 4: The fairness section on Plan channels

**Files:** Modify `webapp/app.py` (`plan_channels` passes `fair=fairness(...)`), `webapp/templates/channels.html` (a
section "Fairness" after the coverage: the week first, then the day picked; per group a table: person, minutes and
share per channel, gap from even, longest on one channel; the furthest from even says so in words; a note that the
planner and coverage are unchanged), `webapp/static/app.css` only if a table needs it. Test: in
`webapp/tests/test_al_fairness.py`.

- [ ] Failing test: the page shows "Fairness", "This week", the day's name, a group label, and "furthest from even"
  for the marked person.
- [ ] Implement; run with test_channel_page; commit.

### Task 5: Reviews, checks and the package

- [ ] Website review skills on the changed pages; security-review on the branch; the fixes they find, each with its
  test.
- [ ] Suite halves, browser tests, page review, route sweep, gate in the package; CHECKS.md; release notes; handoff;
  package parts; report.

## Rulings while building (each with what it costs if wrong)

- Fairness counts the schedule's channel plan (the version and its unsaved draft), not the RTA's changes on the day.
  Cost: a second source later.
- "All channels at once" is its own column, not shared out to P, C and E. Cost: one rule.
- The furthest from even is marked at 10 points or more. Cost: one number.
