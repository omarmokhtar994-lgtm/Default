# AE results — the coverage root cause, located

First handoff to arrive with run artifacts. All six recomputed from source.
**Every RC5 number in your table verifies exactly**, on engine `0e6f6435…`,
~3,470 s per run. Your RC5 side is accurate; nothing there needs correcting.

What the artifacts show is that the conclusion drawn from them does not follow.

---

## 1. 71% of your after-break loss is roster, not optimiser

| Capacity class | Case | Before | After | Loss |
|---|---|---:|---:|---:|
| AMPLE | AE_AR_B2B | 167 | 167 | **0** |
| AMPLE | AE_FR_B2B | 112 | 112 | **0** |
| AMPLE | **AE_FR_Choice** | 112 | 106 | **6** |
| TIGHT | AE_AR_Choice | 139 | 139 | **0** |
| SHORT | **AE_IT_B2B** | 83 | 68 | **15** |
| SHORT | AE_IT_Choice | — | — | no schedule |
| | **ALL** | **613** | **592** | **21** |

613 → 592 reproduces your aggregate exactly. But **15 of the 21 lost intervals
(71%) occur on AE_IT_B2B**, which is short by 28.4 productive hours. On a roster
that cannot cover its demand, taking an hour of breaks per person *must* cost
coverage. That is arithmetic, not an optimiser defect.

Strip it out and the picture inverts: on the three capacity-ample cases the
total loss is **6 intervals, all of them on one case**, and two of three lose
nothing at all.

---

## 2. AE_FR_Choice is a genuine optimiser defect — and the engine proves it

The decisive table. `zero_target_slack_ratio` is the share of quarter-slots
already running at exactly target with no spare body:

| Case | Cap | Loss | Break capacity | Deficit | +HC | 0-slack |
|---|---|---:|---|---:|---:|---:|
| AE_AR_B2B | AMPLE | 0 | SUFFICIENT | 0 | 0 | 3.6% |
| AE_FR_B2B | AMPLE | 0 | SUFFICIENT | 0 | 0 | 1.8% |
| **AE_FR_Choice** | **AMPLE** | **6** | **SUFFICIENT** | **0** | **0** | **40.2%** |
| AE_AR_Choice | TIGHT | 0 | SHORT | 176 | 6 | 93.5% |
| AE_IT_B2B | SHORT | 15 | SHORT | 140 | 5 | 85.7% |

**AE_FR_Choice is the only case where the engine says break capacity is
SUFFICIENT, deficit is zero, no extra headcount is needed — and coverage was
lost anyway.**

The engine's own accounting says every break could have been placed without
giving up a single target interval. It gave up six. Supporting evidence from the
same run:

```
break_capacity_status              BREAK_CAPACITY_SUFFICIENT
break_capacity_deficit_quarters    0
additional_headcount_for_breaks    0
headcount_needed_for_breaks        14   (= current_headcount 14)
target_losses_from_breaks          6
global_best_before_target          112
final_before_target_loss_vs_global_best  0
```

The last two matter: the selector kept the globally best skeleton. **The loss is
entirely inside break placement.** Not candidate generation, not retention, not
selection — the three places your section 8 suspected first.

### Why this case and not the others

`zero_target_slack_ratio` predicts it cleanly:

- **1.8%, 3.6%** → trivial break placement → 0 loss
- **40.2%** → hard but solvable (deficit 0) → **this is where the optimiser fails**
- **85.7%, 93.5%** → capacity short → loss is forced

AE_FR_Choice sits in the hard middle: 40% of quarter-slots have no spare body,
so breaks must thread into the other 60%. Possible — the engine says so — but it
needs search, and it didn't get enough.

---

## 3. Every single run truncated at 3 of 15 profiles

```
AE_AR_B2B 3/15   AE_FR_B2B 3/15   AE_FR_Choice 3/15
AE_AR_Choice 3/15   AE_IT_B2B 3/15
stage1_profile_coverage_status = TRUNCATED_INSUFFICIENT_STAGE1_BUDGET
```

All five, at ~3,470 s. **12 of 15 configured skeleton strategies never ran in
any case.** On AE_FR_Choice specifically, the break stage had 3 skeletons to
choose from instead of 15 — and needed a break-friendly one.

This is the same chain I measured earlier: an objective spanning 800,000,000 : 1
across 77 terms forces a 15-profile portfolio to sample the frontier, and the
portfolio does not fit the budget.

---

## 4. My own runs: the before-break stage is stable

Two independent runs of AE_FR_Choice, before-breaks only, 900 s each (engine
RC5+P1+C1):

```
FRC_BEFORE_A   before_target 112
FRC_BEFORE_B   before_target 112
```

