# Colab run 1 — results, and a packaging failure that wasted most of the compute

Five scenarios came back. **Read the failure first: it bounds what the numbers
are worth.**

## The packaging failure

Package 2 ran the 14,400 s DEEP budget as six 2,400 s segments with `--resume`.
That design does not work, and the ledgers prove it.

Every segment called `build_global_budget_plan(2400)`, so every segment planned
its phases for **2,400 s**, not 14,400 s:

```
stage1_search 332   break_search 460   joint_refinement 840
```

Stage 1 therefore got a ~332 s allocation *in each segment*, which fits two or
three skeleton profiles. Resume carries the **skeleton pool** forward, but not
the **budget**. Six 2,400 s segments are not one 14,400 s run; they are six
independent 2,400 s runs that share a pool of skeletons.

What that cost, from the segment ledgers:

| scenario | wall clock | segments | Stage-1 profiles on the final segment |
|---|---|---|---|
| GDI_REAL28 | 4.01 h | 6, **all exit 2** | 6 of 15 |
| NMG_EN_SP | 3.86 h | 6 | **2** of 15 |
| AE_AR_B2B | 3.73 h | 6 | **2** of 15 |
| NMG_SP | ~2,295 s final segment | — | 8 of 15 |
| CRICUT_VOICE | ~2,293 s final segment | — | 3 of 15 |

Roughly **15 hours of Colab compute**, and not one scenario completed its
15-profile portfolio — which was the entire purpose of the DEEP budget.

My README called a segmented run "a close and honest approximation" of a single
run. That was wrong, and it was the wrong call to ship without testing
accumulation across segments. The in-house test I ran only proved that resume
*does not error*; it never checked that a later segment does more work than the
first.

**The fix is to stop segmenting.** Run 14,400 s as a single Colab session. A
running cell is not idle, so a four-hour run holds a session; write results to
Drive so a disconnect loses the run rather than the results.

## What the runs still tell us

These are real results at roughly a 2,400 s effective budget.

| scenario | Gate 4 | Gate 5 | Gate 8 | Gate 2/9 |
|---|---|---|---|---|
| NMG_SP | PASS* | **PASS** | PASS | NOT_COMPARABLE (8/15) |
| CRICUT_VOICE | PASS* | **PASS** | PASS | NOT_COMPARABLE (3/15) |
| AE_AR_B2B | PASS* | **FAIL** | PASS | NOT_COMPARABLE (2/15) |
| NMG_EN_SP | PASS* | **FAIL** | PASS | NOT_COMPARABLE (input not in baseline) |
| GDI_REAL28 | n/a | NO_EVIDENCE | NO_EVIDENCE | n/a |

\* `PASS_PROTECTED_NOT_EVALUATED` — no workbook configures a protected-tier
minimum, so that benchmark has still never run on anything.

### Against the RC9.1 baseline, for context only

Not gate verdicts — every one of these searches was truncated, which is why the
comparator refuses to score them.

| scenario | RC9.2.1 before target / floor | RC9.1 | delta |
|---|---|---|---|
| NMG_SP | 126 / 126 | 126 / 126 | **0 / 0 — exact** |
| CRICUT_VOICE | 246 / 255 | 256 / 264 | −10 / −9 |
| AE_AR_B2B | 131 / 159 | 168 / 168 | **−37 / −9** |

NMG_SP matching RC9.1 exactly is the strongest positive signal so far. AE AR B2B
at −37 is far beyond the ~6-interval noise floor and is the most concerning
number in the set — but it ran **2 of 15** profiles, so it is a question, not a
verdict.

### Gate 5 is the recurring weak point

Break placement failed on two of the four scenarios that produced artifacts:

- **NMG_EN_SP** — target loss 28/252 (11.1%), floor loss 17/252 (6.7%), and
  **21 language-reserve quarters lost to breaks**
- **AE_AR_B2B** — 2 language-reserve quarters lost to breaks

This is the same trade-off Cricut Chat showed between 900 s and 2,700 s: a
stronger skeleton is harder to place breaks into. It is now visible on three
separate scenarios and is the clearest engine-quality theme in the evidence.

### GDI_REAL28 fails cleanly, and that matters

Six segments, `FAIL_STAGE2_TIME_BUDGET_EXHAUSTED` each time, **510 Stage-2
attempts** without a compliant break solution, and
`stage2_budget_guard: INSUFFICIENT_GUARANTEED_STAGE2_TIME`. Four hours produced
no schedule.

The engine reported that honestly rather than publishing a degraded artifact,
which is the behaviour the audit was meant to secure. But GDI REAL28 plainly
needs more than 2,400 s of Stage 2, and its difficulty is now quantified.

## What to run next

1. **Cricut Voice and AE AR B2B, single 14,400 s runs, no segmentation.** These
   two carry the open gate 2/9 questions and both were badly starved.
2. **GDI REAL28 at a single large budget**, to find out whether it is
   budget-bound or genuinely infeasible under the current break model.
3. Do not re-run NMG_SP at length — it already matches RC9.1 exactly.
