# RC9.2.1 Consolidated Issue Register

Every reported failure, regression and gap from the delivered evidence
(`RELEASE_GATES.csv`, `RULE_VERIFICATION_MATRIX.csv`, `MICRO_TEST_MANIFEST.json`,
`REGRESSION_SCENARIO_MANIFEST.json`, the handoff notepad, and this session's own
execution), consolidated to root causes rather than symptoms.

## Consolidation

Twelve of the recorded PENDING/NOT_RUN entries shared **one** root cause:
`"OR-Tools unavailable offline"`. That is a single environment blocker, not
twelve defects. OR-Tools 9.15.6755 is now installed and solving, so they were
executed rather than re-reported.

| # | Issue | Root cause | Status |
|---|---|---|---|
| 1 | Balance/overage unreachable when floor missed | raw floats above the balance block in a lexicographic tuple | **FIXED** |
| 2 | Deficit metrics had no before-break variant | metric asymmetry in `calculate_metrics` | **FIXED** |
| 3 | Runner stamped runs with the RC9.2 release name | hardcoded literal drifted from engine `VERSION` | **FIXED** |
| 4 | Validator long-shift threshold 660 vs engine 630 | contract constant duplicated instead of shared | **FIXED** |
| 5 | Validator understated avoidable overage | missing ceil tolerance | **FIXED** |
| 6 | All 3 NMG EN fixtures fail preflight | fixture defect, engine correct | **FIXED** (repaired fixture) |
| 7 | Folder 12 validator pair mismatched | 33-associate input vs 40-associate output | **BLOCKED** — needs the real input |
| 8 | Skeleton leaderboards could not explain selection | deficit/overage columns never populated | **FIXED** |
| 9 | Folder 15 cannot test 11H/3OFF | fixture has `use_11h_3off=False`, only 540-min shifts | **MITIGATED** (unit guards) |
| 10 | Folder 17 cannot test directional assist | single Spanish rule, no English rule or mapping | **MITIGATED** (unit guards) |
| 11 | Carry-in overage charged as avoidable | no separation of solver-uncontrollable staffing | **FIXED** |
| 12 | M06/M09/M14 negative tests never executed | OR-Tools unavailable | **EXECUTED — all pass** |

## Issue 6 — NMG EN preflight, root cause and repair

**Root cause.** Not an engine defect. The engine's diagnosis is correct in both
variants, verified by hand:

* Historical/randomized fixtures: prev-Sat `23:00 - 08:00` ends 08:00 Sunday
  against a fixed Sunday start of 14:00 — a 6h gap under a 12h rest rule (the
  second case is 9h). Genuine violations.
* Cleaned fixture: Sunday 02:00–08:00 is active with demand (8.8 FTE at 02:00)
  and an English minimum of 1, but no previous-Saturday shift reaches past
  02:00 and no shift in the library starts early enough on Sunday. Maximum
  possible coverage really is 0. Failures decompose exactly as 24
  `LANGUAGE_WINDOW_MAX_CAPACITY_BELOW_MINIMUM` (per quarter) plus 12
  `ZERO_ACTIVE_INTERVAL_PROVABLY_IMPOSSIBLE` (per interval) over that window.

The rest-safe cleanup resolved the rest conflict by replacing the overnight
carry-in rows with shifts ending at or before 02:00 — and orphaned Sunday's
small hours in the process. The two constraints were traded, not both satisfied.

**Repair** (`fixtures/NMG_EN_REST_SAFE_REGRESSION_CLEAN_SUNDAY_CARRYIN_REPAIR.xlsx`,
authorised by the project owner). Previous-Saturday `23:00 - 08:00` added to
**Associates 016–025** on the `Previous week scheduled` sheet.

Those ten were chosen deliberately: they are fixed **OFF on Sunday**, so a
carry-in ending 08:00 Sunday cannot violate the 12h rest rule. Associates
001–015 are fixed to a Sunday `14:00 - 23:00` shift and would each have gained a
6h-gap violation; the 12 flexible rows (031–042) would have had every Sunday
start before 20:00 forbidden.

Verified equivalent in every other respect — demand, shrinkage, active
intervals, fixed schedules, shift library and all 42 associates identical;
only 10 `previous_saturday` values differ.

