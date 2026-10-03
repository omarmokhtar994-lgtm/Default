# Phase B result: correctness and validation

Started from commit `5597971` (engine sha256 `e5afd99d…`). Engine after Phase B: sha256 `38f494d9…`.

Every fix was written test-first:
- `TESTS_BEFORE_FIX.txt` shows 25 of 30 new tests failing on the Phase A engine.
- `TESTS_AFTER_FIX.txt` shows all 34 passing.
- Four tests were added during the work, each after a check found a case the first version got wrong:
  - three after the workbook snapshot (below);
  - one after the scenario reruns (the break headline).

  Each of the four fails on the code it was written against.

## What changed

| Step | Finding | Change | Where |
|---|---|---|---|
| B1 | F-05 | An overnight language rule with Coverage Days belongs to the day it starts. Mon–Fri 18:00–05:00 is in force from Monday 18:00 to Saturday 05:00. Monday 00:00–05:00 (Sunday night) is not covered; it used to be, and Saturday 00:00–05:00 was not. The required-language shift check now reads after-midnight quarters on the following day. | `language_rules_at`, `shift_overlaps_required_language_for_noneligible` |
| B2 | F-08 | The contract fingerprint now covers every enforced setting it lacked: language working window mode and windows, coverage split rules and gate mode, OFF/leave/preference/fixed switches, 11H mode, the polish setting, and each person's requests. `run_parameters` records the language-window and polish overrides. | `input_contract_payload`, `run_case` |
| B3 | F-12, F-13 | **Coverage Split rows** are read completely or refused (`HARD_INVALID_COVERAGE_SPLIT_ROW`): times, ratio, `Exclusive?`, `Active?`, and a blank `Active?`. On the blank: the template says "blank = ignored" while the parser read it as active, so it now asks instead of guessing.<br>**Coverage Split Gate Mode** now drives a `coverage_split` gate.<br>**The validator and the clean-room checker** both recompute Coverage Split shortfalls after breaks. `coverage_split_gap_count` joins the parity surface (51 → 52 fields).<br>**`validate_schedule`** now checks hard-OFF and leave preferences, Sat→Sun and previous-Saturday rest, consecutive OFF, nesting groups, the language window, and coverage split. | `_parse_coverage_split`, `production_quality_gate`, `validate_schedule`, `independent_validator.coverage_split_gaps`, `clean_room_check.py`, `canonical_metrics` |
| B4 | F-19 | The runner runs the clean-room checker (no engine code) after the validator and parity pass.<br>A rule violation, or a coverage figure that differs from the engine's, blocks with `FAIL_CLEAN_ROOM`.<br>A layout it cannot read is `NOT_CHECKED`: recorded, not blocking.<br>The checker now counts leave days from the published Leave cells, so leave words it doesn't know cannot cause a false OFF-count violation. A published Leave nobody asked for is its own violation. | `RUN_UNIVERSAL_PRODUCTION.run_clean_room_gate`, `clean_room_check.py` |
| B5 | F-10, F-14 | **Infeasible contract:** the diagnosis gets the run's remaining time minus finalization, capped at 15 minutes. Constraint isolation stops at its budget.<br>**Refused before solving, cells named:** fixed shifts in hours the blank rule bans (`FIXED_REQUEST_IN_BLANK_HOURS`) or outside the language window (`FIXED_REQUEST_OUTSIDE_LANGUAGE_HOURS`).<br>**Outcome texts:**<br>• a diagnostics-only run is `DIAGNOSTICS_ONLY_COMPLETE`, no longer "Final schedule generated";<br>• the engine's diagnosis of any no-schedule run is kept; "engine output problem" is gone;<br>• a blocked schedule lists **Why it is blocked** (parity field, validator rule, clean-room rule, FAIL-mode gate), and the engine's own quality findings stay under "Warnings";<br>• findings are de-duplicated;<br>• a failed break search claims an exception-cap gap only when one is proven. | `infeasibility_diagnosis_budget`, `run_constraint_isolation`, `validate_input_contract`, `build_business_outcome`, `format_business_outcome`, runner `reconcile_business_outcome_after_validation`, `_blocking_reasons` |
| B6 | F-16 | Every alternative export (MAX_TARGET, MAX_FLOOR, BALANCED) is independently validated and recorded; this does not affect the main release. It surfaced a real defect: the validator read their artifact type as unrecognised, so **none of them could ever pass validation**. Fixed. | runner `validate_alternative_exports`, `independent_validator.declared_artifact_type` |
| B7 | F-11 | **Unreadable numbers:** every numeric instruction row the parser reads, plus break-window rows, is checked (`HARD_INVALID_INSTRUCTION_NUMBER`).<br>**Contradictions now refused:**<br>• no-break exceptions on with a maximum of 0 (it used to become 8);<br>• long durations with 11H/3OFF off (they used to become 9 h);<br>• zero shift variety (it used to become 1);<br>• no readable duration;<br>• the same label twice on one sheet with different values (the last row used to win).<br>**Notes columns:** a sheet headed `Value \| Purpose` no longer has its notes read as values. | `parse_input`, `_parse_duration_set`, `_instruction_pairs`, `_TrackedInstructions` |

