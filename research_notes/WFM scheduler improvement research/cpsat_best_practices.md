# CP-SAT (OR-Tools 9.x, target 9.15) best practices for large rostering / scheduling models under a fixed time budget

Method note: most findings come from **primary sources read directly**. These are the OR-Tools `v9.15` tag source files (`sat_parameters.proto`, `cp_model_solver.cc`, `cp_model_search.cc`, `cp_model_lns.h`, `cp_model_solver_helpers.cc`, `linear_relaxation.cc`, `python/cp_model.py`, `docs/troubleshooting.md`) and the CP-SAT Primer repository (d-krupke/cpsat-primer, `main` branch, which states it is updated for 9.15). Line numbers refer to the v9.15 tag. The egress proxy blocked some sources: the Perron & Didier "CP-SAT-LP Solver" CP 2023 paper (dagstuhl.de), the CP 2024 generic-LNS paper, the Perron scheduling-seminar slides, arXiv, and solvermax.com. Claims from those appear only as search-result snippets and are labelled as such. "Code fact" means it was read in the v9.15 source. "Anecdotal" means advice from practitioners or the Primer author that was not measured.

Base URLs used below:
- Proto: https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto
- Solver: https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc
- Search/portfolio: https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_search.cc
- LNS: https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_lns.h
- Helpers: https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver_helpers.cc
- LP relaxation: https://github.com/google/or-tools/blob/v9.15/ortools/sat/linear_relaxation.cc
- Primer parameters chapter: https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md

---

## Q1. Large Neighborhood Search, workers, interleaving and subsolver customization

### Takeaway
In 9.15, LNS and the other "incomplete" heuristics run as small **interleaved** tasks that share the threads left over once the full-search workers have theirs. They run only when the parallel code path is taken: `num_workers > 1`, **or** `interleave_search=true`, **or** a non-empty `subsolvers` / `filter_subsolvers`, **or** `use_ls_only`. With `num_workers=1` and default settings you get a single sequential CDCL+LP search with no LNS. With 2 to 4 workers, exactly one thread is shared by all LNS, feasibility-jump and RINS tasks. For a 15 to 60 minute budget on a large roster, where solution quality matters more than the bound, this LNS thread share is the main lever.

### Cited Findings
**When the parallel/LNS path is used (code fact)**
- The solver calls `SolveCpModelParallel` only if `num_workers() > 1 || interleave_search() || !subsolvers().empty() || !filter_subsolvers().empty() || use_ls_only()`. Otherwise it runs the sequential single-worker search. — [cp_model_solver.cc L3038-3041](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L3038)
- With `interleave_search=true` and `num_workers==1`, the code forces one thread for first-solution heuristics so that "we at least have a feasibility_jump subsolver". The interleaved batch size defaults to `1` when num_workers==1 and to `num_workers*3` otherwise. — [cp_model_solver.cc L2150 and L824-836](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L824)
- The Primer's table (measured on 9.9) says: "With a single worker, only the default subsolver is used. With two workers or more, CP-SAT starts using incomplete subsolvers, i.e., heuristics such as LNS. With five workers, CP-SAT will also have a first solution subsolver." — [Primer, parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- The official troubleshooting doc takes a more conservative line: "[8 workers] This is the minimum number of workers needed to trigger parallel search… a quick_restart subsolver, a feasibility_jump first solution subsolver, and dedicated Large Neighborhood Search subsolvers". 16 workers add continuous probing, more first-solution subsolvers, two dual (lower-bound) subsolvers and more LNS. 24 workers add more. 32+ workers add mainly LNS and first-solution workers. — [docs/troubleshooting.md](https://github.com/google/or-tools/blob/v9.15/ortools/sat/docs/troubleshooting.md). *This conflicts with the Primer and with the code, which do run LNS at 2 workers. The doc probably means the full portfolio design needs about 8 workers. Treat "8" as a recommendation, not a hard threshold.*

