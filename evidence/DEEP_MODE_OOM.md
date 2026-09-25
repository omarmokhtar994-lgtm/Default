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
