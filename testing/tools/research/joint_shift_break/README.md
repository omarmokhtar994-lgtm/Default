# Joint shift + break research prototypes

Not part of the engine. Kept so every number in
`evidence/NIGHT_15_JOINT_SHIFT_BREAK_BUILD.md` can be re-run. Each script loads
the engine by path and scores its result with the engine's own
`calculate_metrics`.

| script | what it is | outcome on SYNTH_M2 (optimum 117, engine 108) |
|---|---|---|
| `column_generation_dive.py` | Column generation over weekly (shift, break) tours with DP pricing, diving, then SCIP over the generated tours | LP bound 117; integer recovery 75 (dive) / 42 (SCIP) |
| `aggregated_exact_cpsat.py` | Exact aggregated model: legal weekly tours x (day, shift, pattern) counts. Modes: planted/engine fixed, warm start, two-day LNS, `--allhit`, `--day=`, `+mfix`, `+dfree` | Exact (planted 117 and engine 108 reproduced), but no solver improves 108 in 300 s |
| `aggregated_exact_mip.py` | Same model on HiGHS / SCIP | Same: 108, bound 117 |
| `day_neighbourhood_standalone.py` | Break-only day-neighbourhood search on a fixed skeleton from a saved candidate pool | 108 -> 109; H1 138 -> 145; Voice 246 -> 247. Became the engine's DNBS phase |
| `pool_to_hint.py` | Best compliant candidate of a run -> hint JSON for the aggregated models | - |

Usage examples:

```
python3 aggregated_exact_cpsat.py engine/_tools/l632_universal_scheduler.py \
    fixtures/synthetic_suite/SYNTH_M2_MULTI_START_WITH_BREAKS.xlsx 60 4 "" planted_fix
python3 day_neighbourhood_standalone.py engine/_tools/l632_universal_scheduler.py \
    <input.xlsx> <run>/debug/CANDIDATE_POOL_CHECKPOINT.json 60 4 1
```
