# Whole-engine pass: how the findings connect, and what they are worth

This re-evaluates every defect found in the section-by-section pass plus the
earlier B-list, as one system rather than as a list. Three measurements drive
it; each is reproducible from the commands recorded here.

Engine: RC5 + P-1 + C-1 + capacity gate + stage-aware gates + workbook search
controls + warm slice floor. 22,094 engine lines, 3,322 satellite lines.

---

## 1. What the section pass actually found

**Twenty-one distinct findings.** They are not twenty-one problems. Measured
against the whole file, they collapse into **four root causes plus six
independent items**.

### Root cause A — a fallback that returns a *different quantity*

Scanned every `get(A, get(B, …))` in the package where `A != B`:
**18 sites, all in the engine file, three shapes.**

| shape | sites | what it substitutes |
|---|---|---|
| `*_floor` → `*_80` | **10** | a hardcoded 80% tier for the **configured** floor ratio |
| `before_severe_floor_gap_count` → `severe_floor_gap_count` | 4 | the after-break count for the before-break count |
| `before_max_consecutive_floor_gaps` → `max_consecutive_floor_gaps` | 3 | same, for the run-length |
| `before_raw_min` → `before_raw` | 1 | a plain value for a minimum |

This absorbs what I had reported separately as S8-1, S12-1 and S13-1.

**I under-reported the biggest one.** In S13 I found the `before_floor → before_80`
fallback at line 19370 and called it one site. It is **ten**, and six of them
(10512, 10517, 10554, 10667, 10684, 10939) are on the *after* side, inside
`target_priority_tradeoff_select` and `select_export_candidates` — the
selection path, not reporting.

`_80` is a genuinely fixed tier, distinct from the configurable floor;
`_protected_tier_counts` at 10119 even excludes a tier equal to the floor, so
the code knows the difference. The two coincide only at `floor_ratio == 0.80`,
which is 14 of 15 workbooks. **NMG12 uses 0.85**, where `after_80 >= after_floor`
always, so the fallback would silently overstate floor attainment.

Latent — `calculate_metrics` always emits both keys.

### Root cause B — a default that is more permissive than the declared one

**90 `getattr(parsed, field, default)` sites over 36 fields** in the engine
file; 11 fields where no shadow default matches the declared one, 4 where it
differs between call sites. Every disagreement is permissive.

**Zero instances in any of the nine satellite modules.** This is an
engine-file-local habit, not a project-wide one — which makes it far cheaper to
fix than it first looked.

Measured: raw cap **20 vs 14**; adjacent limit **999999 vs 3**.

S10 raised its importance: these defaults sit **inside `production_quality_gate`**
— `999999` against declared `6` and `0`, `2.0` against declared `1.35`. This is
not internal plumbing; it is the release gate.

### Root cause C — a parser with no "unrecognised" state

Three findings, one cause. `yes()`, `tri_state()` and `preference_kind()` all
map unrecognised input to a *valid* value rather than to an error.

| | surface | mitigated? |
|---|---|---|
| C-2 | 10 instruction booleans | **yes** — stop-style dropdowns on all ten |
| C-3 | preference cells (`leave`/`off` only) | **no** — zero data validations |
| B-11 | name-matched rows | no |

### Root cause D — unexercised code decays

`0 of 15` workbooks define a nesting group; `Fixed Request Use = No` throughout.
Both S6-1 (a nesting group with mixed leave is silently UNSAT) and S6-2 (the
only nesting contract check is unreachable) live in exactly that unexercised
path. 213 further dead lines across 6 functions sit beside it.

### Independent items

S9-2 (dominance vs lexicographic), S11-1 (floor losses), S15-3 (phase
minimums), B-10 (break slice floor used as a cap), B-4, B-6.

---

## 2. Measurement: what the parity architecture can and cannot catch

The release story rests on "two independent computations agree". Classifying
every finding by whether that architecture could ever detect it:

| class | can parity catch it? | why | findings |
|---|---|---|---|
| **A. contract misread** | **never** | the validator parses the *same* contract, sees the same wrong leave, and correctly reports no rule was broken | B-11, C-2, C-3 |
| **B. metric computed wrongly** | **yes** | this is what the architecture is for | B-8 (caught exactly this way) |
| **C. numbers right, decision wrong** | **never** | both sides agree on every number; the gate or the ordering is what is wrong | S11-1, S9-2, S10-1, root cause B |
| **D. unmodelled subsystem** | **structurally not** | there is no second computation to disagree with | the 20 metrics below |

**Only class B is covered.** That is the single most important structural fact
in this report, and it means parity passing 41/41 — as it did on both completed
sweep cases — is real evidence about class B and no evidence at all about A, C
or D.

## 3. Measurement: the gate-coverage matrix

For the 51 metrics read by `_candidate_quality_tuple`, `candidate_dominates`,
`production_quality_gate` or `validate_schedule`, resolved through
`canonical_metrics.ALIASES` against the validator's actual emitted keys:

**51 decision-driving metrics; 20 have no independent recomputation.**

This **corrects B-9**, which said 16. My first naive scan said 36 — that was
wrong too, because the validator names week-boundary metrics `next_sunday_*`
and a raw regex counted those as gaps. The alias-resolved number is 20.

