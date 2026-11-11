# Security audit report: Team Scheduler website (webapp/ and deploy/)

## 1. Run facts
- **Profile:** started as quick (wave 1), changed to standard for wave 2 at the owner's request. Two hunter waves, two coverage-critic passes, one fresh verifier per lead. **Coverage is partial. This is not a clean bill of health.**
- **Scope:** `webapp/` (not tests) and `deploy/`. Engine, RC9.1 baseline workbooks and `engine/regression_assets` out of scope.
- **Source ref:** 8fec106d68e4e630dba5263f1e778e8b7e06bd94 (worktree clean). No code was changed.
- **Budget:** 34 of 40 agent invocations used (4 reconnaissance, 15 hunters, 2 critics, 13 verifiers). The remaining 6 cannot fund another hunter wave plus the final critic and verifiers, so the run stops here with the gaps listed in section 7.
- **Execution policy: source-only.** No OS-enforced sandbox exists on this machine and Flask/ortools are not installed, so no target code, tests or servers were run and nothing was sent to the live site. **No lead could be confirmed**, because a confirmed record needs an observed local result.
- **Deviations from the skill text:** hunters read the skill's attack-class and method blocks from files instead of receiving them pasted into the prompt; the output folder is outside the repository (scratchpad) and copied here afterwards; Phase 3 and Phase 5 are merged (one verifier per candidate); the final-clean critic was not run (budget); the 'quick' profile ledger IDs were kept for wave-1 units.

## 2. Security posture (short)
Sign-in, sessions, CSRF, redirects, CSP and templates, exports, webhook link checks, SQL, uploads (path and argv handling) and the deploy scripts held up under source review: no injection, auth bypass, open redirect, XSS path or secret leakage to a lower-trust user was found in the areas reviewed. The leads are authorization and robustness gaps. The ones with the most weight: **the RTA day POST routes check one program and act on another**, **a user removed from a program keeps control of runs and live schedules they uploaded**, **supervisors can manage users who hold programs the supervisor lacks**, and **one large forecast request can pin the web server's CPU**. All are unverified by execution.

## 3. Confirmed findings
None. Nothing was executed, so nothing could be confirmed. Do not read this as "no vulnerabilities".

## 4. NEEDS VALIDATION (leads, no severity)
The triage hint is only an ordering aid from the verifier, not a severity.

| # | Triage hint | Lead | Trace | Main blocker |
|---|---|---|---|---|
| 1 | medium | RTA day POST routes authorize one program but act on another (query string versus form field) | webapp/app.py:394 -> webapp/attendance.py:1268 | Runtime confirmation of Werkzeug request.values ordering on POST and that empty ?program= leaves the form value in effect |
| 2 | medium | A supervisor can reset the password of, and so take over, a user who also holds programs the supervisor does not have | webapp/routes/people_file.py:236 -> webapp/routes/sign_in.py:17 | Owner confirmation of intended policy |
| 3 | medium | A user removed from a program keeps read, edit, in-use and delete control over the runs and schedule versions they uploaded into it | webapp/routes/week_channels.py:256 -> webapp/schedules.py:746 | Whether the owner intends uploaders to keep control of their own runs after losing the program (wave-1 note: 'confirm intended') |
| 4 | medium | One forecast request with a large typed total can pin a server thread on quadratic Erlang arithmetic | webapp/routes/volumes.py:270 -> webapp/erlang.py:82 | Actual wall-clock cost at 1,000,000 and 5,000,000 contacts per week not measured |
| 5 | low | Cancelling a coaching or break request by id redirects to the request's program even when it is not the caller's | webapp/routes/break_changes.py:110 -> webapp/routes/break_changes.py:122 | Confirm at runtime the Location header carries program=B for a cross-program id |
| 6 | low | Role back-limit on RTA edits can be bypassed with a per-move date in Replan/Rescue apply | webapp/routes/day.py:958 -> webapp/attendance.py:1268 | Runtime confirmation that a non-admin Planner can post a move beyond their limit and have it applied (schedule version for that date must exist; KEEP_DAYS 395) |
| 7 | low | Lockout failure counter is a lost-update race, so concurrent guesses exceed 5 per lock | webapp/routes/sign_in.py:31 -> webapp/store.py:963 | Confirm hashlib.scrypt releases the GIL and 8 threads overlap on the deployed Python |
| 8 | low | Username enumeration by timing: padded passwords take two scrypt checks only for real, unlocked accounts | webapp/routes/sign_in.py:31 -> webapp/store.py:961 | Measured scrypt cost and latency delta on production host/network |
| 9 | low | A swap offer can be answered by an associate of another program who has the same roster name | webapp/routes/my_week.py:206 -> webapp/swaps.py:258 | Whether production has the same roster_name on associate accounts in disjoint programs |
| 10 | low | Volumes and people-sheet xlsx reader materialises every row before the row cap and may pad to a forged sheet dimension | webapp/routes/volumes.py:439 -> webapp/bulk_users.py:99 | Installed openpyxl version and read-only iter_rows padding behaviour (sandboxed local test) |
| 11 | low | Run upload workbooks that pass zipcheck can expand to hundreds of MB and are fully loaded by openpyxl in the web process | webapp/routes/runs.py:106 -> webapp/day.py:175 | Peak RSS of non-read-only openpyxl load for ~150 MB sheet XML on the installed version |
| 12 | low | Schedule version download writes a planner's free-text change reason into the Version Notes sheet as a live formula | webapp/routes/week_channels.py:218 -> webapp/versions.py:739 | Confirm with the installed openpyxl that ws.cell(r, c, '=...') yields data_type 'f' in the saved file |

