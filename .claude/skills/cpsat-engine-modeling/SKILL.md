---
name: cpsat-engine-modeling
description: Use when changing, diagnosing or benchmarking any OR-Tools CP-SAT model in this repository - the scheduler's Stage-1 skeleton, Stage-2 break solve, joint/repair solves, or the independent exact/reference models in tools/ - and whenever a solve is slow, returns UNKNOWN, ignores its hint, or scores below a known optimum.
---

# CP-SAT modeling for the scheduling engine

Distilled from *The CP-SAT Primer* by Dominik Krupke (CC-BY-4.0,
https://github.com/d-krupke/cpsat-primer, commit ca62954), applied to this
engine. Project rules in `CLAUDE.md` outrank everything here: no speculative
behaviour change, every engine change needs a pre-registered A/B rule or a
measured configuration, a failing test first, and protected baselines stay
untouched.

## Facts about this engine (verify before relying on them)

- OR-Tools 9.15; engine `engine/_tools/l632_universal_scheduler.py`;
  production QUICK = 3,600 s, 2 workers, seed 9000.
- **Workers decide which subsolvers run.** Per the primer's table (OR-Tools
  9.9): 1 worker = only `default_lp`, no LNS; 2+ workers add the incomplete
  subsolvers (LNS, feasibility jump). Confirm on 9.15 from a replay log before
  quoting it. Either way a 1-worker result is not evidence about the 2-worker
  production search.
- **Assumptions force a single worker.** `break_infeasibility_core_enabled`
  attaches assumption literals; S2-PAR solves a clone with them fixed on all
  workers and extracts the core only on INFEASIBLE (NIGHT_14 section 10).
- The engine sets hints (`AddHint`) in ~19 places and never checks that a hint
  survives presolve (`keep_all_feasible_solutions_in_presolve`,
  `fix_variables_to_their_hinted_value` are unused). A solve that "returns its
  hint unchanged" is a candidate for a lost hint, not proof of one.

## Diagnose before changing anything

1. Reproduce the exact solve (same model, hint, seed, workers, time). Export
   the model if needed (`model.ExportToFile`) so it can be replayed alone.
2. Turn on `log_search_progress` in the replay, not in production. Read:
   presolve reductions, time to first solution, which subsolvers found the
   improving solutions, final gap. Model-building time shows up here too.
3. Status is evidence of different strength: `OPTIMAL` proves; `FEASIBLE` has a
   bound (`BestObjectiveBound`); `UNKNOWN` proves nothing either way and is
   never reported as infeasible. A bound is a bound of *the model*, not of the
   business problem.
4. Hint questions get a deterministic check: solve once with
   `fix_variables_to_their_hinted_value = True`. INFEASIBLE means the hint is
   wrong or incomplete; FEASIBLE with the plain solve not using it points at
   presolve. Only then A/B `keep_all_feasible_solutions_in_presolve`.
5. Separate "cannot find it" from "does not value it": score a known-good plan
   with the engine's own metric (`calculate_metrics`) and objective. If the
   objective ranks it below what the engine shipped, it is an objective problem,
   and no amount of search time fixes it.

## Modeling rules that have paid off here

- **Aggregate identical entities.** Interchangeable associates create symmetry
  the solver must refute one copy at a time. Counting tour patterns instead of
  assigning workers turned 180 s UNKNOWN into sub-second proofs
  (`tools/public_shift_design_suite.py`, `tour_patterns`). Exact when no rule
  links individuals (break choices per person-day are independent).
- Tight domains over big-M; reification (`OnlyEnforceIf`) over bespoke
  linearisations; enumerate legal patterns up front when the set is small
  (break patterns, tours) instead of encoding the rules inside the solve.
- Never warm-restart by adding the previous objective value as a hard bound:
  it weakens the LP relaxation. Fix a stage's objective only as the
  lexicographic contract requires, and hint the previous solution.
- Large problems: domain-aware LNS (destroy part of the week, re-solve with the
  rest fixed and hinted) beats generic parameters. The engine already has
  day-neighbourhood break search; prefer extending such structure-aware
  neighbourhoods over parameter tinkering.
- Leave decision strategies and subsolver lists at their defaults unless an A/B
  says otherwise; most "tuning" hurts.

## Independent references (how optima are proven here)

- Exact reference models are written from the problem statement, with **no
  engine code** (`tools/benchmark_exact.py`, `tools/public_shift_design_suite.py
  reference`). A reference is either OPTIMAL/INFEASIBLE or it is reported as
  unknown; never guessed.
- The independent validator (`engine/tools/independent_validator.py`) is the
  solver-agnostic oracle: every published schedule must pass it, and
  engine/validator parity is checked field by field.

## Benchmarking and A/B

- Fixed seed, fixed workers, fixed budget, same machine load for both arms;
  pre-register the decision rule before running (see `evidence/production_readiness_audit/phase_c/*_RULE.txt`).
- Report per-instance tables, not only sums: improvements on some instances
  usually cost others (no-free-lunch); state the losses.
- Distinguish exploratory runs (learning) from workhorse runs (the evidence a
  decision rests on). Only workhorse runs go into a decision.
- Time-limited runs: say what a timeout means for each instance, never drop
  timed-out instances silently.

## Testing optimization code

- Validator first, solver second: feasibility and objective checks that do not
  depend on CP-SAT, with precise error messages.
- Regression cases from production inputs (golden replays) with tolerant
  performance checks; CP-SAT timing varies run to run.
- Property-based tests (see the property-based-testing skill) fit naturally:
  "for any valid instance, the published schedule passes the validator" and
  "engine metric == independent recomputation" are oracle properties. Adding
  Hypothesis as a dependency is the owner's decision.
