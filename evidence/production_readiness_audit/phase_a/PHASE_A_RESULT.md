# Phase A result: production blockers closed

Started from commit `2abab44` (engine sha256 `85a87258…`). Engine after Phase A: sha256 `e5afd99d…`.
Every fix was written test-first: `TESTS_BEFORE_FIX.txt` shows 25 of 26 new tests failing on the old engine, and `TESTS_AFTER_FIX.txt` shows all 29 passing. The suite grew by three tests during the work.

## What changed

| Step | Finding | Change | Where |
|---|---|---|---|
| A1 | F-01 | Two **filled** rows for one person are refused: `HARD_PREFERENCE_DUPLICATE_ASSOCIATE` on Preference, `HARD_FIXED_REQUEST_DUPLICATE_ASSOCIATE` on Fixed Request. An extra **empty** row is ignored and can no longer erase the filled one. The validator's raw cross-check and the clean-room checker report the same duplicates. | `_parse_preferences`, `_parse_fixed_nesting`, `independent_validator._xc_day_cells`, `tools/clean_room_check.py` |
| A2 | F-02 | Leave counts against the week. OFF owed = min(2, or 3 in long mode, 7 − leave days), enforced identically everywhere. A contract check, `ASSOCIATE_REQUESTS_EXCEED_WEEK`, names anyone whose leave + OFF + fixed requests cannot fit. | `required_off_days`, `add_weekly_off_rule` (Stage 1 and joint models), `validate_schedule`, validator, clean-room, `validate_input_contract` |
| A3 | F-09, F-15 | Day columns are bound by Sun..Sat text, or by **real dates read as their weekday**, never by position. The employee ID is bound by header. Refused: duplicate, missing or off-grid demand rows; duplicate shrinkage rows; roster names below a long blank gap; unreadable shift labels; non-integer or negative language minimums; unreadable previous-Saturday shifts. | `_day_columns`, `_parse_roster`, `_parse_requirement_table`, `_parse_shifts`, `_parse_language_rules`, `_parse_preferences` |
| A4 | F-03 | Two concurrency definitions, each with its own name on both sides. The existing names cover active-demand quarters plus the next-Sunday horizon; this is unchanged and is what the selector reads. The new `*_all_staffed_quarters` cover every staffed quarter. All six fields are in the parity surface (48 → 51 fields). | `calculate_metrics`, `independent_validator.validate`, `canonical_metrics` |
| A5 | F-04 | The strict release check blocks only on a family in FAIL mode that found an issue, or on a FAIL-mode coverage gate that did not pass. Warnings no longer block. | `phase_c_quality_report.release_blocking_reasons` |

**Not changed:**
- Stage-1 and Stage-2 objectives, search, selection.
- The demand or roster of any workbook.
- Any baseline workbook.

## Proof that good inputs are unaffected

**All 110 workbooks in the repository** (`WORKBOOK_PARSE_SNAPSHOT_BEFORE.json` / `_AFTER.json`) were checked, including the packaged inputs, the real-run fixtures, the synthetic suite and the RC8 regression assets. Each one keeps the same contract result and the same SHA of its parsed facts: associates, preferences, fixed requests, previous Saturday, demand, shrinkage, shifts, language rules and windows, coverage split.

This held only after one design correction made during the work. The RC8 GDI/SAKS Preference sheets head their day columns with real dates. The first version refused them; the final version reads a real date as its weekday, which is certain. It refuses only headers that name no day at all.

## Golden replay: new validator on 23 saved final schedules (`GOLDEN_REPLAY_VALIDATOR.json`)

- **Real runs:** AE_IT ×6, Chat ×2, Voice ×7, H1.
  - Zero parity mismatches on any field that existed before.
  - Zero new rule failures.
  - On every one of them, the new all-staffed concurrency figures equal the active figures, so real runs see no change.
- **Synthetic S01, S02, S03:** the false parity mismatch is gone.
- **S14 (duplicate row):** the new validator now reports `LEAVE_VIOLATION Agent A Mon` plus the duplicate cross-check mismatch. The old validator passed every rule on this schedule.

## Parse probes after Phase A (`PARSE_PROBES_AFTER_PHASE_A.json`)

