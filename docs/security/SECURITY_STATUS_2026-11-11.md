# Security status and verdicts, 2026-11-11 (website and its host only)

Prepared from the owner's handoff and the assessment bundle (`Scheduler_Security_Assessment.zip`), checked against the source, in a local environment with
Flask, Werkzeug, OR-Tools and a browser. **Nothing in this file is a live result**: the server was not touched, and nothing here is an independent penetration
test or an InfoSec approval. "Local" means exercised here; "live" means true on the server and must be shown there.

## Source reconciliation
- The repository matches all ten `original_sha256` values in `evidence/patch_identity.json` (checked against the commit the reviewed package was built from).
  So the repository did not contain the deployed website patch; its ten files are now in the repository, byte for byte as deployed except the changes listed
  under "What this release changes on top".
- The bundle's `proposed_patch` files match their recorded `proposed_sha256`. The copyright-only follow-up differs from the deployed test file by its first line only.

## Verdict for each reported item
| Item | Verdict | Evidence |
|---|---|---|
| Password minimum length bypassed by padding (checked raw, hashed cleaned) | **Valid, fixed (deployed)**; the fix was call-site only | The new regression test fails on the original `app.py` and `admin.py` and passes on the patched ones. Gap found: other callers and the store itself were unguarded. Now `hash_password` checks the cleaned password against `MIN_PASSWORD_LENGTH`, and the bulk people sheet has its own test. **Not retroactive**: accounts already stored with a short effective password are not found or reset. |
| Non-ASCII CSRF token gave a server error | **Valid (500 instead of 400), not a bypass; fixed (deployed)** | Regression test fails on the original `auth.py`. |
| Missing schedule file and bad wallboard input gave uncaught exceptions | **Valid robustness defect (seen under synthetic fixtures; not evidence that production files are missing); fixed (deployed)** | Regression tests fail on the original `week_channels.py` and `day.py`. Gap found: both handlers swallowed the cause silently. Now each logs a warning with the route and cause (below error level), and tests check it. |
| Old sweeps could pass a 500 | **Valid; tightened (deployed)** | The tightened asserts run and pass. |
| Code-write: the service can rewrite its own code | **Valid, open live; proposal validated locally, with corrections** | See "Code-write containment". |
| Unrestricted egress, host OUTPUT accept | **Valid, open; design written, not installed** | `docs/security/EGRESS_DESIGN.md`. |
| SSH from 0.0.0.0/0, root login, forwarding | **Open, infrastructure** | Needs the effective sshd config and an approved source range; not changed here. |
| OS updates and reboot pending | **Open, infrastructure** | Refresh the patch state; do not do an untested distro upgrade. |
| MFA/SSO, backups and restore tests, monitoring, webhook approvals, secrets inventory | **Unverified** | Not evidenced; no defect asserted. Owners and follow-ups in the table at the end. |
| Two resource warnings | **Located; two fixed, one explained** | `test_at_security.py:403` (static file response never closed) and `test_auth.py:121` (`with sqlite3.connect(...)` does not close the connection): both test code, both fixed. The third is a temporary upload file left by the 26 MB body test in `test_bf_attacks.py:270` inside Werkzeug's test client; not traced to production code. |
| "No known vulnerabilities" from pip-audit | **Plausible, dated** | Published Python advisories on 10 November only; refresh, and it says nothing of the operating system, Caddy or custom code. |
| Session length "12 hours" | **Checked: it was a sliding 12-hour idle limit with no absolute cap** | Changed on the owner's instruction to **one hour with no activity**. Tests below. |

## What this release changes on top of the deployed patch
1. **Password floor in the store** (`webapp/store.py`): `hash_password` refuses what is shorter than 10 once spaces and invisible characters at its ends are
   removed. Every caller was already guarded; this makes the store the last line.
2. **Logged warnings** in the two new error handlers (no silent 404 or 400).
3. **Read-only code** (below).
4. **One-hour idle session limit** (`webapp/app.py`): was 12 hours. Each page load starts the hour again; a page's own background requests do not (the page
   watcher's 30-second question was already excluded by `QuietSessions`). One hour is the ceiling in code. The live wallboard reloads itself every minute
   (a page load) and so stays up by design; a run page left open only watching its status will be signed out after an hour.
5. **Passwords expire after 30 days** (owner request): a password older than 30 days must be changed before anything else (the forced change page);
   the last 7 days show a reminder on every page. Accounts that exist at the update start their 30 days then; this does not find or fix passwords that are
   short or weak today, it only makes every password change within 30 days. (Periodic expiry is the policy asked for; it is not a substitute for MFA.)
