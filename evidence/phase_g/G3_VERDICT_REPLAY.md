# G3: stored runs replayed under the release-verdict policy (2026-10-07)

What: `tools/release_gate_report.py` (Phase F verdict + Phase G no-schedule
reason) on every stored run under `evidence/` that has a summary: 157 runs in
11 families (`raw_runs/*`, `aeit_floor_cause`, `f16_single_run_deep`,
`language_hours`, `shift_consistency`). No solves; nothing in `evidence/` was
changed. Per-run rows: `G3_VERDICT_REPLAY.json`.

Method note: stored runs keep `INDEPENDENT_VALIDATION.json` gzipped. A literal
replay therefore read all 157 as "validation not run". The replay was made
from a scratch copy with the `.gz` files decompressed (151 validation files
recovered); the 6 runs without one are genuine (below). Runs span engines from
before the verdict code; each is read as stored.

Policy (Phase F safe default, owner has not named mandatory gates):
NOT_RELEASABLE = validation failed or never ran; REVIEW_REQUIRED = gate 4 or
gate 5 FAIL; otherwise RELEASABLE.

## Per program

| program | runs | releasable | review required | not releasable | of which gate 5 (break loss) FAIL |
|---|---|---|---|---|---|
| AE AR B2B | 19 | 19 | 0 | 0 | 0 |
| AE IT B2B | 6 | 0 | 6 | 0 | 6 |
| Cricut Chat | 24 | 1 | 22 | 1 | 21 |
| Cricut Voice | 27 | 24 | 1 | 2 | 1 |
| NMG SP | 22 | 22 | 0 | 0 | 0 |
| synthetic H1 24x7 | 21 | 0 | 18 | 3 | 16 |
| synthetic H3 | 19 | 0 | 19 | 0 | 19 |
| synthetic M2 | 19 | 2 | 17 | 0 | 16 |

Totals: 68 releasable, 83 review required, 6 not releasable.

Phase F runs (10, not under `evidence/`; scored at the time, see
`evidence/phase_f/F_MEASUREMENTS.md`): Chat 4 review required (gate 5) plus
the :30 arm; Voice control releasable; NMG EN+SP control and AE IT B2B both
arms review required. The three :30 arms read NOT_RELEASABLE as run only
because of the validator defect fixed in 8c6e48f; re-validated they read as
their controls do.

## Reading

* Gate 5 (break-loss regression: more than 5% of active intervals lost at
  target, or 3% at floor, to breaks) is the source of 79 of the 83
  REVIEW_REQUIRED verdicts. It never fires on AE AR B2B, NMG SP or (but once)
  Voice; it fires on every AE IT B2B run and 21 of 24 Chat runs. If the owner
  made gate 5 blocking, Chat and AE IT B2B would almost never release under
  their current break rules; as a review flag it marks exactly the programs
  where breaks cost the most (Phase F: 15-19 target intervals lost to breaks).
* Gate 4's protected tier is not configured anywhere (145 of 157 list it as
  not evaluated); gate 5's absolute standard is configured for none of the
  72 runs where it applies. These are listed, never counted as passes.
* The 6 NOT_RELEASABLE runs: one proven hard-rule contradiction
  (`language_hours/VOICE_CONFLICT_MSG2`, a deliberate conflict test, named as
  "hard rules contradict each other (proven)"), and five runs killed before
  any outcome was written (`seed_portfolio_ab` CHAT_DEEP_9000, H1_DEEP_9000,
  VOICE_DEEP_9000_OOM_KILLED_CONTAMINATED; `dnbs_e2e_3600` H1_CUR_9000,
  H1_NEW_9000), named "reason not recorded". No stored run has a validator
  hard-rule failure.

Input for owner decision 1 (which checks block a release): validation stays
blocking; making gate 5 blocking would stop most Chat and every AE IT B2B
schedule today; gate 4 cannot block anything until a protected minimum is
configured per program.
