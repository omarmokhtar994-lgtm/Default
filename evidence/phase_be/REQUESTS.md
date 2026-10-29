# Phase BE requests and pre-registered rule

Owner, 2026-10-29: "I need now to look after how preference is being done in engine because it doesn't take it really into consideration even there is availability." Then: "Go ahead with the swap step."

## Rule (written before the code)
After the recommended schedule is chosen, one polish step, `preference_swap_polish`, may swap two associates' shifts on the same day. A swap is kept only when all of these hold:
1. Both associates have the same language and the same shift length, so coverage by language and length is unchanged.
2. Neither is nested, and neither cell is a Fixed request. Leave, hard OFF and OFF cells are never touched (only worked cells swap).
3. The sum of start-time distance to the Preference shift gets smaller, and neither associate's own distance gets bigger.
4. The same row rules the consistency polish uses hold for both rows (rest gap, last Saturday, maximum different shifts) and the cell is allowed (language window, demand fit, split rules).
5. Employee quality is no worse on the guarded measures, and `calculate_metrics` is no worse on every guarded coverage measure.
6. At the end the pair is still in the same candidate class, with no more hard failures from `validate_schedule` than before.
If no swap passes, the schedule is returned unchanged (same objects). The break pattern of each shift travels with the shift.

## What it does not touch
Stage 1, the joint model, the repair operators, break planning and the candidate choice. `Use Preferences = No` turns the step off.

## Acceptance (A/B on the shipped workbooks)
- Coverage, floors, break and validation metrics: identical.
- Preference satisfaction ratio: never lower; count of matched preference cells: not lower.
- Hard failures: unchanged (0). Protected baseline workbooks: byte-identical.
- Gate: `run_tests.sh` green with the raised minimum.
