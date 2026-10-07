# Phase I: team scheduler website Implementation Plan

> **For agentic workers:** Execution method fixed by `CLAUDE.md`: executing-plans, inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A private website on the owner's Oracle Always Free server where each team member logs in, uploads a weekly workbook, runs the scheduler and downloads the results; the code never leaves the server.

**Architecture:** A Flask app (`webapp/`) served by Waitress behind Caddy (automatic HTTPS on `<ip>.sslip.io`). SQLite holds users and runs. One background worker thread runs queued jobs by calling the existing production runner (`runners/rc922_runner.py`) as a subprocess in its own process group. The package's offline gate runs once per installed package version; runs then pass `--skip-guards` (engine fingerprint and runtime checks still run every time). A one-command installer (`deploy/install.sh`) sets up Ubuntu ARM.

**Tech Stack:** Python 3.10+, Flask 3.1, Waitress 3.0, SQLite (stdlib), Jinja2, Caddy 2, systemd; tests: unittest + Flask test client, Playwright (Chromium) for UI.

**Spec:** Owner, 2026-10-07 chat: "Login per person, keep results 30 days, start building make it fancy use skills and download any needed skills add copy rights by my name as well"; earlier: website on Oracle (private, link + password), upload -> run -> download; code must not leave the server ("someone might steal it").

## Global Constraints

- Engine, validator, runner and package untouched in behaviour; the website only calls the runner.
- Every published schedule is still independently validated by the runner (exit 0 = approved). The website shows the runner's exit code and the release verdict, never its own judgement.
- Copyright: "© 2026 Omar Mokhtar. All rights reserved." on every page footer, in `webapp/NOTICE`, and as a header line in every new source file.
- Results kept 30 days, then files deleted (run row kept as "Expired").
- Per-person logins; passwords stored as salted hashes (Werkzeug scrypt); first login forces a password change; admin adds/disables users and resets passwords.
- Uploads: `.xlsx` only, max 25 MB; filenames sanitised.
- Website tests live in `webapp/tests/` and run in the web venv (`python -m unittest discover webapp/tests`); they are not part of `run_tests.sh` (its Python has no Flask; Colab/package gate unchanged).
- Design follows the `frontend-design` skill; UI checked with Playwright screenshots (`webapp-testing` skill).

## Review Focus

- Two people press Run at once: both runs queue; one runs at a time by default; neither is lost (`test_two_runs_queue_and_both_finish`).
- The server restarts mid-run: the run shows "Interrupted" with a Resume button that continues from checkpoints (`test_restart_marks_running_as_interrupted`).
- A non-admin opens an admin URL or another user's download link: admin pages refuse (403); downloads are for any logged-in team member, never anonymous (`test_admin_pages_refuse_members`, `test_downloads_need_login`).
- A form posted without its CSRF token (cross-site request): refused (`test_post_without_csrf_is_refused`).
- Repeated wrong passwords: locked for 15 minutes after 5 failures per user (`test_login_lockout`).

---

### Task 1: users, login and security

**Files:** Create `webapp/__init__.py`, `webapp/app.py` (`create_app(config: dict) -> Flask`), `webapp/store.py`, `webapp/auth.py`, `webapp/manage.py` (CLI: `create-admin`, `add-user`, `reset-password`, `disable-user`), `webapp/NOTICE`; Test `webapp/tests/test_auth.py`.

**Interfaces (produced):** `Store(path: Path)` with `add_user(username, display_name, password, is_admin=False) -> int`, `check_password(username, password) -> Optional[dict]`, `set_password(user_id, password, must_change=False)`, `set_active(user_id, active)`, `list_users() -> list[dict]`; decorators `login_required`, `admin_required`; `csrf_token()` in templates, checked on every POST.

- [ ] Failing tests: `test_login_and_logout`, `test_first_login_forces_password_change`, `test_wrong_password_refused`, `test_login_lockout` (5 failures -> locked 15 min), `test_disabled_user_cannot_log_in`, `test_admin_pages_refuse_members` (403), `test_admin_adds_and_disables_a_user`, `test_post_without_csrf_is_refused` (400), `test_passwords_are_hashed` (no plaintext in DB), `test_session_cookie_flags` (HttpOnly, SameSite=Lax; Secure when `HTTPS=True`), `test_copyright_on_login_page`.
- [ ] Run; save `evidence/phase_i/I1_TESTS_BEFORE.txt`. Implement. Pass. Commit.

