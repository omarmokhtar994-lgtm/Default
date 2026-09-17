# Next moves, in order

Written while the post-apply sweep runs. Nothing here is gated yet: a gate run
competes for CPU with a wall-clock-budgeted solver, and perturbing the A/B it is
currently producing would cost more than the wait.

## 0. When the sweep lands (~15:45) — the only blocking item

**Score post-apply vs pre-apply** with `tools/score_sweep45.py`, pointing NEW at
`sweep45_applied`. Identities already confirm this is a clean A/B:
`parameters_sha256`, `seed_sha256` and `input_sha256` all match the pre-apply
arm; only `engine_sha256` differs (plus `contract_sha256`, which W1 legitimately
moves by adding two contract fields).

Three questions it answers at once:

1. **#48** — does the now-unconditional joint-refinement bound change produced
   schedules? This is the one applied change that can, and the only thing
   blocking a clean claim about the release.
2. **Parity at 48/48** on real workbooks. The 7 new checks have only ever run
   under unit tests. Anything below 48/48 is a B-9 defect.
3. **W1's floor-loss metric** reporting. AE_AR_Choice and AE_IT_B2B each gave up
   3 floor intervals pre-apply, so the new metric should now show them.

Decision rule agreed in advance, so the result cannot be rationalised after the
fact:

    no schedule delta   -> #48 closes, multi-seed repeats unnecessary
    delta on 1-2 cases  -> repeat THOSE cases at 2 more seeds (~4h), not all six
    delta everywhere    -> the bound is doing real work; full multi-seed A/B

## 1. Ready now — RC-B, the 90 permissive shadow defaults

`tools/apply_rcb_shadow_defaults.py`, written and verified on a scratch copy.

    collapsed 81 getattr-with-shadow sites across 34 fields
    50 of them had a shadow DIFFERENT from the declared default
    2 fields left alone -- their shadow is load-bearing
    compiles; line count unchanged (pure in-place expression collapse)

**Why it is safe.** `getattr(parsed, "x", shadow)` where `x` is a declared
dataclass field is dead code -- the attribute always exists, so the shadow never
fires. Collapsing to `parsed.x` is behaviour-preserving by construction, and the
applier re-parses and asserts zero sites remain.

**Why it is worth doing.** The shadows are not neutral. They are systematically
more permissive than the real policy:

    whole_week_max_adjacent_raw_change     declared 3      shadow 999999
    whole_week_max_imbalance_violations    declared 0      shadow 999999
    whole_week_max_overage_cap_violations  declared 0      shadow 999999
    whole_week_overage_cap_ratio           declared 1.35   shadow 2.0
    employee_max_weekend_load_delta        declared 3      shadow 999999
    employee_max_overnight_load_delta      declared 3      shadow 999999
    employee_max_late_shift_load_delta     declared 3      shadow 999999
    employee_min_preference_satisfaction   declared 0.5    shadow 0.0
    skill_allocation_audit_enabled         declared True   shadow False
    quality_gate_mode                      declared 'fail' shadow 'off'
    employee_quality_gate_mode             declared 'warn' shadows 'off' AND 'warn'
    whole_week_gate_mode                   declared 'warn' shadows 'off' AND 'warn'

The file reads as though the policy were "unlimited / off" when the policy is a
real limit. Two fields disagree with *themselves* between call sites, which is
what marks this as a habit rather than a decision. The risk it removes is a
future refactor making one of these reachable.

The two exclusions are real and were found by checking rather than assuming:
`qslots_per_interval` and `_shift_day_demand_fit_cache` are **not** declared on
`ParsedInput`, so their shadow IS load-bearing and must stay.

## 2. Group two — the rest of the inert findings, one gated pass

Same shape as the pass that just landed: apply in order, run the full gate after
every step, stop at the first failure.

    RC-A   18 cross-metric fallbacks -- a missing key substitutes a DIFFERENT
           quantity. Needs the same AST treatment as RC-B: enumerate, classify
           reachable vs dead, collapse the dead, fail closed on the rest.
    CM-1   after_avoidable_overage_top10_concentration is the one canonical
           field of 41 that is not its own alias. One-line fix.
    S9-1   7 after-break terms read without a prefix inside the before-break
           ranking.
    S6-2   the only nesting-group contract check is unreachable, guarded by a
           condition the parser cannot produce.
    S13-2  213 dead lines across 6 functions, including a superseded refinement
           phase and a dead budget planner that reads as live policy.

`S6-3` and `C-2` need no code: the first is a corpus-coverage gap (0 of 15
workbooks define a nesting group) and the second is unreachable through Excel
because all ten flags carry dropdowns.

## 3. Three behavioural findings — one at a time, each with its own A/B

These cannot be grouped. If two land together and the sweep moves, the move
cannot be attributed to either.

    B-10    break-slice constant is evidence for a CAP, used as a FLOOR
    S15-3   phases run below their own declared PHASE_MINIMUM_VIABLE_SECONDS
    S9-2    Pareto dominance and the lexicographic order disagree

Sequence each as: apply -> gate -> A/B on the four measurable cases (never the
two CAPACITY_SHORT ones) -> keep or revert on the measured result.

## 4. Needs a decision from the authors, not a patch

    B-9b  three subsystems the validator does not model at all -- language
          reserve (0 refs), skill allocation (0 refs / 116 lines), employee
          quality (0 refs / 82 lines). Adding metrics cannot close this; it is
          a scoping question.
    W1    the default floor-loss cap. Currently mirrors the target cap, so it
          changes no existing outcome. Tightening it is scheduling policy.

## 5. Two measurement debts, both optional

    B-3 vs baseline   the recorded comparison is confounded by both flags and
                      hardware (the baseline ran on Colab). Re-running the
                      treatment arm with the authors' bare flag set removes the
                      flag confound but not the hardware one -- it upgrades the
                      comparison from meaningless to indicative, no further.
    adaptive slice    the hypothesis that the Stage-1 slice should track problem
                      difficulty rather than being a fixed 45s. Grounded in one
                      case so far. Wants reproduction on a clean run before any
                      code is written.
