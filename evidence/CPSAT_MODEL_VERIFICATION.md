# Does the CP-SAT model encode the business rules?

I had listed this as an explicit limit of the review — "I read the constraint
construction and checked invariants; I did not establish equivalence between
the written rule set and the model". This closes that gap for the rules that
can be probed.

## Method — binding-constraint probing

Reading a constraint proves a line exists. It does not prove the constraint
**binds**, nor that the flag which claims to control it does. So for each rule:

| step | expected |
|---|---|
| positive control — the base contract | `FEASIBLE` |
| **binding probe** — make the rule impossible to satisfy | `INFEASIBLE` |
| relaxation control — same contract, rule switched off via `HardConfig` | `FEASIBLE` |

All three together prove the constraint is **present**, that it **binds**, and
that the switch controls **exactly it**. A binding probe returning `FEASIBLE`
would mean the model accepts a rule violation — that is the defect this looks
for.

Base: `AE_IT_Choice` (8 associates, 8 shifts, 112 active intervals) for Stage 1;
`AE_FR_Choice` at pattern width 60 for Stage 2, chosen because it is the
smallest contract whose fully-compliant break solve is feasible.

Tools: `tools/cpsat_constraint_probe.py`, `tools/cpsat_break_probe.py`.

## Stage 1 result — 8 of 8 rules enforced

```
POSITIVE CONTROL (base)            FEASIBLE

rule                               rule ON        rule OFF       verdict
leave blocks work                  INFEASIBLE     FEASIBLE       ENFORCED, switch controls it
hard OFF blocks work               INFEASIBLE     FEASIBLE       ENFORCED, switch controls it
strict OFF count == 2              INFEASIBLE     FEASIBLE       ENFORCED, switch controls it
max shift variety                  INFEASIBLE     FEASIBLE       ENFORCED, switch controls it
rest gap between days              INFEASIBLE     FEASIBLE       ENFORCED, switch controls it
language minimum per interval      INFEASIBLE     FEASIBLE       ENFORCED, switch controls it
opening minimum FTE                INFEASIBLE     FEASIBLE       ENFORCED, switch controls it
fixed shift must be legal          MODEL_INVALID  FEASIBLE       ENFORCED, switch controls it
```

Every rule binds, and every `HardConfig` switch releases exactly the rule it
names. This is the evidence that was missing.

## Stage 2 result

| break rule | status | verdict |
|---|---|---|
| language minimum survives breaks | `INFEASIBLE` | **enforced** — breaks cannot drop a language below its minimum |
| break concurrency cap | — | **not testable this way**, see below |

## Two of my three apparent findings were my own probe errors

Worth recording, because both corrections are more interesting than the
"findings" would have been.

### 1. "Malformed fixed shift is not enforced" — wrong, my probe bypassed the gate

My first probe used `"99:99 - 99:99"` as a fixed request and the model returned
`FEASIBLE`. I took that for a defect in the C-3 family: unparseable text
silently dropped.

It is not. `preference_kind("99:99 - 99:99")` is `"other"`, so the legality
branch at 5525 — guarded by `kind == "shift"` — is never reached. But
`validate_input_contract` **does** catch it, as a hard `UNKNOWN_FIXED_SHIFT`
failure, and the contract gate runs **before** any model is built:

```
validate_input_contract   17443
FAIL_PRE_SOLVER_CONTRACT  18018   <- the guard
first build_skeleton      18059
```

My probe called `build_skeleton` directly and so fed the model a contract that
could never have reached it in a real run. The layering is correct: the
contract layer rejects what the model does not need to defend against.

Re-probed with a **well-formed** shift absent from the contract
(`"03:00 - 12:00"`): `MODEL_INVALID`, as it should be.

### 2. "Break concurrency cap not enforced" — wrong, the cap cannot reach zero

I set `break_max_concurrent_ratio = 0.0` and `break_max_concurrent_absolute =
0`, expecting an impossible model. Both probes returned `UNKNOWN`, which is a
time-limit artifact and not a result — I should not have printed it as a
verdict at all.

The reason it could never work:

```python
ratio_cap    = max(1, int(math.floor(staffed * parsed.break_max_concurrent_ratio + 1e-9)))
absolute_cap = max(1, int(parsed.break_max_concurrent_absolute))
```

Both caps floor at 1 deliberately — the docstring says "preserving at least one
working associate". A zero cap is unreachable through contract settings, so the
model was merely harder, not infeasible. The probe tested a premise that cannot
exist.

**A concurrency probe would need to construct a contract where the legal cap is
genuinely binding rather than trying to force it to zero.** Left as a gap
rather than claimed as a pass.

## What this changes

The correctness assessment previously said: *"I did not prove the CP-SAT model
encodes the business rules."* That limit is now narrower:

* **Proven, by binding probe:** leave, hard OFF, strict OFF count, max shift
  variety, rest gap, language minimum per interval, opening minimum, fixed
  shift legality, and language minimum surviving break placement — **9 rules,
  all enforced, all released by their own switch.**
