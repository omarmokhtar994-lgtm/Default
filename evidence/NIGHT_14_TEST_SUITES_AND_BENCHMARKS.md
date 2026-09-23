# Test suites and published benchmarks: what they proved, what they found, what was fixed

Every run here went through the production runner
(`engine/RUN_UNIVERSAL_PRODUCTION.py`, FULL_SCHEDULE, QUICK, independent
validation on), exactly as a user's workbook does. Anyone can rerun it:

| tool | what it does |
|---|---|
| `tools/build_synthetic_suite.py` | builds the 14 synthetic workbooks and their certified expectations |
| `tools/benchmark_exact.py` | re-derives the published optima with an independent exact model (no engine code) |
| `tools/build_benchmark_suite.py` | translates the benchmarks into engine workbooks |
| `tools/run_synthetic_suite.py` | runs any suite through the production runner and scores it |

## How each expectation is known before the engine runs

**Planted cases.** A complete weekly schedule is written first: a shift per
associate per day, an adjacent OFF pair, and a break pattern taken from the
engine's own legal pattern set. Demand is then *derived* from that plan's
after-break coverage, rounded down to 0.01 FTE, so the plan can only be ahead.
The engine's own `calculate_metrics` scores the plan before the engine sees the
case: every planted case is certified at 100% of active intervals before and
after breaks, with 0 language gaps, 0 blank-staffed quarters and 0
break-concurrency violations. The engine never sees the plan. Zero slack is
deliberate: any misplaced shift or break shows up as a lost interval.

**Proof cases.** The outcome follows from arithmetic: over-demand under a hard
floor, a day everyone is hard-OFF on, and malformed contracts.

**Benchmarks.** Published optima, re-derived independently (below).

## The cases

| id | tier | roster | grid | shrinkage | what it tests |
|---|---|---|---|---|---|
| E1 | easy | 7 | 60 min | 0 | exact-fit days-off: every day needs exactly 5 of 7, which only 7 distinct OFF pairs give |
| E2 | easy | 14 | 60 | 20% | one shift, two per OFF pair, 15/30/15 breaks |
| M1 | moderate | 20 | 60 | 20% | ten legal starts, seven used, zero slack, no breaks |
| M2 | moderate | 28 | 60 | 15% | same shape with breaks |
| H1 | hard | 42 | 60 | 12% | 24/7, overnight shifts across midnight, 12h rest |
| H2 | hard | 20 | 60 | 20% | demand 2x the plan under a HARD floor: provably infeasible |
| H3 | hard | 30 | 60 | 10% | hard Spanish minimum after breaks, 09:00-18:00 |
| X1 | extreme | 120 | 15 | 10% | 24 starts, 24/7, 672 active intervals |
| X2 | extreme | 21 | 60 | 10% | everyone hard-OFF Sunday, Sunday demand = Monday's |
| R1-R5 | extreme | - | - | - | off-grid shift, cap order, gate-mode typo, headcount mismatch, 100% shrinkage |

## Published benchmarks, re-derived before use

Page fetches to the source sites were blocked by the network policy; the
problem data were confirmed by search results, and both published optima were
**re-derived by an independent exact model** (`tools/benchmark_exact.py`,
OR-Tools CBC/CP-SAT, no engine code) before anything was compared:

| benchmark | published | re-derived |
|---|---|---|
| Winston, *Operations Research*, Ch. 3, post office: need Mon 17, Tue 13, Wed 15, Thu 19, Fri 14, Sat 16, Sun 11; 5 consecutive days on, 2 off | 23 employees | IP **23**, LP 22.333 |
| Hillier & Lieberman, *Intro to OR*, Sec. 3.4, Union Airways: 48/79/65/87/64/73/82/43/52 agents per 2h 06:00-24:00, 15 for 00-06; five 8h shifts at $170/160/175/180/195 | $30,610 with (48, 31, 39, 43, 15) | **$30,610**, (48, 31, 39, 43, 15); minimum daily headcount 176 |

Translation, stated so nothing is hidden: shrinkage 0 and no breaks (neither
problem has them); demand is whole people per hour, and with Target 100% an
interval is "hit" exactly when headcount meets the textbook requirement. The
engine's OFF rule (exactly two adjacent OFF days, cyclic) *is* Winston's rule.
Union Airways is daily; the engine plans a week, so the roster is the smallest
weekly one an exact tour model finds, **247**. Last Saturday's shifts (needed for
Sunday carry-in and rest) are the exact plan's own Saturday.

**Optima in the engine's metric** (intervals hit; exact CP-SAT over legal tours):