**Not changed:**
- Stage-1 and Stage-2 objectives, search, selection.
- The demand or roster of any workbook.
- Any baseline workbook.

**Still open:**
- Phase C (elastic mode F-06/F-07, F-20).
- The F-11 range clamps on concurrency and cap ratios.
- The joint-refinement model's missing split constraint (that model is off in the production runner).
- Break legality inside `validate_schedule` (the independent validator and the clean-room gate check it on every release).

## Proof that good inputs are unaffected (`WORKBOOK_PARSE_SNAPSHOT_BEFORE.json` / `_AFTER.json`)

All **111** workbooks in the repository were parsed by the Phase A engine and by the Phase B engine. The comparison covers:
- the contract result;
- the hard warnings;
- the SHA of parsed facts;
- max shift variety, durations, 11H mode, no-break settings;
- the full coverage split rules and gate mode;
- the SHA of which language rules are in force in each of the 672 quarters of the week.

**Result: 0 of 111 changed.**

The first version did not pass this check. It refused 23 workbooks, every one a false positive:
- **The RC8 regression assets and the SAKS fixture.** Their Engine Defaults sheets are headed `Instruction | Value | Purpose` and carry section rows `[section, label, note]`. Reading B→C made the note a second "value" of the label: one duplicate-label refusal and one unreadable-number refusal per workbook.

  A latent bug sat behind this. On those sheets the note had been the *effective* value of `Overage Penalty Weight` all along, and it only fell through to the default because that default (40) happens to equal the real row.

  The fix: a sheet whose header names C as notes is read A→B only. Measured with `instruction_note_column_effect.py` (`INSTRUCTION_NOTE_COLUMN_EFFECT.json`), the change alters **no contract field in any workbook** and removes only the false refusals.
- **Cricut Voice LANGUAGE_HOURS.** The template writes an explanation row under the Coverage Split header. It is now recognised as the template's own row.

**Contract fingerprint.** B2 widens it, so every workbook's hash moves although no workbook changed. For the three RC9.1 baseline-protected workbooks, `BASELINE_CONTRACT_WIDENING.json` proves four things:
- the file bytes equal the pinned `file_sha256`;
- the Phase A hash equals the recorded hash;
- every previously recorded field has the same value;
- 13 fields were added and none removed.

`evidence/RC9_1_BASELINE.json` gained one history entry per scenario, following the earlier merge precedent. The scored RC9.1 metrics are untouched.

One field was dropped from the widened fingerprint: `coverage_split_source`. "No sheet" and "the template's empty sheet" enforce the same thing, and recording the label broke the rebuild-preserves-contract test.

## Parse probes after Phase B (`PARSE_PROBES_AFTER_PHASE_B.json`)

Every probe that Phase A left for Phase B is now refused, or read correctly:

| Probe | After Phase A | After Phase B |
|---|---|---|
| P06 11 h durations, Use 11H/3OFF = No | silently 9 h | `HARD_LONG_DURATION_WITHOUT_11H_MODE` |
| P10 no-break exceptions on, maximum 0 | silently 8 | `HARD_CONTRADICTORY_NO_BREAK_LIMIT` |
| P11 max different shifts `three` / `0` | silently 3 / 1 | `HARD_INVALID_INSTRUCTION_NUMBER` / `INVALID_MAX_SHIFT_VARIETY` |
| P12 Coverage Split Start `9am` | row dropped | `HARD_INVALID_COVERAGE_SPLIT_ROW` |
| P19 `Target` twice, 0.9 then 0.5 | last row won | `HARD_DUPLICATE_INSTRUCTION` |
| P21 Mon–Fri 18:00–05:00 Spanish | in force Mon 00:00–05:00, not Sat 00:00–05:00 | in force Mon 18:00 to Sat 05:00 only |

## End-to-end scenarios through the production runner (`scenario_results/`, QUICK 300 s, 2 workers, seed 9000)

Most rows ran on engine `550788cb…`. The last engine change touches only the headline of a failed break search where no cap gap is proven, so S11 and S13 (the two affected) were rerun on the final `38f494d9…`.

