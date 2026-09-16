# B-1 and B-2: the release gates did not know which stage had run

What this file answers: why every `BEFORE_BREAKS_ONLY` run failed its own
release gates on a schedule with nothing wrong with it, and what was changed
so it no longer does — without any gate becoming easier to pass.

Engine lineage: RC5 + P-1 + C-1 + capacity gate + this change.
Workbook used for every measurement below: `AE_FR_Choice.xlsx`, seed 9000,
2 workers, QUICK.

---

## 1. The defect, as measured

`FRC_BEFORE_A` and `FRC_BEFORE_B` — two independent skeleton-only runs — both
ended at `rc=4`, `FAIL_METRIC_PARITY`, with 41 mismatches. Every one of them
looked like this:

```json
{"field": "active_intervals", "engine": null, "validator": 112,
 "reason": "MISSING_CANONICAL_METRIC"}
{"field": "before_100",  "engine": null, "validator": 112, ...}
{"field": "after_100",   "engine": null, "validator": 112, ...}
```

`engine: null` on all 41. The engine and the validator had not disagreed about
anything. The engine had published **nothing**, and the parity gate read
"did not publish" as "disagrees".

Root cause: `apply_metric_parity_gate` read `selected_candidate.metrics`, which
only a `FULL_SCHEDULE` run creates. A skeleton-only run stops before a final
candidate exists, so the key is absent by construction.

Fixing that alone exposed three more members of the same family, each of which
independently blocked the stage. They are all the same mistake — a gate written
for one stage being applied to the other — and all four are recorded here.

| | What it did | Where |
|---|---|---|
| **B-1** | Parity gate compared a published surface against an unpublished one and failed | `RUN_UNIVERSAL_PRODUCTION.apply_metric_parity_gate` |
| **B-1c** | Quality report published `active_intervals: 0` and `safety: NOT_RUN` for a run that covered 112 of 112 | `phase_c_quality_report.build_report` |
| **B-1d** | Preliminary quality report (which runs *before* validation) latched a blocking code the later clean report could not clear | `RUN_UNIVERSAL_PRODUCTION.quality_allows_validation` |
| **B-2** | Run reported "No final schedule workbook was produced, so independent validation could not run" — on a run whose validation had run and passed | `reconcile_business_outcome_after_validation` |

B-1c is the worst of the four as a reporting defect: a null is a visible
absence, but `active_intervals: 0` is a **number**, and it is wrong.

---

## 2. What was changed

### The engine publishes the surface for the stage it ran

The skeleton already carried a full canonical metric surface in
`skeleton.diagnostics["no_break_metrics"]`, produced by `calculate_metrics`
with an empty break set — **the same evaluator that scores every after-break
candidate**. Nothing needed to be computed; it needed to be published.

```python
audit["stage_metric_surface"] = {
    "stage": "BEFORE_BREAKS_ONLY",
    "break_stage_executed": False,
    "after_metrics_basis": "NO_BREAKS_PLACED_AFTER_EQUALS_BEFORE",
    "metrics": compact_metric_surface(before_break_metrics),
}
```

The full path publishes the same key with `FULL_SCHEDULE`. One key, read by
every consumer, regardless of how far the run went.

This matters for whether the gate means anything: if the skeleton surface came
from a second implementation, parity against the validator would be comparing
the engine to itself. It does not — it is the same function.

### The parity gate compares the same 41 fields at both stages

No field is exempted at either stage. Two checks were **added**:

* **Stage agreement.** The engine declares the stage it ran; the validator
  declares the artifact it read (`artifact_role`). They must agree. A run that
  asked for a skeleton and was handed a final workbook now fails
  `STAGE_DISAGREEMENT` instead of being compared against the wrong stage. A
  side that declares no stage at all also blocks, under its own reason
  (`ENGINE_DECLARED_NO_STAGE` / `VALIDATOR_DECLARED_NO_STAGE`) — "we disagree"
  and "you never said" are different defects and are not reported as one.
* **`ENGINE_PUBLISHED_NO_METRIC_SURFACE`.** An unpublished surface is not
  evidence. Without this the gate would compare `{}` against `{}` on any future
  path that publishes neither and report PASS on no comparison at all — which
  would have turned the original defect into a silent pass.

### B-2: after-break figures on an artifact with no breaks

The validator's `after_100 = 112` on a skeleton artifact is not arithmetically
wrong — no breaks were placed, so after is before. It is wrong as a *claim*:
read out of context it says a post-break schedule held 112 intervals.

