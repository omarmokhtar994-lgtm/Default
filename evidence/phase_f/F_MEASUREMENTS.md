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

## Pair 2: Cricut Voice, control vs :30 starts (landed 08:00)

| | control | :30 starts on |
|---|---|---|
| at target after breaks | 245 | 245 (0) |
| at floor after breaks | 253 | 254 (+1) |
| at target / floor before breaks | 247 / 253 | 247 / 254 |
| :30 shift-days used | - | 1 (Thu 17:30 - 02:30) |
| validator, as run | PASS | FAIL (same "shifts" defect as pair 1) |
| validator, re-run with the fix | - | PASS, 0 hard failures |
| release verdict, as run | RELEASABLE (gates 4/5 absolute not evaluated) | NOT_RELEASABLE (gate 8 only) |

Reading: same target, +1 floor, so **no gain measured**. The engine used one
:30 shift-day; :00 starts already cover Voice.

## Pair 3: NMG EN+SP, control vs :30 starts (landed 09:00)

| | control | :30 starts on |
|---|---|---|
| at target after breaks | 174 | 173 (-1) |
| at floor after breaks | 214 | 216 (+2) |
| at target / floor before breaks | 194 / 232 | 188 / 227 |
| :30 shift-days used | - | 17 |
| validator, as run | PASS | FAIL (same "shifts" defect, 10 twins listed) |
| validator, re-run with the fix | - | PASS, 0 hard failures |
| release verdict, as run | REVIEW_REQUIRED (gate 4: engine quality benchmark WARN; gate 5) | NOT_RELEASABLE (gate 8; gate 5) |

Reading: -1 at target, so **no gain measured**. The engine used 17 :30
shift-days, yet after breaks the result is level with the control and before
breaks it is lower (188 vs 194). The wider library gave the time-limited search
more choices without a better week. Gate 4 differs between the arms because
the engine's own quality benchmark was WARN on the control and PASS on the :30
arm; both have no protected minimum configured.

## :30 starts summary (pairs 1-3)

No program met the pre-registered "worth considering" bar. Chat traded +9
target for -3 floor; Voice and NMG EN+SP were level. Recommendation for the
owner: keep "Allow Half-Hour Starts" off by default (as shipped); it stays
available per program.

## Pair 4: AE IT B2B, concurrent-break ratio 0.3 vs 0.4 (landed 09:58)

Workbook: the owner's own AE IT B2B snapshot from the 2026-10-05 T90 run,
copied; only "Maximum Concurrent Break Ratio" changed (0.3 -> 0.4).

| | control (0.3) | ratio 0.4 |
|---|---|---|
| at target after breaks | 93 | 95 (+2) |
| at floor after breaks | 104 | 103 (-1) |
| at target / floor before breaks | 112 / 112 | 112 / 112 |
| target / floor losses from breaks | 19 / 8 | 17 / 9 |
| break concurrency warnings | 9 | 1 |
| validator | PASS | PASS |
| release verdict | REVIEW_REQUIRED (gate 5) | REVIEW_REQUIRED (gate 5) |

Reading: +2 at target, so **inconclusive** (a second seed would be needed).
Scope note: the same workbook also sets "Maximum Concurrent Breaks" = 4, and
the engine's cap per quarter is min(staffed - 1, floor(ratio x staffed), 4).
So 0.4 only loosens quarters with 5-13 people staffed (from 14 up the cap is 4
under both ratios). The ratio change cuts concurrency warnings 9 -> 1 but
recovers only 2 of the 19 target intervals lost to breaks; a larger effect
would need the absolute cap or the break windows changed (owner's call).
