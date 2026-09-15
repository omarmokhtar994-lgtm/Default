# RC5 — adversarial review

Brief: challenge RC5, find what's hidden, decide whether it is the best practical
engine achievable here. Everything below was measured against the shipped RC5
engine (`0e6f6435…`, patched build `b005d6b6…`).

---

## What I could not do, stated first

The brief asks me to "study the generated schedules" (Phase 2) and quantify
coverage gains (Phase 3). **I have no run artifacts.** Across RC2, RC4 and RC5,
no scenario result has ever been uploaded to me — the RC5 packages contain a
smoke run and nothing else. So:

- Sections E, F, O, P are answered **structurally**, from the model, not from
  output. Where I give a number, I label it a hypothesis and say what run would
  confirm it.
- I have not invented percentages. A board making investment decisions off a
  fabricated "12% coverage uplift" would be badly served.

Everything else is measured.

---

## SECTION A — Executive summary

**RC5 is not near its practical optimum, and the gap is not headcount, hardware,
or solver choice. It is the objective formulation.**

Three measurements tell the whole story:

| Measurement | Value |
|---|---|
| Largest Stage-1 model | **5,880 binary variables** |
| Objective: weight spread in one weighted sum | **800,000,000 : 1** (3.2e9 down to 4), **77 terms** |
| Symmetric equivalents of every solution (Cricut Chat) | **6.2 × 10²³**, with no symmetry breaking |

A 5,880-binary personnel scheduling model is **small**. CP-SAT solves models two
orders of magnitude larger to proven optimality routinely. That this one needs
four hours and still reports `TRUNCATED_INSUFFICIENT_STAGE1_BUDGET` is not a
capacity problem — it is a modelling problem, and it is fixable.

**Everything the project has been fighting traces to one root cause chain:**

```
800M:1 weighted-sum spread  ->  worthless LP relaxation, no pruning
6.2e23 unbroken symmetry    ->  search re-explores equivalent solutions
                            ->  a tiny model cannot converge
                            ->  so 17 weight-profiles were built to sample the frontier
                            ->  17 profiles don't fit the budget -> truncate at 2 of 15
                            ->  TRUNCATED_INSUFFICIENT_STAGE1_BUDGET every long run
                            ->  outcome depends on machine load (measured: same seed,
                                same input -> shippable schedule vs no schedule)
                            ->  "maximum coverage" means best-found-in-truncated-search
```

Fix the top two and the rest dissolve. My honest estimate: **the single largest
available improvement in this project is not a scheduling feature — it is
replacing the scalarized objective with a proper lexicographic solve and adding
symmetry breaking.**

---

## SECTION B — Current RC5 assessment

RC5 is a **well-engineered release chain wrapped around an under-engineered
optimisation model.**

The release machinery is genuinely good, and better than most in-house WFM tools
I would expect to see: exact-artifact independent validation, engine/validator
metric parity as a gate, fail-closed sealing, `production_ready` that no code
path can set true, 453 offline guards. That work is real and should be kept.

The optimiser underneath it is a 2013-era formulation: a single weighted-sum
objective over 77 terms with hand-tuned magic constants, a heuristic two-stage
decomposition, a 17-profile portfolio standing in for multi-objective search, no
search strategy, and no symmetry handling.

---

## SECTION C — Strengths

1. **Release safety.** Verified in code: packaging requires validation PASS;
   `production_ready` is hard-coded `False` in all three writers and set `True`
   nowhere; the seal triple-checks hashes.
2. **CP-SAT is the right solver.** Correct choice for this problem class — good
   at feasibility with complex side constraints, free, actively developed.
3. **Warm starting exists.** `AddHint` at 11 sites. Most in-house engines omit it.
4. **The two-stage decomposition is defensible.** Shift/OFF then breaks is a
   standard industrial decomposition. It costs global optimality but buys
   tractability — see Section M for when to revisit.
5. **The hard-rule model is thorough.** Rest gaps, cyclic Sunday carry-in,
   language eligibility with directional Can-Cover, blank-demand staffing,
   opening guards. Genuinely comprehensive domain coverage.
