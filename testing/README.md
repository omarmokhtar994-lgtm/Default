# testing: a sandbox copy of the engine and its gate

Made on 2026-10-25 at the owner's request ("take this version, make a new copy of it under the name of testing ... not in the
main file, in the test one"). Nothing in `engine/`, `tests/` or the website reads this folder.

- A byte-for-byte copy of `engine/` (without `regression_assets/`), `tests/`, `tests_staged/`, `tools/`, `packages/`,
  `fixtures/` and `run_tests.sh`. The engine file has the same sha256 as the release identity names
  (`0a0a761b66fd7cf2...`).
- `engine/regression_assets` is a symbolic link to the main one, not a copy: the baseline workbooks stay one set of bytes.
  Caution: the regression-lab scripts find the engine from their own location, and a link resolves to the main tree, so they
  would run the main engine from here.
- Run the gate here with `cd testing && PYTHON=/path/to/python bash run_tests.sh`.
- Findings and the plan to try are in `FINDINGS.md`.
