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

---

# The end-to-end A/B was attempted properly, and cannot work here

## A technique that does work

Background processes are collected a few minutes after the assistant's turn
ends. But a process running in the FOREGROUND of a tool call survives, because
the turn stays alive for its duration. The ceiling is the 600-second tool
timeout.

Measured: a pair of runs at a 360-second budget, both arms concurrent,
completed in 351 seconds wall with `rc=0` on both. A pair at 600 seconds
completed in 551 seconds. **Runs of up to about 600 seconds are reliable here.**
That is worth knowing for any future work in this environment.

## Why it still does not settle B-13

B-13 lives in joint refinement, and joint refinement is hard-gated off below a
600-second total budget:

     total   stage1  break   joint_refinement
       360     111    154       0
       480     111    154       0
       540     136    189       0
       600      76    107     151

Lowering `joint_refinement_reserve_sec` does not move the gate -- tested at 900,
400, 200, 120 and 60, all zero below 600.

At exactly 600 seconds the real run allocated joint refinement 53 seconds, and
both arms produced:

    JOINT_CP_SAT operator=incumbent_replay  status=INFEASIBLE  elapsed=0.62s
    JOINT_CP_SAT operator=skill_guard       status=UNKNOWN     elapsed=5.47s

No solution in either arm. The bound cannot influence an outcome that does not
exist, so the comparison is vacuous -- identical results in both arms, for a
reason that has nothing to do with the fix.

The 3600-second runs earlier in this work allocated joint refinement 734 seconds
and exercised many operators. That is the regime where B-13 manifests, and a
3600-second run needs six times the tool ceiling.

## Conclusion

The requirement for applying the B-13 fix is now precise rather than vague. It
is not "more evidence" and not "a warm session". It is **a host that can run a
3600-second solve**, because below that the phase under test is either unfunded
or infeasible. CI, a workstation, or the Colab setup the authors' own baseline
used would all do.

Two identical-result pairs were produced along the way (360s and 600s budgets).
They are recorded here as showing nothing, deliberately: reporting them as
"no regression from B-13" would be false, because the phase B-13 changes never
ran.

## Chunked resume was tried too, and cannot work either

The engine supports `--resume` against a registry of completed work, so a
3600-second plan was attempted in 540-second chunks. Five chunks, 45 minutes of
real solving, both arms in every chunk.

**Resume genuinely works.** Stage-1 profiles carried across chunks:

    chunk 1   runnable=15
    chunk 2   runnable=12
    chunk 3   runnable=7
    chunk 4   runnable=2
    chunk 5   runnable=1

and the budget plan was the full 3600-second one -- `joint_refinement` allocated
734 seconds, not the 0 it gets below a 600-second total.

**But joint refinement was never reached: `JOINT_CP_SAT` lines = 0 in all five
chunks, in both arms.** The phase schedule explains why:

    phase                  allocated   starts at offset from PROCESS START
    preflight_probe             126s          0s
    conflict_refinement          73s        126s
    safe_incumbent              146s        199s
    stage1_search               824s        345s
    break_search               1138s       1169s
    joint_refinement            734s       2307s   <-- B-13 lives here
    coordinated_repair          205s       3041s
    finalization                120s       3480s

Resume preserves the WORK done, through the registry. It does not preserve the
PHASE SCHEDULE, which restarts at t=0 in every chunk. A 540-second chunk
therefore always dies inside `stage1_search`, and no number of chunks advances
the clock past offset 2307.

## Final answer on measuring B-13 end to end

It requires a single process that lives past 2307 seconds. This environment
caps a foreground process at the 600-second tool timeout and collects
background processes a few minutes after a turn ends. Both limits are below the
requirement, and neither is worked around by chunking, by resume, by session
activity, or by any scheduling of check-ins.

Three techniques were tried and measured rather than assumed: background with a
supervisor, foreground within the tool timeout, and chunked resume. The
foreground technique is the useful survivor -- it makes any run up to about 600
seconds reliable here -- and it is recorded above for future work.

B-13 itself remains proven by the structural probe and by the three paired seeds
measured earlier. What cannot be produced here is the end-to-end confirmation
that its FIX is neutral-or-better on real schedules, and that is the only thing
blocking its application.

## Fourth attempt: shrinking the work does not advance the clock

If phases finished early and handed back unspent time, cutting the work ahead of
joint refinement would let it start sooner. Tested with one skeleton profile
instead of fifteen and one break-objective mode instead of seven, both arms,
3600-second plan:

    JOINT_CP_SAT lines = 0, both arms, again

The phase schedule is DEADLINE-driven, not work-driven. `stage1_search` holds
its window to offset 1169 and `break_search` to 2307 whether or not there is
work left to do, so reducing the work changes what happens inside those windows
and not when the next phase begins.

That closes the last idea. Four techniques tried and measured, not assumed:

    background + supervisor   reaped minutes after each turn ends
    foreground in-call        works, reliable to ~600s, below the 2307s needed
    chunked --resume          resumes work, but the phase schedule restarts at 0
    reduced workload          phases are deadline-driven, so the clock is unmoved

All four fail for one reason: joint refinement begins at offset 2307 seconds and
nothing here survives that long in a single process.
