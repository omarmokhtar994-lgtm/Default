# Findings: what the engine is wired to, and what a restructure would touch

Read-only study of the engine, 2026-10-25. Nothing in `engine/` (the main tree) was changed. Experiments happen here, in `testing/`.

## 1. The sandbox

`testing/` holds a copy of `engine/`, `tests/`, `tests_staged/`, `tools/`, `packages/`, `fixtures/`, `run_tests.sh`, and symbolic
links to the main `evidence/`, `webapp/`, `deploy/`, `docs/`, `reports/` (the gate reads them; none is edited from here).
The engine file's sha256 equals `engine_file_sha256` in `RELEASE_IDENTITY_RC9_2_2.json`. `engine/regression_assets` is a
byte-for-byte copy here (19 files, checked equal); a link did not work, because the regression-lab scripts find the engine from
the file's own location and a link resolves to the main tree.

The gate in a first, thinner copy failed 9 suites: 7 for missing `evidence/`, `webapp/`, `deploy/` and 2 for the link above. That is
itself a finding: **the gate reads more than the engine** (evidence baselines, the website, the install script).

## 2. The engine file

`engine/_tools/l632_universal_scheduler.py`: 26,469 lines, 360 functions, 12 classes, 182 module constants. No function is
unreferenced, and no two long functions are near-duplicates. Functions by name group: `run_*` 17 (6,538 lines), `parse_*` 17
(1,848), `solve_*` 2 (1,700), `build_*` 5 (1,400), `calculate_metrics` 916, `write_*` 5 (752), `validate_*` 5 (665),
`select_*` 7, `break_*` 11, `language_*` 8, `coverage_*` 9, `shift_*` 12, `consistency_*` 7, `skeleton_*` 7.

`run_case` (lines 21144 to 25072, 3,929 lines): 72 parameters, 571 local variables, ten statements, one of them a `with`
block of 3,853 lines that holds 466 sequential statements (270 assignments, 75 `if`, 16 `for`). No inner functions, no stage comments.
The big blocks (lines 22248 to 25064) are the profile loop, the skeleton-only branch, the anchors, the task loop, the joint
refinement, the exception search, the candidate selection and the output row.

## 3. How the rest of the repository is wired to it

**Entry points.** The wrapper `engine/RUN_UNIVERSAL_PRODUCTION.py` starts the engine as a script
(`python -u engine/_tools/l632_universal_scheduler.py ...`, line 1307) and also imports it after
`sys.path.insert(0, engine/_tools)`. The independent validator loads the file by path with `spec_from_file_location`. The
website's schedule runner (`webapp/schedules.py:524`) and `webapp/break_rules_cli.py` pass the file's path.

**Identity.** The file's own hash is pinned in six places: `RELEASE_IDENTITY_RC9_2_2.json` (`engine_file_sha256`),
`packages/rc9_2_2_production/SCENARIOS.json` (`engine_sha256`), the package manifest written by
`tools/build_production_package.py` (twice), the runner's `verify_engine` (`rc921_runner.py:87`), and the audit records the wrapper
writes (`sha256_file(ENGINE)`). `tools/refresh_engine_identity.py` rewrites the first two after an engine edit, so the
identity-refresh path exists. The wrapper also reads the release name by regex from the engine's text (a `VERSION` constant,
line 32).

**Callers.** 54 files use 161 of the engine's 554 public names: `parse_input` (36 files), `validate_input_contract` (11),
`capacity_diagnostics` (11), `canonical_hash` (9), `HardConfig` (9), `build_skeleton` (9), `calculate_metrics` (7),
`solve_breaks` (7). Outside the tests, the callers are the wrapper and 12 tools. The validator shares about 20 engine
functions by name (`engine/tools/VALIDATOR_INDEPENDENCE.md`).

**Tests.** 66 test files touch the engine. 27 load it as a module (1,223 calls through the module name). 43 read its text, with 534
`assertIn("literal", source)` checks and 18 uses of `ast` on the engine file.

**Process-wide switches.** Six module-level names are written with `global` by `main()` and read in other functions:
`FINAL_RECOVERY_ENDGAME_ENABLED`, `STAGE1_PROFILE_ROTATION`, `BREAK_LOAD_FEEDBACK_ENABLED`,
`DAY_NEIGHBOURHOOD_BREAK_SEARCH_ENABLED`, `SHIFT_CONSISTENCY_CLI_OVERRIDE`, `SOLVER_DETERMINISTIC_TIME` (the last is changed
around each solve). If the code moved to several modules, a switch written in one module would not be seen by another that
imported its value.

**Already modular.** The engine imports `phase_b_maturity` and `phase_b_adaptive` (siblings in `_tools/`), and
`tools/check_cross_module_calls.py` already checks calls across sibling modules (it walks `engine/**/*.py`). So a split into
siblings follows an existing pattern.

## 4. What would have to be rewired first (in this order)

1. **A source accessor for the tests.** One helper (`engine_source()`) that returns the engine's text across all its files
   replaces the 90 direct reads of the one file. The 534 literal checks stay valid if code is moved without rewriting. This
   can be done and proven before any engine byte moves.
2. **A settings object for the six switches.** One module that owns them, read as `settings.NAME` everywhere. The tests that set
   them (1 to 2 files each) change with it.
3. **Identity over a set of files.** A shared function that hashes the engine's files in a fixed order, used by the six places
   above. `VERSION` stays literal in the file the wrapper reads.
4. **Keep the file and its command line.** `_tools/l632_universal_scheduler.py` stays the entry file and re-exports the public
   names (`from .x import *` style), so the 54 callers, the validator and the website need no change.
5. **A proof that nothing changed.** The engine has `SOLVER_DETERMINISTIC_TIME` (a CP-SAT work budget, not a wall clock), so a
   run with the same input, seed and budget should be reproducible. The proof is to run the protected workbooks and compare every
   output cell, old engine against new. It has to be shown to be reproducible first (old against old).

## 5. Impact by option

| Option | Engine bytes | New identity needed | Tests touched | Risk |
|---|---|---|---|---|
| A: leave it, add a map and a change report | none | no | none | none |
| B: split `run_case` and other very large functions into named stage functions, same file | changes | yes (`refresh_engine_identity.py`, owner's approval) | source checks that name the moved lines | medium: 571 locals shared by the stages |
| C: package of modules behind the same entry file | changes | yes, and a set hash | steps 1 to 3 above, then the 534 checks keep passing | medium to high |

## 6. Plan to try here (each step ends with the gate and the proof run)

E0 baseline: the gate in the copy, and old against old for the proof run. E1 test accessor (step 1). E2 settings object (step 2).
E3 move the leaf groups with no shared state (shift arithmetic, language rules, input parsing) into siblings, re-exported.
E4 turn `run_case` into stage functions with an explicit state object. E5 identity over a set of files. Stop at any step whose
proof run differs.

## 7. Gate result in the copy

(see the bottom of this file once the run ends)