6. **Quality debt is visible rather than hidden.** A hard-valid, quality-blocked
   schedule is retained as review-only evidence. Many commercial tools silently
   discard it.

---

## SECTION D — Weaknesses

### D-1 The objective is a 77-term weighted sum spanning 800,000,000:1 — CRITICAL

Measured on profile `target90_restore_champion`:

```
target_miss          3,200,000,000
floor_miss             420,000,000
quality_global_gap     260,000,000
severe_miss            180,000,000
...
overage                         40
shift_variety                    8
preference                       4
```

Three consequences, all standard results:

**(a) Low-weight terms are arithmetically inert.** `preference` at weight 4
cannot influence any solution where one target interval is worth 3.2e9. It would
take 800 million preference violations to equal one target interval. This is
**exactly the A40 defect** ("break-concurrency penalty inert at 1:140,000") — but
A40 fixed one weight; the pattern remains across ~20 more terms.

**(b) It is a fake lexicographic order.** The intent is clearly hierarchical
(target > floor > quality > overage > preference). A weighted sum only emulates
a hierarchy if every weight exceeds the maximum attainable sum of all lower
terms. Nobody can verify that by hand across 77 terms and 17 profiles, and it
has demonstrably already failed twice.

**(c) Weighted-sum scalarization provably cannot reach unsupported Pareto
points.** For integer programs, many efficient solutions lie off the convex hull
of the Pareto frontier and are unreachable by *any* weight vector. So there exist
schedules that are better on the business's own stated priorities that this
formulation can never return — regardless of runtime. This directly answers the
Phase 3 question "whether alternative optimization sequences produce better
results": yes, provably.

**The 17 profiles are a symptom.** They exist because no single weight vector
works, so the engine samples the frontier by brute force. That is what consumes
the budget.

### D-2 No symmetry breaking, and the symmetry is astronomical — CRITICAL

Grouping associates by the attributes the model actually distinguishes
(language, preferences, fixed rows, previous Saturday, nesting group):

| Workbook | Associates | Distinct classes | Symmetric equivalents per solution |
|---|---:|---:|---:|
| **Cricut_Chat** | 27 | **4** | **6.2 × 10²³** |
| Cricut_Voice | 33 | 11 | 2.1 × 10¹⁷ |
| GDI_REAL28 | 29 | 13 | 3.5 × 10⁷ |
| AE_AR_B2B | 35 | 24 | 6.5 × 10⁵ |
| NMG_EN_AND_SP | 17 | 9 | 1.2 × 10³ |

On Cricut Chat, **24 of 27 associates are mutually interchangeable**. Every
solution the solver finds has 6.2e23 relabelled twins, and nothing tells CP-SAT
they are equivalent. `symmetry_level` is not set; no ordering constraints exist.

This is the textbook cause of "small model, huge runtime". Standard fix: impose
a lexicographic ordering within each interchangeable class (associate *i* may
take pattern *p* only if associate *i−1* takes a pattern ≥ *p*), or set
`symmetry_level=2` and let presolve detect it. Cost: a few dozen lines.

### D-3 No search strategy — HIGH

`AddDecisionStrategy` is used **zero** times. No branching guidance on a problem
with obvious structure (branch on high-demand intervals first, on constrained
associates first). CP-SAT's default portfolio is good, but on a symmetric,
badly-conditioned objective it is being asked to do the impossible.

### D-4 Model constructs left on the table — MEDIUM

| Construct | Uses | Comment |
|---|---:|---|
| `AddExactlyOne` / `AddAtMostOne` | **0** | written as `Add(sum(...) == 1)`; presolve usually recovers these, but the dedicated forms propagate better |
| `AddNoOverlap` / `AddCumulative` | **0** | breaks are boolean-encoded rather than modelled as intervals — the natural encoding for "this person is on break here" |
| `AddAllowedAssignments` | **0** | shift/pattern compatibility is a natural table constraint |
| `AddHint` | 11 | good |

