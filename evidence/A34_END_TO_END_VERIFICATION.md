# A34 end-to-end verification — AE AR B2B at 2,700s

The slice-depth probe isolates `build_skeleton`. This is the whole pipeline:
one production run, same workbook, same budget, same seed and worker count as
the recorded Colab run, with the A34 budget fix in place.

```
engine/RUN_UNIVERSAL_PRODUCTION.py --input AE_AR_B2B.xlsx --mode DEEP
  --time-limit 2700 --num-workers 2 --solver-random-seed 9000 --overwrite
```

Input sha256 `b7dcbbffeb19e05f…` — the manifest hash, identical to the Colab run.
Wall clock 19:12:26 → 19:56:00 UTC, exit 0, inside budget.

## Budget allocation, before and after

| phase | recorded run | this run |
|---|---|---|
| `stage1_search` | 332 | **1,215** |
| `break_search` | 460 | 678 |
| `joint_refinement` | 840 | 363 |
| **Stage-1 profile window** | **150s** | **687.6s** |

## Stage-1 attempts

| profile | slice | status | before_target / before_floor |
|---|---|---|---|
| `target90_restore_champion` | 240.0s | FEASIBLE | **166 / 168** |
| `target90_restore_productive` | 240.0s | FEASIBLE | 156 / 168 |

The recorded run made twelve 45-second attempts and every one returned
`UNKNOWN` — no feasible skeleton at all.

## Result

| | recorded run | this run | RC9.1 |
|---|---|---|---|
| `before_target` / `before_floor` | 131 / 159 | **166 / 168** | 168 / 168 |
| `after_target` / `after_floor` | — | 156 / 168 | — (baseline is before-break only) |
| `status` | — | `PASS_WITH_QUALITY_WARNINGS` | — |
| `functional_status` | — | `PASS_FINAL_SCHEDULE_GENERATED` | — |
| `language_gaps` | — | 0 | 0 |

**+35 before-break target intervals and +9 floor, from the budget change alone.**
Nothing in the scheduling model, the constraints or the objective was touched.

## What this run does not show

**It is still a truncated search, and the report says so.** 2 of 15 profiles
attempted, stopped with 195s left against a 240s minimum. Gates 2 and 9 return
`NOT_COMPARABLE_SEARCH_TRUNCATED` — correctly, because a truncated search must
not be scored against RC9.1. A 2,700-second budget funds roughly two profiles at
honest depth; the DEEP design point of 14,400s funds the portfolio.

**The 168/168 profile did not run here.** `release_gate_floor_satisfaction`,
which reaches RC9.1's figure exactly at a 450s slice, sits at catalog position 3
and is in `skipped_profiles`. Reaching it needs the DEEP budget, not a
reordering — see A34 for why reordering was written and then removed.

**Gate 5 still fails: target loss 10/168 = 6.0% from break placement.** That is
the pre-existing breakability trade-off, untouched by A34 and still an open
policy decision.

**Gate 4 reports `PASS_PROTECTED_NOT_EVALUATED`** — no protected minimum is
configured, so the protected tier was never checked. Also an open decision.
