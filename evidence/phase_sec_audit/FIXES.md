# Fixes for the audit leads (2026-11-11)

Owner: "Fix all". Each fix was written test first (`webapp/tests/test_sec_audit_fixes.py`), watched failing for the stated reason, then made to pass, then run with
the related suites. One existing test was re-pinned with its reason in the test (`test_av_security`: every sign-in answer now costs two hashes, was one; the
equality it guards is unchanged).

| # | Lead (fingerprint) | Files changed | Red first? |
|---|---|---|---|
| 1 | `day.post.program.gate-source-mismatch` | `webapp/app.py` | 21 of 28 mixed query-plus-form cases failed before |
| 2 | `day.replan-rescue.dated-move-bypasses-back-limit` | `webapp/app.py` | move dates, window start, supervisor limit all failed before |
| 3 | `runs.uploader-access-outlives-program-removal` | `webapp/app.py`, `webapp/routes/schedule_versions.py` | 10 failures; the week change really landed |
| 4 | `people.can_manage.partial-overlap-takeover` | `webapp/access.py` | failed before |
| 5 | `h1-lockout-counter-lost-update`, `h1-login-timing-padded-password-enumeration` | `webapp/store.py` | 3 of 5 failed before (barrier inside the hash, so the overlap is certain) |
| 6 | `swaps.answer.roster-name-without-program` | `webapp/swaps.py` | failed before |
| 7 | `coaching.cancel.redirect-program-name-leak` | `webapp/routes/break_changes.py` | failed before |
| 8 | `upload.read-only-iter-rows-unbounded-in-volumes-and-people-reader` | `webapp/bulk_users.py`, `webapp/volumes_io.py` | widths of 16,384 before |
| 9 | `upload.zipcheck-limits-too-loose-for-full-load-workbook-memory` | `webapp/zipcheck.py`, `webapp/routes/runs.py`, `webapp/routes/channel_needs.py` | failed before |
| 10 | `volumes.erlang-agents-needed.quadratic-cpu-with-large-typed-total` | `webapp/erlang.py` | 1.56 s against a 1 s bound; equality with the old search over 1,000+ cases |
| 11 | `versions.with-notes.reason-formula-injection` (and the channel plan and template notes) | `webapp/cellsafe.py`, `webapp/versions.py`, `webapp/channel_export.py`, `webapp/channel_template.py` | formula cells before |
| 12 | `notify.send-invalid-url-logs-webhook-link` | `webapp/notify.py` | InvalidURL escaped before |

## Where the audit's wording was off (found while fixing)
- **Erlang cost:** the audit called it quadratic. Measured: with an occupancy cap the old search stopped on occupancy before it summed the Erlang terms (cheap);
  only a strict answer time with no cap was slow, about T to the 1.5 power (0.9 s for one interval of 40,000 Erlangs). The fix is still right (linear, same
  answers), but the risk was smaller than "minutes".
- **Row reader:** the audit said a forged size tag pads empty rows. Measured: it does not add rows; it pads every real row to 16,384 cells, which is worse for a
  long file (100,000 rows would be about 13 GB). The fix cuts rows at 64 cells.
- **Back-limit:** the audit's `start` variant was real but secondary; both are checked now.

## Not done
- `MemoryMax=` / `TasksMax=` for the service: not measured, so not guessed (project rule on unmeasured changes). Next step is in `docs/security/SECURITY_STATUS_2026-11-11.md`.
- The hardening notes in `REPORT.md` section 6 (about a hundred small items) are left as notes, except the three that were part of leads above.

## Checks and package (2026-11-12, Egypt time)
- Whole chain on the fix commits: 291 units passed (website suites one module each, channel-solver modules alone, browser classes), none failed.
- Package `dist/RC9_2_2_PRODUCTION_PACKAGE.zip`, 18.37 MB, 2,704 files, sha256 `4c7a7d8f9c2018a93674c80e69d22c0772122a06ce4c5dd863def92a3a6f74f4`, built from commit
  `f9b31c0`. Its own release gate: `GATE PASS: 83 suites, 1621 tests (2 skipped) + 2 selfchecks + cross-module call signatures + undefined-name sweep`.
- Sealed and run as an unprivileged account on that exact zip (`readonly_fixes_package_gate.txt`): sealed, sign-in tests pass, both compile checks pass, release gate passes,
  nothing tried to write the code folder.
- Engine, tests, tools and deploy are unchanged from the audited commit (`git diff 8fec106..HEAD -- engine tests tests_staged tools deploy` is empty); the RC9.1 baseline
  workbooks and `engine/regression_assets` keep their bytes.
- Not checked: the new rules on the live server (this was local). The owner installs the package; the first update runs the old installed `update.sh`, so run `seal_package.sh`
  once afterwards, as before.
