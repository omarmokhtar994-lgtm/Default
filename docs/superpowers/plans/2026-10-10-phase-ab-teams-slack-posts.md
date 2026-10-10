# Phase AB: Teams and Slack group posts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RTA changes post to each LOB's Teams or Slack group as approved in samples 01 to 04, with the result of
each post visible on the RTA and on an admin Notifications page.

**Architecture:** `webapp/notify.py` holds everything about posting: the link check, the change kinds, the post
text for Teams and Slack, the queue and a background sender with retries. `DayBook` gives every day-log line a kind
and a text safe for a group, and hands it to the notifier; nothing is sent inside an RTA request. An admin page keeps
each LOB's link (stored in the server's database, shown only by its last four characters), its rule and its results.

**Tech Stack:** Flask 3.1, SQLite (`webapp/store.py`), Jinja2 with the strict CSP, vanilla JS, `urllib.request`
(no new dependency), Playwright for the browser check.

**Spec:** `evidence/phase_ab/DIAGNOSIS.md` and `evidence/phase_ab/samples/01` to `04` (owner, 2026-10-10: "Start
the Teams/Slack notifications now", sent after the samples).

## Global Constraints

- Engine untouched; RC9.1 protected workbooks and `engine/regression_assets` untouched.
- "Notification secrets (SMTP passwords, bot tokens, webhook URLs) live only on the server, never in the repo or
  chat": a link is never rendered in full after saving, never in exports, events, flashes or error text.
- Links accepted only over HTTPS on `hooks.slack.com` (Slack) or a host ending `.logic.azure.com` or
  `.api.powerplatform.com` (Teams), port 443 or none, no user:password; checked on save and again before each send;
  redirects are not followed.
- Strict CSP: no inline script, style or event handlers; copy in sentence case; DESIGN.md v3 colours (actions ink;
  teal/amber/red only as state: posted / waiting / not posted by failure).
- Times in Egypt time (UTC+3). Real names never in fixtures: "Associate NN".
- Never posted to a group: sick, unplanned leave, attendance set back to present, the why of any aux.
- Do not modify or delete tests to pass; re-pin only when an approved sample changed the measured contract, with the
  reason in the test.
- Release gate: `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`.

## Review Focus

1. The sender thread dies or blocks (a slow group, an exception in one LOB): one LOB's failure must not stop others,
   and the thread must keep running. Pinned in Task 2 (`test_one_lob_failing_does_not_stop_another`,
   `test_run_once_survives_a_transport_exception`).
2. A link removed or posting turned Off while a post waits: it must not be sent to the old group. Task 2
   (`test_turning_off_stops_waiting_posts`).
3. A server restart in the middle of a hold or a retry: nothing lost, nothing sent twice. Task 2
   (`test_a_new_notifier_picks_up_waiting_items`).
4. Morning post after a restart hours late: not posted stale. Task 6 (`test_morning_post_not_sent_hours_late`).
5. A name or text with Slack control characters (`<`, `>`, `&`) or Markdown stars: escaped, never a broken link or
   mention. Task 1 (`test_slack_escapes_control_characters`).

---

### Task 1: Links, kinds and the post text

**Files:**
- Create: `webapp/notify.py`
- Test: `webapp/tests/test_notify_posts.py`

**Interfaces:**
- Produces:
  - `KINDS: Dict[str, str]` in this order: `"break"`: "Breaks and lunches moved, or put back to plan",
    `"added_break"`: "Breaks and lunches added on the day", `"overtime"`: "Overtime and VTO", `"called_in"`: "Day off
    cancelled (called in)", `"channel"`: "Channel changes", `"aux"`: "Training, coaching, meetings and other aux",
    `"late"`: "Late and left early". `DEFAULT_KINDS` = the first five. `PRIVATE = "private"` (never posted).
  - `HOLDS = {0: "At once", 120: "2 minutes", 300: "5 minutes"}`, `DEFAULT_HOLD = 120`, `MAX_HOLD = 600`,
    `RETRIES = (60, 300, 900)`, `TIMEOUT = 10`, `MODES = ("off", "preview", "on")`, `SERVICES = {"teams": "Teams",
    "slack": "Slack"}`.
  - `check_link(url: str) -> str` returns "teams" or "slack"; raises `ValueError` with: "Paste the group link."
    (empty), "That is not a Teams or Slack group link: it has to start with https://." (scheme), "That is not a Teams
    or Slack group link. Teams links are on logic.azure.com or api.powerplatform.com; Slack links are on
    hooks.slack.com." (host, port, user:password), "That link is too long to be a group link." (> 2000 characters).
  - `link_end(url: str) -> str`: the last four characters.
  - `Post` (dataclass): `title: str`, `sections: List[Tuple[str, List[Tuple[str, str]]]]` (heading, then (name,
    text) lines), `footer: str`, `url: str` ("" for none).
  - `change_post(label: str, shift_date: str, items: List[Dict], site: str, unit: str) -> Post`: title "{label}:
    changes for {Ddd dd Mon}", one section with heading "", lines (associate, text) oldest first; footer "Changed on
    the RTA by {name}, {HH:MM}." for one person, "Changed on the RTA by {A}, {B} and {C}; last at {HH:MM}." for more;
    url `{site}day?program={quote_plus(unit)}&date={shift_date}` when `site`, else "".
  - `teams_body(post: Post) -> dict` (Workflows "Send webhook alerts to a channel": a message with one Adaptive Card
    1.4 attachment, bold title TextBlock, per section an optional bold heading and a TextBlock of "- **name**: text"
    lines, a subtle small footer, `Action.OpenUrl` "Open the RTA" when url, `msteams.width` "Full").
  - `slack_body(post: Post) -> dict` (`text` fallback = title; blocks: a section with "*title*", per section mrkdwn
    "• *name*: text" lines split into blocks of at most 2900 characters, a context block with the footer and
    `<url|Open the RTA>`); `&`, `<`, `>` escaped and `*` removed from names and texts.
  - `body_for(service: str, post: Post) -> dict`.

- [ ] **Step 1: Write the failing tests** in `test_notify_posts.py`:
  `test_slack_and_teams_links_are_accepted` (a `https://hooks.slack.com/services/T0/B0/x` link → "slack";
  `https://prod-12.westeurope.logic.azure.com:443/workflows/a/triggers/manual/paths/invoke?sig=x` and
  `https://default1.ab.environment.api.powerplatform.com/powerautomate/automations/direct/workflows/a/triggers/manual/paths/invoke?sig=x`
  → "teams"); `test_other_links_are_refused` (http://hooks.slack.com, https://example.com, https://hooks.slack.com.evil.io,
  https://user:pw@hooks.slack.com/x, https://hooks.slack.com:8443/x, https://127.0.0.1/x, "" each raise with the
  exact message above); `test_link_end_is_the_last_four`; `test_change_post_text` (two items by one person →
  title "SAKS, NMG Tier 2: changes for Sat 10 Oct", lines in time order, footer "Changed on the RTA by Omar Mokhtar,
  19:19.", url "https://rta.example/day?program=SAKS+NMG+Tier+2&date=2026-10-10"); `test_footer_for_several_people`;
  `test_teams_body_shape` (attachments[0].contentType "application/vnd.microsoft.card.adaptive", content type
  "AdaptiveCard", version "1.4", title text, a line "- **Associate 019**: Lunch moved 12:15 to 12:45", an
  Action.OpenUrl with the url; no action when url ""); `test_slack_body_shape`;
  `test_slack_escapes_control_characters` (name "Associate <1> & *2*" → "Associate &lt;1&gt; &amp; 2" in the
  mrkdwn, no "<!" or "<@" possible); `test_long_slack_post_splits` (120 lines → every section text ≤ 2900).
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_notify_posts -v` — Expected: ImportError (no module).
- [ ] **Step 3: Implement** the Produces block in `webapp/notify.py`.
- [ ] **Step 4: Run** the same command — Expected: all pass.
- [ ] **Step 5: Commit** "Phase AB task 1: group links, change kinds and post text".

### Task 2: Store, queue and sender

**Files:**
- Modify: `webapp/store.py` (SCHEMA, methods, `add_day_log` returns the new id, `delete_day_before` also clears
  `notify_items` and `notify_posts`)
- Modify: `webapp/notify.py`
- Test: `webapp/tests/test_notify_sender.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - Tables `notify_settings(unit pk, link, service, mode default 'off', kinds (comma list), hold default 120,
    morning default '', morning_day default 'same', site, saved_by, saved_at)`, `notify_items(id, log_id, unit,
    shift_date, associate, kind, text, ref, before, after, by_name, at, status, reason, post_id)`,
    `notify_posts(id, unit, shift_date, what ('changes'|'morning'|'test'), service, count, status, tries, next_at,
    sent_at, reason, body, made_at)`.
  - Store: `get_notify(unit) -> Optional[Dict]`, `set_notify(unit, **fields)`, `list_notify() -> List[Dict]`,
    `add_notify_item(**fields) -> int`, `notify_items(unit=None, shift_date=None, status=None) -> List[Dict]`,
    `set_notify_items(ids, **fields)`, `add_notify_post(**fields) -> int`, `set_notify_post(id, **fields)`,
    `notify_posts(unit=None, status=None, what=None, shift_date=None, limit=None) -> List[Dict]` (newest first).
  - `send_json(url: str, body: dict, timeout: float = TIMEOUT) -> Tuple[bool, int]` (urllib POST, JSON, no
    redirects; (False, 0) on a network error or timeout); `post_json(url, body) -> Tuple[bool, int]` = `check_link`
    then `send_json`.
  - `reason_for(service: str, code: int) -> str`: 0 "{S} could not be reached"; 400 "{S} refused the message (400)";
    401/403 "{S} says this link may not post ({code}); replace the link"; 404/410 "{S} says the link no longer works
    ({code}); replace the link"; 429 "{S} asked to slow down (429)"; 5xx "{S} had a problem ({code})"; else "{S}
    answered {code}".
  - `Notifier(store, transport=post_json, clock=time.time, labels=None)` (`labels`: key → "Program, LOB"):
    `queue(log_id, unit, shift_date, associate, kind, text, by_name, ref="", before="", after="",
    left_out=False) -> None`; `run_once(now: float = None) -> int` (posts attempted); `statuses(unit, shift_date)
    -> Dict[int, Dict[str, str]]` (log_id → {"state", "text"}); `start()` (daemon thread, `run_once` every 15 s, an
    exception logged and the loop kept).
  - Queue rules: no settings or mode "off" → nothing kept. Else the item is kept as "skipped" with reason "kept
    private" (kind PRIVATE), "left out on the RTA" (left_out), "not ticked for this LOB" (kind not in kinds), or
    "waiting". An item whose `after` equals the `before` of the earliest waiting item with the same ref (same unit and
    date) marks all of them, itself included, "skipped" with "undone before it was posted".
  - Sender rules: a unit's waiting items for one date go as one post once `now ≥ last.at + hold` or `now ≥
    first.at + MAX_HOLD`; mode "preview" marks them "preview" and keeps a post with status "preview" (nothing sent);
    mode "on" keeps a post "waiting" and items "sending", then sends. A failed send waits RETRIES[tries-1]; after
    the fourth failure the post and its items are "failed" with `reason_for`. Before each send the unit's settings
    are read again: mode not "on" or no link → "failed", "posting was turned off" / "the group link was removed".
  - Status texts: waiting "Waiting: posts by HH:MM"; sending, tries 0 "Posting now"; sending, tries > 0 "Waiting:
    {S} did not take it, trying again at HH:MM"; sent "Posted to {S}, HH:MM"; preview "Preview only: not sent";
    skipped and failed "Not posted: {reason}".
- [ ] **Step 1: Write the failing tests** with a fake transport that records (url, body) and returns scripted
  answers, and a fake clock: `test_off_keeps_nothing`; `test_private_left_out_and_unticked_are_skipped`;
  `test_items_wait_for_the_hold_then_go_as_one_post` (two items at t and t+60, hold 120: nothing at t+170, one post
  with both lines at t+180); `test_a_busy_day_posts_after_ten_minutes`; `test_undone_changes_are_not_posted`
  (moved 12:15→12:45, 12:45→13:00, back to 12:15 → three skipped, no post); `test_preview_sends_nothing`;
  `test_failure_retries_then_fails` (answers 500, 500, 500, 500 at +0, +60, +300, +900 → failed "Teams had a
  problem (500)"); `test_retry_then_success`; `test_turning_off_stops_waiting_posts`;
  `test_one_lob_failing_does_not_stop_another`; `test_run_once_survives_a_transport_exception`;
  `test_a_new_notifier_picks_up_waiting_items`; `test_statuses_for_the_rta`; `test_reason_texts`;
  `test_send_json_posts_json_and_follows_no_redirect` (a local `http.server` on 127.0.0.1: 200 → (True, 200), 302 →
  (False, 302) and the redirect target never hit, a 2 s sleep with timeout 0.5 → (False, 0));
  `test_post_json_refuses_a_local_link` (`post_json("http://127.0.0.1/x", {})` raises ValueError, nothing sent);
  `test_old_items_go_with_the_day` (`delete_day_before` clears both tables before the date).
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_notify_sender -v` — Expected: failures (missing names).
- [ ] **Step 3: Implement** the store tables and methods and the Produces block.
- [ ] **Step 4: Run** — Expected: all pass; also `$PY -m unittest webapp.tests.test_store webapp.tests.test_attendance`
  (or the files that cover the day log) still pass.
- [ ] **Step 5: Commit** "Phase AB task 2: queue and sender with hold, undo and retries".

### Task 3: Every RTA change carries a kind and a group-safe text

**Files:**
- Modify: `webapp/attendance.py` (a `_log` helper replaces the nine `store.add_day_log` calls; `DayBook.notifier`,
  default None)
- Modify: `webapp/notify.py` (`leave_out(flag: bool)` context manager on a ContextVar; `left_out_now() -> bool`)
- Modify: `webapp/app.py` (build the Notifier after DayBook: `app.extensions["notifier"]`, `days.notifier`; start
  its thread when `config.get("NOTIFY_THREAD", config.get("START_WORKER", True))`; `NOTIFY_TRANSPORT` config for
  tests)
- Test: `webapp/tests/test_notify_daybook.py`

**Interfaces:**
- Consumes: `Notifier.queue` (Task 2).
- Produces: `DayBook._log(program, on, name, what, user_id, kind, post=None, ref="", before="", after="")` writes the
  day log line `what` unchanged and queues `post or what`. Kinds and refs:
  `move_break` "break", `break:{name}:{idx}`, before/after the HH:MM; `add_activity` Break/Lunch "added_break",
  Overtime/VTO "overtime", aux "aux" with post = the line without the why, `activity:{id}`, ""→"on";
  `cancel_activity` the cancelled kind's kind, `activity:{id}`, "on"→""; `_call_in`/`_cancel_call_in` "called_in",
  `callin:{id}`; `channel_move`/`cancel_channel_move` "channel", `channel:{id}`; `set_status` Late/Left early
  "late", aux "aux" (post without the why), Sick/Unplanned leave/Present PRIVATE, `status:{name}`, before = the
  earlier status or "Present", after = the new one.
- [ ] **Step 1: Write the failing tests** on the Phase Z day (`TwoSchedulesForOneWeek` data, Wed 2026-10-14) with a
  Slack link "on", all kinds ticked, hold 120 and a recording transport: `test_each_change_has_its_kind`
  (break move, back to plan, Break added, Overtime after, VTO, Coaching with a why, Late, Sick, Present, call-in
  and its cancel, channel move when the data has channels: else skip that line with a reason) by reading
  `store.notify_items`; `test_the_why_never_reaches_a_post` (coaching "with Lina: Call review" → item text
  "Coaching 14:00 to 14:30 (billable), with Lina", the day log keeps the why); `test_the_day_log_is_unchanged`
  (the `what` texts equal the ones before Phase AB for a move, an overtime and a sick); `test_leave_out_skips_one`;
  `test_no_settings_no_items` (an LOB with nothing saved keeps no item and the RTA log stays as now).
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_notify_daybook -v` — Expected: failures.
- [ ] **Step 3: Implement** `_log`, the ContextVar, and the app wiring.
- [ ] **Step 4: Run** it plus `test_attendance`, `test_day_*`, `test_overtime_side` — Expected: pass.
- [ ] **Step 5: Commit** "Phase AB task 3: RTA changes tagged for the group".

### Task 4: The Notifications page (admins)

**Files:**
- Modify: `webapp/app.py` (routes `GET/POST /notifications` (`notifications_page`), `POST /notifications/test`
  (`notifications_test`), `POST /notifications/remove` (`notifications_remove`); admin only, 403 otherwise; events
  `notify_saved`, `notify_removed`, `notify_tested` with subject = LOB label, detail without the link)
- Modify: `webapp/exports.py` (labels "Notifications changed", "Group link removed", "Test message sent")
- Modify: `webapp/notify.py` (`Notifier.send_test(unit, by_name) -> Tuple[bool, str]`: one post "{label}: test from
  Team Scheduler", footer "Sent by {name} at HH:MM. RTA changes for this LOB post here.", sent at once; flash
  "Test message posted to {S}." or "Test message not posted: {reason}.")
- Create: `webapp/templates/notifications.html`; Modify: `webapp/templates/base.html` (Manage: "Notifications" for
  admins, after "Associate channels"); `webapp/static/app.css`
- Test: `webapp/tests/test_notifications_page.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: the page of sample 02: h1 "Notifications"; lead "Post RTA changes to a Teams or Slack group. Each LOB
  posts to the group whose link it has; the same link can serve several LOBs."; table of every unit (LOB, Posts to,
  Posting, Last post), each LOB a link `?unit=`; the picked LOB's form: link field `type=password`
  `autocomplete=off` name `link` labelled "{S} group link" (or "Group link" when none) with "Ends in …{end}. Saved
  {Ddd dd Mon} by {name}. Kept on this server; never shown again in full." and a Remove link form; Posting radios On
  / Preview only / Off with their small texts; "Post these changes" ticks (KINDS); "Never posted: sick and
  unplanned leave, attendance set back to present, and the why of any aux."; Wait before posting (HOLDS) with
  "Changes made in that time go as one post; a change undone in that time is not posted."; Day's breaks post (time
  field `morning`, empty = off; select `morning_day` "On the day" / "The evening before"); Save; Send test message;
  "The last post, as the group saw it" (site-styled card from the newest sent or preview post); Recent posts (last
  10: time, changes, result); details "Where the group link comes from" with the Teams and Slack steps of sample 02.
  Save errors: "Paste the group link first, or leave posting Off." (mode not off, no link), the `check_link`
  messages, "Pick a time like 07:30, or leave it empty." The site address is saved from `request.host_url`.
