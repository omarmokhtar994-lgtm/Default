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

---

# Correction Pass 02 — Engine ↔ Independent Validator Parity

Audit of `tools/independent_validator.py` (301 lines) against the engine's
`calculate_metrics`, prompted by the recorded NMG SP discrepancy
(engine ~121/122/122 vs validator ~125/126/126).

## Ruled out by direct comparison — the tier-counting math agrees

The ±4 is **not** a coverage-formula difference. Both sides were read line by
line and match exactly:

| Convention | Engine | Validator | Agree |
|---|---|---|---|
| Active-interval guard | `if not parsed.active[d][i]: continue` | same | yes |
| Effective FTE | `Σ raw × eff / qpi` | `sum(vals) × eff / qpi` | yes |
| Zero/blank demand | `pct = x/req if req > 0 else 1.0` | identical | yes |
| Tier epsilon | `>= 0.90 - 1e-9` | `>= .9 - 1e-9` | yes |
| Target/floor epsilon | `pct + 1e-9 >= ratio` | identical | yes |
| Previous-Saturday carry-in | `start = -96 + st//15` | identical, clamped to Sunday | yes (clamp unreachable for ≤11h shifts) |
| Beyond-horizon quarters | never queried | dropped | yes |

So the leading hypothesis for the NMG SP ±4 is an **artifact-role mismatch** —
engine after-break figures compared against a validator run on a
`BEST_BEFORE_BREAKS` export, or vice versa. The validator already records
`artifact_role` in its JSON (`BEST_BEFORE_BREAKS` / `FINAL_AFTER_BREAKS`) and the
engine tracks `target_losses_from_breaks` / `floor_losses_from_breaks`. Checking
those two fields against each other settles it immediately. **Not confirmable
without the NMG SP input/output pair.**

## Finding 4 — Validator long-shift threshold disagreed with the engine

**Severity:** high — a validator false positive blocks a valid release
**Status:** FIXED

The validator used `duration_min >= 660` to decide long mode (3 OFF rather than
2). The engine uses `>= 630` in all three of its sites: the CP-SAT model, its own
`validate_schedule`, and aggregate guidance.

A shift in **[630, 660)** — e.g. 10.75h — is therefore long mode to the engine
and short mode to the validator. The engine builds the schedule with 3 OFF; the
validator demands 2 and raises `OFF_COUNT_VIOLATION`. Under the release gates
any validator mismatch blocks the release, so this fails a correct schedule.

Fixed at root: `LONG_SHIFT_MIN_DURATION_MIN = 630` is now a single named engine
constant, referenced by both sides. The three bare `630` literals in the engine
were replaced, and a guard asserts none return.

**Independence is not compromised.** Independence means the validator recomputes
coverage from the exported workbook rather than trusting optimizer audit values —
which it still does. It does not mean keeping a second private copy of a contract
constant; that is not a cross-check, it is a silent disagreement. Guards pin that
the validator still accumulates its own tier counts and never calls
`calculate_metrics`.

## Finding 5 — Validator understated avoidable overage at floating-point boundaries

**Severity:** medium — disagreement on the release's headline metric
**Status:** FIXED

The engine converts an effective requirement into whole associates as
`ceil(req × target / eff − 1e-9)`. The validator omitted the tolerance.

When `req × target / eff` is integral in exact arithmetic but lands marginally
above integral in floating point, plain `ceil` rounds up a whole associate,
overstating unavoidable staffing and **understating avoidable overage** by one
associate-equivalent on that interval.

Reachable, and found by random search over 400,000 contract draws: **64 hits
(0.016%)**. Example — `req=45.56, eff=0.9112, target=0.90`: exact value 45.0,
engine 45 associates (41.004 effective), validator 46 (41.9152), a 0.9112 FTE
disagreement on that interval alone.

The engine is correct; the validator was wrong. `OVERAGE_CEIL_TOLERANCE` is now
a shared engine constant applied by both. A guard replays 200,000 random
contracts and requires exact agreement, plus a pinned test for the specific
boundary case.

## Files changed (pass 02)

| File | Change |
|---|---|
| `engine/_tools/l632_universal_scheduler.py` | `LONG_SHIFT_MIN_DURATION_MIN`, `OVERAGE_CEIL_TOLERANCE`; three bare `630` literals replaced |
| `engine/tools/independent_validator.py` | uses both shared constants |
| `tests/test_rc9_2_1_validator_parity.py` | new — 16 parity guards |
| `run_tests.sh` | new — fast gate, no solver or workbook needed |

## Tests (pass 02)

| Test | Result |
|---|---|
| `tests/test_rc9_2_1_validator_parity.py` | **16/16 PASS** |
| Same suite against unmodified baseline | **FAILS (3 failures, 7 errors)** |
| `tests/test_rc9_2_1_selector_integrity.py` | 25/25 PASS (unaffected) |
| Engine selfcheck | PASS, still byte-identical to the original baseline |
| Wrapper selfcheck | PASS |

## Correction to an earlier claim in this document's working notes

An initial hypothesis that the validator mishandled **zero-demand** intervals in
its avoidable-overage formula (missing the engine's `if req > 0` guard) was
**wrong**, and was disproved by direct numeric comparison before any change was
made: `ceil(0) == 0`, so both sides return identical values for `req = 0`. No
code was changed on that basis. Recorded here because the notepad requires
findings to be classified honestly rather than retained because they were
plausible.

## Still open after pass 02

- NMG SP ±4 attribution — needs the input/output pair; the discriminating check
  is `artifact_role` vs the engine's break-loss counters
- NMG EN overage causation — needs the 4H candidate leaderboard
- Whether RC9.1 shared the deficit-masking ordering — needs the RC9.1 engine source
- No fresh CP-SAT solve on any production scenario has been run

**Release recommendation unchanged: NO-GO. RC9.1 remains the production engine.**
