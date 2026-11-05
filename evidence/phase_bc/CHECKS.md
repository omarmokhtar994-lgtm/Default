# Phase BC checks (2026-10-26, Egypt time)

| Check | Result |
|---|---|
| Channel rotation | measured cause and sweep in `REQUESTS.md`; unit tests `test_bc_channel_rotation.py` (6) failed first; the Phase AY tick tests and the scenario tests still pass |
| Wheel carries on to the page | browser test failed first (page stayed at the same scroll position), passes; no panel sets `overscroll-behavior: contain` |
| Whole lists on Schedules, Channels (two pages), Week | browser test failed first, passes; choice kept in this browser |
| Clock-change words in a shift cell | server tests `test_bc_schedule_notes.py` failed against the old template; the cell is 88 px wide (was 1055 px); contrast 5.8, 7.8, 5.6 in the three looks |
