# Long-run polish (40 min of break-load feedback on the best schedule): not built

Question (2026-09-27): after a DEEP/OVERNIGHT seed portfolio, would spending
~40 minutes of Stage-2 -> Stage-1 break-load feedback on the winner raise
scores? The engine phase exists (--enable-break-load-feedback) but at 540 s
it accepted nothing (evidence/break_load_feedback_ab). Before building a
long-budget polish mode and its multi-hour A/B, the same loop was run with
40 minutes (2,400 s, 2-4 workers) on the best compliant candidate of each
case's 3,600 s run:

| case | start after_target | end | accepted | note |
|---|---|---|---|---|
| SYNTH_H1 (24x7) | 142 | **150** | 2 | the only gain |
| Cricut Chat | 178 | 178 | 0 | one try reached 179, rejected (week-boundary, severe gaps, imbalance worse) |
| Cricut Voice | 246 | 246 | 0 | tries reached 247-248, rejected (severe floor gaps, concurrency worse) |
| NMG_SP | 121 | 121 | 0 | |
| SYNTH_M2 | 111 | 111 | 0 | |
| SYNTH_H3 | 92 | 92 | 0 | best try 93 with a break-concurrency violation |

Decision: not built. The polish would help 24x7-shaped cases like H1 only,
nothing on any real workbook measured, and the time it would take (OVERNIGHT
seeds 5-6) is worth about +0.3 in expectation (evidence/seed_portfolio_ab/
SEEDS_CURVE.md), so even H1-like gains would not justify a new budget mode on
this evidence. The phase stays available as a flag for anyone running long
single runs on 24x7 workbooks. Probe outputs: *_PROBE.txt in this folder.