| | source | repaired |
|---|---|---|
| sha256 | `ac24a0fe…` | `ed90d630…` |
| preflight | FAIL, 36 failures | **PASS, 0 failures** |

Resulting Sunday carry-in coverage: 97.4% at 00:00, 98.3% at 01:00, 98.9% at
02:00 — a well-formed scenario.

**Known property, stated explicitly:** a 23:00–08:00 shift runs on while Sunday
demand collapses to 0.9 FTE, so 05:00–07:30 sits at 345–1111% coverage. This is
inherent to the shift shape, not an artefact of the repair, but it inflates
overage metrics — which is why issue 11 was fixed alongside it. Results from
this fixture are **not** comparable to the recorded 4H evidence: that run
consumed `CLEAN2 (1).xlsx` (`fd6b0cc9…`), a different file.

## Issue 11 — carry-in overage was charged as avoidable

**Root cause.** Previous-week carry-in is fixed workbook input, not a decision
variable — the solver cannot remove those associates from an interval. But where
carry-in alone exceeds the staffing the target needs, the whole excess was
charged as *avoidable* overage.

Measured on the repaired fixture: Sunday 07:00 has 0.9 FTE of demand against 10
carry-in associates, booking **9.0 FTE of avoidable overage** in that interval
alone, flagged `severe` and `extreme`, with `indivisible_staffing_only` **False**
so nothing marked it structural. Across Sunday 05:00–07:30 that is **48 FTE**
of "avoidable" overage no schedule could have avoided.

This matters directly for the release question: an overage regression caused by
the input contract was indistinguishable from one caused by the optimizer.

**Fix.** Four additive metrics, measurement only:
`carry_in_forced_overage_fte_sum`, `carry_in_forced_overage_interval_count`,
`before_/after_solver_controllable_avoidable_overage_fte_sum`.
Defined as `max(0, carry-in effective − unavoidable at target)`.

**Ranking is deliberately unchanged.** Feeding this into the selector would be a
behaviour change requiring its own evidence; a guard asserts the new keys never
appear in `_candidate_quality_tuple`.

## Issue 12 — negative fixtures, executed

All four fail for the **correct diagnosed reason**, which is the intended result:

| Fixture | Result | Codes |
|---|---|---|
| NEG_HEADCOUNT_MISMATCH | FAIL | `HEADCOUNT_MISMATCH` ×1 |
| NEG_LANGUAGE_SHORTAGE | FAIL | `LANGUAGE_MINIMUM_EXCEEDS_ELIGIBLE_ROSTER`, `LANGUAGE_WINDOW_MAX_CAPACITY_BELOW_MINIMUM` ×252, +2 more |
| NEG_FIXED_CYCLIC_REST | FAIL | `FIXED_CYCLIC_REST_CONFLICT` ×1 |
| NEG_OPENING_GUARD_CAPACITY | FAIL | `OPENING_MINIMUM_EXCEEDS_ROSTER`, `OPENING_WINDOW_MAX_CAPACITY_BELOW_MINIMUM` ×56, +1 |

Closes M05, **M06**, **M09**, **M14**.

## Issues 9 & 10 — fixture coverage gaps

Confirmed by parsing the shipped workbooks:

* `15_11H_3OFF_SAKS`: `use_11h_3off=False`, shift durations `[540]` only. Cannot
  exercise 11H/3OFF or the 11H break pattern. It *does* exercise separate OFF
  (`separate_off_days=True`).
* `17_BILINGUAL_NMG_EN_SP`: one rule — Spanish, eligible `{spanish}`. No English
  rule and no directional mapping, so "assists English only in the configured
  direction" and "no double counting" are unobservable. GDI REAL28 *does*
  exercise eligibility inversion (`Bilingual/French` accepts both).
* No fixture anywhere in the kit has a shift ≥ 630 min, so nothing would catch a
  regression in the issue-4 threshold change.

**Mitigation.** A missing fixture is not a reason to leave semantics unpinned.
`tests/test_rc9_2_1_rule_semantics.py` exercises the engine's own predicates
directly — 26 guards covering language eligibility and direction, the long-shift
OFF boundary, rest including carry-in, half-open carry-in coverage, and the
9H/11H break patterns. Real fixtures are still required to close the matrix rows.
