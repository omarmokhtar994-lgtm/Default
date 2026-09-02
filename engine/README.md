# RC9.2.1 Protected Tier + Residual Balance RC1

This patch supersedes RC9.2-PROTECTED-BALANCE-RC1 for regression testing. It corrects lower-tier champion ordering and adds target-locked residual OFF/day-balance polish. It is NOT yet a stable production promotion; fresh smoke/standard/deep regression is required.

# L6.3.2.4-RC9.2-PROTECTED-BALANCE-RC1

This is a controlled successor to RC9.1. It preserves the workbook-driven universal engine and fixes proven cross-scenario defects rather than redesigning the solver.

## Main corrections

- Target-protected champion selection: workbook target remains primary; configured floor, concentrated-gap quality, cyclic/language safety, balance and overage are protected before higher-tier upside.
- Fixed-aware aggregate guidance: exact fixed/nesting shifts and hard OFF patterns constrain aggregate day/shift targets.
- Native `--skeleton-only`: no runtime source patching; Stage 1 receives the usable budget and exports the best plus ranked alternatives.
- Overage distribution metrics: total, peak, variance/stddev, low-demand share and consecutive concentration.
- `protected_balance_polish` profile retained alongside all RC9.1 profiles.

## Production run

```bash
python RUN_UNIVERSAL_PRODUCTION.py --input Workbook.xlsx --output-root results --schedule-id MySchedule --mode DEEP
```

## Before-break skeleton run

```bash
python RUN_UNIVERSAL_PRODUCTION.py --input Workbook.xlsx --output-root results --schedule-id MySchedule --mode QUICK --time-limit 3600 --num-workers 4 --skeleton-only --export-top-skeletons 5
```

`BEST_BEFORE_BREAKS` is review-only. Production use still requires `BEST_FINAL_AFTER_BREAKS` plus independent validation.

## Release status

This package is an RC1 candidate. Use the included regression package and release gates before production promotion.
