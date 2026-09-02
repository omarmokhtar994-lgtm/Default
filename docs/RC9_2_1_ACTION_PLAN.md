# RC9.2.1 — Status and Action Plan

Written to replace a list of blockers with a list of actions. Everything marked
DONE was executed in this repository; everything marked ACTIONABLE needs only
compute; only two items need an artifact nobody here holds.

## Where the gates actually stand

| Gate | Status | Evidence |
|---|---|---|
| 1 Environment / smoke | ✅ **PASS** | OR-Tools 9.15.6755, CP-SAT solving, both selfchecks, py_compile clean |
| 2 NMG EN vs RC9.1 | ⛔ **needs RC9.1** | scenario now runs; the comparator does not exist |
| 3 NMG SP reconciliation | ✅ **PASS** | 6/6 coverage metrics exact after the carry-in fix |
| 4 GDI REAL28 24/7 | 🔸 **actionable** | skeleton-only so far; needs one full run |
| 5 Cricut break regression | ⚠️ **2 PASS, 1 FAIL** | measured for the first time — see below |
| 6 11H/3OFF + separate OFF | ✅ **PASS** | 22/22 associates on 11H with exactly 3 OFF, 0 violations |
| 7 Resume / timeout | 🔸 **half done** | resume refusal PASSES; timeout untested |
| 8 Independent validation | ✅ **3 PASS** | NMG SP, Cricut Voice, Cricut Chat all 0 hard failures |
| 9 Regression quality vs RC9.1 | ⛔ **needs RC9.1** | comparator does not exist |

Seven of nine are closed or one run away. Two are genuinely blocked.

## Gate 5 — the finding

Three full runs with the break stage executed:

| Scenario | Verdict | Detail |
|---|---|---|
| NMG SP | ✅ PASS | target −3, floor −2 of 126 active; 0 exceptions, minimum proven |
| Cricut Voice | ✅ PASS | target −2, floor −2 of 264 active; 0 exceptions, minimum proven |
| **Cricut Chat** | ❌ **FAIL** | **target 187 → 132 (−55, 22.7%)**, floor 227 → 195 (−32), 2 language reserve quarters lost |

**Root cause on Chat.** The break stage could not find a compliant placement and
fell back to `diagnostic_zero_exception_fallback` — a mode that guarantees zero
break *exceptions*. It bought that by concentrating breaks: `max_concurrent_breaks_observed = 8`
against a configured maximum of **4**, producing **68 concurrency violations**.
`coordinated_repair_attempted = 1`, `coordinated_repair_committed = 0` — the
repair ran and committed nothing. Elapsed 813s of a 900s budget.

The engine's own verdict on that run is
`phase_c_promotion_status = ELIGIBLE_WITH_DECLARED_QUALITY_WARNINGS` and
`functional_status = PASS_FINAL_SCHEDULE_GENERATED`. A 22.7% target loss is
being carried as a quality warning rather than a gate failure, because
`break concurrency gate mode = Warn` in Engine Defaults.

This is exactly the Stage-2 degradation §16 warns about, on the scenario §5D
names. It is now measured rather than suspected.

**Deliberately not fixed here.** RC9.2 chose not to redesign the Stage-2 model to
avoid regression risk, and that judgement still holds — a break-model change is
not something to attempt on one scenario's evidence. The decision is yours;
options in priority order:

1. Raise `break concurrency gate mode` from `Warn` to `Block` so a run that
   violates the cap 68 times cannot report as promotable. Configuration only,
   no model change, immediately testable.
2. Make `diagnostic_zero_exception_fallback` respect `maximum_concurrent_breaks`
   — arguably a defect rather than a design choice, since the fallback ignores a
   configured hard limit.
3. Investigate why `coordinated_repair` committed nothing on Chat while
   succeeding elsewhere.

## Actionable now — no new artifacts required

| # | Action | Closes | Cost |
|---|---|---|---|
| A1 | Full GDI REAL28 run with break stage | Gate 4, +1 Gate 5, +1 Gate 8 | ~1 run |
| A2 | Timeout-recovery test (short limit, verify truthful artifacts) | Gate 7 | minutes |
| A3 | Full AE_AR_B2B and NMG_EN&SP runs | broadens Gates 5 and 8 | ~2 runs |
| A4 | Re-run Chat at a larger budget / alternate widths | tests whether the fallback is budget-driven | ~1 run |
| A5 | Decide and apply the Gate 5 concurrency option above | Gate 5 | config + 1 run |

## Blocked — and the exact ask

**B1 — RC9.1 comparator.** Gates 2 and 9 are *defined* as "not materially worse
than RC9.1". Neither the RC9.1 engine source (sha `da21c3ba…`) nor per-scenario
RC9.1 KPIs exist in anything delivered. The one RC9.1 artifact present is the
Cricut resume checkpoint, whose input (`675fd57a…`) is also not in the kit — so
it cannot be re-run either.

*Either* of these unblocks both gates:
- the RC9.1 engine source file — I run it against the same fixtures and produce
  the comparison directly, or
- RC9.1 result workbooks/summaries per scenario carrying before/after 100-90-80,
  floor, severe gaps, max consecutive gaps and avoidable overage.

This is the single highest-value outstanding artifact.

**B2 — Cricut Voice Gate 8 pair.** Narrowed from "wrong file" to a precise ask: a
Cricut Voice input with the same 40-name roster in which **Abdullah Khashab,
Maryam AbdulWahab, Zyad Mahrous and Mariem Mohamed** carry no fixed/leave/OFF
configuration. Note this is now optional for Gate 8 — that gate already passes on
three self-generated pairs.

## Tooling built to keep this cheap

| Tool | Purpose |
|---|---|
| `tools/release_gate_report.py` | evaluates gates 4, 5, 8 from run artifacts; marks 2 and 9 `REQUIRES_RC9_1_BASELINE` rather than guessing |
| `tools/replay_candidate_ranking.py` | re-ranks a recorded pool under both orderings, no solver |
| `run_tests.sh` | 86 guards plus both selfchecks, no workbook needed |
| `fixtures/` | four corrected fixtures that made blocked scenarios runnable |

The gate report is regenerated with one command over any results root, so every
future run updates the release picture automatically.