The numbers were not deleted. A consumer needs the values and needs to know
what produced them, so both are now published:

* `break_stage_executed: false`
* `after_metrics_basis: "NO_BREAKS_PLACED_AFTER_EQUALS_BEFORE"`

and the parity gate now *enforces* the claim. On a `BEFORE_BREAKS_ONLY`
artifact, every `after_X` must equal its `before_X` twin on both sides, or the
gate fails with `AFTER_DIFFERS_FROM_BEFORE_WITHOUT_BREAK_STAGE`. A side that
invents a break effect the artifact cannot contain is now a defect that the
gate catches rather than a number a reader has to interpret.

### A second, independent signal for the stage

Stage detection rested on one cell: a `"NOT ASSIGNED IN BEFORE-BREAK ARTIFACT"`
marker in the break sheet. The engine writes a second, independent statement in
the Production Summary (`Artifact Type`), which the validator now also reads.
When the two contradict each other, the workbook cannot say what it is, so the
validator records a hard failure (`ARTIFACT_STAGE_DECLARATION_CONFLICT`) and
takes the stricter reading — so a tampered declaration can never promote a
skeleton into something whose `after_*` figures read as a break outcome.

### The stage gate is not the release gate

A `BEFORE_BREAKS_ONLY` artifact can never be released; asking whether it is
`FINAL_VERIFIED` is a category error, and asking it was what returned 2 on
every skeleton run. The report now answers two separate questions:

* `production_release_eligible` — **always false** at this stage, stated
  explicitly so a clean skeleton report can never read as an approval.
* `stage_gate` — did the stage that was asked for complete and check out?
  Its blocking reasons are the ones that are meaningful here: input contract,
  independent validation, metric parity, and whether the artifact was exported.

The full-schedule release contract is **untouched**. Quality observations are
still computed and published for skeleton runs — this run reports
`REVIEW_EXTREME_OVERAGE` — they are reported rather than used to block a
diagnostic.

---

## 3. Proof that the production path did not move

Every recorded audit available was replayed through the old and the new quality
reporter and compared field by field.

| Case | Stage | old rc | new rc | Result |
|---|---|---|---|---|
| AE_AR_B2B | FULL_SCHEDULE | 0 | 0 | unchanged |
| AE_AR_Choice | FULL_SCHEDULE | 0 | 0 | unchanged |
| AE_FR_B2B | FULL_SCHEDULE | 0 | 0 | unchanged |
| AE_FR_Choice | FULL_SCHEDULE | 0 | 0 | unchanged |
| AE_IT_B2B | FULL_SCHEDULE | 0 | 0 | unchanged |
| AE_IT_Choice | FULL_SCHEDULE | 2 | 2 | unchanged |
| FRC_FULL_A | FULL_SCHEDULE | 0 | 0 | unchanged |
| FRC_FULL_B | FULL_SCHEDULE | 0 | 0 | unchanged |

"Unchanged" means the return code and every pre-existing reported value are
identical. The only differences are additive: `run_stage`,
`production_release_eligible`, `stage_gate`, `after_metrics_basis`, and
`schema_version` 1 → 2 on the canonical surface.

A replay only re-reads a recorded audit, so a full run was also executed end to
end through the patched runner against its recorded baseline — same workbook,
same seed, same 900s budget:

| | `FRC_FULL_A` (before) | `B1_FULL` (after) |
|---|---|---|
| runner return code | 0 | **0** |
| independent validation | PASS, `FINAL_AFTER_BREAKS` | **PASS, `FINAL_AFTER_BREAKS`** |
| metric parity | PASS, 0 mismatches | **PASS, 0 mismatches** |
| before / after target | 105 / 101 | **105 / 101** |
| before / after floor | 112 / 110 | **112 / 110** |
| floor gaps | 2 | **2** |
| Phase C quality status | `WARN_PRODUCTION_QUALITY_LIMITED` | **`WARN_PRODUCTION_QUALITY_LIMITED`** |
| stages declared | not recorded | `FULL_SCHEDULE` / `FULL_SCHEDULE` |
| `production_release_eligible` | not stated | `true` |

Every coverage figure and every gate verdict reproduces. The additions are the
stage declarations.

### A defect the replay caught in this change itself

