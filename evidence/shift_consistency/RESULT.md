# Shift consistency polish: result against the registered rule

> **Correction, 2026-10-04 (audit F-35).** The figures below were read from the engine audit, which
> described the polished schedule. The published workbook was never the polished one: the workbook
> writer used the pre-polish export (checked on six runs, `evidence/production_readiness_audit/phase_c/
> F35_POLISH_NOT_PUBLISHED.txt`). The improvement measured here was therefore never delivered. The polish
> is withheld until it is validated end to end; published schedules are unchanged.


The rule was written before the measurement: `RULE.txt`, commit ef4a540.
**Verdict: all four items pass, so the polish is on by default.** The workbook row
`Shift Consistency Polish = No` or `--no-shift-consistency-polish` turns it off.

## What it does

The polish runs after the final schedule is chosen.

1. **Re-deal.** On each day, associates with the same language and shift length
   can hold that day's shifts in any order without changing coverage. The whole
   week is re-dealt in two steps:
   - a pairwise-swap pass;
   - a CP-SAT model (4 workers, interleaved and deterministic, hinted with the
     current deal), which also enforces the hard rules and the employee guards.
2. **One-hour moves.** A start moves by 1 h only when the engine's full metrics
   show nothing got worse.

Hard rules are enforced on every move:
- legal shift, demand-fit guard, language hours, required-language and exclusive
  coverage-split windows;
- rest (from last Saturday, between days, across the week wrap), maximum
  different shifts, shift length;
- fixed requests and nesting groups are never moved.

After the polish:
- the result must pass `validate_schedule` with the same release class;
- no guarded metric may be worse (the DNBS guard, after_target, and every
  before/after tier);
- preference matches, start-swing violations and the late, overnight and weekend
  load spreads may not get worse.

Otherwise the original schedule is kept. The polish only uses time the run has
left, keeping 30 s for the export, which measured about 5 s.

## (a) The 11 published schedules with a saved candidate pool

Raw rows are in `SAVED_SCHEDULES.json`.

| schedule | start movement (h) | distinct start times | target / floor | hard failures | time (s) |
|---|---|---|---|---|---|
| Voice, corrected sheet, seed 9000 | 76 -> 50 | 62 -> 58 | 242/251 unchanged | 0 | 10.0 |
| Voice, corrected sheet, seed 9001 | 58 -> 49 | 61 -> 61 | 243/252 unchanged | 0 | 10.1 |
| Voice, final sheet | 71 -> 53 | 61 -> 60 | 247/252 unchanged | 0 | 8.4 |
| Voice, ALL_ROWS test | 61 -> 49 | 60 -> 60 | 245/254 unchanged | 0 | 8.3 |
| Chat (F-16 DEEP) | 154 -> 119 | 68 -> 66 | 166/237 unchanged | 0 | 34.5 |
| H1 (F-16 DEEP) | 187 -> 174 | 84 -> 84 | 143/167 unchanged | 0 | 52.6 |
| AE_IT 9004, slice 240 | 35 -> 29 | 21 -> 21 | 69/85 unchanged | 0 | 15.9 |
| AE_IT 9004, no cap | 40 -> 34 | 23 -> 23 | 78/88 unchanged | 0 | 4.1 |
| AE_IT 9002, slice 240 | 16 -> 13 | 19 -> 19 | 72/88 unchanged | 0 | 0.8 |
| AE_IT 9002, no cap | 10 -> 8 | 16 -> 16 | 76/89 unchanged | 0 | 1.0 |
| AE_IT 9002 rerun | 20 -> 20 (no change) | 21 -> 21 | 71/87 unchanged | 0 | 0.4 |

- **Release class:** "compliant" before and after, in every case.
- **Guarded metrics:** none worse in any case.
- **One-hour moves:** one was kept (Voice seed 9001). Elsewhere every candidate
  move cost at least one target interval, so the guard refused it, as specified.

## (b) End to end, polish on

QUICK, 1200 s, 2 workers, seed 9000.

| case | start movement (h) | distinct starts | one start all week | validator | parity | input cross-checks | elapsed / budget |
|---|---|---|---|---|---|---|---|
| Chat | 175 -> 120 | 70 -> 69 | 1 -> 1 | PASS, 0 hard | PASS | all PASS | 1151 / 1200 s |
| Voice (corrected sheet, ALL_ROWS) | 75 -> 54 | 60 -> 58 | 14 -> 14 | PASS, 0 hard | PASS | all PASS | 1120 / 1200 s |
| AE_IT_B2B | 47 -> 14 | 23 -> 19 | 3 -> 7 | PASS, 0 hard | PASS | all PASS | 1109 / 1200 s |

**First attempt.** The first end-to-end attempt reserved 90 s for the export and
skipped the polish for lack of time: 92 s were left. Cutting the reserve to 30 s
fixed it. The export measured about 5 s.

## Rule items

1. **No guarded metric worse:** PASS, in all 14 cases.
2. **Hard failures, release class, validator:** PASS. 0 hard failures, release
   class unchanged, and the independent validator PASS with parity in (b).
3. **Improvement:** PASS. 13 of 14 improved; 1 had nothing to gain; none got worse.
4. **Time:** PASS. At most 52.6 s, with 3 s of the 60 s kept for the final
   checks. Every run ended inside its budget.
