# RC9.2.2 evidence, fixes, and readiness report

## Final decision

**NO-GO for unattended live production at this moment.** The package is the corrected **RC9.2.2** build `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2`. The exact RC5 solver matrix is not runnable in this environment because OR-Tools is missing; historical workbooks remain diagnostics, and the full priority-scenario release review is not closed.

RC9.1 remains the live fallback until the closing checks below pass.

## 1. Evidence collected

Source evidence: the latest Colab results ZIP supplied for the Cricut Voice day-specific workbook.

| Evidence | Result |
|---|---|
| Engine release | `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2` |
| Current RC5 engine SHA-256 | `0e6f643552c5e59f284fefbabc74803c3450b2a1cd2de47fad44781f6408cc5c` |
| Historical reference run | QUICK / FULL_SCHEDULE; completed in about 58 minutes |
| Historical engine schedule | PASS_WITH_QUALITY_WARNINGS; hard-valid artifact present |
| Historical language hard gaps | 0 |
| Historical next-Sunday language gaps | 0 |
| Historical exact polished workbook validation | PASS; 0 hard failures |
| Historical exact polished workbook SHA-256 | `885d1b1b16a61ad9797c46bcd98cea5d907f4b3510ab20ba285b942d9584e8b1` |
| Current RC5 offline gate | 453 tests, 11 suites, 2 self-checks: PASS |

The original Colab run reported `FAIL_OUTPUT_NOT_FOUND` because the release wrapper stopped before invoking the independent validator. The existing final schedule was therefore re-polished and checked locally with the corrected release tools; no new solver run was claimed for that revalidation.

## 2. Issues found and corrections applied

| ID | Root cause | Correction | Verification |
|---|---|---|---|
| R01 | A contract `WARN` was treated as a blocking error even when failure count was zero. | Only contract failures/unknown states block; disclosed warnings remain visible. | Phase-C tests and Cricut evidence: PASS |
| R02 | The wrapper required strict Phase-C success before polishing. This created a circular failure: the final workbook could not be independently validated because validation had not yet run. | Pre-validation `NOT_VALIDATED` may proceed to exact-output validation when the artifact and contract are otherwise sound. | Runner guard + exact-output test: PASS |
| R03 | Phase-C safety was based only on the engine audit and could hide the independent validator result. | Once present, `INDEPENDENT_VALIDATION.json` is authoritative; the final quality report is rerun after validation. | Validator override test + Cricut: PASS |
| R04 | Production sealing could occur without a final post-validation quality decision, while the wrapper's pending-approval manifest contradicted the packager. | Independent PASS now seals hard-gate evidence, records quality status and pending human approval, and packages only as an explicitly review-only delivery when quality is blocked. | Release-path regression suite: PASS |
| R05 | Day-specific language was not previously a complete contract. | Added `Coverage Days` parsing, day-aware windows, Sunday rollover handling, and day-specific validator parity. | Rule semantics suite: PASS; Cricut language gaps: 0 |
| R06 | International was required in intervals with no eligible associate when Friday/Saturday were intended as qualified staff OFF days. | The input now uses International `Sun–Thu`; no Friday/Saturday International requirement is present. | Parser/preflight and day-specific workbook checks: PASS |
| R07 | Candidate selection could sacrifice protected/floor coverage for target gains. | Protected tradeoff cap and complete hard-valid frontier retention reject the damaging exchange. | Selector/adversarial tests: PASS |
| R08 | Fixed OFF/Leave rows could become soft when preference hardness was disabled. | Fixed requests are independently hard in all scheduling models. | Fixed-request tests: PASS |
| R09 | The validator had gaps around duplicates, flexible nesting, language windows, rollover, breaks, and overage distribution. | Independent recomputation and machine-readable error handling were expanded. | Validator parity and hardening tests: PASS |
| R10 | Package identity and release text had stale RC9.1/old engine hashes. | Manifest, scenario identity, runner documentation, and release status now point to RC9.2.2 and the current engine SHA. | Hash/identity suite and package build: PASS |
| R11 | Quality-fail mode still injected quality-first hard locks/objective order into coverage search. | Target-first break/joint order is enforced; quality remains a post-run release decision. | Solver-free policy suite: PASS |
| R12 | Independent validation omitted cyclic next-Sunday break-concurrency observations. | The same concurrency rule now includes the cyclic boundary and is included in canonical parity. | Validator regression and historical Cricut recheck: PASS |
| R13 | Many audit paths removed every metric whose name ended in `gaps`, including scalar max-run/gap evidence. | All compact audit surfaces now exclude only list/dict detail collections. | Compact-surface regression: PASS |
| R14 | Stage-1 retention was capped at 16 and silently reduced to 10 after recovery. | Recovery retains the configured 16-skeleton cap and publishes both counts. | Retention regression: PASS |
| R15 | Finalizer could seal hard gates when the final Phase-C safety report was missing or unreadable. | Final safety evidence is mandatory and must be PASS before sealing. | Compile/gate regression: PASS |
| R16 | Independent validation classified release-quality failures as hard schedule failures. | Hard-rule failures, quality-gate findings, and suppressed findings now have separate fields/statuses. | Validator recheck: PASS |
| R17 | Avoidable-overage concentration used total target overage in the engine and avoidable overage in the validator. | Both now use avoidable overage. | Metric parity analysis: fixed; exact RC5 runtime rerun pending |
| R18 | The validator read only active break rows, so a documented no-break exception could become a false break-segment failure. | Explicit `No-Break Exceptions` rows are imported as evidence-bearing zero-break records and checked against the exception policy. | GDI supplied output recheck: 0 hard failures |
| R19 | Saturday carry-in was counted as current-week staffing in blank intervals. | Current-week assignments and historical carry-in are tracked separately; only current-week assignments can violate the blank-staffing rule. | NMG SP supplied output recheck: 0 hard failures |
| R20 | The actual `*.l6_3_2_3_solver_audit.json` filename did not match the wrapper's `*.solver_audit.json` glob, so pre-solver failures could be overwritten as generated-schedule failures. | Audit discovery now matches the shipped filename contract and preserves no-artifact/input-contract outcomes. | NMG EN supplied failure fixture: correct `INPUT_OR_RESOURCE_CONTRACT_GAP` |
| R21 | Breakability recovery consumed the time reserved for the protected Stage-2 anchor and adaptive exploration. | Break search is deterministically partitioned so recovery cannot starve the anchor or the first meaningful adaptive solve. | 47 production-hardening tests; current-build runtime confirmation pending |
| R22 | Stage-2 ranked proven-zero break diagnostics ahead of higher-coverage skeletons whose diagnostics were still unknown, so the strongest skeleton could receive no break search before the global deadline. | Unknown and proven-zero candidates now share the coverage-first tier; only proven-positive minima are deferred, and the protected anchor is capped at 240 seconds based on measured convergence. | 453 offline tests; targeted runtime confirmation pending |