Both reproduce your 112 exactly, and each other. **So the skeleton stage is not
where the run-to-run variance lives** — that narrows the reproducibility problem
(F11) to the break stage or later. Full-schedule repeats are still running; I
will report whether 106 reproduces.

---

## 5. Answering your section 8 directly

| Your candidate root cause | Verdict |
|---|---|
| 1. After-break recovery weaker than skeleton generation | **CONFIRMED**, and now localised to one measurable case |
| 2. Break placement not jointly optimised enough with shift selection | **Consistent with the evidence.** The skeleton was globally best; the loss is purely downstream |
| 3. Candidate pools too small / over-filtered | **Partly** — 3 of 15 profiles is a small pool, but by truncation, not by filtering |
| 4. Selector cannot improve what was never generated | **Not the cause here.** `final_before_target_loss_vs_global_best = 0` |
| 5. Secondary objectives compete with coverage | **Very likely** — see the 800M:1 weight spread |
| 6. Time limits terminate search early | **CONFIRMED** — all five runs truncated |
| 7. Staged phases make irreversible early decisions | **Not shown.** The skeleton chosen was the best available |
| 11. Some failures are genuine business infeasibility | **CONFIRMED** — AE_IT_Choice (−46.6 h) and AE_IT_B2B (−28.4 h) |
| 13. Language-window has little impact | **Untested.** All six workbooks run `mode: OFF` |
| 15. RC5 safer but not a stronger optimiser | **Supported** — on capacity-ample cases RC5 loses coverage on exactly one, and by 6 intervals |

---

## 6. What to fix, in order

**1. Give the break stage more skeletons — not more time.**
Every run truncated at 3 of 15. The cheapest version: run fewer, better-chosen
profiles rather than 15 configured and 3 executed. The structural version is the
lexicographic objective, which removes the need for a portfolio at all.

**2. Exclude capacity-short cases from coverage benchmarks.**
Built and shipped in this session — see §7. AE_IT_B2B contributed 71% of your
headline loss while measuring the roster.

**3. Treat AE_FR_Choice as the regression test for break placement.**
It is the only case in the set with a provable, non-forced coverage loss. If a
change recovers those 6 intervals, the change is real.

**Not a priority:** candidate retention and selector logic. The evidence
exonerates both on this dataset.

---

## 7. Shipped this session

**Capacity-benchmark gate.** `capacity_diagnostics` now returns a verdict that
the run summary and log carry:

```
AE_IT_Choice   CAPACITY_SHORT   ineligible   -46.6h   max attainable  71%
AE_IT_B2B      CAPACITY_SHORT   ineligible   -28.4h   max attainable  95%
AE_AR_Choice   CAPACITY_TIGHT   eligible     +22.4h   max attainable 100%
AE_FR_Choice   CAPACITY_AMPLE   eligible    +103.0h   max attainable 100%
AE_FR_B2B      CAPACITY_AMPLE   eligible    +302.5h   max attainable 100%
AE_AR_B2B      CAPACITY_AMPLE   eligible    +361.2h   max attainable 100%
```

Example headline, AE_IT_Choice:

> Capacity-limited: 232 productive hours against 279 needed at the 85% target —
> short by 47 hours (17%). 11 associate-day(s) of leave are already deducted.
> This roster cannot exceed about 71% of requirement no matter how shifts or
> breaks are placed, so its coverage does not measure the optimiser and must not
> be averaged into a coverage benchmark. Add about 2 associate(s), reduce leave,
> or lower the target.

Plus, from earlier in this session: **P-1** (pre-solver memoisation, 5.4×,
byte-identical output) and **C-1** (four input-contract fidelity fixes).

**Gate: 14 suites, 485 tests, PASS.**

---

## 8. One new defect found while running

Both my `BEFORE_BREAKS_ONLY` runs returned `rc=4` with
`independent_validation: FAIL_METRIC_PARITY` on a `SKELETON_ONLY_COMPLETE`
artifact. The parity gate appears to compare after-break metrics that a
skeleton-only run does not produce.

If confirmed, **every before-breaks-only run fails its gate by construction** —
which would explain why nobody uses the mode, and it is exactly the cheap
diagnostic you want for this class of question. Worth 30 minutes.

---

## 9. The honest summary

> *Has RC5 improved the engine, or the controls around it?*

**Both, but unevenly, and the evidence now says so precisely.**

Real scheduling gains: break safety (31 vs 138 violations) and balance. Real
control gains: validation, identity, sealing, parity. **Coverage: no
improvement demonstrated** — and now we know why, which is the part that was
missing.

The single coverage defect in this dataset is 6 intervals on AE_FR_Choice, in
break placement, on a case where the engine's own accounting says it had the
room. That is a small, specific, testable target — a far better position than
"RC5 loses coverage after breaks," which was never actionable.
