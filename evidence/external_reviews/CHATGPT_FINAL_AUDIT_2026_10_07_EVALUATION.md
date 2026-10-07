# Evaluation of ChatGPT's "Final Engine Audit Handoff" (7 Oct 2026)

Evaluator: Claude, with the receiving-code-review skill (verify against the
codebase before agreeing) and a Standard LLM council (5 separate advisors,
2 label-blinded reviewers). No code or package was changed for this review,
as the handoff asks. Separate from the Phase E work in `evidence/phase_e/`.

The audited engine (sha 9f91e56) differs from the repository engine only by
two default-off switches added since (mixed-length guide, exact coverage
units), so the findings apply to the current code.

## Finding-by-finding classification

| # | ChatGPT finding | Classification | Evidence (verified today) |
|---|---|---|---|
| 2.2 / P0-01 | Release gate returns success when a gate row FAILs | **Confirmed, correctly prioritized — but the fix is partly a policy decision** | `tools/release_gate_report.py` `main()` always returns 0; `rc921_runner.score_gates` returns that code as the run's exit status. The report prints gates 4, 5 and 8 but never combines them into a verdict; the "status" column is the engine's own summary status. So there is no notion of a mandatory release gate to "fail closed" on until the owner names which gates are mandatory. |
| 2.1 | F-37: hard-valid, quality FAIL, exit 0 | **Confirmed** | F-37 log: gate 5 FAIL (14 language-reserve quarters lost to breaks, 68/112 after target), gate 4 `PASS_PROTECTED_NOT_EVALUATED`, gate 8 PASS, status `PASS_WITH_QUALITY_WARNINGS`, `exit=0`. The engine's own quality gate (fail mode by default) passed with warnings, so no engine-level mandatory failure was hidden; the problem is labelling and missing release policy. |
| 2.4 / P0-03 | Sub-gates default to WARN; NOT_EVALUATED reads as a pass | **Confirmed** | `quality_gate_mode="fail"` and coverage split "hard", but break concurrency, language reserve, whole-week, target loss, floor loss, employee quality and skill allocation default to "warn". Gate 4's label literally starts with PASS while saying it was not evaluated. |
| 2.5 / P0-02 | Bundled gate evidence stale; shortfall test failed on Colab | **Stale evidence: confirmed. Test failure: requires an experiment** | Clean-extract evidence says 1,432 tests vs minimum 1,436 (today's repository gate: 1,461). The shortfall test asserts every zero-coverage shortfall after a 40 s, 2-worker solve is Sunday 03:xx; it passed twice here today on 4 cores. It encodes a search outcome under a time limit, so a slower machine can leave extra gaps. Needs a reproduction at Colab-like CPU before deciding between a regression and an over-specific test. The test is not to be edited to pass. |
| 2.3 / P1-01 | After-break search leaves coverage on the table; improve Stage-1 frontier and Stage-2 search | **Valid concern, severity and solution overstated for real programs** | Skeleton cap of 16 reached in 2 of 151 saved runs (not a binding limit). On Cricut Chat an independent model could not beat the engine's break placement on the same week while holding the floor (171 vs 176); 40 min of break-load feedback accepted nothing on Chat/Voice; joint refinement improved 0 of 474 audits; a better week before breaks (196 vs 191) still ended at 176. Holds for synthetic 24x7 H1 (17-82 intervals lost, budget-sensitive) and rich shift libraries (public benchmark 61-92% of optimum with 90-141 options). Real losses (Chat 13-22, AE IT B2B up to 22) are decided mostly by which week is chosen, not by break search. |
| 2.4 / P1-02 | Rank target before floor may choose a worse-floor schedule | **Valid concern, partly mitigated; business decision** | Within a run, selection caps floor traded for target at 1 interval. Across seeds, `RUN_PORTFOLIO.AFTER_KEY` ranks after_target then after_floor with no such guard. In 6 saved portfolios no winner gave up 3+ floor intervals for 1 target. Floor-vs-target order per program is Omar's call. |
| P1-03 | Distinguish proven infeasibility from exhausted search | **Partly in place, worth finishing** | Reports already call X1 a search-capacity limit, not infeasibility; statuses are not uniform across all outputs. |
| 10.1 | 20 paired seeds per comparison | **Unsupported as a default** | One production run = 1 h at 2 workers, 2 at a time: 20 paired seeds is ~20 h per A/B. Size runs from measured paired variance and the smallest effect worth detecting (the council's reviewers correctly noted the +0.3 seed-portfolio value is not a power estimate). Phase E uses cheap Stage-1 probes first; their own limits are recorded there. |
| 4.4 | 16 retained skeletons may be harmful | **Not supported** | Cap binds in 2 of 151 runs. |
| P2-03 | :30 starts as fallback | **Business decision** | Starts come from each workbook's shift library; real libraries start on the hour. |
| Scores | 60 / 35 / 48 / 35 | Opinion | Production-readiness concern is justified by the gate defect; optimization score ignores that AE AR is 167 vs a proven ceiling of 168. |
| 12 / backlog | No solver rewrite, no giant break model, no multi-week fairness now | **Agree** | Consistent with measured results. |

## Council verdict (Standard mode, complete)

Adopt the release-status fixes first, but split them: make the gate report
produce an explicit verdict and status (RELEASABLE / NOT_RELEASABLE /
NOT_EVALUATED) without changing any schedule, and let Omar decide which gates
and sub-gates are mandatory. Keep search and ranking changes behind cheap
pre-registered probes or owner decisions; reject the blanket 20-seed rule.
Confidence medium: the defect is verified in code, but sub-gate failure rates
and who consumes the exit code are not yet measured.

## Decisions that need Omar

1. Which release gates are mandatory (gate 4 protected tier, gate 5 break
   regression, gate 8 validation) and which engine sub-gates move from warn
   to fail, per program.
2. Floor versus target order, per program, including across seeds.
3. Whether :30 starts may be used as a marked fallback.
4. Who or what reads the runner's exit code and case status today.

## Recommended next steps (in order, no code until Omar approves 1)

1. Owner decisions above.
2. Replay the stored gate reports (no solves) to count, per program, how many
   runs would change releasability under the chosen policy.
3. Failing test first, then the verdict/exit-code/status change; full gate;
   clean-extract gate on the exact package; refresh the stale evidence.
4. Reproduce the shortfall test at Colab-like CPU; decide regression vs
   over-specific test with evidence, never by editing it to pass.
