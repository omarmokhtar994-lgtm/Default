# Joint refinement and its endgame: removed from every default path

Decision (user, 2026-09-26): remove joint refinement if it adds nothing,
unless something different turns up. Measured before removing:

| scope | result |
|---|---|
| 474 solver audits on record (every run in this repository and scratch areas: QUICK sweeps, A/Bs, corpus runs, DEEP runs) | `improved` = 0 in every audit |
| the 28 audits with `accepted` = 1 | all are `ANCHOR_REPLAY_FEASIBLE`: the phase re-derived the schedule it started from (see JOINT_REFINEMENT_NEVER_IMPROVES.md) |
| DEEP, measured for the first time (seeds-vs-time A/B): NMG_SP, Voice (17 attempts each), M2 x2 (1 each) | 36 attempts: 34 UNKNOWN (no solution in time), 2 INFEASIBLE; accepted 0, improved 0 |
| DEEP Chat and H1 | killed by the kernel at 13.0 and 13.9 GB inside the phase (DEEP_MODE_OOM.md) |
| "Something different": the no-release-candidate endgame, which reopens the same joint search | ran in 9 runs (AE_IT_Choice x6, NMG_EN_AND_SP, X1, a Voice variant): EXHAUSTED every time, 0 candidates added |

Nothing different turned up, so both are off by default:

* `RUN_UNIVERSAL_PRODUCTION.py`: `joint_enabled: False` at SMOKE, QUICK, DEEP
  and OVERNIGHT; the budget plan gives the joint reserve to the other phases
  (at 14,400 s: joint 0, more Stage-1 and break search). `--enable-joint-refinement`
  turns it back on.
* Engine: `FINAL_RECOVERY_ENDGAME_ENABLED = False`; a run with no release
  candidate records `DISABLED_NO_MEASURED_VALUE` and finalizes. Engine and
  runner flag `--enable-final-recovery-endgame` turns it back on.
* The code stays (behind those flags, with the memory isolation shipped in
  8506631) so a future workbook can still try it; it no longer runs unless
  asked.

Effect on the default paths: none on scores. QUICK already had it off; DEEP and
OVERNIGHT now run as seed portfolios of QUICK runs (evidence/seed_portfolio_ab),
which never ran it. Only a `--single-run` DEEP/OVERNIGHT changes: its 5,400 /
8,400 s joint reserve now goes to Stage 1 and break search. That path was not
A/B-tested after the change.
