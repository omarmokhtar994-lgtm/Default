# Phase V: Chat, Phone and Email planned per associate (2026-10-09)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, per CLAUDE.md). Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** after a schedule exists, the website places every associate on Chat, Phone or Email for each part of their
shift. It places breaks together with channels, shows live channel coverage on the RTA page, and warns, with fixes,
when coaching, a meeting, a break or an absence leaves a channel or a channel's language uncovered.

**Architecture:**
- The engine is untouched. The channel tabs live in the input workbook, and the engine ignores tabs it does not
  know.
- `webapp/channels.py` reads and checks them.
- `webapp/channel_people.py` keeps who can work which channel, per program.
- `webapp/channel_plan.py` is a CP-SAT model for one day: channels plus the breaks it may move.
- A plan is saved as a new version: a "Channel Plan" tab, plus the moved breaks on the Break Schedule tab.
- The RTA page counts channels from the people really on the floor (`day_view`), as it already counts languages.

**Tech stack:** Flask 3.1, SQLite, openpyxl, OR-Tools CP-SAT 9.15, Playwright (Chromium at
/opt/pw-browsers/chromium).

**Spec:**
- The owner's messages of 2026-10-09 (quoted below).
- The approved samples in `evidence/phase_v/samples/`: plan_channels, associate_channels, rta_channels,
  workbook_tabs, breaks_with_channels, upload_check_channels, rta_channel_warnings.
- The sample input workbook `evidence/phase_v/samples/channels_input_sample.xlsx`.

Owner, verbatim:
- "some programs handles different channels chat, phone, email same associates should rotate on those 3 channels
  my ask is to create 3 sheets in the input sheet we will assign the need per interval for each channel ... planned
  as well per each associate considering language ... schedules are built already ... no chanhe in that ... this
  can be done on the website only no need to add it in the engine and it can automatically plan same as for breaks"
- "3 channels should be covered by the requirements / We need to create language setup for channels yes with start
  end time as well / Not everyone can work all channels so we need somewhere to setup associates working channels /
  4 yes / Email is flexible yes, and lets setup email by 2 different ways if i didn't give u 30 mins requirements
  for emails we need another place where i can mention hours needed for each day and to be distributed
  automatically"
- "FYI this needs to be connected somehow with breaks as well"
- "1 can be changed based on choices / 2 website / 3 yea / 4 during some intervals we might have 1-2 associates
  covering sll channels so i need an option to tell the same to the tool to avoid invalid warning / And this some
  how needs to reflect in RTA view as well with warnings when no channel coverage due to extra coaching etc
  considering the language as well"
- "Go"

## Global Constraints

- CLAUDE.md rules apply.
- No engine change. Protected workbooks and `engine/regression_assets` keep their bytes.
- Tests are written first. A re-pin states its reason in the test. Validation fails closed and names the tab and
  row.
- Channels: Phone, Chat, Email. Letters P, C, E. All channels together: A.
- Planning step: 15 minutes, matching the validator's break alignment.
- Tab names follow the interval:
  - "Chat {n} Min", "Phone {n} Min", "Email {n} Min", where n is the program's interval.
  - "Email Hours" and "Channel Setup".
- Channel tabs add up to FT Wise. A mismatch is a warning, never a block and never a change to the schedule.
  All-channels times are not added up. There, no single channel may need more than FT Wise.
- A workbook with channel tabs must name its requirement tab: the Requirements Source instruction, or an engine
  alias ("FT Wise 30 Min", "FT Wise 60 Min", "FT Wise", "Required HC", "Requirements", "Forecast"). Otherwise the
  upload is refused, because the engine's fallback could read a channel tab as the requirement.
- Order when short: a per-workbook choice of the 6 orders, written "Phone > Chat > Email", with Strict or Balanced.
- Who can work which channel is kept on the website, per program. Someone not listed can work all three. A listed
  person needs at least one channel.
- Email Hours are placed outside all-channels times. Email 30 Min, when filled, is covered by all-channels people
  like any channel.
- Breaks never leave the engine's break rules (windows, gaps, edge margin, at most N at once). Breaks typed on the
  page never move. "Move breaks if it helps" is on by default, and each moved break costs, so few move.
- The same input gives the same plan. The solve runs with a deterministic limit (measured in V5).
- Real employee names never go into fixtures. Use "Associate NN".
- Time shown in Egypt time (UTC+3).