Full traces, blockers, safe validation plans and proposed fixes: `NEEDS-VALIDATION.md`. Leads 1, 2 and 5 are the same family (program checks that read a different place than the code that acts); one fix design can cover them.

## 5. Recon leads that source refuted
- Missing last-admin guard on disable and bulk switch-off: refuted (self-disable refused; only an admin manages an admin). Residual: two admins disabling each other at the same time (hardening).
- Dynamic SQL identifiers in `store.py`: refuted (constants or whitelists; values bound).
- Volumes upload skipping `zipcheck`/`upload_guard`: refuted for the normal path; only the unbounded row read remains.
- Path-id routes skipping the program check for cross-program reads: refuted; the narrower gaps are leads 4, 5, 7 and 9.
- `ProxyFix` plus the sign-in throttle: no client-controlled evasion visible in source while Caddy is the only entry.
- Group-post replay or cross-program posting by action id, mention/markdown injection in posts, path building from run ids, argv/env of the engine and channel-solver subprocesses, one-time password sheet scope and caching, People.xlsx fields: all held.

## 6. Hardening notes (not findings)
- **Defect against the project rule 'notification secrets never go in logs'** (verifier verdict: hardening only, because only an admin can save the link and already knows it): webapp/notify.py `check_link` accepts a space or control character inside the webhook path or query, and `send_json` does not catch `http.client.InvalidURL`, so `_attempt` and `send_test` write the exception, which includes the secret path, to the service log on every try (notify.py:372, 579-580, 691-692). Fix: reject characters <= 0x20 or 0x7f in `check_link`; catch `http.client.HTTPException` in `send_json` and return (False, 0) without logging its text; regression tests for both.
- Cap erlang work: raise ValueError above a traffic limit (e.g. 5,000 Erlangs) or search by doubling and bisection with one Erlang recursion; regression test with calls=5_000_000 per interval that finishes quickly.
- routes/volumes.py:124: use asked.isascii() and asked.isdigit() (or try/except ValueError) so a superscript digit gives the 400 message, not a 500.
- coach_page and coach_download accept up to 400 days without the _heavy_limit and deadline used by incidents, shrinkage and exports; apply the same ExportDays guard.
- VolumeBook held-actuals store (_held in routes/volumes.py:48) has no per-user or total cap for the 20-minute window; each held check can carry up to 400,000 parsed rows (same-principal availability).
- schedules.break_rules cache read (schedules.py:524) is outside the try and the write is not atomic; write to temp and rename, and treat a bad cache as a miss.
- manage.py enable-user and reset-password accept deleted-N accounts and has-admin counts disabled admins; refuse deleted rows.
- The two xlsx files in webapp/workbooks were not opened (binary); the owner should check they hold no external links, macros or real names.
- Notifier.send_action computes action_state, held and items before self._lock, so a double submit of /day/send can queue two posts for the same held items.
- /day/send with again=1 has no rate limit; an RTA user can flood their own LOB's group. Same principal.
- Notifier.run_once sends one post at a time with a 10 s timeout; one slow group delays other LOBs by up to 10 s per message (availability).
- day_send does not check action['undone_at']; an undone bulk action already posted can be re-sent with again=1 (intended resend path).
- store.get_day_action has no program filter; add a program parameter to make the invariant structural.
- Teams card text still renders bare URLs and underscore italics from with_whom/with_dept (capped); no mention or link syntax can form.
- people_file.py:170-173: get() then pop() on the one-time password sheet; use a single pop(token, None).
- people_file._bulk_held prunes only when a bulk route runs and iterates held.items() without a lock; unfetched sheets and typed passwords of a checked-but-never-added file can stay in memory beyond the TTL. Lock and prune on every request or use a timer; drop typed passwords from held rows after planning.
- admin_users_bulk_add pops the token before creating accounts; a mid-loop failure leaves accounts created with generated passwords never shown. Create rows in one transaction or keep the token until success.
- channel_template._lists writes language names from the uploaded workbook raw (formula-capable); neutralise with the _safe used in bulk_users.py (same as channel_export note).
- Temporary_passwords.xlsx and post-add page show generated passwords once in clear (by design); reset flash already known.
- DayBook._locks keeps one RLock per (program, date) forever; program strings (80 chars) can be arbitrary for admin/all-programs users (and via the known mismatch), an unbounded in-memory growth point; prune or key only on known programs.
- book_session skips its busy test when minutes <= 0; reject non-positive minutes explicitly.
- day_send lets any RTA-change user of the program post any other user's bulk action; confirm intended.
- day_add shifts the day back by one in _running_day after the back-limit check ran on the form date (planner can touch today-2 for a running overnight shift): minor variant of the back-limit gap.
- Undo journal covers only on-1..on+1, so changes on other dates (dated moves, bulk with start) cannot be undone or attributed by Undo; the day_log line remains.
- RunQueue.stop() QUEUED branch writes STOPPED without self._lock while _claim() can have moved the run to GATE; the worker keeps executing and a later Resume could start a second execution of the same results folder when PARALLEL>1. Do the check and update under the lock, conditional on status='QUEUED'.
- resume() and run_delete have check-then-act status reads without a lock or conditional update.
- stop and resume need only visibility plus 'runs', while zone/tag/delete/set-in-use need uploader or admin; confirm any same-program planner may stop or resume a colleague's run.
- submit() runs the workbook check synchronously (up to 300 s) on 8 waitress threads; no per-user or global limit on queued or stored runs (30-day retention): a user with 'runs' can occupy request threads or fill disk. Add a per-user in-flight cap and move the check into the worker.
- run_tag/apply_run_change compute the preview and apply in separate steps (same-principal TOCTOU only).
- RUN_ID uses ^...$ which also matches a trailing newline; harmless today (exact DB lookup follows); use re.fullmatch or \Z.
- cleanup() rmtree after a stale list_runs snapshot can race a Resume of an old STOPPED or FAILED run; re-read status under the lock.
- Access.__init__ runs ProgramBook.sync() (a write) on every request that builds Access; harmless registry registration, but a read path doing writes.
- versions.with_notes and channel_export: apply one shared neutraliser to every free-text cell (prefix leading =,+,-,@,tab,CR with an apostrophe or set data_type='s'); add a regression test with reason '=1+1'.
- schedules.set_in_use serialises on the run lock but scopes by program and week: two uploaders can leave two in_use=1 rows. Lock on program+week or use one begin immediate transaction.
- GET run_schedules calls queue.keep_schedules (copies files, runs validator, fires on_kept) for any viewer with schedules_view; side effects on a GET, idempotent.
- run_admin.preview_run_change and store.move_run: in-use conflict check runs before the transaction; re-check inside move_run.
- Break and channel drafts keyed by schedule_id only: two planners on one version overwrite each other's unsaved drafts (same program/role).
- schedules.break_rules writes break_rules.json non-atomically; use temp file + os.replace.
- Uploader-access-after-program-removal (candidate runs.uploader-access-outlives-program-removal) also covers set-in-use, delete, run_tag and every schedule edit route: variant of the same root cause.
- routes/day.py:352-357: Rescue the day and replan previews (CP-SAT up to 12 s, 4 workers, in the web process) run for any rta_view caller while Fix channels preview requires rta_change; gate or rate-limit the same way and consider the isolated child like channel_solver.
- gate.py GateFailed text (log path + last 15 lines of run_tests output) is shown to everyone who can open the run; show a short message and keep detail in the server log.
- gate.py PASS stamp keyed only by sha256(MANIFEST.json) in DATA_DIR/runs/_gate; consider hashing the package files the manifest lists or storing the stamp outside DATA_DIR.
- channel_solver.solve: child has no memory or CPU rlimit and concurrent planner clicks each start 4 workers; add a global semaphore.
- live_stamp absent from PERMISSION_ENDPOINTS: digest-only change oracle.
- upload_guard.look returns None when read-only load fails and stops at 400000 cells, so the personal-data refusal can be bypassed; policy filter only, document it.
- channels.read_channels non-read-only load_workbook and _asks_for_someone list(iter_rows) per candidate break: same memory class as known leads 7 and 8.
- apply_patch.sh: confine PATCH.json files[].path (reject absolute, '..', newlines; resolved path must stay under $PKG) in the Python check, before shell mkdir/cp/rm and in put_back; add regression patch with '../x' and '/tmp/x' that must be refused.
- apply_patch.sh/update.sh: new_sha256 is taken from the same zip; consider operator-held checksum or signature for update and patch zips (they run zip content as root).
- apply_patch.sh swallows failed root pip install (|| true); update.sh leaves service stopped if pip install fails after seal; surface error and roll back.
- requirements.txt: openpyxl, pandas, numpy, scipy lower-bound only; consider pins or hashed lock (--require-hashes).
- install.sh: Caddy apt key piped curl|gpg without fingerprint check; IPv6 (ip6tables) not handled.
- scheduler-web.service optional directives: UMask=0077, CapabilityBoundingSet=, RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6, PrivateDevices=yes, ProtectKernelModules/Logs/Clock/Hostname, LockPersonality, RestrictNamespaces, RestrictRealtime, SystemCallFilter=@system-service (test with CP-SAT subprocess; MemoryDenyWriteExecute likely incompatible).
- Caddyfile.template: HSTS no includeSubDomains; response_header_timeout 10m, no read timeouts; no proxy-level security headers (app sets CSP).
- webapp/channel_export.py writes associate name and language raw via ws.append, unlike exports.py and daily_views.py (_safe) and bulk_users.py; a name starting with '=' would become a formula in the channel-plan download. Origin is the planner-uploaded workbook, impact low. Apply the neutraliser or set data_type='s'.
- Exports 'Other actions' (record) with program=None for users with all_programs lists events with empty program: signed_in, sign_in_failed and sign_in_held (source IP, username), password_reset, user_disabled, user_deleted. Any non-admin with all_programs and default-on Exports permission can export them. Likely intended as audit trail; consider limiting global event kinds to admins.
- schedule_versions._can_see_run and app._visible keep access to runs the person uploaded after their program assignment is removed, so a former program member can still download those schedule workbooks. Authorisation/lifecycle question for the access unit; settle whether intended.
- _csv_safe prefix list does not cover a leading space or newline before '='; theoretical, Excel does not evaluate such cells.
- people_file.py:278 puts the one-time temporary password in a flash message; Flask's default session is a signed, not encrypted, client cookie, so it sits base64-encoded in the admin's own cookie until the next page. Same principal, not a boundary crossing; a server-side flash or render-once page would avoid it.
- notify.py check_link: *.logic.azure.com and *.api.powerplatform.com are multi-tenant, so an admin (or stolen admin session) can send RTA change text to an attacker-owned Logic App; pinning tenant/region is optional hardening.
- app.py _secret_key: a crash between O_EXCL create and write leaves an empty secret_key file; Flask then fails closed (availability only). Write to temp and rename, or regenerate when empty.
- Webhook link stored plaintext in notify_settings (covered by the known service-account item).
- store.authenticate failed-login counter is a non-atomic read-modify-write (same issue as candidate h1-lockout-counter-lost-update).
- swaps.answer checks only roster_name == row['other'], not that the answering user can open row['program']. Roster-name uniqueness is enforced only among users sharing a program, so a namesake associate in another program could accept a swap meant for someone else; the TM approval step still follows. Fix: also require can_open(row['program']) and that the account is the one swaps.account(program, other) resolves to.
- swaps: a failed _apply after both sides were TM-approved returns status to waiting_tm with tm_a_id and tm_b_id still set; _mine then returns [] for every approver so nobody can approve or refuse. A swap left 'applying' by a crash has no recover() (unlike leave.recover()), cannot be cancelled and blocks both days through _open_days. Fix: clear tm ids on rollback; add swaps recover() at start-up.
- change_requests: update_change_request has no status guard; use 'update ... where id=? and status=waiting' so concurrent cancel/expire/decide cannot overwrite a terminal state.
- Two admins acting concurrently (A disables or demotes B while B does the same to A) can leave zero active admins; recovery needs manage.py enable-user. Check the last-admin count inside one begin immediate transaction in set_active and update_user.
- admin_user_action does not reject a deleted target (get_user returns deleted rows): an admin or an all-programs supervisor can enable or reset the password of a 'deleted-N' account, which then signs in as a role-less planner with no programs. No data access gained. Fix: 404 when target['deleted'].
- add_user: usernames of the form deleted-<id> are not reserved, so a manager can create one that makes a later delete_user for that id raise IntegrityError. Self-inflicted availability only. Reserve the prefix in username_problem.
- Store._db wraps reads and writes without begin immediate except in transaction(); multi-step check-then-act flows (leave.ask overlap check, add_user username check) rely on the unique constraint or the in-process day lock. Low impact, same principal.
- CSP has no explicit script-src/connect-src (falls back to default-src 'self'); adding script-src 'self' only makes intent explicit.
- HSTS max-age one year without includeSubDomains/preload; depends on other subdomains (not source-visible).
- download_name values built from user-influenced names rely on Werkzeug header quoting (see exports unit).
- people_file/_rows CSV path: csv.reader raises csv.Error for a field over 131072 chars (and NUL on older Python); parse_pasted has the same exposure with up to 400,000 pasted chars; likely a 500 instead of a message. Catch csv.Error.
- submit_run catches only ValueError, KeyError, OSError, BadZipFile around _channel_upload_check; other parser exceptions give a 500 and leave the .upload file in _incoming until the 24h sweep (runs.py:592).
- Volumes paste path does not run look_rows, but pasted text is parsed strictly to dates and numbers; nothing free-text is stored.
- defusedxml protection of openpyxl depends on the package being installed on the server; consider a startup check that openpyxl.xml.DEFUSEDXML is true.
- Throttle.held/failed protect addresses as seen by ProxyFix(x_for=1): correct while Caddy overwrites or appends X-Forwarded-For (no trusted_proxies). Pin that in deploy docs; do not widen x_for.
- SignInThrottle.failed scans every tracked address on each failure (O(n)); rotating many source addresses (e.g. IPv6 /64) grows the dict and CPU per failed login. Availability-class.
- Per-IP throttle holds a whole address including right passwords; users on one NAT lose sign-in 15 min after 40 wrong tries. Accepted by design.
- Per-account lock at 5 wrong passwords is an accepted lockout-denial lever (admin unlock exists); not re-reported.
- logout revocation entries pruned after 30 days, past the 1-hour lifetime: no replay window.
- No default-deny global login gate: authentication is per-route via decorators; scan found no unprotected non-public route today, but a new route without a decorator would be open (consider an endpoint allow-list check in before_request).
- _can_see_run (app.py:445) lets the uploader see and edit a run after losing the run's program: run access outlives program removal. Confirm intended.
- requests_page and requests_coaching GET are not in permissions.ENDPOINTS and are open to any non-associate with program access regardless of approve_tm/approve_rta; decisions are enforced in the decide methods, so only the read is wider than the matrix.
- OPEN_TO_ALL (app.py:363) skips the program wall for submit_run, run_tag, program_rename, program_setup, workbook; submit_run and run_tag re-check can_open, the others are admin-only or a fixed allow-list. No bypass found.
- Last-admin-on-disable lead refuted; concurrent mutual disable by two admins possible, minor.
- live_stamp returns only digests and checks can_open; no leak found.
- Associate-wall cross-program IDOR on my_week.py:206/224 and break_changes.py:179/204 refuted: decide routes call can_open(row.program) and decide methods re-check roles.

