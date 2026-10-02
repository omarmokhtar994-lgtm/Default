# F-16: single long DEEP run, end to end

**Goal:** confirm that `--mode DEEP --single-run` (one 14,400 s run) completes and
produces a validated schedule. Earlier single DEEP runs on these two cases were
killed at 13-14 GB.

## How it was run

- **Date:** 2026-10-02, 19:10 to 23:13 UTC.
- **Package:** `dist/RC9_2_2_PRODUCTION_PACKAGE.zip`, sha256 `4071c941…` (first build of this branch; the shipped rebuild adds only this evidence and the guidance text), built from this
  branch and unzipped. The runner ran the package's own offline gate first; it passed
  (48 suites, 1244 tests, 2 skipped).
- **Engine:** L6.3.2.8-RC9.2.2-PRODUCTION-HARDENED-RC6, sha256 `251cf35a…`.
- **Machine:** one container with 4 vCPU and 15 GB RAM. Both runs ran at the same time,
  each with the runner's default of 4 workers, so the CPU was oversubscribed 2x.
- **Commands:**

      rc922_runner.py --only CRICUT_CHAT --mode DEEP --single-run --overwrite
      rc922_runner.py --input SYNTH_H1_24x7_OVERNIGHT.xlsx --mode DEEP --single-run --overwrite

## Results

| case | exit | wall s | validator | hard | parity | eligible | after_target | after_floor | best_before_target | break conc. viol. |
|---|---|---|---|---|---|---|---|---|---|---|
| CRICUT_CHAT | 0 | 14,163 | PASS | 0 | PASS | TRUE | 166 / 242 | 237 | 201 | 0 |
| SYNTH_H1 | 0 | 14,148 | PASS | 0 | PASS | TRUE | 143 / 168 | 167 | 168 | 0 |

**Memory:** the two engine processes together peaked at about 3.7 GB RSS. This was
sampled every 9 minutes, so it is not an exact peak. At least 11.8 GB stayed free
throughout.

**Release gates:** both cases scored PASS_WITH_QUALITY_WARNINGS. Gate 5 failed on
both, and both are labelled STAFFING_LIMITED: the break capacity is short by about
1 associate.

## Conclusion

The single-run DEEP path works end to end. On both cases the run completed within
its budget, published a validated schedule with 0 hard failures and full metric
parity, and stayed far from the memory limits that killed the earlier runs.

It is still not the recommended setting. On Chat, this 4-hour run reached an
after-break target of 166. In the F-03 experiment (`experiments/rc5_vs_final/`),
single 1-hour QUICK runs of the same engine on the same machine scored 169 to 184.
On H1, the run reached 143 against a QUICK mean of 143.7.

Two caveats limit that comparison. The inputs are not byte-identical: the packaged
Chat workbook carries the F-18 dropdown rewrite, so its sha256 differs. And this
run's CPU was oversubscribed. Even so, the result agrees with
`evidence/seed_portfolio_ab/RESULT.txt`: DEEP as best of 4 x 1-hour seeds stays
the default.
