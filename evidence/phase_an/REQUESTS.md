# Phase AN: the owner's decisions on the ChatGPT work

© 2026 Omar Mokhtar. All rights reserved.

Received Fri 16 Oct 2026, from about 04:30 Egypt time. ChatGPT worked on a deep review of the website and sent three
rounds of files (the first candidate, "Hardened", and "Completed"). Claude checked each round against branch head
`6803ff4` (Phase AM): ran the full website suite, the browser tests and the release gate on a scratch copy, and read
the code.

## The owner's words

> A yes
> B No. Preserve AM for now
> C warn
> D drop it

Then, on the last round: "Final from chatgpt do the needful to go production".

## What the four answers mean

- **A. Keep ChatGPT's bug fixes.** Yes: zones read on each day's own clock rules; the RTA's "now" in the schedule's own
  zone; Go-to search checks the role's permissions; Fix channels applies all or nothing; overnight, no-staff and
  outside cover counted in Plan channels coverage.
- **B. Fix channels stays as in AM.** It plans today's own shifts only. Last night's people are held and counted;
  tomorrow's early shifts are not planned. ChatGPT had widened it to the whole 24 hours.
- **C. A short hand-set block on Plan channels only warns.** ChatGPT had refused it.
- **D. No draft lock.** ChatGPT had added revision tokens and a per-schedule lock on Plan breaks and Plan channels.

## What Claude found in the first round

Six existing tests broke (the new draft guard answered 409 to saves without its token). The rest of the suite passed.
Behaviour changes nobody asked for: Fix channels over 24 hours, the refusal of short blocks, the stricter scoring rule,
the draft lock. The "Hardened" round removed all four as the owner decided and added a child process for the channel
solver. The "Completed" round added safe handling of repeated and missing clock hours.

## Rulings (what Claude decided; each with what it costs if wrong)

1. **The channel solver runs in a child process** (`webapp/channel_solver.py`). Kept. Cost: about half a second and
   83 MB per solve. It keeps a native solver crash from taking the website down.
2. **The gate's parent-death test is not changed.** ChatGPT rewrote part of
   `tests_staged/test_rc9_2_19_joint_solve_isolation.py` because its sandbox has a different `/proc`. On the project's
   machines the original test passes, so the original stays. Rule: do not edit gate tests to suit a sandbox. Cost: none
   here; if the server's `/proc` differs, the gate would fail at the build, not in production.
3. **The `/proc` helper (`ortools_proc_compat.c`) is not in the repository.** It served ChatGPT's sandbox only.
4. **A repeated clock hour in a source workbook is refused, not guessed.** On a download in another zone, a time that
   occurs twice (or not at all) because the clocks change answers with a clear message, and the original-zone workbook
   is the way out. Cost: such a download fails on two nights a year.
5. **The RTA reads in the schedule's own zone in a window where one offset cannot hold**, and says so on the page. Old
   cross-zone forms in that window are refused before writing. Cost: the picked zone is ignored on those days.
6. **ChatGPT's own evidence logs are not copied in.** They record its sandbox failures. Claude's checks are in
   `CHECKS.md`.
