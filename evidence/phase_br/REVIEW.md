# Phase BR, Task 3: the forecast screens reviewed (2026-11-18)

Screens: `screens/` (made by `screens.py`: a made-up program, 60 weeks of Phone and Chat history, 1440 px and 390 px wide). The script found no console
error and no page wider than its window. Read against better-interface and web-interface-guidelines.

| # | Where | Finding | Decision |
|---|---|---|---|
| 1 | Staffing | The heading read "Volumes:" and stopped: the template's title list had no entry for the Staffing tab. | Fixed: "Volumes: people needed"; `TheHeadings` in `test_br_forecast_accuracy.py` (failed first). |
| 2 | Staffing | Opened from the tab, it says there is no forecast for the week until one is saved, with a link to the Forecast tab. | Leave: by design (Phase BM); the next step is named. |
| 3 | How we did | With no forecast saved: "-" in three tiles and "0 of 0" weeks over forecast. | Leave: the note above the tiles says why, and the tiles keep their place. |
| 4 | Forecast | The summary line names the suggestion and the trend's own miss on the last 8 weeks; the planner's number stays theirs. | Leave: matches the rules (nothing taken without a press). |
| 5 | Months ahead | Monospace figures, a range and how each month was worked out; the typed index shows 100 as a placeholder only. | Leave. |
| 6 | Phone width | Tabs wrap to two rows; every form field is full width; nothing scrolls sideways. | Leave. |