**Positive patterns seen:** server-side session revocation and a password-hash stamp; CSRF checked first on every POST; `safe_next` on every redirect; strict CSP with Trusted Types and no inline script; no `|safe` or `render_template_string`; export formula neutralisation; secrets via `secrets` and a 0600 key file; webhook link admin-only, masked and host allow-listed with redirects refused; sealed read-only code and least-privilege service unit; upload pipeline with zip limits, macro/external-link refusal and `secure_filename`; run ids validated by regex and exact lookup; list-form subprocess argv everywhere; channel solver child with fixed argv, timeout and strict response validation; day edits all-or-nothing with a journal.

## 7. Coverage summary
Ledger: 23 units. Covered 9, candidate 7, blocked 0, deferred 7.
- **Reviewed (waves 1 and 2):** authentication and sessions; route authorization; uploads and paste; exports and downloads; templates, CSP and JS; webhooks and secrets; store and business logic; deploy scripts; RTA day write layer; group-post sender; run lifecycle; schedule versions; credential and per-run downloads; home, live, rescue, channel and gate modules; forecast and volumes routes; operator CLI.
- **Deferred (accepted by the final critic, not assigned):** DayBook page builders and break-rule engines; run start, validator options and `gate.ensure`; **leave and swap application writing schedule versions and setting them in use without `_may_set_in_use`** (the critic's top gap); analytics, outlook and results compute modules; page-builder modules; volumes helper modules and the break-rules CLI; the contents of the two shipped template workbooks (needs an unzip-level look).
- **Files in no unit's reviewed paths (critic list):** webapp/adherence.py, webapp/analytics.py, webapp/break_plan.py, webapp/clock.py, webapp/eta.py, webapp/forecast_methods.py, webapp/insights_page.py, webapp/merge.py, webapp/outcome.py, webapp/outlook.py, webapp/paging.py, webapp/program_page.py, webapp/results.py, webapp/shrink_page.py, webapp/volumes_formulas.py, webapp/volumes_grain.py, webapp/volumes_zone.py, webapp/week.py, webapp/window_tools.py.
- **Parent ruling on the critic's reassign list:** not reassigned. Those units hold candidates with independent verdicts; reopening them would repeat reviewed ground. Cost if wrong: some candidate-bearing units keep their closed status on route-level evidence.
- **Final critic result:** Coverage partial: 19 of about 75 webapp modules are in no unit's reviewed_paths. The most valuable remaining gap is the leave/swap approval path writing schedule versions and setting them in use without _may_set_in_use; next run_start with gate.py and validator-subprocess options; third the unreviewed compute and page modules taking request parameters the app.py program check may not see. Based on file-list and ledger comparison only.
- Already-known items from `docs/security/SECURITY_STATUS_2026-11-11.md` were excluded, not re-reported.