6. **Unlock button** (owner request): a locked account shows "Locked, about N min left" on the People page with an Unlock button. Admins unlock anyone;
   supervisors only people in their own programs, never an admin, another supervisor, or themselves. It clears the lock and the count, leaves the password
   alone, and is recorded ("Account unlocked"). Releasing a held IP address stays admin-only (owner's choice).
7. Test fixes for two resource leaks; `docs/security/EGRESS_DESIGN.md`; `tools/readonly_check.py`.

## Code-write containment
**Problem confirmed from source.** The service file allowed `ReadWritePaths={{DATA_DIR}} {{APP_DIR}}/package`; install, update and patch scripts ran
`chown -R scheduler:scheduler` on the package. So the website's account could change the code that runs after a restart.

**Change** (candidate, not installed live):
- `deploy/seal_package.sh`: root owns the package, the account can read and run it; removes every `__pycache__`; verifies (and `--check` reports) anything
  not root-owned, group/other-writable, a link leaving the package, a file with more than one name, or unreadable by the account. It refuses to run on a
  non-package folder, never follows links, and never touches the data folder.
- `scheduler-web.service`: `ReadWritePaths={{DATA_DIR}}` only; `ReadOnlyPaths` the package and the venv; `PYTHONDONTWRITEBYTECODE=1`;
  `PYTHONPYCACHEPREFIX=/tmp/scheduler-pycache` (inside `PrivateTmp`, emptied when the service stops); `RUFF_CACHE_DIR` and `XDG_CACHE_HOME` in the data folder.
- `install.sh`, `update.sh`, `apply_patch.sh` seal after putting code in place (and fail, putting the old version back, if sealing does not take effect);
  `update.sh` checks `systemctl show ... ReadWritePaths`; the gate the scripts run as the account uses the same cache variables.
- `deploy/rollback.sh`: puts back `package.previous` and its own service file; keeps the version rolled back from.
- Delivery: ship it in the normal update (`update.sh` re-renders the service file from the new package). No separate installer exists or is needed.

**The reported fault reproduced.** As an unprivileged account on a root-owned copy, `py_compile` of the engine file fails without a cache prefix and works with
`PYTHONPYCACHEPREFIX`, writing nothing into the code folder (`webapp/tests/test_sec_containment.py`, `tools/readonly_check.py`). So the engine's own
self-check compiles explicitly and needs the prefix; **no engine file was changed** and no engine identity moved.

**Threat model.** What this stops: the website's account rewriting or adding code, and leaving compiled copies (none are loaded from the code folder; the
private temp cache disappears at stop). What it does not: a compromise of the service account still reads everything it is allowed to read and writes the data
folder (schedules, database, signing key); a process that gains root is outside it; the `venv` is checked only by being root-owned and read-only (the update
installs packages as root); Python itself and the operating system are patched separately. The seal does not make the data folder tamper-proof.

**Run on a root-owned copy as an unprivileged account (local, 2026-11-11, `evidence/phase_sec/`).** The website's own tests that sign in and read pages, the
engine's selfcheck and the whole release gate (83 suites, 1621 tests, 2 skipped) all passed with the code folder read-only and the cache variables the service
sets; no file in the code folder was created or changed. The first run found one real defect, a fixed output name in `/tmp` (`/tmp/xmod.out`) in `run_tests.sh`
that an account other than the file's creator could not use (and a symlink trap on a shared `/tmp`); it is fixed (a private temporary file) and the second run
passed. A second finding of the same kind: development scripts under `tools/` (not used by the website or the installer) also write fixed names in `/tmp`.

**Still unproven (needs the server):** the exact systemd mount namespace (`ProtectSystem=strict` with `ReadOnlyPaths`) as systemd applies it, and the first
real run after an update with the sealed code. Evidence needed: `systemctl show scheduler-web --property=ReadWritePaths --property=ReadOnlyPaths`,
`seal_package.sh --check`, and one real run finishing.

**First update needs one extra step.** The first update runs the `update.sh` already installed, which is the old one and still gives the package to the
website's account. The new package installs and its service file makes the code read-only to the service anyway; run `seal_package.sh` once to make root the
owner. Later updates do it themselves.

