# Colab two-seed portfolio ended in 0.6 s with no schedule

## Report

A Colab run of a workbook named `AE_IT_B2B.xlsx` (QUICK, SEEDS 0, so 2 seeds) ended at once:

    DONE AE_IT_B2B exit=1 wall=0.6s after-breaks winner seed=None

## Root cause (reproduced 2026-10-03)

Every engine run takes a lock, `RUN_LOCK.json`, in its case folder. A new run
refused when the lock's pid was alive (`os.kill(pid, 0)`).

On Colab the results live on Drive and outlive the VM. A run interrupted there
leaves its seed locks behind (`RESULTS_ROOT/_seeds/<WORKBOOK>/seeds/<WORKBOOK>_S900x/`).
In the next VM, small pid numbers belong to other live processes, so each seed
raised `RuntimeError: Case is already running` within a fraction of a second.
RUN_PORTFOLIO then reported no validated seed and exited 1. Packages before
01d4d06 did not show the seed logs, so the reason was invisible.

**Reproduction.** Python 3.12.3 (as on Colab), the package unzipped fresh, the
notebook's command line (`--mode QUICK --stage FULL_SCHEDULE --seeds 2 --input
"<Drive>/My Schedules/AE_IT_B2B.xlsx" --resume`), and a stale lock naming pid 1
in each seed folder:

    START AE_IT_B2B  seeds=2 (base 9000)  side-by-side=2  workers/seed=2  budget/seed=3600s
      [portfolio] seed 9001 finished rc=1 in 0s
      [portfolio] seed 9000 finished rc=1 in 0s
      [portfolio] no seed produced a validated final schedule
    DONE  AE_IT_B2B  exit=1  wall=0.4s  after-breaks winner seed=None
    (seed log) RuntimeError: Case is already running: .../AE_IT_B2B_S9000 (pid=1).

**Ruled out.** Python 3.12 itself: with no stale lock the same command started
both seeds normally.

## Fix (`engine/RUN_UNIVERSAL_PRODUCTION.py`)

- The lock records this machine's boot id, the host name and the pid's kernel start time.
- A lock blocks a new run only in two cases:
  - it was written on this machine, and that pid is alive with the same start time;
  - otherwise (another VM sharing the Drive folder, or a lock written before this
    fix), its `RUN_HEARTBEAT.json` is under 5 minutes old. The heartbeat is
    rewritten every 30 s while a run is alive.
- Any other lock is stale and is cleared.
- The refusal message now names the host, and says to delete `RUN_LOCK.json`
  if no run is active.

**Checked after the fix.** The same replay with the same stale locks: both seeds
cleared them, wrote new locks and started solving.

**Tests.** Five cases in `tests_staged/test_rc9_2_25_input_vocabulary.py::AStaleRunLockNeverBlocksANewRun`:
- a stale lock from another session is cleared;
- another machine's lock is cleared once its heartbeat stops;
- a live run elsewhere keeps its lock;
- a live run on this machine keeps its lock;
- a reused pid on this machine is cleared.

Four of the five fail on the old code.
