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

## Task 2 / F-E1: exact coverage units (pre-registered 2026-10-07 ~00:15, before any A/B run)

Change: switch "Exact Coverage Units" (default No). On: Stage 1
(`build_skeleton`: floor, hard floor, severe, target, full and tier hit
thresholds) and the aggregate guide use `coverage_hit_threshold_units` =
c x n*, the metric's own minimum head-quarters in the existing units. Stage 2
was already exact (audit F-1). Out of scope, recorded: next-Sunday horizon
terms, overage caps, `critical_exception_cells` (hard-floor mode).
Failing-first evidence: `E2_TESTS_BEFORE_FIX.txt` (14 errors: field and
function missing); after: 9/9 tests pass.

Design (revised before any run, because one seed per arm cannot see a
few-interval effect when Chat alone spreads 155-179 between runs):
* Correction (2026-10-07 ~04:35, still before any run): AE_AR_B2B and GDI
  have the same hit decisions either way, but their threshold numbers differ
  (672/672 and 527/624 comparisons), which changes deficit-term magnitudes, so
  their models are not identical. They are included in the A/B.
* A/B on all 7 ready-to-edit programs; control = switch absent, treatment =
  "Exact Coverage Units" = Yes (one row added to Engine Defaults; parser
  warnings identical in both arms); same engine file; production runner,
  QUICK 3,600 s, 2 workers; seeds 9000 and 9001 for both arms (28 runs),
  control and treatment of one program and seed side by side.

The default flips to Yes only if ALL hold:
1. every treatment run exit 0, validator PASS, 0 hard failures, no new refusal;
2. per program, the treatment's mean over the two seeds loses at most 1
   interval at target and at most 1 at floor (after breaks) versus control;
3. summed intervals at target after breaks over the 14 treatment runs >=
   the 14 control runs.
Otherwise the switch stays, default No, and the result is recorded.
