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

---

## Still to build

| fixture | would expose |
|---|---|
| multiple shift durations (11H/3OFF) | that path is at 0/15 coverage, and `rest_compatible` across differing durations is untested |
| fixed requests with exact day values | the fixed/nesting subsystem at 1/15 coverage |

## Once the findings are fixed

Both fixtures should flip: FX1's fallbacks should read the configured floor,
and FX2 should produce a **named contract failure** naming the group and the
conflicting leave — not an unexplained `INFEASIBLE`. They are the acceptance
tests for W5 and for the S6-1/S6-2 fix.
