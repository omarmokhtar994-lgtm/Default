# Needs validation: unresolved leads (no severity)

Each lead is source-grounded but blocked on an execution or deployment fact. Local plans use dummy data in an isolated, memory-capped environment; deployment checks are owner-observed on a staging copy, never audit traffic to the live site. Order = the verifier's triage hint.

## 1. RTA day POST routes authorize one program but act on another (query string versus form field)
- **Fingerprint:** `day.post.program.gate-source-mismatch`
- **Triage hint:** medium (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** Policy and sink disagree on where 'program' comes from: the wall reads request.values (args first), handlers read request.form, and DayBook has no user awareness.
- **Why it matters:** A planner or supervisor restricted to some programs can read previews and change RTA day data (breaks, statuses, channel moves, bulk changes, possibly group posts) of programs they were not granted, breaking the per-program isolation (app.py:399-400). Needs a normal account plus a crafted POST.

**Trace**
- entrypoint: `webapp/app.py:394` (_before program wall) Skipped only for OPEN_TO_ALL; otherwise key=clean_program(request.values.get('program','')) and 403 if not can_open(key); empty key skips the wall.
- propagation: `webapp/routes/day.py:674` (_day_form) Re-reads program from request.form['program']; same at 842, 874, 892, 962, 984, 1002, 1134, 1240, 1299, 1336, 1354, 1376, 1393, 1412, 1428, 1443.
- propagation: `webapp/routes/day.py:791` (day_break) login_required only; role gate satisfied for own program; no can_open follows (contrast day_absences:770, day_operating_start:622).
- sink: `webapp/attendance.py:1268` (DayBook.move_break/set_status) Mutates the named program's day records using the supplied program string; no per-user program check.

**Evidence**
- `webapp/app.py:397` Wall condition: if key and not _access().can_open(key), key from request.values.
- `webapp/routes/day.py:678` _day_form returns clean_program(request.form.get('program','')) only.
- `webapp/routes/day.py:770` Only day_absences re-checks can_open.
- `webapp/routes/analytics.py:165` Sibling POST routes re-check can_open on the form program.
- `webapp/routes/volumes.py:59` Volumes, requests and break-change routes read request.values or re-check.

**Verifier corrections**
- day_break sink is attendance.py:1268 (move_break); set_status at 1189; both take a raw program string with no user/can_open check.
- Role gate is PERMISSION_ENDPOINTS at app.py:377 (permissions.py:37 lists day_break): role only, not program.
- The wall (app.py:394-401) skips OPEN_TO_ALL; no /day/* write endpoint is in that set, so the only program check is on request.values.
- _route_to_lob (app.py:420-432) rewrites form program only for merge=1 merged units: not a control.
- Only day_operating_start (day.py:622), day_absences (day.py:770), day_shrinkage_map (analytics.py:169) re-check can_open. Access.can_open returns True for admins/all_programs, so the gap matters only for restricted users.
- No code overrides request_class/values, so Werkzeug's default (args then form) applies; not opened here.

**Preconditions**
- Authenticated non-admin, non-all_programs user (planner or supervisor) with the role permission for the day endpoint
- Valid CSRF token from their own session (check_csrf runs first, app.py:368)
- Target program key exists with a date in range and an associate name in it
- Werkzeug args-then-form order on POST (library fact), or empty ?program= skipping the wall

**Blockers**
- Confirm on a two-program test instance that the mismatched POST mutates program B and which permissions default planner/supervisor hold for each day_* endpoint
- Per-handler review of the other form-reading handlers (842, 874, 892, 962 ... 1443) to confirm none re-check can_open
- Runtime confirmation of Werkzeug request.values ordering on POST and that empty ?program= leaves the form value in effect
- Werkzeug request.values ordering (args before form) is library knowledge; Flask/Werkzeug not installed here
- no sandbox available; source-only run

**Local validation plan:** Dummy two-program instance (A, B; planner with only A): POST /day/break?program=A with form program=B&date=..&associate=Associate 01&idx=0&at=..&csrf_token=..; check whether B's day changes; repeat with ?program= empty. Regression test expects 403. Fix: can_open check in _day_form and each handler, or have before_request check every source of 'program'.

**Owner-observed deployment check:** Owner on a staging copy with fake 'Associate NN' data and a throwaway planner limited to one program: send the mismatched-program POST and confirm the other program is unchanged or rejected.

**Smallest source fix and regression test (proposal, not applied):** In app.py _before, run can_open on every source of program for POSTs (request.form as well as request.args; 403 if either is not openable), or add the can_open check in _day_form/_posted_day callers (abort 403) and in each handler reading form program. Regression test: planner limited to A posts /day/break?program=A with form program=B (and with empty ?program=); expect 403 and B's day unchanged.

## 2. A supervisor can reset the password of, and so take over, a user who also holds programs the supervisor does not have
- **Fingerprint:** `people.can_manage.partial-overlap-takeover`
- **Triage hint:** medium (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** The management rule tests intersection of program sets (any shared program), not containment of the target's programs in the manager's.
- **Why it matters:** A supervisor can set a temporary password on a user who also holds programs outside the supervisor's scope and sign in as them (must_change lets the supervisor choose a permanent password), reaching the other programs' data and the target's permissions, defeating per-program isolation. The same gate allows disable, delete, unlock and team reassignment of such users.

**Trace**
- entrypoint: `webapp/routes/people_file.py:236` (admin_user_action) POST /admin/users/<id>/<action> gated by manager_required (people) and access.can_manage(target).
- propagation: `webapp/access.py:59` (Access.can_manage) True if people on, target not admin/supervisor, and manager everything() or program_ids & target program ids non-empty; all_programs targets excluded, supersets not.
- propagation: `webapp/routes/people_file.py:274` (admin_user_action reset) store.set_password(user_id, temporary, must_change=True); temporary password flashed to the acting supervisor.
- sink: `webapp/routes/sign_in.py:17` (login) The supervisor signs in as the target with the temporary password and gets the target's full program set.

**Evidence**
- `webapp/access.py:71` return bool(self.program_ids() & set(self.store.user_program_ids(target['id']))): shared-program intersection rule.
- `webapp/routes/people_file.py:278` Temporary password displayed to the acting manager.
- `webapp/tests/test_programs.py:131` Test covers only disjoint and all-programs targets, not a superset target.
- `webapp/routes/admin.py:70` _chosen_programs documents targets can hold programs the supervisor cannot see.

**Verifier corrections**
- people_file.py:278 is the flash of the temporary password; set_password is at 276; 274 is the 'reset' branch header.
- admin.py:70 is the _chosen_programs docstring: the code anticipates partial overlap only for program edits (keep=), not reset/disable/delete.
- The 'programs' action is already safe: _chosen_programs (admin.py:77-80) limits grants to the manager's programs and keeps the target's others. Exposure is reset, disable, delete, unlock, bulk switch and team.

**Preconditions**
- Authenticated supervisor, or a role granted 'people' (permissions.py:30, supervisor by default)
- Non-admin, non-supervisor, non-all_programs target sharing at least one program and also holding a program the attacker lacks
- Target active, or enabled by the attacker via 'enable'

**Blockers**
- Deployment check of Roles page 'people' setting and whether supervisors with partial program sets exist
- Intended policy is not stated in source; owner may consider shared-program management intended
- No execution: end-to-end reset, login and cross-program access not run
- Owner confirmation of intended policy
- no sandbox available; source-only run

**Local validation plan:** Dummy instance: supervisor S with program A, planner P with A and B, People on for Supervisor. As S POST /admin/users/<P>/reset, sign in as P, open B's RTA day. Regression test expects 403 for reset/disable/delete when target's programs are not a subset of S's.

**Owner-observed deployment check:** Owner confirms whether supervisors are meant to reset accounts holding other programs and checks the Roles page 'people' setting.

**Smallest source fix and regression test (proposal, not applied):** In Access.can_manage for non-everything managers require target program ids to be a subset of the manager's: tp = set(user_program_ids(target['id'])); return bool(tp) and tp <= self.program_ids(). Regression test in test_programs.py: supervisor with NMG, planner with NMG and AE/AR B2B: can_manage False and POST /admin/users/<id>/reset 403; planner with NMG only stays manageable. If sharing is intended, document it and let only admins act on out-of-scope targets.

## 3. Cancelling a coaching or break request by id redirects to the request's program even when it is not the caller's
- **Fingerprint:** `coaching.cancel.redirect-program-name-leak`
- **Triage hint:** low (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** The redirect uses the row's program before authorising the row (no can_open or ownership check ahead of the read).
- **Why it matters:** A user limited to one program can learn which program any coaching/break request id belongs to, and which ids exist, from the 303 Location header. Low-sensitivity cross-program metadata leak; nothing modified.

**Trace**
- entrypoint: `webapp/routes/break_changes.py:110` (requests_coaching_cancel) request_id from the path for any non-associate with approve_tm or rta_change.
- propagation: `webapp/routes/break_changes.py:116` (get_change_request) Reads the row for any id with no program or ownership check.
- sink: `webapp/routes/break_changes.py:122` (redirect) redirect(url_for('requests_coaching', program=row['program'])) after a refused cancel exposes the program name.

**Evidence**
- `webapp/change_requests.py:637` cancel() raises 'That is not your request.' but the route still builds the redirect from the row.
- `webapp/routes/break_changes.py:187` Sibling request_change_decide checks can_open(row['program']) first.

**Verifier corrections**
- Trace/evidence lines accurate (decorator 110-112, function 112).
- Location header is also an id existence oracle: missing id redirects without program param (break_changes.py:122, row None); existing id redirects with program=<name>.

**Preconditions**
- Authenticated non-associate with approve_tm or rta_change
- Valid session and CSRF token
- Sequential integer request ids
- Target request in a program the caller cannot open

**Blockers**
- Confirm CSRF enforcement and that 403/404 are otherwise indistinguishable
- Confirm at runtime the Location header carries program=B for a cross-program id
- Impact limited to program names (low sensitivity)
- no sandbox available; source-only run

**Local validation plan:** As a planner limited to A, POST /requests/coaching/<id>/cancel for a request id in B; check whether the 303 Location contains program=B. Fix: abort 403/404 unless the row is in a program the caller can open or the caller is the requester.

**Owner-observed deployment check:** Not required beyond the local check.

**Smallest source fix and regression test (proposal, not applied):** In requests_coaching_cancel, abort(404) if row is None; abort 403/404 if row['requester_id'] != g.user['id'] and not can_open(row['program']) before calling cancel; on refusal redirect to url_for('requests_coaching') with no program param. Regression test in test_ar_walls.py: planner on A POSTs cancel for a B request; Location must not contain program=B and must match a nonexistent id's response.

## 4. Lockout failure counter is a lost-update race, so concurrent guesses exceed 5 per lock
- **Fingerprint:** `h1-lockout-counter-lost-update`
- **Triage hint:** low (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** authenticate reads users.failed, runs scrypt, then writes failed+1 as an absolute value on separate sqlite connections with no write transaction or atomic increment.
- **Why it matters:** The 5-guess per 15-minute lockout can be exceeded (roughly up to 8 guesses per counter step) and a lock can be overwritten back to unlocked by a stale write: a modest multiple of online guessing against one account. It does not bypass authentication; password policy and scrypt cost still bound the gain.

**Trace**
- entrypoint: `webapp/routes/sign_in.py:31` (login POST) Each concurrent POST calls store.authenticate after throttle.held (27) passes; failures recorded after authenticate returns (34).
- propagation: `webapp/store.py:953` (Store.authenticate) Reads user row (failed, locked_until) in its own connection; no begin immediate.
- propagation: `webapp/store.py:961` (Store.authenticate) scrypt verification between read and write widens the window; up to 8 threads at once.
- sink: `webapp/store.py:963` (Store.authenticate) failed = row['failed'] + 1 from the stale read, UPDATE sets absolute value (965); concurrent attempts overwrite each other.

**Evidence**
- `webapp/store.py:609` _db() opens a new sqlite3.connect per call; only transaction() issues begin immediate (646) and authenticate does not use it.
- `webapp/serve.py:58` Waitress threads=8.
- `webapp/routes/sign_in.py:79` change_password -> store.check_password -> authenticate, same counter.

**Verifier corrections**
- Lines hold (sign_in.py:27,31,33-34; store.py:953,961-962,963,965-966; _db 604-637; transaction() begin immediate 640-651; serve.py:58; check_password 998-999; sign_in.py:79).
- Impact understated: the stale UPDATE (store.py:965-966) also writes locked_until. A thread that read failed=N before another set the lock writes (failed=N+1, locked_until=0), so it can erase an existing lock, not only slow the counter.
- Per-IP throttle (throttle.py:13, 40 per 15 min; held 26-29) is checked before and recorded after authenticate (sign_in.py:27,34), so a burst of 8 in flight overshoots slightly; it does nothing against many addresses.
- The authenticate read is a plain select on an autocommit-style connection, so no read lock spans scrypt: confirms the race window.

**Preconditions**
- Attacker can POST /login with no account; knowing a username is enough
- Burst of up to 8 concurrent requests against one username
- Per-IP throttle not yet held; addresses can be rotated
- Real thread overlap during scrypt

**Blockers**
- Confirm hashlib.scrypt releases the GIL and 8 threads overlap on the deployed Python
- Confirm single-process deployment (throttle.py:4); multiple processes widen the race
- Observe on a staging copy (16 parallel wrong-password POSTs) how many guesses are evaluated and whether locked_until is clobbered to 0
- hashlib.scrypt GIL release and real overlap of 8 Waitress threads on the target Python build not observed
- no sandbox available; source-only run

**Local validation plan:** In a sandbox, create a Store with one user, fire 8 to 16 concurrent Store.authenticate(user, wrong) calls from threads and compare users.failed and locked_until with the expected lock after 5 failures; repeat via the Flask test client in a threadpool.

**Owner-observed deployment check:** Owner on a staging copy: send 16 parallel wrong-password POSTs to /login for a test account and check sign_in_failed events for more than 5 evaluated before it reads as locked.

**Smallest source fix and regression test (proposal, not applied):** Make the failure update atomic: single UPDATE with CASE on failed+1 >= LOCK_AFTER_FAILURES setting locked_until, where id=? and locked_until <= now, then read back to choose 'locked' or 'bad'; never write locked_until=0 on the failure path. Regression test: 8-16 threads calling Store.authenticate(user, wrong); assert locked after 5 recorded failures, locked_until stays > now, a stale failure cannot clear a lock.

## 5. Username enumeration by timing: padded passwords take two scrypt checks only for real, unlocked accounts
- **Fingerprint:** `h1-login-timing-padded-password-enumeration`
- **Triage hint:** low (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** Dummy-hash equalisation covers one hash, but the real path performs a second hash when clean_password(typed) != typed, so work differs by input.
- **Why it matters:** An unauthenticated caller can distinguish existing unlocked usernames from unknown or locked ones, defeating the identical-message design (Phase BF). Staff usernames only; no credential access.

**Trace**
- entrypoint: `webapp/routes/sign_in.py:31` (login POST) Username and attacker-padded password go to authenticate; response identical, latency differs.
- propagation: `webapp/store.py:954` (Store.authenticate) Unknown username: one check against dummy hash, return.
- propagation: `webapp/store.py:957` (Store.authenticate) Locked account: one dummy hash check, return.
- sink: `webapp/store.py:961` (Store.authenticate) Existing unlocked account: check on typed string then on cleaned string when it differs: two scrypt computations.

**Evidence**
- `webapp/store.py:955` Comment states the intent: one check as for a real name with a wrong password.
- `webapp/store.py:447` clean_password strips spaces, tabs, line breaks, NBSP and zero-width characters at both ends, so a padded password always triggers the second check.

**Verifier corrections**
- Line 954 is the row-is-None test; the dummy check is at 955 (locked branch: test 957, dummy 958); sink spans 960-962.
- login also runs get_user_by_name (:23) and add_event (:36): extra small DB timing differences, not the claimed cause.
- Scope wider: for a real account a wrong padded password also writes the failed counter (store.py:965), so five padded guesses lock a real account, making lock state observable with identical text.

**Preconditions**
- Unauthenticated access to POST /login
- Padding such as a space in the password
- Enough samples per username to separate one from two scrypt costs within ~40 failures per 15 min per address (more with distributed sources)
- Guessed candidate username

**Blockers**
- Measured scrypt cost and latency delta on production host/network
- Whether the proxy adds noise or limits beyond the app throttle
- no sandbox available; source-only run
- scrypt cost and measurable latency difference on the production host and network path not observed

**Local validation plan:** In a sandbox, time Store.authenticate for an unknown user, a locked user and a real user with ' wrongpassword1 ' over many samples and compare medians.

**Owner-observed deployment check:** Owner on a staging copy with a throw-away account name: compare median /login response times for padded wrong passwords against a real and an unused username.

**Smallest source fix and regression test (proposal, not applied):** Make work constant in Store.authenticate: compute cleaned once and always run the same number of scrypt checks for every branch (second check against dummy or real hash when no padding). Regression test: count check_password_hash calls for unknown user, locked user, real user with padded wrong password and unpadded wrong password; counts must be identical.

## 6. A swap offer can be answered by an associate of another program who has the same roster name
- **Fingerprint:** `swaps.answer.roster-name-without-program`
- **Triage hint:** low (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** Ownership check keyed on a non-unique display roster name instead of the program-bound account found at offer time.
- **Why it matters:** An associate of a different program can accept or decline another program's pending swap in the real colleague's place, forging consent or blocking the swap; the real colleague can then no longer answer. Both teams' manager approval still gates the schedule change: integrity/consent bypass, not a direct roster change.

**Trace**
- entrypoint: `webapp/routes/my_week.py:206` (me_swap_answer) Any associate may call; swap_id from the path, g.user passed to swaps.answer.
- propagation: `webapp/swaps.py:255` (SwapBook.answer) Raises only if not is_associate or roster_name != row['other'].
- sink: `webapp/swaps.py:258` (store.move_swap) Moves swap from waiting_other to waiting_tm (accepted) or declined for the wrong person.

**Evidence**
- `webapp/swaps.py:216` account(program, name) binds the program at offer time; the answer check is weaker.
- `webapp/routes/admin.py:65` Duplicate roster names blocked only when accounts share a program.

**Verifier corrections**
- Sink is store.move_swap at swaps.py:259-260 (258 is the raise); entry my_week.py:206-212 is login_required only.
- Impact narrower than described: _sides() (swaps.py:275) resolves the real colleague via account(row['program'], row['other']), so the real colleague's team manager still must approve; the wrong person only decides the colleague's consent step.

**Preconditions**
- Authenticated active associate whose roster_name equals the target colleague's
- Disjoint programs (admin.py:65-66 blocks overlapping)
- A swap in waiting_other whose 'other' matches that name; ids sequential
- Production roster-name collisions across programs

**Blockers**
- Requires two associates with identical roster names in different programs (production data dependent)
- Source-only: duplicate-name setup not exercised
- Whether production has the same roster_name on associate accounts in disjoint programs
- no sandbox available; source-only run

**Local validation plan:** Dummy instance: 'Associate 07' in programs A and B; A's associate offers a swap to 'Associate 07'; answer as B's associate; expect refusal. Fix: compare user id to account(row['program'], row['other']) or require can_open(row['program']).

**Owner-observed deployment check:** Owner checks whether any roster name appears on associate accounts in two non-overlapping programs.

**Smallest source fix and regression test (proposal, not applied):** In SwapBook.answer resolve target = self.account(row['program'], row['other']) and require target is not None and target['id'] == user['id']; keep the roster_name check as secondary. Regression test: same roster_name in disjoint programs P1 and P2; offer in P1; answer as P2 associate must raise ValueError and leave waiting_other; P1 associate can still answer.

## 7. Volumes and people-sheet xlsx reader materialises every row before the row cap and may pad to a forged sheet dimension
- **Fingerprint:** `upload.read-only-iter-rows-unbounded-in-volumes-and-people-reader`
- **Triage hint:** low (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** Shared reader _rows has no row or column bound on iter_rows (unlike volumes_draft._sheets); row-count limits are enforced only after the whole sheet is in memory.
- **Why it matters:** A low-privilege signed-in user can make one request build a huge in-memory row list: high memory/CPU or an OOM-killed worker (availability only).

**Trace**
- entrypoint: `webapp/routes/volumes.py:439` (volumes_actuals_check) POST /volumes/actuals/check; upload read in full (452) and passed to read_table (458).
- propagation: `webapp/volumes_io.py:63` (read_table) Calls _rows, checks len(rows) > MAX_ROWS only after all rows exist.
- sink: `webapp/bulk_users.py:99` (_rows) [[cell for cell in row] for row in ws.iter_rows(values_only=True)] on read-only worksheet, unbounded; people upload reaches it via webapp/routes/people_file.py:110.

**Evidence**
- `webapp/bulk_users.py:98` load_workbook(read_only=True, data_only=True).worksheets[0] then unbounded iter_rows list.
- `webapp/volumes_draft.py:114` Sibling reader passes max_col=17 and max_row=MAX_SHEET_ROWS+50; _rows does not.
- `webapp/zipcheck.py:32` zip_problem limits expanded size; a forged dimension tag adds no bytes.

**Verifier corrections**
- Lines accurate (volumes.py:439-458, volumes_io.py:59-65, bulk_users.py:90-99, people_file.py:110).
- Forged-dimension padding is not needed: zip_problem (zipcheck.py:11-35) allows up to 250 MB expanded, 150 MB/member, ratio test only above 20 MB; a genuinely dense sheet within limits already becomes a multi-million-row list before the caps (volumes_io.py:64, bulk_users.py:123). The 500-row people cap applies to filtered output after every row is built (107-123).
- MAX_CONTENT_LENGTH 25 MB bounds only the request.
- In volumes_actuals_check, is_draft (volumes_draft.py:190-196) runs first and opens read-only without iterating; only non-draft uploads reach read_table. The draft path uses bounded _sheets (volumes_draft.py:114), unaffected.

**Preconditions**
- Authenticated user reaching POST /volumes/actuals/check for a program they may open, or a manager for /admin/users/bulk
- Non-draft .xlsx
- Web worker with limited memory or request timeout

**Blockers**
- Installed openpyxl version and read-only iter_rows padding behaviour (sandboxed local test)
- Role gating of the volumes check (who can reach it)
- Web process memory cap and timeout
- behaviour of installed openpyxl when dimension tag exceeds real data (empty-row padding) is not source-visible
- no sandbox available; source-only run

**Local validation plan:** In an OS-sandboxed, memory-capped environment, craft a minimal dummy xlsx with sheet1.xml dimension A1:XFD1048576 and one real cell; call bulk_users._rows and record row count and RSS; repeat with iter_rows(max_row=MAX_ROWS+1, max_col=...) to confirm a bound fixes it.

**Owner-observed deployment check:** Owner confirms installed openpyxl version and web process memory limit.

**Smallest source fix and regression test (proposal, not applied):** Bound the read in bulk_users._rows: iter_rows(values_only=True, max_row=cap+N, max_col=~30), raise the existing too-many-rows ValueError if rows beyond the cap have content, or iterate lazily and stop past MAX_ROWS; pass the cap (500 people, 400,000 volumes). Regression test: a small xlsx over the cap and one with a forged huge dimension are refused quickly with the row-limit message, rows materialised stay bounded.

## 8. Run upload workbooks that pass zipcheck can expand to hundreds of MB and are fully loaded by openpyxl in the web process
- **Fingerprint:** `upload.zipcheck-limits-too-loose-for-full-load-workbook-memory`
- **Triage hint:** low (not a severity)
- **Independent verdict:** needs_validation; trace verified: True; preventing control found: False
- **Claimed root cause:** zipcheck caps (250 MB total, 150 MB per member, ratio check only above 20 MB) are sized to avoid a zip bomb, not for peak memory of a non-read-only openpyxl load; no cell-count or dimension cap before that load.
- **Why it matters:** An authenticated uploader can drive the shared web process to very high memory or an OOM kill, taking the site down for all users until systemd restarts it (5 s). Availability only.

**Trace**
- entrypoint: `webapp/routes/runs.py:106` (submit_run) POST /runs saves upload to _incoming; body limit 25 MB (app.py:281).
- propagation: `webapp/zipcheck.py:32` (zip_problem) Accepts up to 2000 members, 150 MB/member, 250 MB total, ratio 100 only above 20 MB.
- propagation: `webapp/upload_guard.py:106` (look) Read-only, stops after 400k cells; does not limit what later loaders materialise.
- propagation: `webapp/routes/runs.py:152` (submit_run) _channel_upload_check calls has_channel_needs then read_inputs on a copy.
- sink: `webapp/day.py:175` (read_inputs) load_workbook(path, data_only=True) without read_only; ready path does same at webapp/ready.py:23.

**Evidence**
- `webapp/zipcheck.py:12` MAX_MEMBER_BYTES 150 MB and MAX_TOTAL_BYTES 250 MB are the only expanded-size limits.
- `webapp/ready.py:23` check_ready uses load_workbook(path) in the web process.
- `webapp/volumes_draft.py:114` Contrast: draft reader bounds max_row/max_col and uses read_only.

**Verifier corrections**
- All cited lines check out (runs.py:106/142/147/152, zipcheck.py:12-13,32-33, upload_guard.py:106 and 131, day.py:175, ready.py:23, volumes_draft.py:114, app.py:281).
- Ready-schedule path is stronger: RunQueue.submit_ready (runs.py:307) calls check_ready synchronously inside the POST /runs request, so the full non-read-only load happens in the Waitress web process after the only post-zipcheck gate (upload_guard.look).
- look() stops at 400k cells, but sparse or styled-empty 150 MB XML still passes; later non-read-only loaders materialise every cell.
- Ratio check (100x) applies only above 20 MB expanded; under 25 MB compressed an expansion of ~10x (250 MB) is allowed.

**Preconditions**
- Valid login and access to POST /runs
- Crafted .xlsx with required tabs whose sheet XML expands to ~150 MB per member / 250 MB total under the 25 MB body limit
- No mandatory memory cap on the service; host OOM behaviour decides impact
- Several concurrent uploads multiply memory

**Blockers**
- Actual MemoryMax/OOM policy and RAM of the live host (guide says 24 GB)
- Any upstream rate limit or per-user concurrency gate (Caddy, login limits)
- Largest legitimate workbook to set caps safely
- Peak RSS of non-read-only openpyxl load for ~150 MB sheet XML on the installed version
- no sandbox available; source-only run
- peak openpyxl memory for a 150 MB sheet XML, installed openpyxl version and service memory limit are not source-visible

**Local validation plan:** In an OS-sandboxed, memory-capped environment, build a dummy workbook with one sheet of ~20 MB compressed / 150 MB XML numeric cells, run zip_problem then check_ready and read_inputs, record peak RSS against the cap.

**Owner-observed deployment check:** Owner checks the systemd unit for MemoryMax/OOM policy and the largest expanded workbook the site accepts, without uploading oversize files to the live site.

**Smallest source fix and regression test (proposal, not applied):** Lower expanded caps to real workbook size (e.g. member ~30-50 MB, total ~60-80 MB) and ratio-check above ~1 MB; add MemoryMax= and TasksMax= to deploy/scheduler-web.service; optionally check ws.max_row/max_column from the read-only look before full loads. Regression test: synthetic zip just over the cap returns a problem, just under returns empty string.
