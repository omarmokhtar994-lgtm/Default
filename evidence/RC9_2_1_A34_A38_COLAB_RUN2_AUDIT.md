# Colab run 2 — RC9.2.1 + A34–A38, 14400s, seven scenarios

## 1. Build identity — there is no RC9.2.2

The audit request names the build **RC9.2.2**. No such build exists. Every run
in this batch reports:

```
release       L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1
engine_sha256 fb96de0ef727e20f91c34031b9b23168d334b26bac30b7b900ed2b55aaa74bbd
```

That hash is byte-identical to the engine shipped in
`RC9_2_1_COLAB_GATE_PACKAGE_A34_A38.zip`, and to this repository at commit
**8a568ba**. So the evidence *is* tied to one exact, named build — it simply is
not called RC9.2.2. `VERSION` was never bumped.

**What the runs contain:** A34 (Stage-1 funding), A35 (Stage-2 anchor),
A36 (protected-tier contract route), A37 (break-slice depth), and A38 in the
gate report.

**What the runs do NOT contain**, both landing after the package was built:
the per-schedule Gate 5 standard (24f5a00) and workbook-driven Run Stage /
Run Depth (3c0edac).

No RC9.2.1-vs-RC9.2.2 comparison is possible, because there is only one build.

## 2. What actually completed

| Scenario | rc | Status | Independent validation |
|---|---|---|---|
| AE_AR_B2B | 0 | PASS_WITH_QUALITY_WARNINGS | **PASS** |
| CRICUT_VOICE | 0 | PASS_WITH_QUALITY_WARNINGS | **PASS** |
| CRICUT_CHAT | 0 | PASS_WITH_QUALITY_WARNINGS | **PASS** |
| NMG_EN_SP | 0 | PASS_WITH_QUALITY_WARNINGS | **PASS** |
| NMG_EN | 2 | FAIL_PRE_SOLVER_CONTRACT | not run |
| GDI_REAL28 | **−9** | killed by the host (SIGKILL) | not run |
| NMG_SP | — | **archive never uploaded intact** (`.oplusdownload`) | — |

**Four of seven scenarios produced usable evidence.** GDI_REAL28 was killed
mid-run — that is a Colab resource limit, not an engine result, and nothing may
be concluded from it. NMG_SP is absent entirely.

## 3. The budget fixes are confirmed on production runs

Every A34/A35/A37 mechanism behaved as designed, on all four completed runs:

| Measure | Before (2,400s run) | This batch (14,400s) |
|---|---|---|
| `stage1_search` | 332s | **4,390s** |
| `break_search` | 460s | **5,694s** |
| `joint_refinement` | 840s | 2,645s |
| Stage-2 anchor granted / spent | 77s / **599.7s** | 188s / **188.0s** |
| Break attempts returning UNKNOWN | 10 of 25 | **0** |
| Objective modes explored | 3 of 7 | **7 of 7** |

Break search now outweighs joint refinement, the anchor stays inside its
reservation, and no break attempt is too shallow to converge. **A35 and A37 are
verified end to end**, which the build environment could not do (five long runs
died to container restarts).

## 4. AE AR B2B reaches RC9.1 exactly

| | before_target | before_floor |
|---|---|---|
| RC9.1 baseline | 168 | 168 |
| **This run** | **168** | **168** |
| Recorded pre-A34 run | 131 | 159 |

`after_target` 162/168 = 96.4%, `after_floor` 168/168, gate 8 PASS, independent
validation PASS. This is the scenario A34 was built for and it lands on the
baseline exactly, matching the 168 measured at component level beforehand.

## 5. Gates 2 and 9 still produce no verdict — and for AE that is now wrong

| Scenario | Gate 2 | Why |
|---|---|---|
| AE_AR_B2B | NOT_COMPARABLE_SEARCH_TRUNCATED | explored 14 of 15 profiles |
| CRICUT_VOICE | NOT_COMPARABLE_SEARCH_TRUNCATED | explored 13 of 15 profiles |
| CRICUT_CHAT, NMG_EN, NMG_EN_SP, GDI_REAL28 | NOT_COMPARABLE_INPUT_NOT_IN_BASELINE | no baseline row for that input hash |

The truncation rule exists so a starved search is never scored against RC9.1.
It is correct for a **shortfall**. It is wrong for a **match**: AE ran 14 of 15
profiles and still equalled the baseline on both axes. Searching less can only
make a result worse, never better, so truncation cannot explain away a
result that meets or beats the baseline. Holding AE at NOT_COMPARABLE
understates a genuine pass.

**Proposed refinement (not yet made):** when a truncated run's before-break
target and floor both meet or exceed the baseline, report
`PASS_AGAINST_CONSOLIDATED_BASELINE_DESPITE_TRUNCATION` rather than
NOT_COMPARABLE. A shortfall under truncation stays NOT_COMPARABLE.

## 6. The remaining failures are real, not budget artifacts

With the search fully funded and zero shallow attempts, two scenarios still
lose heavily at the break stage:

| Scenario | before → after target | Break loss | Gate 5 |
|---|---|---|---|
| CRICUT_CHAT | 199 → 173 | **26 / 242 = 10.7%** | FAIL |
| NMG_EN_SP | 188 → 153 | **35 / 252 = 13.9%**, plus 13 language-reserve quarters | FAIL |
| CRICUT_VOICE | 244 → 243 | 1 / 264 | pass (delta only) |
| AE_AR_B2B | 168 → 162 | 6 / 168 | pass (delta only) |

NMG_EN_SP also fails gate 4 on skeleton retention: the best before-break
skeleton scored 206 and the shipped one 188, an **18-interval loss between
finding and keeping** a candidate.

This is the important shift. Before A34–A37, every quality shortfall was
explainable as starvation. It no longer is. **Cricut Chat and NMG EN+SP are
genuine Stage-2 and selection problems** and need root-causing on their own
terms — break model, break objective, or real capacity.

## 7. Cricut Voice moved the wrong way

| | before_target | before_floor |
|---|---|---|
| RC9.1 baseline | 256 | 264 |
| This run | **244** | **250** |

−12 target and −14 floor, worse than the ~250 the component probes suggested.
The probes measured a single profile in isolation; the run selects across a
portfolio under a different objective, so the two are not equivalent. Voice
remains the least understood scenario and its baseline row is still the only
one sourced from a *leaderboard* rather than a run replay.

## 8. Coverage of the requested audit

This document covers, from the requested scope: build identity (§1), the Colab
artifact review (§18), the RC9.1 comparison (§16), gate scoring, and part of the
optimization question (§21).

**Not covered here, and not to be read as passed:** the code re-audit (§2), the
workbook contract audit (§3), the shrinkage audit (§4), interval-by-interval
schedule review (§5), the overage audit (§8), the language/skill audit (§11),
the fixed/OFF/rest/nesting audit (§12), the 24/7 day-tail audit (§13), the
shift-library geometry audit (§14), test-gap analysis (§19), and the controlled
challenge experiments (§22). Several of those depend on GDI_REAL28 and NMG_SP,
which this batch does not contain.

No production go/no-go is issued on four of seven scenarios.
