# Phase BH: smaller runs on the server

Owner, 2026-11-03: "the schedules are taking very very large size on server, can't we remove unnecessary files?"

## What a finished run kept (measured: GDI week, 29 associates, QUICK 300 s, run by the production runner)
28 MB in the run's results folder plus a 3.2 MB zip of the same: 14 MB `debug/CANDIDATE_POOL_CHECKPOINT.json`, 2.2 MB `debug/SKELETON_CHECKPOINTS.json`, raw outputs and a recovery
checkpoint in `debug/`, the engine's own three split packages in `packages/` (1.1 MB), 6 MB audit, 2.4 MB export manifest, the schedules (about 0.3 MB each). A long (DEEP,
OVERNIGHT) run searches more candidates, so its candidate pool is far larger. All of it stayed for 30 days, then the folder was deleted.

## Rule
When a run finishes as DONE or REVIEW, the website removes `debug/` and `packages/` from each case folder, makes the download zip again without them, and says so in the run's log.
Kept: the schedules, the outcome, the validator's verdict, the quality summary, the audit, the run status and identity, the input snapshot, the run log.
A run that failed or was stopped keeps everything (someone has to find out why). Runs that finished before this are slimmed once when the website starts.
Nothing the website shows or offers reads the removed folders (`debug` was already excluded wherever the website looks for a schedule or an outcome).

## Measured result
28 MB + 3.2 MB zip becomes 11 MB + 1.4 MB zip (about 60 % less) on a five-minute run; more on a long one.

## Not done
Dropping the 6 MB audit and the 2.4 MB export manifest (the website reads the audit; the manifest is the engine's record of its exports); a shorter keep time for run files
(`SCHEDULER_RUN_FILES_DAYS`, 30 to 60 days) is the owner's choice.