| Probe | Before | After |
|---|---|---|
| P02 columns re-ordered | false duplicate-ID refusal | IDs read correctly, accepted |
| P03 Schedule date headers | positional guess | dates read as weekdays |
| P04 blank duplicate Preference row | Leave lost | Leave kept (a second *filled* row is refused) |
| P05 Fixed Request date headers | all requests dropped | requests read by weekday |
| P07 off-grid demand rows | ignored | `HARD_OFF_GRID_REQUIREMENT_TIME` |
| P08 duplicate demand row | demand erased | `HARD_DUPLICATE_REQUIREMENT_TIME` |
| P09 missing demand row | read as no demand | `HARD_MISSING_REQUIREMENT_TIME` |
| P13 language minimum 0.5 / −1 | rule dropped | `HARD_INVALID_LANGUAGE_MINIMUM` |
| P14 seven leave days | infeasible at solve | accepted and schedulable |
| P15 `08:00 - 24:00` | skipped | `HARD_INVALID_SHIFT_LABEL` |
| P17 roster gap | 5 of 10 read | `HARD_ROSTER_ROWS_AFTER_BLANK_GAP` |
| P18 invalid previous Saturday | ignored | `HARD_INVALID_PREVIOUS_SATURDAY_SHIFT` |

Still silent, as planned for Phase B:
- P06: 11 h with Use 11H/3OFF = No.
- P10: Max no-break = 0 becomes 8.
- P11: max-shifts text.
- P12: Coverage Split row.
- P19: duplicate instruction label.
- P21: overnight day attribution.

## End-to-end scenarios through the production runner (`scenario_results/`, QUICK 300 s)

| Scenario | Before Phase A | After Phase A |
|---|---|---|
| S01 baseline | blocked (parity) | **exit 0**, validator PASS |
| S02 demand +10 % | blocked (parity + coverage gate) | validator PASS; blocked only by its real coverage-gate failure |
| S03 demand ×3 | blocked (parity + coverage gate) | validator PASS; blocked only by its real coverage-gate failure |
| S06 7 days leave | no schedule (INFEASIBLE in 2 s) | **exit 0**, Agent A Leave ×7 |
| S07 6 days leave | no schedule | **exit 0**, Agent A OFF + Leave ×6 |
| S08 24/7 week boundary | blocked (warnings) | **exit 0**, 168/168 |
| S12 overlapping skills | blocked (warnings) | **exit 0**, 84/84 |
| S10 fixed vs blank rule | INFEASIBLE, unnamed | unchanged (Phase B, F-10) |
| S14 duplicate Preference row | leave silently lost | **refused in 1 s**, person and rows named |

Clean-room checker on every published schedule: 0 violations, and exact metric agreement with the engine and the validator.

## Gate

`./run_tests.sh`: **GATE PASS — 50 suites, 1,315 tests (2 skipped)**. The floor in `GATE_MINIMUMS.json` was raised to 1,315. Two existing tests were re-pinned, each with its reason written in the test:
- the parity-field count went 48 → 51;
- the canonical-surface fixture now carries the three new fields.

## Real workbook end to end (`real_run_voice_language_hours/`)

Workbook: `fixtures/real_runs/language_hours/Cricut_Voice_LANGUAGE_HOURS.xlsx` (33 associates, language hours enforced with ALL_ROWS, per-day windows). Run: production runner, QUICK 3600 s, 4 workers, seed 9000, Phase A engine `e5afd99d…`.

| Check | Result |
|---|---|
| Runner exit code | **0** (engine 0, quality report 0) |
| Independent validator | **PASS**, parity **PASS** on all 51 canonical fields |
| Production package | built (production / review / debug zips) |
| Clean-room checker | 0 rule violations; 15 coverage metrics identical to engine and validator |
| After-break target | 248 / 264 (earlier runs of this workbook: 243–247; search is unchanged, so this is seed variance) |
| Break concurrency | 3 violations, identical under both definitions |
| Elapsed | 3,448 s of 3,600 |
Package: dist/RC9_2_2_PRODUCTION_PACKAGE.zip, sha256 a86b335c58d27fa1756cdee2b01146e70d9479be343dcda854e5f4bc344e721b, 1514 files; its own ./run_tests.sh: GATE PASS, 50 suites, 1315 tests.