Solver parameters set: `max_time_in_seconds`, `num_search_workers`,
`random_seed`, `randomize_search`, `log_search_progress`, `linearization_level`,
`cp_model_presolve`. **Not set:** `symmetry_level`, `search_branching`,
`interleave_search`, `subsolvers`, `use_lns` family.

### D-5 The portfolio is a budget sink — HIGH

15–17 profiles requested, **2 attempted** in every long run observed, status
`TRUNCATED_INSUFFICIENT_STAGE1_BUDGET`. So 13 of 15 configured search strategies
never execute. The configuration describes a search that does not happen.

### D-6 Reproducibility — HIGH

Measured: identical workbook, identical seed, identical budget →
`production_eligible TRUE` with a full schedule on one run, and **no schedule at
all** on the next. Because the search is wall-clock-bounded and truncating,
machine load changes the result. No single run is evidence, for anyone.

### D-7 Contract-level silent coercions — HIGH (carried from the RC4 audit)

Still open in RC5, re-tested: a contract stating **zero breaks receives 60
minutes of breaks** (`_parse_break_segments` backfills a hard-coded 15/30/15);
an invalid `Interval Minutes` silently becomes 60. Latent on all ten current
workbooks — but these are exactly the defects that bite the first time a real
client contract differs from the templates.

### D-8 Structure — MEDIUM

21,320 lines in one module; `run_case` is **3,465 lines**; 14 functions exceed
200 lines. There is no seam at which the optimiser can be tested independently
of the release chain, which is why the 453 guards are largely source-text
assertions rather than behavioural tests.

---

## SECTION E — Coverage optimization findings

Structural, not empirical (no artifacts).

1. **Coverage is capped by search truncation, not by the roster.** With 13 of 15
   profiles never running, the reported coverage is the best of two strategies,
   not of fifteen.
2. **Unsupported Pareto points are unreachable** (D-1c). Some better schedules
   cannot be returned at any runtime.
3. **The two-stage decomposition loses global optimality by construction.** The
   skeleton is chosen before break feasibility is known. RC5 mitigates with
   break-aware repair and a joint refinement phase, which is the right
   mitigation — but a skeleton that is optimal before breaks and poor after is
   still a structural risk, and the project has already measured exactly that
   (target 257 → 231 after breaks on one run).
4. **Interval-level vs global:** the floor/target/severe-gap terms are per-interval
   penalties summed globally. That is a reasonable proxy, but with the weight
   spread in D-1 the per-interval terms below ~1e6 cannot trade against each
   other meaningfully.

**What would settle it:** one A/B on a frozen workbook — current engine vs
lexicographic + symmetry-broken engine, same budget, both twice.

---

## SECTION F — Utilization findings

Also structural. The utilisation-shaped terms — `preference` (4),
`shift_variety` (8), `overage` (40), `blank` (240) — sit **6 to 9 orders of
magnitude below** `target_miss` (3.2e9). They are mathematically incapable of
changing a solution that differs by even one target interval.

So RC5 does not currently trade coverage against utilisation, fairness or
preference in any meaningful way: coverage wins by construction, always, and the
remaining terms only break exact ties. If the business wants "maximum coverage,
then fairness", that is *achievable* — but it needs a lexicographic solve, not
these weights.

The 8 `Employee ...` fairness gates have **no workbook route at all** (45 of 98
engine parameters are unreachable from any workbook — measured in my RC4 audit),
so fairness is presently not configurable by the business.

---

## SECTION G — Architecture findings

The layering is sound: parse → preflight → Stage 1 → Stage 2 → repair → select →
polish → validate → seal. The release half is strong. The optimisation half
needs the objective rebuilt.

**Would I build it this way today? Mostly yes, with two changes** (Section Q).

---

## SECTION H — Industry benchmark

