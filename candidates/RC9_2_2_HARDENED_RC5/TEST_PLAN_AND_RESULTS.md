# Impact-based test plan and results

## PASSED — no retest required

No solver result was treated as an exact-build pass for this release because the engine SHA changed. Historical passes were retained as comparison evidence and were not rerun as multi-hour DEEP jobs.

## FIX VALIDATION — completed

| Check | Result |
|---|---|
| Offline unit/integration guards | PASS — 453 current tests, 11 suites, 5 skipped |
| Python compilation | PASS — engine, runners, tools, tests |
| Runner help/argument paths | PASS |
| Manifest input hash verification | PASS — 8/8 |
| Workbook parser/preflight | PASS/WARN — 7 PASS, AE_AR_B2B WARN only |
| NMG production workbook | PASS — parser, validation formulas, dropdown/config review, 21-sheet visual review |
| Missing dependency behavior | PASS — failed closed, return code 3, no schedule or production ZIP |
| Independent-validator crash behavior | PASS — JSON/CSV evidence, return code 3 |
| Historical artifact revalidation | Completed for Chat, NMG EN+SP, GDI 24/7, and SAKS |
| Latest Cricut Voice Colab artifact | Engine hard-valid; exact polished workbook independently validated PASS with 0 hard failures |
| Release-chain regression | PASS — contract WARN no longer suppresses polishing/validation; final quality report uses independent evidence |
| Supplied RC5_RUN_900 artifact recheck | PASS — seven generated workbooks independently revalidated with 0 hard failures; NMG_EN correctly remains an input/resource contract failure |
| Stage-2 budget partition guard | PASS — recovery cannot consume the protected anchor and first meaningful adaptive slice |

The five skipped offline tests were one optional ruff check because ruff is not installed and four legacy-package-fixture checks whose expected `packages/rc9_2_2_production/inputs` tree is absent from this standalone package. They are not solver-rule passes.

## TARGETED REGRESSION — required on a compatible solver runtime

Run in this order; stop and fix immediately on a blocking regression:

1. `NMG_EN_PRODUCTION` — QUICK/FULL, exact updated workbook.
2. Genuine 11H/3OFF positive fixture and an 11H-prohibited negative fixture.
3. `NMG_EN_SP` — bilingual/language, breaks, next-Sunday, after80/floor.
4. `NMG_EN` — fixed/nesting/OFF/rest and selector protection.
5. `GDI_REAL28` — 24/7, midnight, zero-active, Sunday rollover, overage distribution.
6. `CRICUT_CHAT` — next-Sunday floor and break concurrency.
7. Remaining manifest scenarios only after affected gates pass.

Use `runners/run_targeted_regression.py`; do not start DEEP unless a reproducible QUICK result proves that search depth is the unresolved variable.

## FAILED / WARN evidence still requiring attention

| Evidence | Status | Main finding |
|---|---|---|
| Current-build NMG smoke | BLOCKED in offline environment | OR-Tools 9.15.6755 absent locally; Colab remains the solver runtime |
| Latest Cricut Voice day-specific run | PASS with WARN | 0 hard language gaps and 0 validator hard failures; quality warnings remain disclosed |
| Older Cricut Chat schedule | FAIL | 9 next-Sunday floor gaps; break concurrency and overage-distribution warnings |
| Older NMG EN+SP schedule | FAIL | 2 next-Sunday floor gaps; 47 current-week floor gaps; quality-gate issues |
| Older GDI 24/7 schedule | PASS with WARN | Floor intact, but 29 break-concurrency and 41 overage-cap warnings |
| Older SAKS schedule | PASS with WARN | Not a real 11H case; very high avoidable overage and break concurrency |
| AE_AR_B2B input | WARN | Five obsolete names in previous-Saturday history are ignored and disclosed |

Older outputs were validated against the contracts embedded in those output workbooks because their original input snapshots were absent. They are diagnostics, not exact-input release proof.

## DEEP runs intentionally skipped

All multi-hour DEEP runs were skipped. There is no evidence that more search time would resolve the missing runtime, mislabeled 11H fixture, or publication-integrity defects. After QUICK validation, use `run_deep.py --reason ...` only for a named reproducible optimization defect.

## Acceptance criteria

- Runtime check PASS, including CP-SAT smoke.
- Runner return code zero.
- Engine and independent validator both report no hard failure.
- Exact final workbook hash matches the sealed manifest.
- No material regression in after80/floor, after90/target, language, breaks, fixed/nesting/OFF/rest, 24/7, or Sunday rollover.
- Overage distribution improves only within protected coverage locks.
- Release-gate CSV contains no blocking FAIL/NO_EVIDENCE.
