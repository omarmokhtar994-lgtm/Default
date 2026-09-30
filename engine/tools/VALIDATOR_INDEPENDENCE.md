# How independent the independent validator is

`independent_validator.py` recomputes every coverage, break, rest, language,
overage and next-Sunday metric from the exported schedule cells. It does not
read the optimiser's audit values. It is **not** independent of the engine's
input parsing or of the rule definitions below. A defect in one of these would
be present in both the engine and the validator, and parity would not reveal it
(audit F-13).

## Shared engine surface (as of L6.3.2.8-RC6)

| Engine symbol | Used for |
|---|---|
| `parse_input` | the whole input contract: roster, shifts, demand, shrinkage, languages, instructions |
| `preference_kind` | classifying Preference/Fixed cells as leave / off / shift / blank |
| `rest_compatible`, `previous_saturday_compatible` | rest-gap rule, including carry-in from the previous Saturday |
| `shift_parts`, `hhmm`, `TOTAL_QSLOTS`, `LONG_SHIFT_MIN_DURATION_MIN` | shift arithmetic and quarter-slot indexing |
| `maximum_concurrent_breaks` | break concurrency cap |
| `opening_intervals_for_day` | opening-guard intervals |
| `language_rules_at`, `associate_language_windows`, `shift_within_language_window`, `shift_overlaps_required_language_for_noneligible` | language minima and language working windows |
| `language_reserve_status`, `language_operational_reserve_target` | language reserve tiers |
| `coverage_quality_limits`, `OVERAGE_CEIL_TOLERANCE` | overage caps |
| `next_sunday_interval_indices`, `next_sunday_interval_quarters`, `next_sunday_raw_cap`, `next_sunday_adjacent_raw_limit`, `whole_week_raw_cap`, `whole_week_adjacent_raw_limit` | next-Sunday and whole-week caps |

`canonical_metrics.py` is also shared. It renames metrics and does not compute them.

## What is checked without engine code

`independent_input_crosscheck` re-reads the raw workbook with openpyxl alone.
It compares the parsed contract with the raw workbook on the facts that every
metric depends on:

* **roster**: the set of associate names on the Schedule sheet equals the parsed roster;
* **demand**: hours per time bucket (at the coarser of the sheet's and the parse's
  granularity) equal those of at least one sheet with Sun–Sat columns and a time column;
* **preference / fixed** (when the workbook enables them), cell by cell:
  * a parsed value must have a non-blank workbook cell behind it;
  * a workbook cell reading leave / OFF / holiday / vacation / sick / PTO / LOA must
    not parse as blank (the B-11 failure mode).

A mismatch is a hard failure (`INPUT_CROSSCHECK_MISMATCH`). A layout the reader
cannot recognise is reported as a warning (`INPUT_CROSSCHECK_NOT_CHECKED`); it is
never counted as a pass.

Corpus result (50 workbooks: packaged inputs, fixtures, RC8 regression assets):
0 mismatches and 0 not-checked.

## Not yet independent

Shift catalog parsing, shrinkage, language rules, instructions and every rule
helper in the table above. Giving the validator its own contract parser is the
remaining step.
