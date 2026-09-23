# Changelog — RC9.2.2 Correction Package RC3

Engine release remains `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2`.
This package revision corrects release validation and reporting; it does not
change the solver’s staffing or language-coverage objectives.

## Corrections

- Independent validation now evaluates only the protected Saturday-to-next-Sunday
  spill horizon. Ordinary current-week Sunday intervals are no longer duplicated
  as false `NEXT_SUNDAY_CARRY_OUT` failures.
- The runner reconciles the final business outcome after exact-workbook
  validation. A validation failure, validation error, skipped validation, or
  failed release gate now forces `production_eligible=false`.
- Root and debug business-outcome files, solver audit JSON, and summary CSV all
  carry the final validation status and blocked-release explanation.

## Verification

- Full offline gate: 10 suites and 2 self-checks passed.
- Targeted hardening suite: 18 tests passed.
- Exact Voice result revalidation: validator PASS, 0 hard failures, 0
  Next-Sunday carry-out failures; genuine quality warnings remain.
- Exact Chat result revalidation: validator PASS, 0 hard failures, 0
  Next-Sunday carry-out failures; genuine quality warnings remain.

This remains a release candidate. It is not production approval until the
required current-build solver and quality gates in `RELEASE_STATUS.json` pass.
