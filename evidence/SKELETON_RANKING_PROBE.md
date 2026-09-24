# Ranking Stage-1 skeletons by a quick after-break estimate: not built

Idea (research report, recommendation 2): Stage 2 only reaches 1-6 of the ~11
Stage-1 skeletons within 3,600 s, starting with the best before-breaks one, so
feed it the skeletons most likely to be good after breaks.

Probe (offline, no run-to-run noise): every Stage-1 skeleton of the 3,600 s
seed-9000 CURRENT runs, breaks placed from scratch by the DNBS per-day
aggregated model (one pass, 1 worker), scored by calculate_metrics.
Script: scratchpad skeleton_estimate_probe.py (same method as
tools/research/joint_shift_break/day_neighbourhood_standalone.py).

| case | delivered | top estimate | skeleton Stage 2 delivered from, its estimate |
|---|---|---|---|
| SYNTH_M2 | 110 | 109 target90_restore_champion | target90_restore_champion, 109 (searched 2nd) |
| SYNTH_H3 | 92 | 93 target90_restore_champion (never searched) | release_gate_floor_satisfaction, 88 |
| Cricut Chat | 171 | 139 break_safe_reserve | target_floor_pareto_master, 129 |

Chat, one skeleton, more time per day: 2 s -> 129, 6 s -> 151, 20 s -> 151,
against 171 delivered by Stage 2 on the same skeleton.

Verdict: the from-scratch day model is a useful refinement of a good break
placement (DNBS) but a poor predictor on complex workbooks: on Chat it
underestimates the delivered skeleton by 20-40 intervals and would rank a
172-before skeleton above the 191-before skeleton that delivered 171. On H3 it
points at an unsearched skeleton that may be worth a few intervals. The signal
is not reliable enough to reorder Stage 2, so this is not built. The seed
portfolio covers the same gap differently: different seeds lead Stage 2 through
different skeletons (H3 3,600 s runs delivered 92, 92, 93, 95).
