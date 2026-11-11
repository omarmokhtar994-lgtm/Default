# Security audit report: Team Scheduler website (webapp/ and deploy/)

## 1. Run facts
- **Profile:** quick. One hunter wave, one final coverage critic, one fresh verifier per candidate. **This is a partial pass, not a clean bill of health.**
- **Scope:** `webapp/` (not tests) and `deploy/`. Engine, RC9.1 baseline workbooks and `engine/regression_assets` out of scope.
- **Source ref:** 8fec106d68e4e630dba5263f1e778e8b7e06bd94 (worktree clean). No prior ledger existed; nothing carried over.
- **Budget:** 21 of 40 agent invocations used (4 reconnaissance, 8 hunters, 1 critic, 8 verifiers).
- **Execution policy: source-only.** This machine has no OS-enforced sandbox and Flask/ortools are not installed, so no target code, tests or servers were run and nothing was sent to the live site. Therefore **no finding could be confirmed** (a confirmed record needs an observed local result).
- **Deviations from the skill text:** hunters read the skill's attack-class and method blocks from files instead of receiving them pasted into the prompt; the output folder is outside the repository (scratchpad), copied here afterwards; in the quick profile Phase 3 and Phase 5 are merged (one verifier per candidate).

## 2. Security posture (short)
Sign-in, sessions, CSRF, redirects, CSP and templates, exports, webhooks, SQL and the deploy scripts held up under source review: no injection, no auth bypass, no open redirect, no XSS path and no secret leakage was found in the areas reviewed. The leads below are authorization and robustness gaps, all unverified by execution. The two with the most weight are a **possible cross-program write through the RTA day POST routes** and **supervisor management of users who hold programs the supervisor does not**. Large parts of the code (see section 7) were not reviewed.

## 3. Confirmed findings
None. Nothing was executed, so nothing could be confirmed. Do not read this as "no vulnerabilities".

## 4. NEEDS VALIDATION (leads, no severity)
The triage hint is only an ordering aid from the verifier, not a severity.

| Triage hint | Lead | Trace | Main blocker |
|---|---|---|---|
| medium | RTA day POST routes authorize one program but act on another (query string versus form field) | webapp/app.py:394 -> webapp/attendance.py:1268 | Runtime confirmation of Werkzeug request.values ordering on POST and that empty ?program= leaves the form value in effect |
| medium | A supervisor can reset the password of, and so take over, a user who also holds programs the supervisor does not have | webapp/routes/people_file.py:236 -> webapp/routes/sign_in.py:17 | Owner confirmation of intended policy |
| low | Cancelling a coaching or break request by id redirects to the request's program even when it is not the caller's | webapp/routes/break_changes.py:110 -> webapp/routes/break_changes.py:122 | Confirm at runtime the Location header carries program=B for a cross-program id |
| low | Lockout failure counter is a lost-update race, so concurrent guesses exceed 5 per lock | webapp/routes/sign_in.py:31 -> webapp/store.py:963 | Confirm hashlib.scrypt releases the GIL and 8 threads overlap on the deployed Python |
| low | Username enumeration by timing: padded passwords take two scrypt checks only for real, unlocked accounts | webapp/routes/sign_in.py:31 -> webapp/store.py:961 | Measured scrypt cost and latency delta on production host/network |
| low | A swap offer can be answered by an associate of another program who has the same roster name | webapp/routes/my_week.py:206 -> webapp/swaps.py:258 | Whether production has the same roster_name on associate accounts in disjoint programs |
| low | Volumes and people-sheet xlsx reader materialises every row before the row cap and may pad to a forged sheet dimension | webapp/routes/volumes.py:439 -> webapp/bulk_users.py:99 | Installed openpyxl version and read-only iter_rows padding behaviour (sandboxed local test) |
| low | Run upload workbooks that pass zipcheck can expand to hundreds of MB and are fully loaded by openpyxl in the web process | webapp/routes/runs.py:106 -> webapp/day.py:175 | Peak RSS of non-read-only openpyxl load for ~150 MB sheet XML on the installed version |

Full traces, blockers and safe validation plans: `NEEDS-VALIDATION.md`.

## 5. Leads the recon suggested that source refuted
- Missing last-admin guard on disable and bulk switch-off: refuted. Self-disable is refused and only an admin can manage an admin, so the acting admin always stays active. Residual: two admins disabling each other concurrently (hardening, recoverable with `manage.py enable-user`).
- Dynamic SQL identifiers in `store.py`: refuted. Every identifier comes from a code constant or a whitelist; values are bound parameters.
- Volumes upload skipping `zipcheck`/`upload_guard`: refuted for the normal path (all readers call `zip_problem`); only the unbounded row read remains (lead 7).
- Path-id routes skipping the program check (`my_week.py:206/224`, `break_changes.py:179/204`): refuted for cross-program reads; see leads 3 and 4 for the two narrower gaps.
- `ProxyFix` plus the sign-in throttle: no client-controlled evasion visible in source while Caddy is the only entry (depends on Caddy config).

## 6. Hardening notes (not findings)
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

**Positive patterns seen:** server-side session revocation and a password-hash stamp; CSRF checked first on every POST; `safe_next` on every redirect; strict CSP with Trusted Types and no inline script; no `|safe` or `render_template_string`; export formula neutralisation; secrets via `secrets`, 0600 key file; webhook link admin-only, masked, host allow-listed, redirects refused; sealed read-only code and least-privilege service unit; upload pipeline with zip limits, macro/external-link refusal and `secure_filename`.

## 7. Coverage summary
Ledger: 15 units. Covered 5, candidate 3, blocked 0, deferred 7.
- **Reviewed:** authentication and sessions, route authorization, uploads and paste, exports and downloads, templates/CSP/JS, webhooks and secrets, store/business logic, deploy scripts and service unit.
- **Deferred (accepted by the final critic, not assigned in the quick profile):** RTA day write layer (`attendance.py`, `merged_day.py`, `channel_day.py`); group-post notifier send path; run lifecycle and admin (`runs.py` queue, `run_admin.py`); schedule versions and schedules (`versions.py`, `schedules.py`); per-user/per-run downloads (`Temporary_passwords.xlsx` and the like); about 30 unmapped feature modules; operator tooling.
- **Parent ruling on the critic's reassign list** (h2 route authorization, h7 business logic, h6 webhooks): not reassigned as separate attempts, because the gaps it points to are captured as the deferred units above. Cost if wrong: those three units keep a closed status on route-level and SQL-level evidence only.
- **Final critic result:** coverage solid for deploy scripts, auth/sessions, CSP/templates, export neutralisation and webhook allow-listing; thin for the large handler and domain modules. One more wave on the day write layer, run lifecycle and versions would add most of the value.
- Already-known items from `docs/security/SECURITY_STATUS_2026-11-11.md` were excluded, not re-reported.
