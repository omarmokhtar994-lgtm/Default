# G1: production package rebuilt with its own gate result (2026-10-07 15:33 Egypt)

`python3 tools/build_production_package.py` (commit bf1513f):

| item | value |
|---|---|
| zip | `dist/RC9_2_2_PRODUCTION_PACKAGE.zip` (not committed; `dist/` is git-ignored) |
| sha256 | `0470a219d1acedb12e068534a0e4ae9f68ab68af766a970e080924331c9fd424` |
| files / size | 1,962 / 16.40 MB |
| engine sha256 | `dd4ee4e95a9fac927b825f5b00dacd1658bf79ee2d7d68d4d0552a64fbc44a52` |
| gate inside the staged package | PASS, 72 suites, 1,497 tests (2 skipped), minimum 1,497 |
| shipped gate record | `PACKAGE_GATE_RESULT.txt` (full output) + `MANIFEST.json` "gate" / "built_utc" |
| SCENARIOS.json | describes the packaged engine and all 7 workbooks |

Clean-extract equivalence: every one of the 1,962 files in the zip is
byte-identical to the staged tree the gate ran on (0 mismatches, 0 files only
on one side, no caches or `.pyc`).

The package's gate refused to ship twice before this build, and both were
real defects, fixed and recorded in the Phase G ledger:
1. two Phase E suites read the repo path to the ready-to-edit inputs; inside
   the package one could not import (2 tests missing, 1,495 < 1,497) and the
   other checked zero workbooks (vacuous pass) - fixed in a3b48e5;
2. the new builder test built from the real repo root, absent in the
   package - made hermetic in bf1513f.

The previous bundled record
(`evidence/production_readiness_audit/phase_c/CLEAN_EXTRACT_GATE_PILOT.txt`,
1,432 tests) stays as history; the package now carries its own current gate.