**How threads are split between full and interleaved workers in 9.15 (code fact)**
- If `num_full_subsolvers` is 0, the number of full-thread workers is: 1 when num_workers=1; `n-1` when n≤4; `n-2` when n≤8; `n-(n/4+1)` when n≤16; else `n-(n/2-3)`. The remaining threads run all interleaved subsolvers (LNS, feasibility jump / violation LS, feasibility pump, RINS/RENS, shaving). — [cp_model_search.cc L1000-1016](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_search.cc#L1000)
  - n=2 gives 1 full worker + 1 interleaved thread. n=4 gives 3 + 1. n=8 gives 6 + 2. n=16 gives 11 + 5.
- The default order of full workers, truncated to the count above, is: `default_lp, fixed, core, no_lp, max_lp (or max_lp_sym if symmetry was detected), quick_restart, reduced_costs, quick_restart_no_lp, pseudo_costs, lb_tree_search, probing, objective_lb_search, objective_shaving_no_lp, objective_shaving_max_lp, probing_max_lp, …`. Entries given in `extra_subsolvers` are put at the front. — [cp_model_search.cc L861-891](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_search.cc#L861)
- Some entries are skipped when they do not apply: `fixed` needs a decision strategy (or scheduling); `pseudo_costs` and `reduced_costs` need an objective; "Core based search will only work if the objective has many terms". — [proto `subsolvers` comment L723-742](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L723)

**LNS neighborhoods that exist in 9.15 (code fact)**
- LNS workers are registered only when `use_lns` is true (default) **and the model has an objective with at least one variable**. — [cp_model_solver.cc L1898-1900](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1898)
- Generic neighborhoods, from the `cp_model_lns.h` class comments:
  - `rnd_var_lns` and `rnd_cst_lns`: relax random variables, or random constraints.
  - `graph_var_lns`: BFS in the variable–constraint graph from a random variable.
  - `graph_arc_lns`: grows a working set by one directly connected variable at a time.
  - `graph_cst_lns`: picks random constraints that share variables with those already chosen and relaxes their variables.
  - `graph_dec_lns`: a decomposition neighborhood "inspired by… a tree decomposition of the constraint-variable graph".
  - `lb_relax_lns`: solves a local-branching LP and relaxes the variables that differ most. It is based on Huang et al. 2023 and is created only when `num_workers >= lb_relax_num_workers_threshold` (**default 16**), so it is off at 2, 4 or 8 workers.
  - Sources: [cp_model_lns.h L575-641](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_lns.h#L575); [cp_model_solver.cc L1902-1945](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1902); [proto L1516](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1516)
- `rins/rens` (on by default through `use_rins_lns=true`): fixes variables to values taken from LP solutions or incomplete solutions. It follows RINS (Danna et al. 2004/2005) and RENS (Berthold 2009). — [cp_model_lns.h L855-870](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_lns.h#L855); [proto L1505](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1505)
- Scheduling-specific neighborhoods, created only when the model contains interval / no_overlap / cumulative constraints:
  - `scheduling_intervals_lns`: relaxes random intervals and adds precedences among the rest.
  - `scheduling_time_window_lns`: relaxes the intervals inside a random time window.
  - `scheduling_resource_windows_lns`: relaxes one window per resource.
  - `scheduling_precedences_lns`.
  - There are also packing (`packing_*_lns`) and routing (`routing_*_lns`) variants.
  - Sources: [cp_model_lns.h L681-726](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_lns.h#L681); [cp_model_solver.cc L1953-2043](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1953)
- Other interleaved subsolvers:
  - `feasibility_pump` (`use_feasibility_pump=true`).
  - Feasibility jump local search (`use_feasibility_jump=true`, Luteberget & Sartor 2023).
  - `violation_ls` workers (`num_violation_ls`, default 0 meaning automatic).
  - Variable shaving, which switches on automatically at `num_workers/20` levels, i.e. from 20 workers.
  - Sources: [proto L1292-1340, L1508](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1292); [cp_model_solver.cc L1848-1878](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1848)

**How LNS works internally (code fact)**
- Neighborhood choice uses a UCB1 multi-armed bandit over the generators. A generator called fewer than 10 times gets score infinity so that it is explored. — [cp_model_lns.h L462-470](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_lns.h#L462)
- Each generator has an adaptive "difficulty" in [0,1], the fraction of the problem relaxed, "dynamically adjusted depending on whether or not we can solve the subproblem in a given time limit". The starting values are `lns_initial_difficulty=0.5` and `lns_initial_deterministic_limit=0.1`. — [cp_model_lns.h L444-449](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_lns.h#L444); [proto L1479-1480](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1479)
- Parameters used to solve LNS sub-problems:
  - Presolve on.
  - SAT inprocessing off, `cp_model_probing_level=0`, **`symmetry_level=0`**.
  - `solution_pool_size=1`.
  - The `lns_base` variant uses `linearization_level=0` with AUTOMATIC_SEARCH.
  - The `lns_stalling` variant uses PORTFOLIO_SEARCH with `search_random_variable_pool_size=5`.
  - You can override these by adding a `subsolver_params` entry named `"lns"`.
  - Source: [cp_model_search.cc L770-811](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_search.cc#L770)
- Handling of each LNS fragment:
  - The fragment is hinted with the base solution.
  - `RestrictObjectiveUsingHint` adds `objective <= hint objective`.
  - The model's symmetry information is cleared from the fragment.
  - After more than 10 consecutive non-improving calls, the hint is dropped with probability 0.5 "to diversify our solution pool".
  - If a neighborhood relaxes no objective variable, it is regenerated rather than solved. It is solved only when stalling, to find diversity.
  - Source: [cp_model_solver.cc L1458-1505](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1458)
- LNS base solutions come from a pool of the top-n solutions: `solution_pool_size` defaults to 3, "mainly impact the 'base' solution chosen for a LNS/LS fragment". `alternative_pool_size` defaults to 1. — [proto L1491-1502](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1491)
- `diversify_lns_params` (default false) "registers more lns subsolvers with different parameters". — [proto L1543](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1543)

**Customizing the portfolio (documented)**
- `subsolvers`: the full list of full workers, in order; only the first `num_full_subsolvers` are scheduled.
- `extra_subsolvers`: "added at the beginning of the list".
- `ignore_subsolvers` and `filter_subsolvers`: glob patterns that "work on LNS or LS names even if these are currently not specified via the subsolvers field".
- `num_full_subsolvers`: overrides the full/interleaved split.
- Source: [proto L715-758](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L715)
- `use_lns_only` ("Experimental… disable everything but lns"; the Primer notes it needs a time limit) and `use_ls_only` ("turns CP-SAT into a pure local-search solver"). — [proto L1296, L1486](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1486); [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- Custom subsolver recipe from the Primer: build a `SatParameters` with a `name`, append it to `subsolver_params`, and add the name to `extra_subsolvers`. Do not change top-level parameters, because those also reach the LNS workers and can "slow them down to the point of being ineffective". Reusing an existing name overrides only the fields you set. — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- Per-subsolver log analysis: the `Solutions` and `Objective bounds` tables show which workers found the incumbents. Set `log_subsolver_statistics=true` for more detail. — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md); [proto L411](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L411)
- Anecdotal: "decreasing the number of search workers can actually improve the runtime for some problems"; matching workers to physical cores (not hyperthreads) may help because of clock frequency and memory bandwidth. — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- Snippet only (paper not fetched): Perron & Didier say the diverse portfolio "increased the robustness of the solver, while the continuous sharing of information between workers has produced massive speedups when running multiple workers in parallel". — [The CP-SAT-LP Solver, CP 2023 (LIPIcs)](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2023.3)

### Inferences
- **At 2 to 4 cores** the default gives one thread to all LNS, feasibility-jump and pump work, which is 25 to 50% of the CPU. With 4 workers and an objective that qualifies for `core`, the full workers are probably `default_lp, core, no_lp`, so **no `max_lp` worker**. Check the log line "N full problem subsolvers: [...]". For a hard roster where improvement comes from LNS, try `num_full_subsolvers=1` or `2` with `num_workers=4`, which leaves 2 to 3 threads for interleaved LNS. Another option is `ignore_subsolvers=["core","lb_tree_search","objective_*","probing*"]` to stop bound-focused workers taking threads. These are levers to benchmark, not documented recommendations.
- For a quality-under-time-limit goal, `num_workers=1` is almost always wrong. If you need exactly one thread, set `interleave_search=true` so that LNS and feasibility jump still run, interleaved deterministically.
- `lb_relax_lns` is disabled below 16 workers. You can force it with `lb_relax_num_workers_threshold` set to a lower value (untested suggestion).
- A time-indexed roster built from Booleans, with no interval variables, gets only the generic neighborhoods (random, graph, RINS). The scheduling time-window neighborhoods need interval constraints. A custom LNS outside CP-SAT (fix most employees or days and re-solve with a hint) is the standard way to add domain structure. The Primer's LNS chapter argues this: CP-SAT "has no way of knowing the structure of your problem". — [Primer lns.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/lns.md)

### Gaps
- No published measurements (paper or blog) of solution quality against worker count at 2, 4, 8 or 16 workers for rostering models. The CP 2023 paper and the CP 2024 "Investigation of Generic Approaches to LNS" paper (which compares generic neighborhoods) could not be fetched because egress was blocked.
- I did not verify whether the `core` worker is actually chosen for a typical weighted roster objective; that depends on the model.

---

## Q2. Solution hints and warm starts

### Takeaway
A **complete and feasible** hint (every non-fixed variable, auxiliaries included) goes straight into the solution pool as an incumbent. LNS can therefore start improving it immediately, and all workers get an objective cutoff. A **partial** hint only steers each full worker's first chunk through a brief `HINT_SEARCH` capped at `hint_conflict_limit=10` conflicts, which often fails on large models. Complete your hints: solve once with `fix_variables_to_their_hinted_value=True` and copy back every variable's value.

### Cited Findings
- Before presolve, `SolutionHintIsCompleteAndFeasible` checks the hint. If the hint covers all non-fixed variables, stays within domains, satisfies all constraints and does not break assumptions, it is added as a solution right away: `manager->NewSolution(solution, "complete_hint", …)`. Otherwise the log says "The solution hint is incomplete: X out of Y non fixed variables hinted" or "complete, but it is infeasible! we will try to repair it". — [cp_model_solver.cc L909-1015, L2640-2644](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L909)
- Each full worker's first chunk runs a "hint search". With `repair_hint=false` (default) this is `QuickSolveWithHint`: `max_number_of_conflicts = hint_conflict_limit` and `search_branching = HINT_SEARCH`. With `repair_hint=true` it is `MinimizeL1DistanceWithHint`, which adds penalties for moving away from the hinted values. — [cp_model_solver.cc L1143-1152](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1143); [helpers L1870-2003](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver_helpers.cc#L1870)
- The quick hint phase is skipped when `optimize_with_core` is on (the core worker). — [helpers L1884-1889](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver_helpers.cc#L1884)
- Proto definitions:
  - `hint_conflict_limit` (default 10): "Conflict limit used in the phase that exploit the solution hint".
  - `repair_hint` (default false): "tries to repair the solution given in the hint… If false, then we do a FIXED_SEARCH using the hint until the hint_conflict_limit is reached".
  - `fix_variables_to_their_hinted_value` (default false).
  - `debug_crash_on_bad_hint` (default false): "Crash if we do not manage to complete the hint into a full solution".
  - `use_optimization_hints` (default true).
  - Source: [proto L869, L885, L1197-1207](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1197)
- The Primer's advice:
  - Only completed hints can be used to prune. If CP-SAT takes long to complete a hint, "it may have wasted a lot of time in branches it could otherwise have pruned". Its `complete_hint()` helper solves with `fix_variables_to_their_hinted_value=True` and re-hints every proto variable (also available as `cpsat-utils.complete_hint`).
  - `debug_crash_on_bad_hint` is "unreliable: it only triggers in multi-worker mode, depends on a race condition… controlled by hint_conflict_limit (default: 10)". Use `fix_variables_to_their_hinted_value` to check hint feasibility deterministically.
  - Source: [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- Presolve and hints (Primer, anecdotal): presolve reductions such as symmetry breaking can make a hint infeasible, "CP-SAT has historically struggled to preserve the feasibility of hints through presolve… I am still encountering this behavior in recent releases". The workaround is `keep_all_feasible_solutions_in_presolve=True`, which may slow the solver. — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md); [proto L1435](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1435)
- "In older versions of CP-SAT, hints could sometimes visibly slow down the solver, even if they were correct but not optimal… seems resolved in the latest versions" (anecdotal). — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- Hints inside LNS: each LNS fragment is hinted with its base solution and restricted to objective ≤ that solution's objective (see Q1). — [cp_model_solver.cc L1467-1505](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1467)
- Python API: `add_hint(var, value)` appends to `solution_hint` (negated literals are handled). `clear_hints()` empties it. Hints are part of the proto, so they survive `clone()`. — [python/cp_model.py L1650-1666](https://github.com/google/or-tools/blob/v9.15/ortools/sat/python/cp_model.py#L1650)
- Some forum users raise `hint_conflict_limit` to values such as 75000 (search-result snippet; the thread was not read). — [or-tools-discuss](https://groups.google.com/g/or-tools-discuss/c/AI6oGqyhx5Q)

### Inferences
- For a WFM solver that warm-starts from last week's roster or a greedy heuristic, do the following:
  1. Hint **every** decision variable **and every auxiliary**: indicator, deficit and objective-component variables.
  2. Confirm "complete_hint" in the log, or check it programmatically with a `fix_variables_to_their_hinted_value` solve limited to a few seconds.
  3. If only part of the solution is known, either complete it with that short fixed solve, or raise `hint_conflict_limit` (for example 1,000 to 100,000) so that `HINT_SEARCH` can finish.
- A hint that violates manual symmetry-breaking constraints is infeasible, so it degrades to steering only. Permute the hinted employee schedules so that they satisfy your lexicographic ordering (see Q4).

### Gaps
- No quantitative benchmark was found of complete versus partial hints on large rostering instances.
- I did not verify whether 9.15's presolve keeps complete hints feasible in all reductions. The Primer reports it still sometimes does not.

---

## Q3. Assumptions, parallelism, `clone()` and `clear_assumptions()`

### Takeaway
For optimization models, and for any multi-worker solve, CP-SAT does not really support assumptions: it **treats them as fixed literals**, and if the result is INFEASIBLE it returns all of them as the core. Assumptions also disable shared-tree workers. Use them only as a cheap way to fix Booleans temporarily (for example "what if employee X is off on day D"). Use `model.clone()` for real scenario copies.

### Cited Findings
- When assumptions are present and `num_workers > 1 || has_objective || enumerate_all_solutions || interleave_search`, the solver logs "Warning: solving with assumptions was requested in a non-fully supported setting. We will assumes these assumptions true while solving…". It clears them from the proto, sets each literal to true in presolve, and on INFEASIBLE reports all assumptions as `sufficient_assumptions_for_infeasibility`. — [cp_model_solver.cc L2712-2745](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L2712)
- Shared-tree workers are created only when `model_proto.assumptions().empty()`. — [cp_model_solver.cc L1814-1815](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1814)
- A complete hint that contradicts the assumptions is rejected as an incumbent ("breaks the assumptions of the model"). — [cp_model_solver.cc L968-985](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L968)
- Python API:
  - `add_assumption`, `add_assumptions` and `clear_assumptions()` (which empties `model_proto.assumptions`).
  - `clone()` copies the proto into a new `CpModel` and rebuilds the constant map.
  - Source: [python/cp_model.py L1476-1481, L1668-1679](https://github.com/google/or-tools/blob/v9.15/ortools/sat/python/cp_model.py#L1476)
- CP-SAT "is stateless and always starts from scratch": unlike incremental SAT solvers, it keeps no learned clauses between solves. Assumptions are Boolean literals only. Unsat cores are useful for debugging with pure feasibility models. — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)

### Inferences
- For multi-worker optimization, assumptions add nothing over `model.add(lit == 1)` on a clone, apart from convenience. They do not reduce parallelism, except for shared-tree workers (off by default at low worker counts). For infeasibility diagnosis, run a separate single-worker feasibility solve (no objective, `num_workers=1`) with assumptions on the enforcement literals.

### Gaps
- None material.

---

## Q4. Symmetry handling and manual breaking for interchangeable employees

### Takeaway
CP-SAT detects symmetry automatically (`symmetry_level=2` by default: presolve plus dynamic breaking during search). It adds a `max_lp_sym` worker when symmetry is found. LNS sub-solves turn symmetry off. Manual lexicographic ordering of identical employees helps proofs but can hurt the parallel search and hint feasibility. Evidence here is thin.

### Cited Findings
- `symmetry_level` (default 2): "at level 1 we detect them in presolve and try to fix Booleans. At level 2, we also do some form of dynamic symmetry breaking during search. At level 3, we also detect symmetries for very large models, which can be slow. At level 4, we try to break as much symmetry as possible in presolve." Related parameters are `symmetry_detection_deterministic_time_limit` and the experimental `keep_symmetry_in_presolve` (default false). — [proto L1615-1631](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1615)
- If the model has symmetry, the portfolio uses `max_lp_sym` in place of `max_lp`. — [cp_model_search.cc L875-881](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_search.cc#L875)
- LNS workers run with `symmetry_level=0`. LNS fragments call `clear_symmetry()`: "we don't want to use the symmetry of the main problem in the LNS presolved problem". — [cp_model_search.cc L777](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_search.cc#L777); [cp_model_solver.cc L1460-1465](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L1460)
- The log reports detected symmetry, e.g. "[Symmetry] #generators: 2…", "Found orbitope of size 6 x 2". — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- Symmetry breaking in presolve can make hints infeasible (Primer warning, see Q2). — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- Snippet only (paper not fetched): in a CP-SAT workforce-allocation study, "In multi-worker settings, symmetry and redundant constraints have a clear negative effect on both model initialization and solving time. However, in single-worker mode, symmetry constraints help prove optimality for more instances". — [arXiv 2412.10272, "Trustworthy and Explainable Decision-Making for Workforce allocation"](https://arxiv.org/pdf/2412.10272)
- Anecdotal (Primer, decision strategies): a manual search strategy for graph coloring "only gave an advantage for a bad model and after improving the model by symmetry breaking, it performed worse". — [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)

### Inferences
- For identical employees (same contract, skills and availability), the practical choice is between two options:
  - **Let CP-SAT detect the symmetry.** Check the `[Symmetry]` log lines. If detection times out on large models, consider `symmetry_level=3` or a larger `symmetry_detection_deterministic_time_limit`.
  - **Add a weak manual ordering**, such as total hours of associate i ≥ associate i+1 inside each identical class. This is weaker and more LNS-friendly than a full lexicographic order on the whole schedule vectors.
- Full lex-leader constraints restrict LNS: after relaxing a random subset, the ordering can force changes elsewhere. They also make any hint that does not already satisfy the ordering infeasible.
- Symmetry breaking mostly helps **proving** (the bound), which matters little under a quality-focused time budget. Benchmark both options, with and without manual breaking, using several seeds (Q7).

### Gaps
- I found no official Google guidance on manual symmetry breaking and its interaction with LNS.
- The 2412.10272 finding comes from a search snippet only, and its setup (version, worker count) was not verified.

---

## Q5. Modeling threshold/coverage objectives: reified indicators versus deficit variables, LP strength, presolve parameters

### Takeaway
**Code fact, and important for "interval meets target" indicators:** constraints with `OnlyEnforceIf` are added to the LP relaxation **only when `linearization_level >= 2`**, that is only in `max_lp` style workers. In `default_lp` (level 1), `no_lp` and all LNS sub-solves (level 0), a constraint such as `sum(staff[t]) >= target[t]).OnlyEnforceIf(hit[t])` is invisible to the LP. An objective that maximizes `sum(hit)` therefore gets essentially no LP guidance. A non-reified formulation with an integer shortfall or deficit variable (`deficit[t] >= target[t] - sum(staff[t])`, `deficit >= 0`, penalize `deficit`) enters the LP at the default level 1 and gives much stronger bounds and reduced-cost / RINS guidance.

### Cited Findings
- `LinearizeEnforcedConstraints(model)` returns `linearization_level() > 1`. `AppendLinearConstraintRelaxation` adds an enforced constraint only if that is true, and then uses big-M values computed from activity bounds. Constraints without enforcement are always added (at level ≥ 1). — [linear_relaxation.cc L1262-1264, L1318-1343](https://github.com/google/or-tools/blob/v9.15/ortools/sat/linear_relaxation.cc#L1262)
- The code tries to use tight big-M values for "many_literals => many_fixed literal" style constraints, splitting them into at-most-one parts. — [linear_relaxation.cc L372-380](https://github.com/google/or-tools/blob/v9.15/ortools/sat/linear_relaxation.cc#L372)
- `linearization_level` (default 1): "At level zero, no LP relaxation is used. At level 1, only the linear constraint and full encoding are added. At level 2, we also add all the Boolean constraints." — [proto L1648-1652](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1648)
- `add_lp_constraints_lazily` (default true): "we start by an empty LP, and only add constraints not satisfied by the current LP solution batch by batch". — [proto L1733](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1733)
- Presolve controls:
  - `max_presolve_iterations` (default 3; "In case of large reduction in a presolve iteration, we perform multiple presolve iterations").
  - `cp_model_probing_level` (default 2).
  - `presolve_probing_deterministic_time_limit`.
  - The Primer suggests reducing these only if the log shows presolve dominating the run, and warns that "reducing presolve increases the risk of failing to solve more complex models".
  - Sources: [proto L480-505](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L480); [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)
- The LNS sub-solver base uses `linearization_level=0`. — [cp_model_search.cc L796-799](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_search.cc#L796)
- The Primer's modelling chapter notes that `only_enforce_if` removes the need to choose a big-M value by hand. — [Primer modelling.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/modelling.md)
- The Primer's search-internals chapter notes a developer rule of thumb: "if a model genuinely needs per-value Booleans for a variable, that variable probably should not have been a…" integer; value literals are created up front in presolve. — [Primer search_core.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/search_core.md)

### Inferences
- Recommended pattern for coverage objectives:
  - Model shortfall as `short[t] = max(0, target[t] - coverage[t])` using two linear inequalities (`short[t] >= target[t] - coverage[t]`, `short[t] >= 0`) and minimize `sum w_t * short[t]`. It is LP-visible at level 1, has no enforcement literal, and presolve can bound it.
  - If the business metric really is "number of intervals meeting target", keep `hit[t]` but **also** link it linearly and without enforcement, e.g. `short[t] <= target[t] * (1 - hit[t])`. This is a plain linear constraint with a data-derived big-M, so the LP sees it at level 1. You can also add a secondary deficit term so that the LP gets a gradient.
  - As a lighter alternative, add a custom `max_lp` subsolver through `extra_subsolvers` so that at least one worker sees the enforced constraints. Do not set `linearization_level=2` globally, because top-level parameters also reach the LNS workers (see Q1).
- Objective coefficients: large weights (for example 10^6 in a blended lexicographic sum) are exact in CP-SAT, which uses integer arithmetic. They can still hurt the LP numerically, make cuts and reduced costs less informative, and make LNS accept only improvements on the top tier. This is inferred; there is no measured source. Keep weights as small as the priority structure allows (see Q6).
- `add_lp_constraints_lazily` generally does not need changing.

### Gaps
- No published benchmark was found that compares reified-indicator and deficit formulations in CP-SAT. The code fact about linearization is strong, but the size of the effect on a given roster model has to be measured.

---

## Q6. Lexicographic / multi-objective optimization

### Takeaway
CP-SAT has no native lexicographic objective. There are two standard patterns:
1. **Solve, fix, re-solve with a hint.** Optimize level k, add `obj_k == best_k` (or `<=` with a tolerance), re-hint the solution, then optimize level k+1.
2. **A single weighted sum with dominating weights.**

The maintainer (Perron) endorses pattern 1 with hints. Under a fixed total budget, pattern 1 needs a time split across levels. Pattern 2 needs bounded lower-level objectives to derive exact weights.

### Cited Findings
- Primer: "To implement a lexicographic optimization, you can do multiple rounds and always fix the previous objective as constraint". The coding-patterns chapter adds re-hinting from the previous solution and a relaxed fix (`<= ceil(obj*ratio)`) "to prevent degeneration". — [Primer modelling.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/modelling.md); [Primer coding_patterns.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/coding_patterns.md)
- Perron (OR-Tools discussion #4183): blocking previous solutions instead of hinting "you can. It is just harder for the solver at each iterations as the model is bigger (less fixed variables)". The thread endorses hint + equality constraint per level. — [GitHub discussion #4183](https://github.com/google/or-tools/discussions/4183)
- Feature request #2944, "Multiple Objectives" (lexicographic), was closed with milestone v9.2. The fetched page showed no maintainer comments, so the reason it was closed is unverified. — [GitHub issue #2944](https://github.com/google/or-tools/issues/2944)
- Weighted-sum encoding for two objectives, from search-result snippets of a third-party repository (not authoritative): minimize `M·p + o` with `M = o_max - o_min + 1`, giving an "exact mixed-radix lexicographic objective" from finite bounds on the lower-order objectives. — [PeterPirog/alters-base-planner PR #25](https://github.com/PeterPirog/alters-base-planner/pull/25)
- Primer (anecdotal): multi-objective optimization "remains a challenging topic, and even experts rely on significant trial and error". — [Primer coding_patterns.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/coding_patterns.md)
- Mechanism that helps pattern 1 (code fact): a complete, feasible hint becomes an incumbent immediately, and LNS fragments are cut to objective ≤ hint objective. Each phase therefore starts from the previous phase's schedule. — [cp_model_solver.cc L991, L1501-1505](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L991)

### Inferences
- **Solve, fix, re-solve** under a fixed budget:
  - Give each level a time slice, e.g. 50/30/20%.
  - Stop a level early with `relative_gap_limit` or a no-improvement callback.
  - Since level k is rarely proved optimal, fix `obj_k <= best_found_k`, not `== proven_opt`.
  - The equality form can make the model harder. An upper-bound constraint on the objective expression is LP-visible if it has no enforcement literal.
  - Re-hint the **complete** solution each time.
- **Weighted sum**:
  - It uses one solve, so the whole budget is spent on one search and all LNS progress is shared.
  - The weights must dominate exactly: W_k > sum over lower levels of (range × weight). With 3 to 4 levels over thousands of intervals, coefficients can reach 10^9 to 10^12.
  - This is still inside int64, but CP-SAT requires objective activity to avoid overflow. Very large coefficients weaken LP usefulness and make LNS on lower tiers slow.
  - Tighten the lower-level ranges, or use "soft" (non-exact) weights if strict priority is not required.
- **Hybrid** (common practice, not sourced): run a weighted sum for most of the budget, then do a short fix-and-re-solve polish on the lower levels.

### Gaps
- No published comparison was found of the two patterns under a fixed time budget.
- I did not confirm whether 9.15 has any built-in multi-objective API. I found none in `cp_model.py` or the proto.

---

## Q7. Determinism, run-to-run variance and portfolio or seed strategies

### Takeaway
The default multi-worker mode is **non-deterministic**: results vary run to run with thread timing. `interleave_search=true` makes the search deterministic regardless of `num_workers`, at some throughput cost. Use `max_deterministic_time` for reproducible budgets. `random_seed` changes choices; running several seeds is the documented way to benchmark robustly. I found no published variance measurements.

### Cited Findings
- `interleave_search` (default false, "Experimental"): "we interleave all our major search strategy and distribute the work amongst num_workers. The search is deterministic (independently of num_workers!), and we schedule and wait for interleave_batch_size task to be completed before synchronizing". `max_num_deterministic_batches` stops after N batches. — [proto L339-340, L771-774](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L771)
- The code uses `DeterministicLoop` when interleaving and `NonDeterministicLoop` otherwise. The default batch size is `num_workers*3`. — [cp_model_solver.cc L824-836](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc#L824)
- `random_seed` (default 1): "For some problems, the running time may vary a lot depending on small change in the solving algorithm. Running the solver with different seeds enables to have more robust benchmarks". `permute_variable_randomly` exists "mainly here to test the solver variability". — [proto L392-398](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L392)
- `max_deterministic_time`: "the time unit being as close as possible to a second". — [proto L336](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L336)
- Information sharing between workers, all on by default: `share_objective_bounds`, `share_binary_clauses`, `share_glue_clauses` (every `share_glue_clauses_dtime=1.0`), and `minimize_shared_clauses`. — [proto L777-801](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L777)
- Shared-tree search (`shared_tree_num_workers`, default -1 meaning heuristic) splits the tree among some workers. — [proto L1353](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1353)
- The Primer's benchmarking chapter recommends multiple runs and statistical comparison of configurations (general advice). Its log analyzer helps attribute progress to subsolvers. — [Primer benchmarking.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/benchmarking.md); [Primer parameters.md](https://github.com/d-krupke/cpsat-primer/blob/main/chapters/parameters.md)

### Inferences
- For a production WFM solver:
  - Use `max_time_in_seconds` for the real budget. For regression tests and A/B comparisons, use `interleave_search=true` + `max_deterministic_time`, or several seeds.
  - When comparing modeling or parameter changes, run at least 5 to 10 seeds per instance and compare medians. Single runs in non-deterministic mode can mislead.
  - "Multiple seeds in parallel processes, keep the best" is a legitimate portfolio if you have spare machines. On the same 2 to 4 cores it competes with CP-SAT's own internal portfolio, so a single multi-worker solve is usually better (inference).

### Gaps
- I found no published measurements of CP-SAT run-to-run variance or of the throughput cost of `interleave_search`.
- Perron's talks (CPAIOR, CP 2023, the scheduling seminar slides at schedulingseminar.com) could not be fetched because egress was blocked.
