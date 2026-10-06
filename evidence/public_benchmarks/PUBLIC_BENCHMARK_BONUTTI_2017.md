# Public benchmark: Bonutti et al. (2017) shift-design instances through the engine

Status: 10 of 11 cases complete; R7 skill 3 pending (this file is updated when it lands).

## Why this set

NIGHT_14 wanted the hard public sets (schedulingbenchmarks.org, TU Wien's
shift-design and break-scheduling sets). Those hosts are still blocked by the
network policy (checked 2026-10-06 with both the shell and the web fetcher).
The same research group's multi-skill shift-design set is reachable on
Bitbucket: Bonutti, Ceschia, De Cesco, Musliu & Schaerf, "Modeling and solving a
real-life multi-skill shift design problem", Annals of OR 252(2):365-382,
2017; https://bitbucket.org/satt/shift-design @ e3d4bf6. It is the closest
public match to a call-centre week: 15-minute requirements over a cyclic week,
shift types with start and length windows, one break per shift with placement
margins, requirements net of breaks, proven optima for R1-R10, and the authors'
C++ validator. Copies are kept in `bonutti_2017/` for reproducibility.

## Translation (details in `tools/public_shift_design_suite.py`)

* One engine workbook per skill (the instance separates exactly per skill).
* Demand = whole people per 15-minute slot, shrinkage 0, Target 100%.
* Shift library = every start and length on a 30-minute grid inside each type's
  windows; every shift of the published optimum is checked to be in it.
* Breaks: one 60-minute break; the type's distances from shift start and end
  become the engine's break edge margin and lunch earliest offset. The parsed
  break windows match the benchmark's rule slot for slot.
* Translated: R1, R5, R6, R7, R10. Not translated: R2, R3, R4, R8, R9, whose
  optima need two break rules at once (30-minute breaks with 60-minute margins
  beside 60-minute breaks with 120-minute margins, or no-break shifts beside
  a break type). The engine accepts one break rule per workbook: a real
  feature gap, recorded.
* Roster: the benchmark sizes daily shift counts freely (workers take 4-5
  duties, any days off). The engine plans 5-day tours with two adjacent OFF
  days, 12 h rest and at most 2 different shifts. For each case the smallest
  roster with a 100% plan under those rules was proven with an exact,
  aggregated CP-SAT model (no engine code): OPTIMAL at N, INFEASIBLE at N-1.
  Last Saturday's shifts are the published optimum's Saturday nights.

## Results (production settings: QUICK 3,600 s, 2 workers, seed 9000)

`ceil` = duties in the published optimum / 5; `N` = proven minimum full-cover
roster under the engine's rules (the roster the engine was given); a 100% plan
exists at N for every case. Engine = the engine's own metric, intervals at
target before / after breaks (non-cyclic week with carry-in). Cyclic = the same
schedule scored cyclically, as the authors' validator does; under / over are
understaffed and overstaffed slot-units.

| Case | ceil | N | Active | Engine before / after | Cyclic hit | Under / over | Validator | rc |
|---|---|---|---|---|---|---|---|---|
| R1 skill 1 | 24 | 28 | 602 | 554 / 554 | 552 (91.7%) | 98 / 764 | PASS | 0 |
| R1 skill 2 | 30 | 33 | 602 | 468 / 466 | 444 (73.8%) | 508 / 884 | PASS | 0 |
| R5 skill 1 | 34 | 38 | 630 | 546 / 545 | 545 (86.5%) | 280 / 860 | PASS | 1 * |
| R5 skill 2 | 45 | 48 | 630 | 524 / 524 | 524 (83.2%) | 238 / 748 | PASS | 1 * |
| R6 skill 1 | 38 | 40 | 644 | 526 / 526 | 534 (82.9%) | 366 / 716 | PASS | 0 |
| R6 skill 2 | 45 | 47 | 644 | 536 / 533 | 537 (83.4%) | 432 / 786 | PASS | 0 |
| R7 skill 1 | 36 | 38 | 630 | 448 / 448 | 450 (71.4%) | 582 / 654 | PASS | 0 |
| R7 skill 2 | 32 | 35 | 630 | 518 / 518 | 518 (82.2%) | 314 / 656 | PASS | 0 |
| R7 skill 3 | 31 | 34 | 630 | pending | pending | - | - | - |
| R10 skill 1 | 19 | 21 | 504 | 294 / 292 | 306 (60.7%) | 556 / 740 | PASS | 0 |
| R10 skill 2 | 18 | 20 | 504 | 314 / 308 | 320 (63.5%) | 456 / 646 | PASS | 0 |

The authors' validator, run on the engine's merged weeks, reproduces the
under/overstaffing sums exactly: R1 606 / 1,648, R5 518 / 1,608, R6 798 /
1,502, R10 1,012 / 1,386 slot-units (published optima: 0 / 0).

\* R5: the engine finished (exit 0, validator PASS); the packager refused
because the engine file was edited mid-run (Phase D3a commit) and its identity
check caught the mismatch. Both cases are rerun on the current engine.
Recorded in `evidence/phase_d/D_PLAN.md` (incident log).

## What it shows

1. **Always valid.** Every published schedule passes the engine's independent
   validator; no refusal, no hard failure.
2. **Far from optimal on these instances: 61-92% of a provably reachable 100%.**
3. **The loss is in choosing shifts and days off, not in breaks.** Before and
   after breaks differ by 0-6 intervals in every case; the skeleton itself is
   short.
4. **The metric is not the problem (D2a).** Given the proven-perfect week, the
   engine's own `calculate_metrics` scores it 602/602 (R1 skill 2) and 504/504
   (R10 skill 1) with 0 break-cap violations. The shortfall is search.
5. **A concrete cause on these instances (D3a).** The engine's aggregate
   day/shift-count guide refused every case here because the shifts are not all
   540 minutes. Phase D3a makes it optional for mixed lengths; its A/B is
   pre-registered and queued.
6. **Relevance to real programs is limited and was measured.** These instances
   offer 90-141 shift options; the 7 real programs offer 1-24, all 9 h, and
   the guide already runs on them. AE_AR_B2B's ceiling is 168/168 and the
   engine reaches 167.

## Engine rules versus the benchmark

The engine's own week rules cost 2-4 people per case against the benchmark's
free daily counts (`N` vs `ceil`). That is a property of the rules (two
adjacent OFF days, 12 h rest, at most 2 different shifts), proven exactly,
not an engine weakness.
