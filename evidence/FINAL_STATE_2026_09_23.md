# Final state — what is closed, what is open, and what it costs

## Verified this session

| item | result | evidence |
|---|---|---|
| Are #49 (floor cap 0.05→0.03) and #38a (employee-quality validator) a regression? | **No.** Deterministic 1-worker rerun gives 166/165/168/167, byte-identical to the pre-change run. The earlier 4-worker −2 was portfolio nondeterminism. **Both kept, nothing reverted.** | `DETERM_AR` vs `VERIFY_JOINTOFF` |
| Is Stage-2's shortfall a bad objective or a starved search? | **Starved search.** Objective is monotone in coverage (164→1.96e9, 135→3.54e9, 131→3.91e9). | NIGHT_08, NIGHT_09 |
| Why does Stage-2 leave coverage on the table? | The adaptive break search **plans 168 attempts and runs 0** at the production QUICK budget. 15 of 22 runs at 1800s never run it at all. | NIGHT_09, `tools/stage2_attempt_census.py` |
| Gate | **PASS — 16 suites**, up from 9. Verified to exit 1 in both new failure modes. | `run_tests.sh` |

## The two things that were quietly wrong

1. **The engine work was not in the repo.** Everything measured all session
   lives in `L6.3.2.7-...-RC2`; the repo held `L6.3.2.6-...-RC1` from
   2026-09-08. Scratchpad dies with the container. Now preserved and pushed
   under `candidates/RC9_2_2_HARDENED_RC5/`.
2. **The gate passed over tests it never ran.** 7 suites in `tests_staged/`
   were outside the glob. Now wired in; running them exposed two stale pins
   that asserted already-fixed defects were still present.

## Open, with honest cost

| # | item | why it is not done | cost to close |
|---|---|---|---|
| 1 | **Merge `candidates/` into `engine/`** | The trees diverged. The candidate has 0 `coverage_split` references; the repo has 61. A copy would delete the A50–A54 Coverage Split work. 994 lines repo-only, 2082 candidate-only. | A deliberate 3-file merge + full corpus A/B. Not safe to rush: silent corruption of a scheduling engine is worse than delay. |
| 2 | **Fund Stage-2's break search at QUICK** | Reaching DEEP-quality needs ~540s of `break_search`; QUICK allocates 452s nominal and ~277s real. One recovered attempt is *not* automatically better — on Chat the first planned task scores 135, below the 159 that shipped; the +27 came from the second. | Budget-ladder change + per-workbook A/B, ~30 min per arm. |
| 3 | **`min_target_hits` vs `after_target` disagree** | Model uses `ceil_units(req*ratio)*qpi`; metric uses a percentage compare. A lock set to 159 reported 157. Used only by `target_lock_recovery`, which the census shows barely executes — not on the production path. | Reconcile the two definitions + regression test. |
| 4 | `language_reserve` validator (4/9 workbooks exposed) | Scoped, not built. | — |
| 5 | Non-monotonicity: more budget sometimes gives a worse result | Observed, not root-caused. | — |
| 6 | 6 skeleton strategies never executed | Unmeasured. | — |
| 7 | Joint refinement at DEEP (5400s reserve) | Untested. OFF at SMOKE/QUICK on measured evidence (69 attempts, 7 workbooks, 0 improvements). | — |

## Retracted this session, so it is not carried forward as fact

* The probe's printed `VERDICT: WEIGHTING DEFECT` — void. Neither arm proved
  optimality, and A's own answer was feasible for B. See NIGHT_08.
* NIGHT_06's "159 FEASIBLE" — proves a model-counter bound, not `after_target`.
  Its conclusion survives on independent evidence; the proof did not.

## Straight answer on readiness

The engine is **not** shippable-as-merged today. Item 1 is a real merge of two
diverged lineages and item 2 is an unvalidated budget change; both need
measurement runs, and doing either blind risks a silently worse scheduler.
What *is* true today: the hardened engine is preserved and pushed, the gate
genuinely tests it, the two applied fixes are proven inert, and the largest
quality defect is root-caused with a reproducible census.
