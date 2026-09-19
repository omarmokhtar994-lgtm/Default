# Where the run time actually goes, and the two levers that move both dials

Measured 2026-09-19 from the four deterministic runs of 2026-09-18
(`--num-workers 1`, seed 9000, 300s budget) plus one cProfile run.

## 1. The budget is mostly not being spent on search

| case | budget | wall | overrun | CP-SAT attributable | unattributed |
|---|---|---|---|---|---|
| AE_AR_B2B | 300 | 332.0 | **+32.0** | 107.7 | 224.3 (68%) |
| AE_IT_B2B | 300 | 263.9 | -36.1 | 141.5 | 122.4 (46%) |
| AE_FR_B2B | 300 | 268.2 | -31.8 | 78.6 | 189.6 (71%) |
| AE_FR_Choice | 300 | 260.5 | -39.5 | 138.5 | 122.0 (47%) |

"CP-SAT attributable" sums the solve seconds the audit records per phase
(`hard_feasibility_probe`, `early_safe_incumbent`, `stage1_attempts`,
`stage2_attempts`, `joint_cp_sat_refinement`). **Unattributed is not proven
waste** — there may be solves the audit does not carry an `elapsed_sec` for.
What is certain is that it is not visible in the phase records, which is itself
a diagnostic gap.

**Ruled out as the cause,** by direct measurement:

* Excel I/O — 0.77s load + 0.46s save for a 54-sheet, 51,000-cell workbook;
  six output workbooks is about **7s**.
* Audit JSON — 4.68 MB, 128k nodes, 0.13s per serialize, 36 writes per run,
  about **5s**. (Compact instead of `indent=2` would make it 0.7s. Minor.)
* OR-Tools import — 7.8s, paid **once**; the runner spawns the inner scheduler
  exactly once per run.

Together about 20 of 300 seconds. The unattributed time is elsewhere.

## 2. The search plan is an order of magnitude larger than the budget executes

Every one of the four runs:

```
adaptive_search_v1   planned_task_count 28   attempted_task_count 0-1
stage1_profile_coverage_status  TRUNCATED_INSUFFICIENT_STAGE1_BUDGET
stage1_profiles_skipped_for_budget  15
```

15 of 15 Stage-1 profiles skipped at 300s, **after** B-3 lowered the slice floor
from 240s to 45s. B-3 fixed this at 900s; at 300s the Stage-1 window still does
not clear 45s.

At a 300s budget these phases are allocated **zero**: `conflict_refinement`,
`joint_refinement`, `coordinated_repair`, `exception_search`,
`post_break_repair`, `target_lock_recovery`.

Consequence: which single task of the 28 runs is decided by plan ordering, not
by expected value. That is a free quality lever — executing the best-k that fit
instead of the first-k costs nothing and cannot be worse.

## 3. Cold solves are still burning whole phases — the B-3 shape, possibly live

| case | 1st safe_incumbent | 2nd safe_incumbent | stage2 result |
|---|---|---|---|
| AE_AR_B2B | 20.0s FEASIBLE, **hints=0** | did not run | **UNKNOWN, 45.0s** |
| AE_FR_B2B | 20.0s FEASIBLE, **hints=0** | did not run | **UNKNOWN, 39.4s** |
| AE_IT_B2B | 23.2s FEASIBLE, hints=0 | 27.6s FEASIBLE, **hints=62** | FEASIBLE, 45.0s |
| AE_FR_Choice | 6.4s OPTIMAL, hints=0 | 40.4s FEASIBLE, **hints=68** | FEASIBLE, 45.0s |

The two cases whose warm-start chain did not produce a hinted second incumbent
are **exactly** the two whose Stage-2 returned UNKNOWN, burning 39-45 seconds
(13-15% of the budget) for no solution.

**This is a lead, not a finding.** n=4, and the correlation could equally be
driven by case difficulty — AR and FR_B2B may simply be harder. It is recorded
because it is the same shape as B-3, where cold-versus-warm moved the solve
cliff by an order of magnitude and was worth +8 target intervals.

`solve_breaks` does accept `hint_solution` and calls `AddHint` (lines
7337/7342), so the plumbing exists. `warm_start_hint_count` is **not recorded on
stage2_attempts**, so the audit cannot currently answer whether a given Stage-2
solve was hinted. Adding that field is the cheapest next step and settles it.

## 4. Model shape

`hard_feasibility_probe` on AE_AR_B2B: 8,732 variables, 67,628 constraints,
**268,928 branches against 52 conflicts**.

A branch-to-conflict ratio near 5,000:1 means the search is enumerating rather
than learning. That is consistent with weak bounding — and B-5 measured the
objective at a **400,000,000 : 1** dynamic range across 14 tiers, which degrades
CP-SAT's LP relaxation.

B-5 was evaluated for *coverage* impact and correctly closed as "no symptom".
**It was never evaluated for solve speed**, which is a different question with a
known mechanism. Cheap to test: rescale the coefficients, same model, same seed,
compare time-to-first-solution and the bound trajectory.

## 5. Priority

1. **Bound-based early exit.** `best_objective_bound` is already in the audit
   and nothing terminates on it. B-3 showed warm Stage-1 saturates at 30s to
   168/168 — the provable maximum — while being allocated 405s. Stopping at the
   ceiling shortens easy cases and leaves the budget to hard ones. This is the
   one change that improves both dials with no trade-off.
2. **Record `warm_start_hint_count` on stage2_attempts, then settle section 3.**
   One field, then one A/B.
3. **Rank the 28-task plan by expected value and execute top-k.** Free.
4. **Test B-5 for speed** (section 4). New question, known mechanism.

Not worth pursuing, already ruled out by measurement: symmetry breaking (CP-SAT
installs a 137x24 orbitope itself), Excel/JSON optimisation (~12s of 300),
objective restructuring for coverage priority (no symptom).
