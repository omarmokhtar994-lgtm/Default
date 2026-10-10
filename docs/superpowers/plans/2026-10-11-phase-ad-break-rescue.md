# Phase AD: break rescue, cancel, bulk changes, undo and held posts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The RTA can cancel a break, change several breaks at once, rescue a day by giving up at most 3 intervals,
undo your own last 2 changes, and hold bulk changes from the group until Send.

**Architecture:** A day-change journal (`day_actions`) snapshots the day's record tables around each RTA change, so
any change (single or bulk) can be undone exactly; bulk changes carry the journal entry's id into the group queue,
whose items wait as `held` until Send. Rescue the day is a CP-SAT model in a new `webapp/rescue.py`, checked
against the page's own `day_view` before anything is shown.

**Tech Stack:** Flask 3.1, Jinja2 (strict CSP), vanilla JS, SQLite, OR-Tools CP-SAT 9.15, Playwright.

**Spec:** `evidence/phase_ad/SPEC.md` and the approved samples in `evidence/phase_ad/samples/`.

## Global Constraints

- Engine untouched; protected workbooks and `engine/regression_assets` untouched.
- Strict CSP (no inline script, style or event handlers); sentence case; DESIGN.md v3 (actions ink; teal, amber,
  red, violet only for state; `button.danger` for destructive).
- Do not modify or delete tests to pass; re-pin only when this phase changes the measured contract, with the reason.
- Times in Egypt time (UTC+3). Real names never in fixtures (Associate NN).
- Limits from the owner: Undo goes back 2 changes, your own only; Rescue gives up at most 3 intervals in the whole
  day counting those already lost, never below 50% of demand; interval compliance, every interval the same.
- Release gate: `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`.

## Review Focus

1. Two RTAs on one LOB: undoing my change after a colleague changed the same person must refuse, not overwrite
   theirs. Task 2 `test_undo_refuses_when_someone_changed_it_since`.
2. A bulk change undone before Send must never reach the group, and neither may its undo lines. Task 3
   `test_bulk_undone_before_send_posts_nothing`.
3. Rescue on a day where nothing can be rescued (or 3 intervals are already lost and no spreading helps) offers no
   moves and says why, never a plan that lowers the day. Task 6 `test_no_rescue_when_it_cannot_help`.
4. A cancelled break between two others must not stop Fix breaks moving them (the long gap is on purpose). Task 1
   `test_fix_breaks_moves_around_a_cancelled_break`.
5. A refused move in the middle of Rescue's apply keeps what was done and stays one undo step. Task 6
   `test_rescue_apply_stopping_midway_undoes_as_one`.

---

### Task 1: Cancel a break

**Files:** Modify `webapp/store.py` (actual_breaks gets `cancelled integer not null default 0`, `why text not null
default ''`, migrated), `webapp/day.py`, `webapp/attendance.py`, `webapp/exports.py`, `webapp/app.py`,
`webapp/templates/day.html`, `webapp/static/app.js`, `webapp/static/app.css`; Test `webapp/tests/test_cancel_break.py`.

**Interfaces:**
- Produces: `day.CANCELLED = "cancelled"` (an `actual` value meaning the break is cancelled); `day_view` leaves a
  cancelled break out of `seg["breaks"]` and lists it in `seg["cancelled"]` (dicts with idx, kind, minutes, start);
  `DayBook.cancel_break(program, on, name, idx, why, user_id, now=None) -> None`; route `POST /day/break/cancel`
  (program, date, associate, idx, why) answering JSON like `/day/break`.

