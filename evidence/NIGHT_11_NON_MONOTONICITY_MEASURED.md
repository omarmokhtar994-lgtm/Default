# Does more budget ever give a worse schedule?

Recorded as an open defect ("non-monotonicity: more budget -> worse result").
Measured here, and the honest answer is smaller than the file suggested.

## The raw corpus number, and why it is not the effect size

Pairing every recorded run of the same workbook (same `input_sha256`) at
different time limits, over 117 audits:

```
workbooks with >=2 budgets: 18
budget pairs compared:     1469
non-monotonic (more budget, worse after_target): 287   (19.5%)
```

**That figure is confounded and should not be quoted as the effect.** The
pairs mix worker counts, seeds and engine versions -- `TELEM vs AE_FR_Choice`,
`B4_DIAG vs AE_FR_Choice` and so on are different runs of different builds,
not a budget sweep. CP-SAT is a portfolio solver, so a 4-worker run is not
reproducible even against itself.

## The controlled comparison

The `C_*` sweep is the only clean one: one session, one engine build, four
workers throughout, same workbook at 1800s and 3600s.

| workbook | 1800s (target/floor) | 3600s (target/floor) | delta target | delta floor |
|---|---|---|---|---|
| Cricut Chat | 159 / 221 | 164 / 223 | **+5** | +2 |
| Cricut Voice | 248 / 252 | 247 / 249 | **-1** | -3 |
| GDI | 141 / 156 | 150 / 156 | **+9** | 0 |

Two of three improve, and clearly. One regresses by a single target interval
and three floor intervals.

## Verdict

**Not established as a defect beyond solver noise.** A single -1 on one
workbook, at four workers, with one run per budget, is exactly the size of the
multi-worker nondeterminism already measured elsewhere in this project (the
same case moved by 2 intervals between repeats at the same budget). Calling it
non-monotonicity would need repeats at each budget, which have not been run.

What *is* established: doubling the budget is not reliably worth it either.
+5 and +9 on two workbooks for twice the wall clock is a weak return, which is
consistent with NIGHT_09 -- the extra time mostly buys Stage-2 attempts that
the phase budget was not funding in the first place.

## Scope

18 workbooks, 1469 raw pairs, 3 controlled pairs. One run per cell. No repeats.
