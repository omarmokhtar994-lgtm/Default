# RC9.2.2 RC4 — Final Post-Fix End-to-End Audit

Audit date: 2026-09-10  
Target: `RC9_2_2_FIX_VALIDATION_RC4` / `RC9_2_2_PRODUCTION_HARDENED_RC4_RELEASE_CANDIDATE`  
Engine: `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2`

## Scope and final status

This review covered the in-scope engine, parser, optimizer integration,
validator, output preparation, package builders, runners, Colab notebooks,
workbooks, formulas, validations, reports, tests, and release metadata.
Approved deferred modules were excluded from discovery, modification, testing,
scoring, and certification. They are recorded only in the deferred section.

Final status: **NO-GO for unattended live production until the exact RC4
CP-SAT matrix completes in Colab.** The offline and workbook gates are clean;
the remaining blocker is runtime evidence, not an observed failing test.

## A. Issues found

| ID | Category | Severity | Root cause | Status |
|---|---|---:|---|---|
| I-01 | Workbook / data integrity | Critical | Existing Excel validation rules displayed dropdowns but did not reject typed values outside the allowed list/range. | Fixed |
| I-02 | Packaging | High | A legacy Phase-A packager could still create a weaker delivery without exact-output validation and sealing. | Fixed: now a fail-closed compatibility stub |
| I-03 | Operations / Colab | High | Concurrent or abandoned case directories had no ownership lock or heartbeat. | Fixed: atomic lock, heartbeat, stale-lock recovery |
| I-04 | Packaging reliability | High | Split ZIPs were published directly to final names during construction. | Fixed: private staging directory, verified ZIPs, manifest installed last |
| I-05 | Evidence handoff | Medium | Individual split ZIPs were not self-describing. | Fixed: component manifest added inside every ZIP |
| I-06 | Reporting / UX | High | The tested output dashboard/presentation layer existed outside the active RC4 polisher. | Fixed: integrated `Read Me First` / Schedule Control Center |
| I-07 | Release identity | High | Workbook byte changes left scenario and priority-input hashes stale. | Fixed: regenerated hashes and verified every manifest row |
| I-08 | QA coverage | Medium | Shipped-workbook validation-alert and manifest-hash checks were not runtime regression tests. | Fixed: added automated guards |
| I-09 | Operations / Colab | High | The no-Drive notebook handled interruption but did not expose the runner's exact resume control. | Fixed: added `RESUME=True` and forwards `--resume` |
| I-10 | Operations / observability | Medium | A newly acquired case had no heartbeat artifact until the first 30-second tick. | Fixed: heartbeat is written at lock acquisition |

## B. Fixes applied

- Rebuilt all 8 shipped input workbooks through the public spreadsheet
  authoring path. Every existing validation range now has an explicit error
  alert, while values, formulas, sheets, and parsed scheduling contracts are
  preserved.
- Added `tools/harden_input_validations.mjs` so the workbook repair is
  reproducible rather than a one-off edit.
- Disabled the legacy Phase-A packaging implementation so old automation
  receives a nonzero, actionable error and cannot create an unsafe delivery.
- Added `RUN_LOCK.json` ownership control and `RUN_HEARTBEAT.json` liveness
  evidence to the production wrapper. The first heartbeat is written at lock
  acquisition, live owners block concurrent writes, and dead/partial locks are
  safely reclaimable for resume.
- Changed Phase-C split packaging to stage the complete package set privately,
  verify each archive, include `COMPONENT_MANIFEST.json` in each component, and
  publish the aggregate `PACKAGE_SPLIT_MANIFEST.json` last.
- Integrated the RC9.2.2 output UX layer: active `Read Me First` dashboard,
  status cards, before/after coverage chart, risk snapshot, configuration
  summary, status coloring, freezes, filters, widths, and tab ordering. This
  is presentation-only and does not change solver decisions or metrics.
- Added live RC4 preflight/runtime evidence to the package builder and removed
  obsolete RC921 Colab notebooks from delivered RC4 ZIPs.
- Corrected the 8 workbook SHA-256 entries in `SCENARIOS.json` and the priority
  workbook hash in `MANIFEST.json`.
- Added tests for validation enforcement, all-workbook hash identity, current
  dashboard integration, lock ownership/recovery, component manifests, and
  disabled legacy packaging.
- Added an explicit `RESUME` control to the no-Drive Colab notebook so a
  controlled interruption can continue the same staged case instead of
  restarting from scratch.

