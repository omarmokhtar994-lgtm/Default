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

---

## Update — RC9.1 comparator received; gates 2 and 9 are now decidable

The RC9.1 baseline arrived as a **consolidated metrics** package (stored at
`evidence/RC9_1_BASELINE.json`, with the supplier's provenance and caveats). It
is explicitly not a byte-identical replacement for the original RC9.1 result
artifacts, and it declines to assert GDI REAL28 and SAKS rather than inventing
them. B1 is therefore **partially closed**: gates 2 and 9 can be evaluated, at a
stated evidence class, on before-break quality only.

### First results

| Case | Gate 2 / 9 | Detail |
|---|---|---|
| NMG SP | **PASS_AGAINST_CONSOLIDATED_BASELINE** | target 126 vs 126, floor 126 vs 126 |
| Cricut Voice | **NOT_COMPARABLE_SEARCH_TRUNCATED** | explored 1 of 15 skeleton profiles |
| NMG EN historical | **NOT_COMPARABLE** | RC9.2.1 rejects the input; see below |
| AE AR B2B | **NOT_COMPARABLE** | hard contract failure, no solve |

### Two things the comparison surfaced

**1. RC9.2.1 refuses the NMG EN historical input, and is right to.**
`FIXED_CYCLIC_REST_CONFLICT`: Associate 003 carries Previous-Sat 23:00–08:00
into a Sunday 14:00–23:00 shift (**6.0 h** rest) and Associate 009 carries
20:00–05:00 into the same (**9.0 h**), against a 12 h minimum — both verified
through the engine's own `shift_parts`. RC9.1's NMG EN figure of 214 was
therefore obtained on an input that does not satisfy the current contract. No
same-input NMG EN comparison is possible without disabling a safety rule, which
is not something to do for a gate.

**2. Every RC9.2.1 evidence run was executed at 900 s against a 14,400 s design
point.** DEEP mode's default budget is 14,400 s. At 900 s the engine explores
**one** of its fifteen skeleton profiles (see A28 in `CODE_AUDIT.md`). The
Cricut Voice shortfall against RC9.1 — target −14, floor −13 — is very likely an
artifact of that, not an engine regression, and the gate now says so rather than
scoring it.

### The ask has changed

B1 is no longer "we have no comparator". It is now:

- **Re-run the scenario set at DEEP's real budget** (14,400 s) before drawing any
  RC9.1 comparison. Every published RC9.2.1 quality number so far is from a
  six-percent-budget run.
- The RC9.1 engine source (sha `da21c3ba…`) would still be worth having: it
  would let the comparison be generated rather than transcribed, and would
  settle whether RC9.1 enforced cyclic rest against fixed Sunday shifts at all.
