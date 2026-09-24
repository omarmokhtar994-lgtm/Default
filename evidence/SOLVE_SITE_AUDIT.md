# Solve-site audit: worker counts and warm starts (research report, recommendation 5)

A silent single-worker solve once cost 86 summed intervals (S2-PAR). This
checks every CP-SAT solve in the engine for the same class of defect.

## Worker counts

The engine has four `CpSolver()` sites (build_skeleton, solve_breaks and its
infeasibility-core re-solve, solve_joint_shift_off_language_break_refinement);
all four set `num_search_workers` explicitly. An AST scan of every call to
`build_skeleton`, `solve_breaks` and the joint refinement found two calls that
do not pass the configured workers, both deliberate:

* the `deterministic_target_baseline` Stage-1 profile (1 worker, documented as
  deterministic, recorded in the audit as `"workers": 1`);
* the `--selfcheck` 1-second CP-SAT smoke.

The single-worker core re-solve inside solve_breaks is the S2-PAR design
(assumptions force one worker; used only after an INFEASIBLE result).

## Warm starts

All hints set only the positive literals (chosen shift / pattern / OFF), so
they are partial hints; no hint parameter (repair_hint, hint_conflict_limit,
fix_variables_to_their_hinted_value) is set. CP-SAT treats a partial hint as
guidance, not as an incumbent, so a good warm start could in principle be lost.
Measured, re-solving the best candidate's skeleton with that candidate as
`hint_solution` (60 s, 2 workers):

| case | hint | re-solve |
|---|---|---|
| Cricut Chat (3600 s CURRENT seed 9000) | 175 / 227 | 175 / 227 |
| SYNTH_H1 (3600 s CURRENT seed 9000) | 141 / 168 | 141 / 168 |

The hinted solution is recovered in both. No defect found; nothing changed.
