# S15-3 retracted: not truncating under-funded phases is the documented design

S15-3 was logged as "phases run below their own declared minimum" with the fix
"skip a phase allocated below its own floor; give the seconds to one that can
use them". The source says why that is deliberately not done.

## The design, in the engine's own words

    """How many Stage-1 profiles a wall-clock window can pay for at full depth.

    Reporting only: the loop does not truncate its portfolio up front, because
    a profile that proves OPTIMAL in a fraction of a second returns its slice
    unspent (NMG SP does exactly this, seventeen times). This is what the run
    log states it can afford, so a truncated search is visible in the log
    rather than only in the audit afterwards.
    """

and at the phase level:

    # A phase funded below the slice it needs for its own first attempt is
    # not a short phase, it is a phase that will attempt nothing. Record
    # which ones were dropped for that reason, and what they would have
    # needed, so "this phase did not run" is answerable from the audit.
    ...
    f"...it can only run on time carried over from earlier phases"

Nominal allocation is not the budget a phase actually gets. Earlier phases
return unspent time -- measured at seventeen occurrences on NMG SP -- and a
phase nominally below its guard may be funded perfectly well by carryover.
Truncating on the nominal figure would drop phases that would have run.

## The evidence never showed a live problem

S15-3's recorded evidence is `target_lock_recovery` at 43s against a 65s guard
**at a 600s total budget**. Task #37 had already measured the same phase at a
3600s budget: 139s against the same 65s guard, comfortably funded. So the
condition appears only at budgets where every phase is starved, and where the
engine prints `BUDGET_PHASE_AT_RISK` naming the phase and what it needed.

Detected, reported, answerable from the audit, and deliberately not acted on.
That is a design with a rationale, not an unenforced rule.

Closed as not-a-defect. No applier written.

## All four "behavioural" findings resolved without a single behavioural fix

    S9-1   reclassified -- no prefixed variant exists; needs 8 new metrics
    B-10   retracted    -- the constant is correctly a floor; I misread the probe
    S9-2   retracted    -- the frontier overriding the ordering IS the mechanism
    S15-3  retracted    -- not truncating on nominal allocation is documented design

The one real defect in this area, B-13, was not on the list. It was found by
accident while building a fix for something else, and it is the only one of the
five now under measurement.

Four register entries described behaviour the source contradicts. In each case
the engine carried a comment or a test explaining the decision, and the register
summary had preserved the observation while losing the rationale. Reading the
summary was enough to schedule work; only reading the source was enough to know
whether the work was worth doing.
