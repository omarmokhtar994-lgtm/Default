# RC9.2.1 Correction Pass 01 — Candidate-Ranking Numeric Integrity

**Release under work:** L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1
**Baseline engine SHA256:** `56ec2eefe64b56e85d6d5b3d492d052778cf9b4b3a8a57293bf106139fbc441a`
**Production baseline:** RC9.1 (`da21c3ba…`) — unchanged, still the live engine
**Scope:** one consolidated pass over candidate-ranking numeric integrity and
release identity. No optimizer redesign, no rule changes, no new constraints.

---

## Finding 1 — Balance/overage terms were unreachable whenever the floor was missed

**Severity:** high — defeats the stated RC9.2/9.2.1 ordering contract
**Status:** FIXED, guarded, causation still unproven (see Open Questions)

### Root cause

`_candidate_quality_tuple` ranks candidates by lexicographic tuple comparison.
Positions 9 and 10 held `floor_deficit_sum` and `floor_deficit_max` as **raw
floats**, rounded only to 8 decimal places. The balance/overage block sits at
positions 23–30.

Lexicographic comparison stops at the first differing element. `floor_deficit_sum`
is a sum of real-valued ratio deficits, so any two candidates that differ at all
in sub-floor coverage differ in that float — and the comparison terminated there,
before the overage terms were read.

Verified by executing the engine's own selector on coverage-identical candidates:

```
floor deficit differs by 1e-8, overage differs by 141 FTE
  winner  : the WORSE-overage candidate
  decided at tuple index 9   (-1.2 vs -1.20000001)
  overage term lives at index 23 — never consulted
```

The documented ordering — target → protected tiers → floor → quality debt →
safety → balance/overage → higher-tier upside — was therefore **inoperative for
every scenario that misses the configured floor anywhere**, which is precisely
the scenario class the RC9.2 balance work was built to improve.

NMG EN is such a scenario: `before_floor` = 232 of 252 active intervals, so 20
intervals sit below floor and `floor_deficit_sum` is a nonzero continuous value.

This is not floating-point noise. The values are deterministic. It is *spurious
precision*: a difference of 1e-8 in aggregate ratio deficit carries no
operational meaning, but under lexicographic ordering it outranked 141 FTE of
avoidable overage.

### Correction

Compare deficits at an operationally meaningful granularity instead of full
float precision. `FLOOR_DEFICIT_COMPARISON_QUANTUM = 0.01` — one percentage
point of summed interval coverage deficit. `_deficit_bucket()` maps a deficit
to an integer bucket so the comparison is exact and representation-independent.

**The priority model is preserved, not weakened.** A materially worse floor
deficit (≥ one quantum) still outranks every balance and overage term, exactly
as the contract requires. Only differences too small to matter operationally now
fall through and let the balance terms discriminate.

Raw unrounded deficits remain in the metrics dict and in every report. The
constant governs *comparison only*, never reporting. `candidate_selection_breakdown`
now emits `floor_deficit_sum_bucket` and `floor_deficit_comparison_quantum`
alongside the raw value so any ranking decision is auditable after the fact.

The final tuple term (`target_deficit_sum`) keeps full precision deliberately —
nothing ranks below it, so it cannot mask anything and serves as a deterministic
last-resort tie-break.

---

## Finding 2 — Deficit metrics had no before-break variant

**Severity:** low — latent hazard, not a live defect
**Status:** FIXED

`calculate_metrics` computed `target_deficit_sum`, `floor_deficit_sum` and
`floor_deficit_max` from `after_pct` only. Every other coverage metric in that
loop is accumulated as a before/after pair; these three were the sole exception,
and no `before_floor_deficit_sum` key existed anywhere in 19,505 lines.

Before-break skeleton ranking (`select_best_before_skeleton`,
`select_stage1_hint_skeleton`) therefore tie-broke on a key that structurally
could not carry a before-break meaning.

**This was not producing wrong results.** `ensure_before_break_metrics` evaluates
skeletons with no breaks applied, so `after_pct == before_pct` and the value was
numerically correct. It is fixed because the asymmetry is a trap: any future
change that makes the two diverge in that path would silently corrupt Stage-1
selection with no test to catch it.

`before_*` and explicit `after_*` variants are now emitted. `_prefixed_metric()`
resolves the prefixed key when present and falls back to the bare key — so
candidates restored from older checkpoints or replayed evidence still compare
correctly instead of scoring as zero-deficit (which would rank stale candidates
as perfect).

---

## Finding 3 — Production runner stamped every run with the wrong release

**Severity:** medium — defeats the exact-engine-identity release gate
**Status:** FIXED at root

`RUN_UNIVERSAL_PRODUCTION.py:13` hardcoded
`RELEASE = "L6.3.2.4-RC9.2-PROTECTED-BALANCE-RC1"` while the engine it invokes
reports `VERSION = "L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1"`.

`RELEASE` is written into run identity and manifest output. Every RC9.2.1 run
was therefore **recorded under the RC9.2 release name** — directly contrary to
the hard gate requiring exact engine identity, and a live risk of misattributing
evidence between the two branches.

Fixed by deriving `RELEASE` from the engine's own `VERSION` constant at startup,
making this class of drift impossible rather than merely corrected once. It
fails loudly if the constant cannot be read: a wrong-but-plausible release string
is worse than no run.

