# Gate 7 — timeout recovery

Gate 7 has two halves. Resume was already proven; the timeout half had never
been executed. This closes it.

**Method.** Cricut Voice (264 active intervals, 100% target) run through
`RUN_UNIVERSAL_PRODUCTION.py` in DEEP mode at budgets far below the point where
the search can finish, on an otherwise idle 4-CPU container. The question is not
whether the schedule is good — it cannot be — but whether the engine stays
inside its wall clock, publishes valid artifacts, and tells the truth about what
it did.

| Budget | Wall clock | Overrun | Exit | Status reported | Stage-1 profiles |
|---|---|---|---|---|---|
| 90 s | 68 s | **−22 s** | 2 | — | — |
| 180 s | 140 s | **−40 s** | 0 | `FALLBACK_TO_QUICK` | 0 of 15 |
| 300 s | 272 s | **−28 s** | 0 | `PASS_WITH_QUALITY_WARNINGS` | 1 of 15 |

**Results.**

- **No overrun at any budget.** Every run finished inside its wall clock with
  22–40 s to spare. The engine does not blow through its own deadline.
- **Artifacts are complete.** Each run published both schedules
  (`BEST_BEFORE_BREAKS`, `BEST_FINAL_AFTER_BREAKS`), the candidate leaderboard,
  the Pareto manifest, the audit, the summary and the Phase C quality summary —
  18 artifacts at 300 s.
- **Independent validation passes on the published artifact.** 0 hard failures
  on `FINAL_AFTER_BREAKS`.
- **The status is truthful.** The 180 s run reported `FALLBACK_TO_QUICK` rather
  than a clean PASS, and `functional_status` stayed
  `PASS_FINAL_SCHEDULE_GENERATED` — a usable schedule, honestly labelled as
  having come from the fallback path.
- **The truncation is now visible.** These runs carry the new
  `stage1_profile_coverage` fields (A28): the 180 s run records
  `attempted=0, skipped_for_budget=15,
  status=TRUNCATED_INSUFFICIENT_STAGE1_BUDGET`. Before that change a run that
  explored none of its fifteen skeleton profiles was indistinguishable from one
  that explored all of them.

**Verdict: Gate 7 PASS on both halves.**

**One thing worth flagging, which is not a Gate 7 result.** Coverage is not
monotonic in budget on this scenario:

| Budget | before_target | after_target |
|---|---|---|
| 180 s | 244 | 224 |
| 300 s | 248 | **245** |
| 900 s | 242 | 240 |

The 300-second run beats the 900-second one. That is not what a search is
supposed to do, and it is tracked separately against the Cricut Voice
investigation rather than being read as a timeout-recovery finding.
