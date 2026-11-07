# Phase BL A/B: new Schedule-sheet columns blank (pre-registered 2026-11-07, before the run)

**Question.** Do the Phase BL engine changes (optional columns `Shift Length`, `Type`, `Off Days`, `Breaks`; a shift-length rule;
part-timer off-day and break rules) change anything when those columns are blank or absent?

**Arms.** A: the engine file at commit `0b0fefe` (before any Phase BL engine change). B: the engine file in the working tree.

**Workbooks.** All nine files in `engine/regression_assets/ready_inputs` (read only, never modified), none of which has the new columns.

**Measure.** For each workbook, the SHA-256 of the Stage 1 CP-SAT model (`build_skeleton`, seed 9000, default hard rules, stopped
before solving) with `ab_model_hash.py`. The same model hash means the same constraints and objective, so the same search.

**Decision rule.** PASS only if all nine hashes are identical between A and B. Any difference is a regression: the change is
reverted or fixed, not explained away. Limits: the hash covers Stage 1; Stage 2 (breaks) is untouched by task 2 and is covered by
its own check after task 3; the joint refinement and the polish steps are covered by the unit tests in
`webapp/tests/test_bl_engine_85.py` and the existing gate.

## Result
(filled in after the run)
