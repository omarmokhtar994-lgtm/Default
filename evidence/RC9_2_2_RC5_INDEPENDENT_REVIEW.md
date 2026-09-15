# RC5 — independent review (RC4 → RC5)

No code changed, per the brief. Everything below was produced by executing the
shipped RC5 code.

---

## 1. Executive verdict — **split decision**

**RC5 is the better engine, and it is the first build to fix both frozen
blockers.** I re-ran my own reproductions against it:

- **F1 (selector guard collapse) — FIXED.** The exact three-candidate pool that
  made RC2 and RC4 revert to target-first now selects the protected-correct
  candidate.
- **F2 (language working window) — FIXED.** Start-only semantics; the Cricut
  Voice English window goes from **3 to 11 of 24** legal shift starts.

**RC5 still cannot replace RC9.1**, for one reason that is not about code
quality: **there is no exact comparison, for any scenario, and no run evidence
was supplied to me.** Every packaged input hash differs from the RC9.1 baseline
(section 4), and the two ZIPs contain **no result artifacts** — only a smoke run.
The scenario table in `RC5_DEEP_COMPARISON_RC9_1_VS_RC5.md` is therefore not
verifiable from what I hold, and I am not endorsing its numbers.

Their own `RELEASE_STATUS.json` says `NO_GO_PENDING_RC5_TARGETED_RUNTIME_REVIEW`
with `production_ready: false`. That is the correct call and I agree with it.

---

## 2. Identities reviewed — all verify

| Item | Claimed | Actual | |
|---|---|---|---|
| Production package | `4b7d50f8…2b7272` | `4b7d50f8…2b7272` | ✅ |
| Validation package | `a28b98b5…1b6ed` | `a28b98b5…1b6ed` | ✅ |
| Engine (both packages) | `0e6f6435…08cc5c` | `0e6f6435…08cc5c` | ✅ |
| Offline gate | 453 tests | **453 tests, 11 suites, PASS** (re-run here) | ✅ |

Both packages ship the **identical** engine. Package identity is clean — the
best of any build in this project.

Engine diff RC4 → RC5: **65 hunks, +265 / −176 lines.**

---

## 3. RC4 → RC5 change verification

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 4 | Candidate protection anchor-relative, not global dominance | **PASS** | `severity_ok = severe <= severity_limit or material_tradeoff`. Collapse test below. |
| 5 | Defensive fallback protects floor/gap/deficit before target | **PARTIAL** | Thresholds fixed, but `accepted = list(risk_eligible) if risk_eligible else list(pool)` still falls back to the raw pool. Now rarely reached — see below. |
| 6 | Target-first inside the protected envelope | **PASS** | Verified in the reproduction. |
| 7 | Window constrains shift starts, allows overnight continuation | **PASS** | `shift_within_language_window` rewritten; 3→11 legal starts on Voice. |
| 8 | Hard-valid quality-failed reaches polish + validation | **PASS** | `REVIEW_ONLY_QUALITY_GATE_BLOCKED`, `REVIEW_ONLY_HUMAN_APPROVAL_PENDING`. |
| 9 | Automated gate evidence separated from human approval | **PASS** | `approval_status = 'AUTOMATED_HARD_GATES_PASSED_PENDING_HUMAN_APPROVAL'`. This closes my A-11. |
| 12 | Engine/validator metric parity is a release gate | **PASS** | `apply_metric_parity_gate`, sets `FAIL_METRIC_PARITY`. |
| 15 | Missing Phase-C safety evidence fails sealing closed | **NOT PROVEN** | No `safety_evidence` symbol found in the runner or `engine/production/`. May exist under another name; not located. |
| 1, 2, 3, 10, 11, 13, 14, 16–22 | — | **NOT VERIFIED** | Solver-behaviour claims; cannot be confirmed without run artifacts (section 4). |

### F1 — the reproduction that broke RC2 and RC4

```
SAFE    target 150  floor 160  severe 2  run 2  depth 0.10
GREEDY  target 153  floor 151  severe 9  run 6  depth 0.40
ODD     target 150  floor 158  severe 0  run 8  depth 0.50
```

