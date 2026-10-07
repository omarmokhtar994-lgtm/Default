# Phase F measurements (pre-registered 2026-10-07 ~07:20 Egypt, before any run)

Owner order: :30 starts first, then the break-rule what-if. Both are
measurements for the owner's decision; no default changes and no real
workbook is edited (copies only).

Runs (production runner, QUICK 3,600 s, 2 workers, seed 9000; the arms of one
program run side by side; one control per program shared by both questions):

| program | control | :30 starts on | break ratio 30% -> 40% |
|---|---|---|---|
| Cricut Chat (ready-to-edit) | yes | yes | yes |
| Cricut Voice (ready-to-edit) | yes | yes | - |
| NMG EN+SP (ready-to-edit) | yes | yes | - |
| AE IT B2B (owner's own workbook from the 2026-10-05 T90 run) | yes | - | yes |

10 runs in 5 side-by-side pairs, ~5 h: (Chat control, Chat :30),
(Voice control, Voice :30), (NMG EN+SP control, NMG EN+SP :30), (AE IT B2B
control, AE IT B2B 40%), (Chat 40%, Chat control repeat). The repeat gives the
Chat run-to-run noise on this engine and keeps every run paired under the
same machine load.

Reported per arm: intervals at target and at floor after breaks, before
breaks, validator status, release verdict (Phase F task 1), :30 shift-days
used, break concurrency.

Reading rule (single seed; Chat alone varies 155-179 between runs, so small
differences are noise):
* "worth considering" = arm >= control + 5 at target after breaks, floor not
  more than 1 lower, validator PASS;
* +1 to +4 = inconclusive (a second seed would be needed);
* otherwise "no gain measured".
The owner decides whether to turn :30 starts on, or change a break rule, per
program. Nothing changes by default.
