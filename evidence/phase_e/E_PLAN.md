# Phase E: engine model findings, measured

Plan: `docs/superpowers/plans/2026-10-06-phase-e-engine-model.md`.
Spec: `ENGINE_MODEL_REVIEW.md`. Times Egypt (UTC+3).

## Task 1 / F-E3: break stand-in diagnostic (2026-10-06 ~23:30): CLOSED by its rule

Rule (written in the plan before running): proceed to a window-aware Stage-1
change only if its mean absolute error is at most half the flat stand-in's.

`tools/break_proxy_diagnostic.py`, 88 saved engine weeks (33 older run folders
have no input snapshot and 2 other paths were not run folders; all listed in
`E1_BREAK_PROXY_DIAGNOSTIC.json`). Truth = calculate_metrics with the engine's
own breaks (0 unmatched break sets).

| stand-in | MAE (intervals) | mean signed error | rank correlation with truth |
|---|---|---|---|
| flat (Stage 1 today) | 25.0 | -24.4 | 0.82 |
| window-aware | 23.8 | -23.8 | 0.92 |

23.8 is not <= 12.5: no window-aware Stage-1 change. Per program the flat
stand-in under-predicts Chat by 76, GDI by 31, Voice by 21-25, AE IT by 1-14.

What it shows instead: any expected-presence stand-in is biased low, because
real breaks concentrate in a few quarters while an average shaves every
quarter, pushing near-threshold intervals below target. Across the 98 saved
runs the shipped schedule came from profiles that score coverage BEFORE breaks
about 63 times, and from profiles on the flat ("productive") basis about 7
times (restore_productive 4.6, aggregate_floor_binding 1.7,
floor_gate_hunter_productive 0.8, quality_convergence 0.3, daily_floor_balanced
0). This feeds Task 3's treatment (before-basis profiles first); it is not
itself a decision.