- [ ] **Step 1: failing tests:** `test_cancel_keeps_them_on_the_floor` (cancel Associate 006's Break 1: the cells it
  covered gain one on the floor; `seg["cancelled"]` holds it; day log "Break 1 cancelled (HH:MM)");
  `test_cancel_needs_a_reason` ("Say why the break is cancelled."); `test_started_break_cannot_be_cancelled` (today,
  now past its start: "That break has started: it cannot be cancelled."); `test_back_to_plan_brings_it_back`;
  `test_group_post_has_no_reason` (notify item text "Break 1 at HH:MM cancelled", the why absent);
  `test_breaks_export_says_cancelled` (Taken "Cancelled", last column "Cancelled because" = the why);
  `test_fix_breaks_moves_around_a_cancelled_break` (Review Focus 4); `test_dialog_has_cancel_and_close`
  (break dialog: `button.danger[data-cancel-break]`, a Why field, and its close button reads "Close").
- [ ] **Step 2:** run `$PY -m unittest webapp.tests.test_cancel_break` — Expected: failures.
- [ ] **Step 3:** implement. `check_break` ignores cancelled neighbours; `replan`/`advice` skip the gap maximum across
  a cancelled break; `_records` maps cancelled rows to `CANCELLED`; the timeline draws a cancelled break as a dashed
  outline (`rect.brk.cancelled`, focusable, opens the dialog with only Back to plan and Close).
- [ ] **Step 4:** run it with `test_day`, `test_exports`, `test_notify_daybook`, `test_ui_day*` — re-pin the breaks
  export header (new column, reason in the test).
- [ ] **Step 5:** commit "Phase AD task 1: cancel a break".

### Task 2: The change journal and Undo

**Files:** Modify `webapp/store.py` (table `day_actions`: id, program, shift_date, user_id, at, label, kind
'single'|'bulk'|'undo', changes text JSON, log_ids text JSON, undo_of integer, undone_at real, sent_at real,
sends integer default 0), `webapp/attendance.py`, `webapp/app.py`, `webapp/templates/day.html`; Test
`webapp/tests/test_undo.py`.

**Interfaces:**
- Produces: `DayBook.action(program, on, user_id, label="", bulk=False)` — a context manager; nested calls join the
  outer one; per (program, on) lock; snapshots `attendance`, `actual_breaks`, `activities`, `channel_moves` for `on`
  and the day before; keeps `changes = [{"table", "key", "before", "after"}]` when anything changed; yields an
  object with `.id` (None until kept). `DayBook.undo_last(program, on, user_id) -> str` (the flash text).
  `DayBook.undoable(program, on, user_id) -> Optional[dict]` (the action Undo would take back). Store:
  `day_rows(program, dates) -> Dict[str, Dict[tuple, dict]]`, `restore_day_rows(changes) -> None` (one transaction),
  `add_day_action(**f) -> int`, `day_actions(program, shift_date) -> List[dict]` (oldest first),
  `set_day_action(id, **f)`. Every RTA route that changes the day runs inside `action(...)`: attendance, break,
  break cancel, activity, activity cancel, add, undo (per person), book, channel. Route `POST /day/undo-last`.