| Build | Guard accepted | Picked | Outcome |
|---|---|---|---|
| RC2 / RC4 | **0 of 3** | GREEDY | +3 target, **−9 floor**, +7 severe |
| **RC5** | **1 of 3** (SAFE) | **SAFE** | protected-correct |

Collapse rate across pool sizes, same generator:

| Pool | RC2/RC4 accepted | **RC5 accepted** |
|---|---|---|
| 10 | 1 | **6** |
| 25 | 1 | **9** |
| 50 | **0 — collapsed** | **17** |
| 100 | **0 — collapsed** | **30** |

Acceptance now **scales with pool size** instead of inverting. The guard never
collapsed in any test. This is a real fix, not a cosmetic one.

---

## 4. RC9.1 vs RC5 — rebuilt on input hashes

The brief asks for exact/directional/unavailable labels. I computed every
packaged input hash against the baseline's `input_sha256_prefix`:

| Baseline scenario | Baseline prefix | Packaged workbook | Actual | Match |
|---|---|---|---|---|
| NMG EN | `230179d964674219` | NMG_EN_AND_SP | `ab85935a…` | differs |
| NMG EN | `230179d964674219` | NMG_EN_FIXED_NESTING | `3cdc0b75…` | differs |
| NMG EN | `230179d964674219` | RC9_2_2_NMG_EN_PRODUCTION | `f770c326…` | differs |
| NMG SP | `33f540ffa1df748d` | NMG_SP_RC9_1_READY_FIXED | `05f1f7db…` | differs |
| AE AR B2B | `b7dcbbffeb19e05f` | AE_AR_B2B | `b7be7e0a…` | **differs** |
| Cricut Voice | `8e3833c9ef496b46` | Cricut_Voice_RC9_1_READY_SKELETON | `36ddb088…` | **differs** |
| Cricut Chat ×2 | *(none)* | — | — | not comparable |
| GDI REAL28, NMG EN SP | *(no baseline row)* | — | — | unavailable |

**Not one scenario is an exact comparison.** The baseline marks NMG EN, NMG SP,
AE AR B2B and Cricut Voice `comparable: true`, but none of their hashes match
the workbooks RC5 actually ships. AE AR B2B is the near-miss (`b7dc…` vs
`b7be…`) — close enough to look like a match at four characters, and it is not.

Two further disqualifiers on the baseline itself:

- `evidence_class = CONSOLIDATED_HISTORICAL_METRICS_NOT_RAW_RUN_ARTIFACTS`
- `metrics_are_before_break_only = true`

So even with matching hashes it would be a metrics summary against an artifact,
before-break against before-break only.

### Corrected labels

| Scenario | Their label | **Correct label** |
|---|---|---|
| NMG EN | directional (+13) | **directional only** — agreed |
| NMG SP | directional tie | **directional only** |
| AE AR B2B | "RC9.1 ahead by 1" | **directional only** — not a 1-interval loss; different input |
| Cricut Voice | "RC9.1 is better" | **directional only** — see below |
| Cricut Chat | unavailable | **unavailable** — agreed |
| GDI REAL28 | no baseline | **unavailable** — agreed |
| NMG EN SP | no baseline | **unavailable** — agreed |

### On the Cricut Voice "regression" (256/264 → 243/250)

The brief asks whether this is a regression. **On the evidence supplied, it
cannot be called one**, for three independent reasons:

1. The input hash differs (`8e3833c9…` vs `36ddb088…`).
2. The baseline row is a *workbook leaderboard entry*, not a validated artifact
   — its own `evidence_status` says so, and it is the only row with no
   `before_100` value.
3. **RC5 changed what is legal on this workbook.** The F2 fix moves the English
   16:00–03:00 window from 3 to 11 legal shift starts. If the RC5 run enforced
   the window and the RC9.1 baseline did not (or vice versa), the two runs are
   solving different problems. I cannot check which, because no run artifact was
   supplied.

Calling this a regression without settling (3) risks reverting a correct fix.

---

## 5. Confirmed improvements

