# Overnight fact #2: the relative-gap lever would never fire. I was wrong.

Mined from **167 solver-telemetry records** — the instrumentation added
yesterday, now paying for itself by killing one of my own proposals.

## What I claimed earlier

After seeing a single Stage-1 solve on AE_FR_Choice sit at

```
objective 26,211,272   bound 26,211,120   gap 152   (0.00058% relative)
slice_utilisation 1.0
```

I wrote that "a relative-gap stop rule would return roughly 40 of those 45
seconds with no measurable quality cost", and built `relative_gap_limit` on
that basis.

**That was one observation generalised into a lever.**

## What the corpus actually says

| | |
|---|---|
| solves with telemetry | 167 |
| consuming >=99% of their slice | **106 (63%)** |
| of those, reporting objective and bound | 103 |
| **median relative gap** | **88.93%** |
| min / max relative gap | 14.39% / 100.00% |

Would a gap stop ever fire?

| threshold | solves that would stop early |
|---|---|
| 1e-6 | **0 / 103** |
| 1e-5 | **0 / 103** |
| 1e-4 (CPLEX/Gurobi default) | **0 / 103** |
| 1e-3 | **0 / 103** |

**Not one solve, at any threshold.** The tightest solve in the entire corpus is
at 14.4%, four orders of magnitude away from the loosest threshold tested. The
0.00058% case was an outlier, not a representative.

## The correction

`relative_gap_limit` remains at 0.0 (off), which is still the right setting --
but **not for the reason I gave**. I argued it was unsafe because this
objective's 400,000,000:1 tier structure means epsilon in objective space does
not bound coverage loss. That argument stands on its own, but it is beside the
point: the lever would never activate regardless.

The earlier "returns ~40 of 45 seconds" claim is **retracted**. It is not
supported by anything except the single solve it came from.

## What the number actually reveals, and it is more useful

A median relative gap of **88.9%** means the solver finishes with almost no
idea how good its answer is. The bound barely moves. That is consistent with
two other measured facts:

* `branches_per_conflict` reaching **3,846 / 9,920 / 17,913 / 30,690 / 73,797**
  across these same solves. A search generating tens of thousands of branches
  per conflict is enumerating, not learning.
* B-5 measured the objective at **400,000,000:1 across 14 tiers**, which
  degrades CP-SAT's LP relaxation -- the mechanism that produces a bound.

So the engine is not time-starved in the way a gap stop would fix. It is
**bound-starved**: weak relaxation gives a weak bound, a weak bound gives no
pruning, no pruning gives enumeration, and enumeration consumes the whole slice
every time.

## The lever this points to instead

**Test B-5 for solve speed.** B-5 was measured and correctly closed for
*coverage* -- priority comes from lexicographic selection and hard constraints,
not the weights, so the conditioning costs no coverage. It was **never tested
for speed**, and the three facts above all point at it.

Cheap decisive test: rescale the objective coefficients into a narrow range,
same model, same seed, and compare time-to-first-solution and the bound
trajectory. If the bound tightens, everything downstream improves -- including,
finally, making an early-exit rule possible.

## Also recorded

`num_fixed_booleans` is ~0 on nearly every solve, so presolve is not fixing
variables at construction. The "fix variables at build time" optimisation from
the CP-SAT literature has nothing to bite on here. One exception:
`Cricut_Voice records[0]` shows 318 of 3903 booleans fixed (8%), which is the
fixed-request workbook -- consistent with the Voice finding.
