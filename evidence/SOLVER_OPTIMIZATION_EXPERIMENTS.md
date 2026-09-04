# Solver optimization — four experiments, and what they actually showed

Engine RC9.2.2 at commit `103d494` (sha `957ba84c…`) is the fallback baseline.
Every change was measured against it. **None of them earned its place.**

## Context: the run-to-run noise band

A33 established that this engine's coverage figures move by up to **6 intervals
between runs at a fixed seed**, because CP-SAT under a wall-clock limit with
multiple workers is not deterministic. Any difference smaller than that is not a
result. That threshold decides three of the four experiments below.

## 1. CP-SAT parameter sweep — NULL RESULT

Cricut Voice, `release_gate_floor_satisfaction`, 180s, seed 9000, 4 workers.
Voice was chosen because it plateaus at 250 whether given 150s or 450s, so it is
stuck rather than time-limited — the ideal probe for whether search is the
constraint.

| variant | before_target | before_floor |
|---|---|---|
| **baseline (as shipped)** | **237** | 257 |
| `linearization_level = 2` | 235 | 257 |
| `symmetry_level = 3` | 236 | 257 |
| `lin=2 + symmetry=3` | 235 | 257 |
| `repair_hint = True` | 238 | 257 |

Full spread: **3 intervals across all five variants**, floor identical in every
one. That is well inside the 6-interval noise band. **No parameter moved this
model.**

The symmetry hypothesis was the strongest of the four on paper — 40 largely
interchangeable associates is real symmetry — and it produced nothing. Either
CP-SAT's default detection already handles it, or the shift/OFF structure breaks
the symmetry before it can be exploited.

**Recommendation: change nothing.** Keep `linearization_level = 1`, default
symmetry, no `repair_hint`.

## 2. `primary_target_tolerance` 1 vs 3 — INCONCLUSIVE, and my simulation was wrong

The epsilon-constraint I proposed building **already exists** as
`--primary-target-tolerance`, set to 1 by the production runner. Simulating the
recorded NMG EN+SP leaderboard suggested raising it to 3 would admit a candidate
at 150/212 with 22.07 FTE overage instead of 153/203 at 29.96.

The real A/B, NMG EN+SP at 1500s, seed 9000:

| tolerance | before_target | after_target | before_floor | after_floor | overage FTE | extreme |
|---|---|---|---|---|---|---|
| **1 (current)** | 187 | **158** | 225 | **207** | **34.89** | **21** |
| 3 | 185 | 154 | 218 | 203 | 43.85 | 22 |

Tolerance 3 came out worse on every axis. **But this A/B is confounded and
cannot support that conclusion either.** `before_target` differs (187 vs 185),
and tolerance cannot affect Stage 1 — so the two runs diverged for reasons
unrelated to the parameter, i.e. solver nondeterminism. The 4-interval gap sits
inside the noise band.

**What my simulation got wrong:** it assumed the candidate pool is fixed and
only the final pick changes. It is not. The recommendation feeds joint
refinement, repair and polish, so changing it changes what gets explored
afterwards. A leaderboard replay cannot predict a live run.

**Recommendation: keep tolerance at 1.** Not because 3 is proven worse, but
because nothing here shows it is better, and the current value is the one every
released figure was measured with. A clean answer needs single-worker
deterministic runs or several seeds per arm.

## 3. Cricut Chat slack — FORCED, like NMG EN+SP

| | Cricut Chat | NMG EN+SP | Cricut Voice |
|---|---|---|---|
| slots with zero target slack | **302 of 484 (62.4%)** | 396 of 504 (78.6%) | 108 of 528 (20.5%) |
| break-quarters to place | 540 | 340 | 660 |
| lossless capacity | **336** | 112 | 902 |
| | **deficit 204 — FORCED** | deficit 228 — FORCED | surplus 242 |
| observed absorption | 3% | −25% | 97% |

**Both scenarios whose Gate 5 fails are arithmetically forced.** Cricut Chat
must place 540 break-quarters into 336 lossless slots; 204 have nowhere to go.
No scheduler and no solver parameter can create that capacity.

## 4. Balanced candidate export — kept

A42 remains. It is reporting only, changes no recommendation, and gives the
planner the frontier knee that the two extreme exports missed.

## Findings

* **The solver is not the bottleneck on these scenarios.** Five parameter
  variants moved before_target by 3 intervals total, inside noise.
* **The selector tolerance is not demonstrably mis-set.** The mechanism exists,
  and a leaderboard simulation is not evidence about a live run.
* **The two failing scenarios are staffing-limited, not search-limited.**
  Cricut Chat is short 204 break-quarters, NMG EN+SP short 228. Cricut Voice,
  with a surplus, absorbs 97% on the same engine.
* **The engine is at its practical ceiling for these inputs.** What remains is
  headcount, target ratio, or break structure — business decisions, not code.

## What would change the answer

* Several seeds per arm, or single-worker deterministic runs, to get below the
  noise band. Expensive and unlikely to overturn a 3-interval spread.
* A scenario with genuine slack that still underperforms. Cricut Voice has the
  slack and already absorbs 97%, so no such case exists in the current set.
