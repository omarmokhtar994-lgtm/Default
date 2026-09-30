# RC9.2.2 Maximum-Coverage RC5 engine

This is the universal, workbook-driven engine for the RC9.2.2 RC5 correction package.

The engine has no client-name branches. It applies one normalized contract to 9H/2OFF and 11H/3OFF schedules, fixed rows, fixed OFF/Leave, separate or consecutive OFF, nesting groups, rest gaps, language and bilingual coverage, operating boundaries, overnight shifts, 24/7 demand, breaks, and cyclic Sunday boundaries.

Quality order is enforced as:

1. hard rules;
2. critical coverage;
3. floor and after80;
4. target and after90;
5. after100 where applicable;
6. language/skill coverage;
7. break legality;
8. overage amount and distribution;
9. schedule polish.

Production publication is fail-closed. The wrapper snapshots the input, runs the engine, keeps the strongest generated candidate, prepares the output workbook even when an operational quality gate fails, validates that exact workbook independently, and seals/packages it only when every release condition passes. A quality-blocked schedule remains available for review and is never silently approved.

The `L6_3_2_3` text retained in some output filenames is a compatibility token. Use `RUN_IDENTITY.json`, `UNIVERSAL_RUN_IDENTITY.json`, the engine SHA-256, validation seal, and package manifest as identity authority.

Install and verify:

```bash
python3 -m pip install -r requirements.txt
python3 ../tools/runtime_environment_check.py
```

Current release status is recorded at package root in `RELEASE_STATUS.json`.
