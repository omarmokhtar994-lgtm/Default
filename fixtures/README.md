# Synthetic review fixtures

Purpose-built test inputs for fix-plan item **W3**. Each is **derived** from a
shipped workbook by changing exactly one contract dimension, and written to a
new file — no shipped asset is modified.

**These are not baselines.** They carry no recorded results and must never be
compared against the RC5 authors' figures. They exist to make latent findings
reachable. The `SYNTHETIC_FIXTURE_` prefix is deliberate.

Built by `tools/build_review_fixtures.py`, source `AE_IT_Choice.xlsx`.

---

## `SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx`

**Changes:** `Minimum Per Interval` 0.80 → **0.60** (target stays 0.85).

**Exposes:** the ten `*_floor → *_80` cross-metric fallbacks (register #5,
root cause A). On 14 of 15 shipped workbooks the configured floor *is* 80%, so
`before_floor` and `before_80` are the same number and the substitution is
invisible. Here they are not:

```
floor_ratio=0.60
before_floor=86  before_80=72   -> differ by 14
after_floor =86  after_80 =72   -> differ by 14
```

A fallback that silently reads the 80% tier in place of the configured floor
now **understates floor attainment by 14 intervals**.

**Why 0.60 and not a rounder 0.75:** this contract's coverage is clustered with
nothing between 60% and 90%, so a floor anywhere in 0.70–0.90 selects exactly
the same 70 intervals as the 80% tier and the fixture would prove nothing. The
value was chosen from the measured distribution, not picked for looking
plausible.

## `SYNTHETIC_FIXTURE_NESTING_GROUP_MIXED_LEAVE.xlsx`

**Changes:** `Fixed Request Use` → `Yes`; two associates placed in nesting
group `GROUP_A` on the Fixed Request sheet; one of them given `Leave` on Sunday
in the Preference sheet.

**Exposes:** both nesting findings, through the supported path rather than by
in-memory injection:

```
contract failures                : NONE
any nesting-related failure      : NONE        <- S6-2, the check cannot fire
build_skeleton                   : INFEASIBLE  <- S6-1, and nothing says why
```

`leave[a,d]` is pinned from the contract and group equality then adds
`1 == 0`. The whole run dies with no cause reported in the log, the
diagnostics, or the contract report — and the one nesting check that exists
(`CONTRADICTORY_EXACT_SCHEDULES_IN_NESTING_GROUP`) is unreachable because the
parser makes its two guard conditions mutually exclusive.

## `SYNTHETIC_FIXTURE_MULTI_SHIFT_DURATION.xlsx`

**Changes:** `Use 11H/3OFF` → `Yes`; `Allowed Shift Durations Hours` → `9, 11`;
four 11-hour shifts added to the Shift Library.

**Exposes:** a path at **0/15** coverage in the shipped corpus — every shipped
workbook has exactly one shift duration.

```
distinct durations (minutes) : [540, 660]
break patterns generated     : {36q: 60, 44q: 60}   <- two durations, not one
durations actually scheduled : {540: 21 cells, 660: 6 cells}
OFF days per associate       : {2, 3}               <- 11H/3OFF rule firing
build_skeleton               : FEASIBLE
```

This is the only fixture that exercises `_generic_break_patterns` for more than
one duration, `rest_compatible` across differing durations, and the
`sum(off) == 2 + long_mode[a]` branch.

## `SYNTHETIC_FIXTURE_FIXED_EXACT_DAYS.xlsx`

**Changes:** `Fixed Request Use` → `Yes`; one associate given an exact week
(five days on `08:00 - 17:00`, two OFF).

**Exposes:** the fixed-request path, at **1/15** coverage. Also demonstrates
S6-2's root cause directly — the parser clears `nesting_group` the moment exact
day values are present, which is why the contract check guarded by
`nesting_group and any(fixed_schedule)` can never fire.

```
build_skeleton   : FEASIBLE
requested week   : ['08:00 - 17:00' x5, 'OFF', 'OFF']
scheduled week   : identical -- honoured exactly
```

**Note on how this one was built.** My first attempt assigned the fixed week to
`associates[0]`, who is on approved leave Sunday, Monday and Thursday. The
fixture was infeasible by construction — a fixed request cannot be honoured on
a leave day. The builder now picks an associate with no leave and no hard OFF.

That failure surfaced something worth recording separately: a fixed request
that collides with approved leave produces a bare `INFEASIBLE` with **no named
contract failure**. `validate_input_contract` catches `UNKNOWN_FIXED_SHIFT`
(a shift not in the library) but not a fixed request on a day the associate
cannot work. It is the same shape as S6-1 — a pre-solve contradiction that is
detectable from the contract alone and is instead left to die in the solver.

---

## Coverage these four restore

| dimension | shipped corpus | with fixtures |
|---|---|---|
| floor ratio ≠ 0.80 | 1 of 15 | covered, and separating |
| nesting groups | **0 of 15** | covered |
| multiple shift durations | **0 of 15** | covered |
| fixed requests enabled | 1 of 15 | covered |

## Once the findings are fixed

Both fixtures should flip: FX1's fallbacks should read the configured floor,
and FX2 should produce a **named contract failure** naming the group and the
conflicting leave — not an unexplained `INFEASIBLE`. They are the acceptance
tests for W5 and for the S6-1/S6-2 fix.
