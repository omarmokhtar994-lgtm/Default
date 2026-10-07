# Phase F measurements: results as they land

Rules and arms: `evidence/phase_f/F_PLAN.md` (pre-registered before any run).
Production runner, QUICK 3,600 s, 2 workers, seed 9000, engine 65aae568.
Times in Egypt time (UTC+3). Figures are intervals after breaks unless noted.

## Pair 1: Cricut Chat, control vs :30 starts (landed 07:01)

| | control | :30 starts on |
|---|---|---|
| at target after breaks | 167 | 176 (+9) |
| at floor after breaks | 229 | 226 (-3) |
| at target / floor before breaks | 182 / 242 | 186 / 236 |
| :30 shift-days used | - | 9 |
| validator, as run | PASS | FAIL (input cross-check "shifts") |
| validator, re-run with the fix below | - | PASS, 0 hard failures |
| release verdict, as run | REVIEW_REQUIRED (gate 5) | NOT_RELEASABLE (gate 8, gate 5) |

Reading (pre-registered rule): floor more than 1 lower, so **no gain measured**.
It is a trade (+9 at target, -3 at floor), not a clean gain; Chat varies
155-179 at target between runs, and the control repeat in pair 5 measures
that noise on this engine.

### Defect found: validator rejected the :30 shifts

As run, the independent validator failed F_CHAT_HALF with
INPUT_CROSSCHECK_MISMATCH: its raw-workbook shift catalog was read from the
shift sheet only, so all 20 :30 twins the switch adds read as invented shifts.
The F2 plan listed a "validator accepts the flagged shifts" test; it was not
written. Failing test first: `tests_staged/test_rc9_2_49_validator_half_hour_twins.py`
(2 failures before the fix, `F2b_VALIDATOR_TESTS_BEFORE_FIX.txt`). The fix
derives the twins from the raw workbook's own switch (never the parse's
flag), and adds the switch to the request-switch cross-check. Shifts no rule
derives still fail. The fix is held in a separate worktree and merged, gated
and pushed only after the last measured run, so every arm runs on the same code.
Re-validation of the shipped production copy of F_CHAT_HALF with the fixed
validator: PASS, 0 hard failures.
