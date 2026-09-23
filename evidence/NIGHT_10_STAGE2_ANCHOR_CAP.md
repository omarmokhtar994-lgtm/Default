# Giving Stage-2 back the attempt the anchor was eating

## The defect (NIGHT_09)

At the production QUICK budget the adaptive break search runs **zero** of its
planned attempts on most workbooks. On `C_CHAT_1800_w4`:

```json
{"cp_status": "STOPPED_INSUFFICIENT_BREAK_SEARCH_DEPTH",
 "attempts_completed": 0, "attempts_planned": 168,
 "proposed_slice_sec": 139.851, "minimum_slice_sec": 180.0}
```

| | seconds |
|---|---|
| `break_search` allocated | 452 |
| gone before the phase began (Stage-1 overrun; deadlines are absolute) | 175 |
| left when the anchor started | 277.008 |
| granted to `guaranteed_stage2_anchor` | 135.0 |
| left for the adaptive loop | 139.851 |
| `BREAK_MIN_MEANINGFUL_SLICE_SEC` | 180.0 |

Short by 40 seconds. The anchor that spent the 135s returned
`"status": "UNKNOWN"`, `"hard_clean": false`, `"candidate_class": "rejected"`.

Census over 117 audits: at 1800s, **15 of 22 runs** place breaks without ever
running the break search.

## Why the floor is not the thing to change

B-10 was retracted for exactly this reason. The recorded curve is
`90s -> 160, 120s -> 160, 150s -> 160, 180s -> 162, 450s -> 162`. A shorter
attempt does not fail, it ships a materially worse schedule. 180 is right.

The defect is upstream: the phase never *has* 180 seconds to offer.

## The change

`stage2_anchor_slice_seconds` now leaves `BREAK_MIN_MEANINGFUL_SLICE_SEC`
behind whenever the phase can pay for both the anchor's own minimum and one
real attempt:

```python
if remaining >= STAGE2_ANCHOR_MIN_SLICE_SEC + BREAK_MIN_MEANINGFUL_SLICE_SEC:
    granted = min(granted, remaining - BREAK_MIN_MEANINGFUL_SLICE_SEC)
```

| case | remaining | reserved | granted before | granted after | left for the search |
|---|---|---|---|---|---|
| Chat 1800 (the defect) | 277.008 | 135 | 135.0 | **97.0** | **180.0** |
| Chat 3600 (already fine) | 863.325 | 240 | 240.0 | 240.0 | 623.0 |
| small phase | 100 | 135 | 80.0 | 80.0 | inert |
| exhausted phase | 0 | 135 | 0.0 | 0.0 | inert |

It converts 38 seconds of an anchor that returned nothing into one attempt
that runs the real coverage objective. Where the phase is already comfortable,
or too small to fund both, it changes nothing.

## Tests

Five, mutation-checked: deleting the two-line cap fails them, and the engine
was restored byte-identical afterwards. They pin the recorded Chat case, the
untouched roomy case, that the cap never pushes the anchor below its own
minimum, that it is inert when the phase cannot pay for both, and that the
grant never exceeds the phase.

## Honest limits

* This funds **one** attempt at 1800s. The +27 intervals seen at 3600s came
  from the *second and third* attempts (`target90_restore_champion` at 164).
  Reaching that at QUICK needs roughly 540s of `break_search` against 452
  allocated, which is a budget-ladder change and is **not** made here.
* On Cricut Chat the first planned adaptive task is `target_floor_pareto_master`,
  which at 3600s returned 135 -- below the 159 that run shipped. Candidates are
  pooled and ranked, so a weaker candidate cannot displace a stronger one, but
  one recovered attempt is not automatically a better final number.
* The 175s that `break_search` loses before it starts is untouched.

## Result: the cap as written does NOT achieve its goal

**AE_AR_B2B** (1800s, 1 worker, seed 9000) — the cap never bound. The phase had
~400s left, so `min(135, 401 - 180)` is still 135. Both arms granted 135.0s,
ran 1 adaptive attempt, and produced 166/165/168/167. Safe, and uninformative.

**Cricut Chat** (1800s, 4 workers, seed 9000) — the case it was built for:

| | before the cap | with the cap |
|---|---|---|
| phase remaining at the anchor | 277.0s | 307.4s |
| anchor granted | 135.0s | **127.4s** (capped) |
| slice the adaptive loop was offered | 139.9s | **177.0s** |
| real adaptive attempts | 0 of 168 | **0 of 168** |

The cap bound exactly as coded and left 180.0s on paper. The loop saw 177.0s.
**Still zero attempts.** It left exactly the floor with no margin, and the
seconds between the anchor finishing and the loop sizing its slice were not
free. (Coverage is not comparable across these two runs: four workers are
nondeterministic and picked a different skeleton, 196 vs 169 before-target.
That is why this was judged on attempts, not on a coverage number.)

**Measuring the hand-off gap.** In every run where the loop stopped at zero
attempts straight after the anchor, the loop's proposed slice *is* the time
left, so the gap can be measured exactly. Across 61 runs: anchor overrun of its
own grant 0.054s here; the rest is bookkeeping — scoring the anchor, checkpoint
and audit writes, planning the attempts.

| | seconds |
|---|---|
| minimum | 0.62 |
| median | 1.77 |
| 90th percentile | 2.58 |
| maximum | 9.82 |

**What happens next.** The zero-margin cap is withdrawn. A margin version —
leaving `180 + 30` seconds, three times the worst observed gap — is being tested
deterministically against the uncapped engine in the same batch as F-1 (see
`evidence/formula_audit/FINDINGS.md`). It ships only if it helps.
