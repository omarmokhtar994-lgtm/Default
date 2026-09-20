# Joint refinement: 90% of peak memory, no measured quality on 4 of ~15 workbooks

SCOPE FIRST, because the headline below oversells its coverage. Joint
refinement executed in 20 runs across **4 distinct workbooks**, but
AE_AR_B2B accounts for 16 of those runs and 24 of 41 attempts. The other
three contributed 1-2 runs each. Eleven packaged workbooks -- Cricut_Chat,
Cricut_Voice, NMG_EN, NMG_SP, GDI_REAL28, SAKS_NEW and others -- were never
tested, and every run was QUICK at 300-1800s. DEEP allots the phase 5400s
and is untested. `improved: 0` holding across all four is a real signal; it
is NOT grounds to change a shipped default corpus-wide.

Scanned **44 solver audits** — every run produced in this session: the 16-run
budget sweep, the 18-run worker test, the deterministic A/B pairs, and the
memory probes.

| | |
|---|---|
| runs where joint refinement executed | 18 |
| total attempts | **37** |
| accepted | 8 |
| **improved** | **0** |

Attempt outcomes:

| outcome | count |
|---|---|
| `NO_FEASIBLE_SOLUTION` | **26** |
| `ANCHOR_REPLAY_FEASIBLE` | 8 |
| `ANCHOR_REPLAY_INFEASIBLE` | 3 |

The 8 "accepted" are all `ANCHOR_REPLAY_FEASIBLE` — the phase reproduced the
anchor it started from. That is not an improvement, and the engine's own
counter agrees: `improved: 0` in every single audit.

## Cost of that zero

* **Memory.** Peak RSS tracks joint-refinement execution across three
  otherwise-identical 1800s runs: 2 attempts -> 8244 MB and 8297 MB; 0 attempts
  -> 645 MB. The A/B isolating the flag is still running.
* **Budget.** `joint_refinement_reserve_sec` is **900s at QUICK** — a quarter of
  the 3600s default — and 5400s at DEEP.

## The two runs where it burned 7.6 GB, in full

```
MEMPROBE / FINEPROBE   joint_refinement: attempted 2, accepted 0, improved 0
   attempt 1  incumbent_replay        45s  ->  ANCHOR_REPLAY_INFEASIBLE
   attempt 2  release_quality_master  90s  ->  NO_FEASIBLE_SOLUTION
   final quality: before_target 166 -> after_target 165, floor 167 -> 167
```

Both attempts failed. The schedule shipped is the one break search produced.

## A trap to avoid when reading this

TM18 (0 joint attempts) finished at `after_target` **142** against MEMPROBE's
**165**, which looks like joint refinement being worth 23 intervals. It is not.
TM18 ran **2** Stage-1 attempts against MEMPROBE's **9**, and its skeleton was
worse before breaks were ever placed: `before_target` **145 vs 166**. The
deficit is entirely Stage-1's; joint refinement contributed `improved: 0` in
both.

Attributing that gap to joint refinement would have been exactly the error
this review keeps catching — reading a difference between two runs that differ
in more than one way.

## Scope, stated honestly

Every one of these 44 runs is QUICK mode at 300-1800s. At DEEP the phase gets
5400s and may behave differently; that is **untested**. The claim here is
narrow and empirical: *across 37 attempts at the budgets actually measured,
joint refinement has never improved a schedule.*

## Related

B-13 found both joint bounds comparing `model.NewBoolVar` on both sides, so
they constrain nothing. A structurally inert bound is consistent with a phase
that cannot steer itself toward a better solution, though 26 of 37 attempts
returning `NO_FEASIBLE_SOLUTION` points at the joint model being too hard to
solve in its slice rather than at the bound alone.

---

## Isolated A/B (third attempt, correct flag) — AE_AR_B2B, 1800s

Two earlier attempts were void: the first passed a flag the runner does not
accept, the second used `--joint-refinement-reserve-sec 0`, which only shrank
the allocation from 241s to 87s and left the phase enabled in both arms. The
correct switch is `--disable-joint-refinement`.

| | ON | OFF | delta |
|---|---|---|---|
| **peak RSS** | 8197 MB | **820 MB** | **-7377 MB (-90%)** |
| wall | 1811s | 1726s | -85s |
| stage1 / stage2 attempts | 9 / 2 | 9 / 2 | identical |
| before_target | 166 | 166 | 0 |
| after_target | 165 | 165 | 0 |
| before_floor | 167 | **168** | **+1** |
| after_floor | 167 | 167 | 0 |

`OFF` reports `joint status=DISABLED_BY_RUN_PARAMETER`; `ON` reports
`attempted 2, accepted 0, improved 0`.

Search work is identical in both arms, so the variable is isolated. **Joint
refinement is 90% of peak memory on this case, and removing it cost no
coverage** — the floor was marginally better.

This confirms the mechanism behind the 3600s OOM. It does **not** license a
default change on its own: one workbook, one budget.

---

## Corpus extension (2026-09-20) — scope concern resolved

The earlier caveat was that AE_AR_B2B dominated the sample. Six further
workbooks were run at 1800s to settle it.

| workbook | runs | jr ran | attempts | improved |
|---|---|---|---|---|
| AE_AR_B2B | 22 | 17 | 26 | **0** |
| AE_FR_B2B | 15 | 2 | 13 | **0** |
| AE_IT_Choice | 1 | 1 | 12 | **0** |
| NMG_EN_AND_SP | 1 | 1 | 10 | **0** |
| GDI_REAL28 | 1 | 1 | 4 | **0** |
| AE_IT_B2B | 6 | 1 | 2 | **0** |
| AE_FR_Choice | 6 | 1 | 2 | **0** |
| Cricut_Voice | 1 | 0 | 0 | — |
| Cricut_Chat | 1 | 0 | 0 | — |
| **TOTAL** | **55** | **24** | **69** | **0** |

**69 attempts across 7 distinct workbooks. Zero improvements.**

AE_AR_B2B is now 26 of 69 attempts rather than the bulk, and the four newly
covered workbooks (AE_IT_Choice, NMG_EN_AND_SP, GDI_REAL28, plus the existing
AE set) agree.

## Memory correlation holds across the corpus

| workbook | jr attempts | peak RSS |
|---|---|---|
| GDI_REAL28 | 4 | **5254 MB** |
| NMG_EN_AND_SP | 10 | **3389 MB** |
| AE_IT_Choice | 12 | **2017 MB** |
| Cricut_Chat | **0** | **609 MB** |
| Cricut_Voice | **0** | **600 MB** |

Every workbook where the phase ran shows GB-scale peak memory; both where it
did not stay under 610 MB. Together with the isolated A/B on AE_AR_B2B
(8197 MB -> 820 MB with `--disable-joint-refinement`, identical coverage), the
mechanism is established on more than one case.

## Recommendation, now corpus-backed

**Default joint refinement OFF at QUICK.** It recovers a 900s reserve (25% of
the 3600s budget) and the GB-scale memory that caused the 3600s OOM, at no
measured coverage cost across 69 attempts on 7 workbooks.

## Still untested, stated plainly

* **DEEP.** The phase gets 5400s there and has never been measured. The
  recommendation above is scoped to QUICK.
* **Cricut_Chat and Cricut_Voice** never reached the phase at 1800s, so they
  contribute nothing either way.
* Two corpus runs failed for unrelated, pre-existing reasons: NMG_EN_AND_SP
  cannot place breaks without explicit exceptions, and
  NMG_EN_FIXED_NESTING fails pre-solver contract validation. Neither is a
  regression from this work.