## C. Validation results

| Check | Result |
|---|---|
| Full offline release gate | PASS |
| Test suites | 10 suites, 429 tests passed |
| Engine self-check | PASS |
| Wrapper self-check | PASS |
| Python compilation | PASS |
| Input preflight | 8/8 manifest hashes match; 7 PASS, AE_AR_B2B WARN only for supplied unknown prior-Saturday names |
| Workbook contract preservation | 8/8 exact canonical parsed contracts unchanged after workbook repair |
| Workbook validation controls | 8/8 workbooks; every serialized validation has `showErrorMessage=1` |
| Formula token scan | No `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, or `#N/A` formula tokens |
| NMG workbook visual/structure check | PASS; 30/60-minute control path visible, 60-minute default preserved |
| Package ZIP integrity | PASS for both RC4 package types |
| Internal package manifests | PASS; member hashes verified |
| Phase-C split packaging tests | PASS; component manifests and completion marker verified |
| Runner lock tests | PASS; live-owner block and dead-owner recovery verified |
| Static lint | Not available in this runtime; compile and in-process name checks passed |
| Exact CP-SAT smoke | BLOCKED locally because `ortools==9.15.6755` is unavailable; runner fails closed before solver time |

## D. Regression testing

Previously working behavior checked after the final changes:

- Strict malformed-time, malformed-number, invalid-enum, duplicate-identity,
  fixed-OFF/Leave, nesting, language-window, Sunday-boundary, and selector
  guards: PASS.
- 15-, 30-, and 60-minute contract support remains represented by the same
  parser/model path; shipped workbook contracts are unchanged.
- 9H/2OFF and 11H/3OFF contract parsing, including the negative disabled case:
  PASS.
- Exact-output validation ordering, failed-validator classification, return
  codes, atomic ZIP publication, and stale-result protections: PASS.
- Output UX integration is presentation-only; its self-check passes and all
  release tests continue to pass.

## E. Remaining risks and limitations

1. A compatible Colab runtime must run the exact RC4 engine hash through the
   current-build CP-SAT matrix. Static tests cannot prove schedule quality,
   runtime, break placement, fairness, or final workbook publication.
2. A genuine 11H/3OFF end-to-end fixture is still required; a mislabeled
   9H-only asset cannot close that gate.
3. Multi-worker CP-SAT results are not guaranteed bit-for-bit repeatable under
   a wall-clock deadline. Use one worker for formal comparisons and record
   worker count, bounds, seed, budget, and elapsed time.
4. Large-HC, dense 30-minute, and many-language benchmark evidence is not
   available yet. The package has time budgets but no measured memory/scale
   envelope.
5. The workbooks are contract-compatible but not all have identical legacy
   sheet layouts. A single migrated template remains the cleaner long-term
   operating model.
6. Native Excel/Google Sheets recalculation after a user edits formulas was
   not available in this runtime. The engine remains authoritative for release
   checks; displayed workbook formula caches should be recalculated by Excel or
   Sheets before human review.
7. AE_AR_B2B retains a disclosed unknown prior-Saturday-name warning. It is an
   input-history quality issue, not a parser crash, and should be resolved by
   the WFM owner before a cyclic schedule is approved.

## Deferred Items (Out of Scope)

The two approved deferred modules were intentionally frozen. No issue
discovery, fix, refactor, optimization, enhancement, coverage validation,
performance test, regression detail, health-score adjustment, or certification
decision was performed against them:

- **F1:** target-first fallback behavior when the risk-eligible candidate pool
  is empty.
- **F2:** whole-shift language-window containment semantics.

## F. Improvement opportunities implemented

- Safer Excel data entry through enforced validation alerts.
- Safer operations through lock/heartbeat/recovery controls.
- Safer evidence delivery through staged publication and self-describing ZIPs.
- Better management usability through the integrated output Control Center.
- Better reproducibility through current workbook hashes, tests, and package
  evidence.
- Better QA through direct workbook XML checks and contract-equivalence tests.

## G. Scope-controlled health score

These scores exclude the deferred modules and are provisional until the exact
Colab solver matrix completes:

| Measure | Score |
|---|---:|
| Accuracy | 92/100 |
| Stability | 90/100 |
| Performance | 72/100 |
| Coverage management | 88/100 |
| Maintainability | 74/100 |
| Overall in-scope readiness | 84/100 |

The package is a strong corrected RC4 candidate, but it is not certified for
live replacement until the runtime-dependent gates above pass.
