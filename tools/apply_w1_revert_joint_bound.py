#!/usr/bin/env python3
"""Revert W1's unconditional joint-refinement floor bound.

WHY. W1 changed this, in the joint-refinement model:

    # before
    if getattr(parsed, "target_loss_gate_mode", "warn") == "fail" and floor_hits and before_floor_hits:
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - <TARGET budget>)
    # after
    if floor_hits and before_floor_hits:
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - <FLOOR budget>)

The intent was sound: floor losses were unbounded here while target losses were
hard-capped. But BOTH SIDES of that inequality are solver-controlled --
`before_floor_hit` is a `model.NewBoolVar`, not a measured constant. So the
constraint

    after_floor_hits >= before_floor_hits - cap

can be satisfied either by protecting the after-floor (the intent) or by
DEGRADING the before-floor (cheaper). The solver took the cheaper route.

EVIDENCE. Three seeds, both arms, paired under identical machine conditions:

    AE_IT_B2B    post before_floor   pre before_floor    after-floor delta
      seed 9000        91                  91                  -1
      seed 9001        91                  98                  -4
      seed 9002        91                  97                  -2

The post arm's before_floor is pinned at exactly 91 on every seed while the pre
arm ranges 91-98, and the after-floor is worse on all three. That is the
perverse incentive showing up in production data.

The headline result that appeared to justify the change did not survive either.
AE_IT_Choice looked unblocked by the applied stack at seed 9000. Across seeds:

      seed 9000   post=schedule   pre=BLOCKED
      seed 9001   post=schedule   pre=schedule     <- pre unblocks too
      seed 9002   post=BLOCKED    pre=BLOCKED

Blocked-vs-unblocked tracks the SEED, not the code. The apparent unblocking was
a lucky draw on one seed.

WHAT THIS REVERTS AND WHAT IT KEEPS. Only the model constraint goes back to its
prior form. Everything else in W1 stays: the floor_losses_from_breaks metric,
its cap, its gate, and its place in the canonical surface. Those are reporting
and gating, they were separately verified, and they found real losses nobody
was measuring (7 intervals on AE_IT_Choice).

THE PROPER FIX, NOT DONE HERE. Bound the after-floor against the incumbent's
MEASURED before-floor -- a constant -- so degrading the skeleton cannot buy
slack. That is a new behavioural change and needs its own A/B with repeats
before it goes anywhere near a release tree.

Usage: apply_w1_revert_joint_bound.py <engine_file> [--dry-run]
"""
import sys

APPLIED = '''    # W1: this used the TARGET budget, and only when the TARGET gate was in
    # fail mode -- so by default floor losses were unbounded here while target
    # losses were hard-capped. It now uses the floor budget, unconditionally,
    # exactly as the target bound above does.
    if floor_hits and before_floor_hits:
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - parsed.quality_max_floor_losses_from_breaks)
'''

REVERTED = '''    # W1 made this bound unconditional and switched it to the floor budget. Three
    # paired seeds showed that backfiring: both sides are solver-controlled, so
    # "after >= before - cap" is satisfiable by lowering BEFORE, and the solver
    # did exactly that -- AE_IT_B2B's before_floor pinned at 91 on every seed
    # against 91/98/97 unconstrained, with a worse after-floor each time. Bound
    # the after-floor against a MEASURED constant before reinstating this.
    if getattr(parsed, "target_loss_gate_mode", "warn") == "fail" and floor_hits and before_floor_hits:
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - getattr(parsed, "quality_max_target_losses_from_breaks", 999999))
'''


def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    src = open(path).read()
    if APPLIED not in src:
        if REVERTED.split("\n")[-2] in src:
            print("  already reverted; nothing to do")
            return
        sys.exit("ABORT: the W1 bound is not in the expected form; refusing to guess")
    out = src.replace(APPLIED, REVERTED, 1)
    import ast
    ast.parse(out)
    print("reverted the joint-refinement floor bound to its conditional form")
    print("  W1's metric, cap, gate and canonical-surface entry are untouched")
    if dry:
        print("  --dry-run: nothing written"); return
    open(path, "w").write(out)
    print("  patched: %s" % path)


if __name__ == "__main__":
    main()
