# B-8: the independent validator was checking a weaker rule under the same name

What this file answers: how a metric-parity failure on a clean schedule turned
out to be a defect in the checker rather than in the schedule, and why fixing
it makes validation stricter rather than weaker.

## 1. How it surfaced

`AE_AR_B2B`, `FULL_SCHEDULE`, 900s. The run produced a valid schedule and then
failed its release gate:

```
rc 4 | FAIL_METRIC_PARITY | 1 mismatch
{"field": "week_boundary_imbalance_violation_count",
 "engine": 1, "validator": 0, "reason": "VALUE_MISMATCH"}
```

Stage detection agreed (`FULL_SCHEDULE` both sides), the surface was published,
and **40 of the 41 canonical fields matched exactly**. One field disagreed, and
it disagreed on both runs of the A/B pair — so it was reproducible and not a
symptom of the change being tested.

## 2. The two implementations were not measuring the same thing

The **solver** penalises next-Sunday adjacency between neighbouring *quarter
slots*:

```python
ordered_boundary = sorted(next_sunday_raw_sequence_vars, key=lambda row: row[0])
for (previous_qslot, ...), (current_qslot, ...) in zip(ordered_boundary, ordered_boundary[1:]):
    if current_qslot != previous_qslot + 1:
        continue
    adjacent_limit = next_sunday_adjacent_raw_limit(parsed, previous_interval, current_interval)
```

The **engine metric** measures exactly that — same iteration, same guard.

The **independent validator** compared adjacent *intervals*, using each
interval's maximum:

```python
for previous, current in zip(next_rows, next_rows[1:]):
    delta = abs(int(current.get('after_raw_max', 0)) - int(previous.get('after_raw_max', 0)))
```

On a 60-minute workbook — which `AE_AR_B2B` is — that is **a quarter of the
adjacent pairs**, and an interval maximum cannot see a staffing cliff *inside*
the hour. The validator was not independently confirming the rule the engine
enforces; it was confirming a weaker rule that happens to share its name.

This is the failure mode the canonical metric surface exists to prevent, one
level deeper than naming: the names matched, the *measurements* did not.

## 3. The fix

The validator already computed the per-quarter `after_raw` values — it kept
only `max(after_vals)` and discarded the sequence. It now records the sequence
against its quarter-slot index and walks adjacent quarters with the same guard
the solver uses, enumerating the protected horizon through
`next_sunday_interval_quarters(parsed)`.

**It still computes every raw count itself, from workbook cells.** Sharing
*which* quarters are protected is contract; sharing the measurement would make
the parity gate compare the engine to itself. Pinned by
`test_the_validator_still_computes_the_raw_counts_itself`.

This makes the validator **stricter** — it can now see violations it previously
could not — which is the correct direction for a release checker that was
under-reporting.

## 4. Verification

Both AE_AR_B2B artifacts re-validated with the fixed checker:

| artifact | engine | validator before | validator after | status |
|---|---|---|---|---|
| `B3_ARB2B_BASE` | 1 | 0 | **1** | PASS, 0 hard failures |
| `B3_ARB2B_S30` | 1 | 0 | **1** | PASS, 0 hard failures |

The validator found the violation on its own and agrees. The parity failure
resolves because the disagreement is gone, not because the check was relaxed.

No false positives introduced — four further artifacts across two workbooks and
both stages:

| artifact | engine | validator |
|---|---|---|
| `B1_FULL` (AE_FR_Choice, full) | 0 | 0 |
| `B3_SLICE30` (AE_FR_Choice, full) | 0 | 0 |
| `B1_BEFORE3` (AE_FR_Choice, skeleton) | 0 | 0 |
| `B7_CTRL` (AE_FR_Choice, skeleton) | 0 | 0 |

Six artifacts, six agreements.

## 5. What this says about the earlier AE results

The six recorded AE runs in the comparison package were validated with the
under-reporting checker. Any next-Sunday adjacency violation in those schedules
would have gone unreported. That does not invalidate their coverage numbers —
this metric is a balance-quality measure, not a coverage one — but a clean
`next_sunday_imbalance_violation_count` in that package is weaker evidence than
it appears.

## 6. Tests

`NextSundayAdjacencyIsMeasuredWhereItIsEnforced` — 6 tests:

* the solver constrains adjacent quarter slots (read from the model)
* the engine metric measures what the solver penalises
* the validator walks quarter slots, not intervals
* the validator no longer uses an interval maximum for imbalance
* the validator still computes its own raw counts
* both sides agree on a real artifact **that has a non-zero count** — a checker
  that under-reports is invisible on a schedule with no violations, so the
  regression test uses the case that caught it

Full gate: **16 suites, 588 tests, PASS.**