## Review Focus

1. A shift crossing midnight: the plan covers both sides, and the RTA counts the after-midnight part on the next
   day (V5, V7 tests).
2. A plan saved before a later shift edit or swap: plan rows outside the new shift are ignored and the page says
   "re-plan". They are never counted silently (V4, V7 tests).
3. A day with no channel tabs: the RTA, the booking preview and exports behave exactly as before (V7 test).
4. A break moved in RTA: the person's freed time takes the channel of the block before it (or after it, at the
   shift start). The channel's time during the new break is not counted (V7 test).
5. A Channel Setup tab missing but channel tabs present: these defaults are used and said in the check (V1 test):
   - minimum block of one interval
   - no maximums
   - Phone > Chat > Email, Strict
   - no language rows and no all-channels times

---

### Task 1 (V1): Channel inputs, `webapp/channels.py`

**Files:** create `webapp/channels.py`; test `webapp/tests/test_channels.py` (with the builder
`add_channel_tabs(path, ...)`).

**Interfaces:**
- Produces `read_channels(path: Path, step: int) -> Optional[Dict]`. It returns None when the workbook has no
  channel tab, otherwise:
  - `need`: `{ch: {day: {t: n}}}` (ch in "PCE"; Email only in interval mode)
  - `email_mode`: "interval" or "hours"
  - `email_hours`: `{day: {"hours": h, "languages": {lang: h}, "start": m, "end": m}}`
  - `rules`: `{"min_block": m, "max_run": {ch: m or 0}, "order": [ch, ch, ch], "strict": bool, "fair": bool}`
  - `languages`: `[{"channel", "language", "minimum", "start", "end", "days": set, "active"}]`
  - `blended`: `[{"days": set, "start", "end"}]`
  - `notes`: list of strings
- Produces `blended_at(setup, day: int, t: int) -> bool`.
- Produces `requirement_tab(path) -> Optional[str]`, which follows the engine: the instruction first, then the
  aliases.
- Produces `check_lines(setup, inputs, path) -> List[Tuple[str, str]]`, each line a (level in "ok", "info",
  "warn"; text) pair, matching the upload_check sample.
- [ ] Tests first:
  - Reading the sample tabs.
  - Each malformed cell is refused, naming tab and row: a negative need, a word in a grid, an unknown channel, a
    bad time, a bad day, an order that is not a permutation, Strict/Balanced misspelt, a minimum block not a
    multiple of 15.
  - Defaults when Channel Setup is missing.
  - Blended windows, including one wrapping midnight.
  - `requirement_tab` by instruction, by alias, and None.
  - `check_lines`:
    - add-up warnings outside blended times only
    - the blended single-channel check
    - Email Hours against FT Wise left after Chat + Phone, per day
- [ ] Run (`$PY -m unittest webapp.tests.test_channels -v`): expect failures, then implement, then expect a pass.
  Commit.

### Task 2 (V2): Upload refuses bad channel tabs; the schedule page shows the check

**Files:** modify `webapp/app.py` (the run upload route and the ready upload) and `webapp/templates/schedules.html`;
test `test_channels.py` (app class).

- [ ] Tests first:
  - An upload with channel tabs and no named requirement is refused, with the message naming the fix.
  - An upload with a bad Channel Setup row is refused, naming the row.
  - A good upload flashes "Channel tabs: N warnings".
  - `/runs/<id>/schedules` shows the "Channel tabs" panel with the check lines.
  - A workbook without channel tabs shows no panel.
- [ ] Implement, run, commit.

### Task 3 (V3): Who can work which channel (`webapp/channel_people.py`, `/setup/channels`)

**Files:**
- create `webapp/channel_people.py`
- create `webapp/templates/channel_setup.html`
- modify `webapp/store.py`: table `associate_channels` (program_id, name, channels text of letters, user_id,
  updated, unique (program_id, name))
- modify `webapp/app.py` and `base.html`: the menu link "Associate channels" under Manage
- modify `exports.py`: event `channels_changed`, shown as "Associate channels"
- test `webapp/tests/test_channel_people.py`

**Interfaces:**
- Produces `ChannelPeople(store)` with:
  - `skills(program_id) -> Dict[str, str]`: the letters per listed name
  - `skills_for_unit(key) -> Dict[str, str]`
  - `roster(program_id) -> List[(name, language)]`: from the program's latest version, plus anyone listed
  - `save(program_id, rows: Dict[str, str], user_id) -> int`: the number changed
  - `paste(program_id, text, user_id) -> int`: lines "Name, Chat, Phone, Email" with Yes/No, or Excel tabs
