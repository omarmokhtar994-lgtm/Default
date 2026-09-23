# Final state

## The headline

The two engine lineages are **merged**. `engine/` now carries both the
L6.3.2.6 Coverage Split work and the L6.3.2.7 RC5 hardening, verified by
marker count on both sides and by a real end-to-end run. The gate went from
**9 suites to 17**, plus a new static check that catches the exact class of
defect the merge introduced.

## Every item that was open, and where it landed

| # | item | outcome |
|---|---|---|
| 1 | **Merge `candidates/` into `engine/`** | **DONE.** Real 3-way merge against ancestor `93ab7f8`. 6 conflicts in the scheduler resolved by hand, 5 further files merged clean after a real run exposed that I had under-scoped the first pass. Both lineages verified present at full marker count. |
| 2 | **Stage-2 never searches** | **FIXED (partially, measured).** The anchor may no longer eat the last fundable attempt. On the recorded Chat case 135s → 97s, leaving exactly 180 = one real attempt instead of none. Inert where the phase is roomy or too small. |
| 3 | `min_target_hits` vs `after_target` | **CLOSED.** Measured across all 242 demanded intervals: the model threshold is stricter on 242, looser on 0. A lock at N *does* force `after_target ≥ N`. NIGHT_06's proof stands; my retraction of it was the error. Pinned by test. |
| 4 | `language_reserve` validator | **BUILT.** Independent recomputation of the reserve tier, reusing the after-break eligible count and the engine's own tier helpers. 10 tests, mutation-checked twice (the first version passed under mutation and was strengthened to an AST check). |
| 5 | Non-monotonicity | **NOT A DEFECT, as far as the data goes.** Raw corpus says 287/1469 pairs, but those mix workers, seeds and builds. Controlled: Chat +5, GDI +9, Voice −1. The single −1 is the size of known multi-worker noise. |
| 6 | Never-executed skeleton strategies | **MEASURED: five, not six, for two different reasons.** 2 are never requested by the runner (dead by configuration), 3 are requested but lose to the Stage-1 budget tail. Neither fixed, with reasons. |
| 7 | Joint refinement at DEEP | **CLOSED.** `VOICE_DEEP` allocates 5040s, records `enabled: true`, `status: PENDING`, 0 attempts. Across 54 runs ≥3600s: 0 attempts, 0 improvements. It is not merely ineffective at DEEP — it never runs. |
| 8 | `skill_allocation` validator | **DELIBERATELY NOT BUILT.** 0 of 9 corpus workbooks configure it; there is nothing to validate against. |

## Two defects found *because* of this work

1. **The merge shipped a caller and callee from different lineages.**
   `build_global_budget_plan(diagnostics=...)` against a definition without
   that parameter. Every suite and both selfchecks passed — none enter
   `run_case` — and ruff cannot see it because the *name* resolves. A real
   1800s run died on the first call. Now caught statically in under a second
   by `tools/check_cross_module_calls.py`, verified against the real bug.

2. **The gate was passing over tests it never ran.** `run_tests.sh` globbed
   one filename pattern, so 7 suites sat unexecuted. Wiring them in exposed
   two stale pins that asserted already-fixed defects were still present.

## Corrections made to my own earlier claims

* The probe's printed `VERDICT: WEIGHTING DEFECT` — **void**. Neither arm
  proved optimality and arm A's answer was feasible for arm B.
* My retraction of NIGHT_06 — **itself retracted**, on measurement.
* A joint-refinement scan using the wrong audit key — **discarded, not
  published**.
* "Six never-executed strategies" — **five**, with two distinct causes.

## Verification

* Gate: **PASS — 17 suites + 2 selfchecks + cross-module call signatures +
  undefined-name sweep.**
* Every behavioural change mutation-checked, with the source restored
  byte-identical afterwards and that restoration verified by `diff`.
* No assertion was weakened to obtain a pass. Where a test failed because the
  engine had improved, the pin was moved to the *new* contract and a negative
  test added alongside it.

## End-to-end verification

`MERGED_AR` -- AE_AR_B2B, 1800s, `--num-workers 1` (reproducible), seed 9000,
on the fully merged engine:

| metric | baseline (pre-merge) | merged engine |
|---|---|---|
| `before_target` | 166 | **166** |
| `after_target` | 165 | **165** |
| `before_floor` | 168 | **168** |
| `after_floor` | 167 | **167** |

**The merge changed no schedule.** Four for four against the pre-merge
deterministic result, on a run that exercises the whole pipeline rather than
the selfchecks.

### The anchor cap on this case is inert, by design

| | `MERGED_AR` (no cap) | `CAP_AR` (cap) |
|---|---|---|
| phase remaining at anchor | 399.5s | 401.1s |
| anchor granted | 135.0s | **135.0s** |
| real adaptive attempts | 1 | 1 |

The cap only binds when the anchor would consume the last fundable attempt.
Here the phase had ~400s, so 135 already left ~265 -- comfortably over the
180s floor -- and `min(135, 401 - 180)` is still 135. AE_AR_B2B therefore
demonstrates that the cap is **safe**, not that it **works**.

The case it was built for is Cricut Chat, where the phase had 277s and the
adaptive search ran 0 of 168. That test is running separately and is judged
on `attempts_completed`, not on a coverage number -- four workers are
nondeterministic and one run cannot settle a coverage delta.
