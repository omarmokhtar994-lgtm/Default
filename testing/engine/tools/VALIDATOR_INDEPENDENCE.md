# How independent the independent validator is

`independent_validator.py` recomputes every coverage, break, rest, language,
overage and next-Sunday metric from the exported schedule cells. It does not
read the optimiser's audit values. It reads the input through the engine's
`parse_input`. Every fact that parse produces and a metric or hard rule depends on
is then compared with an openpyxl-only re-reading of the workbook (below), so a
misread input is a hard failure. What it shares with the engine is the rule
definitions listed next (audit F-13).

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

`independent_input_crosscheck` re-reads the raw workbook with openpyxl alone. It
compares the parsed contract with the raw workbook on every input fact a metric or
a hard rule depends on:

| check | compared |
|---|---|
| `roster` | the set of associate names on the Schedule sheet |
| `roster_language` | each associate's Language on the Schedule sheet |
| `demand` | hours per time bucket, at the coarser of the sheet's and the parse's granularity, against at least one sheet with Sun–Sat columns and a time column |
| `shrinkage` | every interval's ratio against a shrinkage sheet at the run's interval |
| `shifts` | every shift the engine may assign exists on a shift sheet with the same start and length |
| `request_switches` | Use Preferences, Fixed Request Use, Leave, Hard OFF, Strict 2 OFF (Instructions over Engine Defaults; last row wins) |
| `contract_numbers` | Target, Minimum Per Interval (floor) and the rest gap |
| `preference`, `fixed` | cell by cell, when enabled: a parsed value needs a non-blank cell; a leave/OFF cell must not parse as blank (B-11) |
| `language_hours` | Language Setup Coverage Start/End per language and day (Coverage Days, Active, Minimum) |
| `language_window_mode` | the Language Working Window row; a run override (`--language-working-window`) is applied instead and reported as such |

A mismatch is a hard failure (`INPUT_CROSSCHECK_MISMATCH`). A layout or value the
reader cannot interpret is reported as a warning (`INPUT_CROSSCHECK_NOT_CHECKED`)
and never counted as a pass.

Corpus result, 2026-10-03: 70 workbooks (packaged inputs, fixtures and the RC8
regression assets) gave 0 mismatches. One check was not run: shrinkage on
`SYNTH_R5_SHRINKAGE_100`, whose 100% shrinkage the input contract refuses anyway.

## What remains shared, by design

The validator still takes the rule **definitions** from the engine: the rest-gap
arithmetic, break concurrency cap, opening guard, overage caps, the next-Sunday and
whole-week caps, the language-reserve tiers, and the start-only window rule. These
are the contract's semantics, not readings of the workbook. A second implementation
would be a second opinion on what the rule means rather than a check that the
workbook was read correctly. Every input those rules consume is now checked above.
