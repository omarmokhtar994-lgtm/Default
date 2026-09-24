# Seeds vs time: what the existing runs say

Retrospective. Every finished, validator-PASS run of the current engine code
(S2-PAR; DNBS absent or inactive) collected by the earlier A/Bs and production
runs, grouped by case and time budget. Same input, 2 workers, differing only
in seed and in run-to-run nondeterminism. The sample is small (2-4 runs per
cell) and was not collected to answer this question, so it motivates the seed
portfolio; it does not prove a policy. Mode defaults change only on a
prospective, pre-registered test.

```
case   budget  n  after_target values            mean  best | before_target values          best
CHAT      900  3  [167, 179, 182]                176.0   182 | [188, 194, 196]                196
CHAT     3600  3  [171, 178, 180]                176.3   180 | [191, 192, 197]                197
VOICE     900  2  [246, 246]                     246.0   246 | [248, 250]                     250
VOICE    3600  3  [245, 246, 247]                246.0   247 | [247, 248, 249]                249
AR        900  3  [167, 168, 168]                167.7   168 | [168, 168, 168]                168
AR       3600  2  [168, 168]                     168.0   168 | [168, 168]                     168
NMGSP     900  3  [121, 121, 122]                121.3   122 | [126, 126, 126]                126
NMGSP    3600  3  [121, 121, 122]                121.3   122 | [126, 126, 126]                126
M2        900  3  [109, 110, 111]                110.0   111 | [117, 117, 117]                117
M2       3600  4  [105, 108, 110, 112]           108.8   112 | [117, 117, 117, 117]           117
H3        900  3  [90, 91, 92]                    91.0    92 | [105, 105, 105]                105
H3       3600  4  [92, 92, 93, 95]                93.0    95 | [105, 105, 105, 105]           105
H1        900  2  [83, 117]                      100.0   117 | [121, 168]                     168
H1       3600  2  [138, 141]                     139.5   141 | [168, 168]                     168
```

## What it shows

* Real workbooks: 900 s -> 3,600 s leaves the mean after_target unchanged
  (Chat 176.0 vs 176.3, Voice 246 vs 246, AE_AR 167.7 vs 168, NMG_SP equal).
  The spread across seeds is larger than the effect of 4x the time: Chat
  167-182, and the best of three 900 s runs (182) beats every 3,600 s run (180).
* Before-breaks: equal or within 1 either way (Chat best 196 vs 197).
* The hard 24x7 overnight case needs a long single run: H1 at 900 s gave
  83 and 117, at 3,600 s 138 and 141. H3 gains about 2 with time.

## Consequence

Extra time is worth more as extra seeds than as a longer single run on the
real workbooks, but each seed must still be long enough for hard 24x7 cases.
`engine/RUN_PORTFOLIO.py` runs K seeds and keeps the best validated
after-breaks sheet and, separately, the best before-breaks sheet, so neither
can be worse than any of its own seed runs. The per-mode seeds x time default
is decided by a pre-registered measurement (evidence/seed_portfolio_ab/).
