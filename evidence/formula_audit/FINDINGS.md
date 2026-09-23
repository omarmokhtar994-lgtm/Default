# Formula audit — findings

Inventory: 1,102 formula statements across 5 engine files
(`evidence/formula_audit/formula_statements.json`).

---

## F-1 · Stage-1/Stage-2 score coverage in a different arithmetic from the metric  — CONFIRMED

**Where.** Eight coefficient sites build an integer effective factor at scale 100:
`int(round((1.0 - shrinkage) * 100))` — `aggregate_pattern_mix_guidance:5328`,
`build_skeleton:6335/6616`, `critical_exception_cells:7349/7389`,
`solve_breaks:7926`, `global_zero_exception_break_reserve_requirements:16693/16705`.
Their thresholds use `ceil_units(req * ratio) * qpi` — ceil per quarter, then ×qpi.

The metric (engine `calculate_metrics` and the independent validator) averages
the quarter counts and compares a float: `sum_q(count)*(1-s)/qpi/req + 1e-9 >= ratio`.

The engine already knew. `scaled_effective_factor`'s docstring: rounding
shrinkage to whole percentage points "could become artificially infeasible"
against the canonical evaluator, so the **joint** model moved to 6-decimal
scaling. Stage-1 and Stage-2 were never moved, and `solve_breaks` is internally
inconsistent — ×1e6 in its next-Sunday block (line 8107), ×100 in its main loop.

**Measured.** Every distinct (demand, shrinkage, ratio) combination in 13 real
workbooks × every quarter-count vector: **2,810,982 cases.**

| form | model "covered", truth short | model "short", truth covered |
|---|---|---|
| ×100 (Stage-1/2) | **14** | **56** |
| ×1e6 (`scaled_*` helpers) | **0** | **0** |

All disagreements are on Cricut Chat and Cricut Voice, whose shrinkage is
0.0923… (12/130, non-terminating). AE, GDI and NMG use round values and agree.

Worked case — Chat, day 1, interval 35: demand 10 FTE, shrinkage 0.0923,
11 people. Truth: 11 × 0.9077 = 9.985 → **99.85%, a miss**. Model:
11 × round(90.77)=91 = 1001 ≥ 1000 → **"hit"**. The optimiser banks an interval
the reported metric scores as missed.

**Why a naive fix is wrong.** The deficit terms are in the same units.
`floor_def` (30,000) × `floor_slack`: at ×100 one FTE short costs 3,000,000; at
×1e6 it would cost 3×10¹⁰ and swamp `target_miss` (12,000,000), silently
reordering the whole objective.

**Fix.** Keep every magnitude as tuned. Add a parallel ×1e6 linear expression
over the same assignment variables and use it **only** for the hit
reifications (`target_hit`, `floor_hit`, `full_hit`, `severe_hit`, tier hits),
with thresholds from `scaled_coverage_threshold`. The model then counts hits
exactly as the metric does, and nothing the objective weighs changes scale.

---

## Scan S-1 · Shrinkage direction — CLEAN

Industry standard (Call Centre Helper, WFM Labs, Peopleware): gross up by
**dividing** by `(1 - shrinkage)`. Multiplying by `(1 + shrinkage)` under-staffs
every interval — 100 FTE at 30% needs 143, not 130.

All **24** shrinkage sites use `1 - shrinkage`. **0** use the multiply form.
Every `1 - s` denominator is strictly positive because `validate_input_contract`
rejects shrinkage outside `[0, 1)` before any solve.

## Scan S-2 · Division by zero — CLEAN

80 division/modulo sites whose denominator is not a literal.

* **32** cleared by an upstream invariant or not a division at all: interval
  length is constrained to `INTERVAL_MINUTE_CHOICES = (15, 30, 60)` (instructed)
  or clamped to {15, 30, 60} (inferred), so `qpi >= 1`; `Path / name` joins;
  positive module constants.
* **48** checked individually with context. Every one is guarded by
  `max(1, …)` / `max(1e-9, …)` on the preceding line, an enclosing `if`, or an
  early return on empty input.

One hypothesis was wrong and is recorded because it was checked, not assumed:
the engine's top-10 overage concentration divides by `sum(values)` guarded only
by "list non-empty", which looked like it would crash on an all-zero list. It
cannot: values are appended only when `> 0` (line 8938), deliberately, for
parity with the validator.

## Scan S-3 · Rounding direction on staffing — CLEAN

A headcount requirement must round **up**; `round()` or `int()` under-staffs,
and Python 3's `round()` is banker's rounding (`round(2.5) == 2`).

