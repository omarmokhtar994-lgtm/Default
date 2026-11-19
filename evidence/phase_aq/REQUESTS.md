# Phase AQ: a language window that holds the whole shift (engine)

© 2026 Omar Mokhtar. All rights reserved.

Owner's request, Wed 21 Oct 2026: "can we do something related to language to take the 16:00 to 07:00 as shift start
and end not only shift start?" Background: `evidence/phase_ao/ENGINE_LANGUAGE_WINDOW.md`.

## What the engine does now

`shift_within_language_window` (engine/_tools/l632_universal_scheduler.py) is true when a shift's START is inside the
window. That was chosen on purpose: a first version required the whole shift inside the window, and on an 11-hour
window with 9-hour shifts it left 3 of 24 starts and made Stage 1 infeasible. So the default must not change.

## Proposal (owner decides)

An opt-in Instructions row, "Language Working Window Shift Rule": `START` (default, today's behaviour, blank = START)
or `WHOLE_SHIFT` (a shift is legal only when it starts and ends inside the window; 16:00 to 07:00 then allows 9-hour
starts from 16:00 to 22:00). It applies to the same rows the existing Language Working Window mode selects
(MINIMUM_ROWS or ALL_ROWS) and does nothing when that mode is OFF. The Allowed Shift Start Window is not touched.

## Pre-registered A/B rule (written before any code)

Input: the owner's GDI week of 18 Oct input (scratch copy; Quick; before breaks). Arm A: ALL_ROWS, START. Arm B: ALL_ROWS,
WHOLE_SHIFT. Accept B only if all hold:
1. B is feasible (RELEASABLE or equal status to A) within the same time limit.
2. No English, French or Bilingual shift in B starts or ends outside its window on any day (checked on the output).
3. Coverage at the 80% floor in B is not worse than A by more than 2 intervals of 140.
4. Default path unchanged: with the row blank, every existing gate test and the regression assets give the same bytes
   and the same result as before.
If 1 fails the row stays but the website says "may be infeasible on narrow windows". The independent validator must
agree with B (its own language-window check reads the same row).

## Build plan

Engine change only behind the new row; call sites of `shift_within_language_window` (about 8) get the rule; the
validator and the input vocabulary learn the row; the web input workbooks get the row (after "Language Working
Window"); test first (shift 23:00 to 08:00 refused under WHOLE_SHIFT, allowed under START); gate must pass.
Starts after the Phase AP package is out.