## Independent challenge of the strengthened tests
Each of the new regression tests was run against the original file for the change it covers and fails there; the sweeps now fail on any 500. The password test
covers padding with six invisible characters, the real-password-with-padding case, the add-account path, the bulk-sheet path and the store. What the tests
cannot show: that an unknown caller of `set_password` passes a short password through a new code path (now refused in the store), or live behaviour.

## Source-audit leads fixed (owner, 2026-11-11: "Fix all")
A source-only audit of `webapp/` and `deploy/` (`evidence/phase_sec_audit/`, 45 agents, four hunting waves, nothing executed) left 12 leads that needed a
test, plus one defect against the rule that notification secrets never go in logs. Each is now reproduced by a failing test first and fixed; the tests are
`webapp/tests/test_sec_audit_fixes.py`. Where a lead was a policy question the owner's "Fix all" settled it as a defect. The audit's own wording was checked
while fixing: two leads were weaker than written and one was stronger (see `evidence/phase_sec_audit/FIXES.md`).

| Lead | Fix |
|---|---|
| Day-page POSTs checked one program and acted on another | The program wall checks every program the request names (query and form) |
| Replan, Rescue and Bulk skipped the role back-limit | The back-limit checks the date of every move and the earliest day a window reaches |
| A removed uploader kept control of a run and the live schedule | A run of a program needs that program, also for its uploader; a run with no program stays with its uploader |
| A supervisor could take over a person who also holds other programs | A manager acts only on people whose programs are all the manager's own |
| Lockout counter lost updates; padded passwords revealed usernames by time | One atomic update, a lock re-check for a right password, two hashes for every answer |
| A swap could be answered by a namesake of another program | The answer needs the account the offer resolved |
| Cancelling a coaching request named another program | A request of a program the person cannot open answers like a missing number |
| Sheet readers padded every row to 16,384 cells and read every row | Rows cut at 64 cells and refused beyond a row limit while reading |
| A schedule upload could open to 250 MB in the web process | A schedule upload has its own limit (25 MB a member, 40 MB in all) |
| The staffing search recomputed its sums at every step | Same answers (checked against the old search), linear cost; an interval beyond 50,000 Erlangs is refused in words |
| Typed names and reasons became formulas in three downloads | Those cells are plain text |
| A group link with a space was accepted and its path logged | Refused when saved; a transport error never escapes or is logged |

Not done, and why: a `MemoryMax=` (and `TasksMax=`) in the service unit. The engine's peak memory for a full schedule run is not measured, and a cap set without
it could kill legitimate runs, which the project rules forbid as an unmeasured change. Next step for the owner or a later phase: measure the peak resident memory
of a full run on the 24 GB host, then set a cap above it. Also not done, left as hardening notes in the audit report: about a hundred smaller items.

## Open items, owners and the smallest next step
| Item | Owner | Next step |
|---|---|---|
| Install this release live | Owner | `update.sh` with the new package; then `seal_package.sh --check` and `systemctl show`; keep `rollback.sh` ready |
| Weak passwords already stored | Owner and InfoSec | Every password now changes within 30 days of the update, which replaces them in time; to replace them sooner, reset the accounts concerned |
| Absolute session cap | Owner | Not added: idle one hour only, as chosen |
| Egress restriction | Owner and cloud admin | Apply per `EGRESS_DESIGN.md` host rule first, with the 10-minute revert |
| SSH source range, root login, patches and reboot | Cloud admin | Read the effective sshd config; restrict ingress to an approved address; patch in a window |
| MFA/SSO, backups and a restore test, alerting | Owner and InfoSec | Evidence, not code |
| Webhook destinations and what posts may carry | Owner and the group owners | Approve the list; webhook links are secrets in the database |
| Independent vulnerability assessment | InfoSec | Scope in the bundle's `INDEPENDENT_ASSESSOR_SCOPE.txt` |
| Memory cap for the service | Owner | Measure the peak memory of a full schedule run, then set `MemoryMax=` above it (not guessed here) |
| Confirm the audit leads on a running copy | Owner | The audit read source only; the new tests reproduce each lead locally, but a staging check of the same cases is still the proof for the live site |

## InfoSec-facing statement
The website has been reviewed in source and exercised locally, three defects were corrected and deployed, further gaps found in that review are corrected in
this release, and the code is moved to a root-owned, read-only footing in this release (not yet live). The compromise boundary of the website's account
remains its data folder and, until egress is restricted, the Internet; the system holds schedules, attendance and leave data and local password hashes, and
a compromise of the service account can read and alter them. No claim is made of "no SGS data" or "no SGS impact". No independent penetration test has been done.