The first version of the fallback read `selected_before_break_skeleton.metrics`
whenever no final candidate existed. **AE_IT_Choice** is a `FULL_SCHEDULE` run
that reached Stage 2 and failed break placement — it still carries a
before-break skeleton. That version would have published before-break coverage
as that run's result, under a `FULL_SCHEDULE` label with
`after_metrics_basis: BREAKS_PLACED_BY_STAGE_2`: precisely the fabrication this
change exists to prevent, introduced by the change itself. The replay showed it
as field drift on that one case.

The fallback now applies only when the run genuinely **stopped** at Stage 1
(`artifact_state == BEST_BEFORE_BREAKS_ONLY` or
`status == SKELETON_ONLY_COMPLETE`). A full run that failed Stage 2 has no
metric surface and continues to say so. Pinned by
`test_a_full_run_that_failed_stage_2_must_not_borrow_skeleton_metrics`.

---

## 4. End-to-end result

Same workbook, same seed, skeleton-only, 300s, through the whole runner:

| | before | after |
|---|---|---|
| runner return code | **4** | **0** |
| independent validation | PASS | PASS |
| metric parity | **FAIL**, 41 mismatches | **PASS**, 0 mismatches, 41 fields compared |
| engine stage / validator stage | not recorded | `BEFORE_BREAKS_ONLY` / `BEFORE_BREAKS_ONLY` |
| Phase C coverage | `active_intervals: 0`, `after_target: 0` | `112`, `112` |
| Phase C safety | `NOT_RUN` | `PASS` |
| `production_release_eligible` | not stated | `false`, explicitly |
| business outcome | "No final schedule workbook was produced, so independent validation could not run" | "Before-break skeleton generated for review; breaks are not assigned" |

`initial_quality_report_return_code` is still 2 and that is correct: the
preliminary report runs before validation and is honestly blocked at that
moment. It is now superseded by the post-validation report instead of latching.

---

## 5. Tests

`tests/test_rc9_2_4_stage_aware_parity.py` — 61 tests. Every defect is pinned
from both sides, because a fix that only proves the new pass is indistinguishable
from a gate that was weakened.

| Class | Pins |
|---|---|
| `StageLabelling` | stage is recorded, never guessed; omitting it leaves the surface exactly as before |
| `ParityAtTheSkeletonStage` | a correct skeleton passes; all 41 fields still compared; value mismatches, missing fields and stage disagreement still fail; a fabricated after-break figure fails; the same figures are legitimate at the full stage |
| `EngineSurfaceDiscovery` | both stages readable; archived audits still readable; an absent surface stays visibly absent |
| `ParityGateEndToEnd` | the exact case that used to fail now returns 0; an engine that publishes nothing still fails; a stage mix-up still fails; the full path still passes and still fails for the right reasons |
| `EnginePublishesTheStageSurface` | the engine call sites, and that both stages use the same evaluator |
| `ValidatorStageDeclaration` | the second signal is read; a conflict is a hard failure |
| `RealBeforeBreakArtifact` | the same checks against a workbook the engine actually produced, including a tampered declaration |
| `PhaseCReadsTheStageThatRan` | real coverage reported; never releasable; a failed full run may not borrow skeleton metrics |
| `PhaseCExitContract` | a validated skeleton no longer blocks; a skeleton with a failed contract, failed validation, failed parity or no artifact still blocks; the full release contract is unchanged |
| `BusinessOutcomeForTheSkeletonStage` | the stage gets its own outcome; the full run's outcome is unchanged |
| `PreliminaryQualityGateWaitsForValidation` | the skeleton may proceed to its validation; the allowance does not leak into the full path |

Full gate: **15 suites, 546 tests, PASS**, plus both selfchecks and the
undefined-name sweep.

---

## 6. What is *not* claimed

* **This does not change a single scheduling decision.** No constraint, no
  objective, no search budget was touched. It changes what the run reports
  about itself.
* **No gate became easier to pass.** The full-schedule release contract is
  byte-identical on all 8 recorded full runs. The skeleton stage gained a gate
  where it previously had a contradiction, and the parity gate gained two
  checks it did not have.
* **`REVIEW_EXTREME_OVERAGE` on this skeleton is a real observation**, not
  noise. It is reported and not used to block, because a diagnostic stage has
  no release decision to make. It would still block a full run.
* **B-3 through B-7 remain open.** What this unlocks is the fast diagnostic
  mode that exposed B-3 in the first place: `BEFORE_BREAKS_ONLY` now returns a
  usable result instead of `rc=4`.
