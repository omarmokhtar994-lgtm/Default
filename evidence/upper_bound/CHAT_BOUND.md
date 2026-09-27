# Is Chat's 179 near the maximum? A cheap bound cannot say

Tools: tools/research/upper_bound/after_target_bound.py (pattern model) and
after_target_bound_v2.py (aggregated breaks). Both keep only rules no schedule
can escape (per-day availability, <= 5 - leave work days per person, legal
break timing and minimum break time) and score coverage with the engine's own
exact formulas; both reproduce the engine's own best schedule exactly inside
the model (M2 111 = 111, Chat 178 = 178, Voice 246 = 246).

| model | Chat best relaxed schedule | proven upper bound | of 242 active |
|---|---|---|---|
| patterns (900 s, 4 workers) | 192 | 242 | trivial |
| aggregated breaks (600 s, 4 workers, linearization 2) | 218 | 242 | trivial |

What this shows: once the weekly rules are dropped (two consecutive OFF days,
rest gaps between shifts, the limit on different shifts per person, fixed
assignments, language rules, break concurrency caps), schedules reach at least
218 target intervals. So the gap between the engine's 179 and 218 is created by
those rules, and certifying how much of it is recoverable needs them modelled
exactly - the full joint shift+break optimizer, which is out of scope by
decision (2026-09-27). A cheap valid bound for Chat is therefore not available.

Indirect evidence that 179 is close to what this search can reach: across four
3,600 s seeds Chat's best saturates at 179 (171, 178, 179, 179); break
placement on the chosen skeletons is already proven optimal per day (DNBS);
and the Stage-2 -> Stage-1 feedback found no improvement on Chat in 40 minutes
(evidence/feedback_loop). M2's bound is 117 = its known optimum (engine 111).