| instance | optimum | proof |
|---|---|---|
| Winston N=23 | 56/56 | OPTIMAL |
| Winston N=22 | **48/56** | OPTIMAL: one day must fall short |
| Union N=247 | 168/168 | feasible plan under the engine's rest and variety rules |
| Union N=246 | reference 166, bound 168 | 166 is proven optimal for the cyclic week (1,230 shift-starts vs 1,232 needed; a day-window short by even one head loses at least 2 hours). The engine's week is not cyclic: last Saturday's carry-in covers Sunday 00-06 for free, so a relaxation reaches 168. Engine results between 166 and 168 are all legitimate. |

## First pass (the tier budgets I chose: 300 / 600 / 900 / 1200 s, 1 worker)

| case | result | vs. optimum | validator / parity |
|---|---|---|---|
| E1 | 63/63 | **OPTIMAL** | PASS / PASS |
| E2 | 45/63 | far | PASS / PASS |
| M1 | 116/118 | near (-2) | PASS / PASS |
| M2 | 82/117 | far | PASS / PASS |
| H1 | 114/168 | far | PASS / PASS |
| H2 | refused `HARD_FLOOR_PROVABLY_IMPOSSIBLE`, `AGGREGATE_HARD_FLOOR_CAPACITY_SHORTAGE` (-480 h) | **correct** | - |
| H3 | 77/105 | far | PASS / PASS |
| X1 | stopped after 78 s of 1,200: `HARD_FEASIBILITY_SEARCH_INCOMPLETE` | **defect** | - |
| X2 | refused `ZERO_ACTIVE_INTERVAL_PROVABLY_IMPOSSIBLE` for every Sunday hour | **correct** (see note) | - |
| R1-R5 | refused with exactly the expected code, nothing published | **correct** | - |
| Winston N=23 | 56/56 | **OPTIMAL** | PASS / PASS |
| Winston N=22 | 48/56 | **OPTIMAL** | PASS / PASS |
| Union N=247 | stopped after 61 s: `HARD_FEASIBILITY_SEARCH_INCOMPLETE` | **defect** | - |
| Union N=246 | stopped after 61 s | **defect** | - |

X2: I expected a schedule with Sunday at 0 hits. The engine refuses instead:
it treats "someone on the floor in every demanded interval" as a hard contract
and proves, before solving, that Sunday cannot meet it. That is its documented
fail-closed policy and a stricter correct answer, not a defect.

Every schedule the engine published validated clean. Every refusal was the
right one. The shortfalls needed root causes, which follow.

## What the failures were, and what was done

### 1. The feasibility probe gave up with 94% of the budget unspent (FIXED)

X1 and both Union runs spent a 30 s one-worker probe, got UNKNOWN (no proof
either way) and stopped the whole run. UNKNOWN is not INFEASIBLE, and Stage-1
cannot start without a feasible skeleton anyway, so the engine now retries the
probe on half the Stage-1 window (cap 600 s) before giving up. Union N=247 and
N=246 now produce schedules, validator and parity PASS, 0 hard failures.

### 2. A starved Stage-1 could only produce a proxy-biased skeleton (FIXED)

E2's schedule put 11 people on Sun/Mon and 7 on Tue/Wed, when 10 every day was
possible. Stage-1 ran exactly one solve: the deterministic baseline, a
**productive-basis** profile. That basis credits each person with
(1 - shrinkage) x (paid - break) / paid = 0.711 FTE in *every* hour, as if
break loss were spread evenly. Ten people read as 7.11 FTE against 7.4 (a miss
everywhere) and eleven as 7.82 (a hit), so stacking days scores better. Pinned
to the planted schedule, the same model scores it **worse** (2.18e10 vs 1.57e10):
an objective effect, not a search failure. A **before-basis** profile solves
the case OPTIMALLY in 0.2 s with 10 on every day. The portfolio refused the 19 s
left because of its 45 s-per-profile floor.

With a full budget the portfolio's before-basis profiles run: at 1,800 s E2 is
63/63. When the portfolio cannot fund a single profile, the engine now runs its
first before-basis profile on whatever is left (at least 5 s). **E2 at 300 s: 45
-> 63/63 before and after, status PASS.** Inert whenever any portfolio profile
runs.

### 3. The headcount advisory reported shortages that do not exist (FIXED)