- **F1 selector guard** — anchor-relative thresholds; no collapse at any pool size.
- **F2 language window** — start-only; 3 → 11 legal starts on Voice.
- **A-11 closed** — `production_ready` is now hard-coded `False` in all three
  writers and set `True` nowhere in the codebase. The automated chain can
  package a review-only artifact but can never self-approve. This is the single
  best release-safety decision in the project.
- **Metric parity gate** — engine vs validator disagreement now blocks release.
- **Review-only retention** — a hard-valid, quality-blocked schedule survives to
  polishing and validation instead of being discarded.
- **Package identity** — all four claimed hashes verify; both packages carry the
  same engine.
- **453 tests, 11 suites** — reproduced.

---

## 6. Confirmed regressions

**None found.** The F4 return-code fix from RC4 is preserved verbatim
(`rc = 5 if args.skip_independent_validation else 4`).

One **deliberate semantic change** worth naming explicitly, because it looks
like a loosening: the packaging gate dropped `rc == 0`.

```
RC4:  engine_rc == 0 and qrc == 0 and rc == 0 and status == 'PASS'
RC5:  (engine_rc == 0 or quality_pending_validation)
      and (qrc == 0 or quality_pending_validation)
      and hard_valid_artifact(audit) and status == 'PASS'
```

A quality-blocked run can now be packaged. That is intended (review-only
evidence) and it is **safe only because `production_ready` is unconditionally
`False`**. Those two changes must be treated as a pair — if anyone ever makes
`production_ready` conditional, this gate becomes a fail-open. Worth a guard
test pinning "no code path sets production_ready True".

---

## 7. Remaining blockers

| Blocker | Root cause | Status |
|---|---|---|
| **No exact comparison exists** | Every packaged input hash differs from the baseline; baseline is consolidated metrics, before-break only | Blocks any "RC5 beats RC9.1" claim |
| **No run artifacts supplied** | The RC5 result ZIPs named in the brief were not uploaded | Blocks verification of items 1,2,3,10,11,13,14,16–22 |
| **A-1** zero breaks → 60 min of breaks | `_parse_break_segments` backfills a hard-coded 15/30/15 | **Still open** — re-tested on RC5 |
| **A-2** invalid `Interval Minutes` → silent 60 | Out-of-set value discarded in favour of inference | **Still open** — 7, 45, "abc" all → 60, no warning |
| **A-3** `norm()` doesn't strip spaces | `"All Days"`, `"Every Day"`, `"7 Days"` hard-rejected | **Still open** |
| **A-7** `language_rules_at(day=7)` → no rules | No range guard | **Still open** (latent) |
| **P-1** pre-solver 9–10× slower than needed | `shift_day_demand_fit` recomputed ~632k times | **Still open** — 11.25 s measured on RC5 |

A-1 through P-1 are from my RC4 audit and were presumably not yet received when
RC5 was built. None is a new RC5 defect.

---

## 8. Hidden risks, by business impact

1. **A-1 — a "no breaks" contract silently gets 60 minutes of breaks.** Highest
   business impact of anything still open: it changes required headcount and
   leaves no audit trail.
2. **Search truncation is still the dominant quality variable.** Every long run
   I have seen on any build reports `TRUNCATED_INSUFFICIENT_STAGE1_BUDGET`. Any
   claim of "maximum coverage" is *best found within a truncated search* — the
   brief asks this directly, and that is the honest answer.
3. **Reproducibility.** Same workbook, same seed, same budget produced
   `production_eligible TRUE` and no schedule at all on two runs I made. Until
   characterised, no single run proves a scenario passes or fails — for either
   side of this comparison.
4. **A-2** — every coverage percentage computed at a granularity the scheduler
   did not choose.
5. **The `production_ready` / packaging-gate pairing** (section 6) is a
   correctness invariant held by convention, not by a test.

---

## 9. Runtime and scalability

Measured on RC5, no solver:

- `capacity_diagnostics`: **11.25 s** on AE_AR_B2B before Stage 1 starts.
- Root cause unchanged from my RC4 audit: `shift_day_demand_fit` is pure in
  `(day, shift.index)` and returns **168 distinct results from ~632k calls**;
  `cyclic_requirement_context` is called ~22.8 M times.
