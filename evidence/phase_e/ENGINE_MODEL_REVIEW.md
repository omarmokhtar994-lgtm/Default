# Engine model review: equations, relationships, search (2026-10-06)

Method: cpsat-engine-modeling skill (diagnose before changing; separate "cannot
find" from "does not value"; never re-propose what was measured dead). Sources:
engine `engine/_tools/l632_universal_scheduler.py` (26,192 lines), the Chat
C4 run audit, 98 saved production-runner audits in the session scratchpad,
earlier decision records under `evidence/`. No engine change was made.

## How the engine decides (as built)

1. Stage 1 (week): one Boolean per associate x day x shift; weighted-sum
   objective (`build_skeleton`, ~40 term families: target / floor / severe /
   full hits, deficits, overage tiers, reserves, preferences, variety, quality
   gaps). Coverage per interval = sum over its quarters of heads x
   round((1 - shrinkage) x 100); a "hit" is coverage >= ceil(req x ratio x 100)
   x quarters. Most profiles count each shift at a flat 8/9 presence
   (`productive_coeff`) as a stand-in for breaks.
2. Stage 2 (breaks): pattern choice per working day, same 100-scale units.
3. Around them: a 15-profile portfolio (each profile a different weight set),
   ~12 repair / recovery phases, a global time budget, and selection rules
   that protect the floor (max 1 floor interval traded for target).
4. The published metric (`calculate_metrics`) is exact: mean over the
   interval's quarters of on-floor heads x (1 - shrinkage) >= ratio x req.

## Findings

### F-E1 (defect, small): three models round coverage differently from the metric

Stage 1, Stage 2, the aggregate guide and the shortfall pass use percent units
(shrinkage rounded to 1%, requirement rounded up to 0.01 FTE per interval);
only the joint refinement uses exact thresholds (`scaled_coverage_threshold`,
scale 1,000,000). Measured on the 7 real programs, over every active interval
and both target and floor thresholds: the minimum head-quarters for a hit
differs from the metric's on

| program | Stage 1 thinks it is a hit when the metric says miss | Stage 1 demands one more than needed |
|---|---|---|
| Cricut Chat | 5 | 3 |
| Cricut Voice | 3 | 4 |
| NMG EN | 0 | 5 |
| NMG SP | 0 | 5 |
| NMG EN+SP | 0 | 4 |
| AE_AR_B2B, GDI | 0 | 0 |

Example: Chat Monday 17:30, 10 FTE, shrinkage 9.23%: metric needs 23
head-quarters, Stage 1 accepts 22 (91 x 22 = 2,002 >= 2,000). Effect bound: at
most these intervals, only when coverage sits exactly at the threshold. Fix:
exact thresholds everywhere (the joint stage's function already exists).
Cost low; correctness gain; expected score effect 0 to a few intervals.

### F-E2 (search budget): the Stage-1 portfolio spends most of its time on profiles that rarely ship

Chat C4: 9 of 15 requested profiles ran, 45 s each, all stopped FEASIBLE
(none proven); before-target ranged 163-191 across profiles. Across 98 saved
runs, the shipped schedule came from (fractional when tied):
target90_restore_champion 42.2, target_floor_pareto_master 12.7,
hard_feasibility_probe 6.5, repairs ~17, everything else <= 4.6 each; several
profiles almost never (quality_convergence 0.3, daily_floor_balanced 0,
coverage_rebalance 0) and 6-7 profiles are routinely cut by the deadline
(e.g. coverage_rebalance never ran in 72 of 80 runs). Profile order decides
which ones get time. Candidate (measured-configuration A/B, not a code
fix): order by historical yield and give the top 2-3 longer slices; keep the
rest as diversity only if the A/B shows they earn their time.

### F-E3 (largest real-program loss): break loss is decided by the week, and Stage 1's break stand-in is coarse

Before vs after breaks on saved runs: Chat 13-22 intervals, AE IT B2B 22,
AE IT 6-16, GDI 6-7, NMG SP 4-5, Voice 2-4, AE AR 0-2; synthetic H1 17-82.
Break placement itself is near its best on Chat: a model with the floor held
could not beat the engine's breaks on the same week (171 vs 176, Phase D), and
40 minutes of break-load feedback accepted nothing on Chat or Voice
(`evidence/feedback_loop/LONG_RUN_POLISH_DECISION.md`). A better week before
breaks did not survive breaks either (Phase D: 196 before -> 176 after).
So the lever is Stage 1 choosing weeks that lose less to breaks. Stage 1
charges every shift a flat 8/9 presence in every quarter, although breaks can
only fall inside each shift's break windows (100% presence outside them).
Next step (offline, no engine change): on saved weeks, compare how well the
flat stand-in and a window-aware stand-in (presence per offset = share of
legal patterns not on break there) predict the actual after-break metric. Only
if the window-aware one predicts clearly better: pre-register, failing test,
A/B.

### F-E4 (hypothesis, needs a replay log): objective scale

Stage-1 objectives reach ~1.7 x 10^11 (Chat C4) from weights spanning about
seven orders of magnitude. Wide coefficient ranges can weaken the LP bound and
LNS acceptance. Not a finding until a replayed solve with
`log_search_progress` shows it (presolve/LP stats, which subsolvers improve).

## Measured before and not re-proposed

Break-load feedback (540 s and 40 min), day-neighbourhood break search, joint
refinement (0 improvements in 474 audits), long-run polish, more seeds
(~+0.3 expected), the Phase-D starting week on real programs (176 vs 177).

## Outside the engine (input levers, owner's decision)

Break rules (30% concurrency cap with small night teams, break windows) and
the shift library (1-24 options, 60-minute starts) shape the break loss and the
coverage ceiling more than any search change measured so far. These can be
quantified per program on request (what-if runs), not changed silently.
