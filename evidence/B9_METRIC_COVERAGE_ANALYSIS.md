# B-9: the sixteen decision-driving metrics, checked one by one

What this file answers: for each metric that drives a decision and has no
independent check, is the **engine's own computation** sound, can the validator
derive it **from workbook cells**, and what should be built first. Done ahead of
the AE sweep so the fixing can start the moment it lands.

Method is the one that found B-8: compare what the metric measures against what
the solver actually constrains, and look for a basis, granularity or scope
mismatch. A metric that reports on a rule at a different granularity from the
rule's enforcement is a check of something else wearing the right name.

---

## Findings

### 1. `hard_floor_gap_count` — basis divergence, not exploitable

Decides hard validity through `skeleton_hard_clean`.

| | |
|---|---|
| metric | `after_pct + 1e-9 < parsed.hard_floor_ratio`, where `after_pct = (after_sum / qpi) / req` |
| solver | `model.Add(eff >= ceil_units(req * hard_floor_ratio) * qpi)` |

The solver **ceils** the per-interval requirement to whole units; the metric
compares raw ratios. `ceil(req·r) >= req·r` always, so **the metric is
systematically weaker than the constraint** — a schedule can satisfy the metric
while falling short of what the solver would have enforced.

It is not exploitable today: the only two places that relax `hard_floor` are
`run_constraint_isolation` and the conflict-refinement core search, both
diagnostic paths whose solutions are never release candidates. Every candidate
path builds with `base_hard = HardConfig(hard_floor=(floor_mode == "hard"))`.

**Verdict: not a defect. Worth an independent check anyway** — it is the
hard-validity predicate, and a validator that recomputes `after_pct` from
workbook cells would catch an error in the engine's own coverage arithmetic,
which nothing currently would.

### 2. `week_boundary_hard_failure_count` — double-counts, harmlessly

Also decides hard validity. It is a sum of five categories:

```
floor gaps + zero-staffed quarters + language gaps + opening gaps + blank-staffed
```

These **overlap**: one quarter can be simultaneously zero-staffed, a language
gap and an opening gap, and is then counted three times. So the number is not a
count of failing quarters and should not be read as one.

Because every consumer tests `== 0`, over-counting can only ever cause a false
**failure**, never a false pass. That is the safe direction.

**Verdict: a reporting defect, not a safety one.** Fix by counting distinct
quarters, or rename to make the basis explicit. **The validator already
computes all five components** (`next_floor_gaps`, `next_zero`, `next_language`,
`next_opening`, `next_blank`) — an independent check is nearly free.

### 3. `week_boundary_max_adjacent_raw_change` — the B-8 sibling

Comes from `boundary_adjacent_rows`, the **same loop** whose violation count was
B-8. The engine side is quarter-granular and matches the solver. The count is
now independently checked; **this max is not**.

**Verdict: engine correct, coverage absent.** Near-free to add — the
quarter-granular sequence built for the B-8 fix already exists in the
validator; this is `max(delta)` over the same pairs.

### 4. `whole_week_max_adjacent_raw_change` — clean

The current-week analogue. Checked specifically for a B-8 repeat and it is
**not** one: the loop is `for qslot in range(d*96, (d+1)*96 - 1)`, quarter
granular, matching the solver's constraint.

**Verdict: engine correct.** Independent check is moderate work — the validator
computes per-quarter raw staffing for next Sunday but not for the current week.

### 5. `target_losses_from_breaks` — the one to build first

```python
target_losses_from_breaks += int(before_pct + 1e-9 >= parsed.target_ratio
                                 and after_pct + 1e-9 < parsed.target_ratio)
```

A per-interval count from `before_pct` and `after_pct` — **both already
computed by the validator**. Gates the release via
`quality_max_target_losses_from_breaks`, and ranks candidates via
`break_solution_key`.

It is also the B-4 quantity: the number that read **3 on one run and 2 on a
byte-identical repeat**. Nothing independently confirms either.

**Verdict: engine computation correct; highest-value, lowest-cost gap in the
list. Build this first.**

### 6. `before_severe_floor_gap_count` — free

The mirror of `severe_floor_gap_count` (which **is** checked, as
`severe_floor_gaps`) computed on `before_pct` instead of `after_pct`, against
the same `severe_threshold`.

**Verdict: engine correct.** The validator already computes the after-side; the
before-side is the same line with a different input.

### 7. `week_boundary_max_coverage_ratio` — easy

`max(after_pct)` over the boundary rows. The validator already builds
`next_rows` carrying `pct`.

**Verdict: engine correct, cheap to check.**

### 8–12. The language group — moderate, and self-consistent

`language_rule_quarters`, `language_minimum_only_quarters`,
`language_minimum_only_ratio`, `language_reserve_shortfall_quarters`,
`language_break_caused_reserve_loss_quarters`, plus the two
`week_boundary_language_*`.

All derive from `language_quarter_rows`, one row per **rule × quarter**. Note
the basis: a quarter with two active rules contributes two rows, so
`language_rule_quarters` counts rule-quarters, not quarters. The name says so,
and the ratio uses the same denominator, so it is self-consistent.

**Verdict: engine correct.** Independent checking is moderate: the validator
detects language *gaps* but not the reserve/minimum-only *status*, which needs
`language_operational_reserve_target` semantics recomputed from the workbook.

### 13–14. `skill_allocation_gap_quarters`, `employee_quality` — hard

Derived from structured audit objects built by dedicated engine routines.

**Verdict: no evidence of a defect, but genuine independent derivation means
reimplementing non-trivial engine logic.**

### 15. `transferable_overstaffing_pair_count` — do not fake it

Counts interval pairs where staffing could move from a surplus to a deficit. An
independent check means reimplementing the pairing heuristic.

**Verdict: the highest risk of a fake check in the list.** Copying the engine's
implementation into the validator would produce a parity field that can never
disagree — worse than leaving it uncovered, because it looks covered. If it is
not genuinely re-derivable, say so and leave it out.

---

## Build order

| # | metric | cost | why |
|---|---|---|---|
| 1 | `target_losses_from_breaks` | trivial | gates release, ranks candidates, is the B-4 quantity, inputs already present |
| 2 | `before_severe_floor_gap_count` | trivial | after-side already checked; same line, different input |
| 3 | `week_boundary_hard_failure_count` | near-free | all five components already computed |
| 4 | `week_boundary_max_adjacent_raw_change` | near-free | B-8's quarter sequence already built |
| 5 | `week_boundary_max_coverage_ratio` | easy | `next_rows` already carries `pct` |
| 6 | `hard_floor_gap_count` | easy | hard-validity predicate |
| 7 | `whole_week_max_adjacent_raw_change` | moderate | needs current-week per-quarter raw |
| 8–12 | the language group | moderate | needs reserve-target semantics |
| 13–15 | skill / employee / transferable | hard | **may be honest to exclude** |

Items 1–6 close the two hard-validity metrics, the release-gating loss cap and
the B-8 sibling for very little code.

## Two fixes that are not about coverage

* **`week_boundary_hard_failure_count` double-counts** overlapping categories.
  Safe direction, but it is not the count it appears to be.
* **`hard_floor_gap_count` is weaker than the constraint it reports on.** Not
  reachable today; it becomes reachable the moment any candidate path is built
  with `hard_floor=False`.

## What is not claimed

* **No metric was found returning a wrong value.** The analysis is static:
  basis, granularity and scope against the constraint each metric reports on.
  The one real granularity bug of this kind, B-8, was in the *validator*.
* **Coverage is not the goal; genuine independence is.** A check that
  reimplements the engine cannot fail. B-8 was detectable only because the two
  sides were written independently and drifted.
