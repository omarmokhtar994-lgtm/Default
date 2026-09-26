# DEEP mode: Chat killed by the kernel at 13 GB inside joint refinement

Found by the seeds-vs-time measurement (evidence/seed_portfolio_ab), run
`CHAT_DEEP_9000`: runner `--mode DEEP` (14,400 s, joint refinement ON, as
shipped), 2 workers, Cricut Chat, seed 9000, current engine (pre-DNBS frozen
copy, identical joint-refinement code).

* Engine return code -9 after 7,500 s. Kernel log:
  `Memory cgroup out of memory: Killed process 8931 (python3) ...
  anon-rss:13043508kB` (13.0 GB resident).
* Last engine log line: `JOINT_CP_SAT operator=incumbent_replay
  stage=MAXIMIZE_AFTER_TARGET status=INFEASIBLE` - the joint-refinement phase.
* No schedule, no summary, no validation. A second run (a 1 h QUICK seed,
  about 1-2 GB) shared the 15 GB machine.

Why it matters:
* Joint refinement is OFF at QUICK for exactly this reason (8,197 MB -> 820 MB
  when disabled, coverage unchanged; 69 attempts, 0 improvements across 7
  workbooks, evidence/JOINT_REFINEMENT_NEVER_IMPROVES.md). DEEP and OVERNIGHT
  keep it ON and were never measured.
* The joint memory guard (`joint_memory_headroom`) checks available memory
  before building a model; this model then grew to 13 GB on its own.
* A standard Colab runtime has about 12.7 GB of RAM, so DEEP on Chat would be
  expected to be killed there as well.

Status: recorded, not changed. The Colab package defaults to QUICK (joint
refinement off). Recommendation: do not use DEEP/OVERNIGHT until joint
refinement is disabled or bounded at those depths; that is a behaviour change
and gets its own evidence (the remaining DEEP runs of this measurement show
whether Voice, NMG_SP and H1 hit the same limit).

## Second kill: VOICE_DEEP_9000 (2026-09-25 20:12 UTC) - contaminated, to be rerun

* Engine return code 247 (runner) after ~2.5 h; kernel log:
  `Memory cgroup out of memory: Killed process 14250 (python3) ...
  anon-rss:7062976kB` (7.0 GB resident, oom_score_adj 0).
* Last engine log lines: six `JOINT_CP_SAT ... status=UNKNOWN` attempts - again
  inside joint refinement.
* **Not a clean measurement.** While it ran, my own verification jobs for the
  memory fix (evidence/joint_solve_isolation) shared the machine: a Chat
  joint-refinement equivalence replay and an M2 DEEP end-to-end run (plus the
  1 h QUICK seed of the measurement itself). Voice at 7 GB alone would not
  have filled the machine, so the kill cannot be attributed to the engine
  alone. It is therefore not scored as "F fails Voice"; it is an interrupted
  run and, as for every interrupted run in these A/Bs, is rerun with the same
  seed (9000) once the queue is done, with nothing else on the machine.
* From 20:20 UTC all verification processes run with oom_score_adj 1000, so
  if memory runs out again the kernel takes those first, not a measurement run.

## Third data point: H1 joint refinement alone reaches 13 GB (2026-09-25 20:31 UTC)

A verification replay of SYNTH_H1's joint refinement (its saved 3,600 s
candidate pool, DEEP joint settings: 10 shift options per cell, 64 break
patterns per shift; 1 worker; joint solves in process, i.e. the shipped
behaviour) was killed by the kernel at **13.0 GB** resident
(`Killed process 20010 ... anon-rss:13015912kB ... oom_score_adj:1000`). It
was the kernel's chosen victim because every verification process runs at
oom_score_adj 1000; the measurement's NMG_SP DEEP run carried on. So the
joint-refinement memory problem is not specific to Cricut Chat: a 24x7
synthetic case hits it too. Evidence file for the fix:
evidence/joint_solve_isolation/.

## Fourth kill: H1_DEEP_9000 (2026-09-26 02:38 UTC) - genuine

* Runner `--mode DEEP` (14,400 s), SYNTH_H1_24x7_OVERNIGHT, 2 workers, seed
  9000, frozen pre-isolation engine. Killed after ~2.5 h:
  `Memory cgroup out of memory: Killed process 28978 (python3) ...
  anon-rss:13935856kB` (13.9 GB resident, oom_score_adj 0).
* Last engine log line: `JOINT_CP_SAT operator=incumbent_replay ...
  status=INFEASIBLE` - the next joint model is the one that grew.
* Nothing else of mine was running (the Voice rerun waiter was asleep; the
  measurement's 3,600 s queue had finished at 20:30). This is the engine
  alone: under the registered rule, F (one DEEP run) fails H1.
* The engine shipped since (8506631, joint-solve isolation) replays this
  exact situation and returns normally (evidence/joint_solve_isolation/
  H1_SURVIVAL_REPLAY.txt); the measurement deliberately keeps the frozen
  engine so both arms of the A/B use the same code.