6 candidates. Every headcount requirement uses `ceil`. The one `floor` —
`maximum_concurrent_breaks` — is a **cap** on simultaneous breaks and must round
down (10 staff × 15% = 1.5 → at most 1). The rest are seconds, booleans, a
4-dp display ratio, or `int()` over values that are already integers.

Cosmetic, not fixed: `coverage_split_capacity_report` flags a "tight" margin at
`round(need * 0.15)`, which is banker's rounding. It is a warning heuristic, not
a requirement, so it cannot change a schedule.

---

## Section FA-6 · Time, index, rest and budget arithmetic — CLEAN (1 latent gap)

Verified exhaustively against independent `datetime` reference
implementations, not spot examples (`tests_staged/test_rc9_2_11_time_arithmetic.py`,
15 tests, hundreds of thousands of sub-cases):

| helper | checked over | result |
|---|---|---|
| `hhmm` ↔ `minute_of_day` | all 1,440 minutes, text and Excel day-fractions | exact round trip |
| `minute_of_day` | invalid text (`24:00`, `12:60`, blank, garbage) | rejected, not wrapped |
| `shift_parts` | every start × end pair on the 15-min grid (9,216) | forward duration, `00:00–00:00` = 24h |
| `shift_covers_week_qslot` | 7 days × 96 starts × 5 durations | identical quarter sets to `datetime` |
| Saturday overnight | spill past quarter 672 into next-Sunday pseudo-quarters | reaches them |
| `previous_saturday_covers_qslot` | 96 starts × 3 durations | identical to the week arithmetic |
| `next_sunday_own_qslot` | all 96 pseudo-quarters | maps back to Sunday |
| `rest_compatible` | 96 × 4 × 96 prev/next pairs × 3 rest rules | identical to `datetime` |
| `circular_minute_distance` | all 9,216 grid pairs | shorter way round the clock |

Mutation check: changing the rest rule's `1440` to `1455` (one quarter) fails
**953** sub-cases. Engine restored byte-identical.

**Budget ladder** (`build_global_budget_plan`), 33,216 plans over every budget
30–22,000s × every combination of the five phase-enable flags × three Stage-1
minimums:

* every allocation non-negative;
* every disabled phase receives exactly 0;
* for every budget **≥ 60s**, the ladder sums to exactly the total.

Below 60s the plan is clamped to 60s — an explicit `max(60, …)` in two places,
so a deliberate minimum rather than an arithmetic error. The CLI accepts a
smaller `--time-limit` without saying so. All shipped modes start at 900s, so
no real run reaches it; documented, not changed.

## F-2 · Shifts off the 15-minute grid are silently mis-modelled — LATENT

`_parse_shifts` checks neither that a shift starts on the 15-minute grid nor
that its duration is a multiple of 15, and it accepts any duration within
**±5 minutes** of an allowed one. Every coverage function then floors:
`start_min // 15`, `duration_min // 15`. So:

* `09:00–17:57` (537 min) passes as "9 hours" and becomes 35 quarters = 8h45;
* a `09:10` start is modelled from 09:00, crediting ten minutes of coverage the
  associate cannot provide.

**Measured: 0 of 197 shifts across all 13 real workbooks are off-grid.** No
schedule has ever been affected. A future workbook would be, silently.

**Fix.** The engine's own convention for supplied-and-invalid input
(`_detect_interval_minutes`, B-11, C-1): a `HARD_` parser warning that blocks
the run before CP-SAT, instead of a silent rewrite. By construction this cannot
change any current schedule.

---

## Section FA-3 · Coverage metrics and engine/validator parity — CLEAN

**Parity census, 212 validated runs in the corpus.**

| parity status | runs |
|---|---|
| PASS (41–48 fields) | 136 |
| predates the parity check | 72 |
| FAIL | 4 |

All four FAILs predate the fix for what they show. The two
`week_boundary_imbalance_violation_count` mismatches (engine 1, validator 0) ran
at 22:18 and 22:37 on 09-16; the B-8 fix — "the validator was checking a weaker
next-Sunday rule under the same name" — landed at 22:48. They are the evidence
that motivated it. The other two are before-break runs on an older build where
the engine emitted no canonical metrics, addressed by stage-aware parity; the
before-break stage is re-proven on the current engine in FA-7.

**Every run since 09-20 — 14 runs across three engine builds, including the
merged engine — passes 48-field parity.** All 48 canonical fields are compared;
none exist unchecked.

