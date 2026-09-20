# Cricut Voice: RC9.1's floor is provably unreachable, and fixed requests are why

## What was proven

Probe on the **exact** workbook RC9.1 used — sha `55b4ee899cfd38ad`, hash
verified against `RC9_1_BASELINE.json`, profile `floor_gate_hunter_before`
(RC9.1's own winning profile).

`build_skeleton` accepts `minimum_tier_hits`, which becomes a hard constraint,
so CP-SAT can be asked directly whether RC9.1's result is reachable:

| case | result | time |
|---|---|---|
| control, no lock | FEASIBLE | 243s |
| today's level (90>=246, 80>=250) | FEASIBLE | 243s |
| **RC9.1 floor (80>=264)** | **INFEASIBLE** | **4.6s** |
| RC9.1 target (90>=256) | UNKNOWN | 243s |
| RC9.1 both | **INFEASIBLE** | 5.0s |

**INFEASIBLE in 4.6 seconds is a proof, not a timeout.** The two controls
passing confirm the harness. The target side is UNKNOWN — not proven
impossible, merely not found — which fits the earlier reading that the -6
target sits inside the noise band while the **-12 floor is the solid finding**.

## Which constraint

Relaxing each hard flag in turn, with the floor lock held:

| relaxed flag | result |
|---|---|
| (baseline) | INFEASIBLE |
| zero_active, language, opening, rest | INFEASIBLE |
| **fixed** | **FEASIBLE** |
| hard_off, leave, strict_off, max_shift_variety, hard_floor, week_boundary | INFEASIBLE |

**Exactly one flag flips it: `fixed`.** Fixed requests are what make RC9.1's
floor unreachable — not language rules, not rest gaps, not the week boundary.

## How much of the schedule is pre-assigned

```
roster                     33 associates
fixed day-entries         105
slots in the week         231  (33 x 7)
pre-assigned              45%
```

Fifteen associates carry exact shift times on every day (`05:00 - 14:00` and
similar). With 45% of the week pinned, the solver's remaining freedom is not
enough to cover 264 intervals at floor level, and CP-SAT proves it in seconds.

## What this does NOT establish

**Whether RC9.1 enforced all 105 of those entries.** Its engine
(`da21c3bacf577e5a...`) is not present anywhere in the tree — the oldest copy
available is RC9.2.1 — so the two cannot be diffed.

That leaves two readings, and the evidence here does not separate them:

1. **Regression.** Something tightened fixed-request handling between versions,
   and the tightening is wrong.
2. **Correctness fix.** RC9.1 silently dropped some fixed requests, so its 264
   was achieved by ignoring constraints it should have honoured — and today's
   251 is the honest number.

Reading 2 is not idle speculation: **B-11 found exactly this class of defect**
in this engine — name-matched input sheets failing open, so rows that did not
match were silently discarded rather than rejected. A parser that used to drop
fixed-request rows and now reads them correctly would produce precisely this
pattern.

The parser currently emits 15 `EXACT_FIXED_ROW_NESTING_GROUP_IGNORED` warnings
on this workbook, one per pinned associate, where an exact day request causes a
flexible nesting group to be cleared. That is visible, declared behaviour, not
a silent drop.

## Consequence

The Voice gap is **not** a general search-quality regression, which is how it
was previously characterised. It is a specific, proven interaction with fixed
requests, and it is arithmetic rather than search effort: more budget, more
workers and more profiles cannot recover it.

The question worth answering next is whether those 105 entries *should* all be
binding. That is a business question about the workbook, not an engine bug:
if the fixed requests are genuine, 251 is the correct answer and RC9.1's 264
was wrong.
