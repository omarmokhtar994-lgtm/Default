# LP-visible hit links: measured, not shipped

Idea (research report, recommendation 4, from the OR-Tools v9.15 source):
OnlyEnforceIf rows reach the LP only at linearization_level >= 2, so add the
redundant plain-linear row `coverage >= threshold * hit` beside every reified
hit constraint (5 in Stage 1, 6 in Stage 2). Parked as
`patches/LPLINK_lp_visible_hit_links.patch`.

Component test (Stage 2 on the best candidate's fixed skeleton from each
3,600 s CURRENT seed-9000 run, no hint, 120 s, 2 workers, same seeds):

| case | links OFF (seed 9000 / 9001) | links ON (seed 9000 / 9001) |
|---|---|---|
| SYNTH_M2 | 111 / 110 | 109 / 111 |
| Cricut Chat | 172 / 169 | 169 / 168 |
| SYNTH_H1 | no solution / 133 | no solution / no solution |

No gain on M2 and Chat; on H1 the larger model found no solution in 120 s
where the unmodified model found one on seed 9001. The mechanism is real, but
the extra rows cost more than the tighter relaxation returns here. Not shipped;
the patch stays parked for the record.
