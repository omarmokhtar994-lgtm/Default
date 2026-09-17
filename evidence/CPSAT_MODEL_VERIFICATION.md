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
