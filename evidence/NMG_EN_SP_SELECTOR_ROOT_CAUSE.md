# NMG EN+SP — why a strong skeleton became a weak final schedule

Answers the "candidate X vs candidate Y" question against the run-2 artifact
(engine `fb96de0e…`, commit 8a568ba, 14400s).

## Reconciliation first

Every RC9.1 baseline figure supplied in the review prompt was checked against
`evidence/RC9_1_BASELINE.json`: **24 of 24 CONFIRMED**, exact match including
`before_avoidable_overage_fte_sum` 1103.08 / 122.47 / 180.39 / 178.45 and the
NMG EN gap counts (33 severe, 14 max consecutive).

Every RC9.2.1 NMG EN+SP figure supplied was checked against the run artifact:
**CONFIRMED** — 138/188/221/225 before, 102/153/175/203 after, 49 floor gaps,
28 severe, max consecutive 7, floor deficit 8.546, 18 break-concurrency
violations, 13 language-reserve quarters, 14 extreme-overage intervals.

*Correction to my own first pass:* I briefly reported several of these as
CONTRADICTED. That was my error — my script matched an arbitrary Stage-2
attempt instead of the shipped candidate. The two sources agree.

## The loss happens twice, for two different reasons

Stage 1 found, by before-break target:

| before_target | profile |
|---|---|
| **206** | `before_target_champion` |
| 205 | `target90_restore_champion` |
| 196 | `target_floor_pareto_master` |
| 196 | `protected_balance_polish` |
| 193 | `floor_gate_hunter_before` |
| 192 | `release_gate_floor_satisfaction` |

The shipped schedule has before_target **188**. So 18 intervals are lost, and
the summary's own `best_before_target` field records exactly that: **206**.

### Loss 1 — 206 → 192: the five best skeletons never reach the leaderboard

The Stage-2 candidate leaderboard's highest `before90` is **192**
(`release_gate_floor_satisfaction`). The 206, 205, 196, 196 and 193 skeletons
appear nowhere on it. Fourteen intervals are lost before break search is even
scored.

`successful_skeletons` *is* sorted by `skeleton_quality_key` immediately before
Stage 2, so this is not a plain ordering bug. Two candidate explanations remain,
**not yet distinguished**:

* `skeleton_quality_key` opens with `diagnostic_rank`, and
  `production_break_skeletons` then filters out anything
  `skeleton_release_diagnostic_only`. A strong skeleton flagged diagnostic-only
  would be excluded from break search entirely regardless of its coverage.
* The top skeletons may have been carried in and produced no compliant break
  solution.

Distinguishing these is the next step; it decides whether this is a filter
defect or a genuine breakability wall.

### Loss 2 — 192 → 188: the selector chose the weaker candidate

Both were on the leaderboard. The winner is row 1; row 3 is
`release_gate_floor_satisfaction`.

| metric | **winner (shipped)** | row 3 | winner is |
|---|---|---|---|
| before90 | 188 | **192** | −4 worse |
| before80 | 221 | **225** | −4 worse |
| before_floor | 225 | **239** | **−14 worse** |
| after90 | **153** | 150 | **+3 better** |
| after80 | 175 | **177** | −2 worse |
| after_floor | 203 | **212** | **−9 worse** |
| avoidable overage FTE | 29.96 | **22.07** | **+7.89 worse** |
| extreme-overage intervals | 14 | **9** | **+5 worse** |

**The winner beats the alternative on exactly one metric — after90, by three
intervals — and loses on seven.** Among them nine after-break floor intervals,
five extreme-overage intervals and 7.89 FTE of avoidable overage.

For a 90% contract `after_target` *is* `after90`, and it is the dominant
lexicographic term in `_candidate_quality_tuple`. It is overwhelming floor,
overage and tier breadth rather than being traded against them.

This is not a search-budget artifact. The search was fully funded: 7 of 7
objective modes, 121 adaptive attempts, zero UNKNOWN, `break_search` 5694s.
Both candidates were found. **The ranking picked the worse one.**

## Why this matters operationally

Row 3 is the better production schedule on any reasonable operational reading:
nine more floor-covered intervals after breaks, five fewer extreme-overage
intervals, and 26% less avoidable overage — for three fewer intervals at the
90% tier.

## Status

**CONFIRMED DEFECT — selector.** Evidence is the shipped leaderboard.
Loss 1's mechanism is **UNVERIFIED** pending the diagnostic-only check.

No fix is proposed here. Changing `_candidate_quality_tuple` alters candidate
selection for every scenario, so it needs a controlled experiment across all
scenarios with a baseline, not a judgement call on one leaderboard.
