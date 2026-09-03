# Stage-1 slice depth probe — what a skeleton profile returns per second of search

**Why this exists.** Every RC9.2.1 run recorded in this project pinned every
Stage-1 attempt to the same 45.0-second slice. Nothing in the project measured
what a profile produces when it is actually given time, so the minimum slice
could not be chosen from evidence. This probe calls `build_skeleton` directly
at a range of time limits — same workbook, same profile, same seed, same worker
count — and records before-break coverage for each.

**Method.** `tools/stage1_slice_depth_probe.py`: `parse_input`, then
`build_skeleton(parsed, profile, HardConfig(hard_floor=…), slice_sec, workers=2,
random_seed=0)`, then `calculate_metrics` on the returned skeleton. No Stage 2,
no repair, no selection — this isolates the one variable.

Engine: `L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1`.
OR-Tools 9.15.6755. Inputs: `AE_AR_B2B.xlsx`,
`Cricut_Voice_RC9_1_READY_SKELETON.xlsx` (the Colab gate package copies).

## Results

`before_target` / `before_floor`, before breaks. `—` = no skeleton returned.

| Scenario | Profile | 45s | 150s | 210s | 450s | RC9.1 baseline |
|---|---|---|---|---|---|---|
| AE AR B2B | `target90_restore_champion` | UNKNOWN — | 101 / 130 | — | **167 / 168** | 168 / 168 |
| AE AR B2B | `before_target_champion` | UNKNOWN — | UNKNOWN — | **166 / 168** | **166 / 168** | 168 / 168 |
| Cricut Voice | `target90_restore_champion` | 248 / 252 | 250 / 252 | — | 250 / 252 | — |
| Cricut Voice | `floor_gate_hunter_before` | 238 / 258 | 238 / 258 | — | 236 / 258 | 256 / 264 |

## What the numbers say

**1. 45 seconds is not a short attempt on AE AR B2B; it is no attempt.**
Both profiles return `UNKNOWN` — CP-SAT found no feasible skeleton at all.
The 131/159 that RC9.2.1 published for this scenario did not come from Stage 1;
Stage 1 produced nothing and a downstream fallback carried the run.

**2. The AE AR B2B gap is a depth gap, and it very nearly closes.**
`target90_restore_champion` goes UNKNOWN → 101 → **167** across 45s → 150s →
450s. RC9.1's recorded figure is 168. Same engine, same model, same constraints
— the only variable is how long the solver was allowed to run.

**3. Profile choice does not explain AE AR B2B.** At 450s the two profiles land
within one interval of each other (167 and 166). The earlier reading — that
RC9.2.1 lost 37 intervals because RC9.1's champion profile
(`before_target_champion`) was skipped for budget — is **not supported**: given
equal depth, the profile that did run reaches the same place. No portfolio
reordering was made on the strength of it.

**4. Cricut Voice plateaus below its RC9.1 baseline.** `target90_restore_champion`
reaches 250 at 150s and does not improve at 450s. `floor_gate_hunter_before` —
the profile RC9.1's baseline names as the Voice champion — sits at 236–238 at
every depth, trading target coverage for floor coverage (258 floor at all three
depths). Depth funding is worth roughly +4 target intervals here (the recorded
run scored 246), not the +10 that would reach 256.

That leaves the Voice baseline row unexplained by search budget. It is also the
one row in `RC9_1_BASELINE.json` sourced from a *"preserved workbook
leaderboard"* rather than a candidate replay — a leaderboard is a best-of-pool
figure, which is not effort-comparable to a single run. This is recorded as an
open question, not as a solved one.

**5. There is a cliff, and it is narrow.** `before_target_champion` on AE AR
B2B returns nothing at 150s and 166/168 at 210s — and 450s returns the same
166. The useful range is not "as long as possible"; it is "past the cliff".

## What was set from this

`STAGE1_MIN_MEANINGFUL_SLICE_SEC = 240.0` in `l632_universal_scheduler.py`.
The measured cliff on the hardest scenario in the regression set sits between
150s and 210s. 240s clears it with margin, and the flat 210s/450s result says
spending more than that per profile buys nothing — better to spend it on the
next profile.
