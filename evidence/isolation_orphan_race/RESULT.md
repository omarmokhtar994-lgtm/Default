# The 1-in-24 isolation-suite error: an orphan race, fixed

**Open item from df3715d.** During F-16, 1 of 24 side-by-side runs of
`test_rc9_2_19_joint_solve_isolation` errored, and its log was overwritten.

## Caught (2026-10-03)

The isolation suite ran 100 times in pairs: a repo copy and a package copy side
by side, with every log kept. Results are in `SIDE_BY_SIDE_ROUNDS.txt`.

| round | copy | failure | engine | cause |
|---|---|---|---|---|
| 25 | repo | `test_killing_the_engine_kills_its_solve`: "orphaned solve still running" | old | the race below |
| 92 | package | same as round 25 | old | the race below |
| 43 | repo | `test_joint_refinement_solves_are_isolated` | - | I edited the engine file while that round was running, and the test reads source by line number. Not a defect. |

## Cause

`isolated_cp_solve` forks a child for each isolated CP-SAT solve. The child is
meant to die with its parent through `PR_SET_PDEATHSIG`, but it armed that signal
only after disabling gc and writing `oom_score_adj`. If the parent is killed
between `fork()` and `prctl()`, the child is already reparented, gets no signal,
and runs on as an orphan until its own time limit. The test kills the parent as
soon as the child appears, so it lands in that window now and then. In
production the same thing happens to an engine killed by a timeout or interrupt
at that instant.

## Fix (engine `_child_prepare_for_isolated_solve`)

The child arms the death signal first. It then compares `getppid()` with the
parent pid recorded before the fork, and exits at once (code 73) if the parent
is already gone.

## Evidence

- **Deterministic test.**
  `test_a_parent_killed_before_the_signal_is_armed_leaves_no_orphan` holds the
  child for 1 s before arming, so the parent is always killed inside the window.
  - Old engine: fails (orphan left running).
  - Fixed engine: passes, 5 of 5.
- **Re-check test.** `test_a_child_whose_parent_is_already_gone_exits_at_once`
  checks the re-check directly.
- **Stress (`STRESS_150.txt`).** 150 runs of the kill test on loaded cores:
  - old engine: 1 failure;
  - fixed engine: 0.
- **Side by side.** About 57 rounds on the fixed engine, with 0 failures.

There is no schedule change, because joint refinement, the main user of isolated
solves, is off by default. The engine sha256 is now `8d148627...`.