- Produces `can_work(skills: Dict[str, str], name: str) -> str`: "PCE" when not listed.
- [ ] Tests first:
  - Unlisted means all three.
  - Ticking none is refused.
  - A paste is all or nothing, naming the line, and refuses a name not on the roster or a word other than Yes/No.
  - Admins see every program; supervisors their own; planners get 403.
  - Each change is recorded in Exports' "Other actions".
  - A program's deletion removes its rows.
- [ ] Implement, run, commit.

### Task 4 (V4): A version carries its channel plan

**Files:** modify `webapp/versions.py`; test `test_channels.py` (versions class).

**Interfaces:**
- Produces `write_channels(src, dst, rows: Dict[(name, day), List[(start, end, ch)]])`. It replaces those
  person-days on the "Channel Plan" tab (headers: Associate, Day, Shift, Start, End, Channel).
- `read_week` adds `week["channels"]`, a list of `{associate, day, start "HH:MM", end "HH:MM", channel}`.
- Produces `channel_blocks(week, d, name) -> List[{start, end, channel}]`:
  - in minutes; after midnight reads +24h, as breaks do
  - blocks outside today's shift dropped, and `stale_blocks(week, d) -> List[str]` names them
- [ ] Tests first:
  - Round trip of rows.
  - Another person-day is untouched.
  - The independent validator still passes a version with the tab.
  - Overnight blocks.
  - A swapped shift's leftover blocks are reported stale, not counted.
- [ ] Implement, run, commit.

### Task 5 (V5): The planner, `webapp/channel_plan.py` (CP-SAT; load cpsat-engine-modeling first)

**Interfaces:**
- Produces `plan_day(people, setup, rules, day, carry=None, move_breaks=True, locked=frozenset())`:
  - `people`: `[{name, language, start, end, breaks: [(kind, start or None, minutes)], skills}]`
  - returns `{"blocks": {name: [(start, end, ch)]}, "breaks": {name: [starts]}, "moved": [(name, kind, old, new)],
    "status", "metrics"}`
- Produces `score_day(people, plan, setup, day) -> Dict`, an independent recount:
  - short hours per channel
  - language short hours
  - email placed
  - mid-stretch switches
  - long stretches per person
  - a rule check of every break
- Model:
  - Variables:
    - one x per person, 15-minute slot and channel the person can work
    - none in all-channels slots: there the person covers every channel they can work
    - one boolean per break candidate, at 15-minute starts inside window, margin and gaps
  - Constraints and costs:
    - Exactly one of the person's channels or a break in each slot, and at most max_concurrent people on a break.
    - A block shorter than the minimum is forbidden unless a break, the shift end or all-channels time cuts it.
    - The maximum run per channel is soft, 40 per window over it.
    - A channel change mid-stretch costs 2; a change at a break is free.
    - A moved break costs 5. Locked breaks are fixed.
    - Shortfall weights:
      - Balanced: language rows 200 per slot short; channels in order 100 / 60 / 30.
      - Strict: lexicographic weights, each above the most the next one down can lose that day.
    - Email Hours: total email slots, and per language, inside the window and outside all-channels times.
    - Fair spread: 1 per slot on a channel the person has had more of this week (`carry`).
  - Solve with a deterministic limit (`max_deterministic_time`) and the worker count measured in this task.
    Record the measurement in the ledger and in a test docstring.
- [ ] Tests first, on a small made-up day (16 associates):
  - Every slot has exactly one channel or a break.
  - Skills are respected.
  - No short block unless cut.
  - All-channels slots.
  - A language minimum is met when possible.
  - The strict order wins over Balanced on a set-up shortage.
  - Email Hours placed and in the window.
  - Breaks are inside the rules, and locked ones are unmoved.
  - The same input gives the same output twice.
  - Overnight shift.
  - `score_day` agrees with the model's own shortfall.
- [ ] Implement, run, commit.

### Task 6 (V6): The "Plan channels" page

**Files:**
- create `webapp/templates/channels.html`
- modify `webapp/app.py`: route `/schedules/<id>/channels`
- modify `webapp/store.py`: `channel_drafts`, like `break_drafts`
- modify `webapp/schedules.py`: `save_channels`, which writes breaks and channels into one new version, with one
  change row per person-day