- [ ] **Step 1: Write the failing tests**: `test_only_admins` (planner 403 on all three routes, no nav item);
  `test_save_a_slack_link_then_it_is_masked` (the full link appears nowhere in the page, the events, the exports
  file or a flash; "Ends in …" with the last four); `test_bad_link_refused_and_nothing_saved`;
  `test_rule_saved` (mode, kinds, hold, morning saved and shown checked); `test_on_without_link_refused`;
  `test_send_test_message` (recording transport gets one body with the title; flash "Test message posted to
  Slack."; a 404 answer flashes "Test message not posted: Slack says the link no longer works (404); replace the
  link."); `test_remove_link_turns_posting_off`; `test_recent_posts_and_last_post_shown`.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_notifications_page -v` — Expected: failures (404 routes).
- [ ] **Step 3: Implement** routes, template, nav, CSS.
- [ ] **Step 4: Run** — Expected: pass; plus `test_exports`, `test_access` (or the nav tests) pass.
- [ ] **Step 5: Commit** "Phase AB task 4: Notifications page for admins".

### Task 5: The RTA shows each change's post, and one tick to leave a change out

**Files:**
- Modify: `webapp/app.py` (`day_page` passes `posts` = `notifier.statuses(program, date)` and `post_to` = the
  service name when the LOB's mode is on or preview, else ""; `day_break` and `day_add` run inside
  `leave_out(request.form.get("post_asked") == "1" and request.form.get("post") != "1")`)
- Modify: `webapp/templates/day.html` (Changes today: after each line `<span class="post-st {state}">{text}</span>`;
  the break dialog and + Add carry, when `post_to`, `<label class="post-tick"><input type="checkbox" name="post"
  value="1" checked> Post to the {S} group <small>Untick to keep this one change off the group.</small></label>` and
  `<input type="hidden" name="post_asked" value="1">`); `webapp/static/app.js` (the break dialog sends `post` and
  `post_asked`); `webapp/static/app.css` (`.post-st.sent` covered text, `.waiting` short ink, `.failed` gap ink,
  `.skipped`/`.preview` dim)
- Test: `webapp/tests/test_notify_rta.py`

**Interfaces:**
- Consumes: Tasks 2 to 4.
- [ ] **Step 1: Write the failing tests**: `test_changes_today_show_their_post` (a waiting, a sent, a skipped and a
  failed line render their texts and classes); `test_no_tags_without_notifications` (the page has no `post-st` and
  no `post-tick`); `test_the_tick_leaves_one_change_out` (`/day/add` with post_asked=1 and no post → item skipped
  "left out on the RTA"; with post=1 → waiting); `test_the_break_dialog_sends_the_tick` (`/day/break` form with
  post_asked=1, no post → skipped).
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_notify_rta -v` — Expected: failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: pass; plus the day page tests.
- [ ] **Step 5: Commit** "Phase AB task 5: post status on the RTA and the tick".

### Task 6: The day's breaks, posted at a set time (sample 04)

**Files:**
- Modify: `webapp/notify.py` (`Notifier(..., days=None)`; `breaks_post(label, unit, on, page, site, at) -> Post`;
  `run_once` posts once per unit and date when `morning` is set, mode is on or preview, and Egypt time is between
  the set time and two hours after it; target date = that day, or the next day for "before")
- Test: `webapp/tests/test_notify_morning.py`

**Interfaces:**
- Consumes: `DayBook.page(unit, date)` (`view.lanes[].segments[]` with `offset`, `label`, `status`, `breaks[]` of
  `kind`, `start`); Tasks 1 and 2.
- Produces: title "{label}: breaks for {Ddd dd Mon}", one section per shift label in start order, heading "{HH:MM}
  to {HH:MM} ({n} person|people)", lines (name, "Break 1 11:00, Lunch 12:45, Break 2 13:45") with breaks as they
  stand (moved ones at their new time); people marked sick or unplanned leave are left out; footer "As planned at
  {HH:MM}. Changes during the day are posted as they happen." (the second sentence only when mode is on and a
  change kind is ticked). No schedule for the day: a post kept as "skipped", "there is no schedule in use for that
  day", nothing sent.
- [ ] **Step 1: Write the failing tests**: `test_morning_post_lists_breaks_by_shift`; `test_morning_post_once_a_day`;
  `test_evening_before_posts_tomorrow`; `test_morning_post_not_sent_hours_late`; `test_sick_people_left_out`;
  `test_no_schedule_no_post`.
- [ ] **Step 2: Run** `$PY -m unittest webapp.tests.test_notify_morning -v` — Expected: failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: pass.
- [ ] **Step 5: Commit** "Phase AB task 6: the day's breaks posted at a set time".

### Task 7: Browser check, suite, gate, package

**Files:**
- Modify: `webapp/tests/test_ui_playwright.py` (class `ThePhaseABInTheBrowser`)
- Create: `evidence/phase_ab/CHECKS.md`, `evidence/phase_ab/screens/`
- Modify: `deploy/ORACLE_SETUP_GUIDE.md` (a short "Teams or Slack posts" section: where to paste the link, that the
  server needs outbound HTTPS, nothing to install)

- [ ] **Step 1:** `test_notifications_page_and_rta_posts`: save a Slack link with a recording transport, see "Ends in
  …", send a test, make a break move with the tick on and one with it off, run the sender, see "Posted to Slack" and
  "Not posted: left out on the RTA" on the RTA; screens at 1280, 390 and 320 px; no sideways scroll; no page errors.
- [ ] **Step 2:** axe crawl (`zaudit.py`) of the signed-in site, night and day looks, including /notifications.
- [ ] **Step 3:** full suite `$PY -m unittest discover -s webapp/tests -t .`, then `git checkout -- evidence/`.
- [ ] **Step 4:** self-review of the branch (final review), fix pass if needed.
- [ ] **Step 5:** `python3 tools/build_production_package.py` (gate), split into two halves of different sizes,
  check the rejoin by sha256, commit and push.
