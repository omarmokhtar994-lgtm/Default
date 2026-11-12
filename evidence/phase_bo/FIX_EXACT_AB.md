# Phase BO change 1: Fix rest of the day solved exactly, result (rule: FIX_EXACT_RULE.txt, written before the B run)

Run 2026-11-12 (Egypt time), `bench_breaks.py`, figures in `breaks_ab.json`. Intervals at the 90% target out of 28; worst = the worst interval's share.

| Case | Fix (greedy) | Replan fresh (greedy) | B, exact balanced | B worst against best A worst | B time |
|---|---|---|---|---|---|
| 6 slack days | 28 | 28 | 28 | 0.900 = 0.900 | 0.3 to 1.3 s |
| n=20 tight s1 | 25 | 25 | 25 | 0.882 = 0.882 | 0.4 s |
| n=20 tight s2 | 25 | 24 | 26 | 0.882 > 0.877 | 0.8 s |
| n=35 tight s1 | 24 | 19 | 25 | 0.882 = 0.882 | 1.2 s |
| n=35 tight s2 | 28 | 28 | 28 | 0.900 = 0.900 | 1.4 s |
| n=50 tight s1 | 26 | 24 | 27 | 0.899 > 0.893 | 1.7 s |
| n=50 tight s2 | 25 | 25 | 27 | 0.898 > 0.888 | 3.1 s |

Rule: 1 holds (B's count is never below either A tool; higher on 4 tight days). 2 holds (B's worst is never lower). 3 holds (OPTIMAL on all 12).
4 holds (slowest 3.1 s; B total about 14 s against about 17 s for the two A tools). 5 holds (the page recounts every exact proposal before it is
offered and falls back to the greedy answer otherwise; `test_bo_balanced_fix`, and 220 related tests pass). Decision: adopt B for Fix rest of the day.
Losses: none on these cases. B is slower than Fix on 3 cases by up to 1.2 s and faster on 5.

Not changed, and why: "Replan the day's breaks" (fresh). On the page it is called with the default break times as its goal (owner, Phase AX: "prioritize
the default, followed by the engine") and shows its result whether or not it beats the day, so it answers a different question than the benchmark's
fresh arm; swapping it would change what the button means. It stays as it is.

How it is wired: `DayBook._fix_exact`. The exact solver runs with nothing given up and the worst interval lifted; its proposal is kept only when the
page's own recount shows no fewer intervals at the target and a worst interval no lower. Otherwise, and whenever the exact search proposes nothing
(for example a day already at its best count where the greedy search can still cut hours short), the greedy answer stands as before.