**Parity is only evidence if the two sides are independent.** The validator
shares code with the engine through `eng.*`, so each shared dependency was
verified on its own:

| dependency | shared? | verified by |
|---|---|---|
| input parsing (`eng.parse_input`) | yes | engine-free openpyxl read of every demand and shrinkage cell in all 13 workbooks: **3,024 cells, 0 mismatches** |
| time helpers (`hhmm`, `shift_parts`, `rest_compatible`, …) | yes | exhaustive `datetime` reference, FA-6 |
| coverage counting | **no** | engine counts from solver objects; validator counts from the exported workbook and never calls `calculate_metrics` |

So agreement on 48 fields across 136 runs is two independent computations
agreeing, not one formula checked against itself.

**Definition check.** Coverage = average headcount over the interval's
quarters × (1 − shrinkage) ÷ requirement. That is the standard net-staff over
required-staff definition; averaging quarters inside an interval is what makes a
15-minute break count as half of a 30-minute interval.

## Gate hardening · the validator's 25 references into the engine were unchecked

Found while auditing independence. `tools/check_cross_module_calls.py` resolved
only `from X import f`. The validator binds the engine dynamically —
`eng = load_engine(path)` — so its **25** `eng.*` references were never
checked. A renamed engine function would have passed the gate and crashed the
validator at run time.

Extended with an explicit dynamic-binding map. It now checks that every
`eng.X` exists and every `eng.f(...)` call matches the real signature. Verified
against both failure modes: calling a function the engine does not have, and
calling one with a missing argument. Each is reported with its exact line; the
validator was restored byte-identical after each.

A stale comment naming `eng.language_reserve_target` (the function is
`language_operational_reserve_target`) was corrected. It was a comment, not a
call, so it never affected a run.

---

## Section FA-2 · Demand units, shrinkage and headcount — CLEAN except F-1

92 formula statements. Three kinds.

**Minimum headcount for a ratio.** Ground truth is the smallest whole headcount
the **metric** scores as meeting the ratio (`h * (1-s) / req + 1e-9 >= ratio`).
Every raw-requirement function must return exactly that.

28,905 cases: every real (demand, shrinkage) pair in 13 workbooks (355) plus a
dense fractional grid (demand 0.1–40.0 FTE × 14 shrinkage values including the
non-terminating 12/130) × five ratios.

| function | under-staffs | over-staffs |
|---|---|---|
| `whole_week_raw_requirement` | 0 | 0 |
| `next_sunday_raw_requirement` | 0 | 0 |
| `coverage_split_required_headcount` | 0 | 0 |

The float gross-up — divide by `(1-s)`, then `ceil` — is exact. F-1 lives only
in the ×100 integer coefficients, not here.

**Caps.** `whole_week_raw_cap` and `next_sunday_raw_cap` use `ceil`, which
defines the cap as the first whole person at or above the cap ratio — lenient
by up to one person (demand 10, shrinkage 0.17: exact cap 16.27, allowed 17 =
141%). The cap is then raised to at least every hard minimum
(`max(target_raw, percentage_cap, opening_cap, language_cap)`), so it can never
make the model infeasible.

Checked for the defect that would matter — a constraint that allows what the
metric flags. It cannot happen: **all ten constraint sites** (Stage-1, Stage-2,
joint) **and all four metric sites** (engine `calculate_metrics`, validator)
call the same two functions. One definition, applied everywhere. Documented,
not changed.

**Integer effective coefficients.** F-1.

---

## F-3 · The break headcount recommendation divides a weekly deficit by one day — CONFIRMED

**Where.** `break_capacity_headcount_requirement`:

```python
break_demand      = worked_days * break_q_per_shift          # per WEEK
deficit           = max(0, break_demand - lossless_capacity)  # per WEEK
net_per_associate = max(1, typical_shift_q - break_q_per_shift)  # ONE SHIFT = one day
additional_hc     = ceil(deficit / net_per_associate)
```

`worked_days` counts every non-OFF cell across the roster and
`lossless_capacity` is summed over all seven days, so the deficit is per week.
`net_per_associate` is what one associate contributes in a single shift. Dividing
one by the other treats each added associate as working **one day a week**. It
must be divided by `workdays × net_per_associate`.

The docstring calls the figure a **lower bound**. As written it is roughly the
days-per-week multiple of one. The sibling estimate in `capacity_diagnostics`
already multiplies by `default_workdays` — the two headcount estimates in the
same engine disagree on units.

**Measured on real audits** (9-hour shift, 4 break quarters → 32 net quarters;
5 workdays → 160 a week):