| Scenario | After Phase A | After Phase B |
|---|---|---|
| S01 baseline | exit 0 | **exit 0**. Validator PASS, clean-room gate PASS (0 violations), MAX_TARGET export validated PASS |
| S05 Spanish shortage | INFEASIBLE in 2 s; "not enough time left to find which rules conflict" | INFEASIBLE. The diagnosis gets 179 s and names **language rules** as the conflicting family |
| S06 7 days leave | exit 0 | **exit 0**. Clean-room PASS, export PASS |
| S08 24/7 week boundary | exit 0 | **exit 0**. Clean-room PASS, export PASS |
| S09 lone night coverage | no schedule; "engine output problem" | no schedule. Text: "The break plan exceeds the approved exception limit … proven gap is 6", with the 7 associate-days named |
| S10 fixed shift vs blank rule | INFEASIBLE after the probe, cause unnamed | **refused in 1 s**: `FIXED_REQUEST_IN_BLANK_HOURS`, Agent A Sun–Thu `22:00 - 07:00` |
| S11 overnight Mon–Fri Spanish | refused: `SKILL_WINDOW_PAID_CAPACITY_PROVABLY_INSUFFICIENT` (false, caused by F-05) | **contract accepted**, probe FEASIBLE. Stops at break placement: Agent C is the only Spanish cover Monday 18:00–23:45, so any break leaves Spanish uncovered. That is real, and it is Phase C (elastic) work. Text: "No legal final break plan was found" with Agent C named |
| S13 24/7 understaffed | no schedule; "engine output problem" | no schedule. "No legal final break plan was found" with the bottleneck named |
| S14 duplicate Preference row | refused in 1 s | refused in 1 s (unchanged) |

## Golden replay: final validator, parity and clean-room gate on 40 saved schedules (`GOLDEN_REPLAY_GATES.json`)

The set:
- Every saved final schedule from this audit: real AE_IT, Chat, Voice, H1, the polish runs, and the Phase A and Phase B real runs.
- The synthetic scenarios.

Results:
- **Parity:** zero mismatches on any field, including the new `coverage_split_gap_count`. Schedules made before Phase A lack only the three Phase A `*_all_staffed_quarters` names in their old audits; that is expected.
- **Clean-room gate:** PASS on 39 of 40.
- **The one failure is correct:** the S14 schedule made by the pre-Phase-A engine from a duplicate Preference row. The clean-room gate reports `duplicate_input_row`; the validator reports `LEAVE_VIOLATION` and the cross-check mismatch.
- **No false block** on any real workbook.

## Real workbook end to end (`real_run_voice_language_hours/`)

- **Workbook:** `fixtures/real_runs/language_hours/Cricut_Voice_LANGUAGE_HOURS.xlsx` (33 associates, ALL_ROWS language hours, per-day windows).
- **Run:** production runner, QUICK 3600 s, 4 workers, seed 9000, final engine `38f494d9…`. Same settings as the Phase A real run.

| Check | Result |
|---|---|
| Runner exit code | **0** (engine 0, quality report 0) |
| Independent validator | **PASS**; parity **PASS** on all **52** canonical fields |
| Clean-room gate (new) | **PASS**, 0 violations, 0 disagreements with the engine |
| Alternative exports (new) | MAX_FLOOR **PASS**, MAX_TARGET **PASS**. Before Phase B neither could pass: the validator did not recognise their artifact type |
| After-break target | 248 / 264, identical to the Phase A run (search unchanged) |
| Time added by the new checks | about 4 s after the validator |
| Engine elapsed | 3,447 s of 3,600 |
| Outcome text | "Hard-valid final schedule generated with declared operational warnings", with the four quality findings listed once each under **Warnings** |

## Gate (`GATE_RUN.txt`)

`./run_tests.sh` on the final engine `38f494d9…`: **GATE PASS — 51 suites, 1,349 tests (2 skipped)**. The floor in `GATE_MINIMUMS.json` was raised to 1,349.

Four existing tests were re-pinned or adjusted, each with its reason written in the test or the evidence:

| Test | Change and reason |
|---|---|
| `test_rc9_2_4_b9_metric_coverage` | Parity field count 51 → 52 (`coverage_split_gap_count` added; nothing removed). |
| `test_rc9_2_3_max_coverage_hardening` | Both sides of the canonical-surface fixture publish `coverage_split_gap_count`. |
| `test_rc9_2_1_tooling_integrity` (baseline prefix) | Satisfied by the new baseline history entries; proof above. |
| `test_rc9_2_1_validator_parity` (source scan for `rc = 4` after `ERROR_VALIDATOR_DID_NOT_COMPLETE`) | The new alternative-export helper used the same status literal earlier in the file. The helper moved below `main()`; the check again reads the main validator path, whose behaviour did not change. |

## Package

`dist/RC9_2_2_PRODUCTION_PACKAGE.zip`, sha256 `33f67cfdf3c80f7ee25ef4eae2a760715f5903d82a28e818115dbd2bc0477eb8`, 1,572 files. The checks run on it:
- Its own `./run_tests.sh`, run from a clean extract: GATE PASS, 51 suites, 1,349 tests.
- The clean-room checker ships at `tools/clean_room_check.py`, where the runner looks for it.
