# RC9.2.1 — DEEP 14,400 s as resumable segments (day-2 SAMPLE)

The second package. Run it **only where the 2,700 s pass says a full budget is
needed**, or on the scenarios you care most about. One scenario per Colab
instance.

## Why this exists

DEEP's design budget is 14,400 s. Only at roughly that budget does the engine
explore its whole 15-profile skeleton portfolio:

| budget | Stage-1 profiles explored |
|---|---|
| 900 s | 1 of 15 |
| 2,700 s | 3 of 15 |
| 5,400 s | 6 of 15 |
| **14,400 s** | **15 of 15** |

## Why segments rather than one 4-hour run

A four-hour unattended run does not survive a Colab disconnect. It did not
survive in our own container either: two attempts were killed at 10 and 40
minutes. So the budget is reached as **6 segments of 2,400 s**, each resuming the
previous one from the engine's own checkpoints. A lost segment costs one segment.

## Resume only began working with this build

`--resume` was broken in **every** RC9.2.1 build before this package. `run_id` is
hashed from `run_parameters`, which contained an absolute wall-clock timestamp,
so the recomputed identity never matched the checkpoint and resume always raised
*"Resume refused"*. Measured: two identical runs produced `parameters_sha256`
`dc5d8541…` vs `d833ecb1…` with input, contract and engine hashes all identical.

That is finding **A32**, fixed in the engine shipped here. Two consequences of
the old behaviour are worth knowing:

- checkpoint/resume never worked at all, and
- **run identity was not reproducible**, which quietly defeated the
  exact-engine-identity release gate.

Check `SCENARIOS.json` → `engine_sha256` to confirm you are running the fixed
engine. It must match the one in the 2,700 s package.

## Usage

```bash
python runners/rc921_deep_segmented.py --package-root . --only CRICUT_VOICE
```

or open `runners/RC921_DEEP_Colab_B_WITH_DRIVE.ipynb` (**recommended** — Drive
keeps the checkpoints, so a disconnect costs nothing).

After a disconnect, set `CONTINUE_FROM` to the segment that did not finish and
re-run. `<SCENARIO>_SEGMENT_LEDGER.json` records which segments ran and how many
skeletons were banked after each.

## Suggested day-2 order

1. **CRICUT_VOICE** — the one scenario that failed gate 2/9 against RC9.1
   (target −14, floor −13 at 900 s). The question this run answers: was that a
   real regression, or starvation? Its own global best skeleton was 247 against
   RC9.1's 256, so the gap is in Stage-1 search, not break placement.
2. **CRICUT_CHAT** — at 2,700 s its retention loss went 15 → 0 but Gate 5 flipped
   to FAIL (break loss 8 → 38, `after_target` 164 → 158). Does a full budget
   resolve that trade-off or deepen it?
3. Anything the 2,700 s pass flagged.

## What to send back

The whole results directory: each `<SCENARIO>/`, every
`<SCENARIO>_segment*.log`, `<SCENARIO>_SEGMENT_LEDGER.json`, and
`_gate_report/`.

## A caution on reading the results

A segmented run is **not** identical to one uninterrupted 14,400 s run. Resume
skips proven work, but each segment re-plans its phase budget from its own start,
so time is not distributed exactly as a single run would distribute it. It is a
close and honest approximation, and it is the only way to reach this budget on
Colab — but do not present a segmented result as a single-run result.