With E2 at 63/63 and zero break losses, the Read-Me sheet still said "1 more
associate needed". `break_capacity_headcount_requirement` counted room per
15-minute quarter against ceil(requirement), but the metric averages an
interval's quarters, so at 30/60 minutes it under-counted room. Its own
docstring promised "a deficit is proof that headcount is short". Room is now
floor(sum of the interval's quarter heads - quarters x requirement), with the
concurrency cap still applied per quarter; at 15 minutes the result is
unchanged. A true shortage (H2) is still reported.

### 4. The no-candidate joint endgame was OOM-killed (GUARDED)

After the probe fix, X1 got further, found no break-compliant candidate, and
entered the joint endgame, which reopens a joint shift+break model with widening
neighbourhoods. On 120 associates at 15 minutes the process reached 13.9 GB and
the cgroup OOM killer SIGKILLed it: no schedule, no audit, no validation.
CP-SAT's own 6 GB cap bounds search, not model construction. Both joint loops
now check available memory before building a model (at least max(2 GB, 15%))
and record a clean stop. Real workbooks peak near 1 GB (NIGHT_03), so this never
triggers on the corpus.

### 5. A budget question, not a defect: my tier budgets were below the engine's floor

Production QUICK is **3,600 s**. At 300-1,200 s the 15-profile Stage-1
portfolio cannot run. The four "far" cases were rerun at 1,800 s:

| case | first pass | 1,800 s | optimum | Stage-1 profiles run |
|---|---|---|---|---|
| E2 | 45 | **63** | 63 | 15/15 |
| M1 | 116 | **118** | 118 | - |
| M2 | 82 | 82 | 117 | 10/15 |
| H1 | 114 | 114 | 168 | 9/15 |
| H3 | 77 | 76 | 105 | 10/15 |

E2 and M1 reach the proven optimum. M2, H1 and H3 do not; the next section
explains why.

### 6. Stage-2 leaves coverage behind on zero-slack cases (MEASURED)

On M2, Stage-1 found skeletons at **112/117** before breaks, but the shipped
schedule came from the probe skeleton at 85/82. Every 35 s break solve on the
good skeletons returned UNKNOWN; the one 180 s attempt returned its warm-start
hint unchanged (72/111, `solution_info: main [hint]`). Replaying that exact
solve outside the run (same skeleton, same 115-pattern model, same hint, same
seed) reaches **97-100/115**, even with four replays in parallel, so neither
the hint nor CPU contention explains it. Model size, weights and hint count
match exactly. What is established: on these instances a single-worker break
solve of 120-180 s is fragile, and the engine's break search is sized in exactly
such slices.

It also exposed why more workers never helped Stage-2:
`break_infeasibility_core_enabled` (default **Yes**) attaches assumption
literals to every break model so an infeasible one can be explained, and
assumption solves are single-worker, so **every Stage-2 solve ran on one worker
whatever `--num-workers` said.** See the S2-PAR section.

### 7. X1 after the fixes: a clean, actionable refusal instead of a kill

X1 (120 associates, 15-minute grid, 24/7) at 1,800 s, one worker, on the final
engine: the probe retry found a skeleton (first probe UNKNOWN at 55 s, retry
FEASIBLE), no OOM, and the run ended `FAIL_NO_BREAK_FEASIBLE_CANDIDATE` /
`BREAK_EXCEPTION_CAP_GAP`: no break-compliant schedule found within budget, with
the engine's standard guidance (add or overlap resources in the named windows,
or raise the no-break exception cap as an explicit business decision). The
planted plan proves a compliant schedule exists, so this is a **capacity limit
of the engine at this size and budget**, not an infeasible input. It is reported
as such, not hidden.

### 8. FA-7 on the final engine found one more real defect (FIXED)

All 12 runnable corpus workbooks plus 2 BEFORE_BREAKS_ONLY runs, 900 s, one
worker, on the final engine:

| workbook | outcome | validator | parity (48 fields) | target before -> after |
|---|---|---|---|---|
| AE_AR_B2B | schedule | PASS, 0 hard | PASS | 145 -> 142 |
| AE_AR_Choice | schedule | PASS, 0 hard | PASS | 127 -> 125 |
| AE_FR_B2B | schedule | PASS, 0 hard | PASS | 112 -> 112 |
| AE_FR_Choice | schedule | PASS, 0 hard | PASS | 112 -> 106 |
| AE_IT_B2B | schedule | PASS, 0 hard | PASS | 75 -> 69 |
| AE_IT_Choice | needs break-exception permission | - | - | same outcome at 1,800 s before this work; genuinely short 46.6 h |
| Cricut Chat | schedule | PASS, 0 hard | PASS | 154 -> 147 |
| Cricut Voice | schedule | PASS, 0 hard | PASS | 232 -> 231 |
| GDI REAL28 24/7 | schedule | PASS, 0 hard | PASS | 139 -> 139 |
| NMG EN+SP | needs break-exception permission | - | - | same outcome at 1,800 s before this work (break damage is arithmetically forced) |
| NMG EN nesting | pre-solver contract refusal | - | - | known fixture contract gap |
| NMG SP | schedule | **FAIL_METRIC_PARITY** | **FAIL: blank_staffed_quarters 16 vs 0** | 126 -> 123 |
| AE_FR_Choice (before only) | skeleton | PASS | PASS | 112 |
| Chat (before only) | skeleton | PASS | PASS | 166 |