- modify `schedules.html`: a "Plan channels" button when the run has channel tabs
- modify `app.css` and `app.js`
- test `webapp/tests/test_channel_page.py`

**Interfaces:**
- Produces `ScheduleBook.save_channels(schedule_id, user_id, draft, reason, use=False) -> (int, List[str])`.
- Produces the actions:
  - suggest (with `move` = 1 or 0)
  - edit: person, from, to, channel; refused outside the shift, on a break, or for a channel they cannot work
  - copy to days with the same shifts
  - save (reason, use)
  - discard
- [ ] Tests first:
  - GET shows a grid of P/C/E/B/L/A cells, coverage per channel and language per interval, and the facts line,
    matching the plan_channels sample.
  - Suggest fills the draft, and nothing is kept until save.
  - An edit is refused with its reason.
  - Save makes a version whose week has channels and whose moved breaks pass the validator.
  - The change log reads "Channels planned".
  - A program with no channel tabs gets a 404 with words.
- [ ] Implement, run, commit.

### Task 7 (V7): RTA channel coverage, warnings and fixes; booking preview

**Files:**
- modify `webapp/day.py` (`day_view(..., channels=None)`)
- modify `webapp/attendance.py`:
  - `page` passes channels
  - `channel_move`
  - `preview_item` adds channel effects and better times
- modify `webapp/store.py`: table `channel_moves` (program, shift_date, associate, offset, start, end, channel,
  user_id, at)
- modify `webapp/app.py`: `/day/channel`, `/day/channel/cancel`, `/day/activity/move`
- modify `day.html`, `app.js` and `app.css`
- test `webapp/tests/test_channel_day.py`

**Interfaces:**
- `view["channels"]` is None without channel tabs, otherwise:
  - `{"rows": [{name, cells: [{t, need, have, low, cls}]}], "langs": [...], "warnings": [{t0, t1, what, causes:
    [str], fixes: [{kind, text, form}]}], "now": {ch: have}}`
- Causes name the person, the kind and, for an aux, its With and Why (Phase T/U).
- Fixes, each applied by a POST that records and logs it:
  - a channel swap that keeps the person's other channel covered and respects skills and language
  - moving the aux to the nearest time that keeps every channel and language covered
  - moving a break inside the rules
- [ ] Tests first:
  - Coverage counts only people really on the floor: coaching, a break, absent and late are taken out.
  - Coaching on the only Arabic Chat person raises "no Arabic speaker on Chat" with that coaching's With and Why.
  - A blended evening with one person on break and one in a meeting raises "nobody on Phone, Chat or Email".
  - Each fix applied clears its warning, and the day log says who did it.
  - The booking preview names the channel drop and offers times that keep coverage.
  - A day without channel tabs gives a view and preview identical to before.
  - A moved break gives its freed time to the block before it.
- [ ] Implement, run, commit.

### Task 8 (V8): Break moves and re-plan respect channels

**Files:** modify `webapp/day.py` (`advice`, `replan`); test `test_channel_day.py`.

- [ ] Tests first:
  - The break advice text gives the channel effect ("Phone stays covered" or "Phone −1").
  - Re-plan from now never makes a move that creates a channel or language warning.
- [ ] Implement, run, commit.

### Task 9 (V9): Exports and the person's timeline

**Files:** modify `webapp/exports.py`: kind "channels", shown as "Channels planned and changed on the day". Modify
the person-day popup (`day.html` or `app.js`). Tests in `test_exports.py` and `test_channel_day.py`.

- [ ] Tests first:
  - Export rows: one per planned block and one per day change, with who and when.
  - The person popup lists "08:00 Phone · 10:00 Break · 10:15 Chat …".
- [ ] Implement, run, commit.

### Task 10 (V10): Browser check, screens, suite, gate, package, report

- [ ] Add a class `ThePhaseVInTheBrowser` at the end of `test_ui_playwright.py`. It walks:
  - the upload with channel tabs
  - Associate channels
  - Plan channels: Suggest, then Save
  - RTA warnings: book coaching, see the warning, apply the fix
- [ ] Screens go to `evidence/phase_v/screens`.
- [ ] Run the full website suite, then restore the screenshots.
- [ ] Run `run_tests.sh` (the gate), build the package, split it into halves, send them and report.
