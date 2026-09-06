# Cricut Voice on RC9.2.2 — partly budget, mostly real

Voice was the last baseline-comparable scenario not re-run on this build, and
the one carrying the known 244-vs-256 open item. Three runs, engine
`b1acc9a949c30639`, `Language Working Window = Off`.

## The runs

| | RC9.1 | QUICK 3600s | DEEP 14400s | Stage-1 only, 2 profiles |
|---|---|---|---|---|
| before target | **256** | 247 | 247 | **250** |
| before floor | **264** | 251 | 250 | 252 |
| after target | — | 228 (86.4%) | 246 (93.2%) | n/a |
| Gate 5 | — | **FAIL** (−19) | PASS_DELTA_ONLY (−1) | n/a |
| break-concurrency violations | — | 87, peak 13 | 8, peak 5 | n/a |
| Gate 8 | — | PASS | PASS | n/a |
| Stage-1 profiles | — | 3 of 15 | 13 of 15 | 2 of 2, **COMPLETE** |

## What was budget and what was not

**The QUICK alarm was starvation, not engine behaviour.** Gate 5 failing with 19
intervals lost to breaks, 87 concurrency violations and 13 people on break at
once all came from a run that explored 3 of 15 skeleton profiles. At the design
budget the break stage costs 1 interval and violations drop to 8. Gates 2 and 9
correctly refused to score the QUICK run rather than reporting a regression that
was really a starved search.

**Stage 1 is still starved at DEEP.** 13 of 15 profiles; Stage 1 received 3398s
of the 14400s budget. The two it dropped were `before_target_champion` — the
profile built to maximise the exact metric that is short — and
`protected_balance_polish`.

**Running the dropped profile closes part of the gap, not all of it.** Given the
full Stage-1 window (2525s, both profiles COMPLETE, no truncation),
`before_target_champion` reaches **250**, up from 247. So profile starvation
accounts for **3** of the 9 intervals.

## The remaining gap is real

**−6 target, −12 floor against RC9.1**, with no truncation and with RC9.1's own
winning profile (`floor_gate_hunter_before`) run to completion alongside. That
profile did not reach 256 on this engine either.

The −6 sits exactly on this project's documented 6-interval run-to-run noise
band, so it alone would not be conclusive. **The −12 floor is well outside it**
and is the solid finding.

Both profiles finished `FEASIBLE`, not `OPTIMAL`, so 250 is not proven to be the
ceiling — more time could still move it. What is established is that RC9.2.2
does not reach RC9.1's Voice result at any budget tried here.

## Status

Voice does **not** match RC9.1 and is the one scenario in the set that does not.
It is not a crash, not a validation failure and not a headcount problem: Gate 8
passes with zero hard failures and the break stage is healthy at the design
budget. It is a search-quality gap of roughly 6 target and 12 floor intervals.

Two scenarios match RC9.1 exactly on this engine (AE AR B2B 168/168, NMG_SP
126/126) and GDI 24/7 is production-eligible. Voice is the open item.
