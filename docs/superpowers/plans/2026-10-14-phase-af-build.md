# Phase AF build (after the samples) Implementation Plan

> **For agentic workers:** run inline (executing-plans), as CLAUDE.md asks. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the approved Phase AF samples: channel stretches and changes, the two-view channel download, the RTA
timeline extras, shrinkage and the new statuses, day-off proposals and the week outlook, then time zones per page
and the operating day.

**Architecture:** Server-rendered Flask pages (Jinja, SVG for timelines), one `app.js` and `app.css`, SQLite through
`webapp/store.py`. New logic sits in the module that owns the data (`day.py`, `channel_day.py`, `channel_page.py`,
`attendance.py`, `exports.py`); routes stay thin in `app.py`.

**Tech Stack:** Python 3.11, Flask, openpyxl, OR-Tools (unchanged), Playwright for browser checks.

**Spec:** `evidence/phase_af/OWNER_NOTES.md` (sections A to F, "Samples answered") and the samples in
`evidence/phase_af/samples/`.

## Global Constraints

- Strict CSP: no inline script, style or event handlers; positions come from SVG attributes or CSS classes.
- Copy in sentence case; made-up "Associate NN" names in tests and samples; times in Egypt time unless a page's
  zone drop-down says otherwise.
- Nothing existing is removed (owner, 2026-10-14: "dont remove any feature currently exist").
- Failing test first for every behaviour; re-pin a test only when the owner changed the contract, saying why.
- Every new website file starts with `# © 2026 Omar Mokhtar. All rights reserved.` (the release gate checks it).
- The engine is not touched.

## Review Focus

- Overnight shifts (16:00 to 07:00): stretches, hovers and drags must work past midnight (minute > 1440).
- A person with no channel plan for the day: the RTA lane says so instead of drawing nothing.
- An absent person (Sick, Unplanned leave, Public holiday): no stretches, no drag, counted in out-of-office shrinkage.
- 30-minute and 60-minute programs: the 6-interval rule for day-off proposals counts the program's own intervals.
- Zones with summer time: the offset is taken for the date shown, never a fixed number.

---

### Task C2: each associate's channels on the RTA, as stretches
**Files:** `webapp/channel_day.py` (`_timelines` gains structured runs), `webapp/templates/day.html` (Channels tab),
`webapp/static/app.css`; test `webapp/tests/test_af_channels_rta.py`.
- `channel_view(...)["runs"]: Dict[str, List[Tuple[int, int, str]]]` per person: (start, end, letter or status word),
  one entry per stretch, beside the existing text `timelines`.
- Drawn as an SVG row per person (rect + letter/name), the existing `ch-*` colours, under the warnings.
- Test: a person on Phone 16:00 to 18:00 then Break 1 gives `(960, 1080, "P"), (1080, 1095, "Break 1")`; the page
  shows one `ch-P` stretch for that hour block.

### Task C1: Plan channels as stretches
**Files:** `webapp/channel_page.py` (`grid` gains `runs`), `webapp/templates/channels.html`, `webapp/static/app.js`;
test in `webapp/tests/test_channel_page.py`.
- The per-quarter table becomes one SVG stretch per run; each stretch is a focusable link that fills the existing
  edit form (who, from, to, channel). The table stays reachable as "Show quarter hours" (nothing removed).

### Task C3: change a channel from the RTA
**Files:** `webapp/attendance.py` (`channel_preview(program, on, name, start, end, letter)`), `webapp/app.py`
(`POST /day/channel-preview` JSON), `day.html` dialog, `app.js`; test `webapp/tests/test_af_channels_rta.py`.
- Click a stretch: dialog with channel, from, to; Preview returns the warnings the change would raise and the fixes
  `channel_day` already proposes; Apply posts the existing `/day/channel` `swap` (journal, Undo, group posts).

