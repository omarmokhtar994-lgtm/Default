# Phase BL: a full engine run with 8.5 hour and part-time associates

Run 2026-11-07 (Egypt time) with `engine/RUN_UNIVERSAL_PRODUCTION.py --mode QUICK --time-limit 240 --num-workers 2` on the example workbook
(`webapp/workbooks/Scheduler_Input_Example.xlsx`, 28 made-up "Synth Agent" associates), changed in a copy: Allowed Shift Durations Hours `9, 8.5, 5`,
five 8.5 hour and five 5 hour shifts added to the Shift Library, and four columns on the Schedule sheet for the first five associates.

| Associate | Schedule row | Schedule produced |
|---|---|---|
| Synth Agent 001, 002 | Shift Length 8.5 | 8.5 hour shifts only, 2 days off, 3 breaks a shift |
| Synth Agent 003, 004 | Part time, Shift Length 5, Off Days 3, Breaks 1 | 5 hour shifts only, 3 days off, 1 break a shift |
| Synth Agent 005 | Part time, Shift Length 5, Off Days 4, Breaks 1 | 5 hour shifts only, 4 days off, 1 break a shift |
| Synth Agent 006 to 028 | nothing | no 5 hour shift for any of them; 2 days off; 3 breaks a shift (the 8.5 hour shift is open to them, as it was not claimed by a part-timer) |

Outcome: PASS_WITH_QUALITY_WARNINGS, production eligible, independent validation PASS, clean-room check 0 violations. The quality warnings
(floor and severe gap ratios) are what five people on shorter or fewer days cost against a demand sheet made for full-timers.

What this run found, and was fixed before the package:
1. The first run passed the independent validator but was blocked (`FAIL_CLEAN_ROOM`): the clean-room check, which shares no code with the engine,
   still owed everyone two off days and the usual break set (`off_count` x3, `break_set` x52). It now reads the three columns
   (`tools/clean_room_check.py`; tests in `webapp/tests/test_bl_clean_room.py`).
2. A full-timer with no length was given 5 hour shifts. A shift length a Part time row names is now reserved for part-timers.

The input and outputs of the run are not kept in the repository (they are made-up and large); the run is repeated by `/tmp/bl/mixed.py` style
steps in `docs/howto/SCHEDULE_COLUMNS_AND_VOLUMES.md`: build the workbook with the columns, then run the wrapper.
