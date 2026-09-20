# Overnight fact #1: 6 of 15 skeleton profiles have never executed, once

Mined from **48 candidate leaderboards** across every run in this session — the
budget sweep, worker test, deterministic A/Bs, corpus batch and memory probes.
No new machine time; this is existing evidence counted properly.

| # | catalog profile (in configured order) | ran | won | verdict |
|---|---|---|---|---|
| 1 | `target90_restore_champion` | 77 | **21** | WINNER |
| 2 | `target90_restore_productive` | 1 | 0 | ran, never won |
| 3 | `release_gate_floor_satisfaction` | 22 | **3** | WINNER |
| 4 | `target_floor_pareto_master` | 33 | **8** | WINNER |
| 5 | `floor_gate_hunter_before` | 16 | **1** | WINNER |
| 6 | `floor_gate_hunter_productive` | 10 | 0 | ran, never won |
| 7 | `aggregate_floor_binding` | 6 | 0 | ran, never won |
| 8 | `quality_convergence` | 2 | **1** | WINNER |
| 9 | `daily_floor_balanced` | **0** | 0 | **NEVER EXECUTED** |
| 10 | `break_safe_reserve` | 2 | 0 | ran, never won |
| 11 | `target_priority_balanced` | **0** | 0 | **NEVER EXECUTED** |
| 12 | `floor_protected` | **0** | 0 | **NEVER EXECUTED** |
| 13 | `coverage_rebalance` | **0** | 0 | **NEVER EXECUTED** |
| 14 | `before_target_champion` | **0** | 0 | **NEVER EXECUTED** |
| 15 | `protected_balance_polish` | **0** | 0 | **NEVER EXECUTED** |

**5 of 15 ever win. 4 run and never win. 6 have never run at all.**

## Two facts that follow, not opinions

**Efficiency.** Four profiles (positions 2, 6, 7, 10) consumed 19 executed
slices across the corpus and won nothing. At the measured 45s slice that is
roughly 855 seconds of solver time per full portfolio pass spent on candidates
that have never been selected.

**Quality.** The six that never execute occupy positions 9-15, so the portfolio
truncation always falls before them. Among them is **`before_target_champion`
at position 14** — and the Cricut Voice investigation measured that profile
reaching `before_target` **250 against the run's 247**. The single profile
known to close part of the Voice gap has never been executed in any run
recorded here.

## What this does NOT establish

**That reordering is the right fix.** `A34_END_TO_END_VERIFICATION.md` states
reordering "was written and then removed" and points to a rationale document
that is **not present in `evidence/`**. I could not read why it was rejected,
so I am not re-proposing it as though the objection never existed.

My own reading of the risk, stated as inference rather than fact: ranking the
portfolio by wins on this corpus overfits to these workbooks. A new client
roster could need precisely one of the profiles the ranking cut, and the
portfolio exists to be diverse rather than tuned. That is a real argument
against reordering and it is not answered by this table.

**That win rate equals value.** A profile can be valuable by producing the
candidate that another phase repairs into the winner, without ever being
`selected` itself. Nothing here measures that.

## The cheap next measurement

Run the six never-executed profiles directly, one at a time, on two or three
workbooks with a full slice — the same way `before_target_champion` was run
during the Voice work. That answers "are they worth their position" with
evidence instead of ordering theory, and it costs a handful of single-profile
solves rather than a portfolio change.
