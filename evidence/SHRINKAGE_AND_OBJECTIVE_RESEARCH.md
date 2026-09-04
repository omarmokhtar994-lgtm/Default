# Scheduling research — shrinkage treatment and objective design

External research against the actual engine code and the real workbooks.
Scheduling perspective only.

## A. Shrinkage — RESOLVED: the engine is correct

### What the engine does

Requirement is grossed up by shrinkage to get scheduled headcount
(`whole_week_raw_requirement`, and the same shape throughout):

```
staffing_requirement = ceil( requirement x target_ratio / (1 - shrinkage) )
```

That is exactly the industry-standard conversion from *agents needed on the
phone* to *agents that must be scheduled* — Erlang output divided by
(1 − shrinkage). **This part is correct and is not double-counted.**

### Where the risk is

In `calculate_metrics`, after-break staffing is computed as:

```python
after_raw  = before_raw - break_count_actual   # agent physically removed
after_sum += after_raw * eff_factor            # then shrinkage applied again
```

`eff_factor = 1 - shrinkage`. So an agent on a break is removed from the
headcount **and** the remaining headcount is discounted by the shrinkage
factor.

Whether that is correct depends entirely on one business fact:

**Reading A — the Shrinkage sheet EXCLUDES breaks** (absence, training,
meetings only). Then removing the agent and applying shrinkage are two
different things and **the engine is right**.

**Reading B — the Shrinkage sheet INCLUDES breaks and lunch**, which is the
standard industry definition ("the percentage of paid time agents are
unavailable… includes breaks, lunch, training, meetings", industry average
25–35%). Then break time is counted twice: once physically, once through the
factor. **The engine understates after-break productive capacity.**

### What the real workbooks suggest — inconclusive, and it differs by scenario

| Workbook | Shrinkage | Break time per shift | Note |
|---|---|---|---|
| AE AR B2B | **17.0% flat**, all 168 active intervals | 60 min of 540 = **11.1%** | 17% sits *below* the 25–35% industry band, which is weak evidence it may be break-exclusive (Reading A) |
| NMG EN+SP | mean **24.6%**, range 13–50% | 60 min of 540 = 11.1% | inside/above the industry band, more consistent with Reading B |

If Reading B holds for AE, the after-break effective factor should be about
`1 - (0.17 - 0.111) = 0.94` rather than `0.83` — roughly **13% of productive
capacity understated after breaks**, which would inflate every after-break
target loss the gates are currently failing on.

### Conclusion — RESOLVED

**The business states the Shrinkage sheet is out-of-office, not breaks.** That
is Reading A. **The engine is correct and there is no double-count.** No change
is needed, and the after-break losses in the gate reports are real coverage
losses rather than measurement artifacts.

### The consequence that matters more

Because shrinkage excludes breaks, the requirement gross-up budgets for
out-of-office but **not** for break time. Break minutes must therefore be
absorbed out of the same scheduled headcount. Break time is
`60 min / 540 min = 11.1%` of a shift, so **about 11% of coverage is
structurally at risk in every scenario**, and avoiding it is precisely the break
stage's job — place breaks in troughs, stagger them, keep them off peaks.

Measuring how much of that structural cost each run actually avoided:

| Scenario | structural break cost | actual target loss | **absorbed by break placement** |
|---|---|---|---|
| CRICUT_VOICE | 11.1% | 1 / 264 = 0.4% | **97%** |
| AE_AR_B2B | 11.1% | 6 / 168 = 3.6% | **68%** |
| CRICUT_CHAT | 11.1% | 26 / 242 = 10.7% | **3%** |
| NMG_EN_SP | 11.1% | 35 / 252 = 13.9% | **−25%** |

This is the clearest quality signal in the whole batch.

* Cricut Voice absorbs **97%** — the break stage is capable of doing this job
  nearly perfectly on a real workbook.
* Cricut Chat absorbs **3%** — break placement achieves essentially nothing.
* NMG EN+SP is **−25%**: the loss is *larger* than placing breaks blind would
  cost. Break placement is actively harming coverage there.

Because Voice proves the machinery works, Chat and NMG EN+SP are **not** a
capacity limit and **not** a measurement error. They are a break-placement
failure on those two workbooks.

NMG EN+SP also recorded **18 break-concurrency violations** — breaks clustering
rather than staggering, which is exactly the "lunch problem" the industry
literature names, and exactly what would produce a worse-than-blind result.

## B. Objective design — the selector behaviour is textbook, which is the problem

The NMG EN+SP selector finding (winner beats the alternative on after90 by 3
and loses on seven other metrics, including 9 after-break floor intervals and
7.89 FTE of avoidable overage) is not a bug in the ranking code. It is the
defining property of a strict lexicographic objective:

> "Lexicographic optimization presumes that the decision-maker prefers even a
> very small increase in the first objective to even a very large increase in
> others."
> — Lexicographic optimization, Wikipedia

