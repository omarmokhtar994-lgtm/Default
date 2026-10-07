# H3: three-step Colab notebooks, local dry run (2026-10-07 ~19:10 Egypt)

Both notebooks were executed cell by cell on this machine with a stand-in for
`google.colab` (upload returns a chosen file, download/mount print), against a
package built from the current code. Dry-run-only settings: `SKIP_GUARDS =
True` (the 15-30 min offline gate is run separately by the package build),
`SEEDS = 1`, short `TIME_LIMIT`. Production defaults are unchanged.

| notebook | mode | steps | result |
|---|---|---|---|
| A (no Drive) | QUICK, 300 s | 1 Setup: package ZIP uploaded, extracted; 2 Your workbook: Cricut Voice ACCEPTED; 3 Run | exit 0, RELEASE VERDICT VOICE: RELEASABLE; results ZIP (4.4 MB) downloaded |
| B (Drive) | SMOKE, 120 s | 1 Setup: Drive mounted, ZIP found at MyDrive top level, results folder on Drive; 2 Your workbook: ACCEPTED; 3 Run | exit 2 (SMOKE builds no schedule, by design); verdict names it "diagnostics-only run"; ZIP written beside the Drive results |

Output look in the QUICK run folder: the top-level before-breaks file shows
Read Me First / Schedule / Coverage Before Breaks / Production Summary /
Validation Log with "Before Target / Before Floor"; the top-level after-breaks
file and all three alternatives show the same eight tabs with "After Target /
After Floor"; the raw engine copies are under debug/raw_engine_output/.

Found by the dry run and fixed: a SMOKE run's verdict read "reason not
recorded" (now "diagnostics-only run"); the notebook described SMOKE as "a
short trial run" (it builds no schedule).
