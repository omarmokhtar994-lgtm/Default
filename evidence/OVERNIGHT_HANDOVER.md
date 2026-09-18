# Overnight handover

Written 03:50. Read this first.

## The one-line state

All nine cleanup fixes are applied and gated. One real defect (B-13) is proven
and its fix is built, gated and deliberately **not** applied. Four findings that
were on the list as defects turned out not to be.

## What is in the release tree right now

    GATE PASS - 18 suites + 2 selfchecks + undefined-name sweep
    four real workbooks solve clean: validation PASS, parity 48/48

Applied and verified:

    W1 (reporting half)  floor_losses_from_breaks metric, cap and gate
    W1 bound revert      the harmful constraint removed
    B-11                 name-matched sheets fail closed  (found a real defect
                         in SAKS_NEW: Associate 051 was being silently dropped)
    B-12                 header lookup cannot match a prose banner
    C-3                  preference vocabulary fails closed
    B-9                  parity surface 41 -> 48
    RC-B                 49 permissive shadow defaults aligned to declared policy
    RC-A                 18 silent cross-metric fallbacks now fail by name
    CM-1                 the one canonical field that was not its own alias
    S6-1 + S6-2          nesting-group leave conflict is now a named failure
    S13-2                213 lines of dead code deleted

Rollback for the whole stack: `tar xzf scratchpad/rc5p/PRE_FIXPLAN_SNAPSHOT.tgz`

## B-13: the real defect, proven, fix NOT applied

Both joint-refinement bounds compared a solver-controlled left side against a
solver-controlled right side:

    model.Add(sum(after_hits) >= sum(before_hits) - cap)

`before_hit` is a `model.NewBoolVar`. So the bound is satisfiable by degrading
the before-state instead of protecting the after-state. The TARGET bound is
pre-existing, unconditional and **live in production**.

`tools/b13_structural_probe.py` puts it to CP-SAT directly:

    no bound at all              before_hits 0   after_hits 0
    gameable after >= before-cap before_hits 0   after_hits 0
    constant after >= 10-cap     before_hits 8   after_hits 8

The gameable form gives exactly the answer that having no constraint gives. It
is not weak protection, it is none.

Real-engine corroboration, from three paired seeds run before the environment
degraded:

    AE_IT_B2B   bound active     before_floor  91, 91, 91
                bound inactive   before_floor  91, 98, 97

`tools/b13_safety_probe.py` checks the fix does not over-constrain: feasible
across every realistic cap and break load; only cap=0 under extreme removals
fails, which is genuinely infeasible, and the default cap is never 0.

**Why it is not applied.** It changes search behaviour. The defect evidence is
strong; evidence that the fix is neutral-or-better on real schedules is absent,
because no end-to-end A/B could be completed. Applying a behavioural change
without that is exactly how the W1 regression got in.

## Why the A/B never ran

Container restarts, five of them: 01:19, 02:33, 02:43, 03:12, 03:45. Not memory
-- 15 GB free; the kernel log shows `idle-reclaim` recycling the container. Three
attempts died, including at a reduced 900-second budget. Nothing completed.

The pivot to structural probes was the response, and it produced a stronger
result than the A/B would have: the A/B could only have shown a difference in
outcomes, whereas the probe shows the constraint cannot protect anything at all.

## Four findings that were not defects

    S9-1   reclassified  logged as "add the missing prefix"; no prefixed variant
                         exists anywhere, so the fix is eight new metrics and a
                         ranking change, not a rename
    B-10   retracted     logged as "a CAP used as a FLOOR"; the probe shows
                         90-150s return 160 and 180s returns 162, so 180 is
                         where the BEST value appears and the floor is correct.
                         My misreading. The gate caught it.
    S9-2   retracted     dominance overriding the lexicographic order is the
                         mechanism, not a bug. My fix disabled it and the
                         engine's selfcheck rejected it on two regressions.
    S15-3  retracted     not truncating on nominal allocation is documented
                         design: phases run on time carried over from earlier
                         phases, measured at seventeen occurrences on NMG SP.

In every case the engine carried a comment or a test explaining the decision,
and the register entry had preserved the observation while losing the rationale.
Two of my "fixes" were caught by the project's own tests and selfcheck.

## What is left

    open, needs a decision from you
      B-9b   should the validator model language reserve, skill allocation and
             employee quality? Zero references each today.
      W1 cap the floor-loss cap currently mirrors the target cap, so it changes
             no outcome. Tightening it is scheduling policy.
      B-13   apply the fix, once there is an environment where an A/B survives.

    open, needs no code
      C-2    unreachable through Excel; all ten flags carry dropdowns
      S6-3   corpus-coverage gap, not code

## The honest summary

RC9.2.x is not proven better than RC9.1, and I would keep RC9.1 as production.
What this work genuinely bought:

  - the engine now REPORTS things it was silently hiding, and one of those
    reports immediately found a real defect in a shipped regression asset
  - a harmful change was caught and reverted before release
  - one live production defect is proven with a reproducible probe
  - the defect register is four entries shorter and considerably more truthful

What it did not buy: any evidence that produced schedules are better.