- Memoisation measured **9–10×** on RC4 with no behaviour change; the code is
  unchanged in RC5, so the same gain is available.

This is not merely slow — Stage 1 is wall-clock budgeted and already truncating,
so those seconds are search that never happens. **Fixing P-1 is the cheapest
available increase in schedule quality**, which is the stated business priority.

On workers: I cannot answer whether 2 or 4 is correct without run artifacts.
Worker count should not change correctness (CP-SAT with a fixed seed is
deterministic per search path) but **does** change how much search fits in a
wall-clock budget — which, given truncation, changes the result. That is the
same mechanism as risk 3.

---

## 10. Should RC5 replace RC9.1 now?

**No — but for evidentiary reasons, not engineering ones.** Keep RC9.1 as the
operational baseline.

RC5 is clearly the better forward engine and I would develop on it without
hesitation. The blocker is that nothing in my hands demonstrates RC5 producing a
better schedule than RC9.1 on the same input, because no such comparison exists
yet and no run artifacts were supplied.

I agree with their own framing — **RC5 forward, RC9.1 fallback** — and with
their `production_ready: false`.

---

## 11. Smallest safe set of final changes

| Fix | File / function | Root cause | Benefit | Regression risk | Validation test |
|---|---|---|---|---|---|
| **A-1** | `l632…py` → `_parse_break_segments` | Empty result backfilled with hard-coded 15/30/15; invalid durations coerced | Break contract becomes truthful; headcount correct | Workbooks relying on the backfill would start failing — that is itself a finding | Unit-pin each row of the A-1 table; preflight matrix across all workbooks |
| **A-2** | `l632…py` line ~1465 | No else-branch distinguishing absent from supplied-and-invalid | Coverage percentages match the chosen granularity | None expected; all packaged workbooks supply 15/30/60 or nothing | Unit-pin 15/30/7/45/"abc"; preflight matrix |
| **P-1** | `l632…py` → `shift_day_demand_fit` | Pure function called in three nested loops | 9–10×; returns ~10 s of Stage-1 budget per run | Stale cache only if `parsed.active` mutates post-parse; key on `id(parsed)` | Byte-compare `capacity_diagnostics` output before/after on all workbooks |
| **A-3** | `_parse_language_days` | `norm()` keeps spaces | `"All Days"` stops being a hard failure | None | Fuzz table; add the Coverage Days dropdown |
| **Guard** | new test | `production_ready`/packaging-gate pairing is convention-only | Prevents a future fail-open | None | Assert no code path sets `production_ready` True |

A-1, A-2 and P-1 together are roughly half a day.

---

## 12. Tests required before production

**Offline, minutes — before any solver time**
1. The four unit-pins above; re-run the 453-test gate.
2. Byte-compare `capacity_diagnostics` output before/after P-1.

**Solver, on the RC5 engine, each scenario run twice** (risk 3)
3. **NMG_EN_PRODUCTION** QUICK/FULL — their #1 required-to-close item.
4. **Cricut Voice** with the window mode *recorded in the artifact* — settles
   whether 243/250 is a regression or a different contract (section 4).
5. **GDI REAL28** — confirms the corrected metric-parity result holds.
6. **A genuine 11H/3OFF fixture** plus the 11H-prohibited negative. Still the
   only wholly untested rule family; the old SAKS artifact was 9H/2OFF with 11H
   disabled.

**To make any RC9.1 comparison meaningful at all**
7. Re-run RC9.1 and RC5 **on the same workbook file**, or retire the exact-
   comparison goal and state plainly that all comparisons are directional. The
   current baseline cannot support an exact claim for any scenario.

---

### What I could not review

The RC5 result ZIPs named in the brief — the corrected GDI and NMG results and
`RC5_RUN_2000` — were not among the uploaded files. Only the two package ZIPs
arrived. Every solver-behaviour claim (items 1, 2, 3, 10, 11, 13, 14, 16–22) and
every scenario number in the comparison document remains unverified for that
reason. Send those archives and I can close most of section 3 without a re-run.
