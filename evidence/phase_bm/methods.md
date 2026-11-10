# Phase BM: which method gives the suggested week total (pre-registered 2026-11-10, before any run)

**Question.** The suggestion for a week's contacts is today one method: a robust line through the last clean weeks (`forecast.suggest_total`, "trend").
Phase BM adds four more (`recent`: the last four weeks weighted 4, 3, 2, 1; `last_week`; `seasonal`: the same week a year before times the ratio of
the last four weeks to the same four a year before; `blend`: the median of the others) and a back-test that scores each on the program's own past
weeks (each of the last eight clean weeks predicted from the weeks before it; error = sum of absolute misses over sum of actuals) and picks the lowest.
Should the suggestion come from the picked method, or stay the trend with the back-test shown as information?

**Test.** Four made-up histories of 70 weeks with a known truth, fixed seeds (`methods_rule.py`): (1) flat with 6 % noise; (2) a steady rise of 0.8 % a
week with 6 % noise; (3) a yearly season (plus and minus 25 %) with 5 % noise; (4) flat, then a level shift of +30 % twelve weeks before the end, 6 %
noise. For each, the last four weeks are held out one at a time: the method is picked by the back-test on the weeks before the held-out week only, and
its prediction is compared with the trend's prediction for the same week.

**Rule for taking the picked method** (written before the runs): its error over the four held-out weeks is no higher than the trend's on at least
three of the four histories, and never more than 2 percentage points higher on the fourth. Otherwise the suggestion stays the trend and the back-test is
shown as information only. Either way the total stays the planner's: the suggestion is never used unless they press "Use the suggestion".

## Result
Run 2026-11-10 (`methods_rule.py`, seeds 11 to 14):

| history | picked by the back-test | picked, error | trend, error |
|---|---|---|---|
| flat | recent x4 | 1.93 % | 1.74 % |
| rise | recent x3, blend | 6.10 % | 4.25 % |
| season | seasonal x4 | 2.17 % | 6.53 % |
| shift | last_week x3, recent | 9.25 % | 8.65 % |

No higher than the trend on 1 of 4 (largest excess 1.85 points): **the rule is not met.** Always taking the picked method is rejected: on plain
histories it swaps the trend for a method that was a hair better in the back-test and is a little worse afterwards.

## Candidate 2 (pre-registered 2026-11-10, before its runs)
Take the picked method only when its back-test error is at least 20 % lower than the trend's own back-test error (relative: picked <= 0.8 x trend);
otherwise the trend. A clear win in the back-test (the season) is taken, a hair's breadth is not.

**Test.** The same four kinds of history on fresh seeds (21 to 24), so the margin is not fitted to the runs above; and the first four seeds again as a
second look. **Rule:** on each set of four, the error is no higher than the trend's on at least three histories and never more than 2 points higher
on the fourth. Both sets must meet it; otherwise the suggestion stays the trend and the back-test is information only.

## Result of candidate 2
(filled in after the runs)