### Task C4: download the channel plan, two views
**Files:** `webapp/channel_export.py` (new: `channel_workbook(week, rules, draft_or_version) -> BytesIO`),
route `GET /schedules/<id>/channels.xlsx`, a button on Plan channels; test `webapp/tests/test_af_channel_export.py`.
- Tabs: Read me; per working day a table (Associate, Language, From, To, Channel, Minutes) and a timeline tab
  (a row per person, a column per quarter hour, cells filled in the channel's colour with its letter); Week
  (hours per person and channel).

### Task D2/D3: what hovering shows
**Files:** `webapp/day.py` (`hover_lines(seg, now) -> List[str]`, `break_lines(seg, b) -> List[str]`), `day.html`
(`data-tip` on shift bars and breaks), `app.js` (one card element shown on hover and focus), `app.css`.
- Shift: start, end, length, worked so far, left until logout, breaks taken of planned. Break: since the last break
  (or shift start), from shift start. Same lines in the interval view's titles.

### Task D4: drag a break, then confirm
**Files:** `app.js` (pointer drag on break rects, 5-minute snap), `day.html` (confirm dialog); uses
`POST /day/break-advice` and `POST /day/break` as they are; test `webapp/tests/test_ui_playwright.py` (new case).
- Release asks "Change <break> from Y to Z?" listing each warning from break advice; Yes posts the move.

### Task D6: today at a glance
**Files:** `webapp/day.py` (`glance(view, target, channels) -> List[Dict]`), `day.html`; test in
`webapp/tests/test_af_glance.py`. Six tiles: on shift now of planned, short now, above demand, language gaps,
channel warnings, achieved of intervals.

### Task E2/E3: Task and Public holiday
**Files:** `webapp/day.py` (`STATUSES`, `ABSENT`, `AUX`), `webapp/notify.py` (Public holiday private like Sick),
exports; test `webapp/tests/test_af_statuses.py`. Task asks who with and why like the other aux; Public holiday is
a whole-shift absence.

### Task E1: shrinkage in and out of office
**Files:** `webapp/shrinkage.py` (new: `out_of_office(view, week, day, mapping) -> Dict`), program settings
(`ProgramBook` options key `shrinkage`), `/setup/programs` form, RTA tiles; test `webapp/tests/test_af_shrinkage.py`.
- Sutherland = (unplanned + planned + sick) / scheduled, days off left out; client adds public holiday; planned
  leave read from the schedule; in office keeps today's measure; the mapping defaults to non-billable aux in office.

### Task F1/F2: proposed day-off cancellations
**Files:** `webapp/day.py` (`dayoff_proposals(view, week, day, rest_hours, minimum=6) -> List[Dict]`), Rescue the
day panel; test `webapp/tests/test_af_dayoff.py`.
- Group short intervals into shift windows from the Shift Library; a proposal covers at least 6 short intervals of
  the program's interval; how many people (the window's largest shortfall), the shift (matching the person's day
  before or after when possible) and up to 5 candidates; rule bends (rest, days in a row, weekly hours) said; then
  overtime per interval for what is left.

### Task F3/F4: the rest of the week
**Files:** `webapp/attendance.py` (absences for later days allowed), `webapp/week.py` outlook table, `week.html`;
test `webapp/tests/test_af_outlook.py`. Per later day: known absences, short hours, overtime needed, days off to
cancel (F1 per day).

### Task Z1: the schedule's zone at upload (A5)
**Files:** `webapp/store.py` (runs gain `tz`, default `Africa/Cairo`), upload form, schedule page edit; test
`webapp/tests/test_af_zones.py`.

### Task Z2: times in any zone on every page, and the operating day (D5, D1, A4)
**Files:** `webapp/clock.py` (`shift_minutes(day, minutes, from_zone, to_zone) -> int` by the date's offsets),
`webapp/day.py` (a window view stitched from two schedule days), RTA, Week and Schedules pages (a zone drop-down,
default Egypt), program setting or workbook "Operating day start"; test `webapp/tests/test_af_zones.py`.
- A day in the picked zone is that zone's day: the window is stitched from the schedule's days around it.
- The operating day shows the program's start to the next day's start (16:00 to 07:00 when no shift runs later).
