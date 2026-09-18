# B-13: the joint refinement bounds can be satisfied by degrading the schedule

Found while building the corrected version of the bound reverted earlier today.
This one is **pre-existing and live in production**, and it is more serious than
the change that was reverted.

## The defect

Two bounds sit next to each other in the joint refinement model:

    if before_target_hits and target_hits:                       # UNCONDITIONAL
        model.Add(sum(target_hits) >= sum(before_target_hits)
                  - parsed.quality_max_target_losses_from_breaks)

    if ... == "fail" and floor_hits and before_floor_hits:       # conditional
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - ...)

Both sides of each inequality are solver-controlled:

    before_floor_hit  = model.NewBoolVar(f"joint_before_floor_hit_{d}_{i}")
    before_target_hit = model.NewBoolVar(f"joint_before_target_hit_{d}_{i}")

So `after >= before - cap` has two solutions. Protect the after-state, which is
the intent. Or **lower the before-state**, which is cheaper and buys slack on
the whole inequality. The solver is free to choose the second.

## This was already measured

W1 made the FLOOR bound unconditional, and three paired seeds showed the
mechanism operating:

    AE_IT_B2B    patched before_floor    unpatched before_floor
      seed 9000        91                       91
      seed 9001        91                       98
      seed 9002        91                       97

Pinned at exactly 91 whenever the bound was active, free to range 91-98 when it
was not, with a worse after-floor every time. That change was reverted.

**The target bound was never reverted, because it was never added.** It is
original code, it is unconditional, and it carries the identical flaw. W1 did
not invent this pattern -- it copied the target bound beside it.

## The engine already contains the correct pattern

Twelve lines below, in the same function:

    if min_after_target is not None and target_hits:
        model.Add(sum(target_hits) >= max(0, int(min_after_target)))
    if min_after_floor is not None and floor_hits:
        model.Add(sum(floor_hits) >= ...)

`min_after_target` and `min_after_floor` are **integers passed by the caller**.
Bounding against a measured constant cannot be satisfied by degrading anything,
because there is nothing on the right-hand side for the solver to move.

So the correct mechanism exists. It is simply not used everywhere:

    line 14998-14999   min_after_target=replay_target_min     <- passed
    line 15119-15120   min_after_target=None                  <- not passed
    line 15227-15228   min_after_target=None                  <- not passed
    line 15407-15408   min_after_target=min_after_target      <- passed through

In the paths that pass `None`, the only active protection is the bound that can
be satisfied by making the schedule worse.

## The fix, specified but deliberately not applied today

1. Delete both variable-versus-variable bounds.
2. In the call sites that currently pass `None`, compute
   `min_after_floor = measured_before_floor - floor_cap` and
   `min_after_target = measured_before_target - target_cap` from the incumbent.
   `anchor_candidates` is already a parameter, so the measured counts are in
   scope; nothing needs new plumbing.
3. A/B with repeats before it goes near a release tree.

It is not applied now for the reason today demonstrated: a behavioural change
to the search, written at the end of a long session and measured on one seed,
is exactly how the reverted regression got in. This one deserves its own run.

## Why this matters more than the reverted change

The reverted floor bound was off by default -- it only fired when the target
gate was in `fail` mode, which is not the default. The target bound has no such
guard. It is active on every joint refinement, in every run, today.

Whether it actually degrades production schedules is unmeasured. The mechanism
is proven; the magnitude is not. That is the run to do next.

---

# Structural probe: the gameable bound is equivalent to no bound

## Why the method changed

The end-to-end A/B could not be completed. Container restarts in this session
moved from roughly hourly to every 10-30 minutes (01:19, 02:33, 02:43, 03:12),
killing four runs simultaneously 5.5 minutes into a wave. Not memory -- 15 GB
free; the kernel log shows `idle-reclaim` recycling the container. At that
cadence no multi-minute solve is reliable.

B-13's claim is structural rather than statistical: it is about what the
constraint PERMITS, which is a property of the formulation and does not depend
on budget, seed or workbook. That can be asked of CP-SAT directly, in seconds.

## The probe and its result

`tools/b13_structural_probe.py` rebuilds the engine's exact shape -- before and
after coverage bools tied to a threshold, breaks only removing staff -- and
compares three cases:

    no bound at all             before_hits =  0   after_hits =  0
    GAMEABLE  after >= before-cap  before_hits =  0   after_hits =  0
    CONSTANT  after >= 10-cap      before_hits =  8   after_hits =  8

**The gameable form produces exactly the same answer as having no constraint.**
It is not a weak protection; it is no protection. Whenever anything would lower
the before-state, the bound moves with it and never binds. The constant form,
whose right-hand side the solver cannot move, holds after_hits at 8.

## What this does and does not establish

It establishes that the constraint cannot protect the after-state, because a
solution that degrades before satisfies it for free. That is a property of the
formulation and is now demonstrated rather than argued.

It does **not** establish that the engine's full objective always chooses to
degrade. The probe's objective pushes staffing down; the engine's rewards
coverage, so it will not drive before to zero. What the probe proves is that
the bound contributes nothing when the objective does lean that way.

For whether it leans that way in practice, the real-engine evidence already
exists from the three paired seeds run earlier:

    AE_IT_B2B    with the bound active     before_floor pinned at 91, 91, 91
                 with the bound inactive   before_floor 91, 98, 97

Pinned whenever the constraint was on, free to range when it was off, with a
worse after-floor every time. Mechanism proven structurally here; occurrence
observed there.

## Status

The fix (`tools/apply_b13_constant_joint_bounds.py`, gate PASS at 18 suites)
replaces both bounds with the engine's own constant-bound pattern. It is NOT
applied to the release tree: it changes search behaviour, and the evidence for
the defect is now strong while the evidence that the fix is neutral-or-better on
real schedules is not. That still wants an end-to-end A/B in an environment
where runs survive.