## 3. Cricut Voice result interpretation

The run did **not** fail because of International coverage. With International configured for Sun–Thu only, the resulting schedule has zero hard language gaps and zero next-Sunday language gaps.

The schedule is hard-valid, but quality warnings remain:

- 6 break-concurrency violations after including the cyclic next-Sunday boundary; maximum simultaneous breaks observed: 5.
- 92 whole-week overage-cap observations and 23 adjacent-balance observations.
- 6 transferable-overstaffing-beside-undertarget observations.
- 27 isolated-offday observations.
- 5 late-shift and 5 overnight-fairness load deltas.
- 58 language reserve-shortfall/minimum-only quarters; hard language coverage itself remains zero-gap.

These are not hidden as PASS. They are quality debt requiring operational review or stricter workbook gates before live approval.

## 4. Internal tests completed

- 453 current offline tests passed.
- 11 test suites passed, including selector, language semantics, validator parity, packaging, release identity, and production hardening.
- Engine and wrapper self-checks passed.
- All Python sources compiled.
- Exact polished Cricut Voice workbook reopened and passed independent validation with zero hard failures.
- ZIP/archive and internal hash-manifest checks passed on the rebuilt packages.
- The 30-minute and 60-minute input modes remain supported.
- The day-specific workbook retains the 30-minute and 60-minute requirement/shrinkage sheets, with 60 minutes as the default.

## 5. Remaining release gates

1. Run NMG EN in Colab with the canonical RC9.2.2 runner and obtain a zero-return-code sealed case.
2. Run the bounded NMG bilingual/fixed-nesting and GDI 24/7 regressions.
3. Run a genuine 11H/3OFF fixture and the negative 11H-prohibited fixture.
4. Review Cricut Voice warnings and either correct the schedule/configuration or formally accept them under configured WARN gates.
5. Confirm every live workbook has the intended day-specific language rows; International should be absent on Friday/Saturday if those days are not required.

The package is therefore a corrected **RC9.2.2 release candidate**, not a blanket live-production approval. The current blocker is runtime evidence, not an unreported release-path failure.
