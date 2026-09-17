# Defect register — every finding, sorted

One row per finding across the whole engine review: the B-list from the earlier
work and the C/S findings from the section-by-section pass.

Sorted by **reachability first, blast radius second**. That ordering is
deliberate and it moves things: C-2 has the widest blast radius in the register
and sits in the low band, because it cannot be reached through the supported
workflow.

**Status** — `LIVE` observed happening; `REACHABLE` no barrier, not yet
observed; `LATENT` real defect, currently unreachable; `STRUCTURAL` a gap in
what is checked rather than a wrong line; `DEAD` unreachable code.

---

## Band 1 — open, high

| # | finding | sev | status | impact if it fires | where |
|---|---|---|---|---|---|
| 1 | **S11-1** `floor_losses_from_breaks` has no cap and no gate | **HIGH** | **LIVE** | Break placement destroys floor coverage and every gate passes. The only bound borrows the *target* cap (declared 6) and applies only when `target_loss_gate_mode == "fail"`, whose default is `"warn"` — so by default floor losses are unconstrained while target losses are hard-capped. Floor is the safety threshold *below* target. | 14308–14310, 11790 |
| 2 | **B-11** name-matched sheets fail open | **HIGH** | REACHABLE | A name spelled differently from the roster silently discards that person's approved **leave** and hard **OFF**; they become schedulable and are rostered. Run passes contract, quality gate, parity and validation. | 1447, 1476, 1497 |
| 3 | **C-3** preference vocabulary is two exact words | **HIGH** | LATENT | `Annual Leave`, `A/L`, `Vacation`, `Sick`, `OFF (approved)`, `Off Day`, `RD`, `Leve` all return `"other"`, which falls through all three blocking branches. Same outcome as B-11, one level down. No dropdown on the sheet, no warning. | 3475, 8750–8767 |

**Evidence:** #1 — sweep case 2 (`AE_AR_Choice`): `floor_losses_from_breaks=3`,
gate `PASS`, floor `160 → 159` against the authors' baseline.
#2 — `SAKS_NEW` ships a real unreconciled row (`Associate 051`, previous
Saturday `22:00 - 07:00`).
#3 — 0 of 15 workbooks affected today; the Preference sheet carries **zero**
data validations and invites free text by design.

## Band 2 — open, medium

