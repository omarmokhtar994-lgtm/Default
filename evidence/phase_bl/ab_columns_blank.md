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
Run 2026-11-07 (Egypt time), after task 2. Arm A: engine at `0b0fefe`. Arm B: working tree.

| Workbook | Associates | Shifts | Model SHA-256 (A = B) |
|---|---|---|---|
| AE_FRENCH_RC8_6_1_INPUT_READY.xlsx | 13 | 8 | `09e950f255093d99…` |
| GDI_28HC_NO247_RC8_6_1_INPUT_READY.xlsx | 28 | 24 | `bbf10329331ed0ab…` |
| GDI_REAL28_RC8_6_1_INPUT_READY.xlsx | 28 | 24 | `40cadc131d0e3aa0…` |
| NMG12_RC8_6_1_INPUT_READY.xlsx | 12 | 10 | `71b754b2a7035886…` |
| NMG13_RC8_13_CONDITIONAL_PRODUCTION_INPUT_READY.xlsx | 13 | 24 | `64c278d4bc0e48b9…` |
| NMG13_RC8_6_1_INPUT_READY.xlsx | 13 | 24 | `64c278d4bc0e48b9…` |
| NMG_EN_RC8_6_1_INPUT_READY.xlsx | 12 | 10 | `a5cd3f51cc054ef3…` |
| NMG_SPEN_RC8_6_1_INPUT_READY.xlsx | 17 | 10 | `6e508030f6d88dcc…` |
| SAKS_NEW_RC8_6_1_INPUT_READY.xlsx | 50 | 10 | `554a740f38628537…` |

**Verdict: PASS.** All nine hashes are identical between A and B, so with the new columns blank the Stage 1 model is unchanged.
Positive control: on the example workbook with `Shift Length` 8.5 on one associate, the hash differs from the same workbook with the
column blank (`eda1b7bd…` against `8313f58b…`), so the check can detect a change.

Task 3 (part-timers) re-runs this A/B with its own changes in; the final row of results is added below it.

### Re-run after task 3 (part-timers: Off Days, Breaks, capacity estimates)

Same nine workbooks, same helper, engine in the working tree after the part-timer changes. All nine hashes are again identical to arm A
(`diff` of the two outputs is empty). With the new columns blank, the Stage 1 model is unchanged by all of Phase BL's engine work.
Also run, all passing: `tests_staged` capacity, input-safety, shortfall, formula-audit and input-vocabulary suites with the three
`webapp/tests/test_bl_engine_*` files (137 tests), and `webapp/tests/test_bl_validator_length.py` (2 tests) for the independent validator.

### Re-run after the part-time reservation and the clean-room change

A full run of a workbook with an 8.5 hour associate and part-timers passed the independent validator but was blocked by the clean-room
check, which did not know the new columns; it was fixed, and shifts a Part time row claims were reserved for part-timers (a full-timer
without a length was seen working a 5 hour shift). The same nine workbooks and helper were run again against the engine after both changes:
all nine model hashes are again identical to arm A. The three mixed-run outputs (the best schedule and the two candidates) pass the
clean-room check with 0 violations, where before the change they showed `break_set` x52 and `off_count` x3.
