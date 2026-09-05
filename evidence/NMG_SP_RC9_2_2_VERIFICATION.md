# NMG_SP on RC9.2.2 — the last scenario with no evidence

`NMG_SP` had never produced a result on any RC9.2.x build: its Colab archive
never uploaded intact. It was the only scenario in the set with nothing at all,
and its workbook still hashes to the RC9.1 baseline prefix
(`33f540ffa1df748d`), so gates 2 and 9 could decide rather than report
NOT_COMPARABLE.

Run: `--mode QUICK` (3600s), 4 workers, engine `b1acc9a949c30639`,
`Language Working Window = Off`.

## Against the RC9.1 baseline — matched exactly

| tier | RC9.1 | RC9.2.2 | delta |
|---|---|---|---|
| before target (90%) | 126 / 126 | **126 / 126** | +0 |
| before 100% | 125 | **125** | +0 |
| before 90% | 126 | **126** | +0 |
| before 80% | 126 | **126** | +0 |
| before floor | 126 | **126** | +0 |

`skeleton_retention_loss = 0`. RC9.1 solved this scenario to OPTIMAL, so there
was no room to be close: matching it is the only passing result.

## Gates

| gate | verdict |
|---|---|
| 2 — vs RC9.1 | **PASS_AGAINST_CONSOLIDATED_BASELINE** — target +0, floor +0 |
| 9 — vs RC9.1 | **PASS_AGAINST_CONSOLIDATED_BASELINE** |
| 8 — independent validation | **PASS**, 0 hard failures |
| 4 — quality retention | PASS_PROTECTED_NOT_EVALUATED — no protected minimum configured |
| 5 — break regression | PASS_DELTA_ONLY — target −3, floor −2 of 126; after-break 123/126 = 97.6%; no absolute standard configured |

`production_eligible = TRUE`, 0 no-break exceptions, 0 language gaps,
0 hard floor gaps.

## Two things worth stating rather than leaving in the CSV

**5 break-concurrency violations, max 3 concurrent observed.** The workbook sets
`break_max_concurrent_ratio = 0.3` with the gate in **warn** mode, so at 7
staffed the cap is 2 and the schedule ran 3. It is not a hard-rule breach —
gate 8 passed with zero hard failures — but it is a real operational finding on
a 7-person roster, and it would become a hard constraint if the gate mode were
set to enforce.

**Enabling the language working window would cost nothing here.** The Spanish
row is 17:00–02:00 with minimum 1, which is exactly the row that keeps the
feature's default at Off. Measured on this schedule with the mode Off:
`shifts_outside_language_window = 0` of 35 scheduled cells. So
`Rows With A Minimum` could be enabled on this workbook without changing the
result — unlike GDI, where it costs 4 floor gaps.

## What this does and does not close

It closes the only zero-evidence scenario, and it is the second scenario to
match RC9.1 exactly on this engine (after AE AR B2B at 168/168).

It does not make Cricut Voice verified — that scenario has still not been re-run
on this build, and it is the third of the three baseline-comparable workbooks.