My staged B-9 patch covers 6 of the 20. The residual 14 is not a scattered
list — it is three whole subsystems:

| subsystem | engine lines | validator references |
|---|---|---|
| language **reserve** (soft headroom) | 21 helpers | **0** |
| skill allocation | 116 | **0** |
| employee operational quality | 82 | **0** |

The validator models coverage, breaks, week boundaries and language **hard
minimums**. It does not model these three at all, and their metrics feed both
the quality tuple and the production gate.

**So B-9 was framed wrongly.** It is not "16 metrics need derivations". It is
"three subsystems have no independent model, and their outputs gate releases".
Adding seven derivations closes the coverage/boundary part; the rest is either
a substantial validator build or an explicit decision that engine-only metrics
must not gate a release.

---

## 4. Re-evaluated severity

Reachability first, blast radius second. That ordering is deliberate: C-2 has a
wider blast radius than B-11 and ranks below it because it cannot be reached
through the supported workflow.

| # | finding | severity | live? | evidence |
|---|---|---|---|---|
| 1 | **S11-1** floor losses have no cap and no gate | **HIGH** | **YES — observed** | sweep case 2: `floor_losses_from_breaks=3`, gate PASS, floor 160→159 |
| 2 | **B-11** unmatched names fail open | HIGH | reachable | SAKS_NEW carries a real unreconciled row |
| 3 | **C-3** two-word preference vocabulary | HIGH | latent | 0/15 workbooks today; the sheet is free text by design |
| 4 | **B-10** break slice floor used as a cap | MEDIUM | yes | 112 planned / 0 completed every run |
| 5 | **Root cause A** 18 cross-metric fallbacks | MEDIUM | latent | 10 sites substitute the 80% tier for the floor |
| 6 | **Root cause B** 90 permissive shadow defaults | MEDIUM | latent | inside the release gate; cap 20 vs 14 |
| 7 | **S15-3** phases run below their declared minimum | MEDIUM | yes <1800s | `target_lock_recovery` 43s vs 65s at 600s |
| 8 | **S6-1** nesting group + mixed leave = silent UNSAT | MEDIUM | latent | INFEASIBLE in 0.04s, no cause reported |
| 9 | **B-9 / class D** three unmodelled subsystems | MEDIUM | structural | 20 of 51 decision metrics |
| 10 | **S9-2** dominance vs lexicographic disagree | LOW-MED | latent | affects alternatives, not the release pick |
| 11 | **C-2** unvalidated instruction booleans | LOW-MED | **not reachable in Excel** | dropdowns on all ten flags |
| 12 | **S6-2 / S13-2** 213 dead lines + an unreachable check | LOW | n/a | incl. a dead budget planner that reads as policy |
| 13 | B-4, B-6, misc low items | LOW | various | measured, no symptom |

### Corrections to my own earlier claims

1. **B-9's count was wrong** — 16 → **20** (alias-resolved), and its framing was
   wrong: subsystems, not metrics.
2. **S13-1 was under-counted** — 1 site → **10**, six in selection code.
3. **C-2 was overstated** — HIGH → LOW-MEDIUM once I checked the workbooks
   rather than only the parser.
4. **Task #37 / B-4 was mis-framed** — not "fund it or not"; at 3600s it gets
   139s against a 65s minimum. The issue is only below ~1200s.
5. **"B-5 is Stage-2 only"** — wrong twice; B-5 was Stage-1, and there is no
   problem in either stage. Both objectives are genuine weighted sums
   (343/343 and 152/152 terms decisive).

### What is sound, and worth not breaking

Measured, not assumed: checkpoint identity (S2), budget allocation exactness
(S15-2), the polish→validate ordering (S15-1), `NOT_ENFORCED` gate semantics
(S10-0), before/after metric symmetry (S8-0, 39 pairs, 0 asymmetries), the
minimum-exception proof (S7-2), the per-duration break-window contract check
(S7-1), and the quality tuple's correct prefix branching (S9-0).

---

## 5. Fix order, and why

Ordered by *reachability × evidence*, not by severity label.

1. **S11-1 — cap and gate floor losses.** The only finding with a live
   observation. Add `quality_max_floor_losses_from_breaks`, gate it in
   `production_quality_gate`, and stop line 14310 borrowing the target cap.
   Fixing this alone would have flagged the 160→159 regression in case 2.
2. **B-11 + C-3 together.** They are the same defect at two levels — an
   unmatched *name*, and a matched name whose *value* is not understood.
   Fixing B-11 alone leaves the cheaper half open. B-11 is already staged.
3. **Root cause A — the 18 fallbacks.** Mechanical, verifiable, no behaviour
   change expected (all latent), and it removes a whole class.
4. **Root cause B — delete the 90 shadow defaults.** `ParsedInput` is the
   single source of truth; a second contradictory answer at the call site *is*
   the defect. Engine-file-local, so contained.
5. **B-9 as staged (7 metrics)** — then a decision on the three unmodelled
   subsystems, which is a scoping question for the authors, not a patch.
6. **S15-3 — enforce `PHASE_MINIMUM_VIABLE_SECONDS`.** Skip a phase allocated
   below its own floor; give the seconds to one that can use them.
7. **B-10**, then the low items.

**Nothing above is applied.** The sweep is still importing the release tree;
4 of 6 cases remain.
