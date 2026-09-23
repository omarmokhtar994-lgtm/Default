# Which skeleton strategies actually run?

Recorded as an open item ("the 6 never-executed skeleton strategies, measured
directly"). Measured.

## Declared vs requested vs executed

| | count |
|---|---|
| profiles declared by `skeleton_profiles()` | **17** |
| requested by the runner's `--skeleton-profiles` list | **15** |
| distinct profiles that actually ran across the controlled `C_*` sweep (6 runs, 4 workers, 1800s and 3600s) | **12** |

**Never requested at all (2):**

* `preference_neighborhood`
* `target_100_wins`

These are declared in the engine and omitted from the runner's default list, so
no production run can reach them. They are dead by configuration, not by budget.

**Requested but never executed in any of the 6 runs (3):**

* `before_target_champion`
* `coverage_rebalance`
* `protected_balance_polish`

These sit at the tail of the requested order. Stage-1 stops when the window
cannot fund another profile, so the tail is what gets dropped -- the same
budget boundary B-3 measured, seen from the other end.

## What this corrects

The open item said "six never-executed strategies". The real figure splits into
**two that are unreachable by configuration** and **three that lose to the
Stage-1 budget on this corpus** -- five, not six, and they fail for two
different reasons needing two different answers.

## Why neither is fixed here

* The two unrequested profiles are a one-line configuration change, but adding
  a profile to the default list lengthens the Stage-1 queue, and B-3 already
  shows the tail does not get funded. Adding profiles at the tail would be
  adding profiles that never run.
* The three starved profiles would be reached by funding Stage-1 more or by
  reordering, and reordering changes which skeleton wins. Either is a
  quality-affecting change that needs the per-workbook A/B this session has
  not run.

## Scope

6 controlled runs, one engine build, 4 workers, 1800s and 3600s. One run per
cell, so a profile counted as "executed" ran at least once, not reliably.
