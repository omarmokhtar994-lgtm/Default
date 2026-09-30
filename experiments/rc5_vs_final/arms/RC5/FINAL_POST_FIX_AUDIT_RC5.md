# RC9.2.2 RC5 — Maximum-Coverage Post-Fix Audit

Audit target: `RC9_2_2_MAX_COVERAGE_RC5`

## Decision

The RC4 validation evidence showed that the engine could produce a hard-valid
schedule but that two deferred behaviors could weaken the selected result or
make a valid language roster appear infeasible. RC5 closes those two defects
and changes quality-gate handling so a generated hard-valid schedule is not
discarded merely because a quality gate blocks production approval.

## Corrections applied

1. Candidate selection now uses limits relative to the best-floor anchor. The
   old global-dominance tests could reject every candidate in a realistic
   deep-run pool; the fallback then selected by target only. RC5 keeps the
   target primary inside a protected safety envelope and uses a safety-first
   fallback if the envelope is unexpectedly empty.
2. Language working windows now bound shift starts. Overnight shifts are
   allowed to continue past the window end, consistent with the contract's
   interpretation as a working-window start restriction.
3. A hard-valid final workbook is prepared and independently validated even
   when the operational quality gate is WARN/FAIL. The quality result still
   blocks sealing and production use; it no longer prevents the schedule from
   being returned for review.
4. Automated hard-gate evidence is no longer labeled as human production
   approval in the sealed manifest.
5. The break/joint objective order is target-first even under a failing
   quality gate; quality remains visible and release-authoritative but no
   longer suppresses the coverage search.
6. Cyclic next-Sunday break concurrency is included in independent validation,
   and canonical engine/validator metric parity is a release gate.
7. Scalar gap and boundary metrics are retained in every compact audit
   surface, and the Stage-1 retention cap is preserved through recovery.
8. Final Phase-C safety evidence is required before a production manifest can
   be sealed; missing or unreadable safety evidence fails closed.
9. Independent validation now keeps quality-gate findings separate from
   hard-rule failures, and avoidable-overage concentration uses one definition
   in both evaluators.
10. Explicit no-break exception rows are now consumed by independent
    validation, and current-week blank staffing is separated from Saturday
    carry-in coverage.
11. Business-outcome reconciliation now matches the actual solver-audit
    filename and preserves genuine pre-solver contract failures.
12. Break-search recovery, the protected Stage-2 anchor, and adaptive search
    now have separate deterministic reservations; recovery cannot starve the
    high-coverage anchor.
13. Stage-2 anchor and adaptive ordering now keep unknown breakability eligible
    beside proven-zero candidates, ranking by coverage first; only proven
    positive exception minima are deferred. The anchor reserve is capped at the
    measured convergence-sized budget.

## Verification

- Offline gate: PASS.
- Test suites: 453 tests passed; 5 environment/legacy checks skipped.
- Engine self-check: PASS.
- Wrapper self-check: PASS.
- Selector reproduction: the three-candidate +3 target / -9 protected-tier
  trade selects the protected-safe candidate rather than reverting to
  target-first fallback.
- Language-window reproduction: a 16:00-03:00 window accepts starts from
  16:00 through 02:59 and rejects a 03:00 start, regardless of shift duration.
- Package identity: manifests are regenerated against the RC5 engine hash.
- Stage-2 ordering reproduction: a 227-target unknown-breakability skeleton
  leads a 226-target proven-zero skeleton, while a proven-positive minimum is
  deferred; the protected anchor reserve is 240 seconds for the 904-second
  measured break-search window.

## Release boundary

RC5 does not silently approve quality-blocked schedules. It returns the best
available hard-valid candidate and its independent validation evidence. A
quality-blocked hard-valid case can be packaged as review-only evidence, but
not as a production-ready delivery. Input contract failures, hard-rule
violations, metric-parity failures, and missing/corrupt artifacts remain
blocking.
