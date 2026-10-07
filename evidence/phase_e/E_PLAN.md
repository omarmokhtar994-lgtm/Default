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

### Task 2 design replaced at the owner's request (2026-10-07 ~04:55, before any run)

The owner asked for fewer, shorter runs without losing quality. The switch only
changes Stage 1's (and the guide's) hit thresholds, so the direct effect is
measured on Stage 1 itself; the 28 production hours mostly measure Stage 2,
repairs and selection noise around it. Replaces the 28-run design above.

Stage A (probe, `tools/stage1_ab_probe.py`): the 7 ready-to-edit programs x the
two profiles that shipped most schedules in 98 saved runs
(target90_restore_champion, target_floor_pareto_master) x seeds 9000, 9001,
9002 x arms off/on = 84 Stage-1 solves at the production slice (45 s,
2 workers, production hard rules, the guide as production passes it, no hint),
two at a time (~35 min). Each week scored by calculate_metrics before breaks.
Pairs: (program, profile, seed).

Stage A passes only if ALL hold:
1. every "on" solve returns a week (OPTIMAL/FEASIBLE) wherever "off" does;
2. per program, the mean over its 6 pairs loses at most 1 interval at target
   and at most 1 at floor (before breaks);
3. summed before-target over the 42 "on" solves >= the 42 "off" solves.

Stage B (only if A passes): one production-runner pair per program for the 2
programs with the largest Stage-A gain (QUICK 3,600 s, 2 workers, seed 9000,
side by side, ~2 h); default flips to Yes only if neither loses more than 1
interval at target or floor after breaks, every run exit 0, validator PASS,
0 hard failures. If A fails: switch stays, default No, no production runs.
Limitation stated now: Stage A measures weeks before breaks; Stage B is the
check on what ships.

## Task 3 / F-E2: Stage-1 time on the profiles that ship (pre-registered 2026-10-07 ~05:05, before any run)

Question: does giving the most-shipped profile more of the Stage-1 budget
produce better weeks? (98 saved runs: target90_restore_champion shipped 42.2,
target_floor_pareto_master 12.7; most others ~0-5, several never ran.)

Stage A (probe, `tools/stage1_ab_probe.py` with a time arm): the 7 programs x
seeds 9000, 9001, 9002, target90_restore_champion at 45 s (today's slice) vs
135 s (the time of the two lowest-yield profiles that usually run, added to
it), 2 workers, production hard rules and guide, no hint; scored by
calculate_metrics before breaks. ~32 min.

Stage A passes only if: per program, the 135 s mean loses nothing at target or
floor versus 45 s, AND the summed before-target over the 21 pairs gains at
least 7 (one interval per program on average). Otherwise: record that more
time on the champion does not pay, and close F-E2 without production runs.
Stage B (only if A passes): one production pair per program for the 2
programs with the largest gain, today's profile list vs the list with
target90_restore_champion first and the two lowest-yield profiles that
usually run dropped (QUICK 3,600 s, 2 workers, seed 9000); adopt only if
neither loses more than 1 interval at target or floor after breaks, every run
exit 0, validator PASS, 0 hard failures.

### Task 2 Stage A verdict (2026-10-07 ~05:50): FAIL; switch stays, default No; no Stage B

Data: `E2_STAGE_A_PROBE.json` (84 solves). Rule 1 failed: on Cricut Chat
(target_floor_pareto_master, seeds 9000 and 9002) the off arm returned a week
and the on arm returned UNKNOWN at 45 s. Rules 2 and 3 held on the 21 pairs
with a week in both arms (sum 3,842 on vs 3,806 off; per-program mean
dTarget: GDI +6.67, Voice +1.33, NMG EN+SP +1.33, NMG SP 0; no program below
-1). Per the rule: no production runs; recorded as not adopted.

Probe fidelity, stated with the result (not used to re-score it): only 21 of
42 pairs were usable. NMG EN was INFEASIBLE in both arms under the probe's
hard configuration (production reaches a schedule through its fallback
passes); AE_AR_B2B, Chat (restore_champion) and GDI (restore_champion) found
no week in 45 s from a cold start (production hints later profiles from
earlier ones). A probe without production's warm start and fallback is not a
faithful Stage-1 stand-in for those programs. The positive signal on the
usable pairs is an observation, not evidence for adoption; any re-test needs a
new pre-registration with a fixed probe, written before it runs.

Consequence for Task 3: its pre-registered probe has the same cold-start bias
and would favour the longer slice simply by finding a first week; it is not run
as written. Its design is revised (below) before any run.