| # | finding | sev | status | impact if it fires | where |
|---|---|---|---|---|---|
| 4 | **B-10** break-slice constant is evidence for a cap, used as a floor | MED | LIVE | Adaptive break attempts are clamped so that **112 planned / 0 completed** on every run — the search does work that cannot finish. | break slice floor |
| 5 | **RC-A** 18 cross-metric fallbacks *(absorbs S8-1, S12-1, S13-1)* | MED | LATENT | A missing key silently substitutes a **different quantity**: 10 sites swap the fixed 80% tier for the **configured floor** (wrong on any workbook whose floor ≠ 0.80 — NMG12 is 0.85); 7 swap an after-break count for a before-break one, including in the break-loss guard. Six of the ten are in the **selection** path. | 18 sites, engine only |
| 6 | **RC-B** 90 permissive shadow defaults *(C-1 + S10-1)* | MED | LATENT | Gate limits read via `getattr(parsed, f, default)` where the default is looser than the declared one, **every time they disagree** — `999999` vs `6`/`0`, `2.0` vs `1.35`, `'off'` vs `'fail'`. Some sit **inside `production_quality_gate`**. Measured: cap 20 vs 14; adjacent limit 999999 vs 3. | 90 sites / 36 fields |
| 7 | **S15-3** phases run below their own declared minimum *(resolves B-4 / task #37)* | MED | LIVE <1800s | `PHASE_MINIMUM_VIABLE_SECONDS` is reporting-only. At 600s `target_lock_recovery` gets 43s against its own 65s minimum and spends it anyway; at 120–450s six phases get **0s**. At ≥2700s nothing is short. | phase_b_maturity |
| 8 | **S6-1** nesting group + mixed leave is silently UNSAT | MED | LATENT | `leave[a,d]` is pinned from the contract, then group equality adds `1 == 0`. Whole run dies **INFEASIBLE in 0.04s** with no cause reported anywhere — not in the log, the diagnostics, or the contract report. | 5518, 5578 |
| 9 | **B-9 / class D** 20 of 51 decision-driving metrics have no independent check | MED | STRUCTURAL | The residual after the staged patch is not scattered — it is **three subsystems the validator does not model at all**: language reserve (0 refs), skill allocation (0 refs / 116 engine lines), employee quality (0 refs / 82 lines). Their metrics gate releases with no second opinion. | validator |

## Band 3 — open, low / low-medium

| # | finding | sev | status | impact | where |
|---|---|---|---|---|---|
| 10 | **S9-2** Pareto dominance and the lexicographic order disagree | LOW-MED | LATENT | 15 dominance dimensions vs ~31 tuple terms; ~15 terms are not dimensions, so the filter can discard the lexicographic winner. **Bounded**: the release pick comes from the full pool, so only the *alternative* exports (`MAX_FLOOR`, `BALANCED`, `SAFER_BALANCED`) can omit the best soft-dimension option. | 10704, 10952 |
| 11 | **C-2** instruction booleans have no unrecognised state | LOW-MED | **not reachable in Excel** | `yes()` maps anything outside eight words to `False`, silently. Would disable leave / hard-OFF / preferences for the **whole roster** from one cell. Mitigated by stop-style dropdowns on all ten flags; survives only via paste, programmatic writes, or non-Excel editors. | 326, 2444–2448 |
| 12 | **CM-1** one canonical field is not its own alias | LOW | LATENT | `after_avoidable_overage_top10_concentration` is the only field of 41 omitting its own name, so re-canonicalizing an already-canonical surface drops it to `MISSING_CANONICAL_METRIC`. A trap for any new caller, since `compare_metric_surfaces` canonicalizes its inputs. | canonical_metrics |
| 13 | **S9-1** unprefixed after-terms inside the before-break ranking | LOW | LATENT | Seven terms are after-break quantities read without a prefix, beside two that are prefixed. Correct only because all four `prefix="before"` callers pass `no_break_metrics`; the invariant is stated nowhere. | 10196–10261 |
| 14 | **S6-2** the only nesting-group contract check is unreachable | LOW | DEAD | Guarded by `nesting_group and any(fixed_schedule)`, which the parser makes mutually exclusive. 0 associates across 15 workbooks can satisfy it. The engine has one nesting check that cannot fire and none for the condition that kills the model (#8). | 3341, 1511 |
| 15 | **S13-2** 213 dead lines across 6 functions | LOW | DEAD | Two mislead rather than merely sit there: a complete superseded refinement phase, and a **dead budget planner whose docstring describes exactly the starvation failure B-3 investigated** — anyone investigating budgets reads it as policy. | 6 functions |
| 16 | **S6-3** the fixed/nesting subsystem is unexercised | LOW | STRUCTURAL | 0 of 15 workbooks define a nesting group; `Fixed Request Use = No` throughout. Both #8 and #14 live in exactly this untested path. | coverage gap |
| 17 | misc: `minute_of_day` ambiguity at `1`; `to_float` (58 permissive sites) beside `strict_float` (11 strict) in one contract layer; 3 dead determinism guards; 54 unreferenced RC-marker constants; progressive audit-key rewrites | LOW | mixed | Individually harmless; together they are the texture that makes the real defects above easy to introduce. | various |

---

## Fixed and shipped

| # | finding | evidence |
|---|---|---|
| B-1 / B-1c / B-1d / B-2 | stage-aware release gates — a skeleton-only run no longer fails parity with 41 phantom mismatches | 8 recorded audits replay identically |
| B-3 | Stage-1 slice floor was measured cold and applied to warm solves; default 240 → 45 | warm-curve JSON; sweep in flight |
| B-7 | 43 workbook parameter routes | 34 tests |
| B-8 | validator under-reported next-Sunday adjacent imbalance | now walks adjacent quarter slots |

## Staged, not applied *(the sweep is still importing the tree)*

| # | what | proof |
|---|---|---|
| B-9 | validator derives 7 previously engine-only metrics; parity surface 41 → 48 | 8/8 pass patched, 27 failures unpatched |
| B-11 | name-matched sheets fail closed, with a **named** departed-associate list as the only escape; empty rows stay soft | 14/15 workbooks clean; gate 17 suites PASS |
| B-12 | single-term header lookup no longer matches a prose banner | 0 of 15 contract hashes change |
| — | fast logic-check suite, 41 tests in 5 ms | **8 of 8 mutations caught** |

## Investigated — no defect

| # | finding | what the measurement showed |
|---|---|---|
| B-5 | Stage-1 objective conditioning | genuine weighted sum; **343/343 terms decisive** |
| B-6 | symmetry on interchangeable associates | real at 6.2e23 but presolve installs a 137×24 orbitope; `symmetry_level` already 2 |
| S7-0 | break objective | **152/152 terms decisive** |
| S2 | checkpoint / resume | `run_id` covers input, contract, engine, seed, parameters, git; writes are atomic |
| S7-1/2/3 | pattern legality, minimum-exception proof, `MODEL_INVALID` handling | all guarded |
| S8-0 | metric arithmetic | every division guarded; 39 before/after pairs, 0 asymmetries |
| S9-0 | quality tuple prefix handling | branches correctly where 7 other sites fall back |
| S10-0 | disabled gates | report `NOT_ENFORCED`, never `PASS` |
| S14-0 | CLI defaults | 72 flags vs 117 fields — no contradiction |
| S15-1/2 | polish→validate ordering; budget allocation | correct order; phase sum equals total in every configuration |

---

## Corrections to my own earlier claims

Recorded so the register is not read as if it were right first time.

1. **B-9's count and framing** — 16 → **20** unchecked (alias-resolved), and the
   residual is three subsystems, not a metric list. My first scan said 36; that
   was also wrong (week-boundary aliases counted as gaps).
2. **S13-1 under-counted** — 1 site → **10**, six of them in selection code.
3. **C-2 overstated** — HIGH → LOW-MED once I checked the workbooks, not just
   the parser.
4. **Task #37 / B-4 mis-framed** — not "fund it or not"; at 3600s it gets 139s
   against a 65s minimum. Only below ~1200s is it short.
5. **"B-5 is Stage-2 only"** — wrong twice: B-5 was Stage-1, and neither stage
   has the problem.
6. **B-4 variance** — attributed to wall clock; the precise cause is
   multi-worker nondeterminism, which the engine documents at 17975.

---

# Status as of the post-apply state

The bands above are the register as first written. This section supersedes
their status columns.

## Tally (distinct findings; the "investigated — no defect" ten are excluded)

    total real findings                     22
      fixed and verified before today        4   B-1/B-2 group, B-3, B-7, B-8
      fixed and applied today                4   S11-1, B-11, B-12, C-3
      partially fixed today                  1   B-9  (W7a landed, W7b open)
      still open                            13

**All three Band-1 HIGH findings are now closed.** Nothing open is rated HIGH.

## Closed today, with what proves it

    S11-1  floor losses now have a metric, a cap and a gate     gate 18 suites
    B-11   name-matched sheets fail closed                      TRUE POSITIVE on
                                                                SAKS_NEW real data
    B-12   header lookup cannot match a prose banner            0 of 15 contract
                                                                hashes change
    C-3    preference vocabulary fails closed                   0 false positives
                                                                across 15 workbooks
    B-9    7 metrics independently recomputed, parity 41 -> 48  W7b still open

## Still open — 13

    B-10    break-slice constant is a cap used as a floor        MED   behavioural
    RC-A    18 cross-metric fallbacks                            MED   inert
    RC-B    90 permissive shadow defaults                        MED   inert
    S15-3   phases run below their declared minimum              MED   behavioural
    S6-1    nesting group + mixed leave silently UNSAT           MED   inert
    B-9b    3 subsystems the validator does not model            MED   scoping call
    S9-2    Pareto dominance vs lexicographic order disagree     LOW-MED behavioural
    C-2     instruction booleans have no unrecognised state      LOW-MED not reachable
    CM-1    one canonical field is not its own alias             LOW   inert
    S9-1    unprefixed after-terms in the before-break ranking   LOW   inert
    S6-2    the nesting-group contract check is unreachable      LOW   inert
    S13-2   213 dead lines across 6 functions                    LOW   inert
    S6-3    the fixed/nesting subsystem is unexercised           LOW   structural
            (plus the misc bundle: minute_of_day, to_float/strict_float, 3 dead
             determinism sites -- carried as one low item)

## How to sequence the remaining work

The distinction that matters is **not** severity, it is whether a change can
alter a produced schedule.

**Inert changes** -- parsing, reporting, validation, dead code. The gate can
prove these. Group them freely and gate after every step. That is exactly what
`tools/apply_fix_plan.sh` did today: five changes in one session, gate green at
every step, then a contract smoke across 15 workbooks confirming zero false
positives. Total cost, one session.

Grouping without per-step gating is the thing to avoid. The B-9 applier was
incomplete and the per-step gate caught it immediately; batched to the end, that
failure would have surfaced underneath four later changes and been far harder to
attribute.

**Behavioural changes** -- anything that alters what the solver produces. These
cannot be grouped, because if two land together and the sweep moves, the move
cannot be attributed to either. Each needs its own A/B with repeats, since
multi-worker CP-SAT is nondeterministic and the effect sizes here are around one
interval.

Exactly one behavioural change went in today (the now-unconditional
joint-refinement bound), which is why #48 exists and why it is the one item
blocking a clean claim about this release.

Of the 13 open findings, **9 are inert and 3 are behavioural** (B-10, S15-3,
S9-2); B-9b needs a scoping decision before it is either. So the bulk can go in
one more grouped, per-step-gated pass, and only three need individual A/B runs.
