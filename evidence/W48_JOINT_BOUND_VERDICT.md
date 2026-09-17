# #48 verdict: the unconditional joint-refinement bound should be reverted

Nine paired runs -- three cases, three seeds, both arms, each pair run
concurrently so both arms saw identical machine conditions.

## The headline result did not survive

At seed 9000, AE_IT_Choice appeared to go from BLOCKED to a hard-valid
schedule, which I reported as the strongest result in this work. Across seeds:

    seed 9000   post = schedule   pre = BLOCKED
    seed 9001   post = schedule   pre = schedule     <- the PRE arm unblocks too
    seed 9002   post = BLOCKED    pre = BLOCKED

Blocked-versus-unblocked tracks the SEED, not the code. At 9001 the unpatched
engine unblocks the same case on its own; at 9002 neither arm does. The seed-9000
result was a lucky draw, and reporting it as an effect of the applied stack was
wrong. Retracted.

## The bound actively hurts the floor it was meant to protect

    AE_IT_B2B     post before_floor   pre before_floor   after-floor delta
      seed 9000         91                  91                 -1
      seed 9001         91                  98                 -4
      seed 9002         91                  97                 -2

The post arm's before_floor is pinned at exactly 91 on every seed while the
pre arm ranges 91 to 98, and the after-floor is worse on all three.

**The mechanism.** W1 made this unconditional:

    model.Add(sum(floor_hits) >= sum(before_floor_hits) - cap)

`before_floor_hit` is a `model.NewBoolVar`, not a measured constant, so BOTH
sides are solver-controlled. "after >= before - cap" is therefore satisfiable
two ways: protect the after-floor, which was the intent, or lower the
before-floor, which is cheaper. The solver took the cheaper route. Constraining
the skeleton to a worse before-floor buys slack on the whole inequality.

The third case, AE_AR_Choice, moved by +1, -1 and +3 across the three seeds --
inconsistent in sign, so noise.

## What is reverted, and what stays

Reverted: only the model constraint, back to its prior conditional form.
`tools/apply_w1_revert_joint_bound.py`, gate PASS at 18 suites.

Kept: the `floor_losses_from_breaks` metric, its cap, its gate, and its place
in the canonical surface. Those are reporting and gating rather than search
behaviour, they were verified independently, and they found real losses nobody
was measuring -- 3 intervals on AE_AR_Choice, 4 on AE_IT_B2B, 7 on
AE_IT_Choice. The visibility was the valuable half of W1. The constraint was
not.

## The proper fix, deliberately not done here

Bound the after-floor against the incumbent's **measured** before-floor -- a
constant -- so that degrading the skeleton cannot buy slack. That is a new
behavioural change and needs its own A/B with repeats before it goes near a
release tree. Logged rather than written.

## What this says about the method

The single-seed result was clean, internally consistent, parity-verified, and
wrong. Nothing about that run was defective; it simply could not distinguish a
one-interval effect from a one-interval noise floor, and the qualitative
unblocking made the wrong answer look like the strong one.

The decision rule was written down before the repeats ran, which is the only
reason the retraction is cheap now rather than expensive later.
