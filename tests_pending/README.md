# Tests waiting on their fixes

These suites test fixes that are written (`tools/apply_formula_audit_fixes.py`,
`tools/apply_f1_exact_stage2_hits.py`) but not yet applied to `engine/`. They
fail by design until then, so they live outside `tests_staged/`, which the gate
runs. Each moves into `tests_staged/` in the same commit that applies its fix.

| suite | fix | status |
|---|---|---|
| `test_rc9_2_12_formula_audit_fixes.py` | F-2, F-3, F-4, F-5 | provably inert on every corpus workbook; applied after the A/B batch frees the CPU |
| `test_rc9_2_13_f1_exact_stage2_hits.py` | F-1 | ships only if the four-arm deterministic A/B passes its pre-registered rule |

Both were confirmed to fail before their fix, for the intended reason, so they
are not vacuous.
