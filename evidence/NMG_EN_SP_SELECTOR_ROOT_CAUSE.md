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

**RESOLVED — this is not an engine defect.** I hypothesised a diagnostic-only
filter defect; the artifact refutes it. Stage-2 outcomes per skeleton:

| before_target | profile | Stage-2 outcome |
|---|---|---|
| 206 | `before_target_champion` | `SKIPPED_PROVEN_MINIMUM_EXCEPTION_POSITIVE` ×28 |
| 193 | `floor_gate_hunter_before` | INFEASIBLE ×19 |
| **192** | `release_gate_floor_satisfaction` | **FEASIBLE ×19** |
| 190 | `quality_convergence` | INFEASIBLE ×18 |
| 189 | `target_priority_balanced` | INFEASIBLE ×18 |
| 188 | `daily_floor_balanced` | INFEASIBLE ×18 |

The 206 skeleton has `minimum_exception_count = 1`, **proven**, against a
workbook policy of `max_no_break_exceptions = 0` and
`no_break_permission = False`. It provably cannot be broken without an
exception the contract forbids, so it can never ship. Every other strong
skeleton is break-INFEASIBLE. `release_gate_floor_satisfaction` at 192 is the
only Stage-1 skeleton that admits a feasible break solution at all.

**The 206 → 192 gap is a genuine breakability wall, not a lost candidate.** The
engine behaved correctly.

### Consequence — a reporting defect (A39)

`best_before_target` reported **206**, so `skeleton_retention_loss` read
**206 − 188 = 18**, and gate 4 FAILED partly on it. That is a loss against a
schedule that cannot exist. `select_best_before_skeleton` filters on
hard-clean and diagnostic-only but **not** on the exception cap.

Measured against the best *shippable* skeleton the retention loss is **4**
(192 → 188) — the selector defect below, and nothing more.

**Fixed.** `skeleton_exceeds_exception_cap` excludes only skeletons whose
minimum exception count is **proven** above the cap (an unproven bound may
still come down with more search, and discarding it would throw away a
candidate that is merely unmeasured). The engine emits
`best_shippable_before_target`, the gate measures retention against it and
names the basis in its detail, and artifacts predating the column still score
against the old basis with that basis stated.

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

**Loss 1: NOT A DEFECT** — a proven breakability wall. The engine was right.
**A39: CONFIRMED REPORTING DEFECT** — retention measured against an unshippable
skeleton, failing gate 4 for a reason that does not exist. Fixed and guarded.
**Loss 2: CONFIRMED DEFECT — selector.** Evidence is the shipped leaderboard.

No fix is proposed here. Changing `_candidate_quality_tuple` alters candidate
selection for every scenario, so it needs a controlled experiment across all
scenarios with a baseline, not a judgement call on one leaderboard.