* **Still unproven:** break concurrency (needs a better probe), week-boundary
  carry-out, blank-interval staffing, nesting group equality (no workbook
  exercises it), and the coverage floor/target constraints themselves, which
  are soft objective terms rather than hard constraints and so cannot be probed
  this way.

**Zero new engine defects were found by this exercise.** Everything that looked
like one was a flaw in how I constructed the probe.

---

# Round 2 — the rules the first pass could not reach

## Result: 12 rules proven enforced, 1 directionally confirmed, 2 not provable this way

### Newly proven enforced

| rule | rule ON | rule OFF | released by |
|---|---|---|---|
| nesting group shares OFF/leave | `INFEASIBLE` | `FEASIBLE` | `hard.fixed` |
| hard floor solver constraint | `INFEASIBLE` | `FEASIBLE` | `hard.hard_floor` |
| minimum tier lock binds | `INFEASIBLE` | `FEASIBLE` | `minimum_tier_hits=None` |

The nesting result independently confirms **S6-1** from the section pass: a
group whose members carry different approved leave is infeasible, and it is the
`hard.fixed` switch that gates it.

### Week-boundary carry-out — enforced, release not proven

My first attempt ran on `AE_IT_Choice`, which has **0 next-Sunday protected
quarters** and no shift spilling past midnight — so no carry-out constraint is
built at all and the probe was vacuous. Re-run on `AE_AR_B2B`, which has 32:

```
base AE_AR_B2B                                        UNKNOWN   (12s, 39 associates)
next-Sunday floor made impossible, week_boundary ON   INFEASIBLE
same, hard.week_boundary=False                        UNKNOWN
```

`ON → INFEASIBLE` proves the constraint binds. `OFF → UNKNOWN` means the
infeasibility proof disappeared when the switch was thrown, which is the right
direction, but `UNKNOWN` is not `FEASIBLE` — at this time limit the release is
indicated, not proven.

### Tier locks clamp, as intended

Asking for 100× more 100%-tier hits than there are intervals still returns
`INFEASIBLE`. My probe reported that as "NOT clamped", which was a wrong label:
line 6068 clamps to `min(requested, len(tier_vars))`, and that clamped value —
every active interval at 100% — is itself unachievable for this contract. **The
clamp works; the clamped target is simply impossible.**

## Two rules this method cannot reach, stated as gaps

**Blank-interval staffing.** On `GDI_28HC_NO247` (34 blanks a shift can
actually reach) the probe gives `INFEASIBLE` in `hard` mode — but *also*
`INFEASIBLE` in `allow` mode, so the result cannot be attributed to the blank
rule. Forcing an associate onto a shift that covers a zero-demand interval
trips the demand-fit guard independently.

Worth recording separately: **202 of 818 blank intervals across the corpus are
coverable by some shift**; the other 616 are hours no shift reaches, where the
constraint is trivially satisfied. So the rule only ever binds on three
workbooks.

**Break concurrency.** A cap of 1 in `fail` mode was satisfiable — the solver
simply spreads breaks out. Not a binding probe. A real one needs a contract
where the legal cap is forced to bind, e.g. by narrowing the break window so
placements must collide.

## The methodological limit — five invalid probes, one cause

Five of my probe constructions were wrong, and they share a cause worth naming:

| probe | why it was invalid |
|---|---|
| malformed fixed shift | bypassed `validate_input_contract`, which catches it |
| concurrency = 0 | the cap floors at 1 by design |
| week boundary on `AE_IT_Choice` | that contract has no carry-out horizon |
| blank interval via `active` flags | mutating `active` post-parse leaves derived structures stale |
| blank interval via a forced shift | confounded by the demand-fit guard |

**Mutating a parsed contract after parsing is unreliable.** `parse_input`
derives interdependent structures — demand-fit eligibility, opening intervals,
cyclic windows, coverage variable maps — and a mutation that changes `active`
flags or forces a shift leaves those inconsistent, so the model becomes
infeasible for a reason other than the rule under test.

The probes that *were* valid all mutated things the model reads directly:
preference cells, scalar contract settings, and `HardConfig` switches. That is
the boundary of what this technique can prove without purpose-built fixtures —
which is the same conclusion as fix-plan item **W3**, reached from a different
direction.

## Standing tally

**Proven enforced, with the switch releasing exactly that rule — 12 rules:**
leave, hard OFF, strict OFF count, max shift variety, rest gap, language
minimum per interval, opening minimum FTE, fixed shift legality, language
minimum surviving breaks, nesting group equality, hard floor, minimum tier lock.

**Enforced, release indicated but not proven:** week-boundary carry-out.

**Not provable without purpose-built fixtures:** blank-interval staffing, break
concurrency.

**Not probeable by construction:** the coverage floor/target terms, which are
soft objective terms rather than hard constraints.

**New engine defects found across both rounds: zero.**
