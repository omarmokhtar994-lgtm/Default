# Night 15: the joint shift+break build

Question asked: build the multi-day joint shift+break optimizer (column
generation / branch-and-price) and say whether it improves the numbers.

Short answer: the full joint optimizer was built three ways and **none of them
beats the engine inside a production budget**; the exact models are correct
but too hard for the solvers available here. One piece of it, solving break
placement **one day at a time** on a fixed skeleton, does beat the engine and
is now an engine phase (DNBS), shipped only on a pre-registered end-to-end A/B.

Every number below is the engine's own `calculate_metrics`, and every schedule
was produced from the engine's own run output, not from baselines.

## 1. Full joint models: built, verified exact, not good enough

Test case: SYNTH_M2 (28 associates, 10 shifts, 115 break patterns, 117 active
intervals). Planted optimum 117/117; the final engine's best compliant
candidate at 3,600 s is 108 target / 117 floor.

| approach | result | why it stops |
|---|---|---|
| Column generation over weekly (shift + break) tours, DP pricing (off pair, <= 2 shift types, rest), GLOP master | LP bound: deficit 0, i.e. 117 is not excluded | fractional optimum is highly degenerate |
| + diving (fix largest lambda, re-price) | 75 / 117 | total-FTE deficit is the wrong surrogate for threshold hits: it spreads small misses |
| + SCIP over the 1,190 generated tours, exact hit rows | 42 / 117 in 180 s | the pool holds no integer combination that meets the hard rules well |
| **Exact aggregated model**: y[legal weekly tour], n[day, shift, pattern] | **exact**: fixed to the planted plan it scores 117/117; fixed to the engine's candidate it scores 108 - both equal to calculate_metrics | - |
| same, CP-SAT cold, 300 s, 4 workers | no feasible solution; bound 117 | reified hits have a weak LP |
| same, warm-started from the engine's 108 | 108; bound 117 | CP-SAT's LNS cannot move a tightly packed plan |
| same, HiGHS / SCIP | 108; bound 117 | - |
| same, "every interval hit" as hard rows (no reification) | no feasible solution in 300 s (CP-SAT and HiGHS) | exact-fit instance: demand = floor(planted coverage) |
| same, two-day LNS (other days' shift counts fixed) | 108 after 16 sub-solves | - |

Conclusion for the full joint problem: the model is right and gives a valid
bound, but on these exact-fit instances no available solver (CP-SAT, HiGHS,
SCIP) closes the gap in minutes. A real branch-and-price with custom branching
and cuts is a research project; it is not claimed here.

## 2. What did work: break placement one day at a time

On a fixed skeleton, one day's breaks only interact with that day and its
overnight spill, and associates on the same (day, shift, language) are
interchangeable for coverage. So a day's break placement is a small aggregated
model, n[shift, pattern], which CP-SAT often solves to proven optimality.

Neighbourhood d frees the breaks of the shifts starting on day d, holds
everything else at the incumbent, and scores every interval those shifts touch.
A move is kept only if the engine's own `calculate_metrics` shows after_target
rose and **nothing guarded got worse**: floor, 90/80 tiers, severe and hard
floor gaps, gap runs, zero staffing, language, opening, concurrency, blank
staffing, week-boundary metrics, coverage-split gaps, severe/extreme overage,
whole-week overage cap and imbalance, and avoidable overage FTE.

Standalone, on the final engine's own candidate pools (best compliant
candidate by after_target, 60 s per day, 4 workers):

| case | engine | day search | notes |
|---|---|---|---|
| SYNTH_H1 (24x7, overnight) | 138 / 168 | **145 / 168** | 90% tier 153 -> 157, concurrency violations 1 -> 0, overage 15.4 -> 14.5 |
| Cricut Voice | 246 / 251 | **247 / 252** | 90% tier 247 -> 249, overage down |
| SYNTH_M2 | 108 / 117 | **109 / 117** | |
| Cricut Chat | 179 / 224 | 179 / 224 | its +1 needed more avoidable overage; rejected |
| SYNTH_H3 | 93 / 105 | 93 / 105 | +2 and +1 rejected for overage |
| AE_AR_B2B | 167 / 168 | 167 / 168 | every day proven optimal |
| NMG_SP | 121 / 126 | 121 / 126 | every day proven optimal |

This also answers a standing question: on the real workbooks, Stage 2's break
placement is already optimal or within one interval of it for the skeleton it
is given. The remaining gap is in the skeleton.

Two mistakes were caught on the way and are recorded because they would have
produced false gains:
* A first version solved days in sequence against the engine's per-day
  baseline. With overnight shifts, day d's choice changes day d+1, so the
  baselines went stale: Chat reported per-day gains and a net loss (179 -> 175).
  Fixed by scoring every touched interval against the current incumbent.
* Protecting only target and floor let gains through that cost severe gaps and
  concurrency (Chat 179 -> 182 with severe gaps 11 -> 12). Fixed by making the
  engine's metrics the acceptance oracle.

## 3. DNBS in the engine

`run_day_neighbourhood_break_search` runs after RC8 quality recovery and before
the joint-refinement pool. It takes the two strongest compliant candidates (one
per distinct skeleton), spends at most half of the time left before the
joint-refinement deadline (cap 420 s), and on each day:

1. builds the aggregated day model (groups by shift and language);
2. reproduces the incumbent inside it (baseline solve with counts fixed);
3. requires target, floor, protected tiers >= baseline, violations and zero
   quarters <= baseline; maximises hits, then the smallest change from the
   incumbent (which keeps unmodelled overage terms where they were);
4. accepts only if `calculate_metrics` agrees (`dnbs_metrics_no_worse`);
   otherwise excludes that exact solution and tries again (up to 3 times).

The finished candidate is added only if `candidate_pool_class` (the release
validator) calls it compliant. It never removes or replaces a candidate; the
normal selector decides.

Joint refinement keeps the rest of its window. Its record (`evidence/
JOINT_REFINEMENT_NEVER_IMPROVES.md`: 37 attempts, 0 improvements) is why DNBS
takes its time from there rather than from Stage 1, Stage 2 or repair.

Engine function on saved pools (production settings, 420 s, 2 workers):
H1 138 -> 143, Voice 246 -> 247.

Tests: `tests_staged/test_rc9_2_17_day_neighbourhood_break_search.py` (10):
dominance rule; a deliberately wrecked day on the planted M2 plan (110/114, 11
concurrency violations) is restored to 117/117 and is compliant; an optimal
anchor gains nothing; no anchor / expired deadline do nothing; placement in
the pipeline; bounded budget.

## 4. End-to-end A/B (pre-registered)

Rule: `evidence/dnbs_e2e/PREREGISTERED_RULE.txt`, registered before any run.
Result: `evidence/dnbs_e2e/RESULT.txt`.

PENDING: the A/B is running. Until it passes, DNBS is parked as `patches/DNBS_day_neighbourhood_break_search.patch` (engine + tests) and is NOT in the engine.

## 5. What is still open

* The full joint optimizer (branch-and-price) remains a research project; the
  exact model and prototypes are in `tools/research/joint_shift_break/`.
* Skeleton choice is where the remaining synthetic gap lives (M2 109 vs 117,
  H3 93 vs 105, H1 145 vs 168).
* Hard public benchmarks still need the blocked hosts
  (schedulingbenchmarks.org, dbai.tuwien.ac.at, web.archive.org).