NMG SP: the engine counted a blank (no-demand) quarter as "staffed" when last
Saturday's carry-in covered it; the validator counts only current-week staffing,
which is what the rule ("no new staffing in blank intervals") means. The engine's
comment claimed the validator did the same; it did not. The inconsistency is
already present in the RC5 candidate. Carry-in is fixed input the solver cannot
move, so the engine is corrected to count current-week staffing only. Proven on
the workbook: carry-in covers 16 blank quarters, and an empty current week now
reports 0. Pinned by a test that fails on the previous engine. **Rerun on the
final engine (900 s, 1 worker): validator PASS, 0 hard failures, parity PASS
on all 48 fields, same coverage (126 -> 123).**

### 9. Two further decisions, taken on rules written before the runs

**F-6: the next-Sunday deficit weight: NOT shipped.** In `solve_breaks` the
next-Sunday deficit is measured in x1e6 units but weighted `target_def // 100`,
so a next-Sunday shortfall costs 100x the same shortfall in the current week
(Stage-1 weighs it at 1/25). It looks like a leftover from a unit change, and
8 of 12 corpus workbooks have Saturday overnight shifts that reach next Sunday.
Treatment (hits exact, deficit in x100 units), Cricut Chat, 1 worker, 1,800 s:
after-target **161 vs 165** for the control. The rule said any regression means
no. The weights stay; the inconsistency is documented.

**Anchor hand-off margin: shipped (safe; benefit shown by arithmetic).** It
never binds on one worker: bit-identical in every pair run (1,800 / 900 / 700 s;
e.g. 700 s: 140/217 both arms). It binds only in the 4-worker case that
motivated it, where the worst measured hand-off (9.82 s) is under the 30 s
margin.

### 10. S2-PAR: Stage-2 on all cores. Measured, held back by its own rule

`break_infeasibility_core_enabled` (default Yes) attaches assumption literals to
every break model so an infeasible one can be explained, and assumption solves
are single-worker. So **every Stage-2 break solve runs on one worker, whatever
`--num-workers` says.** The candidate (`patches/S2_PAR_stage2_parallel_break_solve.patch`)
solves a clone with those literals fixed true on all workers, and extracts the
core, single-worker, only when the result is INFEASIBLE. With one worker the
code path is unchanged.

Component A/B, rule registered before the run: same skeleton, same 120 s, 4
workers, seed 9000.

| skeleton | current (forced to 1 worker) | candidate (4 workers) |
|---|---|---|
| Cricut Chat | 165 / 211 | **167** / 211 |
| AE_AR_B2B | **no solution** (UNKNOWN) | 166 / 166 |
| SYNTH_M2 | **100** / 115 | 96 / 115 (better objective) |
| SYNTH_H1 | **no solution** | 113 / 149 |
| SYNTH_H3 | **no solution** | 92 / 105 (the full run shipped 76) |
| X1 probe skeleton (infeasible) | INFEASIBLE, core [pattern_assignment, zero_coverage, week_boundary] | same status, same core |

Criteria: core preserved **pass**; one-worker path identical **pass**; never
loses a solution **pass**; no case worse by more than 2 **FAIL** (M2 -4: the
candidate found a solution its own objective prefers, trading 4 target hits for
other quality terms). Held back on this component test.

**Then shipped on its end-to-end A/B** (rule registered before the runs,
`evidence/s2par_e2e/`): production runner, 900 s, 2 workers, seed 9000.

| workbook | current | S2-PAR | proven optimum |
|---|---|---|---|
| Cricut Chat | 155 | **179** | - |
| Cricut Voice | 227 | **246** | - |
| AE_AR_B2B | 166 | **167** | 168 |
| NMG SP | 121 | 121 | - |
| SYNTH_M2 | 82 | **109** | 117 |
| SYNTH_H3 | 76 | **91** | 105 |

Summed 827 -> 913, every run validator and parity PASS, no workbook worse.
Commit 37288d0; tests `tests_staged/test_rc9_2_16_stage2_parallel.py`.

## Final scoreboard (final engine)