| run | deficit (person-q/week) | engine says add | correct lower bound |
|---|---|---|---|
| AE_AR_Choice | 200 | **7** | **2** |
| AE_AR_Choice | 192 | 6 | 2 |
| NMG_EN_AND_SP | 150 | 5 | 1 |
| GDI_REAL28 (RC8.6.1) | 144 | 5 | 1 |
| C_CHAT_3600_w4 | 144 | 5 | 1 |
| C_CHAT_1800_w4 | 28 | 1 | 1 |

Hidden when the deficit is under one shift's worth (the `ceil` gives 1 either
way), up to 3.5× over above it. This is a number a business acts on by hiring.

**Blast radius.** Every consumer is reporting — leaderboard columns, two workbook
sheets, the audit. None feeds a constraint, gate or selection, so the fix
corrects the reported recommendation and **cannot change any schedule**.

**Fix.** Divide by `workdays × net_per_associate`, with `workdays` derived exactly
as `capacity_diagnostics` derives it (4 for shifts of 10.5h or longer, else 5),
through one shared helper so the two estimates cannot drift apart again.

---

## Section FA-4 · Break model — CLEAN except F-3

**Pattern generator — validity and completeness.** Every emitted pattern was
checked by an independent rule checker (segment count, shape and order; edge
margins; minimum gap; per-segment windows). Completeness was checked at
unlimited width against a brute force over every combination of start
positions, which shares none of the generator's recursion or pruning.

| scope | contracts | patterns / checks | invalid | unlimited ≠ brute force |
|---|---|---|---|---|
| real workbooks (all 13 share one contract) | 1 | 1,573 across widths 24/44/60/115/∞ | **0** | **0** |
| synthetic sweep: 7 segment sets × 17 durations (4–12h) × 4 margins × 5 gaps × 3 window configs | **7,140** | widths 24 and 115 | **0** | **0** |

The synthetic sweep exists because the real corpus exercises a single break
contract, so it alone would prove nothing about the next workbook.

**Concurrency cap** (`maximum_concurrent_breaks`), 21,070 cases over staffing
0–300 × 10 ratios × 7 absolute caps: never breaks a sole associate, always
leaves one working, never exceeds either cap. **0 violations.** Its `floor` is
correct — it is a maximum.

**Break capacity headcount.** The gross-up has the right shape — divide by the
productive fraction, `need × shift / (shift − break)`, the same direction as
shrinkage. The headcount *recommendation* built on it has a unit error: F-3.

---

## F-4 · Overage caps above 150% are silently divided by 100 — LATENT

```python
if value > 1.5:           # meant: "135" is a percentage
    value = value / 100.0
overage_severe_cap_ratio  = max(overage_soft_cap_ratio,  overage_severe_cap_ratio)
overage_extreme_cap_ratio = max(overage_severe_cap_ratio, overage_extreme_cap_ratio)
```

The `> 1.5 → ÷100` rule is correct for **Target** and **Floor**, which can never
exceed 100%, so "90" is unambiguously 0.90. It was copied to the **caps**, which
legitimately exceed 100%. A workbook setting *Overage Extreme Cap = 1.6* (160%)
gets 0.016, which the chained `max()` then lifts to the severe cap. The workbook
asks for extreme overage from 160%; it silently gets 120%. That changes both the
reported extreme-overage counts and the penalty the model optimises.

Second defect in the same lines: the chained `max()` forces the caps into order
**before** `validate_input_contract` checks their order (line 3799), so
`INVALID_OVERAGE_CAP_ORDER` is unreachable — a validation that cannot fail. A
mis-ordered workbook is rewritten silently instead of rejected.

**Measured:** all 13 real workbooks leave the caps at the defaults 1.10 / 1.20 /
1.40 and override nothing. No current schedule is affected.

**Fix.** For caps only, treat a bare number as a percentage only when it is
**≥ 10** (no plausible cap is ten times demand), so 160 → 1.60 and 1.6 stays
1.60. Remove the chained `max()` so the existing order check can fire. Both
are no-ops for every current workbook by construction.

**Overage formula itself** (`fractional_safe_overage_metrics`), 68,451 cases
over demand, five shrinkage values, three targets and every headcount up to 2.2×
demand: avoidable overage never negative, never above target overage, monotone
in staffing, exactly 0 at the minimum whole headcount, severity flags always
nested. **0 violations.**

---

## Section FA-5 · Objective weights, loss caps and gates

