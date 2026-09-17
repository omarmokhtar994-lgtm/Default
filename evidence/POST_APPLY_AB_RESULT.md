# Post-apply A/B: the applied stack measured against itself

Six cases, pre-apply tree vs post-apply tree. Verified clean before scoring:
`input_sha256`, `parameters_sha256` and `seed_sha256` match on all six; only
`engine_sha256` differs (and `contract_sha256`, which W1 legitimately moves by
adding two contract fields). This is the comparison the earlier
sweep-vs-authors'-baseline could not be, because that one also changed ~25 CLI
flags.

    case            target b->a (pre)     floor b->a (pre)      parity  gate  delta
    AE_AR_B2B       168->168 (168->168)   168->168 (168->168)   48/48   WARN  +0/+0
    AE_AR_Choice    141->141 (141->141)   163->160 (162->159)   48/48   PASS  +0/+1
    AE_FR_B2B       112->112 (112->112)   112->112 (112->112)   48/48   WARN  +0/+0
    AE_FR_Choice    112->109 (112->109)   112->112 (112->112)   48/48   WARN  +0/+0
    AE_IT_B2B        79->73  ( 78->72 )    91->87  ( 91->88 )   48/48   WARN  +1/-1
    AE_IT_Choice    BLOCKED -> hard-valid schedule                              --

## Three questions, three answers

**1. Parity holds at 48/48 on real workbooks.** B-9's seven new independent
recomputations agree with the engine on all six cases. They had only ever run
under unit tests before this.

**2. W1's floor-loss metric reports.** `floor_losses_from_breaks` is now
populated on every case, and it found losses nobody was measuring:

    AE_AR_B2B      floor 0   target 0
    AE_AR_Choice   floor 3   target 0
    AE_FR_B2B      floor 0   target 0
    AE_FR_Choice   floor 0   target 3
    AE_IT_B2B      floor 4   target 6
    AE_IT_Choice   floor 7   target 10

**3. The joint-refinement bound DOES change produced schedules** -- three of six
cases moved. That settles the question the bound was flagged for. It does not
yet settle whether the movement is the bound or the solver.

## AE_IT_Choice went from blocked to a valid schedule

Pre-apply it produced nothing: `FAIL_BREAKS_REQUIRE_EXPLICIT_EXCEPTION`, needing
one no-break associate-day against a cap of zero. Post-apply:

    technical_status      PASS_WITH_QUALITY_WARNINGS
    outcome_code          FINAL_SCHEDULE_GENERATED_WITH_DECLARED_QUALITY_DEBT
    headline              Hard-valid final schedule generated with declared
                          operational warnings
    no_break_exceptions   0
    production_eligible   True
    independent validation PASS

**It did not bypass the cap.** `no_break_exceptions` is 0 -- the search found a
genuinely zero-exception skeleton. This is consistent with the pre-apply run's
own wording, which proved a minimum of one exception *for the tested skeletons*;
a different skeleton set is entitled to do better. The hard rule was respected,
not relaxed.

## Why this is not yet a claim

The two numeric movements are ±1 interval. That is exactly the magnitude of
multi-worker CP-SAT nondeterminism, which the engine documents itself. On a
single seed I cannot separate the bound's effect from the solver's noise, and
the unblocking of AE_IT_Choice is too valuable a claim to rest on one draw.

Per the decision rule written down *before* the result was known: delta on more
than two cases means repeat those cases at further seeds. Three moved, so all
three are being repeated at seeds 9001 and 9002, both arms.

## How the repeats are run

12 runs as 3 waves of 4. Each wave runs two pre/post PAIRS concurrently, so both
arms of a comparison see identical machine conditions -- which is stronger than
running them hours apart, not weaker.

This corrects an earlier claim of mine that A/Bs had to run sequentially. That
was asserted without measurement and was wrong: one run uses ~105-115% CPU on a
4-core box, so three cores sat idle through every sweep in this work. Four
concurrent runs is a small oversubscription that every run in a wave absorbs
equally, leaving each pair matched. The correction cut the remaining A/B budget
from about 15 hours to about 4.
