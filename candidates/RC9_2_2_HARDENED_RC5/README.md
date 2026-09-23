# RC9.2.2 Maximum-Coverage — Correction Package RC5

Engine release: `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2`

Package revision: `RC9_2_2_FIX_VALIDATION_RC5` / `RC9_2_2_MAX_COVERAGE_RC5_RELEASE_CANDIDATE`

Status: **NO-GO pending current-build CP-SAT validation.** Keep RC9.1 live until the closing runs listed in `RELEASE_STATUS.json` pass. This package is a hardened release candidate, not a production approval.

## What this batch corrects

- Prevents small target gains from buying material after80/floor losses during champion selection.
- Prevents the multi-candidate guard fallback from reverting to target-only selection.
- Treats Language Setup Coverage Start/End as a shift-start window, so legal overnight shifts may continue past the window end.
- Continues producing and validating a hard-valid schedule when only operational quality limits fail; the result remains quality-blocked and cannot be sealed for production.
- Preserves the complete hard-valid frontier and exports distinct candidate roles.
- Makes fixed OFF/Leave authoritative independently of preference-hardness settings.
- Corrects language parsing, quarter overlap, unknown `Can Cover` targets, working-window validation, and bilingual/current-to-next-Sunday checks.
- Rejects contradictory 11H configuration and duplicate cyclic-boundary rows before solving.
- Validates break legality, fixed/nesting rows, OFF/rest/overnight rules, coverage tiers, operating boundaries, zero-active intervals, Sunday rollover, and overage distribution independently.
- Freezes the exact input snapshot and seals only the exact polished workbook that independently passed.
- Prevents the polisher from creating a production ZIP before validation.
- Makes quality, validation, packaging, runner, and release-gate failures return nonzero while preserving the generated schedule for review.
- Keeps coverage as the first staged optimization objective even when quality gates are configured to fail; quality remains a post-run release decision.
- Publishes one canonical metric surface and blocks release on engine/independent-validator metric parity mismatches.
- Reports truncated Stage-1 portfolios and retained-candidate caps explicitly; no run claims a global coverage maximum without proof.
- Compares the engine and independent validator through one canonical release metric surface, including cyclic boundary, overage, and gap metrics.
- Retains hard-valid schedules through quality-gate failure as review-only artifacts; missing safety evidence, hard-rule failures, or metric-parity failures still block sealing.
- The independent validator reports hard-rule failures separately from quality-gate debt, so a quality-only block does not discard the generated schedule.
- Enforces the Excel validation alerts across all eight shipped input workbooks.
- Disables the obsolete Phase-A packager and protects case directories with an immediate lock/heartbeat.
- Publishes split evidence atomically with a self-contained component manifest in every ZIP.
- Integrates the RC9.2.2 `Read Me First` / Schedule Control Center output dashboard.
- Defaults to QUICK targeted validation; DEEP requires a documented unresolved-defect reason.
- Separates break-search recovery from protected anchor/adaptive time so a high-coverage skeleton is not discarded solely because the anchor timed out.
- Keeps unknown breakability in the coverage-first Stage-2 tier instead of
  treating it as worse than a weaker proven-zero skeleton; proven-positive
  exception minima remain deferred and the anchor reserve is bounded.

The detailed defect map and evidence are in `FINAL_VALIDATION_AND_READINESS_REPORT.md`.
The RC3, RC4, and RC5 correction details are in the corresponding changelog files.

## Required runtime

Use Python 3.12 and install the pinned environment:

```bash
python3 -m pip install -r engine/requirements.txt
python3 tools/runtime_environment_check.py
```

The runtime check must report `PASS`, including its tiny CP-SAT solve, before any schedule run. OR-Tools must be exactly `9.15.6755`.

## Priority NMG validation

```bash
python3 runners/run_smoke.py \
  --input inputs/RC9_2_2_NMG_EN_PRODUCTION_INPUT.xlsx \
  --schedule-id NMG_EN_PRODUCTION_SMOKE_RC5 \
  --output-root results

python3 runners/run_production.py \
  --input inputs/RC9_2_2_NMG_EN_PRODUCTION_INPUT.xlsx \
  --schedule-id NMG_EN_PRODUCTION_QUICK_RC5 \
  --output-root results
```

Do not use any final schedule unless the command returns zero and the case contains a sealed manifest, independent-validation JSON with `status: PASS`, matching hashes, and the final production ZIP.

## Runners

See `runners/README.md`. The standard paths are:

- `run_production.py` — one live workbook, QUICK/FULL by default.
- `run_smoke.py` — bounded smoke path.
- `run_targeted_regression.py` — explicit affected scenarios only.
- `run_standard_regression.py` — bounded manifest regression.
- `run_deep.py` — requires `--reason`.
- `run_parallel.py` — guarded manifest sharding.
- `run_resume.py` — exact-identity checkpoint resume.

The no-Drive Colab notebook (`RC922_Colab_A_NO_DRIVE.ipynb`) also exposes
`RESUME=True` and preserves checkpoints after a controlled interrupt. The
Drive-backed notebook provides the same resume control with persistent storage.

## Compatibility note

Some artifact filenames retain the historical `L6_3_2_3` token for downstream compatibility. That token is not build identity. Identity authority is the embedded release, exact engine/input/contract hashes, independent-validation seal, and package manifest.

## Validation already completed

- 453 current offline tests passed across 11 suites; five environment/legacy-fixture checks were skipped.
- All Python files compile.
- Eight manifest workbooks parse and match their hashes; seven PASS, AE_AR_B2B WARN for obsolete historical names.
- The updated NMG workbook passed contract parsing, formula-error scan, validation-sheet checks, and visual review.
- Four older schedules were independently revalidated for diagnostic baselines only.
- A current-build smoke attempt failed closed because OR-Tools was unavailable; no schedule or package was emitted.

These checks do not replace the required current-build CP-SAT runs.
