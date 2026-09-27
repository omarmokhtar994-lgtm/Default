# How much does each extra seed add? (from existing runs, no new compute)

Same engine (the frozen CURRENT engine of the seeds-vs-time measurement), QUICK
3,600 s, 2 workers, four validated runs per case (seeds 9000-9003). Expected
best-of-N = the average over every N-run subset of the four observed runs.

| case | runs (after_target) | N=1 | N=2 | N=3 | N=4 |
|---|---|---|---|---|---|
| Cricut Chat | 171 178 179 179 | 176.75 | 178.83 | 179.00 | 179.00 |
| Cricut Voice | 246 247 248 246 | 246.75 | 247.33 | 247.75 | 248.00 |
| NMG_SP | 121 121 122 121 | 121.25 | 121.50 | 121.75 | 122.00 |
| SYNTH_H1 | 141 143 143 125 | 138.00 | 142.67 | 143.00 | 143.00 |
| sum | | 682.75 | 690.33 | 691.50 | 692.00 |

Gain per extra seed: +7.58 (1 -> 2), +1.17 (2 -> 3), +0.50 (3 -> 4).

Reading: the second seed is where the value is (mainly insurance against an
unlucky run: H1 125, Chat 171). Beyond four seeds nothing measurable is left in
these cases. The shipped defaults already follow this: QUICK 2 seeds (Notebook
A), DEEP 4. OVERNIGHT's six seeds add little over four; its extra time is the
candidate slot for a long polish step (evidence/long_run_polish, if shipped).
Limits: four realizations per case; the curve is an estimate, not a guarantee.