---

## Files changed

| File | Change |
|---|---|
| `engine/_tools/l632_universal_scheduler.py` | `FLOOR_DEFICIT_COMPARISON_QUANTUM`, `_deficit_bucket()`, `_prefixed_metric()`; quantized positions 9–10 of the quality tuple; before/after deficit accumulators and metric keys; breakdown reports bucket + quantum |
| `engine/RUN_UNIVERSAL_PRODUCTION.py` | `RELEASE` derived from engine `VERSION` |
| `tests/test_rc9_2_1_selector_integrity.py` | new — 25 ranking-integrity guards |
| `tools/replay_candidate_ranking.py` | new — causation harness for recorded leaderboards |

## Why the change is safe

- **The engine's own selfcheck output is byte-identical** before and after,
  including all four pinned selector replays. Those replays route through
  `select_export_candidates` → `_candidate_quality_tuple`, so they genuinely
  exercise the changed path. The NMG12 replay carries floor deficits of 4.2 vs
  4.0 — 20 quanta apart — and still resolves identically, confirming the fix is
  conservative where deficit differences are material.
- No constraint, rule, objective weight, or solver parameter was touched.
- No metric was removed or renamed; only additive keys.
- Ordering *intent* is unchanged — only the precision at which one term is
  compared.
- Guards fail red on the unmodified baseline and green after the fix.

## What could regress

Stated plainly, because this is a selection-behaviour change:

1. **Champion selection will change on some scenarios.** That is the intent, but
   it means before/after KPI comparison on every regression scenario is
   mandatory before promotion. A candidate that previously won on an 8th-decimal
   deficit edge will now lose to a better-balanced peer.
2. **Quantum calibration is a judgement call.** 0.01 is defensible (one point of
   aggregate coverage deficit) but not derived from data. If real candidate pools
   cluster tighter than that, the fix under-discriminates on floor; wider, and it
   does nothing. It is a single named constant, tunable in one place, and
   reported in every breakdown so its effect stays visible.
3. **Bucket boundary effects.** Any bucketing creates edges (1.0149 vs 1.0151).
   Inherent and acceptable versus deciding on 1e-8.
4. **Runs will now stamp a different release string** than earlier RC9.2.1 runs.
   That is the correction, but tooling that string-matches on the old value will
   need updating.

## Tests executed

| Test | Result |
|---|---|
| `tests/test_rc9_2_1_selector_integrity.py` (25 guards) | **25/25 PASS** on fixed engine |
| Same suite against unmodified baseline | **FAILS (3 failures, 9 errors)** — confirms the guards catch the real defect |
| `RUN_UNIVERSAL_PRODUCTION.py --selfcheck` | **PASS**, RC=0 |
| `l632_universal_scheduler.py --selfcheck` | **PASS** 4/4, output byte-identical to baseline |
| `py_compile` across all package modules | **PASS** |
| OR-Tools 9.15.6755 CP-SAT smoke | **OPTIMAL** — Gate 1 dependency half satisfied |

Not executed: any fresh CP-SAT solve on a real scenario workbook. None is
present in this environment.

## Open questions — what is NOT proven

**The 1103.08 → 1244.11 FTE regression is not yet attributed.** The masking
defect is proven to exist and is fixed. Whether it *caused* that specific
regression is still open, and two outcomes remain consistent with the evidence:

- the overage was **bought** — the honest price of +14 floor intervals; or
- the overage was **avoidable** — a lower-overage candidate with equal coverage
  existed and lost to the masking.

`tools/replay_candidate_ranking.py` settles this in seconds, without a solve, as
soon as the candidate leaderboard from
`NMG_EN_FIXED_NESTING_REST_SAFE_REGRESSION_CLEAN2__1__RC9_2_1_4H_SKELETON_RESULTS.zip`
is available.

A synthetic pool study (4,000 pools × 15 floor-equivalent candidates) found the
champion changed in 78.2% of pools, mean avoidable overage saved 109.0 FTE. This
is **illustrative of the mechanism, not evidence about the real run** — the
magnitude is entirely determined by the assumed distribution, and the pools were
deliberately constructed floor-equivalent, which is the condition where the fix
bites. It shows that under floor-equivalence the old ordering chose essentially
arbitrarily with respect to overage. It does not show the real pool was
floor-equivalent.

Still required before any promotion decision:

- RC9.1 engine source, to establish whether this ordering is what *changed*
  between RC9.1 and RC9.2.1, or was present in both
- The NMG EN workbook (`…CLEAN2 (1).xlsx`, input SHA `fd6b0cc9…`) for a fresh
  targeted skeleton run
- RC9.1 baseline KPI evidence for every gate defined as "not materially worse
  than RC9.1"
- NMG SP validator reconciliation (engine ~121/122/122 vs validator ~125/126/126)
  — untouched by this pass

## Release recommendation

**NO-GO for production. RC9.1 remains the live engine.**

This pass corrects three real defects and proves the corrections with guards
that fail on the baseline. It does not constitute release evidence: no fresh
CP-SAT solve was run against any production scenario, and the headline overage
regression remains unattributed. Promotion requires the regression corpus.
