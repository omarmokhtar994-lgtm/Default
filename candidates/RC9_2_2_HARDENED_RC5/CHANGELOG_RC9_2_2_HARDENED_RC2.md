# Changelog — RC9.2.2 Production Hardened RC2

Base: `L6.3.2.6-RC9.2.2-BUDGETED-SEARCH-AND-BREAK-CONCURRENCY-RC1`

New release: `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2`

## Scheduling and selection

- Added a one-interval protected/floor tradeoff cap and pairwise rejection so a small after-target gain cannot cause material after80/floor damage.
- Separated the absolute max-target artifact from the guarded production recommendation.
- Removed target-tolerance pruning of the hard-valid frontier and retained all distinct export roles.
- Made fixed OFF and Leave independent of general OFF-preference hardness in aggregate guidance, main CP-SAT, and joint CP-SAT.
- Added fail-fast contradictions for 11H enabled without long shifts and long shifts present while 11H is prohibited.

## Language and cyclic boundaries

- Stabilized the no-language parser contract to always return rules, groups, and mappings.
- Changed language-window membership from point inclusion to quarter-interval overlap.
- Rejects `Can Cover` mappings whose target language is not defined.
- Added independent current-week and next-Sunday language, bilingual, working-window, opening, blank-interval, and zero-active checks.
- Duplicate previous-Saturday rows now hard-fail; unknown historical names are reported as warnings.

## Independent validation

- Preserves duplicate output rows as evidence instead of collapsing them into a dictionary.
- Recomputes hard rules, coverage tiers, floor gaps, language/skill requirements, breaks, OFF patterns, fixed rows, nesting groups, rest gaps, operating boundaries, midnight rollover, and zero-active intervals.
- Validates break segment count, duration, order, alignment, windows, spacing, overlap, edge margins, and concurrency.
- Measures avoidable overage sum, peak, variance, low-demand share, top-10 concentration, maximum run, severity tiers, cap violations, and adjacent distribution imbalance.
- Validates current-to-next-Sunday continuation rather than ending validation at Saturday.
- Emits JSON and CSV error evidence and return code 3 if the validator itself crashes.

## Release integrity

- All phases run against one immutable input snapshot and hash.
- The final prepared workbook—not an earlier source—is independently validated.
- The polisher no longer creates a production ZIP.
- Packaging requires a sealed manifest, validation PASS, and matching input/output/engine hashes.
- Quality reporting, release gates, validation, packaging, and scenario runs now fail with nonzero return codes.
- Run status is written before packaging, so package failure cannot leave a false success state.
- Existing case directories are protected unless overwrite is explicit.

## Performance and runners

- QUICK is the default for ad-hoc, manifest, production, and resume paths.
- DEEP requires a recorded unresolved-defect reason.
- Added production, smoke, targeted, standard, deep, parallel, resume, and canonical RC9.2.2 runners.
- Added pinned-runtime/CP-SAT preflight to stop before consuming optimization time.
- Parallel shards use distinct ledgers, run guards once, and score gates once after all shards complete.

## Input workbook

- Added `inputs/RC9_2_2_NMG_EN_PRODUCTION_INPUT.xlsx`, based on the manually corrected NMG workbook.
- Preserved 42 associates, ten legal 9-hour shifts, fixed/nesting data, rest and OFF semantics.
- Corrected dropdowns, validation messages, formula checks, production gate settings, 24/7/operating-hour controls, language/Can Cover guidance, and invalid-combination visibility.
- Set break concurrency, next-Sunday, and production-quality gates to fail-closed.
- Kept whole-week overage distribution at WARN because it is lower priority than coverage and must not force coverage sacrifice.

## Release status

This is a **NO-GO release candidate** until a runtime with `ortools==9.15.6755` completes the targeted current-build solver gates. See `FINAL_VALIDATION_AND_READINESS_REPORT.md`.