| case | final result | proven optimum / expected | verdict |
|---|---|---|---|
| E1 | 63 | 63 | **optimal** |
| E2 | 63 (300 s and 1,800 s) | 63 | **optimal** (was 45 before fix 2) |
| M1 | 118 (1,800 s) | 118 | **optimal** |
| M2 | 82 | 117 | far: Stage-2 (section 6) |
| H1 | 114 | 168 | far: Stage-2 |
| H2 | refused, hard floor provably impossible | refuse | **correct** |
| H3 | 76 | 105 | far: Stage-2 |
| X1 | clean refusal, `BREAK_EXCEPTION_CAP_GAP` | 672 (planted) | capacity limit at 1 worker / 1,800 s; was a crash |
| X2 | refused, zero-staff interval provably unavoidable | refuse or 0 on Sunday | **correct** |
| R1-R5 | refused with the exact code | refuse | **correct** |
| Winston N=23 | 56 | 56 | **optimal** (matches the published 23) |
| Winston N=22 | 48 | 48 | **optimal** |
| Union N=247 | 118 | 168 | valid schedule (was a stop); far from optimal at this size |
| Union N=246 | 126 | 166-168 | valid schedule (was a stop); far |

**What this says about the engine, plainly.**

* It never published an invalid schedule. Every published schedule across
  suites, benchmarks and corpus passed the independent validator with 0 hard
  failures, and after the blank-staffing fix, engine/validator parity holds on
  all 48 fields.
* Every refusal was correct and named the right reason.
* On small and structured problems, including both textbook benchmarks, it
  reaches the proven optimum.
* On zero-slack problems with breaks, and on large rosters, it leaves 10-30% of
  the proven optimum on the table at one worker and 1,800 s. The mechanism was
  identified (Stage-2 break solves ran on one worker in 35-180 s slices), and
  S2-PAR, which fixes it, is shipped: M2 82 -> 109 and H3 76 -> 91 of the
  proven 117 and 105, Chat +24, Voice +19.

## Round 2: closing the gaps (after S2-PAR)

### At the production budget

QUICK's default 3,600 s, 2 workers, final engine (S2-PAR included). H1 and
Union N=247 shared the CPU with prototype experiments for part of their run.

| case | 1 worker, <= 1,800 s (earlier) | production budget | proven optimum |
|---|---|---|---|
| M2 | 82 | **105** (109 at 900 s in the A/B) | 117 |
| H3 | 76 | **93** | 105 |
| H1 | 114 | **138** | 168 |
| Union N=247 | 118 | **168 = optimum** | 168 |

Every run validator PASS, 0 hard failures, parity PASS. Union N=247 now
matches the published benchmark exactly.

### What still separates M2 / H3 / H1 from the optimum, and what was tried

In all three, the engine's best skeleton already covers **every** interval
before breaks (117/117, 105/105, 168/168); the loss is in fitting breaks into it.

* **Break placement is not the limit.** On the *planted* skeleton the break
  model finds the optimum 117/117 with no hint, even on one worker (300 s),
  and keeps it when hinted. On the engine's own skeletons, 600 s on 4 workers
  plateaus at 110 (M2) and 95 (H3). Those skeletons cover everything before
  breaks but are not shaped to absorb them.
* **Implicit-break Stage-1 (Bechtold & Jacobs 1990, Aykin 1996): tried, not
  shipped.** Breaks as an aggregate flow inside each shift's break windows.
  The model scores the planted plan as near-perfect (1.5e5 against 3.4e10 for
  the engine's skeleton), so the objective is right, but the search does not
  converge: 120-180 s on 4 workers, even warm-started with shifts and flows,
  gave skeletons worth 95-98 after breaks. Relaxing spacing makes it too loose
  to steer.
* **Local search on breaks: tried, not shipped.** One-agent-at-a-time
  re-placement stalls on coverage plateaus (81/117 even on the planted skeleton).
* **Day-by-day joint shift+break re-optimisation: tried, not shipped.** Its
  apparent gains (106 -> 112) came entirely from violating the break-concurrency
  cap; with the cap respected and only improvements kept, 104 -> 104.

The remaining gap needs a global joint shift+break optimiser (column
generation / branch-and-price, as in the break-scheduling literature). That is
a multi-day build, and no claim is made here that it has been done.

### Hard public benchmarks

The benchmark sets that match this problem (schedulingbenchmarks.org's
multi-activity multi-day set; TU Wien's shift-design and break-scheduling
sets) could not be downloaded: the environment's network policy blocks
www.schedulingbenchmarks.org, www.dbai.tuwien.ac.at and web.archive.org.
They stay untested until those hosts are allowed.