| Dimension | RC5 | Industry practice | Verdict |
|---|---|---|---|
| Solver | CP-SAT | CP-SAT / Gurobi / CPLEX | **On par** — correct choice |
| Formulation | Explicit `x[a,d,s]` assignment | Set-covering (Dantzig) columns for large rosters; explicit for small | **On par at this scale** — 5,880 vars does not need column generation |
| Multi-objective | Weighted sum, 800M:1 | **Lexicographic / epsilon-constraint** | **Behind** — this is the gap |
| Symmetry | None | Standard practice for interchangeable staff | **Behind** |
| Search guidance | None | Decision strategies, LNS | **Behind** |
| Break modelling | Boolean per quarter | Interval variables / `AddCumulative` | **Behind, minor** |
| Warm start | `AddHint` ×11 | Standard | **On par** |
| Validation & audit | Exact-artifact independent validation, metric parity gate | Rare in commercial WFM | **Ahead** |
| Reproducibility | Wall-clock bounded, load-dependent | Deterministic budgets / fixed node limits | **Behind** |

**Where RC5 exceeds industry practice:** auditability. The independent validator,
metric-parity gate and fail-closed sealing are better than what most commercial
WFM platforms expose. Keep that.

Column generation / Dantzig set-covering is the classic answer for large
personnel scheduling — but at 5,880 binaries it would be **over-engineering**.
Correctly *not* adopted. Revisit above ~200 associates.

---

## SECTION I — Open source and research findings

**Techniques RC5 already uses well:** CP-SAT, warm starting, two-stage
decomposition, assumption literals for infeasibility cores (a genuinely
sophisticated touch).

**Techniques RC5 is missing, in value order:**

| Technique | Benefit | Complexity | Risk | Effort | ROI |
|---|---|---|---|---|---|
| **Lexicographic / epsilon-constraint objective** | Removes D-1 entirely; one model replaces 17 profiles; frees the whole Stage-1 budget | Medium | Medium — changes selection on every scenario, needs a baseline | ~1 week | **Highest** |
| **Symmetry breaking on interchangeable associates** | Attacks a 6.2e23 factor | Low | Low — provably solution-preserving up to relabelling | ~1 day | **Very high** |
| **`AddDecisionStrategy`** | Guides search on known structure | Low | Low | ~1 day | High |
| **`symmetry_level=2`, subsolver tuning** | Free, parameter-only | Trivial | Low | hours | High |
| Interval vars / `AddCumulative` for breaks | Better propagation in Stage 2 | Medium | Medium | ~3 days | Medium |
| Deterministic budgets (node/conflict limits instead of wall clock) | Fixes D-6 reproducibility | Low | Low | ~1 day | High |

**Techniques RC5 should avoid:** column generation (over-engineering at this
scale), genetic algorithms / simulated annealing / tabu search (would *lose* the
hard-rule guarantees CP-SAT gives you — a strict downgrade here), and commercial
solver migration (CP-SAT is not the bottleneck).