**Overflow.** CP-SAT validates every model before solving and returns
`MODEL_INVALID` on integer overflow. Across **282 audits and ~9,400 recorded
solves** — every Stage-1 profile and Stage-2 mode — it has done so **0** times.
Analytically the largest objective term is about 10¹³ against a 64-bit limit of
9.2×10¹⁸.

**Priority consistency.** Every mode's weights order the way its name says:
`target_priority` target 12M > floor 2.5M; `floor_protected` floor 12M > target
6M; `target_100` full coverage 10M > target 8M; `release_quality_guard` and
`quality_convergence` put gap penalties (10⁸–10⁹) above both.

**`lexicographic_target` is lexicographic in practice, not algebraically.**
Its 10⁹ target weight could in principle be outweighed by the *aggregate*
floor-deficit terms. It cannot be in practice: one break move changes one
interval's deficit by at most `break_q × 100` units, so the best non-target gain
per move is 14M–38M, and a single target interval outweighs **26–71** such moves.
Documented; a tuned weight is not changed on a theoretical bound.

**Loss caps.** `max(3, ceil(active × ratio))` — a floor of 3 so a small
workbook still tolerates some loss; 168 active intervals at 3% gives 6,
matching #49.

## F-5 · Target-loss gate typos are silent; floor-loss typos report the wrong setting — CONFIRMED (introduced by this project)

Every gate mode rejects an unknown value with a `HARD_` warning naming itself —
six of them correctly. Two do not:

| gate | invalid value today |
|---|---|
| `target_loss_gate_mode` | silently becomes `warn`, **no message** |
| `floor_loss_gate_mode` | `HARD_INVALID_`**`TARGET`**`_LOSS_FROM_BREAKS_GATE_MODE` — the wrong name |

**Cause — my own earlier change.** The target block was three lines: the `if`,
the default, and its warning. `tools/apply_w1_floor_loss_gate.py`, written in an
earlier session of this project, anchored on only the first two and inserted the
floor block between them and the third. Target's warning was left stranded under
the floor's `if`. A user mistyping the floor mode is told their target mode is
wrong; a user mistyping the target mode is told nothing.

**Measured:** none of the 13 workbooks sets either mode. The fix is a no-op for
every one of them.

**Fix.** Give the target block its own `HARD_INVALID_TARGET_LOSS_FROM_BREAKS_GATE_MODE`
and the floor block `HARD_INVALID_FLOOR_LOSS_FROM_BREAKS_GATE_MODE`, matching the
six siblings. Plus a test that every gate mode rejects a typo *under its own
name*, so an insertion can never split a block silently again.

---

## Unclassified statements — triaged by hand

195 statements matched no section's keywords. 94 sorted mechanically (text
building 69, list concatenation 11, sort keys 7, display rounding 7). The other
**101 were read one by one.** They are header maps, set and list operations,
deduplication, or arithmetic already proven by the exhaustive tests (clock
parsing, `% 1440` wraps, the budget ladder, `maximum_gap_run` via the 48-field
parity on `max_consecutive_floor_gaps`).

One is a domain formula with F-3's flaw, and is fixed with it:
`coverage_split_capacity_report` uses `workdays = max(1, 7 - 2)` — a hard-coded
five-day week. `capacity_diagnostics` and `break_resilience_diagnostics` both use
`default_workdays` (4 for shifts of 10.5h or longer, else 5). On a 4×10 roster
the three capacity reports disagree about the week. All three move to the one
shared helper.

---

## Note · The packaged AE_AR_B2B baseline workbook is refused by the contract — engine correct, fixture stale

Found while writing behavioural tests. `packages/rc9_2_2_production/inputs/AE_AR_B2B.xlsx`
(sha 321f1eff…) names **five** associates on its *Previous week scheduled* sheet
who are not on the Schedule roster, e.g. *Jessica Gendy Youssef Abdelshahid*,
*Hager Ahmed Abo Elnaga Ahmed Qenawy*. The engine rejects it with
`HARD_PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE`.

That is the correct, deliberate behaviour (B-11 family): a misspelled name on
the previous-week sheet would otherwise silently drop last Saturday's carry-in
coverage from Sunday. The message states the remedy — correct the spelling, or
list the name under *Known Departed Associates* in Instructions.

The other six packaged inputs are runnable. Every run in this project used the
AE package copy (sha 5c15a9bc…), which is clean. Nothing documents running this
folder directly; it is the pinned baseline fixture for the tooling tests.

**Not changed.** It is a pinned historical baseline, which must not be
regenerated or edited, and whether those five people have left or are
misspelled is a data decision for the workbook owner, not the engine.
