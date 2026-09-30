# Changelog — RC9.2.2 Maximum-Coverage Correction Package RC5

This patch responds to the RC4 validation review and the latest NMG/GDI
results. The engine's primary outcome is the strongest schedule it can find;
release approval remains a separate, explicit gate.

## Corrections

- Reordered the protected Stage-2 anchor and adaptive portfolio by coverage
  first: an unfinished exception diagnostic no longer causes a stronger
  coverage skeleton to lose to a weaker proven-zero skeleton. Proven-positive
  exception minima remain deferred when an eligible candidate exists.
- Capped the protected anchor reserve at the measured convergence-sized budget
  so the adaptive portfolio receives the remaining Stage-2 search time.

- Replaced the global-dominance candidate guard with floor-anchor-relative
  severity, concentration, and deficit limits. A normal deep-run candidate
  pool can no longer make every candidate ineligible and then silently revert
  to target-only selection.
- Added a protected-safety fallback ordering for the defensive case where no
  candidate satisfies the guard. The fallback prioritizes hard-floor safety,
  floor coverage, protected tiers, gap shape, and then maximum target coverage.
- Preserved target-first selection inside the protected safety envelope, so the
  engine still seeks the maximum schedule rather than defaulting to the
  lowest-risk but materially weaker result.
- Changed language working-window enforcement to constrain shift start times.
  A legal overnight shift may continue beyond the Coverage End time; its start
  must still fall inside the authored cyclic window.
- Quality-gate failures no longer prevent exact-artifact preparation and
  independent validation when the generated schedule is hard-valid. The
  schedule is retained with a visible quality-blocked status, while production
  sealing remains blocked until all release gates pass.
- Sealed manifests now distinguish automated hard-gate evidence from human
  production approval and no longer claim `production_ready: true` solely from
  automated checks.
- Coverage-first objective order is now enforced in the break and joint
  search paths even when the quality gate is configured to fail; quality debt
  remains a release decision rather than a hidden coverage constraint.
- The independent validator now checks cyclic next-Sunday break concurrency,
  and the runner blocks publication when engine and validator canonical
  metrics disagree.
- All exported audit metric surfaces now retain scalar gap, blank-staffing,
  overage, and boundary values; only bulky row/detail collections are omitted.
- The full audited Stage-1 skeleton retention cap is preserved through
  recovery instead of being silently reduced before Stage 2.
- Quality-failed but hard-valid engine results now reach polishing and exact
  validation; unreadable or missing final Phase-C safety reports fail release
  sealing closed.
- Independent validation now separates hard-rule failures from release-quality
  failures, so a quality-only failure cannot masquerade as an unsafe workbook.
- Overage concentration now measures avoidable overage in both evaluators,
  removing the prior total-overage versus avoidable-overage mismatch.
- Added regression coverage for the three-candidate selector collapse, start
  window semantics, and validation of hard-valid schedules carrying quality
  warnings.
- The independent validator now imports explicit rows from `No-Break
  Exceptions` as zero-duration, evidence-bearing break records, including the
  GDI exception contract, instead of reporting a false missing-break failure.
- Blank-staffing validation now distinguishes current-week assignments from
  Saturday carry-in, preventing prior-week spillover from being counted as
  staffing in the current week.
- Business-outcome reconciliation now matches the actual solver-audit filename
  contract, preserves genuine pre-solver input failures, and reads validator
  JSON before deriving quality fields; a failed or missing validation report can
  no longer be treated as a completed result.
- Break-search time is explicitly partitioned between recovery, a protected
  full-width anchor solve, and meaningful adaptive exploration. The anchor is
  no longer starved by recovery work, so high-coverage skeletons receive a
  real search opportunity before being classified as infeasible.
- The RC9.1 comparison baseline and provenance are carried into both rebuilt
  package types so release-gate comparisons are reproducible on a fresh
  runner.

## Operating rule

The solver must continue searching and return the best available schedule
within its budget. Minor quality debt is reported and blocks clean release;
it does not erase the schedule or convert a completed search into an internal
engine error. A quality-blocked hard-valid case may be packaged as explicitly
review-only evidence, but it cannot be sealed as production-ready. True
input-contract failures, unsafe hard-rule violations, metric-parity failures,
and missing/corrupt artifacts remain blocking.
