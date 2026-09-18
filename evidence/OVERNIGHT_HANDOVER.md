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

---

# Correction: why the A/B never ran (the real reason)

I reported container restarts as the cause. That was wrong, and the timings
say so:

    wave started 02:37:51   runs stopped writing 02:43:21   (5.5 min)
    wave started 03:50:48   runs stopped writing 03:56:18   (5.5 min)

Both died 5.5 minutes after launch. The container restarts were at 03:12 and
04:22 -- long AFTER the runs were already dead. Restarts were a coincidence I
mistook for a cause, twice, because I checked uptime and stopped looking.

**The actual pattern: background work is reaped a few minutes after the session
goes idle.** The kernel log shows `idle-reclaim` activity, and the earlier
sweeps in this work ran for hours precisely because the session was
continuously active across many turns. Once check-ins moved to 30-minute
intervals, every launch got about five minutes of live session and was then
collected.

## What follows from it

Long background work is not possible in this environment while the session is
idle. Scheduled check-ins do not keep it alive; they only wake it up
afterwards to find the work gone. Relaunching the A/B a fifth time would fail
the same way, so I stopped.

Two options exist for whoever picks this up:

  - keep the session continuously active (check-ins every few minutes), which
    costs a great deal to buy one measurement that is already proven
    structurally; or
  - run the A/B somewhere runs survive, which is the honest requirement
    recorded against applying the B-13 fix.

## Why this matters beyond tonight

Every claim in this handover about B-13 rests on the structural probes and on
the three paired seeds measured earlier, when the session was active. None of
it rests on the overnight A/B, because the overnight A/B produced nothing. That
separation was deliberate and it is why the conclusions still stand.

---

# Second correction: "the session being warm" does not help either

I told the user the A/B failed because background work is reaped when the
session goes idle, and therefore that it did not need a different environment --
it just needed them present. That was wrong too, and this run disproves it.

    05:11:36   wave launched, 4 solvers confirmed running, user actively present
    05:12:36   my turn ended
    05:16:36   all four heartbeats stop

Four minutes after the TURN ended, not after the user went away. The user was
here throughout; they sent messages at 05:11, 05:12 and 05:25.

## The actual rule

Background processes are collected roughly four to five minutes after the last
assistant turn completes. What keeps them alive is TURN ACTIVITY, not a human
being present and not a scheduled check-in every 30 or 45 minutes.

That is consistent with every observation now, including the two long sweeps
earlier in this work: those ran for about six hours each during stretches where
turns were happening continuously, a few minutes apart, as the work was being
driven.

## What follows

A 58-minute wave would need roughly fifteen turns spaced under five minutes
apart. The full seven-wave A/B would need well over a hundred. That is not a
reasonable use of anyone's budget to buy one measurement of a defect that is
already proven structurally.

**So: long end-to-end runs are not achievable in this environment.** Not
"needs the user around" -- that was my second wrong answer. The requirement is
an environment where a process survives without being driven, which this is
not.

## What this does not change

B-13 remains proven. `tools/b13_structural_probe.py` runs in seconds and shows
the gameable bound gives exactly the answer that having no bound gives. The
three paired seeds that corroborate it on the real engine were measured earlier,
during continuous work, and are unaffected.

The B-13 fix stays unapplied, and the reason is now sharper: the A/B it needs
cannot be run here at all, by me or by the user. It needs CI, a workstation, or
any host that does not collect idle processes.

## On my own reasoning

I gave three explanations for the same failure. First container restarts, which
the timings disproved. Then session idling, which this run disproved. The
pattern in both wrong answers is the same: I had a plausible mechanism and one
or two consistent data points, and I reported it as the cause instead of as a
hypothesis with a test attached. The third explanation is better supported --
it accounts for the successful sweeps as well as the failures -- but it deserves
the same scepticism until something tests it directly.
