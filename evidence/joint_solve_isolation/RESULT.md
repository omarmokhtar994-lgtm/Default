# Joint-solve isolation: result under the registered rule

Rule: `VERIFICATION_RULE.txt` (commit da3fc6c, registered before the
real-model and end-to-end checks). Verdict: **SHIP** (all five hold).
Engine sha256 2cfe3be0f51714bf7d0d69c37457dc66f71bc77b45e4f94b90aede4a43ed01eb.

| # | Check | Result |
|---|---|---|
| 1 | Toy models, deterministic (1 worker, deterministic time limit), isolated vs in process | identical status, objective, bound, every variable value, branches, conflicts, deterministic time (`iso_unit.py`; staged test `SameAnswerAsInProcess`) |
| 2 | Real models, isolation OFF vs ON | Chat: 4 solves identical, but all INFEASIBLE in presolve (0 branches), so weak (`CHAT_EQUIVALENCE_TRIVIAL.txt`). M2 (DEEP joint settings, 30 det-s per solve): 3 solves identical, 2 of them searched (1,156 and 16,482 branches, 52 conflicts, same bound 117); neither found a solution in its limit, so real-model solution vectors were compared only via the identical search trace (`M2_EQUIVALENCE.txt`). H1: could not be run in process at all - the in-process arm was OOM-killed at 13 GB twice (the bug itself). |
| 3 | Survival | Chat replay on an emulated 7 GB machine: child stopped at 233 MB free 35 s into attempt 2, parent returned normally, no further joint model started (`CHAT_SURVIVAL_REPLAY.txt`). H1 the same: build 4.5 GB in the parent, child stopped at 251 MB free, returned normally (`H1_SURVIVAL_REPLAY.txt`). The in-process replays died (MemoryError at 280 s; 13 GB kernel kills). |
| 4 | End to end, `RUN_UNIVERSAL_PRODUCTION.py --mode DEEP --time-limit 3600`, M2, 1 worker | validator PASS, 0 hard failures, metric parity PASS; `joint_solve_isolation`: 1 solve, ISOLATED, child exit 0, no memory stop (`M2_DEEP_3600_*`). A first run also passed validation but its audit could not show how the solve ran; the audit summary was added (commit 9473e99) and the run repeated. |
| 5 | `./run_tests.sh` | GATE PASS, 26 suites (16 isolation tests) |

Scores in the two end-to-end runs (98 and 95 after_target) differ by
run-to-run solver variation at 1 worker; their single joint solve was
INFEASIBLE in both and contributes no candidate either way.

What it does not cover: the Python-side model build runs in the parent and is
not isolated. H1's build was 4.5 GB and Chat's 3.8 GB, both within a 12.7 GB
Colab; a workbook whose build alone exceeds the machine is still exposed
(the existing pre-build headroom check, 2 GB or 15% free, is the only guard
there).

While these checks ran, VOICE_DEEP_9000 of the seeds-vs-time measurement was
OOM-killed with verification jobs on the machine; it is being rerun alone
(`evidence/DEEP_MODE_OOM.md`). From 20:20 UTC every verification process ran
at oom_score_adj 1000 and the kernel took those, not measurement runs.
