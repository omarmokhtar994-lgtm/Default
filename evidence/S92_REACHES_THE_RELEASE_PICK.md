# S9-2 correction: dominance DOES decide a shipped artifact

The defect register recorded S9-2 as "affects alternatives, not the release
pick", and earlier today I repeated that and proposed closing it by tracing
rather than measuring. Both were wrong. Tracing is what showed it.

## The chain

Inside the release selection function:

    frontier      = nondominated_candidates(parsed, pool)          # Pareto, 15 dims
    safer_options = [p for p in frontier if genuinely_safer_than_strict(p)]
    recommended   = max(safer_options, key=safety_key) if safer_options \
                    else recommendation_anchor

and the function returns, among its exports:

    ("RECOMMENDED_FINAL", recommended)

which is written as `_RECOMMENDED_FINAL_AFTER_BREAKS_SCHEDULE.xlsx` -- a release
artifact, not a diagnostic.

So when `safer_options` is non-empty, the shipped recommendation is chosen from
the **dominance frontier**, not from the lexicographic ordering that
`target_priority_tradeoff_select` produced. `recommendation_anchor` is only the
fallback.

## Why that matters

S9-2 is that the dominance test and the lexicographic order disagree: roughly 15
dominance dimensions against roughly 31 tuple terms, with about 15 terms absent
from the dominance test entirely. A candidate can therefore sit on the frontier
-- non-dominated on the 15 dimensions dominance knows about -- while the
lexicographic order, which sees all 31, ranks it below the anchor.

When that candidate also passes `genuinely_safer_than_strict`, it becomes
`recommended` and it ships.

## Status change

S9-2 moves from "trace and close" to "needs an A/B with repeats", alongside
B-13. It is not a reporting defect; it can change the workbook a user receives.

Whether it actually does so on real inputs is unmeasured. The mechanism is now
established by reading; the magnitude is not.

## Third register description to prove wrong today

    S9-1   logged as "add the missing prefix"     -- no prefixed variant exists;
                                                     the fix is eight new metrics
    B-10   logged as "a CAP used as a FLOOR"      -- the constant is correctly a
                                                     floor; the finding was my
                                                     misreading of the probe
    S9-2   logged as "not the release pick"       -- it decides a shipped artifact

The register's one-line descriptions have been less reliable than the source.
Each remaining item should be re-derived from the code before any work is
scheduled against it, rather than trusted from its summary.