Sources consulted:
[OR-Tools multi-objective discussion](https://github.com/google/or-tools/issues/1344) ·
[CP-SAT Primer](https://d-krupke.github.io/cpsat-primer/) ·
[Weighted sum scalarization limits](https://arxiv.org/pdf/1908.01181) ·
[Core-guided multi-objective algorithms](https://arxiv.org/pdf/2204.10856) ·
[Lexicographic objectives in scheduling](https://arxiv.org/pdf/2604.05153)

---

## SECTION J — Gap register

| ID | Category | Description | Root cause | Coverage | Utilisation | Compliance | Business risk | Tech risk | Cplx | Pri |
|---|---|---|---|---|---|---|---|---|---|---|
| **G1** | Optimisation | 77-term weighted sum, 800M:1 spread | Scalarized multi-objective | **High** | **High** | None | Schedules provably unreachable; weights already failed twice | Med | Med | **1** |
| **G2** | Optimisation | No symmetry breaking; 6.2e23 equivalents | Interchangeable associates unmodelled | **High** | Med | None | Runtime wasted re-exploring twins | Low | Low | **2** |
| **G3** | Search | 13 of 15 profiles never run | Portfolio exceeds budget (caused by G1) | **High** | Med | None | Configured search doesn't happen | Low | Low | **3** |
| **G4** | Reliability | Same input+seed → schedule or no schedule | Wall-clock-bounded truncating search | Med | Low | None | No single run is evidence | Med | Low | **4** |
| **G5** | Contract | Zero-break contract gets 60 min of breaks | Hard-coded backfill in `_parse_break_segments` | Med | **High** | **High** | Roster sized to wrong contract, silently | Low | Low | **5** |
| **G6** | Contract | Invalid `Interval Minutes` → silent 60 | No else-branch for supplied-but-invalid | Med | Low | Med | Every % computed at wrong granularity | Low | Low | **6** |
| **G7** | Config | 45 of 98 parameters unreachable from any workbook | No template rows | Low | **High** | Med | Fairness/skill gates not configurable | Low | Med | **7** |
| **G8** | Search | No decision strategy | — | Med | Low | None | Slower convergence | Low | Low | **8** |
| **G9** | Modelling | Breaks boolean-encoded, not intervals | — | Low | Med | None | Weaker Stage-2 propagation | Low | Med | **9** |
| **G10** | Structure | 21,320-line module, 3,465-line function | Accreted | Low | Low | Low | Defects can't be isolated; guards are textual | Med | High | **10** |
| **G11** | Validation | Validator `exec_module`s the engine | Shared parser | None | None | Med | Can't catch a contract misreading | Low | High | **11** |

---

## SECTION K — Prioritised roadmap

**A. Immediate quick wins (hours)**
- Set `symmetry_level=2`; try `search_branching`. Parameter-only, reversible.
- Deterministic budgets instead of wall clock (fixes G4).
- P-1 memoisation — **already done**, 5.4×, byte-identical output.

**B. High impact / low effort (days)**
- **G2 symmetry breaking** — lexicographic ordering within interchangeable
  classes. One day. Attacks a 6.2e23 factor.
- G8 decision strategy on high-demand intervals and constrained associates.
- G5, G6 contract coercions — fail closed instead of silently rewriting.

**C. Medium term (weeks)**
- **G1 lexicographic objective.** The big one. Solve target → fix as constraint
  with tolerance → solve floor → … Replaces 17 profiles with one model and
  returns the entire Stage-1 budget to a single well-guided search.
- G7 expose the 45 missing parameters.

**D. Major architectural**
- G10 split the module at its seams so the optimiser is testable alone.
- G9 interval-based break model.

**E. Experimental**
- LNS on the skeleton once G1/G2 land and there is budget left to spend.

**F. Not recommended**
- Metaheuristics (lose hard-rule guarantees), column generation (over-engineering
  at 5,880 vars), commercial solver migration (not the bottleneck).

---

## SECTION L — Quick wins

| Win | Effort | Expected |
|---|---|---|
| P-1 memoisation | **done** | 5.4× pre-solver, byte-identical |
| `symmetry_level=2` | 1 hour | unknown until measured; free to try |
| Symmetry-breaking constraints | 1 day | large on Chat/Voice (10¹⁷–10²³ factors) |
| Decision strategy | 1 day | faster first-solution, better incumbents |
| Deterministic budgets | 1 day | reproducibility — makes all other results trustworthy |

---

## SECTION M — Major upgrades

**The lexicographic rebuild.** Replace the 77-term sum with an explicit
hierarchy the business already states in words:

```
1. maximise intervals at target
2. subject to (1) within tolerance t1, maximise intervals at floor
3. subject to (2), minimise severe gaps and max consecutive gaps
4. subject to (3), minimise avoidable overage
5. subject to (4), maximise preference satisfaction and fairness
```

Each stage fixes the previous as a constraint. This is the epsilon-constraint
method — standard, and what the OR-Tools community recommends for exactly this
case. Benefits: magic weights disappear; the hierarchy becomes verifiable and
auditable; unsupported Pareto points become reachable; **17 profiles collapse to
one model**, returning ~90% of Stage-1 budget to a single guided search.

Risk: it changes candidate selection on every scenario, so it needs a frozen-
workbook baseline first. That is the same prerequisite as the RC9.1 comparison —
do them together.

---

## SECTION N — Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Lexicographic rebuild changes every result | Certain | High | Frozen-workbook A/B, twice each, before adopting |
| Symmetry breaking excludes a needed solution | Low | High | Break only within provably interchangeable classes; assert feasibility preserved |
| G5 bites a real client contract | Med (rises with live use) | High | Fix before any non-template workbook |
| Truncation masks improvement | Certain today | High | Deterministic budgets + G1/G2 |
| Reviewing without artifacts (this review) | Certain | Med | Every structural claim labelled as such |

---

## SECTION O — Coverage improvement potential

**I will not give a single number without an A/B run.** What I can bound:

- G3 alone means 13 of 15 configured strategies never execute. The realistic
  gain from running the full portfolio is *at least* the observed spread between
  profiles — which the project has already seen at 5–14 intervals on several
  scenarios.
- G1 makes currently-unreachable schedules reachable. Magnitude unknown,
  direction certain.
- G2 attacks 10¹⁷–10²³ redundancy on the two largest workbooks.

**Reasoned estimate, labelled as hypothesis:** mid-single-digit to low-double-digit
percentage of target intervals on the truncation-limited scenarios (Chat, Voice,
NMG EN). Confirm with the A/B in Section R. I would not put a number in a board
pack until that run exists.

## SECTION P — Utilization improvement potential

Currently near zero is being extracted, by construction: every utilisation term
is 6–9 orders of magnitude below coverage (Section F). A lexicographic hierarchy
would make fairness and preference *actually operative* for the first time —
from "mathematically inert" to "tie-breaking within the coverage-optimal set".
That is a step change in kind, not in percent.

---

## SECTION Q — What I would build differently today

**Keep:** CP-SAT, the two-stage decomposition, the release chain, the independent
validator, the identity/sealing discipline. That is genuinely good work.

**Change two things:**

1. **Objective as an explicit hierarchy from day one.** No weighted sum, no magic
   constants, no profile portfolio. The business states its priorities as a
   ranked list; the model should encode a ranked list.
2. **Model the workforce as classes, not individuals.** Solve over interchangeable
   groups and assign names afterwards. This removes the symmetry at the source
   rather than patching it, and it is how large WFM systems scale.

**Also:** deterministic budgets, and the optimiser as a separately testable module.

---

## SECTION R — Final verdict

> **Is RC5 the best practical scheduling engine for this project, or are
> meaningful improvements still available?**

**Meaningful improvements are still available, and they are large.**

RC5 is the best *release-engineered* build this project has produced, and the
release chain should not be touched. But the optimiser is not near its practical
optimum, and the evidence is unambiguous: a **5,880-variable** model that
**truncates at 2 of 15 strategies** after four hours is not solver-limited or
headcount-limited. It is limited by an objective with an **800,000,000:1** weight
spread and **6.2 × 10²³** unbroken symmetry.

Ranked:

| # | Improvement | Why it matters | Effort |
|---|---|---|---|
| 1 | **Lexicographic objective** | Removes inert weights, makes unreachable schedules reachable, collapses 17 profiles into 1 and returns the Stage-1 budget | ~1 week |
| 2 | **Symmetry breaking** | Attacks a 10²³ factor on your largest scenario | ~1 day |
| 3 | **Deterministic budgets** | Without it no result is reproducible, so nothing else can be measured | ~1 day |
| 4 | **Decision strategy** | Faster convergence on a now-tractable model | ~1 day |
| 5 | **G5/G6 contract coercions** | Silent wrong contracts the day a real client differs from the template | ~half day |

**If I owned this project, my next move would be:** freeze one workbook, run the
current engine on it twice as a baseline, then implement #2 and #3 (two days,
low risk) and run it twice again. That single A/B answers "how much is
truncation costing us" with real numbers — and it is the same frozen-workbook
setup the RC9.1 comparison needs. Only then commit to #1.

**Do not redesign the architecture.** The foundation is right. The objective is
what needs rebuilding.
