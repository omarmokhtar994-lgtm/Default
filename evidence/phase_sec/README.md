# Evidence: the final package run as the server will run it, sealed (2026-11-11)

Package `RC9_2_2_PRODUCTION_PACKAGE.zip`, sha256 `d5e2a39dc911d38cbc837289212cb3a654c9ece42244658491026eba193e36ef`, built from commit `6b61c7f`.
Method: `tools/readonly_check.py --package ZIP`: the package is unpacked, made root-owned and unwritable (`deploy/seal_package.sh`), and everything below runs
as the unprivileged account `nobody` with the service's cache settings. A file created or changed in the code folder fails the step. This is Unix permissions
on a copy, not the server's systemd mount namespace.

| Step | Result | File |
|---|---|---|
| Seal, then check | SEALED | `readonly_package_run.txt` |
| Website tests that sign in and read pages | PASS | same |
| Explicit compile without a cache prefix | refused, as the earlier server run found | same |
| Explicit compile of the engine file with the cache prefix | PASS, nothing written into the code | same |
| The release gate (run on the previous build of the package, same code) | PASS: 1621 tests | `readonly_check_after_fix.txt` |
| Every non-browser website test module (233) | 231 passed, 0 wrote into the code; 2 are development screenshot writers (`test_ax_downloads`, `test_ax_merge_pick`: they save pictures under `evidence/`, which a package does not have) | `readonly_package_run_web.txt` |
| One real engine run, full schedule, 2 minutes of solving, smallest example workbook | PASS: RELEASABLE, 9 workbooks and 44 files written to the results folder, nothing into the code | `readonly_package_run.txt` |
| The same engine run left to its full hour (earlier attempt) | ran the whole hour on sealed code with no write error (the check's own wait ended first) | not kept |

Findings from these runs, all fixed: `run_tests.sh` wrote a fixed `/tmp/xmod.out` (failed for another account, and a symlink trap); a test of mine could not find its files in the package layout; the check itself needed the service's `PYTHON` and a writable home for LibreOffice.
Not shown by these runs: the systemd namespace itself (`systemctl show scheduler-web --property=ReadWritePaths --property=ReadOnlyPaths` on the server) and the first real run after an update there.