CP-SAT supports lexicographic objectives directly, and the literature notes the
known drawback plainly: lexicographic methods have "evident drawbacks, above
all regarding the identification of compromise non-dominated solutions that
represent a trade-off between two or more objectives".

So the engine is doing exactly what a strict lexicographic model does. The
question is whether that assumption matches the business: is three intervals at
the 90% tier genuinely worth nine floor-covered intervals after breaks?

### What the literature does instead

The common personnel-scheduling formulation is **two-level, not fully strict**:
minimise maximum understaffing first, then minimise a **weighted sum of
understaffing and overstaffing** — i.e. the top tier is protected, and the
remaining objectives are traded against each other rather than ranked.

### Applicable options, in order of risk

| Option | Method | Applies here | Risk |
|---|---|---|---|
| **Epsilon-constraint on the trade** | keep after_target primary but forbid a candidate that loses more than N floor intervals to gain one target interval | directly answers the NMG EN+SP case; smallest possible change | low — only removes pathological trades |
| **Weighted tail** | keep the top tier lexicographic, replace the lower tiers with a weighted sum of floor, overage and tier breadth | matches the standard formulation in the literature | medium — changes selection on every scenario |
| **Pareto surfacing** | already partly present (`MAX_TARGET_CANDIDATE`, `MAX_FLOOR_CANDIDATE` exports); surface the non-dominated set and let the planner choose | zero solver risk, pure reporting | very low |

**Recommendation: epsilon-constraint first**, because it is the only option
that fixes the demonstrated defect without moving selection on scenarios that
are currently fine. The weighted tail is the better long-term formulation but
needs a controlled experiment across all scenarios and a baseline, which this
project does not yet have.

## C. Break placement — the engine's two-stage design matches practice

The industry frames break placement as its own constrained problem, and names
exactly the failure this engine measures: the "lunch problem", where a
well-staffed centre becomes dramatically understaffed because breaks cluster in
a narrow window. Standard mitigations are staggering breaks across the team and
avoiding peak intervals.

The engine already models this: `Maximum Concurrent Break Ratio` (0.3),
`Maximum Concurrent Breaks` (4), break spacing rules, and it reports
`break_concurrency_violations`. NMG EN+SP recorded **18** such violations
alongside its 35-interval target loss, so the guard is measuring the right
thing but is configured as a **warn**, not a constraint
(`Break Concurrency Gate Mode = Warn`).

**This is now the leading P1.** On the one scenario whose break placement is
worse than blind (−25% absorbed), the concurrency rule that exists to prevent
break clustering is set to warn rather than enforced, and it recorded 18
violations. The mechanism, the measurement and the disabled guard all agree.

Cheap to test: set `Break Concurrency Gate Mode` to fail on NMG EN+SP alone and
compare absorbed-cost against the 24.6%-shrinkage baseline. No engine change
required to run the experiment — it is a workbook cell.

## D. Where RC9.2.1 stands against common practice

| Area | Verdict |
|---|---|
| Interval coverage, target/floor tiers | **similar** — tiered coverage with a protected floor is standard |
| Shrinkage gross-up of requirement | **similar** — matches the standard formula |
| Two-stage shift-then-break | **similar** — standard decomposition |
| Break concurrency / staggering | **similar** modelling, **weaker** enforcement (warn, not hard) |
| Objective hierarchy | **weaker** — strict lexicographic where the literature uses protect-then-weight |
| Feasibility diagnostics | **better** — proven minimum-exception bounds per skeleton are more than most published formulations carry |
| Multi-skill / language | **unassessed** — no interval-level language audit done yet |

## Sources

- Lexicographic optimization — https://en.wikipedia.org/wiki/Lexicographic_optimization
- CP-SAT docs — https://developers.google.com/optimization/cp/cp_solver
- OR-Tools CP-SAT README — https://github.com/google/or-tools/blob/stable/ortools/sat/docs/README.md
- Lexicographic multi-stage staffing, emergency call centres — https://www.researchsquare.com/article/rs-9744201/v1
- Hospital call-centre manpower scheduling, multi-objective multi-stage — https://www.tandfonline.com/doi/full/10.1080/24725579.2023.2202424
- Multi-objective personnel scheduling with customer and staff requests — https://www.sciencedirect.com/science/article/abs/pii/S0305048322001293
- Contact-centre shrinkage calculation — https://www.callcentrehelper.com/how-to-calculate-contact-centre-shrinkage-90353.htm
- Agents required in a contact centre — https://www.callcentrehelper.com/how-to-calculate-the-number-of-agents-required-206886.htm
- Shrinkage definition — https://www.platform28.com/glossary/shrinkage
- Call-centre shrinkage — https://www.givainc.com/blog/call-center-shrinkage/
- Call-centre scheduling components — https://www.givainc.com/blog/call-center-scheduling/