- [ ] **Step 1: failing tests:** `test_undo_takes_back_my_last_change` (a break move undone: the break is back, log
  "Break 1 back to HH:MM (undone)"); `test_undo_goes_back_two_at_most` (three changes: two undos work, the third
  says "Nothing of yours to undo on this day: Undo goes back 2 changes at most."); `test_undo_is_mine_only` (Sara's
  change is not offered to Omar); `test_undo_refuses_when_someone_changed_it_since` (Omar moves, Sara moves the same
  break, Omar's undo: "Not undone: Associate 006's Break 1 was changed again after it, by Sara." and nothing
  changes) (Review Focus 1); `test_undo_restores_an_added_item_and_a_status` (an overtime added is removed; a Sick
  goes back to Present); `test_nested_calls_are_one_change` (apply_replan's moves are one journal entry).
- [ ] **Step 2–4:** run, implement, run with `test_attendance`, `test_day`, `test_notify_daybook`, `test_runs`.
- [ ] **Step 5:** commit "Phase AD task 2: the change journal and Undo".

### Task 3: Bulk changes held from the group; Send, Send again, Send the correction

**Files:** Modify `webapp/store.py` (notify_items gets `action_id integer`), `webapp/notify.py`,
`webapp/attendance.py`, `webapp/app.py`, `webapp/templates/day.html`, `webapp/static/app.js`, `webapp/static/app.css`;
Test `webapp/tests/test_held_posts.py`.

**Interfaces:**
- Consumes: Task 2's `action(...)`.
- Produces: `Notifier.queue(..., action_id=None, held=False)` — an item that would wait is `held` when `held`;
  `Notifier.send_action(action_id, again=False) -> Tuple[bool, str]` (refuses a posted action without `again`:
  "Already posted to the group at HH:MM."); `DayBook.bar(program, on, user_id) -> dict` with `undo` (label, at) and
  `send` (action_id, label, state 'held'|'posted'|'correction', service, at, by_name) or None. Routes
  `POST /day/send` (action_id, again). The bar sits above Today's achievement; Send again opens a `dialog`
  (`#resend-dialog`) from app.js; without script the server's refusal is the safeguard.

- [ ] **Step 1: failing tests:** `test_bulk_waits_for_send` (a bulk action's items are `held`; `run_once` long after
  the hold sends nothing); `test_send_posts_the_bulk_as_one` (Send: one post, its lines are the action's changes);
  `test_send_again_needs_a_yes` (again=0 refused with the text above; again=1 makes a second post with the same
  lines); `test_single_changes_still_post_by_themselves`; `test_bulk_undone_before_send_posts_nothing` (Review Focus
  2); `test_undo_after_send_offers_the_correction` (bar state 'correction'; Send posts the undo lines);
  `test_bar_words` ("Rescue the day moved 14 breaks at HH:MM." style label, "Not posted to the Slack group yet.").
- [ ] **Step 2–4:** run, implement, run with `test_notify_sender`, `test_notify_rta`, `test_notify_daybook`.
- [ ] **Step 5:** commit "Phase AD task 3: bulk changes wait for Send".

### Task 4: Fix breaks as one change; + Add on Overtime when nobody is on shift

**Files:** Modify `webapp/app.py`, `webapp/templates/day.html`; Test `webapp/tests/test_add_overtime_default.py`,
extend `webapp/tests/test_held_posts.py`.

**Interfaces:**
- Consumes: Tasks 2 and 3. Produces: `add_panel["default_what"]` ("Overtime" when nobody present is on shift in the
  interval, else "Break"), `add_panel["default_side"]` ("before" when the first person's shift starts at or after the
  interval's end, else "after") and `add_panel["default_minutes"]` (the smallest of `ADD_LENGTHS` that reaches the
  interval, at most 120).

- [ ] **Step 1: failing tests:** `test_fix_breaks_apply_is_one_held_change` (label "Fix breaks moved N breaks");
  `test_nobody_on_shift_opens_on_overtime` (the who list starts with the person whose shift starts right after the
  interval; Overtime checked; side before; minutes reach the interval); `test_someone_on_shift_still_opens_on_break`.
- [ ] **Step 2–5:** run, implement, run with `test_review_rta`, `test_overtime_side`, commit.

### Task 5: Change several breaks

**Files:** Create `webapp/bulk_breaks.py`; modify `webapp/attendance.py`, `webapp/app.py`, `webapp/templates/day.html`,
`webapp/static/app.css`; Test `webapp/tests/test_bulk_breaks.py`.

**Interfaces:**
- Produces: `bulk_breaks.plan(page, names, which, action, amount, at, now) -> dict` with `changes` [{name, idx, kind,
  minutes, start, new}] (`new` a minute, `CANCELLED`, or None for the plan) and `skipped` [{name, kind, why}];
  `DayBook.bulk_preview(program, on, form, now) -> dict` (adds before/after day figures from `page(extra=...)`);
  `DayBook.apply_bulk(program, on, form, user_id, now) -> int` inside `action(bulk=True, label=...)`. `which` is a
  break kind or "all"; `action` is "cancel" (needs why), "shift" (amount in −30, −15, −10, −5, 5, 10, 15, 30),
  "set" (at HH:MM) or "plan". View `view=bulk`; a "Change several breaks" button next to Fix breaks.
- [ ] **Step 1: failing tests:** `test_cancel_several` (4 cancelled, 1 left as it is: "it has started");
  `test_shift_several_by_15`; `test_set_the_same_time_skips_who_it_does_not_fit` (outside the shift: the reason
  shown); `test_back_to_plan_for_several`; `test_apply_is_one_held_change` (label "Change several breaks: cancelled 4
  breaks"); `test_preview_changes_nothing`.
- [ ] **Step 2–5:** run, implement, run with `test_day`, commit.

### Task 6: Rescue the day

**Files:** Create `webapp/rescue.py`; modify `webapp/attendance.py`, `webapp/app.py`, `webapp/templates/day.html`,
`webapp/static/app.css`, `webapp/static/app.js` (the strips' now line); Test `webapp/tests/test_rescue.py`.

**Interfaces:**
- Produces: `rescue.solve(view, inputs, target, now, may_give_up, hold=None) -> dict` with `moves` [{name, idx,
  kind, minutes, from, to}], `given_up` [t], `status`; `DayBook.rescue_plan(page, now) -> dict` adding `lost`
  [(t, pct)] (intervals with demand ended before now below target), `may_give_up = max(0, 3 - len(lost))`, and the
  before/after figures recounted by `page(extra=...)` (the model's own numbers are never shown); `DayBook.apply_rescue(
  program, on, moves, user_id) -> int` inside `action(bulk=True, label="Rescue the day moved N breaks")`. View
  `view=rescue`; button "Rescue the day" next to Fix breaks; shown with the Interval compliance measure only.
- Model (`cpsat-engine-modeling`): one boolean per (break not started, legal start); per 5-minute slot the floor is
  fixed people minus breaks covering it; per open interval with demand `at` ⇔ floor ≥ ⌈target × required × slots⌉;
  `given_up` ⇒ floor ≥ ⌈0.5 × required × slots⌉ (or its current level if already lower); not given up ⇒ floor ≥
  min(current, target level); Σ given_up ≤ may_give_up; gaps between a person's breaks within the program's rules
  (a gap already outside them may stay as it is); language minimums and channel needs never fall below min(current,
  need). Lexicographic: max Σ at, then min Σ given_up, then min moved breaks; 4 workers, seed 9000, time measured on
  the review day and set in the module with the measurement.
- [ ] **Step 1: failing tests:** `test_rescue_gives_up_one_to_save_more` (a built day: 2 hours short where moving
  three breaks into one hour lifts both; that hour stays ≥ 50%); `test_never_below_half` ; `test_limit_counts_what_is_already_lost`
  (2 lost before now: may give up 1); `test_no_rescue_when_it_cannot_help` (Review Focus 3);
  `test_every_rule_holds_on_the_recount` (each move passes `check_break`, gaps, languages; figures from `page`);
  `test_rescue_apply_stopping_midway_undoes_as_one` (Review Focus 5); `test_service_level_measure_has_no_rescue`.
- [ ] **Step 2–5:** run, implement, run with `test_day`, `test_channel_day`, commit.

### Task 7: Browser checks, suite, gate, package

- [ ] `ThePhaseADInTheBrowser`: cancel a break with a reason and bring it back; Change several breaks cancels 3 and
  the bar offers Send; Send, then Send again shows the question; Undo twice, the third time says why not; Rescue the
  day preview and apply on a short day; + Add at an empty hour opens on Overtime; no sideways scroll at 390 and 320;
  no page errors. Screens to `evidence/phase_ad/screens/`.
- [ ] Re-run `acsweep.py` and `acconsole.py`; full suite; `git checkout -- evidence/` (keep phase_ad screens);
  self-review; gate and package; two halves of new sizes; sha256; push; `evidence/phase_ad/CHECKS.md`; report.