### Task 2: runs, queue and retention

**Files:** Create `webapp/runs.py`, `webapp/gate.py`; extend `webapp/app.py` routes; Test `webapp/tests/test_runs.py`.

**Interfaces:** `RunQueue(store, package_root, runs_root, runner_cmd=None, parallel=1)`; `submit(user_id, upload_path, mode) -> run_id` (random 12-char id); statuses `CHECKING -> REJECTED | QUEUED -> GATE -> RUNNING -> SCORING -> DONE | FAILED | INTERRUPTED | EXPIRED`; per run: `exit_code`, `verdict` (line from `release_gate_report.py`), `log_tail`, `results.zip`. `gate.ensure(package_root) -> GateStamp` runs `run_tests.sh` once per package MANIFEST sha256 and caches PASS in `runs_root/_gate/<sha>.json`; runs pass `--skip-guards` only with a PASS stamp for the installed package. `cleanup(now) -> int` expires runs older than 30 days. `runner_cmd` is injectable so tests use a fake runner script.
- [ ] Failing tests (fake runner): `test_upload_rejects_non_xlsx_and_oversize`, `test_check_rejection_is_shown_with_its_message`, `test_accepted_run_goes_through_to_done_with_zip_and_verdict`, `test_failed_runner_exit_code_is_shown`, `test_two_runs_queue_and_both_finish`, `test_restart_marks_running_as_interrupted`, `test_resume_passes_resume_flag`, `test_gate_runs_once_per_package_and_failure_blocks_runs`, `test_skip_guards_only_with_pass_stamp`, `test_runs_older_than_30_days_expire`, `test_downloads_need_login`, `test_runner_command_matches_production_flags` (mode, seeds auto, `--input`, `--results-root`, `--num-workers`, `--resume`).
- [ ] Run; save `I2_TESTS_BEFORE.txt`. Implement. Pass. One real end-to-end run (QUICK, short time limit) through the website in this container. Commit.

### Task 3: the look (frontend-design) and UI tests (webapp-testing)

**Files:** `webapp/templates/*.html`, `webapp/static/app.css`, `webapp/static/app.js` (status polling only); Test `webapp/tests/test_ui_playwright.py` (skips with a clear message if Playwright/Chromium missing).
- [ ] Design plan first (frontend-design: palette, type, layout, one signature element), reviewed against the skill's list of generic defaults; recorded in `webapp/DESIGN.md`.
- [ ] Failing UI tests: `test_login_page_renders_with_copyright`, `test_dashboard_upload_run_flow` (fake runner: upload -> status moves to Done -> Download button), `test_mobile_width_has_no_horizontal_scroll` (390 px), `test_keyboard_focus_visible`, screenshots to `evidence/phase_i/screens/`.
- [ ] Implement; pass; review screenshots; commit.

### Task 4: installer and Oracle guide

**Files:** `deploy/install.sh`, `deploy/update.sh`, `deploy/scheduler-web.service`, `deploy/Caddyfile.template`, `deploy/ORACLE_SETUP_GUIDE.md`; Test `webapp/tests/test_deploy.py`.
- [ ] Failing tests: `test_install_script_is_valid_bash` (`bash -n`), `test_install_pins_the_solver` (`ortools==9.15.6755`), `test_service_runs_waitress_on_localhost_only`, `test_caddy_uses_sslip_domain_and_only_proxies_to_localhost`, `test_firewall_opens_80_and_443_only`, `test_install_creates_admin_interactively_never_with_a_default_password`.
- [ ] Implement; dry-run `install.sh` steps that can run in a container (venv, pip, admin creation, service file render) with `DRY_RUN=1`; pass; commit.

### Finish

- [ ] Package builder ships `webapp/` and `deploy/`; full engine gate; package rebuild; push; send the owner screenshots, the guide and the package.
