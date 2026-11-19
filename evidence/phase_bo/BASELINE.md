# Phase BO baseline (2026-11-12): the break tools and the channel planner, measured before any change

Owner: improve results, speed and ease of use of break planning (normal, Rescue the day, Fix rest of the day) and channel planning.

## Break tools on made-up days (`bench_breaks.py`, intervals at the 90% target out of 28)
| Case | As planned | Fix rest of the day (greedy) | Replan the day (greedy, fresh) | Exact solver, nothing given up |
|---|---|---|---|---|
| 6 slack days (need 0.95) | 28 | 28 | 28 | 28 |
| n=20 tight, seed 1 | 24 | 25 | 25 | 25 |
| n=20 tight, seed 2 | 24 | 25 | 24 | 26 |
| n=35 tight, seed 1 | 19 | 24 | 19 | 25 |
| n=35 tight, seed 2 | 23 | 28 | 28 | 28 |
| n=50 tight, seed 1 | 22 | 26 | 24 | 27 |
| n=50 tight, seed 2 | 23 | 25 | 25 | 27 |

- The exact solver was proven best (OPTIMAL) on every case in 0.4 to 2.4 s; the greedy tools took 0.1 to 2.1 s.
- On tight days Fix rest of the day is 1 to 2 intervals short of the best on 4 of 6 cases; Replan the day is up to 6 short (19 against 25).
- On slack days all tools agree, so nothing is lost there.
- Caveat: the greedy tools rank the tightest interval first, the exact solver ranks the count of intervals at the target first, so a swap changes what "best" means, not only how well it is found.

## Channel planner (`tools/channel_scenarios.py --arms fair+tick --move-breaks`, seven made-up teams, Mon to Fri)
- Every scenario's slowest day took 25 to 28 s: the placing stage always runs to its 25 s limit (it searches by LNS only and cannot prove it is done).
- Quality figures per scenario are in `channel_base.json` (hours short, fair spread, stretches under two hours, problems).

Nothing has been changed. Proposed changes and their pass rules are to be written before any B arm is run.
